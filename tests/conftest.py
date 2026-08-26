"""Test fixture to ensure DB connection."""
import pytest
from pathlib import Path

@pytest.fixture(scope="session")
def db_config():
    """Return database configuration string for testing."""
    return "postgresql://postgres:postgres@localhost:5432/postgres"
