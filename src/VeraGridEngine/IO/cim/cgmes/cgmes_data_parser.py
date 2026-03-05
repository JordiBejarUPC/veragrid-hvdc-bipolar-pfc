# This Source Code Form is subject to the terms of the Mozilla Public
# License, v. 2.0. If a copy of the MPL was not distributed with this
# file, You can obtain one at https://mozilla.org/MPL/2.0/.
# SPDX-License-Identifier: MPL-2.0

import os
import zipfile
from typing import BinaryIO, Dict, List, Union, Callable, Tuple
import xml.etree.ElementTree as ET
from VeraGridEngine.data_logger import DataLogger
from VeraGridEngine.IO.base.base_circuit import BaseCircuit
from VeraGridEngine.enumerations import CGMESVersions


def find_id(child: ET.Element):
    """
    Try to find the ID of an element
    :param child: XML element
    :return: RDFID
    """
    obj_id = ''
    for attr, value in child.attrib.items():
        if 'about' in attr.lower() or 'resource' in attr.lower():
            if ':' in value:
                obj_id = value.split(':')[-1]
            else:
                obj_id = value
        elif 'id' in attr.lower():
            obj_id = value

    return obj_id.replace('_', '').replace('#', '')


def find_class_name(child: ET.Element):
    """
    Try to find the CIM class name
    :param child: XML element
    :return: class name
    """
    if '}' in child.tag:
        class_name = child.tag.split('}')[-1]
    else:
        class_name = child.tag

    if '.' in class_name:
        class_name = class_name.split('.')[-1]

    return class_name


def fix_child_result_datatype(child_result: Dict):
    for key, val in child_result.items():
        if val == "true":
            child_result[key] = True
        elif val == "false":
            child_result[key] = False
    return child_result


def _convert_leaf_value(value: str) -> Union[str, bool]:
    """
    Convert XML leaf text to the expected scalar type.

    :param value: XML leaf text value
    :return: Converted scalar value
    """
    if value == "true":
        return True
    elif value == "false":
        return False
    else:
        return value


def _append_unique_value(container: Dict[str, Union[str, bool, dict, list]],
                         key: str,
                         value: Union[str, bool, dict]) -> None:
    """
    Append a value in a stable manner, preserving scalar form when unique.

    :param container: Property dictionary to modify in place
    :param key: Property name
    :param value: Property value
    """
    current_value = container.get(key, None)
    if current_value is None:
        container[key] = value
    else:
        if isinstance(current_value, list):
            if value not in current_value:
                current_value.append(value)
        else:
            if current_value != value:
                container[key] = [current_value, value]


def parse_xml_stream_to_dict(xml_stream: BinaryIO) -> Dict[str, Dict[str, Dict[str, str]]]:
    """
    Parse XML stream to CGMES dictionary format using streaming events.

    :param xml_stream: Binary file-like XML stream
    :return: Dictionary representing parsed CGMES objects
    """
    result: Dict[str, Dict[str, Dict[str, str]]] = dict()
    stack: List[Dict[str, Union[str, bool, Dict[str, Union[str, bool, dict]], int]]] = list()

    for event, element in ET.iterparse(xml_stream, events=("start", "end")):
        if event == "start":
            frame = {
                "class_name": find_class_name(element),
                "obj_id": find_id(element),
                "props": dict(),
                "depth": len(stack)
            }
            stack.append(frame)
        else:
            frame = stack.pop()
            class_name = frame["class_name"]
            obj_id = frame["obj_id"]
            props = frame["props"]
            depth = frame["depth"]

            if depth == 0:
                # root rdf:RDF element
                element.clear()
                continue

            if depth == 1:
                class_objects = result.get(class_name, None)
                if class_objects is None:
                    class_objects = dict()
                    result[class_name] = class_objects
                class_objects[obj_id] = props
            else:
                parent_frame = stack[-1]
                parent_props = parent_frame["props"]

                if len(props) > 0:
                    # Keep compatibility with legacy recursive parser for nested object values.
                    nested_value = {obj_id: fix_child_result_datatype(props)}
                    _append_unique_value(parent_props, class_name, nested_value)
                else:
                    text_value = element.text
                    if text_value is None:
                        _append_unique_value(parent_props, class_name, obj_id)
                    else:
                        stripped = text_value.strip()
                        if stripped == "":
                            _append_unique_value(parent_props, class_name, obj_id)
                        else:
                            _append_unique_value(parent_props, class_name, _convert_leaf_value(stripped))

            element.clear()

    return result


def merge(A: Dict[str, Dict[str, Dict[str, str]]],
          B: Dict[str, Dict[str, Dict[str, str]]],
          logger: DataLogger):
    """
    Modify A using B
    :param A: CIM data dictionary to be modified in-place
    :param B: CIM data dictionary used to modify A
    :param logger: DataLogger to fill in logs
    """
    # for each category in B
    for class_name_b, class_obj_dict_b in B.items():

        class_obj_dict_a = A.get(class_name_b, None)

        if class_obj_dict_a is None:
            # the category does not exist in A, just copy it from B
            A[class_name_b] = class_obj_dict_b

        else:

            # for every object in the category from B
            for rdfid, obj_b in class_obj_dict_b.items():

                obj_a = class_obj_dict_a.get(rdfid, None)

                if obj_a is None:
                    # the object in B does not exist in A, copy it
                    class_obj_dict_a[rdfid] = obj_b
                else:
                    # the object in B already has an entry in A, modify it

                    # for each property
                    for prop_name, value_b in obj_b.items():

                        value_a = obj_a.get(prop_name, None)

                        if value_a is None:
                            # the property does not exist in A, add it
                            obj_a[prop_name] = value_b
                        else:
                            if value_b != value_a:
                                # the value exists in A, and the value in B is not None, add it
                                obj_a[prop_name] = value_b
                                logger.add_warning("Overwriting value",
                                                   device=str(obj_a),
                                                   device_class=class_name_b,
                                                   device_property=prop_name,
                                                   value=value_b,
                                                   expected_value=value_a)
                            else:
                                # the assigning value from B is the same as the already stored in A
                                pass


def sort_cgmes_files(links: List[Tuple[str, str, str]]) -> List[str]:
    """
    Sorts the CIM files in the preferred reading order
    :param links: list of filename, model id, dependent on model id
    :return: sorted list of file names
    """

    file_name_model_dict = dict()
    for filename, model_id, dependent_id in links:
        file_name_model_dict[model_id] = filename

    deps = list()
    items = list()
    for filename, model_id, dependent_id in links:
        if dependent_id == '':
            deps.insert(0, model_id)
            items.insert(0, filename)
        else:
            found = False
            i = 0
            if len(deps) > 0:
                while not found and i < len(deps):
                    if deps[i] == dependent_id:
                        deps.insert(i + 1, model_id)
                        items.insert(i + 1, filename)
                        found = True
                    i += 1
                if not found:
                    deps.append(model_id)
                    items.append(filename)
            else:
                deps.append(model_id)
                items.append(filename)

    return items


class CgmesDataParser(BaseCircuit):
    """
    Class to read any cgmes-like set of files
    """

    def __init__(self,
                 text_func: Union[Callable, None] = None,
                 progress_func: Union[Callable, None] = None,
                 logger=DataLogger()):
        """
        CIM circuit constructor
        :param text_func: text callback function (optional)
        :param progress_func: progress callback function (optional)
        :param logger: DataLogger
        """
        BaseCircuit.__init__(self)

        self.text_func = text_func
        self.progress_func = progress_func
        self.logger: DataLogger = logger

        # file: Cim data of the file
        self.parsed_data = dict()

        # merged CGMES data (dictionary representation of the xml data)
        self.data: Dict[str, Dict[str, Dict[str, str]]] = dict()

        # boundary set data
        self.boundary_set: Dict[str, Dict[str, Dict[str, str]]] = dict()

        # store the CGMES version from the data files
        self.cgmes_version: Union[None, CGMESVersions] = None

    def emit_text(self, val: str) -> None:
        """
        Emit text via the callback
        :param val: text value
        """
        if self.text_func is not None:
            self.text_func(val)

    def emit_progress(self, val: float) -> None:
        """
        Emit floating point values via the callback
        :param val: numeric value
        """
        if self.progress_func is not None:
            self.progress_func(val)

    def load_files(self, files: List[str]) -> None:
        """
        Load CIM file
        :param files: list of CIM files (.xml or .zip)
        """

        cgmes2_4_15_uri = ["http://entsoe.eu/CIM/EquipmentCore/3/1",
                           "http://entsoe.eu/CIM/EquipmentOperation/3/1",
                           "http://entsoe.eu/CIM/EquipmentShortCircuit/3/1",
                           "http://entsoe.eu/CIM/Topology/4/1",
                           "http://entsoe.eu/CIM/SteadyStateHypothesis/1/1",
                           "http://entsoe.eu/CIM/StateVariables/4/1"]
        cgmes3_0_0_uri = ["http://iec.ch/TC57/ns/CIM/CoreEquipment-EU/3.0",
                          "http://iec.ch/TC57/ns/CIM/SteadyStateHypothesis-EU/3.0",
                          "http://iec.ch/TC57/ns/CIM/StateVariables-EU/3.0",
                          "http://iec.ch/TC57/ns/CIM/Topology-EU/3.0"]
        def process_parsed_file(file_name: str, file_cgmes_data: Dict[str, Dict[str, Dict[str, str]]]) -> None:
            full_models_dict = file_cgmes_data.get('FullModel', None)
            difference_full_models_dict = file_cgmes_data.get('DifferenceModel', None)

            if full_models_dict:
                model_keys = list(file_cgmes_data['FullModel'])
                if len(model_keys) == 1:  # there must be exacly one FullModel
                    model_info = file_cgmes_data['FullModel'][model_keys[0]]
                    self.parsed_data[file_name] = file_cgmes_data
                    profile = model_info.get('profile', '')

                    if isinstance(profile, list):
                        for prof in profile:
                            if prof in cgmes2_4_15_uri:
                                self.cgmes_version = CGMESVersions.v2_4_15
                            elif prof in cgmes3_0_0_uri:
                                self.cgmes_version = CGMESVersions.v3_0_0

                        if len(profile) > 0 and 'Boundary' in profile[0]:
                            merge(self.boundary_set, file_cgmes_data, self.logger)
                        else:
                            merge(self.data, file_cgmes_data, self.logger)
                    else:
                        if profile in cgmes2_4_15_uri:
                            self.cgmes_version = CGMESVersions.v2_4_15
                        elif profile in cgmes3_0_0_uri:
                            self.cgmes_version = CGMESVersions.v3_0_0

                        if 'Boundary' in profile:
                            merge(self.boundary_set, file_cgmes_data, self.logger)
                        else:
                            merge(self.data, file_cgmes_data, self.logger)
                else:
                    self.logger.add_error("File does not contain exactly one FullModel",
                                          device=file_name,
                                          device_class="",
                                          device_property='FullModel', value="", expected_value="FullModel",
                                          comment="This is not a proper CGMES file")
            elif difference_full_models_dict:
                model_keys = list(file_cgmes_data['DifferenceModel'])
                if len(model_keys) == 1:  # there must be exacly one Ontology
                    model_info = file_cgmes_data['DifferenceModel'][model_keys[0]]
                    self.parsed_data[file_name] = file_cgmes_data
                    profile = model_info.get('priorVersion', '')
                    self.cgmes_version = model_info.get('versionInfo', '')

                    for prof in profile:
                        if prof in cgmes2_4_15_uri:
                            self.cgmes_version = CGMESVersions.v2_4_15
                        elif prof in cgmes3_0_0_uri:
                            self.cgmes_version = CGMESVersions.v3_0_0

                    if 'Boundary' in profile:
                        merge(self.boundary_set, file_cgmes_data, self.logger)
                    else:
                        merge(self.data, file_cgmes_data, self.logger)
                else:
                    self.logger.add_error("File does not contain exactly one DifferenceModel",
                                          device=file_name,
                                          device_class="",
                                          device_property='DifferenceModel', value="", expected_value="DifferenceModel",
                                          comment="This is not a proper CGMES file")
            else:
                self.logger.add_error("File does not contain any FullModel or DifferenceModel",
                                      device=file_name,
                                      device_class="",
                                      device_property='FullModel', value="", expected_value="FullModel",
                                      comment="This is not a proper CGMES file")

        xml_files: List[str] = list()
        zip_members: Dict[str, List[str]] = dict()
        for path in files:
            _, file_extension = os.path.splitext(path)
            ext = file_extension.lower()
            if ext == ".xml":
                xml_files.append(path)
            elif ext == ".zip":
                try:
                    with zipfile.ZipFile(path) as zip_ptr:
                        members: List[str] = list()
                        for member in zip_ptr.namelist():
                            _, member_ext = os.path.splitext(member)
                            if member_ext.lower() == ".xml":
                                members.append(member)
                        zip_members[path] = members
                except zipfile.BadZipFile:
                    self.logger.add_error("BadZipFile", value=path)
                    print(f"BadZipFile {path}")

        n_items = len(xml_files) + sum(len(members) for members in zip_members.values())
        i = 0

        for xml_path in xml_files:
            file_name = os.path.basename(xml_path)
            name, _ = os.path.splitext(file_name)
            self.emit_text('Parsing xml structure of ' + name)
            with open(xml_path, "rb") as file_ptr:
                file_cgmes_data = parse_xml_stream_to_dict(file_ptr)
            process_parsed_file(file_name=file_name, file_cgmes_data=file_cgmes_data)
            if n_items > 0:
                self.emit_progress((i + 1) / n_items * 100)
            i += 1

        for zip_path, members in zip_members.items():
            with zipfile.ZipFile(zip_path) as zip_ptr:
                for member_name in members:
                    file_name = os.path.basename(member_name)
                    name, _ = os.path.splitext(file_name)
                    self.emit_text('Parsing xml structure of ' + name)
                    with zip_ptr.open(member_name) as file_ptr:
                        file_cgmes_data = parse_xml_stream_to_dict(file_ptr)
                    process_parsed_file(file_name=file_name, file_cgmes_data=file_cgmes_data)
                    if n_items > 0:
                        self.emit_progress((i + 1) / n_items * 100)
                    i += 1

        self.emit_text('Parsing done!')

    # def set_cgmes_version(self, profile):
    #     if profile == "":
    #         pass
