import os

from typing import List, Dict
from pathlib import Path
from dataclasses import dataclass, field

from .log_parser import FrameDumpLog
from .filename_parser import ResourceDescriptor, CallDescriptor


@dataclass
class Dump:
    # Input
    dump_directory: Path
    # Output
    log: FrameDumpLog = field(init=False)
    resources: Dict[str, ResourceDescriptor] = field(init=False)
    calls: Dict[str, CallDescriptor] = field(init=False)

    def __post_init__(self):
        self.log = FrameDumpLog(self.dump_directory)
        self.resources = {}
        self.calls = {}

        for filename in os.listdir(self.dump_directory):
            resource_path = os.path.join(self.dump_directory, filename)

            if not os.path.isfile(resource_path):
                continue
            if filename.endswith('txt'):
                continue

            resource_descriptor = ResourceDescriptor(resource_path)
            self.resources[resource_descriptor.raw] = resource_descriptor

            if resource_descriptor.call_id not in self.calls:
                self.calls[resource_descriptor.call_id] = CallDescriptor(resource_descriptor.call_id)
            call = self.calls[resource_descriptor.call_id]
            resource_descriptor.call = call

            call.import_resource_descriptor(resource_descriptor)
            logged_call = self.log.calls.get(call.id, None)
            if logged_call is not None:
                call.parameters = logged_call.parameters
