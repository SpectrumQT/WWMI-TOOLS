
from typing import Union, List, Dict

from dataclasses import dataclass

from ..buffers.byte_buffer import ByteBuffer, IndexBuffer

from .filename_parser import ShaderType, SlotType, SlotId, CallDescriptor, ResourceDescriptor
from .dict_filter import DictFilter, FilterCondition, Filter
from .dump_parser import Dump


@dataclass
class Slot:
    shader_id: str
    shader_type: ShaderType
    slot_type: SlotType
    slot_id: SlotId = None


@dataclass
class ShaderMap:
    shader_type: ShaderType
    inputs: List[Slot]
    outputs: List[Slot]
    # with_resources: List[Slot] = []
    # without_resources: List[Slot] = []


@dataclass
class BranchCall:
    call: CallDescriptor
    resources: Dict[str, Union[ResourceDescriptor, ByteBuffer, IndexBuffer]] = None


@dataclass
class ShaderCallBranch:
    shader_id: str
    calls: List[BranchCall]
    nested_branches: List['ShaderCallBranch'] = None

    def get_call(self, call_id):
        for branch_call in self.calls:
            if branch_call.call.id == call_id:
                return branch_call


@dataclass
class CallsCollector:
    dump: Dump
    shader_data_pattern: Dict[str, ShaderMap]
    call_branches: Dict[str, ShaderCallBranch] = None

    def __post_init__(self):
        self.cache = {}
        self.call_branches = self.get_call_branches()

    def get_call_branches(self):
        call_branches = {}

        root_shaders = self.get_root_shaders(self.shader_data_pattern)

        for shader_id in root_shaders:

            shader_map = self.shader_data_pattern[shader_id]

            branch = ShaderCallBranch(shader_id=shader_id, calls=[], nested_branches=[])

            for output_slot in shader_map.outputs:

                root_shader_resource_candidates = self.get_all_slot_resources(shader_map.shader_type, output_slot)

                output_hashes = []

                for resource_raw, root_resource in root_shader_resource_candidates.items():

                    # Quick hack to allow short-cirquit shader on itself
                    if output_slot.shader_id == shader_id:

                        for input_slot in shader_map.inputs:
                            if input_slot.shader_id != shader_id:
                                continue
                            input_filter_attributes = {
                                'call_id': root_resource.call_id,  # ID of child call should differ from parent call
                            }
                            input_candidate_resources = DictFilter(Filter(
                                attributes=input_filter_attributes,
                                dictionaries=self.get_all_slot_resources(shader_map.shader_type, input_slot)
                            )).filtered_dict
                            if len(input_candidate_resources) > 0:
                                continue

                        branch.calls.append(BranchCall(call=root_resource.call))
                        continue

                    nested_branch = self.resolve_branch(output_slot.shader_id, self.shader_data_pattern, root_resource, shader_id)

                    if nested_branch is None:
                        continue

                    if root_resource.hash in output_hashes:
                        branch.calls.append(BranchCall(call=root_resource.call))
                        continue
                    else:
                        output_hashes.append(root_resource.hash)

                    if isinstance(nested_branch, list):
                        branch.nested_branches.extend(nested_branch)
                    else:
                        branch.nested_branches.append(nested_branch)

                    branch.calls.append(BranchCall(call=root_resource.call))

            call_branches[shader_id] = branch

        return call_branches

    def resolve_branch(self, shader_id, shader_data_pattern, parent_resource, parent_shader_id):
        shader_map = shader_data_pattern[shader_id]

        input_slot = None
        for mapped_input_slot in shader_map.inputs:
            if parent_shader_id == mapped_input_slot.shader_id:
                input_slot = mapped_input_slot
        if input_slot is None:
            return None

        branch = ShaderCallBranch(shader_id=shader_id, calls=[], nested_branches=[])

        input_filter_attributes = {
            '!call_id': parent_resource.call_id,  # ID of child call should differ from parent call
            'hash': parent_resource.hash,  # Hash of input resource should be the same as one of parent's output
        }

        input_candidate_resources = DictFilter(Filter(
            attributes=input_filter_attributes,
            dictionaries=self.get_all_slot_resources(shader_map.shader_type, input_slot)
        )).filtered_dict

        if len(input_candidate_resources) == 0:
            return None

        for _, input_candidate_resource in input_candidate_resources.items():
            if int(input_candidate_resource.call_id) < int(parent_resource.call_id):
                continue
            if branch.get_call(input_candidate_resource.call_id) is not None:
                continue
            branch.calls.append(BranchCall(call=input_candidate_resource.call))

        # If shader doesn't have listed outputs, we've reached the end of current branch
        if len(shader_map.outputs) == 0:
            return branch

        branches = []

        for output_slot in shader_map.outputs:

            output_hashes = []

            output_branch = ShaderCallBranch(shader_id=shader_id, calls=[], nested_branches=[])

            for branch_call in branch.calls:

                output_filter_attributes = {
                    'shaders:type': shader_map.shader_type,
                    'slot_type': output_slot.slot_type,
                }
                if output_slot.slot_id is not None:
                    output_filter_attributes['slot_id'] = output_slot.slot_id
                if output_slot.shader_type != ShaderType.Empty:
                    output_filter_attributes['slot_shader_type'] = output_slot.shader_type

                output_resource = branch_call.call.get_filtered_resource(output_filter_attributes)

                if output_resource is None:
                    continue

                skip_branch = False
                if output_resource.hash in output_hashes:
                    skip_branch = True
                else:
                    output_hashes.append(output_resource.hash)

                nested_branch = self.resolve_branch(output_slot.shader_id, shader_data_pattern, output_resource, shader_id)

                if nested_branch is None:
                    continue

                if skip_branch:
                    output_branch.calls.append(branch_call)
                    continue

                output_branch.calls.append(branch_call)

                # output_branch.nested_branches.append(nested_branch)

                if isinstance(nested_branch, list):
                    output_branch.nested_branches.extend(nested_branch)
                else:
                    output_branch.nested_branches.append(nested_branch)

            if len(output_branch.calls) == 0:
                continue

            branches.append(output_branch)

        if len(branches) == 0:
            return None

        return branches

    @staticmethod
    def get_root_shaders(shader_data_pattern):
        root_shaders = []
        for shader_id, shader_map in shader_data_pattern.items():
            # Hack: Force short-cirquited shaders into root shaders
            for outputs in shader_map.outputs:
                if outputs.shader_id == shader_id:
                    root_shaders.append(shader_id)
                    break
            if len(shader_map.inputs) == 0:
                root_shaders.append(shader_id)
        return root_shaders

    def get_all_slot_resources(self, shader_type, slot):
        hash = (shader_type, slot.slot_type, slot.slot_id, slot.shader_type)
        cached_result = self.cache.get(hash, None)
        if cached_result is not None:
            return cached_result

        input_filter_attributes = {
            'shaders:type': shader_type,
            'slot_type': slot.slot_type,
        }
        if slot.slot_id is not None:
            input_filter_attributes['slot_id'] = slot.slot_id
        if slot.shader_type != ShaderType.Empty:
            input_filter_attributes['slot_shader_type'] = slot.shader_type

        slot_resources = DictFilter(Filter(
            attributes=input_filter_attributes,
            dictionaries=[self.dump.resources]
        )).filtered_dict

        self.cache[hash] = slot_resources

        return slot_resources


