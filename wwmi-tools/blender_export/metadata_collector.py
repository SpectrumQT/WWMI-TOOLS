
from dataclasses import dataclass, field
from pathlib import Path


class Version:
    def __init__(self, version: str):
        self.version = version.split('.')

    def __str__(self) -> str:
        return f'{self.version[0]}.{self.version[1]}.{self.version[2]}'

    def as_float(self):
        return float(f'{self.version[0]}.{self.version[1]}{self.version[2]}')

    def as_ints(self):
        return [map(int, self.version)]
    

@dataclass
class ModInfo:
    wwmi_tools_version: Version
    required_wwmi_version: Version
    mod_name: str
    mod_author: str
    mod_desc: str
    mod_link: str
    mod_logo: Path
