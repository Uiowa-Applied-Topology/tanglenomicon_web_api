import asyncio
import json
from datetime import datetime, timedelta, timezone
from functools import partial, wraps
from pathlib import Path

import pytest
from jose import jwt
from mongomock import MongoClient as SyncMongoClient

from tanglenomicon_data_api.internal import config_store as cfg
from tanglenomicon_data_api.internal import db_connector as dbc
from tanglenomicon_data_api.internal import job_queue

test_path = Path.cwd() / Path("tests")
fixture_path = test_path / Path("fixtures")


class AsyncMongoMockClient:
    """
    Mock AsyncMongoClient that emulates PyMongo's async interface.
    This is designed to work with Beanie 2.0's expectations.
    """

    def __init__(self, *args, **kwargs):
        """Initialize with a sync mongomock client."""
        # Filter out async-specific kwargs that mongomock doesn't understand
        clean_kwargs = {
            k: v
            for k, v in kwargs.items()
            if k not in ["io_loop", "maxPoolSize", "minPoolSize"]
        }
        self._sync_client = SyncMongoClient(*args, **clean_kwargs)

    async def aconnect(self):
        """PyMongo AsyncMongoClient connection method."""
        pass  # mongomock doesn't need explicit connection

    async def aclose(self):
        """PyMongo AsyncMongoClient close method."""
        if hasattr(self._sync_client, "close"):
            self._sync_client.close()

    def __getitem__(self, name):
        """Get database by name - returns AsyncDatabase mock."""
        sync_db = self._sync_client[name]
        return AsyncDatabaseMock(sync_db)

    def get_database(self, name, **kwargs):
        """Get database by name with options."""
        sync_db = self._sync_client.get_database(name, **kwargs)
        return AsyncDatabaseMock(sync_db)

    @property
    def admin(self):
        """Get admin database."""
        return AsyncDatabaseMock(self._sync_client.admin)

    # Forward other PyMongo AsyncMongoClient methods as needed
    def __getattr__(self, name):
        """Forward unknown attributes to sync client, making them async if callable."""
        attr = getattr(self._sync_client, name)
        if callable(attr):

            @wraps(attr)
            async def async_wrapper(*args, **kwargs):
                return await asyncio.get_event_loop().run_in_executor(
                    None, partial(attr, *args, **kwargs)
                )

            return async_wrapper
        return attr


class AsyncDatabaseMock:
    """Mock async database that emulates PyMongo's async database interface."""

    def __init__(self, sync_db):
        self._sync_db = sync_db

    def __getitem__(self, name):
        """Get collection by name."""
        sync_collection = self._sync_db[name]
        return AsyncCollectionMock(sync_collection)

    def get_collection(self, name, **kwargs):
        """Get collection by name with options."""
        sync_collection = self._sync_db.get_collection(name, **kwargs)
        return AsyncCollectionMock(sync_collection)

    async def command(self, command, **kwargs):
        """Execute database command."""
        # Handle special commands that Beanie needs
        if isinstance(command, dict):
            if "buildInfo" in command:
                return {
                    "ok": 1.0,
                    "version": "4.4.0",
                    "gitVersion": "mock",
                    "modules": [],
                    "allocator": "tcmalloc",
                    "storageEngines": ["wiredTiger"],
                }
            elif "ping" in command:
                return {"ok": 1.0}

        # For other commands, execute synchronously in thread pool
        func = partial(self._sync_db.command, command, **kwargs)
        return await asyncio.get_event_loop().run_in_executor(None, func)

    def __getattr__(self, name):
        """Forward other database methods, making them async."""
        attr = getattr(self._sync_db, name)
        if callable(attr):

            @wraps(attr)
            async def async_wrapper(*args, **kwargs):
                func = partial(attr, *args, **kwargs)
                result = await asyncio.get_event_loop().run_in_executor(None, func)
                # If result is a mongomock collection, wrap it
                if hasattr(result, "__class__") and "mongomock" in str(
                    result.__class__
                ):
                    if "Collection" in str(result.__class__):
                        return AsyncCollectionMock(result)
                return result

            return async_wrapper
        return attr


class AsyncCollectionMock:
    """Mock async collection that emulates PyMongo's async collection interface."""

    def __init__(self, sync_collection):
        self._sync_collection = sync_collection

    async def find(self, *args, **kwargs):
        """Return an async cursor mock."""
        sync_cursor = self._sync_collection.find(*args, **kwargs)
        return AsyncCursorMock(sync_cursor)

    async def find_one(self, *args, **kwargs):
        """Find one document."""
        func = partial(self._sync_collection.find_one, *args, **kwargs)
        return await asyncio.get_event_loop().run_in_executor(None, func)

    def __getattr__(self, name):
        """Forward other collection methods, making them async."""
        attr = getattr(self._sync_collection, name)
        if callable(attr):

            @wraps(attr)
            async def async_wrapper(*args, **kwargs):
                func = partial(attr, *args, **kwargs)
                result = await asyncio.get_event_loop().run_in_executor(None, func)

                # Handle cursor results
                if hasattr(result, "__class__") and "mongomock" in str(
                    result.__class__
                ):
                    if "Cursor" in str(result.__class__):
                        return AsyncCursorMock(result)

                return result

            return async_wrapper
        return attr


class AsyncCursorMock:
    """
    Mock async cursor that emulates PyMongo's async cursor interface.
    This is what Beanie expects from cursor operations.
    """

    def __init__(self, sync_cursor):
        self._sync_cursor = sync_cursor
        self._data_cache = None

    async def to_list(self, length=None):
        """Convert cursor to list - this is what Beanie calls."""
        if self._data_cache is None:
            func = partial(list, self._sync_cursor)
            self._data_cache = await asyncio.get_event_loop().run_in_executor(
                None, func
            )

        if length is not None:
            return self._data_cache[:length]
        return self._data_cache.copy()

    def __aiter__(self):
        """Async iterator support."""
        return self

    async def __anext__(self):
        """Async iterator next."""
        try:
            func = partial(next, self._sync_cursor)
            return await asyncio.get_event_loop().run_in_executor(None, func)
        except StopIteration:
            raise StopAsyncIteration

    def __getattr__(self, name):
        """Forward other cursor methods."""
        attr = getattr(self._sync_cursor, name)
        if callable(attr):

            @wraps(attr)
            async def async_wrapper(*args, **kwargs):
                func = partial(attr, *args, **kwargs)
                result = await asyncio.get_event_loop().run_in_executor(None, func)
                # If result is another cursor, wrap it
                if hasattr(result, "__class__") and "Cursor" in str(result.__class__):
                    return AsyncCursorMock(result)
                return result

            return async_wrapper
        return attr


##################################################################################
##################################################################################
# fixture loading functions
##################################################################################
##################################################################################


def _load_fixture(path: Path) -> dict:
    dat = None
    with open(path) as f:
        dat = json.load(f)
    return dat


@pytest.fixture
async def get_test_cfg():
    cfg.load(str(fixture_path / "test_config.yaml"))
    yield
    token = None


@pytest.fixture
async def setup_job_queue(
    get_test_cfg,
):
    # stub the db connection.
    job_queue._job_queue = {}
    yield  # Provide the data to the test
    job_queue._job_queue = {}
    # Teardown: Clean up resources (if any) after the test


@pytest.fixture
async def setup_database(
    get_test_cfg,
):
    # stub the db connection.
    dbc.db = AsyncMongoMockClient()["test_tanglenomicon"]
    yield  # Provide the data to the test
    dbc.db = None
    # Teardown: Clean up resources (if any) after the test


##################################################################################
##################################################################################
# Arborescent
##################################################################################
##################################################################################


@pytest.fixture
async def empty_arborescent_col(get_test_cfg, setup_database):
    col = dbc.db[cfg.cfg_dict["tangle-classes"]["arborescent"]["col_name"]]
    await col.delete_many({})
    yield
    await col.delete_many({})


@pytest.fixture
async def valid_arborescent_col(get_test_cfg, setup_database):
    col = dbc.db[cfg.cfg_dict["tangle-classes"]["arborescent"]["col_name"]]
    dat = _load_fixture(fixture_path / "valid_arborescent_col.json")

    await col.delete_many({})
    await col.insert_many(dat)
    yield
    await col.delete_many({})


@pytest.fixture
async def empty_arborescent_stencil_col(get_test_cfg, setup_database):
    col = dbc.db[cfg.cfg_dict["tangle-classes"]["arborescent"]["stencil_col_name"]]
    await col.delete_many({})
    yield
    await col.delete_many({})


@pytest.fixture
async def valid_arborescent_stencil_col(get_test_cfg, setup_database):
    col = dbc.db[cfg.cfg_dict["tangle-classes"]["arborescent"]["stencil_col_name"]]
    dat = _load_fixture(fixture_path / "valid_stencil_col.json")

    await col.delete_many({})
    await col.insert_many(dat)
    yield
    await col.delete_many({})


@pytest.fixture
async def valid_arborescent_stencil_col_all_new(get_test_cfg, setup_database):
    col = dbc.db[cfg.cfg_dict["tangle-classes"]["arborescent"]["stencil_col_name"]]
    dat = _load_fixture(fixture_path / "valid_stencil_col_all_new.json")

    await col.delete_many({})
    await col.insert_many(dat)
    yield
    await col.delete_many({})


@pytest.fixture
async def empty_arborescent_job_col(get_test_cfg, setup_database):
    col = dbc.db[cfg.cfg_dict["tangle-classes"]["arborescent"]["job_col_name"]]
    await col.delete_many({})
    yield
    await col.delete_many({})


@pytest.fixture
async def valid_arborescent_job_col(get_test_cfg, setup_database):
    col = dbc.db[cfg.cfg_dict["tangle-classes"]["arborescent"]["job_col_name"]]
    dat = _load_fixture(fixture_path / "valid_job_col.json")

    await col.delete_many({})
    await col.insert_many(dat)
    yield
    await col.delete_many({})


##################################################################################
##################################################################################
# Montesinos
##################################################################################
##################################################################################


@pytest.fixture
async def empty_montesinos_col(get_test_cfg, setup_database):
    col = dbc.db[cfg.cfg_dict["tangle-classes"]["montesinos"]["col_name"]]
    await col.delete_many({})
    yield
    await col.delete_many({})


@pytest.fixture
async def empty_montesinos_stencil_col(get_test_cfg, setup_database):
    col = dbc.db[cfg.cfg_dict["tangle-classes"]["montesinos"]["stencil_col_name"]]
    await col.delete_many({})
    yield
    await col.delete_many({})


@pytest.fixture
async def valid_montesinos_stencil_col(get_test_cfg, setup_database):
    col = dbc.db[cfg.cfg_dict["tangle-classes"]["montesinos"]["stencil_col_name"]]
    dat = _load_fixture(fixture_path / "valid_stencil_col.json")

    await col.delete_many({})
    await col.insert_many(dat)
    yield
    await col.delete_many({})


@pytest.fixture
async def valid_montesinos_stencil_col_all_new(get_test_cfg, setup_database):
    col = dbc.db[cfg.cfg_dict["tangle-classes"]["montesinos"]["stencil_col_name"]]
    dat = _load_fixture(fixture_path / "valid_stencil_col_all_new.json")

    await col.delete_many({})
    await col.insert_many(dat)
    yield
    await col.delete_many({})


@pytest.fixture
async def valid_montesinos_col(get_test_cfg, setup_database):
    col = dbc.db[cfg.cfg_dict["tangle-classes"]["montesinos"]["col_name"]]
    dat = _load_fixture(fixture_path / "valid_montesinos_col.json")

    await col.delete_many({})
    await col.insert_many(dat)
    yield
    await col.delete_many({})


##################################################################################
##################################################################################
# Rational
##################################################################################
##################################################################################


@pytest.fixture
async def empty_rational_col(get_test_cfg, setup_database):
    col = dbc.db[cfg.cfg_dict["tangle-classes"]["rational"]["col_name"]]
    await col.delete_many({})
    yield
    await col.delete_many({})


@pytest.fixture
async def valid_rational_col(get_test_cfg, setup_database):
    col = dbc.db[cfg.cfg_dict["tangle-classes"]["rational"]["col_name"]]
    dat = _load_fixture(fixture_path / "valid_rational_col.json")

    await col.delete_many({})
    await col.insert_many(dat)
    yield
    await col.delete_many({})


##################################################################################
##################################################################################
# Auth
##################################################################################
##################################################################################


@pytest.fixture
async def valid_auth_col(get_test_cfg, setup_database):
    col = dbc.db[cfg.cfg_dict["auth"]["auth-col-name"]]
    dat = _load_fixture(fixture_path / "valid_auth_col.json")

    await col.delete_many({})
    await col.insert_many(dat)
    yield
    await col.delete_many({})


@pytest.fixture
async def get_test_jwt(get_test_cfg, valid_auth_col):
    dat = _load_fixture(fixture_path / "fake_creds.json")
    expire = datetime.now(timezone.utc) + timedelta(minutes=15)
    dat["exp"] = expire
    token = jwt.encode(
        dat,
        cfg.cfg_dict["auth"]["secret_key"],
        algorithm=cfg.cfg_dict["auth"]["algorithm"],
    )
    yield token
    token = None