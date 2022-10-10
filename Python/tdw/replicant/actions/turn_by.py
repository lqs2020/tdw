from typing import List
from tdw.replicant.actions.action import Action
from tdw.replicant.action_status import ActionStatus
from tdw.replicant.replicant_static import ReplicantStatic
from tdw.replicant.replicant_dynamic import ReplicantDynamic
from tdw.agents.image_frequency import ImageFrequency


class TurnBy(Action):
    """
    Turn by an angle.
    """

    def __init__(self, angle: float):
        """
        :param: The angle to turn by, in degrees.
        """

        super().__init__()
        self._angle: float = angle

    def get_initialization_commands(self, resp: List[bytes], static: ReplicantStatic, dynamic: ReplicantDynamic,
                                    image_frequency: ImageFrequency) -> List[dict]:
        commands = super().get_initialization_commands(resp=resp, static=static, dynamic=dynamic,
                                                       image_frequency=image_frequency)
        commands.append({"$type": "rotate_object_by",
                         "angle": self._angle,
                         "id": static.replicant_id,
                         "axis": "yaw",
                         "is_world": True,
                         "use_centroid": False})
        return commands

    def get_ongoing_commands(self, resp: List[bytes], static: ReplicantStatic, dynamic: ReplicantDynamic) -> List[dict]:
        self.status = ActionStatus.success
        return []
