# Changelog

All notable changes to this project are documented here. The format follows
[Keep a Changelog](https://keepachangelog.com/en/1.1.0/) and the project uses
[Semantic Versioning](https://semver.org/).

## [Unreleased]

## [2.0.1] - 2026-10-31

### Changed
- The PyPI project page now shows a short readme (`docs/PYPI.md`):
  what bookmgr does, how to install it, and links to the full README,
  the frontend guide and this changelog. The README's release section
  says that tagging publishes to PyPI.

### Fixed
- The package docstring no longer lists MOBI among the supported
  formats; bookmgr imports EPUB and PDF only.

## [2.0.0] - 2026-10-26

The project is renamed `bookmgr` and published on PyPI for the first
time. Apart from the names, nothing changed: the API and the CLI behave
exactly as in 1.3.0.

### Changed
- **Breaking:** the project is renamed `bookmgr`, because PyPI's
  `bookman` is an unrelated project (ADR-45). Everything that said
  `bookman` now says `bookmgr`: the distribution (`uv add bookmgr`), the
  import package (`from bookmgr import Library`), the CLI command, the
  `"bookmgr"` logger, `BookmanError` → `BookmgrError`, the environment
  variables `BOOKMGR_LIBRARY` and `BOOKMGR_CONFIG`, the config folder
  (`bookmgr/`), and the GitHub repository (`konoerik/bookmgr`). There are
  no aliases for the old names.
- **Breaking:** a library is marked by `.bookmgr-library.json` and indexed
  in `.bookmgr-index.sqlite3`. To keep using a 1.x library, rename its
  `.bookman-library.json` to `.bookmgr-library.json` and delete
  `.bookman-index.sqlite3` (the next `scan` rebuilds the index). Move the
  saved config from the old `bookman/` config folder to `bookmgr/`, or run
  `bookmgr init` again.

## [1.3.0] - 2026-10-04

For the TUI's import screens: recognizing files already in the library,
saying why a book has no record, covers a user can fix, and imports that
stay fast as the library grows.

### Added
- A file whose exact bytes the library already holds is recognized
  before it is parsed or looked up and changes nothing: `iter_import`
  yields an `AlreadyInLibrary` outcome and `ImportBatchResult.unchanged`
  collects them; `bookman import` prints "already in library"
  (spec GROUP-0, ADR-40).
- `Library.find_file(path)` and `Library.find_files(paths)`: which book
  already holds a file, offline and without importing, for an import
  preview (ADR-40).
- `Book.added` (when the import that created the book ran) and
  `BookFormat.sha256` (the hash of each file's bytes), in metadata.json
  schema 6; older books read None and are upgraded on their next save
  (ADR-40).
- `Book.lookup`, a `LookupOutcome`: identified, no match, failed, or not
  attempted (offline), so a frontend can retry exactly the failed
  lookups (spec `lookup_outcome`, ADR-41).
- `Library.set_cover(book, image | None)` and
  `Library.reidentify(book, replace_cover=True)`: supply, replace or
  remove a cover without touching a reviewed book's other fields
  (ADR-42).
- `ReadIssue.summary`: a short, sentence-cased label beside `advice`.
- `LibraryNotFoundError.reason` (a `LibraryNotFoundReason`) and
  `.location` (ADR-43).

### Changed
- Re-importing a file already in the library no longer re-runs its
  lookup; `reidentify` is the retry (ADR-40).
- Public functions and methods that take a path accept a `str` or any
  path-like object (ADR-43).
- `LibraryNotFoundError` messages name a next step in frontend-neutral
  words; the CLI adds its `bookman init` hint (ADR-43).
- Importing into a large library is faster: grouping reads the search
  index, checked against each `metadata.json`'s modification time and
  size, rather than every `metadata.json` (about 3x at 2000 books).
  The index's schema changes and it rebuilds itself.

### Fixed
- `reidentify` no longer clears `identified` when its lookup fails or
  finds nothing that agrees, as its docstring always said (ADR-41).

## [1.2.0] - 2026-09-27

For frontends: one way to open the configured library, telling a
library from any other folder, and a guide to the public API.

### Added
- `Config.offline`: a saved setting that turns off Open Library lookups
  and cover downloads, so imports catalog each book from its file alone
  (ADR-38).
- `configured_library()`: opens the configured library with the source
  its settings choose, the one way for a frontend to build its `Library`
  (ADR-38).
- `docs/API.md`: a task-oriented guide for frontend authors.
- A library is marked by `.bookman-library.json` at its root, and
  `is_library(path)` tells a library from any other folder (ADR-39).
- `locate_library()` returns the library root together with where it was
  named (`LibraryLocation`, `LibraryOrigin`) (ADR-39).

### Changed
- `bookman import` opens the library through `configured_library` and
  says in its header when lookups are off; `bookman config` shows the
  setting; `bookman init` keeps the other saved settings.
- `configured_library` opens only an existing library unless
  `create=True`, raising the new `LibraryNotFoundError`, so a saved
  library on a disconnected drive is reported instead of recreated empty
  (ADR-39). The CLI's `list`, `search` and `import` refuse a missing
  library or a folder of other files; `import --library <new dir>` still
  creates one. `bookman config` says where the library path came from.

## [1.1.0] - 2026-09-26

From running the rest of the author's library (340 books, 603 files)
through bookman; see `docs/FIELD-NOTES.md`, FN-11..21.

### Added
- `ReadIssue` and `BookFormat.read_issue`: why bookman could not read
  inside a file it still imported, with `ReadIssue.advice` naming the
  next step (ADR-29).
- `bookman[crypto]` optional extra (PyCryptodome) to read AES-encrypted
  PDFs, such as every InformIT PDF (ADR-29).
- An EPUB whose metadata declares no ISBN has its front matter scanned
  for one, flagged as scraped (Packt; ADR-33).

### Changed
- A PDF bookman cannot read inside -- AES without the extra, a real
  password, a DRM handler, a null `/Encrypt` -- is imported under its
  filename and flagged for review instead of failing (ADR-29). A file
  that is not a PDF at all still fails, with a message saying to check
  it opens in a PDF reader.
- `metadata.json` schema version 5: a format entry may carry
  `read_issue`. Version 4 files load and are upgraded on save.
- Title fuzz stays within a word: a swapped word ("Excel" / "Access")
  no longer matches however long the title (ADR-30). Words run together
  still match, and a trailing inverted article ("…, The") is dropped.
- A volume marker ("Volume 2", "Part II", "Volume Two") survives the
  subtitle and bracket rules, so volumes stay apart (ADR-31).
- A layout tool's filename as the title ("css.indb") is a placeholder,
  and the operator login beside it is dropped (ADR-32).
- Two titles also agree when their full forms do, for a colon that is
  not a subtitle ("Python 3: Pocket Primer"; ADR-34).
- An import whose stronger identification changes a book's title now
  renames its folder and files, as an edit does (ADR-36).
- Search leaves a trailing bracketed tag ("(Humble)") out of the query,
  and retries by title alone when title and author find nothing
  (ADR-37).

### Fixed
- A copy that fails midway (a full disk) no longer leaves a truncated
  file or a half-imported folder, and a failed re-import no longer
  destroys the copy already in the library; the CLI says to free up
  space and import again (ADR-35).

## [1.0.0] - 2026-09-20

First release. EPUB and PDF parsing, ISBN extraction, Open Library lookup
and title/author search behind a `MetadataSource` protocol, an
evidence-based match rule for identification and grouping, a flat
title-named library layout with `metadata.json` per book, a sqlite search
index, persisted library config, and the `bookman init` / `import` /
`list` / `search` / `config` CLI. MOBI files are recognized and reported
as skipped, not parsed.

Shipped after a real bundle went through it: 37 No Starch and O'Reilly
titles imported, every EPUB+PDF pair grouped, every book with a cover
(see `docs/FIELD-NOTES.md`). The public API in `bookman.__all__` is
frozen from here under semantic versioning.

The sections below record what changed during development, since the
ADRs in `docs/ARCHITECTURE.md` refer to them.

### Added
- The EPUB's own embedded cover is used when identification supplies
  none — no Open Library record, a record without a cover, or a failed
  download (ADR-28). A record's cover still takes precedence. In the
  first real bundle this took covers from 16 of 37 books to 37 of 37.
- `docs/FIELD-NOTES.md`: a running register of what real bundles do that
  the test suite did not predict, numbered `FN-n` so ADRs and FEATURES
  rows can cite them.
- Progress while importing a directory: `Library.iter_import` yields an
  `ImportEvent` before each file is attempted and again with its outcome
  (the `Book`, a `FormatConflictError`, or the exception that failed it),
  so a frontend can show which file it is waiting on and a progress
  fraction; stopping the iteration cancels the rest of the batch.
  `import_directory` is unchanged and now collects the same events via
  `ImportBatchResult.record`. `bookman import <dir>` prints each file's
  line as it finishes (`[3/41] foo.epub ... imported: …`) instead of
  going quiet until the whole batch is done.
- Curation: `Library.mark_reviewed`, `Library.edit` and
  `Library.reidentify` — the half of the review workflow that was
  missing. `edit` corrects a book's title, author or ISBN, renaming its
  folder and format files when the title changes, normalizing an ISBN to
  ISBN-13 and refusing an invalid one. Editing marks a book reviewed, so
  the correction is not overwritten the next time another format of that
  book is imported. `reidentify` looks a book up again; a reviewed book
  keeps everything a human set and gains only a cover it was missing,
  which is the way to get a cover for a book Open Library could not match
  on its own.
- A book now holds one file per format kind, and an import that would
  put a *different* file where one already is — a second EPUB edition, or
  two unrelated books that grouped by title — is refused instead of
  silently overwriting it. `Library.import_file` raises
  `FormatConflictError`, which carries the book, the file it already
  holds, how the file joined it (ISBN, title and author, or title only)
  and what the refused file resolved to, so a frontend can ask the user
  what they meant. `Library.import_directory` collects these in
  `ImportBatchResult.conflicts`, separate from `failed`. Re-importing the
  same file (same bytes, any name) stays idempotent. `bookman import`
  reports each refusal with the reason and how to replace the file.
- `Book.id` — a stable identity minted once per book and stored in
  `metadata.json`, which moves to schema version 3. Unlike `Book.directory`
  it survives a rename of the book's folder, so a frontend can hold a
  reference to a book, edit its title, and still be talking about the same
  book afterwards. Libraries written by earlier versions are migrated on
  read: a book with no stored id gets a deterministic one derived from its
  folder name, which becomes a stored id the next time it is saved. Schema
  versions 2 and 3 are both readable, and version 1 keeps its existing
  migration path.

- `Book.record_author` — what the Open Library record named as the
  author, kept beside the book's own `author` so a frontend can show
  "Open Library says …" and offer it as an alternative spelling.
  `metadata.json` moves to schema version 4 to carry it; versions 2 and 3
  are read as before and upgraded on the next save.

- `Library.scan()` refreshes the search index from the `metadata.json`
  files it reads, so a book fixed by editing its `metadata.json` by hand
  is found by `search` after the next `scan` (or `bookman list`) without
  a repair step.

### Changed
- The CLI is for import and inspection only: `init`, `config`, `import`,
  `list`, `search`. Fixing a book is a frontend's job (`Library.edit`,
  `Library.mark_reviewed`, `Library.reidentify` from Python) or a hand
  edit of `metadata.json`; the README says how.
- On an accepted Open Library match the file's own author now stands,
  the same way its title already did; the record's author is used only
  when the file names none. Open Library returns the *work's* author
  list — every edition's contributors, so an audiobook's narrator was
  landing on the book as a co-author. Files whose own author is a
  stand-in for a blank ("Unknown", "N/A") are treated as having none
  and get the record's author instead; "Anonymous" and "Various" are
  kept as written.
- A different edition is now a different book, whatever punctuation the
  title uses. An ordinal edition marker — "2nd Edition", "Second Edition",
  "2nd ed." — is recognized before the subtitle and bracket rules run,
  so "Algorithmic Thinking (2nd Edition)" and "Algorithmic Thinking: 2nd
  Edition" no longer group with the first edition (they did; the comma
  form never did). Two files carrying the same edition, however written,
  still group, and a shared ISBN still identifies an edition file
  against its edition record.

### Fixed
- Grouping a PDF with its EPUB when the PDF's copyright page lists
  several ISBNs (print, ebook, prior editions): the join now considers
  every ISBN the file carries, not only the one Open Library answered
  first (ADR-26). And a follow-up file identified through a *different*
  ISBN than the one it joined on — a title-less PDF citing the previous
  edition's number — no longer renames the book to that edition or
  fetches its cover (ADR-27). Real case: *The Rust Programming Language,
  3rd Edition* was being relabelled as the 2nd edition.
- The PDF ISBN scan now covers the first 10 pages instead of 5. Every
  No Starch PDF puts the copyright page at index 5, so their ISBNs — and
  for the quarter of them with an empty info dictionary, their only
  metadata — were never seen.
- A PDF whose `/Title` is a placeholder ("untitled") is shelved under its
  filename stem, or the accepted record's title, as the spec always said
  (IDENT-4), instead of a folder called `untitled`.
- A junk title no longer groups unrelated files. A *placeholder* —
  "Untitled", "Untitled Document 2", "No Title", or a converter's
  filename stamp ("Microsoft Word - chapter1.docx") — now normalizes to
  nothing and counts as no title at all: it matches nothing and is no
  longer searched for on Open Library. A merely *generic* title —
  "Book", "Final Draft", "New Document" — is still searched and can
  still be matched, but no longer on its own: it needs an agreeing
  author, so two unrelated files called "Book" stay two books while
  Alan Watts' "The Book" is identified as before. Neither kind vetoes a
  shared ISBN, exactly as a missing title never did.
- Volumes of a set ("... Volume 1" / "... Volume 2", "Part II" / "Part III")
  no longer merge into one book: the fuzzy title comparison now requires the
  numbers in both titles to match before consulting the similarity ratio.
- A shared ISBN no longer groups two files whose title *and* author both
  contradict each other (a false-positive ISBN scraped from PDF text);
  grouping now applies the same guard identification already did.
- An ISBN scraped from a PDF's page text is no longer accepted on the
  strength of a shared author alone (the "Also by this author" citation
  case); it now needs the record's title to agree with the file's. ISBNs
  from an EPUB's `dc:identifier` are unaffected.
- A file carrying several ISBNs — a print and an ebook ISBN, or a cited
  list — now has each tried in turn until one is accepted. Previously only
  the first was looked up, so if Open Library did not know it, or its
  record contradicted the file, the rest were never tried. A rejected ISBN
  is dropped; the first one Open Library does not know is kept as the
  file's own claim.
- ISBN lookup works again. Open Library's Books API (`/api/books`) stopped
  answering — 404 on every bibkey — which left every ISBN-based
  identification falling through to title search. The lookup now goes
  through the Search API (`/search.json?isbn=`), which answers in one
  request with the same document shape title search already uses.
  Requests also now carry a `bookman/<version>` User-Agent, as Open
  Library asks of API clients.
- An ISBN from a file's metadata is no longer accepted on the strength
  of a record whose title contradicts the file's and which names no
  author. Previously "title and author must both disagree" let a record
  with no author through, so a mis-keyed ISBN landing on some other
  book's record was identified with confidence. Now the title
  disagreement stands unless the author agrees; the ISBN is dropped and
  the file goes to title search instead (ADR-19).
- A generational suffix ("Martin Luther King Jr.", "King, Martin
  Luther, Jr.") is no longer taken as the surname when authors are
  compared, so such a file now agrees with Open Library's record
  instead of being vetoed on author.

### Added
- `ImportBatchResult` is exported from `bookman` itself, so a frontend
  reporting an import run no longer has to import it from
  `bookman.library`.
- `ParsedMetadata.isbns_scraped` records whether a parser found its ISBNs
  by scanning text (PDF) rather than in a metadata field (EPUB);
  `match_basis` takes a matching `isbn_scraped` keyword.

[Unreleased]: https://github.com/konoerik/bookmgr/compare/v2.0.1...HEAD
[2.0.1]: https://github.com/konoerik/bookmgr/releases/tag/v2.0.1
[2.0.0]: https://github.com/konoerik/bookmgr/releases/tag/v2.0.0
[1.3.0]: https://github.com/konoerik/bookmgr/releases/tag/v1.3.0
[1.2.0]: https://github.com/konoerik/bookmgr/releases/tag/v1.2.0
[1.1.0]: https://github.com/konoerik/bookmgr/releases/tag/v1.1.0
[1.0.0]: https://github.com/konoerik/bookmgr/releases/tag/v1.0.0
