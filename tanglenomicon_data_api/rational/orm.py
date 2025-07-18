"""Defines the ORM for rational tangles."""

from dataclasses import dataclass
from typing import List
from pymongo.asynchronous.collection import AsyncCollection
from ..internal import db_connector as dbc
from ..internal import config_store as cfg


def get_rational_collection() -> AsyncCollection:
    """Return the mongodb collection containing the rational tangles.

    Returns
    -------
    AsyncIOMotorDatabase
        The rational tangle collection.
    """
    return dbc.db[cfg.cfg_dict["tangle-classes"]["rational"]["col_name"]]


@dataclass
class RationalTangDB:
    """The ORM for rational tangles stored in mongodb."""

    _id: str
    twist_vector: str
    crossing_num: int
    tv_array: List[int]
    in_unit_interval: bool
