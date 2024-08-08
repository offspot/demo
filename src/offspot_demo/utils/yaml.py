from typing import Any

import yaml

try:
    from yaml import CDumper as Dumper
    from yaml import CSafeLoader as SafeLoader
except ImportError:
    # we don't NEED cython ext but it's faster so use it if avail.
    from yaml import Dumper, SafeLoader


def yaml_dump(data: dict[str, Any]) -> str:
    """YAML textual representation of data"""
    return yaml.dump(data, Dumper=Dumper, explicit_start=True, sort_keys=False)


def yaml_load(data: str) -> dict[str, Any]:
    return yaml.load(data, Loader=SafeLoader)
