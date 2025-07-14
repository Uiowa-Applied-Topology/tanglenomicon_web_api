"""ORM for the Arborescent submodule."""

from typing import List
from enum import Enum
from dataclasses import dataclass
from bson import ObjectId
from ..internal import db_connector as dbc
from ..internal import config_store as cfg
from motor.motor_asyncio import AsyncIOMotorDatabase


def get_stencil_collection() -> AsyncIOMotorDatabase:
    """Return the mongodb collection containing the Arborescent stencils.

    Returns
    -------
    AsyncIOMotorDatabase
        The Arborescent stencils collection.
    """
    return dbc.db[cfg.cfg_dict["tangle-classes"]["arborescent"]["stencil_col_name"]]


def get_arborescent_collection() -> AsyncIOMotorDatabase:
    """Return the mongodb collection containing the Arborescent tangles.

    Returns
    -------
    AsyncIOMotorDatabase
        The Arborescent tangles collection.
    """
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
    cursor: List[int]

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
    head: List[int]
    state: int
    open_jobs: List[StencilJobDB]


@dataclass
class ArborescentTangleDB:
    """A montesinos tangle to be read from the tangle collection."""

    _id: str
    positivity: str
    parents: List[List[str]]
    is_good: bool
    ACN: int