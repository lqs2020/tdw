from typing import List, Union
from json import loads
from pathlib import Path
import xml.etree.ElementTree as ElementTree
from tdw.add_ons.add_on import AddOn
from tdw.asset_bundle_creator import AssetBundleCreator
from tdw.robot_creator import RobotCreator
from tdw.lisdf_data.lisdf_robot_metadata import LisdfRobotMetadata


class LisdfReader(AddOn):
    """
    Parse an [.lisdf file](https://learning-and-intelligent-systems.github.io/kitchen-worlds/tut-lisdf/).

    .lisdf models can't be directly added into TDW; they must first be converted into asset bundles. These asset bundles will be saved to the local disk, meaning that converting .lisdf data to asset bundles is a one-time process.

    Note that this is only a partial implementation of an .lisdf parser. More functionality will be added over time.

    When `read()` is called, asset bundles are automatically generated if they don't already exist. Then this add-on appends commands to the controller to add the objects to the scene.
    """

    def __init__(self):
        super().__init__()
        self.initialized = True

    def read(self, lisdf_path: Union[str, Path], output_directory: Union[str, Path], overwrite: bool = False,
             cleanup: bool = True, robot_metadata: List[LisdfRobotMetadata] = None, send_commands: bool = True,
             quiet: bool = False, display: str = ":0", unity_editor_path: Union[Path, str] = None) -> None:
        """
        Read an .lisdf file and send commands to the build to add the objects to the scene.
        If corresponding asset bundles don't exist in `asset_bundles_directory` or if `overwrite == True`, this function will call the `asset_bundle_creator` Unity project and generate new asset bundles.

        Example source directory:

        ```
        source_directory/
        ....scene/
        ........kitchen.lisdf
        ....models/
        ........counter/
        ............urdf/
        ................counter_0.urdf
        ................textured_objs/
        ....................01.obj
        .................... (etc.)
        ........ (etc.)
        ```

        - In this example, set `lisdf_path` to `"source_directory/scene/kitchen.lisdf"`
        - The location of the .urdf files must match the relative path in `kitchen.lisdf` (in this case, `../models.counter/urdf/counter_0.urdf`)
        - The location of the .obj files must match the relative path in the .urdf files (in this case, `counter_0.urdf` is expecting meshes to be in `textured_objs/`)

        Example output directory after running `LisdfReader.read()`:

        ```
        output_directory/
        ....counter_0/
        ........model.json
        ........Darwin/
        ............counter_0
        ........Linux/
        ............counter_0
        ........Windows/
        ............counter_0
        ....commands.json
        ....log.txt
        ```

        - `model.json` is a JSON representation of the model structure. This can be useful for debugging.
        - `Darwin/counter_0`, `Linux/counter_0` and `Windows/counter_0` are the platform-specific asset bundles.
        - `commands.json` is the list of commands that can be sent to the build. They will be sent automatically if the `send_commands=True`.
        - `log.txt` is a log of all events while creating asset bundles, including errors.

        :param lisdf_path: The path to the .lisdf file as either a string or [`Path`](https://docs.python.org/3/library/pathlib.html).
        :param output_directory: The directory of the object asset bundles as either a string or [`Path`](https://docs.python.org/3/library/pathlib.html). If it doesn't exist, it will be created while the .lisdf models are being converted.
        :param overwrite: If True, overwrite any asset bundles in `asset_bundles_directory`. If False, skip converting models if the asset bundles already exist. This should usually be False, especially if you're using robot asset bundles generated by [`RobotCreator`](../robot_creator.md).
        :param cleanup: If True, delete intermediary files such as .prefab files generated while creating asset bundles.
        :param robot_metadata: If not None, this is a list of [`LisdfRobotMetadata`](../lisdf_data/lisdf_robot_metadata.md). **If there are any robots in the scene, they must be added to this list, or else they will be imported incorrectly.**
        :param send_commands: If True, the commands generated from the .lisdf file will be sent the next time `c.communicate()` is called.
        :param quiet: If True, don't print any messages to console.
        :param display: The display to launch Unity Editor on. Ignored if this isn't Linux.
        :param unity_editor_path: The path to the Unity Editor executable, for example `C:/Program Files/Unity/Hub/Editor/2020.3.24f1/Editor/Unity.exe`. If None, this script will try to find Unity Editor automatically.
        """

        if isinstance(lisdf_path, Path):
            src_str = str(lisdf_path.resolve())
            src_path = lisdf_path
        elif isinstance(lisdf_path, str):
            src_str = lisdf_path
            src_path = Path(lisdf_path)
        else:
            raise Exception(lisdf_path)
        if isinstance(output_directory, Path):
            dst_str = str(output_directory.resolve())
            dst_path = output_directory
        elif isinstance(output_directory, str):
            dst_str = output_directory
            dst_path = Path(output_directory)
        else:
            raise Exception(output_directory)
        if not dst_path.exists():
            dst_path.mkdir(parents=True)
        # Fix Windows paths.
        dst_str = dst_str.replace("\\", "/")
        src_str = src_str.replace("\\", "/")
        ignore_includes = []
        # Generate robot asset bundles.
        if robot_metadata is not None:
            for rm in robot_metadata:
                # Ignore the robot.
                ignore_includes.append(rm.name)
                robot_output_directory = dst_path.joinpath(rm.name)
                # The asset bundles exist.
                if not overwrite and AssetBundleCreator.asset_bundles_exist(name=rm.name,
                                                                            output_directory=robot_output_directory):
                    if not quiet:
                        print(f"Found asset bundles for robot: {rm.name}. These will be used and not overwritten.")
                    continue
                r = RobotCreator(quiet=quiet, display=display, unity_editor_path=unity_editor_path)
                element_tree = ElementTree.parse(src_str)
                includes = element_tree.getroot().find("world").findall("include")
                includes = [e for e in includes if e.attrib["name"] == rm.name]
                assert len(includes) > 0, f"Couldn't find <include> elemement for: {rm.name}."
                urdf_path = src_path.parent.joinpath(includes[0].find("uri").text).resolve()
                # Fix the .urdf file.
                urdf_path = RobotCreator.fix_urdf(urdf_path=urdf_path,
                                                  link_name_excludes_regex=rm.link_name_excludes_regex,
                                                  link_exclude_types=rm.link_exclude_types)
                r.source_file_to_asset_bundles(source_file=urdf_path, output_directory=robot_output_directory)
                if not quiet:
                    robot_log_path = robot_output_directory.joinpath("log.txt")
                    if robot_log_path.exists():
                        print(robot_log_path.read_text(encoding="utf-8"))
                    else:
                        print(f"Error! Log not found: {robot_log_path}")
                assert AssetBundleCreator.asset_bundles_exist(name=rm.name, output_directory=robot_output_directory),\
                    f"Failed to create asset bundles from: {urdf_path}"
        # Generate asset bundles if needed.
        args = [f'-source="{src_str}"',
                f'-output_directory="{dst_str}"']
        if overwrite:
            args.append("-overwrite")
        if cleanup:
            args.append("-cleanup")
        if len(ignore_includes) > 0:
            args.append('-ignore_includes="' + ",".join(ignore_includes) + '"')
        a = AssetBundleCreator(quiet=quiet, display=display, unity_editor_path=unity_editor_path)
        a.call_unity(class_name="LisdfReader",
                     method="Read",
                     args=args,
                     log_path=dst_path.joinpath("log.txt"))
        # Send the commands, if any.
        commands_path = dst_path.joinpath("commands.json")
        if send_commands and commands_path.exists():
            self.commands.extend(loads(commands_path.read_text(encoding="utf-8")))

    def on_send(self, resp: List[bytes]) -> None:
        pass

    def get_initialization_commands(self) -> List[dict]:
        return []
