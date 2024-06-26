import os
import re

from enum import Enum, auto
from dataclasses import dataclass


@dataclass
class Dispatch:
    ThreadGroupCountX: int
    ThreadGroupCountY: int
    ThreadGroupCountZ: int


@dataclass
class DrawIndexed:
    IndexCount: int
    StartIndexLocation: int
    BaseVertexLocation: int


class CallParameters(Enum):
    Dispatch = auto()
    DrawIndexed = auto()


class FrameDumpCall:
    def __init__(self, call_id):
        self.id = call_id
        self.parameters = {}
        self.patterns = {
            CallParameters.Dispatch: (
                re.compile(r'^Dispatch\(ThreadGroupCountX:(\d+), ThreadGroupCountY:(\d+), ThreadGroupCountZ:(\d+)\)'),
                lambda data: Dispatch(int(data[0]), int(data[1]), int(data[2]))
            ),
            CallParameters.DrawIndexed: (
                re.compile(r'^DrawIndexed\(IndexCount:(\d+), StartIndexLocation:(\d+), BaseVertexLocation:(\d+)\)'),
                lambda data: DrawIndexed(int(data[0]), int(data[1]), int(data[2]))
            ),
        }

    def import_data(self, raw_log_entry):
        raw_log_entry = ' '.join(raw_log_entry)
        for name, (pattern, decoder) in self.patterns.items():
            result = pattern.findall(raw_log_entry)
            if len(result) == 0:
                continue
            if len(result) != 1:
                raise ValueError(f'More than 1 data entries for pattern {pattern} in {raw_log_entry}')
            self.parameters[name] = decoder(result[0])


class FrameDumpLog:
    def __init__(self, dump_path):
        self.path = os.path.join(dump_path, 'log.txt')
        self.calls = {}
        self.parse_log()
        self.validate()

    def validate(self):
        pass

    def parse_log(self):
        self.calls = {}
        with (open(self.path, "r") as f):
            lines = f.readlines()
            call = None
            raw_log_entry = []
            for line_id, line in enumerate(lines):
                raw_call_id = line[0:6]
                if raw_call_id.isnumeric():
                    line_call_id = int(raw_call_id)
                    if call is None:
                        call = FrameDumpCall(line_call_id)
                        self.calls[raw_call_id] = call
                    elif line_call_id != call.id:
                        call = FrameDumpCall(line_call_id)
                        if line_call_id in self.calls:
                            raise ValueError(f'Malformed log line {line_id}: '
                                             f'data collection for call id {raw_call_id} was already finished, '
                                             f'current call id: {call.id}')
                        self.calls[raw_call_id] = call
                    call.import_data(raw_log_entry)
                    raw_log_entry = [line[7:]]
                elif call is None:
                    continue
                else:
                    raw_log_entry.append(line.strip())
            # Handle last line of the log
            call.import_data(raw_log_entry)

