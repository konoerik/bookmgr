import sqlite3
from dataclasses import replace

import pytest

from bookmgr.models import Book, BookFormat, FormatKind
from bookmgr.storage import index
from bookmgr.storage.catalog import save_metadata
from bookmgr.storage.store import Catalog


def _new_book(root, title, author=None):
    directory = root / title
    directory.mkdir()
    (directory / f"{title}.epub").write_bytes(b"epub bytes")
    return Book(
        title=title,
        author=author,
        isbn=None,
        formats=[BookFormat(kind=FormatKind.EPUB, path=directory / f"{title}.epub")],
    ), directory


@pytest.fixture
def root(tmp_path):
    root = tmp_path / "Library"
    root.mkdir()
    return root


def test_put_new_book_saves_metadata_sets_directory_and_indexes_it(root):
    catalog = Catalog(root)
    book, directory = _new_book(root, "Deep Work", "Cal Newport")

    catalog.put(book, directory)

    assert book.directory == directory
    assert (directory / "metadata.json").exists()
    assert [b.directory for b in catalog.search("newport")] == [directory]


def test_put_existing_book_uses_its_own_directory(root):
    catalog = Catalog(root)
    book, directory = _new_book(root, "Deep Work", "Cal Newport")
    catalog.put(book, directory)

    book.author = "C. Newport"
    catalog.put(book)  # no directory argument needed

    assert catalog.get(directory).author == "C. Newport"
    assert catalog.search("cal newport") == []
    assert [b.title for b in catalog.search("c. newport")] == ["Deep Work"]


def test_put_without_any_directory_is_an_error(root):
    with pytest.raises(ValueError):
        Catalog(root).put(Book(title="T", author=None, isbn=None))


def test_all_returns_books_in_folder_order_skipping_unreadable_folders(root):
    catalog = Catalog(root)
    for title in ("Zebra", "Apple"):
        book, directory = _new_book(root, title)
        catalog.put(book, directory)
    (root / "Not A Book").mkdir()
    (root / "Broken").mkdir()
    (root / "Broken" / "metadata.json").write_text("{")

    assert [b.title for b in catalog.all()] == ["Apple", "Zebra"]


def test_all_raises_file_not_found_for_missing_root(tmp_path):
    with pytest.raises(FileNotFoundError):
        Catalog(tmp_path / "missing").all()


def test_puts_rebuild_the_index_once_when_missing_and_never_again(root, monkeypatch):
    catalog = Catalog(root)
    real_rebuild = index.rebuild_index
    rebuilds = []

    def _counting_rebuild(library_root, db_path):
        rebuilds.append(db_path)
        real_rebuild(library_root, db_path)

    monkeypatch.setattr(index, "rebuild_index", _counting_rebuild)

    for title in ("A", "B", "C"):
        book, directory = _new_book(root, title)
        catalog.put(book, directory)

    assert len(rebuilds) == 1  # the first put found no index
    assert [b.title for b in catalog.search("")] == ["A", "B", "C"]


def test_search_rebuilds_an_index_from_an_older_layout(root):
    catalog = Catalog(root)
    book, directory = _new_book(root, "Deep Work", "Cal Newport")
    save_metadata(book, directory)
    # Pre-R3 index: absolute-path rows, no schema stamp.
    db_path = root / ".bookmgr-index.sqlite3"
    conn = sqlite3.connect(db_path)
    conn.execute("CREATE TABLE books (directory TEXT PRIMARY KEY, title TEXT)")
    conn.commit()
    conn.close()

    [found] = catalog.search("deep")

    assert found.directory == directory
    assert index.is_current(db_path)


def test_search_omits_a_matched_folder_whose_metadata_vanished(root):
    catalog = Catalog(root)
    book, directory = _new_book(root, "Deep Work", "Cal Newport")
    catalog.put(book, directory)
    (directory / "metadata.json").unlink()

    assert catalog.search("deep") == []


def test_reindex_replaces_the_index_with_the_given_books(root):
    catalog = Catalog(root)
    book, directory = _new_book(root, "Deep Work", "Cal Newport")
    catalog.put(book, directory)
    other, other_dir = _new_book(root, "Sapiens", "Harari")
    save_metadata(other, other_dir)  # bypasses put, so the index does not know it
    assert catalog.search("harari") == []

    catalog.reindex(catalog.all())

    assert [b.title for b in catalog.search("harari")] == ["Sapiens"]
    assert [b.title for b in catalog.search("deep")] == ["Deep Work"]


def test_reindex_failure_is_logged_not_raised(root, caplog):
    """The index is a cache; a scan must not fail because it could not
    be refreshed."""
    catalog = Catalog(root)
    book, directory = _new_book(root, "Deep Work", "Cal Newport")
    catalog.put(book, directory)
    catalog._index_path = root  # a directory: the replace cannot succeed

    with caplog.at_level("WARNING", logger="bookmgr.storage"):
        catalog.reindex(catalog.all())

    assert "could not refresh the search index" in caplog.text


def test_rebuild_index_repairs_a_hand_edited_library(root):
    catalog = Catalog(root)
    book, directory = _new_book(root, "Deep Work", "Cal Newport")
    catalog.put(book, directory)
    # A folder added by hand, bypassing put.
    other, other_dir = _new_book(root, "Sapiens", "Harari")
    save_metadata(other, other_dir)
    assert catalog.search("harari") == []

    catalog.rebuild_index()

    assert [b.title for b in catalog.search("harari")] == ["Sapiens"]


# --- the index's hashes and stamps (ADR-40) ------------------------------


def test_holding_finds_the_book_with_a_hash_and_ignores_others(root):
    catalog = Catalog(root)
    book, directory = _new_book(root, "Deep Work")
    book.formats = [replace(book.formats[0], sha256="ab" * 32)]
    catalog.put(book, directory)

    found = catalog.holding(["ab" * 32, "cd" * 32])

    assert list(found) == ["ab" * 32]
    assert [b.id for b in found["ab" * 32]] == [book.id]


def test_rows_restate_every_book_and_follow_a_hand_edit(root):
    import json

    catalog = Catalog(root)
    book, directory = _new_book(root, "Deep Work", "Cal Newport")
    catalog.put(book, directory)
    assert [(r.name, r.title) for r in catalog.rows()] == [("Deep Work", "Deep Work")]

    metadata = directory / "metadata.json"
    data = json.loads(metadata.read_text())
    data["title"] = "Deep Work, Edited By Hand"
    metadata.write_text(json.dumps(data))

    assert [r.title for r in catalog.rows()] == ["Deep Work, Edited By Hand"]


def test_rows_drop_a_folder_removed_behind_bookmgrs_back(root):
    import shutil

    catalog = Catalog(root)
    for title in ("Dune", "Emma"):
        book, directory = _new_book(root, title)
        catalog.put(book, directory)
    shutil.rmtree(root / "Dune")

    assert [r.name for r in catalog.rows()] == ["Emma"]
    assert [b.title for b in catalog.search("")] == ["Emma"]


def test_rows_pick_up_a_book_folder_added_behind_bookmgrs_back(root):
    from bookmgr.storage.catalog import save_metadata as save

    catalog = Catalog(root)
    catalog.rows()  # build the index while the library is empty
    book, directory = _new_book(root, "Dune")
    save(book, directory)

    assert [r.name for r in catalog.rows()] == ["Dune"]
