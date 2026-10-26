"""The exception hierarchy a frontend can rely on."""

import pytest

import bookmgr
from bookmgr import (
    BadEpubError,
    BadPdfError,
    BookmgrError,
    CatalogError,
    ConfigError,
    LibraryNotConfiguredError,
    MetadataSourceError,
    OpenLibraryError,
    ParseError,
    UnsupportedFormatError,
)


@pytest.mark.parametrize(
    ("error", "parents"),
    [
        (ParseError, (BookmgrError, ValueError)),
        (BadEpubError, (ParseError,)),
        (BadPdfError, (ParseError,)),
        (UnsupportedFormatError, (BookmgrError, ValueError)),
        (MetadataSourceError, (BookmgrError,)),
        (OpenLibraryError, (MetadataSourceError,)),
        (CatalogError, (BookmgrError, ValueError)),
        (ConfigError, (BookmgrError, ValueError)),
        (LibraryNotConfiguredError, (BookmgrError,)),
    ],
)
def test_every_bookmgr_error_has_its_documented_parents(error, parents):
    for parent in parents:
        assert issubclass(error, parent)
    assert issubclass(error, BookmgrError)


def test_every_exported_error_is_a_bookmgr_error():
    exported = [
        getattr(bookmgr, name)
        for name in bookmgr.__all__
        if isinstance(getattr(bookmgr, name), type)
        and issubclass(getattr(bookmgr, name), BaseException)
    ]
    assert exported, "no error types exported?"
    assert all(issubclass(e, BookmgrError) for e in exported)


def test_corrupt_metadata_raises_catalog_error(tmp_path):
    from bookmgr.storage.catalog import load_metadata

    (tmp_path / "metadata.json").write_text("{")
    with pytest.raises(CatalogError):
        load_metadata(tmp_path)


def test_bad_config_file_raises_config_error(tmp_path, monkeypatch):
    from bookmgr import config

    path = tmp_path / "config.json"
    path.write_text("nope")
    monkeypatch.setenv(config.ENV_CONFIG, str(path))
    with pytest.raises(ConfigError):
        config.load_config()
