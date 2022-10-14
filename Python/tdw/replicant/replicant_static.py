from typing import Dict, List
from tdw.output_data import OutputData, Replicants, StaticEmptyObjects
from tdw.agents.arm import Arm
from tdw.replicant.replicant_body_part import ReplicantBodyPart, BODY_PARTS


class ReplicantStatic:
    """
    Static data for the Replicant.
    """

    """:class_var
    A dictionary of arms and their constituent joints.
    """
    ARM_JOINTS: Dict[Arm, List[ReplicantBodyPart]] = {Arm.left: [__b for __b in ReplicantBodyPart if __b.name.endswith("_l")],
                                                      Arm.right: [__b for __b in ReplicantBodyPart if __b.name.endswith("_r")]}

    def __init__(self, replicant_id: int, resp: List[bytes]):
        """
        :param replicant_id: The ID of the Replicant.
        :param resp: The response from the build.
        """

        """:field
        The ID of the Replicant.
        """
        self.replicant_id: int = replicant_id
        """:field
        The ID of the Replicant's avatar (camera). This is used internally for API calls.
        """
        self.avatar_id: str = str(replicant_id)
        """:field
        Body parts by name. Key = [`ReplicantBodyPart`](replicant_body_part.md). Value = Object ID.
        """
        self.body_parts: Dict[ReplicantBodyPart, int] = dict()
        """:field
        The IDs of each empty object (affordance point).
        """
        self.empty_object_ids: List[int] = list()
        """:field
        The IDs of each empty object's (affordance point's) parent object.
        """
        self.empty_object_parent_ids: List[int] = list()
        """:field
        The Replicant's hands. Key = [`Arm`](../agents/arm.md). Value = Object ID.
        """
        self.hands: Dict[Arm, int] = dict()
        for i in range(len(resp) - 1):
            r_id = OutputData.get_data_type_id(resp[i])
            # Get Replicants data.
            if r_id == "repl":
                replicants = Replicants(resp[i])
                for j in range(replicants.get_num()):
                    object_id = replicants.get_id(j)
                    # We found the ID of this replicant.
                    if object_id == self.replicant_id:
                        # The order of the data is always:
                        # [replicant_0, replicant_0_hand_l, replicant_0_hand_r, ... ,replicant_1, replicant_1_hand_l, ... ]
                        # So, having found the ID of this replicant, we know that the next IDs are those of its body parts.
                        for k in range(len(BODY_PARTS)):
                            # Cache the ID.
                            self.body_parts[BODY_PARTS[k]] = replicants.get_id(j + k + 1)
                        break
            # Get the empty object IDs.
            elif r_id == "stem":
                static_empty_objects: StaticEmptyObjects = StaticEmptyObjects(resp[i])
                for j in range(static_empty_objects.get_num()):
                    self.empty_object_ids.append(static_empty_objects.get_empty_object_id(j))
                    self.empty_object_parent_ids.append(static_empty_objects.get_object_id(j))
        """:field
        The Replicant's hands. Key = [`Arm`](../agents/arm.md). Value = Object ID.
        """
        self.hands: Dict[Arm, int] = {Arm.left: self.body_parts[ReplicantBodyPart.hand_l],
                                      Arm.right: self.body_parts[ReplicantBodyPart.hand_r]}
        """:field
        Body parts by ID. Key = Object ID. Value = [`ReplicantBodyPart`](replicant_body_part.md).
        """
        self.body_parts_by_id: Dict[int, ReplicantBodyPart] = {v: k for k, v in self.body_parts.items()}
