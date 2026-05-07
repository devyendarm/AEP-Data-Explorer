from PySide6.QtWidgets import (QWidget, QVBoxLayout, QHBoxLayout, QLabel, 
                               QPushButton, QScrollArea, QSplitter, QListWidget,
                               QFrame, QComboBox, QLineEdit, QFormLayout, 
                               QMessageBox, QStackedWidget, QTextEdit, QProgressBar, QFileDialog,
                               QTableWidget, QTableWidgetItem, QHeaderView)
from PySide6.QtCore import Qt, Signal, QThread
from logger import logger
import persistence
import datetime
import json
import re
import time
import requests
from aep_service import AEPService

class WorkflowWorker(QThread):
    progress_signal = Signal(str, int)  # status_msg, progress_value
    log_signal = Signal(str)
    finished_signal = Signal(bool, str) # success, error_msg
    
    def __init__(self, steps_config, parent=None):
        super().__init__(parent)
        self.steps = steps_config
        self.state = {} # Holds step outputs like {{step1_batchID}}
        self.is_running = True
        
    def stop(self):
        self.is_running = False
        
    def resolve_variables(self, text):
        """Replaces {{key}} with values from self.state"""
        if not text: return text
        pattern = r'\{\{(.*?)\}\}'
        
        def replace_match(match):
            key = match.group(1)
            return str(self.state.get(key, match.group(0)))
            
        return re.sub(pattern, replace_match, text)

    def run(self):
        try:
            service = AEPService()
            service.auth.get_access_token()
        except Exception as e:
            self.log_signal.emit(f"Failed to initialize AEPService: {str(e)}")
            self.finished_signal.emit(False, str(e))
            return
            
        self.log_signal.emit(f"Starting workflow execution with {len(self.steps)} steps.")
        
        for i, step in enumerate(self.steps):
            if not self.is_running:
                self.log_signal.emit("Workflow stopped by user.")
                break
                
            step_id = step.get("id", f"step{i+1}")
            step_type = step.get("type", "Unknown")
            
            self.log_signal.emit(f"--- Executing Step {i+1}: {step_type} ---")
            self.progress_signal.emit(f"Running {step_type}", int((i / len(self.steps)) * 100))
            
            # --- Live Execution Logic ---
            try:
                if step_type == "Ingest Data":
                    file_path = self.resolve_variables(step.get("file_path", ""))
                    target_id = self.resolve_variables(step.get("dataset_id", ""))
                    method = step.get("method", "batch")
                    schema_id = step.get("schema_id", "")
                    
                    if method == "flow":
                        self.log_signal.emit(f"Ingesting via Dataflow: {target_id}")
                        service.ingest_via_flow(target_id, file_path)
                        self.log_signal.emit("File uploaded to Dataflow source successfully.")
                        self.progress_signal.emit("Dataflow Triggered", int((i / len(self.steps)) * 100))
                    else:
                        self.log_signal.emit(f"Creating batch for dataset: {target_id}")
                        batch_id = service.create_batch(target_id)
                        self.log_signal.emit(f"Batch created: {batch_id}. Uploading file...")
                        
                        service.upload_file_to_batch(batch_id, target_id, file_path)
                        
                        self.log_signal.emit("File uploaded. Completing batch...")
                        service.complete_batch(batch_id)
                        
                        self.log_signal.emit("Polling ingestion status...")
                        while True:
                            status = service.get_batch_status(batch_id)
                            self.log_signal.emit(f"Batch status: {status}")
                            if status == "success":
                                self.state[f"{step_id}_batchID"] = batch_id
                                self.log_signal.emit(f"Ingestion successful! Batch ID: {batch_id}")
                                break
                            elif status in ["failed", "aborted"]:
                                raise Exception(f"Ingestion failed with status: {status}")
                            time.sleep(10)
                        
                elif step_type == "Run Query":
                    query_method = step.get("query_method", "Direct SQL")
                    initial_wait = int(step.get("initial_wait", 30))
                    poll_interval = int(step.get("poll_interval", 10))
                    
                    if query_method == "Template based":
                        template_id = self.resolve_variables(step.get("template_id", ""))
                        self.log_signal.emit(f"Submitting Template Query: {template_id}")
                        import aep_template
                        job_id = aep_template.submit_template(template_id)
                        self.log_signal.emit(f"Template Query submitted: {job_id}")
                    else:
                        sql = self.resolve_variables(step.get("sql", ""))
                        self.log_signal.emit(f"Executing SQL:\n{sql}")
                        job_id = service.post_query(sql)
                        self.log_signal.emit(f"Direct Query submitted: {job_id}")
                    
                    self.log_signal.emit(f"Initial wait of {initial_wait} seconds...")
                    time.sleep(initial_wait)
                    
                    self.log_signal.emit(f"Polling for completion (Interval: {poll_interval}s)...")
                    url = f"https://platform.adobe.io/data/foundation/query/queries/{job_id}"
                    headers = service.auth.get_headers()
                    
                    while True:
                        if not self.is_running: break
                        resp = requests.get(url, headers=headers)
                        resp.raise_for_status()
                        data = resp.json()
                        state = data.get("state")
                        self.log_signal.emit(f"Query {job_id} state: {state}")
                        
                        if state == "SUCCESS":
                            self.state[f"{step_id}_jobID"] = job_id
                            self.log_signal.emit(f"Query completed successfully.")
                            break
                        elif state in ["FAILED", "CANCELLED"]:
                            raise Exception(f"Query failed with state: {state}")
                        
                        time.sleep(poll_interval)
                    
                elif step_type == "Batch Lookup":
                    dataset_id = self.resolve_variables(step.get("dataset_id", ""))
                    self.log_signal.emit(f"Looking up latest batch for dataset: {dataset_id}")
                    
                    # Use the robust catalog lookup that validates batch status.
                    from aep_catalog import get_latest_batch
                    try:
                        latest_batch_id = get_latest_batch(dataset_id)
                        self.state[f"{step_id}_batchID"] = latest_batch_id
                        self.log_signal.emit(f"Found latest batch: {latest_batch_id}")
                    except Exception as e:
                        # Propagate to on_error to surface UI error.
                        raise Exception(f"Batch lookup failed: {e}")
                        
                elif step_type == "Trigger Destination":
                    flow_id = self.resolve_variables(step.get("flow_id", ""))
                    self.log_signal.emit(f"Triggering Destination Dataflow: {flow_id}")
                    
                    url = f"https://platform.adobe.io/data/foundation/flowservice/runs"
                    headers = service.auth.get_headers()
                    payload = {"flowId": flow_id}
                    
                    resp = requests.post(url, headers=headers, json=payload)
                    resp.raise_for_status()
                    run_id = resp.json().get("id", "Unknown")
                    self.log_signal.emit(f"Destination run triggered! Run ID: {run_id}")
                    self.state[f"{step_id}_runID"] = run_id
                    
                elif step_type == "External API":
                    method = step.get("method", "GET")
                    url = self.resolve_variables(step.get("url", ""))
                    self.log_signal.emit(f"Calling External API -> {method} {url}")
                    
                    resp = requests.request(method, url)
                    resp.raise_for_status()
                    self.log_signal.emit(f"API Call Succeeded: {resp.status_code}")
                    self.state[f"{step_id}_apiStatus"] = resp.status_code
                    
            except Exception as e:
                self.log_signal.emit(f"ERROR in Step {i+1}: {str(e)}")
                self.finished_signal.emit(False, str(e))
                return

            
        if self.is_running:
            self.progress_signal.emit("Workflow Complete", 100)
            self.log_signal.emit("=== Workflow Execution Completed Successfully ===")
            self.finished_signal.emit(True, "")

class WorkflowStepWidget(QFrame):
    """A single step in the workflow accordion."""
    def __init__(self, step_id, step_type, parent=None):
        super().__init__(parent)
        self.step_id = step_id
        self.step_type = step_type
        self.setObjectName("AccordionStep")
        self.setStyleSheet("""
            #AccordionStep {
                border: 1px solid #333;
                border-radius: 5px;
                background-color: #252526;
                margin-bottom: 5px;
            }
        """)
        self.layout = QVBoxLayout(self)
        self.layout.setContentsMargins(0, 0, 0, 0)
        
        # Header (Clickable to expand/collapse)
        self.header = QFrame()
        self.header.setStyleSheet("background-color: #2d2d2d; border-radius: 5px;")
        self.header.setCursor(Qt.PointingHandCursor)
        header_layout = QHBoxLayout(self.header)
        
        self.lbl_title = QLabel(f"Step: {step_type}")
        self.lbl_title.setStyleSheet("font-weight: bold; font-size: 14px; color: #fff;")
        header_layout.addWidget(self.lbl_title)
        header_layout.addStretch()
        
        self.btn_delete = QPushButton("✖")
        self.btn_delete.setCursor(Qt.PointingHandCursor)
        self.btn_delete.setStyleSheet("border: none; background: transparent; font-weight: bold; color: #d9534f; font-size: 14px; margin-right: 10px;")
        header_layout.addWidget(self.btn_delete)
        
        self.btn_toggle = QPushButton("▼")
        self.btn_toggle.setStyleSheet("border: none; background: transparent; font-weight: bold; color: #888;")
        header_layout.addWidget(self.btn_toggle)
        self.layout.addWidget(self.header)
        
        # Body (Configuration Forms)
        self.body = QWidget()
        self.body_layout = QFormLayout(self.body)
        self.setup_body()
        self.layout.addWidget(self.body)
        
        # Connections
        self.header.mousePressEvent = self.toggle_body
        self.btn_toggle.clicked.connect(self.toggle_body)
        self.expanded = True
        
    def toggle_body(self, event=None):
        self.expanded = not self.expanded
        self.body.setVisible(self.expanded)
        self.btn_toggle.setText("▼" if self.expanded else "▶")
        
    def toggle_query_mode(self, index=None):
        if self.step_type == "Run Query":
            idx = self.query_method_combo.currentIndex()
            is_template = (idx == 1)
            self.lbl_template_id.setVisible(is_template)
            self.template_id.setVisible(is_template)
            self.lbl_query_text.setVisible(not is_template)
            self.query_text.setVisible(not is_template)
        
    def setup_body(self):
        """Build form based on step type"""
        if self.step_type == "Ingest Data":
            # Method
            self.method_combo = QComboBox()
            self.method_combo.addItems(["Direct Batch (No Mapping)", "Dataflow (With Mapping)"])
            self.body_layout.addRow("Ingestion Method:", self.method_combo)
            
            # IDs
            self.dataset_id = QLineEdit()
            self.dataset_id.setPlaceholderText("Dataset UUID or Dataflow UUID")
            self.body_layout.addRow("Target ID:", self.dataset_id)
            
            self.schema_id = QLineEdit()
            self.schema_id.setPlaceholderText("Schema UUID (Optional)")
            self.body_layout.addRow("Schema ID:", self.schema_id)
            
            # File
            file_layout = QHBoxLayout()
            self.file_path = QLineEdit()
            self.file_path.setPlaceholderText("Path to CSV/Excel File or Dynamic {{var}}")
            btn_browse = QPushButton("Browse")
            btn_browse.clicked.connect(self.browse_file)
            file_layout.addWidget(self.file_path)
            file_layout.addWidget(btn_browse)
            
            self.body_layout.addRow("Local File:", file_layout)
        elif self.step_type == "Run Query":
            from PySide6.QtWidgets import QSpinBox
            
            self.query_method_combo = QComboBox()
            self.query_method_combo.addItems(["Direct SQL", "Template based"])
            self.body_layout.addRow("Method:", self.query_method_combo)
            
            self.template_id = QLineEdit()
            self.template_id.setPlaceholderText("Template UUID or Dynamic {{var}}")
            self.lbl_template_id = QLabel("Template ID:")
            self.lbl_template_id.setVisible(False)
            self.template_id.setVisible(False)
            self.body_layout.addRow(self.lbl_template_id, self.template_id)
            
            self.query_text = QTextEdit()
            self.query_text.setPlaceholderText("SELECT * FROM dataset WHERE batch_id = '{{step1_batchID}}'")
            self.lbl_query_text = QLabel("SQL Query:")
            self.body_layout.addRow(self.lbl_query_text, self.query_text)
            
            self.query_method_combo.currentIndexChanged.connect(self.toggle_query_mode)
            
            self.spin_initial = QSpinBox()
            self.spin_initial.setRange(5, 3600)
            self.spin_initial.setValue(30)
            self.spin_initial.setSuffix(" sec")
            self.body_layout.addRow("Initial Wait:", self.spin_initial)
            
            self.spin_subsequent = QSpinBox()
            self.spin_subsequent.setRange(5, 600)
            self.spin_subsequent.setValue(10)
            self.spin_subsequent.setSuffix(" sec")
            self.body_layout.addRow("Poll Interval:", self.spin_subsequent)
        elif self.step_type == "Batch Lookup":
            self.dataset_id = QLineEdit()
            self.body_layout.addRow("Dataset ID:", self.dataset_id)
        elif self.step_type == "Trigger Destination":
            self.flow_id = QLineEdit()
            self.body_layout.addRow("Dataflow ID:", self.flow_id)
        elif self.step_type == "External API":
            self.url = QLineEdit()
            self.method = QComboBox()
            self.method.addItems(["GET", "POST", "PUT"])
            self.body_layout.addRow("Method:", self.method)
            self.body_layout.addRow("URL:", self.url)
            
    def browse_file(self):
        path, _ = QFileDialog.getOpenFileName(self, "Select CSV/Excel File", "", "Excel/CSV Files (*.xlsx *.csv)")
        if path:
            self.file_path.setText(path)
            
    def get_config(self):
        config = {"id": self.step_id, "type": self.step_type}
        if self.step_type == "Ingest Data":
            config["method"] = "batch" if "Batch" in self.method_combo.currentText() else "flow"
            config["dataset_id"] = self.dataset_id.text()
            config["schema_id"] = self.schema_id.text()
            config["file_path"] = self.file_path.text()
        elif self.step_type == "Run Query":
            config["query_method"] = self.query_method_combo.currentText()
            config["template_id"] = self.template_id.text()
            config["sql"] = self.query_text.toPlainText()
            config["initial_wait"] = self.spin_initial.value()
            config["poll_interval"] = self.spin_subsequent.value()
        elif self.step_type == "Batch Lookup":
            config["dataset_id"] = self.dataset_id.text()
        elif self.step_type == "Trigger Destination":
            config["flow_id"] = self.flow_id.text()
        elif self.step_type == "External API":
            config["method"] = self.method.currentText()
            config["url"] = self.url.text()
        return config
        
    def load_config(self, config):
        if self.step_type == "Ingest Data":
            self.method_combo.setCurrentIndex(0 if config.get("method", "batch") == "batch" else 1)
            self.dataset_id.setText(config.get("dataset_id", ""))
            self.schema_id.setText(config.get("schema_id", ""))
            self.file_path.setText(config.get("file_path", ""))
        elif self.step_type == "Run Query":
            method = config.get("query_method", "Direct SQL")
            self.query_method_combo.setCurrentText(method)
            self.template_id.setText(config.get("template_id", ""))
            self.query_text.setPlainText(config.get("sql", ""))
            self.spin_initial.setValue(int(config.get("initial_wait", 30)))
            self.spin_subsequent.setValue(int(config.get("poll_interval", 10)))
            self.toggle_query_mode()
        elif self.step_type == "Batch Lookup":
            self.dataset_id.setText(config.get("dataset_id", ""))
        elif self.step_type == "Trigger Destination":
            self.flow_id.setText(config.get("flow_id", ""))
        elif self.step_type == "External API":
            self.method.setCurrentText(config.get("method", "GET"))
            self.url.setText(config.get("url", ""))

class WorkflowCanvas(QWidget):
    def __init__(self, parent=None):
        super().__init__(parent)
        self.layout = QVBoxLayout(self)
        self.layout.setContentsMargins(10, 10, 10, 10)
        
        # Tools
        tools_layout = QHBoxLayout()
        self.cb_step_types = QComboBox()
        self.cb_step_types.addItems(["Ingest Data", "Run Query", "Batch Lookup", "Trigger Destination", "External API"])
        self.btn_add_step = QPushButton("Add Step +")
        self.btn_add_step.setStyleSheet("background-color: #007acc; color: white;")
        tools_layout.addWidget(self.cb_step_types)
        tools_layout.addWidget(self.btn_add_step)
        tools_layout.addStretch()
        self.layout.addLayout(tools_layout)
        
        # Scroll Area for Steps (Vertical Accordion)
        self.scroll = QScrollArea()
        self.scroll.setWidgetResizable(True)
        self.scroll.setStyleSheet("QScrollArea { border: none; }")
        
        self.steps_container = QWidget()
        self.steps_layout = QVBoxLayout(self.steps_container)
        self.steps_layout.setContentsMargins(0,0,0,0)
        self.steps_layout.setAlignment(Qt.AlignTop)
        
        self.scroll.setWidget(self.steps_container)
        self.layout.addWidget(self.scroll)
        
        # Bottom Actions
        actions_layout = QHBoxLayout()
        self.btn_save = QPushButton("Save Workflow")
        self.btn_run = QPushButton("Run Workflow")
        self.btn_run.setStyleSheet("background-color: #28a745; color: white; font-weight: bold;")
        actions_layout.addStretch()
        actions_layout.addWidget(self.btn_save)
        actions_layout.addWidget(self.btn_run)
        self.layout.addLayout(actions_layout)
        
        self.steps = []
        self.btn_add_step.clicked.connect(self.add_step)
        
    def add_step(self, step_type=None, config=None):
        if not step_type:
            step_type = self.cb_step_types.currentText()
            
        step_id = f"step{len(self.steps)+1}"
        step_widget = WorkflowStepWidget(step_id, step_type)
        
        if config:
            step_widget.load_config(config)
            
        # Collapse all others
        for existing in self.steps:
            if existing.expanded:
                existing.toggle_body()
                
        self.steps.append(step_widget)
        self.steps_layout.addWidget(step_widget)
        
        # Connect delete button
        step_widget.btn_delete.clicked.connect(lambda checked=False, s=step_widget: self.remove_step(s))
        
    def remove_step(self, step_widget):
        if step_widget in self.steps:
            self.steps.remove(step_widget)
        self.steps_layout.removeWidget(step_widget)
        step_widget.deleteLater()
        
    def get_workflow_config(self):
        return [step.get_config() for step in self.steps]
        
    def clear(self):
        for step in self.steps:
            self.steps_layout.removeWidget(step)
            step.deleteLater()
        self.steps.clear()

class DashboardScorecard(QWidget):
    def __init__(self, parent=None):
        super().__init__(parent)
        self.layout = QVBoxLayout(self)
        self.layout.setContentsMargins(10, 10, 10, 10)
        
        title = QLabel("Execution Dashboard")
        title.setStyleSheet("font-size: 16px; font-weight: bold; color: #fff;")
        self.layout.addWidget(title)
        
        self.progress_overall = QProgressBar()
        self.progress_overall.setValue(0)
        self.layout.addWidget(QLabel("Overall Progress:"))
        self.layout.addWidget(self.progress_overall)
        
        self.log_area = QTextEdit()
        self.log_area.setReadOnly(True)
        self.log_area.setStyleSheet("background-color: #1e1e1e; font-family: monospace; color: #ccc;")
        self.layout.addWidget(self.log_area)
        
    def append_log(self, msg):
        self.log_area.append(f"[{datetime.datetime.now().strftime('%H:%M:%S')}] {msg}")

class WorkflowSummaryWidget(QWidget):
    """Displays a table summary of all saved workflows."""
    def __init__(self, parent_task_widget):
        super().__init__()
        self.parent_task = parent_task_widget
        
        layout = QVBoxLayout(self)
        layout.setContentsMargins(20, 20, 20, 20)
        
        lbl_title = QLabel("Workflows Summary")
        lbl_title.setStyleSheet("font-size: 24px; font-weight: bold; color: white; margin-bottom: 10px;")
        layout.addWidget(lbl_title)
        
        self.table = QTableWidget()
        self.table.setColumnCount(2)
        self.table.setHorizontalHeaderLabels(["Workflow Name", "Step Count"])
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
        workflows = persistence.load_workflows()
        self.table.setRowCount(0)
        self.workflows_map = {}
        
        if not workflows: return

        self.table.setRowCount(len(workflows))
        for idx, w in enumerate(workflows):
            self.table.setItem(idx, 0, QTableWidgetItem(w.get("name", "Unknown")))
            step_count = str(len(w.get("steps", [])))
            self.table.setItem(idx, 1, QTableWidgetItem(step_count))
            self.workflows_map[idx] = w
            
    def on_row_clicked(self, item):
        row = item.row()
        if row in self.workflows_map:
            config = self.workflows_map[row]
            self.parent_task.load_workflow(config)

class TaskWorkflowWidget(QWidget):
    def __init__(self):
        super().__init__()
        self.layout = QVBoxLayout(self)
        self.layout.setContentsMargins(0, 0, 0, 0)
        
        self.stacked_widget = QStackedWidget()
        self.layout.addWidget(self.stacked_widget)
        
        self.summary_widget = WorkflowSummaryWidget(self)
        self.stacked_widget.addWidget(self.summary_widget)
        
        self.detail_widget = QWidget()
        detail_layout = QVBoxLayout(self.detail_widget)
        detail_layout.setContentsMargins(0, 0, 0, 0)
        
        # Header Strip with Toggle
        header_strip = QWidget()
        header_strip.setFixedHeight(20)
        header_strip.setStyleSheet("background-color: #1e1e1e; border-bottom: 1px solid #333;")
        header_layout = QHBoxLayout(header_strip)
        header_layout.setContentsMargins(10, 0, 10, 0)
        header_layout.addStretch()
        
        self.btn_toggle_top = QPushButton("▲")
        self.btn_toggle_top.setFixedSize(20, 20)
        self.btn_toggle_top.setCursor(Qt.PointingHandCursor)
        self.btn_toggle_top.setStyleSheet("border: none; background: transparent; color: #888; font-weight: bold;")
        self.btn_toggle_top.clicked.connect(self.toggle_top_panel)
        header_layout.addWidget(self.btn_toggle_top)
        
        detail_layout.addWidget(header_strip)
        
        # Splitter to hold Canvas and Dashboard (Top/Bottom)
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
        
        self.canvas = WorkflowCanvas()
        self.dashboard = DashboardScorecard()
        
        self.split_view.addWidget(self.canvas)
        self.split_view.addWidget(self.dashboard)
        
        # Initial ratio: Top Canvas (60%), Bottom Dashboard (40%)
        self.split_view.setSizes([600, 400])
        detail_layout.addWidget(self.split_view)
        
        self.stacked_widget.addWidget(self.detail_widget)
        
        # Wire up buttons
        self.canvas.btn_save.clicked.connect(self.save_workflow)
        self.canvas.btn_run.clicked.connect(self.run_workflow)
        self.worker = None

    def toggle_top_panel(self):
        sizes = self.split_view.sizes()
        if sizes[0] > 0:
            self.last_top_height = sizes[0]
            self.split_view.setSizes([0, sizes[0] + sizes[1]])
            self.btn_toggle_top.setText("▼")
        else:
            top_h = getattr(self, "last_top_height", 400)
            if top_h == 0: top_h = 400
            self.split_view.setSizes([top_h, sizes[1] - top_h])
            self.btn_toggle_top.setText("▲")

    def run_workflow(self):
        steps_config = self.canvas.get_workflow_config()
        if not steps_config:
            QMessageBox.warning(self, "No Steps", "Please add items to your workflow first.")
            return
            
        self.dashboard.log_area.clear()
        self.dashboard.progress_overall.setValue(0)
        
        self.worker = WorkflowWorker(steps_config)
        self.worker.log_signal.connect(self.dashboard.append_log)
        self.worker.progress_signal.connect(lambda msg, val: self.dashboard.progress_overall.setValue(val))
        
        # Disable buttons during run
        self.canvas.btn_run.setEnabled(False)
        self.worker.finished_signal.connect(self.on_workflow_finished)
        self.worker.start()
        
    def on_workflow_finished(self, success, error_msg):
        self.canvas.btn_run.setEnabled(True)
        if not success:
            QMessageBox.critical(self, "Workflow Failed", f"Execution stopped due to error:\n{error_msg}")

    def load_workflow(self, config):
        self.canvas.clear()
        self.current_config = config
        
        if not config:
            self.stacked_widget.setCurrentWidget(self.summary_widget)
            self.summary_widget.refresh_data()
            return
            
        self.stacked_widget.setCurrentWidget(self.detail_widget)
        self.canvas.btn_save.setEnabled(True)
        steps = config.get("steps", [])
        for step in steps:
            self.canvas.add_step(step_type=step["type"], config=step)

    def save_workflow(self):
        if not hasattr(self, 'current_config') or not self.current_config:
            return
            
        new_steps = self.canvas.get_workflow_config()
        self.current_config["steps"] = new_steps
        
        # Save to persistence
        workflows = persistence.load_workflows()
        for i, w in enumerate(workflows):
            if w["name"] == self.current_config["name"]:
                workflows[i] = self.current_config
                break
        persistence.save_workflows(workflows)
        QMessageBox.information(self, "Success", "Workflow saved successfully.")

    def clear(self):
        self.canvas.clear()
        self.current_config = None
