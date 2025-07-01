######################################################################################################################
# General Information
######################################################################################################################
# This file contains the Table class and associated types like ColumnDetails, which are used to place a Pydantic
# BaseModel-style syntax on a Postgres table (an ORM, really)


######################################################################################################################
# Dependencies
######################################################################################################################


from typing import Dict, Any, Optional
from pydantic import BaseModel, Field

from psycopg.rows import dict_row
from psycopg_pool import ConnectionPool
from psycopg import Connection, Error as PsycopgError
from psycopg.types.json import Jsonb

from .config import config

import logging
import time

logger = logging.getLogger(__name__)

# Pool configuration constants
DEFAULT_MIN_SIZE = 1
DEFAULT_MAX_SIZE = 10
DEFAULT_TIMEOUT = 30  # seconds
DEFAULT_KEEPALIVE = 60  # seconds
DEFAULT_RECONNECT_TIMEOUT = 5  # seconds
DEFAULT_MAX_RETRIES = 3

_pool = None
_last_pool_check = 0
_pool_check_interval = 300  # Check pool health every 5 minutes


class SchemaConnection(Connection):
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        with self.cursor() as cur:
            cur.execute("set search_path to auth, public")


def is_connection_alive(conn):
    """Test if a database connection is still alive and usable"""
    try:
        with conn.cursor() as cur:
            cur.execute("SELECT 1")
            return True
    except Exception as e:
        logger.warning(f"Connection health check failed: {str(e)}")
        return False


def validate_pool(pool: ConnectionPool, pg_key: str) -> bool:
    """Validate the entire pool's health and attempt to fix issues"""
    try:
        # Test a connection from the pool
        with pool.getconn() as conn:
            if not is_connection_alive(conn):
                logger.warning(f"Pool {pg_key} failed health check")
                return False
        return True
    except Exception as e:
        logger.error(f"Pool {pg_key} validation failed: {str(e)}")
        return False


def get_pool(reset: bool = False) -> Dict[str, ConnectionPool]:
    """Get or create the connection pool with enhanced health checks"""
    global _pool, _last_pool_check

    current_time = time.time()

    # Check if we need to validate existing pools
    if (
        _pool is not None
        and not reset
        and (current_time - _last_pool_check) > _pool_check_interval
    ):
        logger.debug("Performing periodic pool health check")
        for pg_key, pool in _pool.items():
            if not validate_pool(pool, pg_key):
                logger.warning(f"Pool {pg_key} failed health check, will be recreated")
                reset = True
        _last_pool_check = current_time

    if _pool is None or reset:
        _pool = {}
        for pg_key, pg_conn_string in config.get_all_pg_connection_strings().items():
            try:
                _pool[pg_key] = ConnectionPool(
                    pg_conn_string,
                    min_size=DEFAULT_MIN_SIZE,
                    max_size=DEFAULT_MAX_SIZE,
                    timeout=DEFAULT_TIMEOUT,
                    kwargs={
                        "row_factory": dict_row,
                        "keepalives": 1,
                        "keepalives_idle": DEFAULT_KEEPALIVE,
                        "keepalives_interval": DEFAULT_KEEPALIVE,
                        "keepalives_count": 3,
                    },
                    connection_class=SchemaConnection,
                    check=is_connection_alive,
                )
                logger.info(f"Created new connection pool for {pg_key}")
            except Exception as e:
                logger.error(f"Failed to create pool for {pg_key}: {str(e)}")
                raise

    return _pool


######################################################################################################################
# Table Class
######################################################################################################################


def ColumnDetails(*args, primary_key: bool = False, **kwargs):
    """Wrap Field to bring some metadata args top-level"""
    if not hasattr(kwargs, "json_schema_extra"):
        kwargs["json_schema_extra"] = {}
    kwargs["json_schema_extra"]["primary_key"] = primary_key
    return Field(*args, **kwargs)


class Table(BaseModel):
    __abstract__ = True

    class Config:
        extra = "ignore"

    @classmethod
    def _get_sql_table_name(cls, schema_name=None) -> Optional[str]:
        tablename = cls.__tablename__
        if tablename is None:
            return None
        if schema_name is None:
            return tablename
        return f"{schema_name}.{tablename}"

    @classmethod
    def sql(
        cls,
        sql_statement: str,
        params: Dict[str, Any] | None = None,
        schema_name: str = "public",
        max_retries: int = 3,
    ):
        pg_key = config.get_pg_key_for_table(cls.__name__)
        pool = get_pool()
        retry_count = 0

        while retry_count < max_retries:
            current_pool = None
            conn = None

            try:
                if pg_key in pool:
                    current_pool = pool[pg_key]
                    conn = current_pool.getconn()
                else:
                    pool = get_pool(reset=True)
                    current_pool = pool[pg_key]
                    conn = current_pool.getconn()

                with conn:
                    with conn.cursor() as cursor:
                        try:
                            if schema_name != "public" and schema_name != "auth":
                                cursor.execute(f"SET search_path TO {schema_name}")
                            cursor.execute(sql_statement, params)
                            if cursor.description is not None:
                                return cursor.fetchall()
                            else:
                                return []
                        finally:
                            if schema_name != "public" and schema_name != "auth":
                                cursor.execute("SET search_path TO public, auth")
                return  # Success, exit the retry loop

            except PsycopgError as e:
                retry_count += 1
                logger.warning(
                    f"Database operation failed (attempt {retry_count}/{max_retries}): {str(e)}"
                )

                if conn is not None:
                    try:
                        if current_pool is not None:
                            current_pool.putconn(conn)
                        else:
                            conn.close()
                    except Exception:
                        try:
                            conn.close()
                        except Exception:
                            pass

                if retry_count < max_retries:
                    # Refresh the pool before retrying
                    pool = get_pool(reset=True)
                    continue
                else:
                    logger.error(
                        f"Database operation failed after {max_retries} attempts"
                    )
                    raise

            finally:
                if conn is not None:
                    try:
                        if current_pool is not None:
                            current_pool.putconn(conn)
                        else:
                            conn.close()
                    except Exception:
                        try:
                            conn.close()
                        except Exception:
                            pass

    def _prepare_value(self, value):
        """Helper to recursively prepare values for database insertion"""
        if isinstance(value, list):
            # Only recurse if list is non-empty and first item is list/dict
            if value and (isinstance(value[0], (list, dict))):
                return [self._prepare_value(item) for item in value]
            return value
        elif isinstance(value, dict):
            return Jsonb(value)
        return value

    def sync(self):
        """Sync the model to the database"""
        table_name = self.__class__._get_sql_table_name()
        if table_name is None:
            raise ValueError("Cannot sync without a table name defined")
        data = self.model_dump()

        # Get column names and values
        columns = list(data.keys())
        values = []
        for col in columns:
            value = data[col]
            field_info = self.__class__.model_fields[col]
            values.append(self._prepare_value(value))

        # Find primary key
        primary_key = None
        for field_name, field_info in self.__class__.model_fields.items():
            if field_info.json_schema_extra and field_info.json_schema_extra.get(
                "primary_key", False
            ):
                primary_key = field_name
                break

        if not primary_key:
            raise ValueError("Cannot sync without a primary key defined")

        # Build the SQL statement
        columns_str = ", ".join(columns)
        placeholders = ", ".join(["%s"] * len(columns))
        set_clause = ", ".join([f"{col} = EXCLUDED.{col}" for col in columns])

        sql_statement = f"""
            INSERT INTO {table_name} ({columns_str})
            VALUES ({placeholders})
            ON CONFLICT ({primary_key}) DO UPDATE
            SET {set_clause}
        """
        self.__class__.sql(sql_statement, values)

    @classmethod
    def sync_many(cls, objects, batch_size=1000):
        """
        Sync multiple model instances to the database in batched transactions.

        Args:
            objects: A single model instance or a list of model instances
            batch_size: Maximum number of objects to sync in a single transaction

        Returns:
            None

        Raises:
            ValueError: If no table name is defined or no primary key is found
        """
        # Handle single object case
        if not isinstance(objects, list):
            objects = [objects]

        if not objects:
            return  # Nothing to sync

        table_name = cls._get_sql_table_name()
        if table_name is None:
            raise ValueError("Cannot sync without a table name defined")

        # Find primary key
        primary_key = None
        for field_name, field_info in cls.model_fields.items():
            if field_info.json_schema_extra and field_info.json_schema_extra.get(
                "primary_key", False
            ):
                primary_key = field_name
                break

        if not primary_key:
            raise ValueError("Cannot sync without a primary key defined")

        # Process in batches
        for i in range(0, len(objects), batch_size):
            upper_idx = min(i + batch_size, len(objects))
            batch = objects[i:upper_idx]

            # Build a SQL transaction for this batch
            all_values = []
            columns = list(batch[0].model_dump().keys())
            columns_str = ", ".join(columns)
            placeholders = ", ".join(["%s"] * len(columns))
            set_clause = ", ".join([f"{col} = EXCLUDED.{col}" for col in columns])

            # Collect values for this batch
            for obj in batch:
                if not isinstance(obj, cls):
                    raise TypeError(
                        f"Expected instance of {cls.__name__}, got {type(obj).__name__}"
                    )

                data = obj.model_dump()
                row_values = []
                for col in columns:
                    value = data[col]
                    row_values.append(obj._prepare_value(value))
                all_values.extend(row_values)

            # Build the SQL statement for this batch
            values_placeholders = ", ".join([f"({placeholders})" for _ in batch])

            sql_statement = f"""
                INSERT INTO {table_name} ({columns_str})
                VALUES {values_placeholders}
                ON CONFLICT ({primary_key}) DO UPDATE
                SET {set_clause}
            """

            cls.sql(sql_statement, all_values)
