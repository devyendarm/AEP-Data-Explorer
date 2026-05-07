from PySide6.QtWidgets import (QWidget, QVBoxLayout, QHBoxLayout, QLabel, 
                               QPushButton, QTextEdit, QFileDialog, QMessageBox, 
                               QFrame, QStackedWidget, QTableWidget, QTableWidgetItem, QHeaderView)
from PySide6.QtCore import Qt
from logger import logger
import persistence
import os
from data_utils import generate_flattened_query

from ui_shared import StandardTaskLayout

class QuerySummaryWidget(QWidget):
    """Displays a table summary of all saved local queries."""
    def __init__(self, parent_task_widget):
        super().__init__()
        self.parent_task = parent_task_widget
        
        layout = QVBoxLayout(self)
        layout.setContentsMargins(20, 20, 20, 20)
        
        lbl_title = QLabel("Local Queries Summary")
        lbl_title.setStyleSheet("font-size: 24px; font-weight: bold; color: white; margin-bottom: 10px;")
        layout.addWidget(lbl_title)
        
        self.table = QTableWidget()
        self.table.setColumnCount(1)
        self.table.setHorizontalHeaderLabels(["Query Name"])
        self.table.horizontalHeader().setSectionResizeMode(QHeaderView.Stretch)
        self.table.setEditTriggers(QTableWidget.NoEditTriggers)
        self.table.setSelectionBehavior(QTableWidget.SelectRows)
        self.table.setAlternatingRowColors(True)
        self.table.setStyleSheet("""
            QTableWidget { background-color: #252526; border: 1px solid #333; }
            QHeaderView::section { background-color: #333; color: white; padding: 5px; border: none;}
            QTableWidget::item { padding: 5px; color: #e0e0e0; }
            QTableWidget::item:selected { background-color: #007acc; color: white; }
        """)
        self.table.itemDoubleClicked.connect(self.on_row_clicked)
        layout.addWidget(self.table)
        
        self.refresh_data()

    def refresh_data(self):
        import persistence
        queries = persistence.load_local_queries()
        self.table.setRowCount(0)
        self.queries_map = {}
        
        if not queries: return

        self.table.setRowCount(len(queries))
        for idx, q in enumerate(queries):
            self.table.setItem(idx, 0, QTableWidgetItem(q.get("name", "Unknown")))
            self.queries_map[idx] = q
            
    def on_row_clicked(self, item):
        row = item.row()
        if row in self.queries_map:
            config = self.queries_map[row]
            self.parent_task.load_config(config)

class TaskValidateWidget(QWidget):
    def __init__(self):
        super().__init__()
        # Use Shared Layout, but embedded inside detail widget
        self.layout = QVBoxLayout(self)
        self.layout.setContentsMargins(0, 0, 0, 0)
        
        self.stacked_widget = QStackedWidget()
        self.layout.addWidget(self.stacked_widget)
        
        self.summary_widget = QuerySummaryWidget(self)
        self.stacked_widget.addWidget(self.summary_widget)
        
        self.detail_widget = QWidget()
        detail_layout = QVBoxLayout(self.detail_widget)
        detail_layout.setContentsMargins(0, 0, 0, 0)
        
        self.ui = StandardTaskLayout(self.detail_widget)
        detail_layout.addWidget(self.ui)
        self.stacked_widget.addWidget(self.detail_widget)
        
        # Customize Controls (Top Pane)
        # Strategy: Replace the top pane (controls_widget) with our own container that holds:
        # 1. Config Frame
        # 2. Query Editor
        # 3. Standard Controls (Run, Status)
        
        self.config_container = QWidget()
        self.controls_layout = QVBoxLayout(self.config_container)
        self.controls_layout.setContentsMargins(10, 10, 10, 10)
        self.controls_layout.setSpacing(10)
        
        # Access exposed standard widgets
        self.results = self.ui.results_widget
        self.btn_run = self.ui.btn_run
        self.lbl_status = self.ui.lbl_status
        self.progress_bar = self.ui.progress_bar
        
        # Reparent them to our new container
        self.btn_run.setParent(self.config_container)
        self.lbl_status.setParent(self.config_container)
        self.progress_bar.setParent(self.config_container)
        
        # --- Top Section: Configuration & Query ---
        
        # 1. Configuration Row (File + Feeds)
        config_frame = QFrame()
        config_frame.setStyleSheet("background-color: #252526; border-radius: 6px; padding: 10px; border: 1px solid #333;")
        config_layout = QHBoxLayout(config_frame)
        
        # ... (rest of config setup)
        
        # Local File Selection
        self.lbl_file = QLabel("No file selected")
        self.lbl_file.setStyleSheet("color: #aaa; font-style: italic;")
        btn_file = QPushButton("Select Local File")
        btn_file.setCursor(Qt.PointingHandCursor)
        btn_file.clicked.connect(self.select_local_file)
        
        # Datafeed Selection (Multi-Select Menu)
        from PySide6.QtWidgets import QMenu
        
        self.btn_select_feeds = QPushButton("Select Feeds to Join")
        self.btn_select_feeds.setCursor(Qt.PointingHandCursor)
        self.btn_select_feeds.setStyleSheet("""
            QPushButton { background-color: #333; color: white; border: 1px solid #555; padding: 5px 10px; border-radius: 4px; }
            QPushButton:hover { background-color: #444; }
        """)
        
        self.feed_menu = QMenu(self)
        self.btn_select_feeds.setMenu(self.feed_menu)
        self.feed_menu.aboutToShow.connect(self.populate_feed_menu)
        
        # Selected Tables Display
        self.lbl_active_tables = QLabel("Active Tables: None")
        self.lbl_active_tables.setStyleSheet("color: #aaa; font-size: 11px; margin-left: 10px;")
        
        config_layout.addWidget(QLabel("Local File (Optional):"))
        config_layout.addWidget(btn_file)
        
        self.btn_clear_file = QPushButton("X")
        self.btn_clear_file.setFixedSize(20, 20)
        self.btn_clear_file.setToolTip("Clear Local File")
        self.btn_clear_file.setCursor(Qt.PointingHandCursor)
        self.btn_clear_file.setStyleSheet("background: transparent; color: #ff5555; font-weight: bold; border: none;")
        self.btn_clear_file.clicked.connect(self.clear_local_file)
        self.btn_clear_file.setVisible(False)
        
        config_layout.addWidget(self.btn_clear_file)
        config_layout.addWidget(self.lbl_file)
        config_layout.addSpacing(20)
        config_layout.addWidget(self.btn_select_feeds)
        config_layout.addWidget(self.lbl_active_tables)
        config_layout.addStretch()
        
        self.controls_layout.addWidget(config_frame)
        
        # 2. SQL Query Area
        query_group = QFrame()
        query_group.setStyleSheet("background-color: #1e1e1e; border: 1px solid #333; border-radius: 6px;")
        query_layout = QVBoxLayout(query_group)
        
        lbl_query = QLabel("SQL Query:")
        lbl_query.setStyleSheet("color: #ccc; font-weight: bold; border: none;")
        
        self.txt_query = QTextEdit()
        self.txt_query.setPlaceholderText("SELECT * FROM local_table l JOIN feed_my_feed f ON l.id = f.id ...")
        self.txt_query.setStyleSheet("background-color: #1e1e1e; color: #dcdcdc; font-family: Consolas; font-size: 13px; border: none;")
        
        # Action Buttons Layout (Save, Run)
        btn_layout = QHBoxLayout()
        
        self.btn_save = QPushButton("Save Changes")
        self.btn_save.setCursor(Qt.PointingHandCursor)
        self.btn_save.setFixedHeight(35)
        self.btn_save.setStyleSheet("""
            QPushButton { background-color: #333; color: white; border: 1px solid #555; border-radius: 4px; }
            QPushButton:hover { background-color: #444; }
        """)
        self.btn_save.clicked.connect(self.save_config)
        
        # Run Button reused
        self.btn_run.setFixedHeight(35) # Ensure height matches
        self.btn_run.clicked.connect(self.run_validation)
        
        btn_layout.addWidget(self.btn_save)
        btn_layout.addWidget(self.btn_run)
        
        query_layout.addWidget(lbl_query)
        query_layout.addWidget(self.txt_query)
        query_layout.addLayout(btn_layout)
        
        self.controls_layout.addWidget(query_group)
        
        # Status Bar at bottom of controls
        status_layout = QHBoxLayout()
        status_layout.addWidget(self.progress_bar)
        status_layout.addWidget(self.lbl_status)
        self.controls_layout.addLayout(status_layout)
        
        # Replace the Top Pane in Splitter
        # StandardTaskLayout.splitter index 0 is controls_widget
        # We replace it with our config_container
        
        # Note: We must be careful not to trigger destruction of controls_widget BEFORE we reparented buttons.
        # We already reparented them above.
        
        self.ui.splitter.replaceWidget(0, self.config_container)
        
        # Set Splitter Sizes (Taller top for config)
        self.ui.splitter.setSizes([350, 450])
        self.ui.splitter.setCollapsible(0, False)
        
        # Hide standard top toggle because we don't want to hide config easily? 
        # Or keep it. Let's keep it.

        # State
        self.local_file_path = None
        self.selected_feeds = set() # Set of feed names
        self.feed_alias_map = {} # name -> alias
        self.current_config = None # The currently loaded configuration dict
        
        self.load_config(None)

    def show_summary(self):
        """Displays the high-level summary table."""
        self.stacked_widget.setCurrentWidget(self.summary_widget)
        self.summary_widget.refresh_data()

    def load_config(self, config):
        """
        Loads a query configuration into the UI.
        config: dict with keys 'name', 'sql', 'local_file', 'feeds'
        """
        self.current_config = config
        
        if not config:
            self.show_summary()
            return
            
        self.stacked_widget.setCurrentWidget(self.detail_widget)

        self.btn_save.setEnabled(True)
        
        # 1. Load File
        self.local_file_path = config.get('local_file')
        if self.local_file_path:
             self.lbl_file.setText(os.path.basename(self.local_file_path))
             self.lbl_file.setStyleSheet("color: #fff; font-weight: bold;")
             self.btn_clear_file.setVisible(True)
        else:
             self.lbl_file.setText("No file selected")
             self.lbl_file.setStyleSheet("color: #aaa; font-style: italic;")
             self.btn_clear_file.setVisible(False)
             
        # 2. Load Feeds
        self.selected_feeds = set(config.get('feeds', []))
        
        # 3. Load SQL
        self.txt_query.setText(config.get('sql', ''))
        
        self.update_active_tables_label()

    def save_config(self):
        """Saves current UI state to the persistence file."""
        if not self.current_config:
            return
            
        # Update current config object
        self.current_config['local_file'] = self.local_file_path
        self.current_config['feeds'] = list(self.selected_feeds)
        self.current_config['sql'] = self.txt_query.toPlainText()
        
        # Load all queries, find and replace
        queries = persistence.load_local_queries()
        
        found = False
        for i, q in enumerate(queries):
            if q['name'] == self.current_config['name']:
                queries[i] = self.current_config
                found = True
                break
                
        if not found:
            # Should technically be a new add, but usually we add at creation
            queries.append(self.current_config)
            
        persistence.save_local_queries(queries)
        QMessageBox.information(self, "Saved", f"Query '{self.current_config['name']}' saved successfully.")
        
    def populate_feed_menu(self):
        """Populates the menu with checkable feed items."""
        self.feed_menu.clear()
        feeds = persistence.load_feeds()
        
        if not feeds:
            action = self.feed_menu.addAction("No Datafeeds Available")
            action.setEnabled(False)
            return
            
        for feed in feeds:
            name = feed["name"]
            action = self.feed_menu.addAction(name)
            action.setCheckable(True)
            action.setChecked(name in self.selected_feeds)
            action.triggered.connect(lambda checked, n=name: self.toggle_feed(n, checked))
            
    def toggle_feed(self, name, checked):
        if checked:
            self.selected_feeds.add(name)
        else:
            self.selected_feeds.discard(name)
        self.update_active_tables_label()
        
    def sanitize_table_name(self, name):
        """Converts 'My Feed Name' -> 'feed_my_feed_name'"""
        clean = "".join(c if c.isalnum() else "_" for c in name.lower())
        # Remove duplicate underscores
        while "__" in clean:
            clean = clean.replace("__", "_")
        return f"feed_{clean.strip('_')}"

    def update_active_tables_label(self):
        parts = []
        self.feed_alias_map = {}
        
        if self.local_file_path:
            parts.append("local_table")
            
        for name in self.selected_feeds:
            alias = self.sanitize_table_name(name)
            self.feed_alias_map[name] = alias
            parts.append(f"{alias} ('{name}')")
            
        if not parts:
            self.lbl_active_tables.setText("Active Tables: None")
        else:
            self.lbl_active_tables.setText("Active Tables: " + ", ".join(parts))

    def select_local_file(self):
        path, _ = QFileDialog.getOpenFileName(self, "Select Local File", "", "Data Files (*.csv *.xlsx *.parquet)")
        if path:
            self.local_file_path = path
            self.lbl_file.setText(os.path.basename(path))
            self.lbl_file.setStyleSheet("color: #fff; font-weight: bold;")
            self.btn_clear_file.setVisible(True)
            self.update_active_tables_label()

    def clear_local_file(self):
        """Clears the currently selected local file."""
        self.local_file_path = None
        self.lbl_file.setText("No file selected")
        self.lbl_file.setStyleSheet("color: #aaa; font-style: italic;")
        self.btn_clear_file.setVisible(False)
        self.update_active_tables_label()
            
    def run_validation(self):
        # Allow running if a query is present, regardless of file/feed selection
        # This supports "Pure SQL" or "Feed Only" workflows
        
        query = self.txt_query.toPlainText().strip()
        if not query:
            QMessageBox.warning(self, "Missing Input", "Please enter a SQL query.")
            return
            
        # UI Updates
        self.btn_run.setEnabled(False)
        self.btn_run.setText("Processing...")
        
        # Prepare Configs for Worker
        feed_configs = []
        if self.selected_feeds:
            all_feeds = persistence.load_feeds() # Reload to be safe
            for f in all_feeds:
                if f["name"] in self.selected_feeds:
                    # Get persistent state for data path
                    state = persistence.load_state(f["name"])
                    if state and state.get("data_path"):
                        alias = self.feed_alias_map.get(f["name"])
                        feed_configs.append({
                            "name": f["name"],
                            "path": state.get("data_path"),
                            "alias": alias
                        })
                    else:
                        logger.warning(f"Skipping feed {f['name']} - No data found.")
                        
        if self.selected_feeds and not feed_configs:
             QMessageBox.warning(self, "Data Warning", "Selected feeds have no downloaded data yet. Run them first.")
             self.btn_run.setEnabled(True)
             return

        # Start Worker
        self.worker = ValidationWorker(self.local_file_path, feed_configs, query)
        self.worker.finished.connect(self.on_validation_finished)
        self.worker.error.connect(self.on_validation_error)
        self.worker.start()
        
    def on_validation_finished(self, df):
        self.results.load_data(df)
        self.btn_run.setEnabled(True)
        self.btn_run.setText("Run Validation")
        self.ui.set_status(f"Validation complete. Loaded {len(df)} rows.")
        QMessageBox.information(self, "Success", f"Validation complete. Loaded {len(df)} rows.")

    def on_validation_error(self, error_msg):
        self.btn_run.setEnabled(True)
        self.btn_run.setText("Run Validation")
        logger.error(f"Validation Error: {error_msg}")
        self.ui.set_status(f"Error: {error_msg}", error=True)
        QMessageBox.critical(self, "Execution Error", f"Failed to run validation:\n{error_msg}")

from PySide6.QtCore import QThread, Signal

class ValidationWorker(QThread):
    finished = Signal(object) # Emits DataFrame
    error = Signal(str)

    def __init__(self, local_path, feed_configs, query):
        super().__init__()
        self.local_path = local_path
        self.feed_configs = feed_configs # List of dicts: {path, alias}
        self.query = query

    def run(self):
        try:
            import duckdb
            # 1. Create In-Memory Connection
            con = duckdb.connect(database=':memory:')
            self.progress.emit(10, "Local database initialized.")
            
            # 2. Register Local File (Optional)
            if self.local_path:
                if self.local_path.endswith('.csv'):
                    con.execute(f"CREATE OR REPLACE VIEW local_table AS SELECT * FROM read_csv_auto('{self.local_path}')")
                elif self.local_path.endswith('.parquet'):
                    con.execute(f"CREATE OR REPLACE VIEW local_table AS SELECT * FROM read_parquet('{self.local_path}')")
                elif self.local_path.endswith('.xlsx'):
                    import pandas as pd
                    df = pd.read_excel(self.local_path)
                    con.register('local_table', df)
                elif self.local_path.endswith('.csv'):
                    df = pd.read_csv(self.local_path)
            # 3. Register Feed Data
            for feed in self.feed_configs:
                path = feed["path"]
                alias = feed["alias"]
                
                if os.path.isdir(path):
                    # Directory of parquet files
                    parquet_glob = os.path.join(path, "*.parquet")
                    parquet_glob = parquet_glob.replace("\\", "/") # DuckDB needs forward slashes
                    con.execute(f"CREATE OR REPLACE VIEW {alias} AS SELECT * FROM read_parquet('{parquet_glob}')")
                else:
                    # Single DB Attach (Legacy/Alternative)
                    # Note: Attaching multiple DBs needs distinct attach names
                    # Simplifying: if it's a DuckDB file, attach and create view
                    attach_name = f"db_{alias}"
                    con.execute(f"ATTACH '{path}' AS {attach_name}")
                    con.execute(f"CREATE OR REPLACE VIEW {alias} AS SELECT * FROM {attach_name}.data")

            # 4. Auto-Flattening
            # For each view (local_table, aliases), check if it has structs and flatten it
            views_to_flatten = []
            if self.local_path: views_to_flatten.append("local_table")
            for feed in self.feed_configs: views_to_flatten.append(feed["alias"])
            
            for view_name in views_to_flatten:
                # Generate a flat view
                flat_name = f"{view_name}_flat"
                try:
                    # Check if view exists
                    con.execute(f"SELECT 1 FROM {view_name} LIMIT 0")
                    
                    # Generate flat view
                    generate_flattened_query(con, view_name, flat_name)
                    
                    # Replace original view with flat view for seamless querying
                    con.execute(f"DROP VIEW {view_name}")
                    con.execute(f"CREATE VIEW {view_name} AS SELECT * FROM {flat_name}")
                except Exception as e:
                    # If it fails (e.g. view doesn't exist or empty), skip
                    print(f"Skipping flattening for {view_name}: {e}")

            
            # 5. Run User Query
            result_df = con.execute(self.query).df()
            
            con.close()
            self.finished.emit(result_df)
            
        except Exception as e:
            self.error.emit(str(e))
