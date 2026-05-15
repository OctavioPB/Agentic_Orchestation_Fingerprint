"""Integration test configuration. Tests in this directory require Docker."""
from __future__ import annotations

import pytest


def pytest_configure(config: pytest.Config) -> None:
    config.addinivalue_line(
        "markers",
        "integration: mark test as requiring a running Docker daemon (skipped in unit CI)",
    )


def pytest_collection_modifyitems(
    config: pytest.Config, items: list[pytest.Item]
) -> None:
    """Auto-mark all tests in tests/integration/ with the 'integration' marker."""
    for item in items:
        if "integration" in str(item.fspath):
            item.add_marker(pytest.mark.integration)
