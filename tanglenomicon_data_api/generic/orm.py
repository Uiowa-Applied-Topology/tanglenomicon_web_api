"""Defines the ORM for generic tangles."""

from dataclasses import dataclass
from pymongo.asynchronous.collection import AsyncCollection
from ..internal import db_connector as dbc
from ..internal import config_store as cfg


def get_generic_collection() -> AsyncCollection:
    """Return the mongodb collection containing the generic tangles.

    Returns
    -------
    AsyncCollection
        The generic tangles collection.
    """
    return dbc.db[cfg.cfg_dict["tangle-classes"]["generic"]["col_name"]]


@dataclass
class GenericTangDB:
    """The ORM for generic tangles stored in mongodb."""

    _id: str
