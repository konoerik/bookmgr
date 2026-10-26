"""Every exception bookmgr raises on purpose, under one base class.

A frontend can catch `BookmgrError` to mean "bookmgr refused or failed
in a way it anticipated" and let anything else (OSError, a bug)
propagate. The subclasses that also inherit `ValueError` do so for
compatibility with code that already catches `ValueError` around the
same calls; the bookmgr type is the one to catch going forward.

Format-specific parse errors (`BadEpubError`, `BadPdfError`) live with
their parsers and subclass `ParseError`; the Open Library client's
`OpenLibraryError` subclasses `MetadataSourceError`.
"""

from __future__ import annotations

from enum import Enum
from pathlib import Path
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from bookmgr.config import LibraryLocation
    from bookmgr.models import Book, MatchBasis


class BookmgrError(Exception):
    """Base class for every exception bookmgr raises deliberately."""


class ParseError(BookmgrError, ValueError):
    """A file could not be read as the format its suffix claims."""


class UnsupportedFormatError(BookmgrError, ValueError):
    """A file's suffix has no registered format parser."""


class MetadataSourceError(BookmgrError):
    """A metadata source could not answer: network failure, non-2xx
    response, or a response it could not parse. `identify` treats it as
    "no record"; it never escapes `Library`."""


class CatalogError(BookmgrError, ValueError):
    """A book's metadata.json is unreadable, inconsistent, or unsafe
    (invalid JSON, a missing field, an unknown enum value or schema
    version, a filename that escapes the book's folder), or a Book was
    asked to be saved somewhere it cannot go."""


class FormatConflictError(BookmgrError):
    """A file was refused because the book it belongs to already holds a
    different file of the same format kind (spec GROUP-4, ADR-21).

    Nothing was changed: not the folder, not the catalog, not the book's
    evidence. The attributes are what a person needs to decide what to
    do -- keep what's there, replace it by hand, or conclude the two were
    never the same book.

    Attributes:
        source: The file that was refused.
        book: The cataloged book it would have joined, as it stands.
        existing: The file of the same kind the book already holds.
        basis: How the file joined that book. An ISBN join says "same
            book, which file do you want?"; a TITLE_ONLY join says "was
            this even the same book?".
        title: What the refused file resolved to, so it can be shown
        author: beside the book it collided with.
        isbn: (Likewise.)
    """

    def __init__(
        self,
        source: Path,
        book: Book,
        existing: Path,
        basis: MatchBasis,
        *,
        title: str,
        author: str | None,
        isbn: str | None,
    ) -> None:
        self.source = source
        self.book = book
        self.existing = existing
        self.basis = basis
        self.title = title
        self.author = author
        self.isbn = isbn
        super().__init__(
            f"{source}: {book.title!r} already has a different {existing.suffix.lstrip('.')} "
            f"file ({existing.name}); joined by {basis.value}"
        )


class ConfigError(BookmgrError, ValueError):
    """The user config file exists but is not valid."""


class LibraryNotConfiguredError(BookmgrError):
    """No library root can be resolved from any source."""


class LibraryNotFoundReason(str, Enum):
    """Why a named library root could not be opened (ADR-43)."""

    MISSING = "missing"
    """Nothing is there: often a drive that is not connected."""

    NOT_A_DIRECTORY = "not_a_directory"
    """The root is a file."""

    NOT_A_LIBRARY = "not_a_library"
    """The root is a folder of other files, not a bookmgr library."""


class LibraryNotFoundError(BookmgrError):
    """A library root was named, but there is no library there: the
    folder is missing (often a drive that is not connected), is a file,
    or holds other files and is not a bookmgr library.

    The message says what happened and the next step in words that suit
    any frontend; a frontend that offers its own steps (retry, choose
    another folder) reads `reason` instead of parsing it.

    Attributes:
        path: The root that was named.
        reason: Which of the three it is.
        location: The root and where it was named (`location.describe()`).
    """

    def __init__(
        self,
        path: Path,
        message: str,
        *,
        reason: LibraryNotFoundReason | None = None,
        location: LibraryLocation | None = None,
    ) -> None:
        """Args:
        path: The root that was named.
        message: What happened and what to do, for a person.
        reason: Why it could not be opened. Read off the filesystem
            when omitted.
        location: Where the root was named. "Passed explicitly" when
            omitted.
        """
        from bookmgr.config import LibraryLocation, LibraryOrigin

        self.path = path
        self.reason = reason if reason is not None else _reason_for(path)
        self.location = (
            location if location is not None else LibraryLocation(path, LibraryOrigin.EXPLICIT)
        )
        super().__init__(message)


def _reason_for(path: Path) -> LibraryNotFoundReason:
    if not path.exists():
        return LibraryNotFoundReason.MISSING
    if not path.is_dir():
        return LibraryNotFoundReason.NOT_A_DIRECTORY
    return LibraryNotFoundReason.NOT_A_LIBRARY


__all__ = [
    "BookmgrError",
    "CatalogError",
    "ConfigError",
    "FormatConflictError",
    "LibraryNotConfiguredError",
    "LibraryNotFoundError",
    "LibraryNotFoundReason",
    "MetadataSourceError",
    "ParseError",
    "UnsupportedFormatError",
]
