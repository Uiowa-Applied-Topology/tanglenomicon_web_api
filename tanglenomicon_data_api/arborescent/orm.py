"""ORM for the Arborescent submodule."""

from dataclasses import dataclass
from enum import Enum
from typing import List

from bson import ObjectId
from pymongo.asynchronous.collection import AsyncCollection

from ..internal import config_store as cfg
from ..internal import db_connector as dbc

_sten_col: AsyncCollection = None
_arbor_col: AsyncCollection = None


def get_stencil_collection() -> AsyncCollection:
    """Return the mongodb collection containing the Arborescent stencils.

    Returns
    -------
    AsyncCollection
        The Arborescent stencils collection.
    """
    return dbc.db[cfg.cfg_dict["tangle-classes"]["arborescent"]["stencil_col_name"]]


def get_job_collection() -> AsyncCollection:
    """Return the mongodb collection containing the Arborescent stencils.

    Returns
    -------
    AsyncCollection
        The Arborescent stencils collection.
    """
    return dbc.db[cfg.cfg_dict["tangle-classes"]["arborescent"]["job_col_name"]]


def get_arborescent_collection() -> AsyncCollection:
    """Return the mongodb collection containing the Arborescent tangles.

    Returns
    -------
    AsyncCollection
        The Arborescent tangles collection.
    """
    return dbc.db[cfg.cfg_dict["tangle-classes"]["arborescent"]["col_name"]]


class StencilStateEnum(int, Enum):
    """Enum describing the states of a stencil."""

    new = 0
    started = 1
    no_headroom = 2
    complete = 3


class JobDBStateEnum(int, Enum):
    """Enum describing the states of a stencil."""

    new = 0
    started = 1


@dataclass
class JobDB:
    """A job for a stencil to be read/written to/from a collection."""

    _id: ObjectId
    state: int
    cursor: List[ObjectId]
    rootstock_acn: int
    scion_acn: int


@dataclass
class StencilCfg:
    """The stencil entry that manages state of the system."""

    current_completed_acn: int
    max_acn: int
    _id: str


@dataclass
class StencilDB:
    """A stencil to be read/written to/from a collection."""

    _id: ObjectId
    rootstock_acn: int
    scion_acn: int
    state: int
    cursor: List[ObjectId]


@dataclass
class ArborescentTangleDB:
    """A arborescent tangle to be read from the tangle collection."""

    _id: str
    notation: str
    positivity: str
    is_good: bool
    ACN: int


@dataclass
class AnborescentTangleResult:
    """A arborescent tangle to be read from the tangle collection."""

    notation: str
    positivity: str
    is_good: bool
    ACN: int