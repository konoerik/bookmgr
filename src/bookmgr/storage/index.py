"""Disposable sqlite3 search cache, rebuilt from metadata.json sidecars.

storage.catalog's metadata.json files are the source of truth. This index
exists purely so a TUI (or anything else) can filter/search quickly without
re-reading every metadata.json on each keystroke. Deleting the database
file and calling rebuild_index again always reproduces it faithfully.

Rows are keyed by the book folder's *name* (relative to the library
root), never an absolute path, so a relocated library keeps a valid
index. `PRAGMA user_version` stamps the schema; an index written by an
older layout is detected by `is_current` and rebuilt by its owner
(storage.store.Catalog) rather than read.
"""

from __future__ import annotations

import logging
import os
import sqlite3
from collections.abc import Iterable
from dataclasses import dataclass
from pathlib import Path

from bookman.errors import CatalogError
from bookman.models import Book
from bookman.storage.catalog import load_metadata

_log = logging.getLogger("bookman.storage")
_SCHEMA_VERSION = 3
_CREATE_TABLES = (
    """
    CREATE TABLE books (
        name TEXT PRIMARY KEY,
        title TEXT NOT NULL,
        author TEXT,
        isbn TEXT,
        needs_review INTEGER NOT NULL,
        stamp TEXT
    )
    """,
    # One row per format file with a recorded hash (ADR-40). Not unique:
    # nothing stops the same bytes being copied into two folders by hand.
    "CREATE TABLE files (sha256 TEXT NOT NULL, name TEXT NOT NULL)",
    "CREATE INDEX files_by_sha256 ON files (sha256)",
)
_UPSERT = (
    "INSERT OR REPLACE INTO books (name, title, author, isbn, needs_review, stamp) "
    "VALUES (?, ?, ?, ?, ?, ?)"
)
_INSERT_FILE = "INSERT INTO files (sha256, name) VALUES (?, ?)"


@dataclass(frozen=True)
class Row:
    """What the index holds about one book: enough to judge grouping
    (spec GROUP-1/2) without reading its metadata.json.

    Attributes:
        name: The book folder's name, relative to the library root.
        title: The book's title.
        author: The book's author, or None.
        isbn: The book's ISBN-13, or None.
        stamp: The modification time and size of the metadata.json
            the row was taken from (see `stamp`), or None if unknown.
            A row whose stamp no longer matches the file is stale.
    """

    name: str
    title: str
    author: str | None
    isbn: str | None
    stamp: str | None = None


def stamp(metadata_json: Path) -> str | None:
    """A fingerprint of a metadata.json file -- its modification time in
    nanoseconds and its size -- that changes when the file is rewritten,
    including by hand. None if the file cannot be read.

    Args:
        metadata_json: The file to fingerprint.
    """
    try:
        info = metadata_json.stat()
    except OSError:
        return None
    return f"{info.st_mtime_ns}:{info.st_size}"


def rebuild_index(library_root: Path, db_path: Path) -> None:
    """Rebuild the search index from every metadata.json under library_root.

    Scans each immediate subdirectory of `library_root` for a
    metadata.json (via storage.catalog.load_metadata), and writes one
    row per book into a fresh sqlite3 database at `db_path`, replacing
    any existing database file. Subdirectories without a metadata.json,
    or with one that fails to parse, are skipped rather than raising.

    Args:
        library_root: The managed library's top-level directory, whose
            immediate subdirectories are book folders.
        db_path: Where to write the sqlite3 database file.

    Raises:
        OSError: If library_root does not exist, or db_path cannot be
            written.
    """
    rows = []
    for directory in sorted(p for p in library_root.iterdir() if p.is_dir()):
        try:
            rows.append((directory.name, load_metadata(directory)))
        except FileNotFoundError:
            continue  # not a book folder
        except CatalogError as exc:
            _log.warning("not indexing %s: %s", directory, exc)
    write_index(db_path, rows)


def write_index(db_path: Path, rows: Iterable[tuple[str, Book]]) -> None:
    """Write a fresh index holding exactly `rows`, replacing any database
    at `db_path` in one step (built beside it, then moved into place, so
    a concurrent reader sees either the old index or the new one).

    The counterpart of `rebuild_index` for a caller that has already
    loaded the books -- `Catalog.all` pays that pass anyway, so a scan
    can bring the index back in step with hand-edited metadata.json
    files at no extra read (ADR-12 amendment).

    Args:
        db_path: Where the sqlite3 database file lives.
        rows: (folder name, book) pairs, folder names relative to the
            library root.

    Raises:
        OSError: If db_path cannot be written.
    """
    tmp_path = db_path.with_name(db_path.name + ".tmp")
    if tmp_path.exists():
        tmp_path.unlink()
    conn = sqlite3.connect(tmp_path)
    try:
        for statement in _CREATE_TABLES:
            conn.execute(statement)
        conn.execute(f"PRAGMA user_version = {_SCHEMA_VERSION}")
        for name, book in rows:
            conn.execute(_UPSERT, _row(name, book, library_root=db_path.parent))
            conn.executemany(_INSERT_FILE, _file_rows(name, book))
        conn.commit()
    finally:
        conn.close()
    os.replace(tmp_path, db_path)


def is_current(db_path: Path) -> bool:
    """Whether `db_path` is an index this module can read: it exists and
    carries the current schema stamp. False for a missing file or one
    written by an older layout (which must be rebuilt, not read).

    Args:
        db_path: Path to a sqlite3 database file.
    """
    if not db_path.exists():
        return False
    conn = sqlite3.connect(db_path)
    try:
        version: int = conn.execute("PRAGMA user_version").fetchone()[0]
    except sqlite3.DatabaseError:
        return False
    finally:
        conn.close()
    return version == _SCHEMA_VERSION


def upsert(db_path: Path, name: str, book: Book) -> None:
    """Insert or replace the row for one book folder.

    Args:
        db_path: Path to a sqlite3 database previously built by
            rebuild_index.
        name: The book folder's name, relative to the library root.
        book: The book as just saved to that folder.

    Raises:
        FileNotFoundError: If db_path does not exist.
    """
    if not db_path.exists():
        raise FileNotFoundError(db_path)
    conn = sqlite3.connect(db_path)
    try:
        conn.execute(_UPSERT, _row(name, book, library_root=db_path.parent))
        conn.execute("DELETE FROM files WHERE name = ?", (name,))
        conn.executemany(_INSERT_FILE, _file_rows(name, book))
        conn.commit()
    finally:
        conn.close()


def delete(db_path: Path, name: str) -> None:
    """Drop the row for one book folder, if present.

    Args:
        db_path: Path to a sqlite3 database previously built by
            rebuild_index.
        name: The book folder's name, relative to the library root.

    Raises:
        FileNotFoundError: If db_path does not exist.
    """
    if not db_path.exists():
        raise FileNotFoundError(db_path)
    conn = sqlite3.connect(db_path)
    try:
        conn.execute("DELETE FROM books WHERE name = ?", (name,))
        conn.execute("DELETE FROM files WHERE name = ?", (name,))
        conn.commit()
    finally:
        conn.close()


def search(db_path: Path, query: str) -> list[str]:
    """Search the index for books whose title or author matches query.

    Case-insensitive substring match against the indexed title and
    author columns. Case-folding is done via a registered Python
    function (str.casefold), not SQL's `COLLATE NOCASE` -- NOCASE only
    folds ASCII A-Z/a-z, so it silently fails to match e.g. Greek
    "Λ"/"λ" or accented "É"/"é". Does not read metadata.json itself --
    callers join the returned names back onto the library root and
    load the full Book via storage.catalog.load_metadata.

    Args:
        db_path: Path to a sqlite3 database previously built by
            rebuild_index.
        query: Substring to search for in title or author.

    Returns:
        Matching book folder names (relative to the library root), in
        folder-name order. Empty list if nothing matches or the index
        is empty.

    Raises:
        FileNotFoundError: If db_path does not exist.
    """
    if not db_path.exists():
        raise FileNotFoundError(db_path)

    conn = sqlite3.connect(db_path)
    try:
        conn.create_function("casefold", 1, lambda s: (s or "").casefold())
        like = f"%{query.casefold()}%"
        rows = conn.execute(
            "SELECT name FROM books "
            "WHERE casefold(title) LIKE ? OR casefold(author) LIKE ? "
            "ORDER BY name",
            (like, like),
        ).fetchall()
    finally:
        conn.close()
    return [str(row[0]) for row in rows]


def rows(db_path: Path) -> list[Row]:
    """Every indexed book's grouping fields, in folder-name order.

    Args:
        db_path: Path to a sqlite3 database previously built by
            rebuild_index.

    Returns:
        One Row per indexed book.

    Raises:
        FileNotFoundError: If db_path does not exist.
    """
    if not db_path.exists():
        raise FileNotFoundError(db_path)
    conn = sqlite3.connect(db_path)
    try:
        found = conn.execute(
            "SELECT name, title, author, isbn, stamp FROM books ORDER BY name"
        ).fetchall()
    finally:
        conn.close()
    return [Row(*row) for row in found]


def names_by_hash(db_path: Path, hashes: Iterable[str]) -> dict[str, list[str]]:
    """The book folders holding a format file with each of `hashes`.

    Args:
        db_path: Path to a sqlite3 database previously built by
            rebuild_index.
        hashes: Hex SHA-256 digests to look for.

    Returns:
        For each digest found, the folder names holding it, in
        folder-name order. Digests found nowhere are absent.

    Raises:
        FileNotFoundError: If db_path does not exist.
    """
    if not db_path.exists():
        raise FileNotFoundError(db_path)
    wanted = sorted(set(hashes))
    found: dict[str, list[str]] = {}
    conn = sqlite3.connect(db_path)
    try:
        # Chunked to stay under sqlite's bound-parameter limit.
        for start in range(0, len(wanted), 500):
            chunk = wanted[start : start + 500]
            marks = ",".join("?" * len(chunk))
            for digest, name in conn.execute(
                f"SELECT sha256, name FROM files WHERE sha256 IN ({marks}) ORDER BY name",
                chunk,
            ):
                found.setdefault(digest, []).append(name)
    finally:
        conn.close()
    return found


def _file_rows(name: str, book: Book) -> list[tuple[str, str]]:
    return [(fmt.sha256, name) for fmt in book.formats if fmt.sha256 is not None]


def _row(
    name: str, book: Book, *, library_root: Path
) -> tuple[str, str, str | None, str | None, int, str | None]:
    metadata_json = library_root / name / "metadata.json"
    return (name, book.title, book.author, book.isbn, int(book.needs_review), stamp(metadata_json))
