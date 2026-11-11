import re
from importlib.metadata import version

import client_pulse


def test_version_is_semver_and_matches_installed_metadata() -> None:
    assert re.fullmatch(r"\d+\.\d+\.\d+", client_pulse.__version__)
    assert client_pulse.__version__ == version("client-pulse")
