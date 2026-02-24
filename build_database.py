"""
build_database.py

Reads every PDF in the `pdfs/` folder, extracts text with PyMuPDF (fitz),
and loads the content into a SQLite database with full-text search indexes.

Schema
------
newsletters  – one row per issue
pages        – one row per page per issue
newsletters_fts – FTS5 virtual table over newsletters
pages_fts       – FTS5 virtual table over pages

Usage:
    python build_database.py
    python build_database.py --pdf-dir /path/to/pdfs --db crowsnest_heritage.db
"""

import argparse
import re
import sqlite3
from pathlib import Path

import fitz  # PyMuPDF

# ---------------------------------------------------------------------------
# Configuration defaults
# ---------------------------------------------------------------------------

DEFAULT_PDF_DIR = Path("pdfs")
DEFAULT_DB_PATH = Path("crowsnest_heritage.db")

# Regex to try to parse issue number and date from a PDF filename.
# Examples:  HV_Issue_42_May2018.pdf   HeritageViews-2022-03.pdf
ISSUE_RE = re.compile(r"(?:issue[_\-\s]?(\d+))|(?:(\d{4})[_\-](\d{2}))", re.IGNORECASE)


# ---------------------------------------------------------------------------
# Database setup
# ---------------------------------------------------------------------------


def init_db(conn: sqlite3.Connection):
    conn.executescript(
        """
        PRAGMA journal_mode=WAL;

        CREATE TABLE IF NOT EXISTS newsletters (
            id          INTEGER PRIMARY KEY AUTOINCREMENT,
            filename    TEXT    UNIQUE NOT NULL,
            issue_num   INTEGER,
            year        INTEGER,
            month       INTEGER,
            page_count  INTEGER,
            full_text   TEXT
        );

        CREATE TABLE IF NOT EXISTS pages (
            id              INTEGER PRIMARY KEY AUTOINCREMENT,
            newsletter_id   INTEGER NOT NULL REFERENCES newsletters(id),
            page_num        INTEGER NOT NULL,
            text            TEXT
        );

        CREATE VIRTUAL TABLE IF NOT EXISTS newsletters_fts
            USING fts5(filename, full_text, content=newsletters, content_rowid=id);

        CREATE VIRTUAL TABLE IF NOT EXISTS pages_fts
            USING fts5(text, content=pages, content_rowid=id);
        """
    )
    conn.commit()


# ---------------------------------------------------------------------------
# FTS sync triggers (keep FTS in sync with content tables)
# ---------------------------------------------------------------------------


def create_triggers(conn: sqlite3.Connection):
    conn.executescript(
        """
        CREATE TRIGGER IF NOT EXISTS newsletters_ai AFTER INSERT ON newsletters BEGIN
            INSERT INTO newsletters_fts(rowid, filename, full_text)
            VALUES (new.id, new.filename, new.full_text);
        END;

        CREATE TRIGGER IF NOT EXISTS newsletters_ad AFTER DELETE ON newsletters BEGIN
            INSERT INTO newsletters_fts(newsletters_fts, rowid, filename, full_text)
            VALUES ('delete', old.id, old.filename, old.full_text);
        END;

        CREATE TRIGGER IF NOT EXISTS pages_ai AFTER INSERT ON pages BEGIN
            INSERT INTO pages_fts(rowid, text) VALUES (new.id, new.text);
        END;

        CREATE TRIGGER IF NOT EXISTS pages_ad AFTER DELETE ON pages BEGIN
            INSERT INTO pages_fts(pages_fts, rowid, text)
            VALUES ('delete', old.id, old.text);
        END;
        """
    )
    conn.commit()


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def parse_filename(filename: str) -> tuple[int | None, int | None, int | None]:
    """Return (issue_num, year, month) parsed from filename, or (None, None, None)."""
    m = ISSUE_RE.search(filename)
    if not m:
        return None, None, None
    if m.group(1):
        return int(m.group(1)), None, None
    return None, int(m.group(2)), int(m.group(3))


def extract_text(pdf_path: Path) -> tuple[str, list[str], int]:
    """Return (full_text, [page_texts], page_count) for a PDF."""
    doc = fitz.open(str(pdf_path))
    page_texts = []
    for page in doc:
        page_texts.append(page.get_text())
    doc.close()
    full_text = "\n\n".join(page_texts)
    return full_text, page_texts, len(page_texts)


def already_indexed(conn: sqlite3.Connection, filename: str) -> bool:
    row = conn.execute(
        "SELECT id FROM newsletters WHERE filename = ?", (filename,)
    ).fetchone()
    return row is not None


def index_pdf(conn: sqlite3.Connection, pdf_path: Path):
    filename = pdf_path.name
    if already_indexed(conn, filename):
        print(f"  Skipping (already indexed): {filename}")
        return

    print(f"  Indexing: {filename} … ", end="", flush=True)
    try:
        full_text, page_texts, page_count = extract_text(pdf_path)
    except Exception as exc:
        print(f"ERROR: {exc}")
        return

    issue_num, year, month = parse_filename(filename)

    cur = conn.execute(
        """
        INSERT INTO newsletters (filename, issue_num, year, month, page_count, full_text)
        VALUES (?, ?, ?, ?, ?, ?)
        """,
        (filename, issue_num, year, month, page_count, full_text),
    )
    newsletter_id = cur.lastrowid

    conn.executemany(
        "INSERT INTO pages (newsletter_id, page_num, text) VALUES (?, ?, ?)",
        [(newsletter_id, i + 1, text) for i, text in enumerate(page_texts)],
    )
    conn.commit()
    print(f"OK ({page_count} pages, {len(full_text):,} chars)")


# ---------------------------------------------------------------------------
# Main
# ---------------------------------------------------------------------------


def main():
    parser = argparse.ArgumentParser(description="Build SQLite FTS database from PDFs.")
    parser.add_argument(
        "--pdf-dir", type=Path, default=DEFAULT_PDF_DIR, help="Folder containing PDFs."
    )
    parser.add_argument(
        "--db", type=Path, default=DEFAULT_DB_PATH, help="Output SQLite database path."
    )
    args = parser.parse_args()

    if not args.pdf_dir.exists():
        print(f"PDF directory not found: {args.pdf_dir}")
        print("Run download_crowsnest_pdfs.py first.")
        return

    pdfs = sorted(args.pdf_dir.glob("*.pdf"))
    if not pdfs:
        print(f"No PDFs found in {args.pdf_dir}.")
        return

    print(f"Found {len(pdfs)} PDFs in {args.pdf_dir}")
    print(f"Database: {args.db}\n")

    conn = sqlite3.connect(args.db)
    init_db(conn)
    create_triggers(conn)

    for pdf_path in pdfs:
        index_pdf(conn, pdf_path)

    conn.close()

    total = sqlite3.connect(args.db).execute("SELECT COUNT(*) FROM newsletters").fetchone()[0]
    print(f"\nDone. {total} newsletters in database: {args.db.resolve()}")


if __name__ == "__main__":
    main()
