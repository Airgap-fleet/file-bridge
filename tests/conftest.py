"""Test fixture to ensure DB connection."""
from pathlib import Path

import pytest


@pytest.fixture(scope="session")
def db_config():
    """Return database configuration string for testing."""
    return "postgresql://postgres:postgres@localhost:5432/postgres"
