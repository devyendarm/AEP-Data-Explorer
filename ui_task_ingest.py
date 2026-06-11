from PySide6.QtWidgets import (QWidget, QVBoxLayout, QHBoxLayout, QLabel, 
                               QPushButton, QFileDialog, QProgressBar, QGroupBox, 
                               QLineEdit, QTextEdit, QMessageBox, QDialog, QFormLayout, 
                               QRadioButton, QDialogButtonBox, QCheckBox, QStackedWidget,
                               QTableWidget, QTableWidgetItem, QHeaderView)
from PySide6.QtCore import Qt, QThread, Signal
import pandas as pd
import os
import datetime
import tempfile
import re

class IngestionConfigDialog(QDialog):
    def __init__(self, parent=None):
        super().__init__(parent)
        self.setWindowTitle("Create New Ingestion Task")
        self.resize(400, 300)
        
        layout = QVBoxLayout(self)
        form = QFormLayout()
        
        self.txt_name = QLineEdit()
        self.txt_name.setPlaceholderText("Task Name (e.g. Daily Upload)")
        form.addRow("Name:", self.txt_name)
        
        # Method Selection
        self.rb_batch = QRadioButton("Direct Batch (No Mapping)")
        self.rb_flow = QRadioButton("Dataflow (With Mapping)")
        self.rb_batch.setChecked(True)
        self.rb_batch.toggled.connect(self.toggle_mode)
        
        mode_layout = QHBoxLayout()
        mode_layout.addWidget(self.rb_batch)
        mode_layout.addWidget(self.rb_flow)
        form.addRow("Method:", mode_layout)
        
        # Target ID
        self.lbl_id = QLabel("Target Dataset ID:")
        self.txt_id = QLineEdit()
        self.txt_id.setPlaceholderText("Dataset UUID")
        form.addRow(self.lbl_id, self.txt_id)
        
        # Schema ID
        self.txt_schema_id = QLineEdit()
        self.txt_schema_id.setPlaceholderText("Schema UUID (Optional)")
        form.addRow("Schema ID:", self.txt_schema_id)
        
        layout.addLayout(form)
        
        # Buttons
        btns = QDialogButtonBox(QDialogButtonBox.Ok | QDialogButtonBox.Cancel)
        btns.accepted.connect(self.accept)
        btns.rejected.connect(self.reject)
        layout.addWidget(btns)
        
    def toggle_mode(self):
        if self.rb_batch.isChecked():
            self.lbl_id.setText("Target Dataset ID:")
            self.txt_id.setPlaceholderText("Dataset UUID")
        else:
            self.lbl_id.setText("Target Flow ID:")
            self.txt_id.setPlaceholderText("Dataflow UUID")

    def get_data(self):
        return {
            "name": self.txt_name.text().strip(),
            "method": "batch" if self.rb_batch.isChecked() else "flow",
            "target_id": self.txt_id.text().strip(),
            "schema_id": self.txt_schema_id.text().strip()
        }
        
    def set_data(self, config):
        if not config: return
        self.txt_name.setText(config.get("name", ""))
        self.txt_id.setText(config.get("target_id", ""))
        self.txt_schema_id.setText(config.get("schema_id", ""))
        
        if config.get("method") == "flow":
            self.rb_flow.setChecked(True)
        else:
            self.rb_batch.setChecked(True)
            
        self.toggle_mode()


class IngestSummaryWidget(QWidget):
    """Displays a table summary of all configured ingestion tasks."""
    def __init__(self, parent_task_widget):
        super().__init__()
        self.parent_task = parent_task_widget
        
        layout = QVBoxLayout(self)
        layout.setContentsMargins(20, 20, 20, 20)
        
        # Header
        lbl_title = QLabel("Ingestion Summary")
        lbl_title.setStyleSheet("font-size: 24px; font-weight: bold; color: white; margin-bottom: 10px;")
        layout.addWidget(lbl_title)
        
        # Table
        self.table = QTableWidget()
        self.table.setColumnCount(3)
        self.table.setHorizontalHeaderLabels(["Task Name", "Method", "Target ID"])
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
        tasks = persistence.load_ingestion_tasks()
        self.table.setRowCount(0)
        self.tasks_map = {}
        
        if not tasks: return

        self.table.setRowCount(len(tasks))
        for idx, task in enumerate(tasks):
            self.table.setItem(idx, 0, QTableWidgetItem(task.get("name", "Unknown")))
            self.table.setItem(idx, 1, QTableWidgetItem(task.get("method", "batch").capitalize()))
            self.table.setItem(idx, 2, QTableWidgetItem(task.get("target_id", "N/A")))
            self.tasks_map[idx] = task
            
    def on_row_clicked(self, item):
        row = item.row()
        if row in self.tasks_map:
            config = self.tasks_map[row]
            # Ideally the sidebar will also be updated, but for now just switch view
            self.parent_task.load_config(config)

class TaskIngestWidget(QWidget):
    def __init__(self):
        super().__init__()
        self.current_config = None
        # Initialise AEP service for API calls
        from aep_service import AEPService
        self.service = AEPService()
        # Track temporary file created for ingestionDate column
        self._temp_upload_path = None
        
        self.layout = QVBoxLayout(self)
        self.layout.setContentsMargins(0, 0, 0, 0)
        
        self.stacked_widget = QStackedWidget()
        self.layout.addWidget(self.stacked_widget)
        
        self.summary_widget = IngestSummaryWidget(self)
        self.stacked_widget.addWidget(self.summary_widget)
        
        # --- Detail View Widget ---
        self.detail_widget = QWidget()
        detail_layout = QVBoxLayout(self.detail_widget)
        detail_layout.setContentsMargins(20, 20, 20, 20)
        detail_layout.setSpacing(20)
        
        self.stacked_widget.addWidget(self.detail_widget)
        
        # Title
        self.lbl_title = QLabel("Ingestion Task")
        self.lbl_title.setStyleSheet("font-size: 20px; font-weight: bold; color: white;")
        detail_layout.addWidget(self.lbl_title)
        
        # Details / Config Display
        self.lbl_details = QLabel("Select a task to view details.")
        self.lbl_details.setStyleSheet("color: #aaa; margin-bottom: 10px;")
        detail_layout.addWidget(self.lbl_details)

        # --- File Selection Section ---
        file_group = QGroupBox("File Selection")
        file_layout = QVBoxLayout(file_group)
        
        file_btn_layout = QHBoxLayout()
        self.lbl_file_path = QLabel("No file selected")
        self.lbl_file_path.setStyleSheet("color: #aaa; font-style: italic;")
        
        btn_browse = QPushButton("Browse Excel/CSV")
        btn_browse.setCursor(Qt.PointingHandCursor)
        btn_browse.setStyleSheet("""
            QPushButton {
                background-color: #444; color: white; padding: 8px 15px; border-radius: 4px; border: 1px solid #555;
            }
            QPushButton:hover { background-color: #555; }
        """)
        btn_browse.clicked.connect(self.browse_file)
        
        file_btn_layout.addWidget(btn_browse)
        file_btn_layout.addWidget(self.lbl_file_path)
        file_btn_layout.addStretch()
        
        file_layout.addLayout(file_btn_layout)

        # Ingestion Date Checkbox (optional timestamp column)
        self.chk_ingest_date = QCheckBox("Add ingestionDate column (upload timestamp)")
        self.chk_ingest_date.setChecked(False)
        file_layout.addWidget(self.chk_ingest_date)

        detail_layout.addWidget(file_group)

        # --- Action Section ---
        action_group = QGroupBox("Actions")
        action_layout = QVBoxLayout(action_group)
        
        btn_layout = QHBoxLayout()
        
        # Validate Button
        self.btn_validate = QPushButton("1. Validate Schema")
        self.btn_validate.setCursor(Qt.PointingHandCursor)
        self.btn_validate.setMinimumHeight(40)
        self.btn_validate.setStyleSheet("""
            QPushButton { background-color: #e65100; color: white; font-weight: bold; border-radius: 4px; border: none; }
            QPushButton:hover { background-color: #ef6c00; }
            QPushButton:disabled { background-color: #333; color: #888; }
        """)
        self.btn_validate.clicked.connect(self.validate_schema)
        self.btn_validate.setEnabled(False)
        
        # Upload Button
        self.btn_upload = QPushButton("2. Upload to AEP")
        self.btn_upload.setCursor(Qt.PointingHandCursor)
        self.btn_upload.setMinimumHeight(40)
        self.btn_upload.setStyleSheet("""
            QPushButton { background-color: #2e7d32; color: white; font-weight: bold; border-radius: 4px; border: none; }
            QPushButton:hover { background-color: #388e3c; }
            QPushButton:disabled { background-color: #333; color: #888; }
        """)
        self.btn_upload.clicked.connect(self.upload_file)
        self.btn_upload.setEnabled(False)
        
        btn_layout.addWidget(self.btn_validate)
        btn_layout.addWidget(self.btn_upload)
        action_layout.addLayout(btn_layout)
        
        # Progress Bar
        self.progress = QProgressBar()
        self.progress.setTextVisible(True)
        self.progress.setFormat("%p% - Ready")
        self.progress.setStyleSheet("QProgressBar { border: 1px solid #444; border-radius: 6px; text-align: center; background-color: #1e1e1e; height: 20px; margin-top: 10px; } QProgressBar::chunk { background-color: #007acc; width: 10px; }")
        self.progress.setVisible(False)
        action_layout.addWidget(self.progress)
        
        detail_layout.addWidget(action_group)
        
        # --- Log/Status Section ---
        self.txt_log = QTextEdit()
        self.txt_log.setReadOnly(True)
        self.txt_log.setPlaceholderText("Process logs will appear here...")
        self.txt_log.setStyleSheet("background-color: #1e1e1e; color: #ccc; border: 1px solid #333; font-family: Consolas; font-size: 12px;")
        detail_layout.addWidget(self.txt_log)

        self.selected_file = None
        self.load_config(None)

    def show_summary(self):
        """Displays the high-level summary table."""
        self.stacked_widget.setCurrentWidget(self.summary_widget)
        self.summary_widget.refresh_data()

    def log(self, message):
        self.txt_log.append(f"[{datetime.datetime.now().strftime('%H:%M:%S')}] {message}")
        # Scroll to bottom
        sb = self.txt_log.verticalScrollBar()
        sb.setValue(sb.maximum())

    def load_config(self, config):
        """Loads a specific ingestion configuration."""
        self.current_config = config
        
        if not config:
            self.show_summary()
            return

        self.stacked_widget.setCurrentWidget(self.detail_widget)

        self.setEnabled(True)
        self.txt_log.clear()
        
        name = config.get("name", "Unnamed")
        method = "Dataflow" if config.get("method") == "flow" else "Direct Batch"
        target_id = config.get("target_id", "N/A")
        schema_id = config.get("schema_id", "N/A")
        
        self.lbl_title.setText(name)
        self.lbl_details.setText(f"Method: {method} | Target: {target_id} | Schema: {schema_id}")


    def browse_file(self):
        path, _ = QFileDialog.getOpenFileName(self, "Select File", "", "Excel/CSV Files (*.xlsx *.csv)")
        if path:
            self.selected_file = path
            self.lbl_file_path.setText(os.path.basename(path))
            self.lbl_file_path.setStyleSheet("color: #4caf50; font-weight: bold;")
            self.btn_validate.setEnabled(True)
            self.log(f"Selected file: {path}")

    def validate_schema(self):
        if not self.selected_file:
            # No file selected – keep button disabled
            self.log("Validate clicked without a file selected.")
            return
        if not self.current_config:
            return
        
        schema_id = self.current_config.get("schema_id")
        if not schema_id:
             # If optional? Or warn?
             msg = "No Schema ID configured for this task. Please edit the task to add one."
             self.log(msg)
             QMessageBox.warning(self, "No Schema", msg)
             return

        self.btn_validate.setEnabled(False)
        self.progress.setVisible(True)
        self.progress.setValue(0)
        self.progress.setFormat("Validating...")
        self.log("Starting Schema Validation...")
        
        # Initialize Service (if not already injected)
        if not self.service:
            from aep_service import AEPService
            self.service = AEPService()
        
        # Start Worker
        self.val_worker = SchemaValidationWorker(self.service, schema_id, self.selected_file)
        self.val_worker.progress.connect(self.update_progress)
        self.val_worker.log.connect(self.log)
        self.val_worker.finished.connect(self.on_validation_finished)
        self.val_worker.error.connect(self.on_validation_error)
        self.val_worker.start()

    def on_validation_finished(self, success):
        self.btn_validate.setEnabled(True)
        self.btn_upload.setEnabled(True)
        self.progress.setValue(100)
        self.progress.setFormat("Validation Passed")
        self.log("Validation Successful! File headers match schema.")
        QMessageBox.information(self, "Success", "Validation Passed. You can now upload.")

    def on_validation_error(self, err):
        self.btn_validate.setEnabled(True)
        self.progress.setValue(0)
        self.progress.setFormat("Validation Failed")
        self.log(f"Validation Error: {err}")
        QMessageBox.critical(self, "Validation Failed", str(err))

    def upload_file(self):
        if not self.selected_file:
            self.log("Upload clicked without a file selected.")
            return
        if not self.current_config:
            return
        
        target_id = self.current_config.get("target_id")
        mode = self.current_config.get("method", "batch")
        
        if not target_id:
            QMessageBox.warning(self, "Missing Config", "No Target ID configured.")
            return
        
        # Prepare file path – inject ingestionDate if requested
        upload_path = self.selected_file
        # Reset any previous temp path
        self._temp_upload_path = None
        if getattr(self, "chk_ingest_date", None) and self.chk_ingest_date.isChecked():
            self.log("Adding ingestionDate column (UTC timestamp) to CSV...")
            df = pd.read_csv(upload_path)
            df["ingestionDate"] = datetime.datetime.utcnow().replace(tzinfo=datetime.timezone.utc).isoformat()
            tmp = tempfile.NamedTemporaryFile(delete=False, suffix=".csv")
            df.to_csv(tmp.name, index=False)
            upload_path = tmp.name
            self._temp_upload_path = tmp.name
        # Validate target ID for batch mode (must be a UUID)
        if mode == "batch":
            uuid_regex = re.compile(r"^[0-9a-fA-F-]{36}$")
            if not uuid_regex.match(target_id):
                QMessageBox.warning(self, "Invalid Dataset ID", "When using Direct Batch, the Target ID must be a valid Dataset UUID.")
                return        
        self.btn_upload.setEnabled(False)
        self.progress.setVisible(True)
        self.progress.setValue(0)
        
        label = "Starting Dataflow Ingestion..." if mode == "flow" else "Starting Batch Ingestion..."
        self.progress.setFormat(label)
        self.log(label)
        
        # Start Worker with the (potentially temporary) file
        self.worker = IngestionWorker(self.service, target_id, upload_path, mode)
        self.worker.progress.connect(self.update_progress)
        self.worker.log.connect(self.log)
        self.worker.finished.connect(self.on_upload_finished)
        self.worker.error.connect(self.on_upload_error)
        self.worker.start()

    def update_progress(self, val, msg):
        self.progress.setValue(val)
        self.progress.setFormat(f"{msg} ({val}%)")

    def on_upload_finished(self, success):
        self.btn_upload.setEnabled(True)
        self.progress.setValue(100)
        self.progress.setFormat("Ingestion Complete")
        self.progress.setVisible(False)
        self.log("Batch Ingestion Cycle Completed Successfully.")
        QMessageBox.information(self, "Success", "File successfully ingested into AEP.")
        # Clean up temporary file if it was created
        if self._temp_upload_path:
            try:
                os.remove(self._temp_upload_path)
                self.log(f"Removed temporary file: {self._temp_upload_path}")
            except Exception as e:
                self.log(f"Failed to remove temporary file: {e}")
            finally:
                self._temp_upload_path = None

    def on_upload_error(self, err):
        self.btn_upload.setEnabled(True)
        self.progress.setValue(0)
        self.progress.setFormat("Error")
        self.log(f"Error: {err}")
        QMessageBox.critical(self, "Ingestion Failed", str(err))
        # Clean up temporary file if it was created
        if self._temp_upload_path:
            try:
                os.remove(self._temp_upload_path)
                self.log(f"Removed temporary file: {self._temp_upload_path}")
            except Exception as e:
                self.log(f"Failed to remove temporary file: {e}")
            finally:
                self._temp_upload_path = None

class IngestionWorker(QThread):
    progress = Signal(int, str)
    log = Signal(str)
    finished = Signal(bool)
    error = Signal(str)

            # Determine Mode based on input (Basic Heuristic: Dataset ID (usually UUID) vs Flow ID (usually UUID))
            # But the UI passes 'dataset_id' as variable name.
            # We need to know the mode. 
            # Ideally, the worker should accept a 'mode' param or we infer.
            # Let's assume if we are in 'Flow' mode, the dataset_id passed is actually a flow_id.
            # The safer way is to update __init__, but let's try to infer or check if we can pass a 'is_flow' flag.
            
            # Since I can't easily change the __init__ signature without breaking the UI call site potentially 
            # if I missed it in step 1 (I did not update the UI call site yet).
            # I WILL update the UI call site in the next step. 
            # So here, I will update __init__ to accept 'mode'.

    def __init__(self, service, target_id, file_path, mode="batch"):
        super().__init__()
        self.service = service
        self.target_id = target_id
        self.file_path = file_path
        self.mode = mode

    def run(self):
        try:
            if self.mode == "flow":
                 # DATAFLOW PATH
                 self.progress.emit(10, "Initializing Flow")
                 self.log.emit(f"Ingesting via Dataflow {self.target_id}...")
                 
                 self.service.ingest_via_flow(self.target_id, self.file_path)
                 
                 self.progress.emit(100, "Upload Complete")
                 self.log.emit("File uploaded to flow source. Flow execution is managed by AEP.")
                 self.finished.emit(True)
                 return

            # DIRECT BATCH PATH
            # 1. Create Batch
            self.progress.emit(10, "Creating Batch")
            self.log.emit("Creating new batch in AEP...")
            batch_id = self.service.create_batch(self.target_id)
            self.log.emit(f"Batch Created: {batch_id}")
            
            # 2. Upload File
            self.progress.emit(30, "Uploading File")
            self.log.emit(f"Uploading {os.path.basename(self.file_path)}...")
            self.service.upload_file_to_batch(batch_id, self.target_id, self.file_path)
            self.log.emit("Upload successful.")
            
            # 3. Complete Batch
            self.progress.emit(60, "Signaling Completion")
            self.log.emit("Signaling batch completion...")
            self.service.complete_batch(batch_id)
            
            # 4. Poll Status
            self.progress.emit(70, "Verifying Ingestion")
            self.log.emit("Waiting for ingestion processing...")
            
            import time
            retries = 0
            while retries < 20: # Poll for ~10 mins max
                status = self.service.get_batch_status(batch_id)
                self.log.emit(f"Batch Status: {status}")
                
                if status == "success":
                    self.progress.emit(100, "Success")
                    self.finished.emit(True)
                    return
                elif status == "failed":
                    raise Exception("Batch ingestion failed in AEP.")
                
                time.sleep(30)
                retries += 1
                self.progress.emit(70 + retries, f"Processing ({status})...")
            
            raise Exception("Timed out waiting for batch success.")

        except Exception as e:
            self.error.emit(str(e))

class SchemaValidationWorker(QThread):
    progress = Signal(int, str)
    log = Signal(str)
    finished = Signal(bool)
    error = Signal(str)

    def __init__(self, service, schema_id, file_path):
        super().__init__()
        self.service = service
        self.schema_id = schema_id
        self.file_path = file_path

    def run(self):
        try:
            # 1. Fetch Schema
            self.progress.emit(10, "Fetching Schema")
            self.log.emit(f"Fetching XDM Schema {self.schema_id} from AEP...")
            schema_props = self.service.fetch_schema_fields(self.schema_id)
            
            if not schema_props:
                raise Exception("Schema has no properties or could not be retrieved.")
                
            self.log.emit("Schema fetched successfully.")
            
            # 2. Read Local File Headers
            self.progress.emit(40, "Reading Local File")
            self.log.emit(f"Reading headers from {os.path.basename(self.file_path)}...")
            
            if self.file_path.endswith('.xlsx'):
                df = pd.read_excel(self.file_path, nrows=0)
            elif self.file_path.endswith('.csv'):
                df = pd.read_csv(self.file_path, nrows=0)
            else:
                raise Exception("Unsupported file type. Please select an Excel (.xlsx) or CSV (.csv) file.")
                
            local_headers = set(df.columns)
            
            # 3. Compare
            self.progress.emit(60, "Comparing Fields")
            # XDM properties are keys in the 'properties' dict. 
            # Note: This is a loose match for MVP. XDM is hierarchical (object types).
            # We will flatten the keys or just check top level? 
            # AEP Ingestion often maps flat CSV headers to XDM paths if they match names, 
            # or requires a mapping.
            # For this 'Data Explorer', let's assume flat schema or check if headers exist in schema keys.
            
            # Simple check: Are there any fields in the file that are NOT in the schema?
            # Or do we just check availability?
            # Let's check for at least ONE matching field to confirm plausibility, 
            # and warn about extras.
            
            schema_keys = set(schema_props.keys())
            
            # recursive search for keys if it's nested?
            # For MVP: Flatten schema keys slightly?
            # Let's just use top-level keys for now as many custom schemas are flat-ish or mapped.
            
            common = local_headers.intersection(schema_keys)
            missing_in_schema = local_headers - schema_keys
            
            if not common:
                 self.log.emit("WARNING: No column headers match top-level schema fields.")
                 # Don't fail hard, just warn? Or fail? 
                 # If it's 0 match, it's likely wrong.
                 raise Exception("Validation Failed: No local columns match schema definition.")
            
            if missing_in_schema:
                self.log.emit(f"Note: {len(missing_in_schema)} columns in file are not in top-level schema (will be ignored or need mapping).")
                self.log.emit(f"Extra columns: {', '.join(list(missing_in_schema)[:5])}...")
            
            self.log.emit(f"Confirmed {len(common)} matching fields.")
            self.progress.emit(100, "Validation Passed")
            self.finished.emit(True)

        except Exception as e:
            self.error.emit(str(e))
