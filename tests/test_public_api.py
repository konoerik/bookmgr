"""The package's public surface: what a frontend may import from `bookmgr`.

`bookmgr.__init__` is the contract (CLAUDE.md: "Public API lives in
`src/bookmgr/__init__.py`; keep the public surface minimal"). These tests
pin the names a frontend reaches for, so adding or dropping one is a
deliberate, semver-visible act rather than an accident.
"""

import re
from pathlib import Path

import bookmgr
from bookmgr import library


def test_every_exported_name_resolves():
    missing = [name for name in bookmgr.__all__ if not hasattr(bookmgr, name)]
    assert not missing


def test_all_is_sorted_and_free_of_duplicates():
    assert bookmgr.__all__ == sorted(bookmgr.__all__)
    assert len(bookmgr.__all__) == len(set(bookmgr.__all__))


def test_batch_result_is_exported_from_the_package_root():
    """A frontend reporting an import run shouldn't have to reach into
    `bookmgr.library` for the type `import_directory` hands back."""
    assert "ImportBatchResult" in bookmgr.__all__
    assert bookmgr.ImportBatchResult is library.ImportBatchResult
    assert "ImportEvent" in bookmgr.__all__
    assert bookmgr.ImportEvent is library.ImportEvent


def test_every_exported_name_is_covered_by_the_frontend_guide():
    """docs/API.md is the task-oriented guide to the public surface; a new
    export has to find its place there (as `Name`, `Name.attr` or `Name(`)."""
    guide = (Path(__file__).parents[1] / "docs" / "API.md").read_text(encoding="utf-8")
    missing = [
        name for name in bookmgr.__all__ if not re.search(rf"`{re.escape(name)}[`.(\[]", guide)
    ]
    assert not missing, f"not mentioned in docs/API.md: {missing}"
