from PySide6.QtWidgets import (QWidget, QVBoxLayout, QHBoxLayout, QLabel, 
                               QPushButton, QTextEdit, QProgressBar, QMessageBox, 
                               QStackedWidget, QTableWidget, QTableWidgetItem, QHeaderView,
                               QDialog, QFormLayout, QLineEdit, QDialogButtonBox)
from PySide6.QtCore import Qt, Signal
from ui_results import ResultsWidget
from logger import logger
import persistence
import aep_template
import aep_query
import aep_catalog
import aep_data
from data_manager import DataManager
import re
import os
import secure_store
from aep_query_service import AEPQueryService

class FilterDialog(QDialog):
    """Dialog for configuring dynamic filters for Direct Query feeds"""
    def __init__(self, current_filters=None, parent=None):
        super().__init__(parent)
        self.setWindowTitle("Query Filters")
        self.resize(400, 300)
        self.filters = current_filters or {}
        
        layout = QVBoxLayout(self)
        
        form = QFormLayout()
        self.txt_field = QLineEdit()
        self.txt_field.setPlaceholderText("e.g., country_code")
        form.addRow("Field Name:", self.txt_field)
        
        self.txt_values = QTextEdit()
        self.txt_values.setPlaceholderText("Enter values, one per line\ne.g.\nUS\nCA\nGB")
        form.addRow("Values (IN clause):", self.txt_values)
        
        layout.addLayout(form)
        
        # Helper to load first filter if exists (Simplification: supporting 1 filter for now effectively in UI, 
        # but code structure could support map)
        if self.filters:
            first_key = next(iter(self.filters))
            self.txt_field.setText(first_key)
            self.txt_values.setPlainText("\n".join(self.filters[first_key]))

        btns = QDialogButtonBox(QDialogButtonBox.Ok | QDialogButtonBox.Cancel)
        btns.accepted.connect(self.accept)
        btns.rejected.connect(self.reject)
        layout.addWidget(btns)

    def get_filter(self):
        field = self.txt_field.text().strip()
        raw_vals = self.txt_values.toPlainText().strip()
        if not field or not raw_vals:
            return None
        
        vals = [v.strip() for v in raw_vals.split('\n') if v.strip()]
        return {field: vals}

class FeedSummaryWidget(QWidget):
    """
    Displays a table summary of all configured datafeeds.
    """
    def __init__(self, parent_task_widget):
        super().__init__()
        self.parent_task = parent_task_widget
        
        layout = QVBoxLayout(self)
        layout.setContentsMargins(20, 20, 20, 20)
        
        # Header
        lbl_title = QLabel("Datafeeds Summary")
        lbl_title.setStyleSheet("font-size: 24px; font-weight: bold; color: white; margin-bottom: 10px;")
        layout.addWidget(lbl_title)
        
        # Table
        self.table = QTableWidget()
        self.table.setColumnCount(3)
        self.table.setHorizontalHeaderLabels(["Datafeed Name", "Rows (Last Run)", "Last Run Time"])
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
        
        # Initial Load
        self.refresh_data()

    def refresh_data(self):
        feeds = persistence.load_feeds()
        self.table.setRowCount(0)
        self.feeds_map = {} # row_idx -> feed_config
        
        if not feeds:
            return

        self.table.setRowCount(len(feeds))
        
        for idx, feed in enumerate(feeds):
            name = feed.get("name", "Unknown")
            state = persistence.load_state(name) or {}
            
            last_run = state.get("last_run", "Never")
            row_count = state.get("row_count")
            
            if row_count is None:
                row_str = "N/A"
            else:
                row_str = f"{row_count:,}"
                
            self.table.setItem(idx, 0, QTableWidgetItem(name))
            self.table.setItem(idx, 1, QTableWidgetItem(row_str))
            self.table.setItem(idx, 2, QTableWidgetItem(last_run))
            
            self.feeds_map[idx] = feed
            
    def on_row_clicked(self, item):
        row = item.row()
        if row in self.feeds_map:
            config = self.feeds_map[row]
            # Call parent method to switch view
            self.parent_task.load_feed(config)


class TaskPullWidget(QWidget):
    log_signal = Signal(str)
    progress_signal = Signal(str, int)
    
    # Concurrency Control
    active_tasks = 0
    MAX_CONCURRENT_TASKS = 2
    
    def __init__(self):
        super().__init__()
        self.log_signal.connect(self.append_log)
        self.progress_signal.connect(self.update_progress)
        self.layout = QVBoxLayout(self)
        self.layout.setContentsMargins(0, 0, 0, 0)
        
        # Stacked Widget to holdcached feed views
        self.feed_stack = QStackedWidget()
        self.layout.addWidget(self.feed_stack)
        
        # Cache for feed widgets: { "Feed Name": widget_instance }
        self.feed_views = {}
        
        # Default/Empty State (Now Summary View)
        self.summary_widget = FeedSummaryWidget(self)
        self.feed_stack.addWidget(self.summary_widget)

        # Store filters for direct queries: { "Feed Name": { field: [vals] } }
        self.feed_filters = {} 

        self.current_config = None

    def load_feed(self, config):
        """Loads or switches to the UI for a specific datafeed configuration."""
        self.current_config = config
        
        if not config:
            self.feed_stack.setCurrentWidget(self.summary_widget)
            self.summary_widget.refresh_data()
            return

        feed_name = config.get("name")
        
        # Check if we already have a UI for this feed
        if feed_name in self.feed_views:
            widget = self.feed_views[feed_name]
            self.feed_stack.setCurrentWidget(widget)
            # Update current references for signals
            self.current_log_widget = widget.findChild(QLabel, "status_label")
            self.current_progress_bar = widget.findChild(QProgressBar)
        else:
            # Create new UI
            widget = self.build_feed_ui(config)
            self.feed_views[feed_name] = widget
            self.feed_stack.addWidget(widget)
            self.feed_stack.setCurrentWidget(widget)

    def clear_feed_cache(self, feed_name):
        """Removes the cached UI for a feed, forcing a rebuild next time."""
        if feed_name in self.feed_views:
            widget = self.feed_views.pop(feed_name)
            self.feed_stack.removeWidget(widget)
            widget.deleteLater()
            logger.info(f"Cleared UI cache for feed: {feed_name}")
        
    def build_feed_ui(self, config):
        """Creates the UI elements for the feed and returns the container widget."""
        container = QWidget()
        layout = QVBoxLayout(container)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(0) # Ensure no gaps between header and splitter
        
        # Top Header Strip (Persistent Toggle)
        header_strip = QWidget()
        header_strip.setFixedHeight(20)
        header_strip.setStyleSheet("background-color: #1e1e1e; border-bottom: 1px solid #333;")
        header_layout = QHBoxLayout(header_strip)
        header_layout.setContentsMargins(10, 0, 10, 0)
        header_layout.addStretch()
        
        self.btn_toggle_top = QPushButton("▲") 
        self.btn_toggle_top.setFixedSize(20, 20)
        self.btn_toggle_top.setToolTip("Hide Controls")
        self.btn_toggle_top.setCursor(Qt.PointingHandCursor)
        self.btn_toggle_top.setStyleSheet("border: none; background: transparent; color: #888; font-weight: bold;")
        self.btn_toggle_top.clicked.connect(self.toggle_top_panel)
        header_layout.addWidget(self.btn_toggle_top)
        
        layout.addWidget(header_strip)

        # Splitter to hold Top Controls and Bottom Results
        from PySide6.QtWidgets import QSplitter
        self.split_view = QSplitter(Qt.Vertical)
        self.split_view.setHandleWidth(5)
        self.split_view.setStyleSheet("""
            QSplitter::handle {
                background-color: #444;
                height: 5px;
            }
            QSplitter::handle:hover {
                background-color: #007acc;
            }
        """)

        # Controls Toolbar (Collapsible)
        self.controls_widget = QWidget()
        self.controls_widget.setStyleSheet("background-color: #252526; border-bottom: 1px solid #333;")
        controls_layout = QHBoxLayout(self.controls_widget)
        controls_layout.setContentsMargins(10, 5, 10, 5)
        controls_layout.setSpacing(10)
        
        # Run Button
        btn = QPushButton("Run")
        btn.setCursor(Qt.PointingHandCursor)
        btn.setFixedWidth(140)
        btn.setStyleSheet("""
            QPushButton { 
                background-color: #007acc; 
                color: white; 
                font-weight: bold; 
                font-size: 13px; 
                border-radius: 4px;
                padding: 5px 10px;
                border: none;
            }
            QPushButton:hover { background-color: #005a9e; }
            QPushButton:pressed { background-color: #004578; }
            QPushButton:disabled { background-color: #333; color: #888; }
        """)
        controls_layout.addWidget(btn)

        # Filter Button (Only for Direct Query)
        if config.get("type") == "direct":
            btn_filter = QPushButton("Filter")
            btn_filter.setCursor(Qt.PointingHandCursor)
            btn_filter.setFixedWidth(70)
            btn_filter.setStyleSheet("""
                QPushButton { 
                    background-color: #333; 
                    color: white; 
                    border: 1px solid #555;
                    border-radius: 4px;
                    padding: 5px 10px;
                }
                QPushButton:hover { background-color: #444; }
            """)
            btn_filter.clicked.connect(lambda: self.open_filter_dialog(config))
            controls_layout.addWidget(btn_filter)

        # Progress Bar
        progress = QProgressBar()
        progress.setTextVisible(True)
        progress.setFormat("%p% - Ready")
        progress.setFixedWidth(200)
        progress.setStyleSheet("""
            QProgressBar { 
                border: 1px solid #444; 
                border-radius: 4px; 
                text-align: center; 
                background-color: #1e1e1e; 
                height: 18px; 
                font-size: 11px; 
                color: #ccc;
            } 
            QProgressBar::chunk { background-color: #007acc; }
        """)
        controls_layout.addWidget(progress)
        
        # Status Label
        lbl_status = QLabel("Ready")
        lbl_status.setObjectName("status_label")
        lbl_status.setStyleSheet("color: #aaa; font-size: 12px; font-family: Segoe UI, sans-serif; margin-left: 10px;")
        lbl_status.setWordWrap(False)
        controls_layout.addWidget(lbl_status, 1)

        # Results Widget (Takes remaining space)
        results = ResultsWidget()
        
        # Add to Splitter
        self.split_view.addWidget(self.controls_widget)
        self.split_view.addWidget(results)
        
        # Set Default Sizes (Small top, large bottom)
        self.split_view.setSizes([80, 800])
        self.split_view.setCollapsible(0, True)

        layout.addWidget(self.split_view)

        # Load Persisted State
        feed_key = config.get("name") 
        saved_state = persistence.load_state(feed_key)
        if saved_state:
            try:
                from data_manager import DataManager
                import glob
                data_path = saved_state.get("data_path")
                last_run = saved_state.get("last_run")
                
                # Verify cache is still on disk
                if data_path and os.path.exists(data_path) and glob.glob(os.path.join(data_path, "*.parquet")):
                    manager = DataManager(data_path)
                    results.load_manager(manager)
                    results.set_last_run_time(last_run)
                    lbl_status.setText(f"Data from: {last_run}")
                else:
                    logger.warning(f"Cache expired or deleted by OS for {feed_key}")
                    lbl_status.setText("Cache expired. Please run query again.")
                    # Optionally clear state so we don't keep trying
                    persistence.save_state(feed_key, None)
                    
            except Exception as e:
                logger.error(f"Failed to restore state for {feed_key}: {e}")
                lbl_status.setText("Failed to restore cache.")

        # Connect Button
        btn.clicked.connect(lambda: self.run_query(config, btn, progress, results, log_widget=lbl_status))
        
        # Set initial references for immediate use
        self.current_log_widget = lbl_status
        self.current_progress_bar = progress
        
        return container

    def toggle_top_panel(self):
        """Toggles visibility of the controls toolbar."""
        # Use splitter sizes to act as toggle
        sizes = self.split_view.sizes()
        if sizes[0] > 0:
            # Collapse
            self.last_top_height = sizes[0]
            self.split_view.setSizes([0, sizes[1] + sizes[0]])
            self.btn_toggle_top.setText("▼")
            self.btn_toggle_top.setToolTip("Show Controls")
        else:
            # Expand
            h = getattr(self, 'last_top_height', 80)
            if h == 0: h = 80
            self.split_view.setSizes([h, sizes[1] - h])
            self.btn_toggle_top.setText("▲")
            self.btn_toggle_top.setToolTip("Hide Controls")

    def open_filter_dialog(self, config):
        feed_name = config.get("name")
        
        # Load from memory or persistence
        if feed_name in self.feed_filters:
            current = self.feed_filters[feed_name]
        else:
            # Try loading from saved state
            state = persistence.load_state(feed_name)
            current = state.get("last_filters", {}) if state else {}

        dlg = FilterDialog(current, self)
        if dlg.exec():
            new_filters = dlg.get_filter()
            if new_filters:
                self.feed_filters[feed_name] = new_filters
                QMessageBox.information(self, "Filter Set", f"Filter applied: {new_filters}")
                
                # Save to Persistence immediately
                state = persistence.load_state(feed_name) or {}
                state["last_filters"] = new_filters
                persistence.save_state(feed_name, state)
                
            else:
                if feed_name in self.feed_filters:
                    del self.feed_filters[feed_name]
                    
                # Clear from Persistence
                state = persistence.load_state(feed_name) or {}
                if "last_filters" in state:
                    del state["last_filters"]
                    persistence.save_state(feed_name, state)
                    
                QMessageBox.information(self, "Filter Cleared", "Filter removed.")

    def run_query(self, config, btn, progress_bar, results_widget, email_input=None, log_widget=None):
        """
        Executes the query based on the passed configuration.
        """
        # Concurrency Check
        if TaskPullWidget.active_tasks >= TaskPullWidget.MAX_CONCURRENT_TASKS:
            QMessageBox.warning(self, "Concurrency Limit Reached", 
                              f"Only {TaskPullWidget.MAX_CONCURRENT_TASKS} datafeeds can run simultaneously to prevent system instability.\n"
                              "Please wait for a running task to complete.")
            return

        # Set current log widget for signal handler
        self.current_log_widget = log_widget
        if self.current_log_widget:
            self.current_log_widget.clear()
            
        # Set current progress bar for signal handler
        self.current_progress_bar = progress_bar
        
        # Increment active tasks
        TaskPullWidget.active_tasks += 1
        logger.info(f"Starting task. Active tasks: {TaskPullWidget.active_tasks}")

        # UI Updates
        btn.setEnabled(False)
        btn.setText("Processing...")
        progress_bar.setVisible(True)
        progress_bar.setValue(5)
        progress_bar.setFormat("Starting...")
        
        # Initialize Service
        from aep_service import AEPService
        self.service = AEPService()

        # Worker function
        # Worker function
        def task():
            if not config:
                raise Exception("No configuration provided.")

            template_id = config.get("template_id")
            dataset_id = config.get("dataset_id")
            initial_wait = config.get("initial_poll_wait", 45)
            subsequent_wait = config.get("subsequent_poll_wait", 15)
            params = None # Add param logic if needed

            is_direct = config.get("type") == "direct"
            is_dataset_mode = config.get("type") == "dataset"
            
            mode_label = "Direct" if is_direct else ("Dataset" if is_dataset_mode else "Template")
            self.log_message(f"--- Process Started ({mode_label}) ---")
            
            # --- DIRECT SQL MODE (Synchronous via Postgres) ---
            if is_direct:
                self.progress_signal.emit("Connecting to Query Service", 10)
                
                creds = secure_store.load_credentials()
                if not creds:
                     raise Exception("No credentials found. Please configure settings.")
                     
                qs_config = creds.get("query_service")
                if not qs_config:
                    raise Exception("Query Service credentials not found in Settings.")
                    
                qs = AEPQueryService(
                    host=qs_config['host'],
                    port=int(qs_config.get('port', 80)),
                    database=qs_config['database'],
                    username=qs_config['username'],
                    password=qs_config['password']
                )
                
                self.log_message(f"Connecting to Query Service: {qs_config['host']}:{qs_config.get('port', 80)} ({qs_config['database']})")
                
                if not qs.connect():
                    raise Exception(f"Failed to connect to Query Service at {qs_config['host']}")
                    
                try:
                    sql = config.get("sql_query")
                    if not sql: raise Exception("No SQL query defined.")
                    
                    # Apply Filters (Client-side SQL injection)
                    # We reuse the logic but applied here
                    feed_filters = self.feed_filters.get(config.get("name"))
                    if feed_filters:
                        field = next(iter(feed_filters))
                        vals = feed_filters[field]
                        safe_vals = [v.replace("'", "''") for v in vals]
                        val_str = ", ".join([f"'{v}'" for v in safe_vals])
                        clause = f"{field} IN ({val_str})"
                        
                        # Wrap in subquery if SELECT
                        # Simple regex check for SELECT
                        if re.search(r'\bSELECT\b', sql, re.IGNORECASE):
                             sql = f"SELECT * FROM (\n{sql}\n) AS subquery WHERE {clause}"
                        else:
                             # Just append (risky if not SELECT, but Direct mode implies SELECT for data pull)
                             sql += f" WHERE {clause}"
                        
                        self.log_message(f"Applied Filter: {clause}")
                        
                    self.progress_signal.emit("Executing Query...", 30)
                    self.log_message("Executing SQL on Query Service...")
                    
                    results = qs.execute_query(sql)
                    
                    if not results:
                        self.log_message("Query returned no results.")
                        return None
                        
                    self.progress_signal.emit("Processing Results", 70)
                    self.log_message(f"Query returned {len(results)} rows.")
                    
                    # Save to Parquet
                    import pandas as pd
                    df = pd.DataFrame(results)
                    
                    import os
                    feed_name = config.get("name")
                    safe_name = re.sub(r'[^a-zA-Z0-9_\-]', '_', feed_name)
                    data_dir = os.path.join("downloads", safe_name)
                    if not os.path.exists(data_dir):
                        os.makedirs(data_dir)
                    
                    # Clean directory
                    import glob
                    files = glob.glob(os.path.join(data_dir, "*"))
                    for f in files:
                        try: os.remove(f)
                        except: pass
                        
                    file_path = os.path.join(data_dir, "data.parquet")
                    df.to_parquet(file_path, index=False)
                    self.log_message(f"Saved results to {file_path}")
                    
                    self.progress_signal.emit("Initializing Data Manager", 90)
                    manager = DataManager(data_dir)
                    return manager
                    
                finally:
                    qs.disconnect()

            # --- ASYNC BATCH MODES (Dataset / Template) ---
            
            # Calculate Estimated Wait Time
            est_seconds = initial_wait + subsequent_wait + 120
            if is_dataset_mode:
                est_seconds = 30 # Much faster usually
            
            est_min = est_seconds // 60
            est_sec = est_seconds % 60
            
            if is_dataset_mode:
                 self.log_message("Skipping Query Service (Dataset Mode)...")
                 # We skip step 1 and 2
                 batch_id = None
                 strategy = config.get("batch_strategy", "latest")
                 
                 self.progress_signal.emit("Resolving Batch...", 20)
                 
                 if strategy == "custom":
                     batch_id = config.get("custom_batch_id")
                     if not batch_id: raise Exception("Custom Batch ID is missing.")
                     self.log_message(f"Using Custom Batch ID: {batch_id}")
                 else:
                     self.log_message(f"Fetching latest batch for Dataset {dataset_id}...")
                     batch_id = aep_catalog.get_latest_batch(dataset_id)
                     
                 # Go directly to Step 4 (Download)
                 query_id = None
            else:
                self.log_message(f"Expected wait time: ~{est_min} min {est_sec} sec")
                
                # 1. Submit Query
                self.progress_signal.emit("Query Submitted", 10)
                
                self.log_message(f"Submitting query template {template_id}...")
                query_id = aep_template.submit_template(template_id, params)
                
                # 2. Poll Status
                self.log_message(f"Polling Query {query_id} (Init: {initial_wait}s, Loop: {subsequent_wait}s)...")
                aep_query.poll_query(query_id, initial_wait, subsequent_wait)
                
                # 3. Get Latest Batch
                self.progress_signal.emit("Query Complete, capturing data Batch", 40)
                self.log_message(f"Checking Dataset {dataset_id}...")
                batch_id = aep_catalog.get_latest_batch(dataset_id)
            
            # 4. Download Data to Disk
            self.progress_signal.emit("Downloading Data", 60)
            self.log_message(f"Downloading Batch {batch_id} to disk...")
            data_dir = aep_data.get_batch_data(batch_id)
            
            # 5. Initialize Data Manager
            self.progress_signal.emit("Compiling final Data", 80)
            self.log_message("Initializing Data Manager...")
            manager = DataManager(data_dir)
            
            return manager

        # Run in background
        worker = self.service.run_async(
            task,
            on_success=lambda manager: self.on_success(manager, btn, progress_bar, results_widget, config),
            on_error=lambda err: self.on_error(err, btn, progress_bar, config)
        )

    def log_message(self, message):
        logger.info(message)
        print(message)
        self.log_signal.emit(message)

    def append_log(self, message):
        if hasattr(self, 'current_log_widget') and self.current_log_widget:
            if isinstance(self.current_log_widget, QTextEdit):
                self.current_log_widget.append(message)
            elif isinstance(self.current_log_widget, QLabel):
                self.current_log_widget.setText(message)

    def update_progress(self, message, value):
        if hasattr(self, 'current_progress_bar') and self.current_progress_bar:
            self.current_progress_bar.setFormat(f"{value}% - {message}")
            self.current_progress_bar.setValue(value)



    def on_success(self, manager, btn, progress_bar, results_widget, config):
        # Decrement active tasks
        TaskPullWidget.active_tasks = max(0, TaskPullWidget.active_tasks - 1)
        logger.info(f"Task completed successfully. Active tasks: {TaskPullWidget.active_tasks}")
        
        btn.setEnabled(True)
        btn.setText("Run")

        progress_bar.setValue(100)
        progress_bar.setFormat("Completed")
        
        if manager:
             results_widget.load_manager(manager)
             self.log_message(f"Loaded {manager.total_rows} rows.")
             
             # Save State
             try:
                 feed_key = config.get("name")
                 last_run = persistence.get_current_time_str()
                 persistence.save_state(feed_key, {
                     "data_path": manager.db_path, 
                     "last_run": last_run,
                     "row_count": manager.total_rows
                 })
                 results_widget.set_last_run_time(last_run)
                 self.log_message(f"State saved for {feed_key}. Last Run: {last_run}")
             except Exception as e:
                 logger.error(f"Failed to save state: {e}")
        else:
             self.log_message("No data returned.")

    def on_error(self, error_msg, btn, progress_bar, config):
        # Decrement active tasks
        TaskPullWidget.active_tasks = max(0, TaskPullWidget.active_tasks - 1)
        logger.info(f"Task failed. Active tasks: {TaskPullWidget.active_tasks}")
        
        btn.setEnabled(True)
        btn.setText("Run")

        progress_bar.setValue(0)
        progress_bar.setFormat("Error")
        
        is_dataset = config and config.get("type") == "dataset"
        title = "Data Pull Failed" if is_dataset else "Query Failed"
        
        QMessageBox.critical(self, title, f"{title}: {error_msg}")

    def handle_fullscreen(self, checked, action_frame, log_widget, layout):
        """
        Toggles visibility of non-result widgets to simulate fullscreen.
        """
        # Toggle Action Area & Log
        action_frame.setVisible(not checked)
        log_widget.setVisible(not checked)
        
        # Toggle Margins
        if checked:
            layout.setContentsMargins(0, 0, 0, 0)
        else:
            layout.setContentsMargins(0, 0, 0, 0) # Keep 0 for container
