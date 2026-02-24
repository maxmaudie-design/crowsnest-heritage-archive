"""
download_crowsnest_pdfs.py

Downloads all 82 issues of the Crowsnest Heritage Initiative newsletter (Heritage Views)
from crowsnestheritage.ca/archives into a local `pdfs/` folder.

Usage:
    python download_crowsnest_pdfs.py
"""

import os
import time
import requests
from pathlib import Path

# ---------------------------------------------------------------------------
# Configuration
# ---------------------------------------------------------------------------

ARCHIVES_URL = "https://www.crowsnestheritage.ca/archives"
OUTPUT_DIR = Path("pdfs")
DELAY_SECONDS = 1.5  # polite delay between requests

HEADERS = {
    "User-Agent": (
        "Mozilla/5.0 (compatible; CrowsnestArchiveBot/1.0; "
        "+https://github.com/maxmaudie-design/crowsnest-heritage-archive)"
    )
}

# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def get_pdf_links(session: requests.Session) -> list[dict]:
    """Scrape the archives page and return a list of {url, filename} dicts."""
    from html.parser import HTMLParser

    class LinkParser(HTMLParser):
        def __init__(self):
            super().__init__()
            self.links = []

        def handle_starttag(self, tag, attrs):
            if tag == "a":
                attrs_dict = dict(attrs)
                href = attrs_dict.get("href", "")
                if href.lower().endswith(".pdf"):
                    self.links.append(href)

    print(f"Fetching archive index from {ARCHIVES_URL} …")
    resp = session.get(ARCHIVES_URL, headers=HEADERS, timeout=30)
    resp.raise_for_status()

    parser = LinkParser()
    parser.feed(resp.text)

    links = []
    seen = set()
    for href in parser.links:
        # Make absolute
        if href.startswith("http"):
            url = href
        else:
            url = f"https://www.crowsnestheritage.ca{href}"

        filename = url.split("/")[-1]
        if filename not in seen:
            seen.add(filename)
            links.append({"url": url, "filename": filename})

    print(f"Found {len(links)} PDF links.")
    return links


def download_pdf(session: requests.Session, url: str, dest: Path) -> bool:
    """Download a single PDF. Returns True on success."""
    try:
        resp = session.get(url, headers=HEADERS, timeout=60, stream=True)
        resp.raise_for_status()
        with open(dest, "wb") as f:
            for chunk in resp.iter_content(chunk_size=8192):
                f.write(chunk)
        return True
    except requests.RequestException as exc:
        print(f"  ERROR downloading {url}: {exc}")
        return False


# ---------------------------------------------------------------------------
# Main
# ---------------------------------------------------------------------------


def main():
    OUTPUT_DIR.mkdir(exist_ok=True)

    with requests.Session() as session:
        links = get_pdf_links(session)

        if not links:
            print(
                "No PDF links found. The site structure may have changed — "
                "check ARCHIVES_URL and update the scraper if needed."
            )
            return

        success = 0
        skipped = 0
        failed = 0

        for i, item in enumerate(links, 1):
            dest = OUTPUT_DIR / item["filename"]
            if dest.exists():
                print(f"[{i}/{len(links)}] Skipping (already exists): {item['filename']}")
                skipped += 1
                continue

            print(f"[{i}/{len(links)}] Downloading: {item['filename']} … ", end="", flush=True)
            ok = download_pdf(session, item["url"], dest)
            if ok:
                size_kb = dest.stat().st_size // 1024
                print(f"OK ({size_kb} KB)")
                success += 1
            else:
                failed += 1

            if i < len(links):
                time.sleep(DELAY_SECONDS)

    print(
        f"\nDone. {success} downloaded, {skipped} skipped, {failed} failed.\n"
        f"PDFs are in: {OUTPUT_DIR.resolve()}"
    )


if __name__ == "__main__":
    main()
