"""
Tools to generate Home Assistant configuration files from KNX setup files (ETS) 
"""

import json
import re
import sys
from dataclasses import asdict, dataclass
from functools import reduce
from typing import Dict

import yaml


@dataclass
class KNXDevice:
    """Represents a KNX Device"""

    name: str
    address: str = ""
    state_address: str = ""

    def check(self) -> bool:
        """Tells whether this device is valid"""
        return self.address != "" and self.state_address != ""


class KNXProject:
    """Encapsulates KNX Project"""

    ITEM_RE = re.compile("(\\d+\\/\\d+\\/\\d+) (.*)")
    ITEM_STATUS_RE = re.compile("(\\d+\\/\\d+\\/\\d+) reenv (.*)")

    def __init__(self) -> None:
        self.devices: Dict[str, KNXDevice] = {}

    def check(self) -> bool:
        """Tells whether this project includes valid devices"""
        return reduce(
            lambda c, cc: c and cc,
            [d.check() for d in self.devices.values()],
        )  # type: ignore

    def _parse_line(self, l: str):
        s = self.ITEM_STATUS_RE.match(l)
        if s is not None:
            addr = s.group(1)
            name = s.group(2).lower().strip()
            state_item = True
        else:
            s = self.ITEM_RE.match(l)
            if s is not None:
                state_item = False
                addr = s.group(1)
                name = s.group(2).lower().strip()
        if s is None:
            print(f"Unrecognized: {l}")
            return
        name = name.replace(" ", "_")
        # addr = str(addr)
        if name not in self.devices:
            self.devices[name] = KNXDevice(name=name)
        if state_item:
            self.devices[name].state_address = addr
        else:
            self.devices[name].address = addr

    @classmethod
    def load_from_ets(cls, file: str) -> "KNXProject":
        """Factory method to create a project from an ETS file"""
        _proj: KNXProject = KNXProject()

        with open(file, mode="r+", encoding="UTF-8") as f:
            lines = f.readlines()

        for l in lines:
            _proj._parse_line(l)

        return _proj

    def to_dict(self) -> dict:
        """Creates a dict representation of this project"""
        return {name: asdict(obj) for name, obj in self.devices.items()}

    def to_yaml(self, root: str, devices_type: str) -> str:
        """Creates a yaml representation of this project"""
        d: dict = {
            root: {devices_type: [asdict(dev) for dev in self.devices.values()]}
        }
        return yaml.dump(d, indent=2)

    def to_json(self) -> str:
        """Creates a serialized json representation of this project"""
        return json.dumps(self.to_dict(), indent=2)


if __name__ == "__main__":
    if len(sys.argv) != 2:
        print("Takes only one argument: ETS input file")
        sys.exit(1)

    filename = sys.argv[1]
    p: KNXProject = KNXProject.load_from_ets(file=filename)

    with open(file=f"{filename}.yaml", mode="w+", encoding="UTF-8") as fyaml:
        y = p.to_yaml(root="knx", devices_type="light")
        fyaml.write(y)

    with open(file=f"{filename}.json", mode="w+", encoding="UTF-8") as fjson:
        j = p.to_json()
        fjson.write(j)
