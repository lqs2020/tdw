from abc import ABC, abstractmethod
from typing import List, Dict, Optional, Generic, TypeVar, Union
from copy import deepcopy
import numpy as np
from tdw.controller import Controller
from tdw.tdw_utils import TDWUtils
from tdw.add_ons.add_on import AddOn
from tdw.type_aliases import TARGET, POSITION, ROTATION
from tdw.librarian import HumanoidRecord, HumanoidLibrarian
from tdw.replicant.image_frequency import ImageFrequency
from tdw.replicant.collision_detection import CollisionDetection
from tdw.replicant.arm import Arm
from tdw.replicant.action_status import ActionStatus
from tdw.replicant.replicant_dynamic import ReplicantDynamic
from tdw.replicant.replicant_static import ReplicantStatic
from tdw.replicant.actions.action import Action
from tdw.replicant.actions.do_nothing import DoNothing
from tdw.replicant.actions.grasp import Grasp
from tdw.replicant.actions.drop import Drop
from tdw.replicant.actions.look_at import LookAt
from tdw.replicant.actions.reset_head import ResetHead
from tdw.replicant.actions.rotate_head import RotateHead


D = TypeVar("D", bound=ReplicantDynamic)
S = TypeVar("S", bound=ReplicantStatic)


class ReplicantBase(AddOn, Generic[D, S], ABC):
    """
    Abstract base class for Replicants.
    """

    def __init__(self, replicant_id: int = 0, position: POSITION = None, rotation: ROTATION = None,
                 image_frequency: ImageFrequency = ImageFrequency.once, name: str = "replicant_0",
                 target_framerate: int = 100):
        """
        :param replicant_id: The ID of the Replicant.
        :param position: The position of the Replicant as an x, y, z dictionary or numpy array. If None, defaults to `{"x": 0, "y": 0, "z": 0}`.
        :param rotation: The rotation of the Replicant in Euler angles (degrees) as an x, y, z dictionary or numpy array. If None, defaults to `{"x": 0, "y": 0, "z": 0}`.
        :param image_frequency: An [`ImageFrequency`](../replicant/image_frequency.md) value that sets how often images are captured.
        :param name: The name of the Replicant model.
        :param target_framerate: The target framerate. It's possible to set a higher target framerate, but doing so can lead to a loss of precision in agent movement.
        """

        super().__init__()
        """:field
        The initial position of the Replicant.
        """
        self.initial_position: Dict[str, float] = {"x": 0, "y": 0, "z": 0}
        """:field
        The initial rotation of the Replicant.
        """
        self.initial_rotation: Dict[str, float] = {"x": 0, "y": 0, "z": 0}
        self.__set_initial_position_and_rotation(position=position, rotation=rotation)
        """:field
        The ID of this replicant.
        """
        self.replicant_id: int = replicant_id
        """:field
        The Replicant's current [action](../replicant/actions/action.md). Can be None (no ongoing action).
        """
        self.action: Optional[Action] = None
        """:field
        An [`ImageFrequency`](../replicant/image_frequency.md) value that sets how often images are captured.
        """
        self.image_frequency: ImageFrequency = image_frequency
        """:field
        [The collision detection rules.](../replicant/collision_detection.md) This determines whether the Replicant will immediately stop moving or turning when it collides with something.
        """
        self.collision_detection: CollisionDetection = CollisionDetection()
        # This is used for collision detection. If the previous action is the "same" as this one, this action fails.
        self._previous_action: Optional[Action] = None
        # This is used when saving images.
        self._frame_count: int = 0
        # Initialize the Replicant metadata library.
        library_name = self._get_library_name()
        if library_name not in Controller.HUMANOID_LIBRARIANS:
            Controller.HUMANOID_LIBRARIANS[library_name] = HumanoidLibrarian(library_name)
        # The Replicant metadata record.
        self._record: HumanoidRecord = Controller.HUMANOID_LIBRARIANS[library_name].get_record(name)
        # The target framerate.
        self._target_framerate: int = target_framerate
        """:field
        The [`ReplicantStatic`](../replicant/replicant_static.md) data.
        """
        self.static: Optional[S] = None
        """:field
        The [`ReplicantDynamic`](../replicant/replicant_dynamic.md) data.
        """
        self.dynamic: Optional[D] = None

    def get_initialization_commands(self) -> List[dict]:
        """
        This function gets called exactly once per add-on. To re-initialize, set `self.initialized = False`.

        :return: A list of commands that will initialize this add-on.
        """

        # Add the replicant. Send output data: Replicants, Transforms, Bounds, Containment, and Framerate.
        commands = [{"$type": self._get_add_replicant_command(),
                     "name": self._record.name,
                     "position": self.initial_position,
                     "rotation": self.initial_rotation,
                     "url": self._record.get_url(),
                     "id": self.replicant_id},
                    {"$type": "set_target_framerate",
                     "framerate": self._target_framerate},
                    {"$type": self._get_send_replicants_command(),
                     "frequency": "always"},
                    {"$type": "send_transforms",
                     "frequency": "always"},
                    {"$type": "send_bounds",
                     "frequency": "always"},
                    {"$type": "send_containment",
                     "frequency": "always"},
                    {"$type": "send_framerate",
                     "frequency": "always"},
                    {"$type": "send_replicant_segmentation_colors"}]
        # Add empty objects to the Replicant for relative IK motion targets.
        commands.extend([{"$type": "attach_empty_object",
                          "id": self.replicant_id,
                          "empty_object_id": arm.value,
                          "position": {"x": 0, "y": 0, "z": 0}} for arm in [Arm.left, Arm.right]])
        return commands

    def on_send(self, resp: List[bytes]) -> None:
        """
        This is called within `Controller.communicate(commands)` after commands are sent to the build and a response is received.

        Use this function to send commands to the build on the next `Controller.communicate(commands)` call, given the `resp` response.
        Any commands in the `self.commands` list will be sent on the *next* `Controller.communicate(commands)` call.

        :param resp: The response from the build.
        """

        # If there isn't cached static data, assume we have the output data we need and cache it now.
        if self.static is None:
            self._cache_static_data(resp=resp)
        # Update the dynamic data per `communicate()` call.
        self._set_dynamic_data(resp=resp)
        # Don't do anything if there isn't an action or if the action is done.
        if self.action is None or self.action.done:
            return
        # Start or continue the action.
        else:
            # Initialize the action.
            if not self.action.initialized:
                # The action's status defaults to `ongoing`, but actions sometimes fail prior to initialization.
                if self.action.status == ActionStatus.ongoing:
                    # Initialize the action and get initialization commands.
                    self.action.initialized = True
                    initialization_commands = self.action.get_initialization_commands(resp=resp,
                                                                                      static=self.static,
                                                                                      dynamic=self.dynamic,
                                                                                      image_frequency=self.image_frequency)

                    # Most actions are `ongoing` after initialization, but they might've succeeded or failed already.
                    if self.action.status == ActionStatus.ongoing:
                        self.commands.extend(initialization_commands)
                    else:
                        self.commands.extend(self.action.get_end_commands(resp=resp,
                                                                          static=self.static,
                                                                          dynamic=self.dynamic,
                                                                          image_frequency=self.image_frequency))
            # Continue an ongoing action.
            else:
                # Get the ongoing action commands.
                action_commands = self.action.get_ongoing_commands(resp=resp, static=self.static, dynamic=self.dynamic)
                # This is an ongoing action. Append ongoing commands.
                if self.action.status == ActionStatus.ongoing:
                    self.commands.extend(action_commands)
                # This action is done. Append end commands.
                else:
                    self.commands.extend(self.action.get_end_commands(resp=resp,
                                                                      static=self.static,
                                                                      dynamic=self.dynamic,
                                                                      image_frequency=self.image_frequency))
            # This action ended. Remember it as the previous action.
            if self.action.status != ActionStatus.ongoing:
                # Mark the action as done.
                self.action.done = True
                # Remember the previous action.
                self._previous_action = deepcopy(self.action)

    def grasp(self, target: int, arm: Arm, angle: Optional[float] = 90, axis: Optional[str] = "pitch",
              relative_to_hand: bool = True, offset: float = 0) -> None:
        """
        Grasp a target object.

        The action fails if the hand is already holding an object. Otherwise, the action succeeds.

        When an object is grasped, it is made kinematic. Any objects contained by the object are parented to it and also made kinematic. For more information regarding containment in TDW, [read this](../../lessons/semantic_states/containment.md).

        :param target: The target object ID.
        :param arm: The [`Arm`](../replicant/arm.md) value for the hand that will grasp the target object.
        :param angle: Continuously (per `communicate()` call, including after this action ends), rotate the the grasped object by this many degrees relative to the hand. If None, the grasped object will maintain its initial rotation.
        :param axis: Continuously (per `communicate()` call, including after this action ends) rotate the grasped object around this axis relative to the hand. Options: `"pitch"`, `"yaw"`, `"roll"`. If None, the grasped object will maintain its initial rotation.
        :param relative_to_hand: If True, the object rotates relative to the hand holding it. If False, the object rotates relative to the Replicant. Ignored if `angle` or `axis` is None.
        :param offset: Offset the object's position from the Replicant's hand by this distance.
        """

        self.action = Grasp(target=target,
                            arm=arm,
                            dynamic=self.dynamic,
                            angle=angle,
                            axis=axis,
                            relative_to_hand=relative_to_hand,
                            offset=offset)

    def drop(self, arm: Arm, max_num_frames: int = 100, offset: Union[float, np.ndarray, Dict[str, float]] = 0.1) -> None:
        """
        Drop a held target object.

        The action ends when the object stops moving or the number of consecutive `communicate()` calls since dropping the object exceeds `self.max_num_frames`.

        When an object is dropped, it is made non-kinematic. Any objects contained by the object are parented to it and also made non-kinematic. For more information regarding containment in TDW, [read this](../../lessons/semantic_states/containment.md).

        :param arm: The [`Arm`](../replicant/arm.md) holding the object.
        :param max_num_frames: Wait this number of `communicate()` calls maximum for the object to stop moving before ending the action.
        :param offset: Prior to being dropped, set the object's positional offset. This can be a float (a distance along the object's forward directional vector). Or it can be a dictionary or numpy array (a world space position).
        """

        self.action = Drop(arm=arm, dynamic=self.dynamic, max_num_frames=max_num_frames, offset=offset)

    def look_at(self, target: TARGET, duration: float = 0.1, scale_duration: bool = True):
        """
        Look at a target object or position.

        The head will continuously move over multiple `communicate()` calls until it is looking at the target.

        :param target: The target. If int: An object ID. If dict: A position as an x, y, z dictionary. If numpy array: A position as an [x, y, z] numpy array.
        :param duration: The duration of the motion in seconds.
        :param scale_duration: If True, `duration` will be multiplied by `framerate / 60)`, ensuring smoother motions at faster-than-life simulation speeds.
        """

        self.action = LookAt(target=target, duration=duration, scale_duration=scale_duration)

    def rotate_head(self, axis: str, angle: float, duration: float = 0.1, scale_duration: bool = True):
        """
        Rotate the head by an angle around an axis.

        The head will continuously move over multiple `communicate()` calls until it is looking at the target.

        :param axis: The axis of rotation. Options: `"pitch"`, `"yaw"`, `"roll"`.
        :param angle: The target angle in degrees.
        :param duration: The duration of the motion in seconds.
        :param scale_duration: If True, `duration` will be multiplied by `framerate / 60)`, ensuring smoother motions at faster-than-life simulation speeds.
        """

        self.action = RotateHead(axis=axis, angle=angle, duration=duration, scale_duration=scale_duration)

    def reset_head(self, duration: float = 0.1, scale_duration: bool = True):
        """
        Reset the head to its neutral rotation.

        The head will continuously move over multiple `communicate()` calls until it is at its neutral rotation.

        :param duration: The duration of the motion in seconds.
        :param scale_duration: If True, `duration` will be multiplied by `framerate / 60)`, ensuring smoother motions at faster-than-life simulation speeds.
        """

        self.action = ResetHead(duration=duration, scale_duration=scale_duration)

    def reset(self, position: POSITION = None, rotation: ROTATION = None) -> None:
        """
        Reset the Replicant. Call this when you reset the scene.

        :param position: The position of the Replicant as an x, y, z dictionary or numpy array. If None, defaults to `{"x": 0, "y": 0, "z": 0}`.
        :param rotation: The rotation of the Replicant in Euler angles (degrees) as an x, y, z dictionary or numpy array. If None, defaults to `{"x": 0, "y": 0, "z": 0}`.
        """

        self.initialized = False
        self.action = None
        self._previous_action = None
        self._frame_count: int = 0
        self.collision_detection = CollisionDetection()
        self.__set_initial_position_and_rotation(position=position, rotation=rotation)
        self.commands.clear()
        self.dynamic = None
        self.static = None

    @abstractmethod
    def _get_library_name(self) -> str:
        """
        :return: The Replicant library name.
        """

        raise Exception()

    @abstractmethod
    def _get_add_replicant_command(self) -> str:
        """
        :return: The name of the command used to add the Replicant.
        """

        raise Exception()

    @abstractmethod
    def _get_send_replicants_command(self) -> str:
        """
        :return: The name of the command used to send output data.
        """

        raise Exception()

    @abstractmethod
    def _set_dynamic_data(self, resp: List[bytes]) -> None:
        """
        Set dynamic data.

        :param resp: The response from the build.
        """

        raise Exception()

    def _cache_static_data(self, resp: List[bytes]) -> None:
        """
        Cache static output data.

        :param resp: The response from the build.
        """

        self.static = self._get_replicant_static(resp=resp)
        # Set an initial action.
        self.action = DoNothing()
        # Add an avatar and set up its camera.
        self.commands.extend([{"$type": "create_avatar",
                               "type": "A_Img_Caps_Kinematic",
                               "id": self.static.avatar_id},
                              {"$type": "set_pass_masks",
                               "pass_masks": ["_img", "_id", "_depth"],
                               "avatar_id": self.static.avatar_id},
                              {"$type": "parent_avatar_to_replicant",
                               "position": {"x": -0.1, "y": -0.1, "z": 0},
                               "avatar_id": self.static.avatar_id,
                               "id": self.replicant_id},
                              {"$type": "enable_image_sensor",
                               "enable": False,
                               "avatar_id": self.static.avatar_id},
                              {"$type": "set_img_pass_encoding",
                               "value": False}])

    @abstractmethod
    def _get_replicant_static(self, resp: List[bytes]) -> S:
        """
        :param resp: The response from the build.

        :return: Static Replicant data.
        """

        raise Exception()

    @staticmethod
    def _arms_to_list(arm: Union[Arm, List[Arm]]) -> List[Arm]:
        """
        Converts a single `Arm` value to a list if needed.

        :param arm: Either a single `Arm` value or a list of `Arm` values.

        :return: A list of `Arm` values.
        """

        if isinstance(arm, Arm):
            return [arm]
        elif isinstance(arm, list):
            return arm
        else:
            raise Exception(f"Invalid arms: {arm}")

    def __set_initial_position_and_rotation(self, position: POSITION = None, rotation: ROTATION = None) -> None:
        """
        Set the initial position and rotation.

        :param position: The position of the Replicant as an x, y, z dictionary or numpy array. If None, defaults to `{"x": 0, "y": 0, "z": 0}`.
        :param rotation: The rotation of the Replicant in Euler angles (degrees) as an x, y, z dictionary or numpy array. If None, defaults to `{"x": 0, "y": 0, "z": 0}`.
        """

        if position is None:
            self.initial_position = {"x": 0, "y": 0, "z": 0}
        elif isinstance(position, dict):
            self.initial_position = position
        elif isinstance(position, np.ndarray):
            self.initial_position = TDWUtils.array_to_vector3(position)
        else:
            raise Exception(position)
        if rotation is None:
            self.initial_rotation = {"x": 0, "y": 0, "z": 0}
        elif isinstance(rotation, dict):
            self.initial_rotation = rotation
        elif isinstance(rotation, np.ndarray):
            self.initial_rotation = TDWUtils.array_to_vector3(rotation)