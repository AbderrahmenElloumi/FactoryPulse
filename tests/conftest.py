"""Fixtures shared by more than one host test module."""

import pytest


@pytest.fixture
def env():
    """The pipeline env vars set on every Spark job service in compose.yaml."""
    return {
        "MINIO_ENDPOINT": "minio:9000",
        "MINIO_ACCESS_KEY": "factorypulse",
        "MINIO_SECRET_KEY": "factorypulse-dev-pass",
        "MINIO_BUCKET": "factorypulse",
    }
