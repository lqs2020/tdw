from abc import ABC
from typing import Dict
from tdw.container_data.container_tag import ContainerTag


class ContainerShape(ABC):
    """
    Abstract base class for container shapes, which are used to detect containment events.
    """

    def __init__(self, tag: ContainerTag, position: Dict[str, float]):
        """
        :param tag: The shapes's semantic [`ContainerTag`](container_tag.md).
        :param position: The position of the shape relative to the parent object.
        """

        """:field
        The collider's semantic [`ContainerTag`](container_tag.md).
        """
        self.tag: ContainerTag = tag
        """:field
        The position of the shape relative to the parent object.      
        """
        self.position: Dict[str, float] = {"x": round(position["x"], 8),
                                           "y": round(position["y"], 8),
                                           "z": round(position["z"], 8)}

    def to_dict(self) -> dict:
        """
        :return: A JSON-able dictionary.
        """

        # Convert the tag to a class name.
        d = {"$type": self.__class__.__name__,
             "tag": self.tag.name}
        # Add everything else.
        d.update({k: v for k, v in self.__dict__.items() if k != "tag"})
        return d
