"""
Tools to generate Home Assistant configuration files from KNX setup files (ETS) 
"""

import re
import sys
from enum import Enum
from functools import reduce
from typing import Dict, List, Optional, Tuple, TypedDict

import yaml

KNX_ADDRESS_RE = re.compile("^(\\d+)(\\/\\d+)?(\\/\\d+)? (.*)$")


class ETSCustomAddressType(Enum):
    """Types defined in an ETS exported file"""

    ONOFF = ""
    FEEDBACK_ONOFF = "feedback"
    DIMVALUE = "dimvalue"
    FEEDBACK_DIMVALUE = "feedback dimvalue"
    DIMMER = "dimmer"


ETS_HA_MAP = {
    ETSCustomAddressType.ONOFF.value: "address",
    ETSCustomAddressType.FEEDBACK_ONOFF.value: "state_address",
    ETSCustomAddressType.DIMVALUE.value: "brightness_address",
    ETSCustomAddressType.FEEDBACK_DIMVALUE.value: "brightness_state_address",
}


class KNXDevice(TypedDict, total=False):
    """Represents a KNX Device"""

    name: str
    address: str
    state_address: str


class KNXLight(KNXDevice, total=False):
    """Represents a KNX Device Light"""

    brightness_address: str
    brightness_state_address: str


class KNXHeler:
    """Helper functions"""

    @staticmethod
    def check(device: KNXDevice) -> bool:
        """Tells whether the given device is valid"""
        return "address" in device and "state_address" in device

    @staticmethod
    def should_ignore(device_name: str) -> bool:
        """Tells whether to process this device or not"""
        return device_name.startswith(ETSCustomAddressType.DIMMER.value)

    @staticmethod
    def parse_name(s: str) -> Tuple[str, Optional[str]]:
        """Parses name looking for action prefix and name sufix"""

        def _parse(_s, _type):
            if _s.startswith(_type):
                _s = _s.replace(_type, "").strip()
                return _s, ETS_HA_MAP.get(_type)
            return None

        tup = _parse(s, ETSCustomAddressType.FEEDBACK_DIMVALUE.value)
        if tup is None:
            tup = _parse(s, ETSCustomAddressType.FEEDBACK_ONOFF.value)
        if tup is None:
            tup = _parse(s, ETSCustomAddressType.DIMVALUE.value)
        if tup is None:
            tup = (s, ETS_HA_MAP.get(ETSCustomAddressType.ONOFF.value))

        return tup[0].lower().strip().replace(" ", "_"), tup[1]


class KNXProject:
    """Encapsulates KNX Project"""

    def __init__(self) -> None:
        self.devices: Dict[str, KNXLight] = {}

    def check(self) -> bool:
        """Tells whether this project includes valid devices"""
        return reduce(
            lambda c, cc: c and cc,
            [KNXHeler.check(d) for d in self.devices.values()],
        )  # type: ignore

    def _parse_line(self, l: str):

        s = KNX_ADDRESS_RE.match(l)
        if s is not None:
            address_main = s.group(1)
            address_middle = (
                s.group(2).replace("/", "") if s.group(2) is not None else None
            )
            address_subgroup = (
                s.group(3).replace("/", "") if s.group(3) is not None else None
            )
            name = s.group(4)
        else:
            print(f"Malformed KNX address: '{l}'")
            return

        if KNXHeler.should_ignore(name):
            print(f"Ignoring KNX address: '{l}'")
            return

        if address_middle is None:
            print(f"Processing main group {address_main}: {name}")
            return
        if address_subgroup is None:
            print(
                f"Processing middle group {address_main} / {address_middle} : {name}"
            )
            return

        device_name, device_prop = KNXHeler.parse_name(name)
        if device_prop is None:
            print(f"Unable to extract device property from name '{name}'")
            return
        assert device_prop is not None

        full_address: str = (
            f"{address_main}/{address_middle}/{address_subgroup}"
        )
        if device_name not in self.devices:
            self.devices[device_name] = {"name": device_name}
        device: KNXLight = self.devices[device_name]
        device[device_prop] = full_address

    @classmethod
    def load_from_ets(cls, file: str) -> "KNXProject":
        """Factory method to create a project from an ETS file"""
        _proj: KNXProject = KNXProject()

        with open(file, mode="r+", encoding="UTF-8") as f:
            lines = f.readlines()

        for l in lines:
            l = l.strip()
            if l != "":
                _proj._parse_line(l)

        return _proj

    def to_yaml(self, root: str, devices_type: str) -> str:
        """Creates a yaml representation of this project"""

        device_names: List[str] = sorted(list(self.devices.keys()))
        d: dict = {
            root: {devices_type: [self.devices[n] for n in device_names]}
        }
        return yaml.dump(d, indent=2)


if __name__ == "__main__":
    if len(sys.argv) != 2:
        print("Takes only one argument: ETS input file")
        sys.exit(1)

    filename = sys.argv[1]
    p: KNXProject = KNXProject.load_from_ets(file=filename)

    with open(file=f"{filename}.yaml", mode="w+", encoding="UTF-8") as fyaml:
        y = p.to_yaml(root="knx", devices_type="light")
        fyaml.write(y)
