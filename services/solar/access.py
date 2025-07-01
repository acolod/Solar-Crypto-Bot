from functools import wraps
from typing import Callable
from solar.table import Table
import uuid


class User(Table):
    __tablename__ = "users"
    id: uuid.UUID
    email: str


def authenticated(func) -> Callable:
    @wraps(func)
    def wrapper(*args, **kwargs):
        return func(*args, **kwargs)

    return wrapper


def public(func) -> Callable:
    @wraps(func)
    def wrapper(*args, **kwargs):
        return func(*args, **kwargs)

    return wrapper
