"""internal.config holds and loads the configuration for the server."""

import yaml
from pathlib import Path

cfg_dict: dict = None


def load(path: str):
    """Load the configuration from file.

    Parameters
    ----------
    path : str
        The path to find the configuration on disk.
    """
    global cfg_dict
    path = Path.cwd() / Path(path)
    cfg_dict = dict()
    try:
        with open(path) as f:
            cfg_dict.update(yaml.load(f, Loader=yaml.FullLoader))
        ...
    except Exception:
        raise NameError(
            "config load error"
        )  # @@@IMPROVEMENT: needs to be updated to exception object
    ...
