"""ORM for the Montesinos submodule."""

from typing import List
from enum import Enum
from dataclasses import dataclass
from bson import ObjectId
from ..internal import db_connector as dbc
from ..internal import config_store as cfg
from pymongo.asynchronous.collection import AsyncCollection


def get_stencil_collection() -> AsyncCollection:
    """Return the mongodb collection containing the Montesinos stencils.

    Returns
    -------
    AsyncIOMotorDatabase
        The Montesinos stencils collection.
    """
    return dbc.db[cfg.cfg_dict["tangle-classes"]["montesinos"]["stencil_col_name"]]


def get_montesinos_collection() -> AsyncCollection:
    """Return the mongodb collection containing the Montesinos tangles.

    Returns
    -------
    AsyncIOMotorDatabase
        The Montesinos tangles collection.
    """
    return dbc.db[cfg.cfg_dict["tangle-classes"]["montesinos"]["col_name"]]


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
class StencilDB:
    """A stencil to be read/written to/from a collection."""

    _id: ObjectId
    stencil_array: List[int]
    str_rep: str
    crossing_num: int
    head: List[int]
    state: int
    open_jobs: List[StencilJobDB]


@dataclass
class MontesinosTangleDB:
    """A montesinos tangle to be read from the tangle collection."""

    _id: str
    crossing_num: int
    parent_stencil: str
