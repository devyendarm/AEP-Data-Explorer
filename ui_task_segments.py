"""
Segments UI - Manages Segment Feeds with Query Service integration
(Details View Only - Sidebar managed by Main Window)
"""

from PySide6.QtWidgets import (QWidget, QVBoxLayout, QLabel, QMessageBox)
from PySide6.QtCore import QThread, Signal, QTimer
from logger import logger
from aep_query_service import AEPQueryService
import secure_store
import persistence
from PySide6.QtWidgets import (QWidget, QVBoxLayout, QLabel, QMessageBox, 
                               QStackedWidget, QTableWidget, QTableWidgetItem, QHeaderView)
import time
import os
from ui_shared import StandardTaskLayout

class SegmentQueryWorker(QThread):
    finished = Signal(object, str, str) # Object instead of pd.DataFrame
    error = Signal(str)

    def __init__(self, segment_config, query_template, qs_config):
        super().__init__()
        self.segment_config = segment_config
        self.query_template = query_template
        self.qs_config = qs_config

    def run(self):
        try:
            qs = AEPQueryService(
                host=self.qs_config['host'],
                port=int(self.qs_config.get('port', 80)),
                database=self.qs_config['database'],
                username=self.qs_config['username'],
                password=self.qs_config['password']
            )
            if not qs.connect():
                self.error.emit("Failed to connect to Query Service")
                return
            
            # Build query from template
            profile_dataset = self.qs_config.get("profile_dataset", "")
            segment_id = self.segment_config.get("segment_id")
            namespace = self.segment_config.get("namespace", "")
            
            query = self.query_template.format(
                profile_dataset=profile_dataset,
                segment_id=segment_id,
                namespace=namespace
            )
            
            logger.info(f"Mapping Check: Segment ID='{segment_id}' (from config), Namespace='{namespace}'")
            logger.info(f"Executing segment query:\n{query}")
            
            # Execute query
            results = qs.execute_query(query)
            
            # Convert to DataFrame
            if results:
                import pandas as pd
                df = pd.DataFrame(results)
                self.finished.emit(df, segment_id, self.segment_config.get("name"))
            else:
                self.error.emit("Query returned no results")
            
            qs.disconnect()
            
        except Exception as e:
            logger.error(f"Segment query failed: {e}")
            self.error.emit(f"Query failed: {str(e)}")



class SegmentSummaryWidget(QWidget):
    """Displays a table summary of all configured segment feeds."""
    def __init__(self, parent_task_widget):
        super().__init__()
        self.parent_task = parent_task_widget
        
        layout = QVBoxLayout(self)
        layout.setContentsMargins(20, 20, 20, 20)
        
        # Header
        lbl_title = QLabel("Segment Feeds Summary")
        lbl_title.setStyleSheet("font-size: 24px; font-weight: bold; color: white; margin-bottom: 10px;")
        layout.addWidget(lbl_title)
        
        # Table
        self.table = QTableWidget()
        self.table.setColumnCount(4)
        self.table.setHorizontalHeaderLabels(["Segment Name", "Segment ID", "Rows (Last Run)", "Last Run Time"])
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
        segments = persistence.load_segment_feeds()
        self.table.setRowCount(0)
        self.segments_map = {} # row_idx -> segment_config
        
        if not segments:
            return

        self.table.setRowCount(len(segments))
        
        for idx, seg in enumerate(segments):
            name = seg.get("name", "Unknown")
            seg_id = seg.get("segment_id", "N/A")
            
            # Load persistence state
            state = persistence.load_state(f"segment_{name}") or {}
            last_run = state.get("last_run", "Never")
            row_count = state.get("row_count")
            
            if row_count is None:
                row_str = "N/A"
            else:
                row_str = f"{row_count:,}"
                
            self.table.setItem(idx, 0, QTableWidgetItem(name))
            self.table.setItem(idx, 1, QTableWidgetItem(seg_id))
            self.table.setItem(idx, 2, QTableWidgetItem(row_str))
            self.table.setItem(idx, 3, QTableWidgetItem(last_run))
            
            self.segments_map[idx] = seg
            
    def on_row_clicked(self, item):
        row = item.row()
        if row in self.segments_map:
            config = self.segments_map[row]
            self.parent_task.load_config(config)

class SegmentDetailWidget(QWidget):
    """Displays details and results for a specific segment."""
    def __init__(self, parent_task_widget):
        super().__init__()
        self.parent_task = parent_task_widget
        self.current_feed = None
        self.worker = None
        self.timer = QTimer(self)
        self.timer.timeout.connect(self.update_timer)
        self.elapsed_seconds = 0
        self.dm = None
        
        self.setup_ui()
        
    def setup_ui(self):
        # Use Shared Layout
        self.ui = StandardTaskLayout(self)
        layout = QVBoxLayout(self)
        layout.setContentsMargins(0,0,0,0)
        layout.addWidget(self.ui)
        
        # Access exposed widgets
        self.btn_run = self.ui.btn_run
        self.progress_bar = self.ui.progress_bar
        self.results_widget = self.ui.results_widget
        
        # Add Segment Specific Controls to the toolbar
        # We need to insert them *before* the Run button or after?
        # Let's insert "Back" button at the start of controls
        
        # Info Label
        self.lbl_feed_info = QLabel("")
        self.lbl_feed_info.setStyleSheet("color: white; font-weight: bold; margin-right: 20px;")
        self.ui.controls_layout.insertWidget(0, self.lbl_feed_info)
        
        # Connect Run
        self.btn_run.clicked.connect(self.run_segment_query)

    def go_back(self):
        self.parent_task.show_summary()

    def set_config(self, config):
        self.current_feed = config
        
        feed_name = config.get("name", "Unnamed")
        segment_id = config.get("segment_id", "N/A")
        namespace = config.get("namespace", "None")
        
        self.lbl_feed_info.setText(
            f"<b>{feed_name}</b> | Segment ID: {segment_id} | Namespace: {namespace or 'None'}"
        )
        
        # Attempt to load persistent state
        state = persistence.load_state(f"segment_{feed_name}")
        if state and state.get("data_path"):
            try:
                from data_manager import DataManager
                if os.path.exists(state["data_path"]):
                    self.dm = DataManager(state["data_path"])
                    self.results_widget.load_manager(self.dm)
                    
                    last_run = state.get("last_run", "Unknown")
                    rows = state.get("row_count", 0)
                    self.results_widget.set_status(f"Loaded {rows} rows from last run ({last_run})")
                else:
                    self.results_widget.clear_data()
                    self.ui.set_status("Previous data not found.")
            except Exception as e:
                logger.error(f"Failed to load persistent segment data: {e}")
                self.results_widget.clear_data()
        else:
            self.results_widget.clear_data()
            self.ui.set_status("Ready to run.")

    def run_segment_query(self):
        """Execute segment query when Run button is clicked."""
        if not self.current_feed:
            return
        
        # Check if Query Service is configured
        creds = secure_store.load_credentials()
        if not creds:
            QMessageBox.warning(self, "Configuration Required", "Please configure credentials in Settings first.")
            return
        
        qs_config = creds.get("query_service")
        if not qs_config or not qs_config.get("host"):
            QMessageBox.warning(self, "Query Service Not Configured", 
                              "Please configure Query Service credentials in Settings.")
            return
        
        query_template = creds.get("segment_query_template")
        if not query_template:
            # Fallback to default if not set (should be handled by Settings, but safety check)
            # Actually, SettingsWidget defines the default, let's assume if it's empty we warn
            QMessageBox.warning(self, "Query Template Not Configured",
                              "Please configure a Segment Query Template in Settings.")
            return
            
        # Validate Namespace usage
        if "{namespace}" in query_template and not self.current_feed.get("namespace"):
            QMessageBox.warning(self, "Missing Namespace",
                              "The Query Template requires a {namespace} placeholder,\n"
                              "but this Segment Feed does not have a Namespace configured.\n\n"
                              "Please edit the feed to add a Namespace.")
            return
        
        # Execute query
        self.execute_segment_query(self.current_feed, query_template, qs_config)
    
    def execute_segment_query(self, config, query_template, qs_config):
        """Execute segment query using Query Service."""
        self.results_widget.clear_data()
        self.results_widget.clear_data()
        self.ui.set_status("Executing segment query (0s)...")
        self.progress_bar.setVisible(True)
        self.progress_bar.setRange(0, 0) # Indeterminate
        self.btn_run.setEnabled(False)
        self.elapsed_seconds = 0
        self.timer.start(1000)
        
        # Start worker thread
        self.worker = SegmentQueryWorker(config, query_template, qs_config)
        self.worker.finished.connect(self.on_query_finished)
        self.worker.error.connect(self.on_query_error)
        self.worker.start()
    
    def on_query_finished(self, df, segment_id, segment_name):
        """Handle successful query completion."""
        try:
            # Save to Parquet for DataManager
            from data_manager import DataManager
            
            # Create timestamped directory for this run
            timestamp = int(time.time())
            safe_id = "".join([c for c in segment_id if c.isalnum() or c in ('-','_')])
            data_dir = os.path.join(os.environ.get('APPDATA', os.path.expanduser('~')), 
                                   'AEP_DataExplorer', 'segment_data', f"{safe_id}_{timestamp}")
            os.makedirs(data_dir, exist_ok=True)
            
            parquet_path = os.path.join(data_dir, "data.parquet")
            
            # Save DataFrame to Parquet
            df.to_parquet(parquet_path, index=False)
            
            # Initialize DataManager with the directory
            self.dm = DataManager(data_dir)
            
            # Display results via DataManager (enables filtering, export, paging)
            self.results_widget.load_manager(self.dm)
            
            elapsed = self.elapsed_seconds
            rows = len(df)
            self.results_widget.set_status(f"Loaded {rows} rows in {elapsed}s")
            self.ui.set_status(f"Query Completed: {rows} rows in {elapsed}s")
             
            # Save Persistence State
            last_run_str = persistence.get_current_time_str()
            persistence.save_state(f"segment_{segment_name}", {
                "data_path": data_dir,
                "last_run": last_run_str,
                "row_count": rows
            })
            
            self.progress_bar.setVisible(False)
            self.progress_bar.setRange(0, 100)
            self.progress_bar.setValue(100)
            self.btn_run.setEnabled(True)
            self.timer.stop()
            
            logger.info(f"Segment query saved to {parquet_path} and loaded via DataManager")
            
        except Exception as e:
            logger.error(f"Failed to process segment results: {e}")
            self.ui.set_status(f"Error: {str(e)}", error=True)
            self.progress_bar.setVisible(False)
            self.btn_run.setEnabled(True)
            self.timer.stop()
    
    def on_query_error(self, error_msg):
        """Handle query error."""
        self.timer.stop()
        self.ui.set_status(f"Error: {error_msg}", error=True)
        self.progress_bar.setVisible(False)
        self.btn_run.setEnabled(True)
        QMessageBox.critical(self, "Query Failed", error_msg)

    def update_timer(self):
        """Update the status label with elapsed time."""
        self.elapsed_seconds += 1
        self.ui.set_status(f"Executing segment query ({self.elapsed_seconds}s)...")
        if self.elapsed_seconds % 30 == 0:
            logger.info(f"Query still running ({self.elapsed_seconds}s elapsed)...")


class TaskSegmentsWidget(QWidget):
    """Main Segments UI widget (Manages Stack)."""
    
    def __init__(self):
        super().__init__()
        self.layout = QVBoxLayout(self)
        self.layout.setContentsMargins(0, 0, 0, 0)
        
        self.stack = QStackedWidget()
        self.layout.addWidget(self.stack)
        
        # 1. Summary View
        self.summary_widget = SegmentSummaryWidget(self)
        self.stack.addWidget(self.summary_widget)
        
        # 2. Detail View
        self.detail_widget = SegmentDetailWidget(self)
        self.stack.addWidget(self.detail_widget)
        
        # Start at summary
        self.stack.setCurrentWidget(self.summary_widget)
    
    def setup_ui(self):
        # Legacy compatibility - no op
        pass
        
    def show_summary(self):
        self.summary_widget.refresh_data()
        self.stack.setCurrentWidget(self.summary_widget)

    def load_config(self, config):
        """Load a specific segment configuration."""
        if not config:
            self.show_summary()
            return
            
        self.detail_widget.set_config(config)
        self.stack.setCurrentWidget(self.detail_widget)



