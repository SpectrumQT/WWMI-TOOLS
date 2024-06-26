

from typing import Union, List, Dict

from dataclasses import dataclass, field

from .calls_collector import CallsCollector, ShaderMap, Slot, ShaderCallBranch
from .resource_collector import ResourceCollector, DataMap

from .dump_parser import Dump


@dataclass
class DataCollector:
    # Input
    dump: Dump
    shader_data_pattern: Dict[str, ShaderMap]
    shader_resources: Dict[str, DataMap]
    # Output
    call_branches: Dict[str, ShaderCallBranch] = field(init=False)

    def __post_init__(self):
        self.calls_collector = CallsCollector(self.dump, self.shader_data_pattern)
        self.call_branches = self.calls_collector.call_branches
        self.data_collector = ResourceCollector(self.shader_resources, self.call_branches)


