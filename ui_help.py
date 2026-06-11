from PySide6.QtWidgets import QDialog, QVBoxLayout, QTextBrowser, QPushButton, QHBoxLayout
from PySide6.QtCore import Qt

HELP_CONTENT = {
    "validate": """
# Local Queries Help

Use this screen to run local SQL queries against downloaded data via DuckDB.

### 1. Active Tables
When you select a Local File or a Datafeed, it receives a short alias:
- **`local_table`**: The local file you selected.
- **`feed1`**, **`feed2`**: The downloaded datafeeds you selected.

### 2. Flattened Views
If your datafeed contains nested JSON (like Adobe XDM structs), we automatically create a **flattened view**.
For example, if you select `feed1`, you can query:
- `SELECT * FROM feed1` *(Original nested data)*
- `SELECT * FROM feed1_flat` *(Flattened data where nested keys become columns like `person.name`)*

### Example Join Query
```sql
SELECT 
    l.id, 
    f.person.name
FROM local_table l
JOIN feed1_flat f ON l.id = f._id
LIMIT 100;
```
""",
    "pull": """
# Datafeeds Help

Use this screen to extract data from Adobe Experience Platform.

### Available Operations
- **Query Service: Template**: Runs a query based on a saved AEP Query Template ID. Use this for complex, predefined ETL tasks.
- **Query Service: Direct SQL**: Runs a direct SQL query against AEP's Postgres Query Service endpoint. Data is converted into a local `.parquet` file.
- **Data Pull: Dataset Download**: Directly downloads the raw `.parquet` files from the latest successful batch of an AEP dataset. Fastest for raw ingestion.

**Tip:** Downloaded feeds will appear in the Sidebar and can be used in the **Local Queries** screen!
""",
    "profile": """
# Profile Lookup Help

Use this screen to search for individual profiles in AEP Real-Time Customer Profile.

### Instructions
1. **Namespace**: Enter the Identity Namespace (e.g., `Email`, `CRMID`, `ECID`).
2. **Identity Value**: Enter the exact identifier value.
3. **Fetch Events**: Check this box if you want to pull Experience Events along with the core profile attributes.

**Note:** The flattened profile data will appear in the "Profile Info" tab, and any segmentation data will appear in the "Segments" tab.
""",
    "ingest": """
# Ingestion Help

Use this screen to upload local `.parquet` or `.csv` files directly into an AEP Dataset.

### Instructions
1. **Dataset ID**: Enter the exact AEP Dataset ID you wish to ingest into.
2. **Local File**: Select the `.parquet` or `.csv` file from your machine.
3. **Run Task**: This will initiate an AEP Batch Ingestion API call.

**Important:** Your local file schema must perfectly match the XDM schema of the target dataset, otherwise the batch will fail in AEP.
""",
    "segments": """
# Segments Help

Use this screen to create a Feed from an existing AEP Segment (Audience).

### Instructions
1. Select **Create New Segment Feed**.
2. Enter the **Segment ID** from AEP.
3. The system will use Query Service to generate a query that exports the profiles belonging to that segment into a local dataset feed.

**Tip:** Once the feed is generated, you can query the segment data locally in the **Local Queries** screen.
""",
    "workflow": """
# Workflows Help

Use this screen to string together multiple tasks into an automated sequence.

### Building a Workflow
1. Use the left-side panel to add saved Datafeeds, Profiles, or Ingestion tasks to the workflow canvas.
2. The tasks will execute sequentially from top to bottom.
3. Check the "Logs" panel to monitor the success or failure of each step.

**Tip:** This replaces the old Python polling scripts. You can run complex data pipelines locally with a single click.
""",
    "default": """
# AEP Data Explorer Help

Welcome to AEP Data Explorer!

Select an item from the left sidebar to open a workspace. Press **F1** or click the **Help** button at any time to open documentation specific to the screen you are currently viewing.
"""
}

class HelpDialog(QDialog):
    def __init__(self, context_id="default", parent=None):
        super().__init__(parent)
        self.setWindowTitle("Quick Reference Help")
        self.resize(650, 550)
        
        # Dark theme styling for dialog
        self.setStyleSheet("""
            QDialog { background-color: #1e1e1e; color: #dcdcdc; }
            QTextBrowser { background-color: #252526; color: #dcdcdc; border: 1px solid #333; padding: 10px; }
            QPushButton { background-color: #007acc; color: white; border: none; padding: 8px 15px; border-radius: 4px; font-weight: bold; }
            QPushButton:hover { background-color: #0098ff; }
        """)
        
        layout = QVBoxLayout(self)
        
        self.browser = QTextBrowser()
        self.browser.setOpenExternalLinks(True)
        
        # Load markdown
        content = HELP_CONTENT.get(context_id, HELP_CONTENT["default"])
        self.browser.setMarkdown(content)
        
        layout.addWidget(self.browser)
        
        btn_layout = QHBoxLayout()
        btn_layout.addStretch()
        btn_close = QPushButton("Close")
        btn_close.clicked.connect(self.accept)
        btn_layout.addWidget(btn_close)
        
        layout.addLayout(btn_layout)
