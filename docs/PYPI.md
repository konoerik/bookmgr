# bookmgr

A local ebook library manager. Point it at a folder of purchased ebook
files, such as EPUB and PDF bundles from Humble Bundle, and it:

- identifies each book from its own metadata and any ISBN printed inside it
- fetches metadata and cover art from [Open Library](https://openlibrary.org/)
- files everything into a flat, title-named library, with the EPUB and PDF
  of the same book in one folder
- flags any book it couldn't identify with confidence for review, instead of
  guessing

It is a library first, with a small CLI on top, built so a frontend (such as
the companion TUI) can drive it. Format conversion and device sync are out of
scope.

## Install

Requires Python 3.10+.

```bash
uv tool install "bookmgr[crypto]"   # the command-line tool
uv add bookmgr                      # as a dependency
```

The `crypto` extra lets bookmgr read AES-encrypted PDFs. Without it, such a
PDF is still imported, named after its file.

(The `bookman` package on PyPI is an unrelated bookmarks tool. This project
was called bookman until 2.0.0.)

## Command line

```bash
bookmgr init ~/Books                     # create the library and remember it
bookmgr import ~/Downloads/humble-bundle # import every EPUB/PDF in a folder
bookmgr list --needs-review              # books whose match should be checked
bookmgr search "newport"                 # substring match on title or author
```

## As a library

```python
from bookmgr import configured_library

lib = configured_library()
for book in lib.scan():
    print(book.title, book.author, book.needs_review)
```

## More

- [Full README](https://github.com/konoerik/bookmgr#readme): library layout,
  how identification works, development
- [Frontend guide](https://github.com/konoerik/bookmgr/blob/main/docs/API.md):
  the public API, by task
- [Changelog](https://github.com/konoerik/bookmgr/blob/main/CHANGELOG.md)

MIT licensed.
