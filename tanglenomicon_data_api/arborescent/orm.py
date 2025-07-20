"""ORM for the Arborescent submodule."""

from typing import List
from enum import Enum
from dataclasses import dataclass
from bson import ObjectId
from ..internal import db_connector as dbc
from ..internal import config_store as cfg
from pymongo.asynchronous.collection import AsyncCollection

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
    # global _sten_col
    # if _sten_col is None:
    #     _sten_col = dbc.db[cfg.cfg_dict["tangle-classes"]["arborescent"]["stencil_col_name"]]
    # return _sten_col


def get_arborescent_collection() -> AsyncCollection:
    """Return the mongodb collection containing the Arborescent tangles.

    Returns
    -------
    AsyncCollection
        The Arborescent tangles collection.
    """
    # global _arbor_col
    # if _arbor_col is None:
    #     _arbor_col = dbc.db[cfg.cfg_dict["tangle-classes"]["arborescent"]["col_name"]]
    # return _arbor_col
    return dbc.db[cfg.cfg_dict["tangle-classes"]["arborescent"]["col_name"]]


class StencilHeadStateEnum(str, Enum):
    """Enum describing the states of the Head pointer for stencils."""

    headroom = "headroom"
    no_headroom = "no_headroom"


class StencilStateEnum(int, Enum):
    """Enum describing the states of a stencil."""

    new = 0
    started = 1
    no_headroom = 2
    complete = 3


@dataclass
class StencilJobDB:
    """A subjob for a stencil to be read/written to/from a collection."""

    job_id: str
    cursor: List[ObjectId]


@dataclass
class StencilCfg:
    current_counts: List[int]
    current_good_counts: List[int]
    current_completed_acn: int
    max_acn: int
    _id: str


@dataclass
class StencilDB:
    """A stencil to be read/written to/from a collection."""
    _id: ObjectId
    ACN: int
    rootstock_acn: int
    scion_acn: int
    state: int
    job_backlog: List[StencilJobDB]
    open_jobs: List[StencilJobDB]


@dataclass
class ArborescentTangleDB:
    """A montesinos tangle to be read from the tangle collection."""

    _id: ObjectId
    notation:str
    positivity: str
    # parents: List[List[str]]
    is_good: bool
    ACN: int

@dataclass
class ArborescentTangle:
    """A montesinos tangle to be read from the tangle collection."""

    notation:str
    positivity: str
    is_good: bool
    ACN: int
