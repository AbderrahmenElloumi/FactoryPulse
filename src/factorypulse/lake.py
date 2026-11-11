"""Lake read module (ticket 12): how non-Spark code reads a lake table.

The dashboard and the quality checks read Delta tables through this module
and nowhere else. It owns the MinIO endpoint and credentials, the declared
columns of each table, the meaning of a missing table
(``LakeTableMissing``, never an empty frame) and of a built table that lacks a
declared column (``LakeColumnsMissing``, never a reader error).

``deltalake`` (and the pandas it returns) is imported inside ``read_table``,
never at module level: the Spark image runs Python 3.8 without ``deltalake``,
and importing this module there must not fail.
"""

from __future__ import annotations  # PEP 563: the spark image runs Python 3.8

import os
from typing import Any, Dict, Optional, Sequence

from factorypulse import analytics

# Docker creates this file in every container. Inside one, the compose service
# name resolves; a host process reaches the same storage on localhost.
CONTAINER_MARKER = "/.dockerenv"
STORAGE_SERVICE = "minio"


def _endpoint() -> str:
    endpoint = os.environ.get("MINIO_ENDPOINT", "localhost:9000")
    host, sep, port = endpoint.partition(":")
    if host == STORAGE_SERVICE and not os.path.exists(CONTAINER_MARKER):
        return f"localhost{sep}{port}"
    return endpoint


def storage_options() -> Dict[str, str]:
    """``deltalake`` options for MinIO, read from the environment.

    ``MINIO_ENDPOINT`` is ``host:port`` without a scheme, as compose sets it.
    """
    secure = os.environ.get("MINIO_SECURE", "false").lower() == "true"
    scheme = "https" if secure else "http"
    return {
        "AWS_ACCESS_KEY_ID": os.environ.get("MINIO_ACCESS_KEY", ""),
        "AWS_SECRET_ACCESS_KEY": os.environ.get("MINIO_SECRET_KEY", ""),
        "AWS_ENDPOINT_URL": f"{scheme}://{_endpoint()}",
        "AWS_REGION": "us-east-1",
        "AWS_ALLOW_HTTP": "false" if secure else "true",
    }


class LakeTableMissing(LookupError):
    """The named table has not been built: there is no Delta table at its path.

    Distinct from a built table with no rows, which reads as an empty frame.
    """

    def __init__(self, name: str, uri: str) -> None:
        super().__init__(f"lake table {name!r} has not been built (no Delta table at {uri})")
        self.name = name
        self.uri = uri


class LakeColumnsMissing(LookupError):
    """The named table is built but does not store every declared column."""

    def __init__(self, name: str, uri: str, missing: Sequence[str]) -> None:
        super().__init__(
            f"lake table {name!r} at {uri} lacks declared columns: {', '.join(missing)}"
        )
        self.name = name
        self.uri = uri
        self.missing = tuple(missing)


def read_table(name: str, root: Optional[str] = None) -> Any:
    """Read one lake table as a pandas DataFrame in its declared column order.

    ``root`` defaults to the object-store lake named by the environment; a
    local directory holding Delta tables works too.

    Raises ``LakeTableMissing`` when the table has not been built,
    ``LakeColumnsMissing`` when it is built without a declared column, and
    ``ValueError`` for a name with no declared columns.
    """
    if name not in analytics.TABLE_COLUMNS:
        raise ValueError(
            f"{name!r} has no declared columns: {tuple(analytics.TABLE_COLUMNS)}"
        )
    from deltalake import DeltaTable
    from deltalake.exceptions import TableNotFoundError

    columns = list(analytics.TABLE_COLUMNS[name])
    if root is None:
        root = analytics.lake_root(os.environ)
    # deltalake reads the object store as s3://; Spark and the registry say s3a://.
    if root.startswith("s3a://"):
        root = "s3://" + root[len("s3a://"):]
    uri = f"{root}/{name}"
    options = storage_options() if uri.startswith("s3://") else None
    try:
        table = DeltaTable(uri, storage_options=options)
    except TableNotFoundError as missing:
        raise LakeTableMissing(name, uri) from missing
    stored = {field.name for field in table.schema().fields}
    absent = [column for column in columns if column not in stored]
    if absent:
        raise LakeColumnsMissing(name, uri, absent)
    return table.to_pandas(columns=columns)
