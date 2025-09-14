"""Security submodule handles authenticating users.

This has been mostly lifted from [here](https://web.archive.org/web/20240505104734/https://fastapi.tiangolo.com/tutorial/security/oauth2-jwt/) <!-- # noqa: E501 -->


Raises
------
credentials_exception
    Credentials are invalid.
HTTPException
    Various HTTP error codes.
"""

import logging
from datetime import datetime, timedelta, timezone
from typing import Annotated, Union

from fastapi import Depends, APIRouter, HTTPException, status
from fastapi.security import OAuth2PasswordBearer, OAuth2PasswordRequestForm
from jose import JWTError, jwt
from passlib.context import CryptContext
from pydantic import BaseModel
from pymongo.asynchronous.collection import AsyncCollection

from . import db_connector as dbc
from . import config_store

logging.getLogger("passlib").setLevel(logging.ERROR)


class Token(BaseModel):
    """The jwt token class.

    Parameters
    ----------
    BaseModel : BaseModel
        Usage docs: https://docs.pydantic.dev/2.7/concepts/models/
    """

    access_token: str
    token_type: str


class TokenData(BaseModel):
    """The jwt Token data class.

    Parameters
    ----------
    BaseModel : BaseModel
        Usage docs: https://docs.pydantic.dev/2.7/concepts/models/
    """

    username: Union[str, None] = None


class User(BaseModel):
    """User class outline.

    Parameters
    ----------
    BaseModel : BaseModel
        Usage docs: https://docs.pydantic.dev/2.7/concepts/models/
    """

    username: str
    disabled: Union[bool, None] = None


class UserInDB(User):
    """The ORM definition for user from the database.

    Parameters
    ----------
    User : User
        Implementation of User.
    """

    hashed_password: str
    token_expire: int


_pwd_context = CryptContext(schemes=["bcrypt"], deprecated="auto")

_oauth2_scheme = OAuth2PasswordBearer(tokenUrl="token")

router = APIRouter()

credentials_exception = HTTPException(
    status_code=status.HTTP_401_UNAUTHORIZED,
    detail="Could not validate credentials",
    headers={"WWW-Authenticate": "Bearer"},
)


def _decode_token(token: str) -> TokenData:
    """Return a decoded jwt token.

    Parameters
    ----------
    token : str
        A token supplied by the user.

    Returns
    -------
    TokenData
        The decoded token data.

    Raises
    ------
    credentials_exception
        An error occurred when authenticating user.
    """
    try:
        payload = jwt.decode(
            token,
            config_store.cfg_dict["auth"]["secret_key"],
            algorithms=[config_store.cfg_dict["auth"]["algorithm"]],
        )
        username: str = payload.get("sub")
        if username is None:
            raise credentials_exception
        token_data = TokenData(username=username)
    except JWTError:
        raise credentials_exception
    return token_data


def _verify_password(plain_password: str, hashed_password: str) -> bool:
    """Return a ``True``/``False`` based on if password matches hash.

    Parameters
    ----------
    plain_password : str
        The plain password sent by the user.
    hashed_password : str
        The stored password hash for the user.

    Returns
    -------
    Bool
        ``True`` if the password matched the hash, else ``False``.
    """
    return _pwd_context.verify(plain_password, hashed_password)


async def _get_user(auth_col: AsyncCollection, username: str) -> UserInDB | None:
    """Find and return the user from the auth collection or None.

    Parameters
    ----------
    auth_col : AsyncCollection
        The mongodb auth collection.
    username : str
        The user to find in the collection.

    Returns
    -------
    UserInDB | None
        A user object from the auth collection or None.
    """
    if (user := (await auth_col.find_one({"username": str(username)}))) is not None:
        return UserInDB(**user)
    return None


async def _authenticate_user(
    auth_col: AsyncCollection, username: str, password: str
) -> UserInDB | bool:
    """Return ``True``/``False`` based on if user exists and password matches.

    Parameters
    ----------
    auth_col : AsyncCollection
        The mongodb auth collection.
    username : str
        The user to find in the collection.
    password : str
        The password supplied by the user.

    Returns
    -------
    UserInDB | None
        A user object from the auth collection or False if fail.
    """
    user = await _get_user(auth_col, username)
    if not user:
        return False
    if not _verify_password(password, user.hashed_password):
        return False
    return user


def _get_collection() -> AsyncCollection:
    """Return a reference to the mongodb auth collection.

    Returns
    -------
    AsyncCollection
        A reference to the auth collection.
    """
    return dbc.db[config_store.cfg_dict["auth"]["auth-col-name"]]


def _create_access_token(
    data: dict, expires_delta: Union[timedelta, None] = None
) -> str:
    """Return an access jwt token.

    Parameters
    ----------
    data : dict
        The data to encode into a token.
    expires_delta : Union[timedelta, None], optional
        The timedelta to expire the token, by default None

    Returns
    -------
    str
        A jwt token.
    """
    to_encode = data.copy()
    if expires_delta:
        expire = datetime.now(timezone.utc) + expires_delta
    else:
        expire = datetime.now(timezone.utc) + timedelta(minutes=15)
    to_encode.update({"exp": expire})
    encoded_jwt = jwt.encode(
        to_encode,
        config_store.cfg_dict["auth"]["secret_key"],
        algorithm=config_store.cfg_dict["auth"]["algorithm"],
    )
    return encoded_jwt


async def auth_current_user(token: Annotated[str, Depends(_oauth2_scheme)]) -> bool:
    """Return ``True``/``False`` based on if the supplied token is valid.

    Parameters
    ----------
    token : Annotated[str, Depends
        The token supplied by the user.

    Returns
    -------
    bool
        ``True``/``False`` if user is authenticated.

    Raises
    ------
    credentials_exception
        An error occurred when authenticating user.
    """
    if _decode_token(token):
        return True
    return False


async def get_current_user(
    token: Annotated[str, Depends(_oauth2_scheme)],
    auth_col: Annotated[AsyncCollection, Depends(_get_collection)],
) -> UserInDB:
    """Retrieve a user from the auth collection given a token.

    Parameters
    ----------
    token : Annotated[str, Depends
        A jwt token supplied by the user.
    auth_col : Annotated[AsyncCollection, Depends
        A reference to an auth collection.

    Returns
    -------
    UserInDB
        A user from the auth collection.

    Raises
    ------
    credentials_exception
        An error occurred when authenticating user.
    """
    token_data = _decode_token(token)
    user = await _get_user(auth_col, username=token_data.username)
    if user is None:
        raise credentials_exception
    return user


async def _get_current_active_user(
    current_user: Annotated[User, Depends(get_current_user)],
) -> User:
    """Return data for current active user.

    Parameters
    ----------
    current_user : Annotated[User, Depends
        The current user.

    Returns
    -------
    User
        The current user.

    Raises
    ------
    HTTPException
        An http error if user is disabled.
    """
    if current_user.disabled:
        raise HTTPException(status_code=400, detail="Inactive user")
    return current_user


async def add_user(username: str, password: str, token_expire: int = None):
    """Add a user to the auth collection.

    Parameters
    ----------
    username : The username of the user.
    password : The password supplied by the user.
    token_expire : The expiration time for the token.
    """
    auth_col = _get_collection()
    if not token_expire:
        token_expire = config_store.cfg_dict["auth"]["token_exp"]
    pwdhash = _pwd_context.hash(password)
    if not (await auth_col.find_one({"username": username})):
        await auth_col.insert_one(
            {
                "username": str(username),
                "hashed_password": str(pwdhash),
                "disabled": False,
                "token_expire": int(token_expire),
            }
        )
    else:
        print(f"User {username} already exists")


@router.get("/users/me/", response_model=User)
async def read_users_me(
    current_user: Annotated[User, Depends(_get_current_active_user)],
):
    """Endpoint to return the current active user.

    Parameters
    ----------
    current_user : Annotated[User, Depends
        The current user retrieved from the get current user function.

    Returns
    -------
    User
        The current user's information.
    """
    return current_user


@router.post("/token")
async def login_for_access_token(
    form_data: Annotated[OAuth2PasswordRequestForm, Depends()],
    auth_col: Annotated[AsyncCollection, Depends(_get_collection)],
) -> Token:
    """Generate a token for the current user.

    Parameters
    ----------
    form_data : Annotated[OAuth2PasswordRequestForm, Depends
        The data submitted by the user.
    auth_col : Annotated[AsyncCollection, Depends
        The mongodb auth collection.

    Returns
    -------
    Token
        The generated token.

    Raises
    ------
    HTTPException
        Raised if user is not authenticated.
    """
    user = await _authenticate_user(auth_col, form_data.username, form_data.password)
    if not user:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Incorrect username or password",
            headers={"WWW-Authenticate": "Bearer"},
        )
    access_token_expires = timedelta(minutes=user.token_expire)
    access_token = _create_access_token(
        data={"sub": user.username}, expires_delta=access_token_expires
    )
    return Token(access_token=access_token, token_type="bearer")
