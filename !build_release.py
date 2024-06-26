# Assembles source files into release build, just run it and grab freshly built .zip from \!RELEASE\X.X.X

import shutil
import re
import time

from pathlib import Path
from dataclasses import dataclass, field
from datetime import datetime


class Version:
    def __init__(self, wwmi_ini_path):
        self.wwmi_ini_path = wwmi_ini_path
        self.version = None
        self.parse_version()

    def parse_version(self):
        with open(self.wwmi_ini_path, "r") as f:

            version_pattern = re.compile(r'^"version": \((\d+), (\d+), (\d+)\),')

            for line in f.readlines():

                result = version_pattern.findall(line.strip())

                if len(result) != 1:
                    continue

                result = list(result[0])

                if len(result) != 3:
                    raise ValueError(f'Malformed WWMI Tools version!')

                self.version = result

                return

        raise ValueError(f'Failed to locate WWMI Tools version!')

    def __str__(self) -> str:
        return f'{self.version[0]}.{self.version[1]}.{self.version[2]}'

    def as_float(self):
        return float(f'{self.version[0]}.{self.version[1]}{self.version[2]}')

    def as_ints(self):
        return [map(int, self.version)]


class Project:
    def __init__(self):
        self.root_dir = Path().resolve()
        self.trash_path = self.root_dir / '!TRASH'
        self.wwmi_tools_dir = self.root_dir / 'wwmi-tools'
        self.release_dir = self.root_dir / '!RELEASES'
        self.wwmi_tools_init_path = self.wwmi_tools_dir / '__init__.py'
        self.version = Version(self.wwmi_tools_init_path)
        self.version_dir = self.release_dir / str(self.version)

    def trash(self, target_path: Path):
        trashed_path = self.trash_path / target_path.name
        if trashed_path.is_dir():
            timestamp = datetime.now().strftime('%Y-%m-%d %H-%M-%S')
            trashed_path = trashed_path.with_name(f'{trashed_path.name} {timestamp}')
        shutil.move(target_path, trashed_path)

    def build(self):
        if self.version_dir.is_dir():
            remove_ok = input(f'Directory {self.version_dir} already exists! Overwrite? (y/n)')
            if remove_ok != 'y':
                print('Version building aborted!')
                return
            else:
                self.trash(self.version_dir)
                print(f'Existing directory sent to {self.trash_path}!')

        release_path = self.version_dir / f'WWMI-Tools'
        shutil.copytree(self.wwmi_tools_dir, release_path, ignore=shutil.ignore_patterns('__pycache__'))

        shutil.make_archive(str(self.version_dir / f'{release_path.name}-v{self.version}'), 'zip', self.version_dir, release_path.name)


if __name__ == '__main__':
    try:
        project = Project()
        project.build()
    except Exception as e:
        print(f'Error:', e)
        input(f'Press eny key to exit')
