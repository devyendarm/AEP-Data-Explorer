# AEP Data Explorer

A robust, cross-platform desktop application built with PySide6 and DuckDB to interface directly with Adobe Experience Platform (AEP). The application provides native tooling for marketers and data engineers to run complex AEP queries, analyze profile schemas, and pull segment data into local, highly-performant in-memory tables without heavy browser-based UI overhead.

## Features

* **Data Ingestion & Flattening**: Pull hierarchical AEP data structures (nested Parquet) into local flat tables or DataFrames.
* **Profile Lookups**: Rapid identity searches to validate event streaming and customer profiles.
* **Segment Audience Feeds**: Directly query and export massive audience segments into standalone `.parquet` or `.xlsx` files.
* **Local In-Memory Analytics**: Built-in DuckDB integration lets you run high-speed localized SQL queries over downloaded datasets without accruing Query Service compute costs.
* **Query Service IDE**: Full syntax highlighting and execution engine for running ad-hoc SQL against AEP Query Service.
* **Secure Credential Management**: Uses local Fernet encryption to store your OAuth API credentials in your `AppData` directory—keys never touch the codebase.

## Tech Stack

* **UI Framework**: PySide6 (Qt for Python).
* **Data Processing**: Pandas, DuckDB, PyArrow.
* **Networking & Auth**: Requests, OAuth 2.0 (Server-to-Server), PyJWT, Cryptography.
* **Database Driver**: Psycopg2 (for Postgres/AEP Query Service dialect).

## Building from Source

To compile the application into a standalone executable (Windows):

1. Install dependencies:
   ```bash
   pip install -r requirements.txt
   ```
2. Build the optimized executable:
   ```bash
   pyinstaller --clean AEP_DataExplorer_optimized.spec
   ```
   *Note: Using the optimized spec file strips out unused Anaconda/Data Science blobs to keep the executable lightweight.*

## Run Locally

Simply run:
```bash
python main.py
```

## Security & Architecture Notes

By design, this application does not require Administrator privileges. 
- API credentials are encrypted with AES-128 and stored in your profile at `%APPDATA%/AEP_DataExplorer`.
- Downloaded Parquet datasets and logs are also compartmentalized inside the user's roaming directory.
- In-memory metrics run on transient DuckDB instances and automatically clear upon exit to prevent phantom state issues.

## License

MIT License
