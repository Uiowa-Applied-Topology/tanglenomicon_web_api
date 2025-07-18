"""DB Connector handles the internal mongodb initialization.

Raises
------
NameError
    Connection error occurred.
"""

from pymongo import AsyncMongoClient
from pymongo.asynchronous.database import AsyncDatabase

import urllib.parse

client: AsyncMongoClient = None

db: AsyncDatabase = None


def init_client(url: str, port: int, username: str, password: str, database_name: str):
    """Initialize the db for the server.

    Parameters
    ----------
    url : str
        Base url for the db connection.
    port : int
        Port for the db connection.
    username : str
        DB connection username
    password : strs
        DB connection password.
    database_name : str
        Name of database at url to connect to.

    Raises
    ------
    NameError
        Connection error occurred.
    """
    global client
    global db
    if url and port and username and password:
        username = urllib.parse.quote_plus(username)
        password = urllib.parse.quote_plus(password)
        client = AsyncMongoClient(
            f"mongodb://{username}:{password}@{url}:{port}/?authSource=admin&retryWrites=true&w=majority"
            # noqa: E501
        )
        db = client[database_name]
    else:
        raise NameError(
            "db connection error"
        )  # @@@IMPROVEMENT: needs to be updated to exception object
    ...
