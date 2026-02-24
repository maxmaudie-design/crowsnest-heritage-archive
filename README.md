# Crowsnest Heritage Newsletter Archive

A searchable digital archive of all 82 issues of the **Crowsnest Heritage Initiative** newsletter (*Heritage Views*), published from May 2010 to present.

Source: [crowsnestheritage.ca/archives](https://www.crowsnestheritage.ca/archives)

## What's Included

| Script | Purpose |
|--------|---------|
| `download_crowsnest_pdfs.py` | Downloads all 82 newsletter PDFs |
| `build_database.py` | Extracts text from PDFs → SQLite database with full-text search |
| `search_database.py` | CLI tool to search the database |

## Quick Start

```bash
# 1. Install dependencies
pip install -r requirements.txt

# 2. Download all 82 PDFs (~5 minutes)
python download_crowsnest_pdfs.py

# 3. Build the searchable database
python build_database.py

# 4. Search!
python search_database.py "Frank Slide"
python search_database.py "coal mining" --pages
python search_database.py --list
```

## Database Schema

The SQLite database (`crowsnest_heritage.db`) contains:

- **newsletters** — One row per issue (issue number, date, description, full text)
- **pages** — One row per page per issue (for granular search)
- **newsletters_fts** — Full-text search index (issue level)
- **pages_fts** — Full-text search index (page level)

## Topics Covered

The newsletters cover the rich history of the Crowsnest Pass region in Alberta, Canada, including mining history, the Frank Slide, communities (Coleman, Blairmore, Frank, Bellevue, Hillcrest), pioneers, prohibition & rum running, railways, archaeology, and more.

## Future Plans

- [ ] AI-generated encyclopedia from the extracted text
- [ ] Web-based search interface
- [ ] Topic/entity extraction and cross-referencing

## Credits

All newsletter content is produced by the **Crowsnest Heritage Initiative**.
Subscribe for free at: heritageviews.cnp@gmail.com
