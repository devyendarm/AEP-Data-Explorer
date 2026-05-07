# AEP Data Explorer User Guide

Welcome to the AEP Data Explorer. This application provides direct, high-speed access to Adobe Experience Platform (AEP) data, bypassing heavy browser UIs and querying massive datasets locally using DuckDB.

---

## 1. Initial Setup & Authentication

When you first launch the application, you must provide your AEP API credentials. These are securely encrypted and stored locally.

**APIs Used:**
*   **Adobe IMS (Identity Management System) API**: `https://ims-na1.adobelogin.com/ims/token/v3`
    *   **How it works**: The app uses your Client ID and Client Secret to perform an OAuth 2.0 Server-to-Server flow. It requests an access token scoped for AEP services (`openid`, `AdobeID`, `read_organizations`, etc.). This token is attached as an `Authorization: Bearer` header to all subsequent API calls.

1. Click the **Settings** gear icon.
2. Enter your OAuth Server-to-Server credentials (Client ID, Secret, Org ID, Sandbox Name).
3. *(Optional)* Provide your **Query Service credentials**.
4. Click **Test Connection** to validate, then **Save Settings**.

---

## 2. Main Workspaces

### Datafeeds (Dataset Extraction)
Extract entire AEP datasets locally, structured into optimized Parquet files.

**APIs Used:**
*   **Catalog API**: `https://platform.adobe.io/data/foundation/catalog/datasets`
    *   **How it works**: Fetches the list of available datasets and their metadata (name, description, schema reference).
*   **Schema Registry API**: `https://platform.adobe.io/data/foundation/schemaregistry/tenant/classes/...`
    *   **How it works**: Retrieves the full, hierarchical XDM schema definition for the selected dataset, allowing the UI to present a field-selection tree.
*   **Dataset Export API**: `https://platform.adobe.io/data/foundation/export/batches`
    *   **How it works**: The app queries for completed batches belonging to the dataset within the specified date range. It then retrieves the download URLs for the underlying Parquet files and downloads them directly to your machine.

1. Click **+ New Feed**, select a **Dataset**.
2. Select the specific fields to extract and define a date range.
3. Click **Run Extraction**. The app downloads the data, flattens nested XDM structures, and creates a local DuckDB view for instant querying.

### Profile Lookups
Inspect individual customer profiles and their event streams.

**APIs Used:**
*   **Real-time Customer Profile API**: `https://platform.adobe.io/data/core/ups/models/entities`
    *   **How it works (Profile Info & Segments)**: The app sends the specific identity namespace and value. The API returns the unified profile attributes and the array of segment memberships (`segmentMembership`).
    *   **How it works (Experience Events)**: Using the same endpoint but passing `schema.name=_experience` and `relatedSchema.name=_profile`, the app retrieves a chronological list of incoming Experience Events tied to that identity.

1. Navigate to the **Profile** tab.
2. Select an **Identity Namespace** and enter the **Identity Value**.
3. Click **Lookup**. View core attributes, segment memberships, and Experience Events.

### Audience Segments
Export evaluated audience segments directly into local files.

**APIs Used:**
*   **Segmentation Service API**: `https://platform.adobe.io/data/core/ups/segment/definitions`
    *   **How it works**: Fetches the list of all defined segments/audiences in the selected sandbox.
*   **Query Service API**: `https://platform.adobe.io/data/foundation/query/templates` & `/queries`
    *   **How it works**: Instead of using the slower REST export APIs, the app creates and executes a parameterized SQL template via Query Service to extract the segment members (e.g., `SELECT _id FROM profile_snapshot_export_dataset WHERE segmentMembership...`). It polls the query status and then downloads the resulting Parquet files.

1. Go to the **Segments** tab.
2. Click **+ New Segment Feed** and select an existing AEP Segment.
3. The system leverages Query Service to evaluate and extract the segment.
4. Once complete, page through the results or export to `.xlsx`.

### Query Service IDE
Run custom, ad-hoc PostgreSQL queries directly against Adobe's infrastructure.

**APIs Used:**
*   **Query Service API (RESTful)**: `https://platform.adobe.io/data/foundation/query/queries`
    *   **How it works**: The app POSTs your raw SQL string to the Query Service engine. It then polls the endpoint (e.g., `/queries/{id}`) until the status is `SUCCESS`, and finally retrieves the result rows via `/queries/{id}/rows`.
*   *(Alternative)* **Psycopg2 (Postgres Driver)**:
    *   **How it works**: If Query Service credentials are provided in settings, the app can establish a persistent, direct PostgreSQL connection port (port 80) to Adobe's databases for interactive querying.

1. Navigate to the **Query** tab.
2. Write your SQL query in the editor pane.
3. Click **Run Query**. Results are fetched and rendered below.

---

## 3. Local Data Persistence

* **In-Memory Speed**: Uses a temporary DuckDB database (`:memory:`) for lightning-fast sorts and filters.
* **Disk Storage**: Raw data is saved transparently as compressed `.parquet` files in `%APPDATA%\AEP_DataExplorer`.
* **Resuming Work**: Configured feeds remain when closed and reopened; the app re-attaches existing Parquet files.

---

## 4. Troubleshooting
- **Cannot connect/Fetch failed**: Ensure your Sandbox name is correct and Client ID has `read_organizations` scopes allocated.
- **Application Logs**: Check `%APPDATA%\AEP_DataExplorer\logs` for detailed errors.
