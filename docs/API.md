# Frontend guide

How to build a frontend (a TUI, a GUI, a script) on bookmgr. This guide is
organized by task. For the exact signatures, read the docstrings, which are the
per-function reference. `src/bookmgr/cli.py` is a complete frontend built on
nothing but this API and serves as the worked example throughout.

Everything below is importable from `bookmgr`. The public surface is exactly
`bookmgr.__all__`, and anything else is internal. A test checks that every
exported name appears in this guide.

Every function or method that takes a filesystem path accepts a `str` or any
path-like object as well as a `Path` (ADR-43).

## 1. Open the library

```python
from bookmgr import configured_library

library = configured_library()  # the saved library, which must exist
library = configured_library(Path(pick), create=True)  # a new one the user chose
```

`configured_library` is the one way a frontend should build its `Library`. It
resolves the root in the same order everywhere: the argument you pass (a
`--library` flag, a folder picker), then `$BOOKMGR_LIBRARY`, then the saved
config. It also takes the metadata source from the saved config: Open Library,
or none when the user turned lookups off. The CLI and the TUI therefore always
agree on both the library and the source (ADR-8, ADR-38).

By default it opens only a library that already exists. A saved library on a
drive that isn't connected raises `LibraryNotFoundError` instead of being
silently recreated, empty, on the internal disk (ADR-39). Pass `create=True`
only for a folder the user has just chosen for a new library. An existing empty
folder is accepted either way.

It raises:

- `LibraryNotConfiguredError` when nothing names a library (first run: offer to
  create one).
- `LibraryNotFoundError` when the root is missing, is a file, or holds other
  files but no library. Its `reason` (a `LibraryNotFoundReason`: `MISSING`,
  `NOT_A_DIRECTORY`, `NOT_A_LIBRARY`) says which, so you can offer your own
  next step (retry when a drive is connected, choose another folder) without
  re-checking the disk. `path` is the root and `location` is the
  `LibraryLocation` that named it. The message says what happened and the next
  step in words that suit any frontend; the CLI adds its own `bookmgr init`
  hint (ADR-43).
- `ConfigError` when the config file is malformed (its message names the file).

### First run: is this folder a library?

When the user picks a folder, `is_library(path)` tells the cases apart without
touching anything:

| The folder | `is_library` | Offer |
|---|---|---|
| A bookmgr library | True | Open it: `configured_library(path)` |
| Missing, or empty | False | Create a library there: `configured_library(path, create=True)` |
| Holds other files (`~/Books` full of EPUBs) | False | A library is a folder of its own: suggest a new folder inside it, then import these files |

A library is marked by a `.bookmgr-library.json` file at its root, written when
it is created or first opened. A library from before the marker existed is
recognised by its book folders and gets marked the next time it is opened.
`Library(root)` itself always creates and marks `root`, so call it only on a
folder meant to be a library.

### Which library, and why

`locate_library(explicit)` returns a `LibraryLocation`: the `path`, its
`origin` (a `LibraryOrigin`: `EXPLICIT`, `ENVIRONMENT` or `CONFIG`), and the
`config_file` when the saved config named it. `describe()` gives the phrase
("set by $BOOKMGR_LIBRARY", "saved in …"). A settings screen can show it, and
warn when a flag or the environment variable overrides the saved choice (compare
with `load_config().library`). `bookmgr config` shows it.

### Settings

The persisted settings are a `Config`:

| Field | Meaning |
|---|---|
| `library` | The library's root directory |
| `offline` | Never look books up online: no Open Library search and no cover download. Every book is cataloged from what its file says |

- `load_config()` returns the saved `Config`, or None before first setup.
- `save_config(config)` writes it atomically.
- `config_path()` says where the file lives (per platform; `$BOOKMGR_CONFIG`
  overrides it).
- `resolve_library(explicit)` gives just the root, without opening anything.

To change one setting, keep the others:

```python
import dataclasses
from bookmgr import Config, load_config, save_config

current = load_config() or Config(library=chosen_root)
save_config(dataclasses.replace(current, offline=True))
```

Saving a fresh `Config(library=...)` resets every other field to its default.
`bookmgr init` (`_cmd_init`) and `bookmgr config` (`_cmd_config`) show both
patterns.

`Library(root, source=...)` is still available when you want to choose the
source yourself, as tests do. `Library` never reads the config on its own.

## 2. Import with progress

```python
from bookmgr import (
    AlreadyInLibrary,
    Book,
    FormatConflictError,
    ImportBatchResult,
    UnsupportedFormatError,
)

result = ImportBatchResult()
for event in library.iter_import(folder, recursive=True):
    result.record(event)
    progress = event.index / event.total
    match event.outcome:
        case None:  # about to hash, parse + look up this file
            show_working_on(event.path)
        case AlreadyInLibrary() as hit:  # these exact bytes are already here
            show_unchanged(event.path, hit.book)
        case Book() as book:  # imported; the book as it stands now
            show_imported(event.path, book)
        case FormatConflictError() as conflict:
            ask_user_about(conflict)  # refused; nothing changed
        case UnsupportedFormatError():  # skipped, never attempted
            show_skipped(event.path)
        case Exception() as error:  # this file failed; the batch goes on
            show_failed(event.path, error)
```

`iter_import` yields an `ImportEvent` for every step. `total` counts every
non-hidden file in the batch and is known from the first event, so a progress
bar is exact from the start. Each file gets a "starting" event (outcome None)
before the slow part (the parse and the network lookup), followed by its
result. The exception is a skipped file, which gets only its result event.
`ImportBatchResult.record` sorts the events into `imported`, `unchanged`,
`failed`, `skipped` and `conflicts`, which gives the same summary
`import_directory` returns if you don't need progress. The CLI's `_cmd_import`
is this loop.

**A file already in the library** costs a hash and nothing else. If a book
already holds a file with the same bytes, nothing is parsed, looked up, copied
or written, and the outcome is an `AlreadyInLibrary`: `source` (the file
offered), `book` (the book holding it) and `existing` (that book's
`BookFormat`). A re-import is therefore not a retry of a failed lookup; use
`reidentify` for that (section 5). On its own, `import_file` returns the holding
book unchanged (spec GROUP-0, ADR-40).

### Preview: which of these do I already have?

```python
held = library.find_files(picked_paths)  # {path: Book} for the ones already here
for path in picked_paths:
    mark(path, held.get(path))
```

`find_file(path)` and `find_files(paths)` answer offline without importing:
each file is read once to hash it, and one index query covers the lot. Files
placed before bookmgr recorded hashes (libraries from before 1.3) are not found
until they are next imported.

For one file, `library.import_file(path)` returns the `Book` or raises. Files
with a suffix outside `supported_suffixes()` are skipped in a batch and raise
`UnsupportedFormatError` on their own. Use that function to filter a file
picker.

**Run imports off the UI thread.** A lookup can take seconds. A library assumes
one writer at a time: one import, one edit. Reads (`scan`, `search`) are safe
alongside a writer. See the `Library` docstring.

### A refused file

A book holds one file per kind (ADR-21). A different EPUB for a book that
already has one raises `FormatConflictError`, and nothing is changed. It
carries what you need to ask the user what they meant: `source` (the refused
file), `book` and `existing` (what it collided with), `basis` (how it joined),
and the refused file's own `title`/`author`/`isbn`. An ISBN `basis` means
"same book, which file do you want?". A `TITLE_ONLY` basis means "was this even
the same book?"

## 3. Read the catalog

```python
books = library.scan()  # every book, in folder-name order
hits = library.search("newport")  # title/author substring, case-insensitive
```

Both return fresh `Book` objects read from each folder's `metadata.json`. That
file is the source of truth; the sqlite index only speeds up `search` and is
rebuilt when missing. A folder whose `metadata.json` cannot be read is skipped
rather than failing the call. `scan` also re-indexes, so a `metadata.json`
edited by hand shows up in `search` after the next scan.

## 4. What a `Book` tells you

| Field | Meaning |
|---|---|
| `id` | Stable identity (a uuid hex). Use it for list keys and selection: it survives a title edit, which renames the folder (ADR-17) |
| `title` | Display title. The file's own spelling when it had one (ADR-10) |
| `author` | The file's author string, or None |
| `record_author` | What the online record called the author, kept beside `author` as an alternative spelling to offer ("Open Library says…"). A difference is not a problem |
| `isbn` | ISBN-13 found in one of the files, or None |
| `formats` | One `BookFormat` per file: `kind` (a `FormatKind`: `EPUB`, `PDF`), `path`, `read_issue`, and `sha256` (the hash of the file's bytes, None for files placed before 1.3) |
| `cover_path` | The cover on disk, or None. Always named `cover.png`, but the bytes are as received (often JPEG). Sniff the format; don't trust the suffix |
| `identified` | A `MatchBasis` saying how the online record was matched to the file (`ISBN`, `TITLE_AUTHOR`, `TITLE_ONLY`), or None if no record agreed and everything came from the file |
| `grouped` | The weakest `MatchBasis` that ever joined a second file into this book, or None for a single file |
| `reviewed` | A human confirmed or corrected this book; imports won't overwrite it |
| `needs_review` | Derived: not reviewed, and identified weakly or not at all, or grouped on title alone. This is the review queue |
| `lookup` | A `LookupOutcome` saying what happened when bookmgr looked the book up: `IDENTIFIED` (exactly when `identified` is set), `NO_MATCH` (the source answered and nothing agreed, or the file named nothing to look up), `FAILED` (a request failed: `reidentify` may find it) or `NOT_ATTEMPTED` (offline). None for an unidentified book from before 1.3 |
| `added` | When the import that created the book ran, as a timezone-aware UTC `datetime`, for sorting by arrival. None for books from before 1.3 |
| `directory` | The book's folder: where it lives, and its display name. Not its identity |

A `BookFormat.read_issue` is a `ReadIssue`. It means bookmgr could not read
inside that file (encrypted, password, DRM), so the book was named after the
filename. `read_issue.advice` is the sentence to show the user, and it always
names the next step. The CLI prints it in `_print_read_issue`.
`read_issue.summary` is a short, sentence-cased label for a list row or a
status line ("Password-protected").

The rules behind `identified` and `grouped` are specified in
`docs/IDENTIFICATION.md`. To explain a flagged book, show which basis was weak.

## 5. Curate

```python
library.mark_reviewed(book)  # take it off the queue
library.mark_reviewed(book, False)  # put it back
library.edit(book, title="Deep Work", author=None, isbn="978-1-4555-8669-1")
library.reidentify(book)  # look it up again
library.reidentify(book, replace_cover=True)  # ...and take the record's cover
library.set_cover(book, picked_image)  # a local PNG/JPEG/GIF/WebP
library.set_cover(book, None)  # no cover
```

Each call takes a `Book` from `scan`, `search` or an import, saves it, and
returns the same object updated. Frontends own curation; the CLI deliberately
has none (ADR-24).

- `edit` changes only the fields you pass (None clears `author`/`isbn`), **sets
  `reviewed`** so the edit is durable, and renames the folder and files when
  the title changes. Re-read `directory`, `formats` and `cover_path` afterwards.
- `reidentify` runs the lookup again. It is the usual route to a missing cover,
  and the retry for books whose `lookup` is `FAILED`
  (`[b for b in library.scan() if b.lookup is LookupOutcome.FAILED]`). On a
  reviewed book it only fills gaps. A lookup that fails or finds nothing changes
  nothing but `lookup`.
- To replace a wrong cover, `reidentify(book, replace_cover=True)` takes the
  record's cover even on a reviewed book, and leaves its title, author and ISBN
  alone. `set_cover(book, image)` uses a local image instead, and
  `set_cover(book, None)` removes the cover. Both `set_cover` calls **set
  `reviewed`**, so a later import can't replace the user's choice (ADR-42). A
  file that isn't a PNG, JPEG, GIF or WebP image raises `CatalogError`.

## 6. Errors

Everything bookmgr raises on purpose is a `BookmgrError`. Anything else
(`OSError`, a bug) is not one:

| Error | When |
|---|---|
| `LibraryNotConfiguredError` | No library is named anywhere |
| `LibraryNotFoundError` | The named root is missing, a file, or not a library; `reason` says which (section 1) |
| `ConfigError` | The config file is unreadable or the wrong shape |
| `UnsupportedFormatError` | The suffix has no parser |
| `ParseError` | The file isn't really its format: `BadEpubError`, `BadPdfError` |
| `FormatConflictError` | The book already has a different file of this kind (section 2) |
| `CatalogError` | A `metadata.json` is broken, or a curation call got a bad value (blank title, invalid ISBN, a cover that isn't an image, an unsaved book) |
| `MetadataSourceError` | A lookup failed (`OpenLibraryError` for Open Library). Never escapes `Library`: a failed lookup means "no record", and the book is cataloged from its file |

Messages name the file or setting involved and say what to do next where there
is a next step, so they can be shown to the user as they are.

## 7. Plug in a metadata source

A source is anything that satisfies the `MetadataSource` protocol:

```python
from bookmgr import Candidate, MetadataSourceError


class MySource:
    def lookup_by_isbn(self, isbn: str) -> Candidate | None: ...
    def search(self, title: str, author: str | None = None) -> list[Candidate]: ...
    def fetch_cover(self, url: str) -> bytes: ...


library = Library(root, source=MySource())
```

Return a `Candidate` (`title`, `author`, `cover_url`) per record, best first.
A missing record is None or an empty list, not an error. A failed request
raises `MetadataSourceError` and nothing else. Your source only proposes
candidates. bookmgr decides whether one is the same book as the file, by the
rules in `docs/IDENTIFICATION.md`. `OpenLibrarySource` is the default source,
and `NullSource` knows nothing (offline). Choosing among several sources from
the config is not built yet (FEATURES N8).

## Logging

bookmgr logs under the `"bookmgr"` logger with a `NullHandler`, so nothing
shows unless your application configures logging. Swallowed failures (a lookup
timeout, a skipped `metadata.json`) are logged there, which gives a frontend a
debug pane for free.
