"""
search_database.py

CLI tool to search the Crowsnest Heritage newsletter database.

Usage:
    python search_database.py "Frank Slide"
    python search_database.py "coal mining" --pages
    python search_database.py "rum running" --limit 20
    python search_database.py --list
    python search_database.py "Hillcrest" --pages --context 300
"""

import argparse
import sqlite3
import textwrap
from pathlib import Path

DEFAULT_DB = Path("crowsnest_heritage.db")
DEFAULT_LIMIT = 10
DEFAULT_CONTEXT = 200  # characters of surrounding text to show per match


# ---------------------------------------------------------------------------
# Search helpers
# ---------------------------------------------------------------------------


def search_newsletters(conn: sqlite3.Connection, query: str, limit: int) -> list[dict]:
    """Full-text search at the newsletter (issue) level."""
    rows = conn.execute(
        """
        SELECT
            n.filename,
            n.issue_num,
            n.year,
            n.month,
            n.page_count,
            snippet(newsletters_fts, 1, '[', ']', '…', 20) AS snippet
        FROM newsletters_fts
        JOIN newsletters n ON newsletters_fts.rowid = n.id
        WHERE newsletters_fts MATCH ?
        ORDER BY rank
        LIMIT ?
        """,
        (query, limit),
    ).fetchall()

    return [
        {
            "filename": r[0],
            "issue_num": r[1],
            "year": r[2],
            "month": r[3],
            "page_count": r[4],
            "snippet": r[5],
        }
        for r in rows
    ]


def search_pages(conn: sqlite3.Connection, query: str, limit: int, context: int) -> list[dict]:
    """Full-text search at the individual page level."""
    rows = conn.execute(
        """
        SELECT
            n.filename,
            n.issue_num,
            n.year,
            n.month,
            p.page_num,
            snippet(pages_fts, 0, '[', ']', '…', 20) AS snippet
        FROM pages_fts
        JOIN pages p ON pages_fts.rowid = p.id
        JOIN newsletters n ON p.newsletter_id = n.id
        WHERE pages_fts MATCH ?
        ORDER BY rank
        LIMIT ?
        """,
        (query, limit),
    ).fetchall()

    return [
        {
            "filename": r[0],
            "issue_num": r[1],
            "year": r[2],
            "month": r[3],
            "page_num": r[4],
            "snippet": r[5],
        }
        for r in rows
    ]


def list_newsletters(conn: sqlite3.Connection) -> list[dict]:
    rows = conn.execute(
        """
        SELECT filename, issue_num, year, month, page_count
        FROM newsletters
        ORDER BY issue_num NULLS LAST, year, month
        """
    ).fetchall()
    return [
        {
            "filename": r[0],
            "issue_num": r[1],
            "year": r[2],
            "month": r[3],
            "page_count": r[4],
        }
        for r in rows
    ]


# ---------------------------------------------------------------------------
# Display helpers
# ---------------------------------------------------------------------------

MONTH_NAMES = [
    "", "Jan", "Feb", "Mar", "Apr", "May", "Jun",
    "Jul", "Aug", "Sep", "Oct", "Nov", "Dec",
]


def fmt_issue(row: dict) -> str:
    parts = []
    if row.get("issue_num"):
        parts.append(f"Issue #{row['issue_num']}")
    if row.get("year"):
        date = str(row["year"])
        if row.get("month"):
            date = f"{MONTH_NAMES[row['month']]} {date}"
        parts.append(date)
    if not parts:
        parts.append(row["filename"])
    return "  |  ".join(parts)


def print_separator(char="─", width=72):
    print(char * width)


# ---------------------------------------------------------------------------
# Main
# ---------------------------------------------------------------------------


def main():
    parser = argparse.ArgumentParser(
        description="Search the Crowsnest Heritage newsletter archive.",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog=textwrap.dedent(
            """\
            Examples:
              python search_database.py "Frank Slide"
              python search_database.py "coal mining" --pages
              python search_database.py --list
            """
        ),
    )
    parser.add_argument("query", nargs="?", help="Search terms (FTS5 syntax supported).")
    parser.add_argument(
        "--pages", action="store_true", help="Search at page level instead of issue level."
    )
    parser.add_argument(
        "--limit", type=int, default=DEFAULT_LIMIT, help=f"Max results (default {DEFAULT_LIMIT})."
    )
    parser.add_argument(
        "--context",
        type=int,
        default=DEFAULT_CONTEXT,
        help=f"Characters of context around matches (default {DEFAULT_CONTEXT}).",
    )
    parser.add_argument(
        "--list", action="store_true", help="List all newsletters in the database."
    )
    parser.add_argument(
        "--db", type=Path, default=DEFAULT_DB, help="Path to SQLite database."
    )
    args = parser.parse_args()

    if not args.db.exists():
        print(f"Database not found: {args.db}")
        print("Run build_database.py first.")
        return

    conn = sqlite3.connect(args.db)

    # --list mode
    if args.list:
        newsletters = list_newsletters(conn)
        print(f"\n{'Crowsnest Heritage Newsletter Archive':^72}")
        print_separator()
        print(f"{'#':>4}  {'Issue / Date':<30}  {'Pages':>5}  {'File'}")
        print_separator("-")
        for i, n in enumerate(newsletters, 1):
            issue = fmt_issue(n)
            pages = n["page_count"] or "?"
            print(f"{i:>4}.  {issue:<30}  {str(pages):>5}  {n['filename']}")
        print_separator()
        print(f"Total: {len(newsletters)} newsletters\n")
        conn.close()
        return

    # Search mode
    if not args.query:
        parser.print_help()
        conn.close()
        return

    if args.pages:
        results = search_pages(conn, args.query, args.limit, args.context)
        mode_label = "Page-level"
    else:
        results = search_newsletters(conn, args.query, args.limit, args.context)
        mode_label = "Issue-level"

    conn.close()

    print(f"\n{mode_label} search: "{args.query}"  →  {len(results)} result(s)\n")
    print_separator()

    if not results:
        print("No matches found.")
        print_separator()
        return

    for r in results:
        print(fmt_issue(r), end="")
        if args.pages and r.get("page_num"):
            print(f"  |  Page {r['page_num']}", end="")
        print(f"\n  File: {r['filename']}")
        snippet = r.get("snippet", "")
        if snippet:
            # Wrap snippet text for readability
            wrapped = textwrap.fill(snippet, width=68, initial_indent="  ", subsequent_indent="  ")
            print(wrapped)
        print_separator("-")

    print(f"Showing {len(results)} of up to {args.limit} results.")
    if len(results) == args.limit:
        print(f"Use --limit N to see more.\n")
    else:
        print()


if __name__ == "__main__":
    main()
