"""bookmgr: local ebook library management.

Identifies, catalogs, and organizes EPUB/PDF/MOBI files by title,
independent of any frontend (a companion TUI consumes this as a library).
"""

from __future__ import annotations

import logging

from bookmgr.config import (
    Config,
    LibraryLocation,
    LibraryOrigin,
    config_path,
    configured_library,
    load_config,
    locate_library,
    resolve_library,
    save_config,
)
from bookmgr.errors import (
    BookmgrError,
    CatalogError,
    ConfigError,
    FormatConflictError,
    LibraryNotConfiguredError,
    LibraryNotFoundError,
    LibraryNotFoundReason,
    MetadataSourceError,
    ParseError,
    UnsupportedFormatError,
)
from bookmgr.formats import supported_suffixes
from bookmgr.formats.epub import BadEpubError
from bookmgr.formats.pdf import BadPdfError
from bookmgr.identify.openlibrary import OpenLibraryError, OpenLibrarySource
from bookmgr.identify.source import Candidate, MetadataSource, NullSource
from bookmgr.library import AlreadyInLibrary, ImportBatchResult, ImportEvent, Library, is_library
from bookmgr.models import Book, BookFormat, FormatKind, LookupOutcome, MatchBasis, ReadIssue

# Library convention: emit under the "bookmgr" logger and let the
# application decide whether anything is shown.
logging.getLogger("bookmgr").addHandler(logging.NullHandler())

__all__ = [
    "AlreadyInLibrary",
    "BadEpubError",
    "BadPdfError",
    "Book",
    "BookFormat",
    "BookmgrError",
    "Candidate",
    "CatalogError",
    "Config",
    "ConfigError",
    "FormatConflictError",
    "FormatKind",
    "ImportBatchResult",
    "ImportEvent",
    "Library",
    "LibraryLocation",
    "LibraryNotConfiguredError",
    "LibraryNotFoundError",
    "LibraryNotFoundReason",
    "LibraryOrigin",
    "LookupOutcome",
    "MatchBasis",
    "MetadataSource",
    "MetadataSourceError",
    "NullSource",
    "OpenLibraryError",
    "OpenLibrarySource",
    "ParseError",
    "ReadIssue",
    "UnsupportedFormatError",
    "config_path",
    "configured_library",
    "is_library",
    "load_config",
    "locate_library",
    "resolve_library",
    "save_config",
    "supported_suffixes",
]
