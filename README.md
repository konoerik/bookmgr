# bookmgr

A local ebook library manager. Point it at a folder of purchased ebook files
(EPUB/PDF bundles from Humble Bundle and the like), and it identifies each
book, fetches metadata and cover art from [Open Library](https://openlibrary.org/)
(falling back to the cover embedded in the EPUB),
and files everything into a flat, title-named library — grouping the EPUB and
PDF of the same book under one folder.

It is built as a library first, with a small CLI on top; a separate TUI
consumes it as a frontend.

## Install

Requires Python 3.10+.

```bash
# as a command-line tool
uv tool install "bookmgr[crypto]"

# as a dependency of your own project
uv add bookmgr
```

Each [GitHub Release](https://github.com/konoerik/bookmgr/releases) also
carries the wheel. Until 2.0.0, the project was called `bookman`; the
`bookman` package on PyPI is an unrelated bookmarks tool.

The `crypto` extra (PyCryptodome) lets bookmgr read AES-encrypted PDFs,
such as InformIT's. Without it such a PDF is still imported, named after
its file, and bookmgr says what to install to read it.

## Usage

```bash
bookmgr init ~/Books                     # create the library and remember it
bookmgr import ~/Downloads/humble-bundle # import every EPUB/PDF in a folder
bookmgr import book.epub                 # or a single file
bookmgr list                             # everything, sorted by title
bookmgr list --needs-review              # only books whose match should be checked
bookmgr search "newport"                 # substring match on title or author
bookmgr config                           # which library is in use, and why
```

The library location is resolved in this order: `--library DIR`, then
`$BOOKMGR_LIBRARY`, then the config saved by `bookmgr init` (in the platform
user-config directory; `$BOOKMGR_CONFIG` points it elsewhere).

## Library layout

```
~/Books/
├── .bookmgr-library.json                 # marks the folder as a library
├── .bookmgr-index.sqlite3                # disposable search index
├── Deep Work/
│   ├── Deep Work.epub
│   ├── Deep Work.pdf
│   ├── cover.png
│   └── metadata.json                     # source of truth for this book
└── Software Architecture - The Hard Parts/
    └── ...
```

Every book is one folder named after its title, holding all of its format
files, a cover, and a `metadata.json` sidecar. There is no author-level
nesting; the folder is the book's display name, and `metadata.json` carries
a stable `id` that survives a rename. `metadata.json` records not
just title/author/ISBN but *how* the book was identified (`isbn`,
`title_author`, `title_only`, or not at all) and the weakest evidence used to
group formats together, so a frontend can show why a book needs review
rather than just that it does.

## How identification works

1. Parse the file for its own metadata (EPUB OPF, PDF info dictionary) and
   scan its text for an ISBN.
2. If an ISBN was found, look it up on Open Library — but accept the record
   only if its title/author agree with what the file says about itself, so
   a false-positive ISBN scraped from a PDF can't replace good data.
3. Otherwise, search Open Library by title and author and take the strongest
   agreeing candidate.
4. Group the file with an existing book in the library by the same rule:
   exact ISBN first, then title + author, then identical title alone.

Imports never block for confirmation. A book that couldn't be identified
confidently is flagged for review instead, and a book a human has marked as
reviewed keeps its metadata across later imports.

Fixing a book is a frontend's job — the CLI only imports and inspects. From
Python, `Library.edit`, `Library.mark_reviewed` and `Library.reidentify` do
it; without a frontend, edit `title`, `author` or `isbn` in the book's
`metadata.json` and set `"reviewed": true` so the fix survives the next
import. `bookmgr list` picks such an edit up at once and refreshes the
search index from what it read, so `bookmgr search` sees it from then on.

## As a library

```python
from pathlib import Path

from bookmgr import configured_library

lib = configured_library()
result = lib.import_directory(Path("~/Downloads/humble-bundle").expanduser())
for book in lib.scan():
    print(book.title, book.author, book.needs_review)
```

`configured_library` opens the library the user set up, with the metadata
source their saved settings choose (`"offline": true` in the config turns
lookups off). `Library(root, source=...)` itself never reads global state.
Metadata lookups go through the `MetadataSource` protocol, so you can pass
`NullSource()` to work offline or plug in your own source. Every exception raised is a `BookmgrError`, and the package logs
under the `"bookmgr"` logger with a `NullHandler` installed.

**One writer at a time.** A library assumes a single process writes to it:
one TUI *or* one CLI command, not both at once. Reading while something else
writes is fine (every `metadata.json` is written atomically and the index is
swapped in one step), but two concurrent imports into the same library can
race on a book's folder, and the last `metadata.json` write wins. There is no
lock file; if you run two frontends, run them against different libraries.

The public API is exactly what `bookmgr/__init__.py` exports. `docs/API.md` is
the frontend guide to it, by task; `docs/ARCHITECTURE.md` has the design
decisions behind it.

## Development

```bash
uv sync                # editable install with dev extras
uv run pytest          # tests (no network access needed)
uv run pytest --cov
uv run ruff check .
uv run ruff format --check .
uv run mypy src/
uv build               # sdist + wheel into dist/
```

Releasing is tagging: `git tag v<version> && git push origin v<version>`
runs the checks, builds the wheel, publishes it to PyPI and then to a
GitHub Release (`.github/workflows/release.yml`). PyPI shows the short
`docs/PYPI.md`, not this file. See `CONTRIBUTING.md` for the
spec-first rule that governs changes to identification and grouping.

The `Makefile` wraps these and adds targets for a throwaway dev library
under `.dev/` (`make init`, `make import SRC=...`, `make list`, `make
clean-dev`) that keeps experiments out of your real config.

The only runtime dependency is `pypdf`; EPUB parsing and HTTP are stdlib.
Adding another is a deliberate decision, not a convenience.

## License

MIT — see [LICENSE](https://github.com/konoerik/bookmgr/blob/main/LICENSE). The test fixtures under `tests/fixtures/books/`
are public-domain texts from Project Gutenberg and carry their own headers.
