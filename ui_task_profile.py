import os
from PySide6.QtWidgets import (QWidget, QVBoxLayout, QHBoxLayout, QLabel, 
                               QLineEdit, QPushButton, QComboBox, QTabWidget, 
                               QMessageBox, QTreeWidget, QTreeWidgetItem, QHeaderView, QDialog, QStackedWidget,
                               QTableWidget, QTableWidgetItem, QSizePolicy)
from PySide6.QtCore import QThread, Signal
from ui_shared import StandardTaskLayout
from ui_results import ResultsWidget
from logger import logger
from aep_service import AEPService
import persistence
import json
import datetime

class ProfileConfigDialog(QDialog):
    def __init__(self, parent=None):
        super().__init__(parent)
        self.setWindowTitle("Profile Task Configuration")
        self.resize(500, 300)
        self.layout = QVBoxLayout(self)
        self.service = AEPService()
        
        # --- Fields ---
        
        # Name
        self.layout.addWidget(QLabel("Task Name:"))
        self.txt_name = QLineEdit()
        self.layout.addWidget(self.txt_name)
        
        # Merge Policy
        self.layout.addWidget(QLabel("Merge Policy:"))
        self.combo_policy = QComboBox()
        self.combo_policy.addItem("Default", None)
        self.combo_policy.setEditable(True)
        self.layout.addWidget(self.combo_policy)
        
        # Namespace
        self.layout.addWidget(QLabel("Namespace:"))
        self.combo_ns = QComboBox()
        self.combo_ns.setEditable(True)
        self.layout.addWidget(self.combo_ns)
        
        # Entity ID
        self.layout.addWidget(QLabel("Entity ID/Value:"))
        self.txt_id = QLineEdit()
        self.txt_id.setPlaceholderText("e.g. user@example.com")
        self.layout.addWidget(self.txt_id)

        # Lookup Type
        self.layout.addWidget(QLabel("Lookup Type:"))
        self.combo_type = QComboBox()
        self.combo_type.addItem("Profile Only", "profile")
        self.combo_type.addItem("Experience Events Only", "events_only")
        self.combo_type.addItem("Profile + Experience Events", "both")
        self.layout.addWidget(self.combo_type)
        
        # --- Status / Loading ---
        self.lbl_loading = QLabel("Fetching metadata...")
        self.lbl_loading.setStyleSheet("color: #888;")
        self.layout.addWidget(self.lbl_loading)
        
        # --- Buttons ---
        btn_layout = QHBoxLayout()
        btn_layout.addStretch()
        
        self.btn_save = QPushButton("Save")
        self.btn_save.clicked.connect(self.accept)
        self.btn_cancel = QPushButton("Cancel")
        self.btn_cancel.clicked.connect(self.reject)
        
        btn_layout.addWidget(self.btn_cancel)
        btn_layout.addWidget(self.btn_save)
        self.layout.addLayout(btn_layout)
        
        # --- Fetch Metadata ---
        self.fetch_metadata()

    def fetch_metadata(self):
        self.worker = MetadataWorker()
        self.worker.finished.connect(self.on_metadata_loaded)
        self.worker.start()

    def on_metadata_loaded(self, policies, identities):
        self.lbl_loading.setVisible(False)
        
        # 1. Policies
        current_p = self.combo_policy.currentText()
        if not current_p or current_p == "Default":
             pass # Keep default
        
        self.combo_policy.clear()
        self.combo_policy.addItem("Default", None)
        
        policies.sort(key=lambda x: x.get("name", ""))
        for p in policies:
            name = p.get("name", "Unknown")
            pid = p.get("id")
            self.combo_policy.addItem(name, pid)
            
        if current_p and current_p != "Default":
             self.combo_policy.setCurrentText(current_p)

        # 2. Identities
        current_ns = self.combo_ns.currentText()
        self.combo_ns.clear()
        
        defaults = ["email", "ecid", "crmid", "phone"]
        existing = set()
        
        identities.sort(key=lambda x: x.get("code", ""))
        for ns in identities:
             code = ns.get("code")
             if code:
                 self.combo_ns.addItem(code)
                 existing.add(code)
                 
        for d in defaults:
            if d not in existing:
                self.combo_ns.addItem(d)
                
        if current_ns:
            self.combo_ns.setCurrentText(current_ns)

    def set_data(self, data):
        if not data: return
        self.txt_name.setText(data.get("name", ""))
        self.combo_policy.setCurrentText(data.get("merge_policy", "Default"))
        self.combo_ns.setCurrentText(data.get("namespace", "email"))
        self.txt_id.setText(data.get("entity_id", ""))
        
        lookup_type = data.get("lookup_type", "profile")
        index = self.combo_type.findData(lookup_type)
        if index >= 0:
            self.combo_type.setCurrentIndex(index)

    def get_data(self):
        # Normalize namespace to lowercase for API compatibility
        ns = self.combo_ns.currentText().strip()
        if ns:
            ns = ns.lower()
            
        return {
            "name": self.txt_name.text().strip(),
            "merge_policy": self.combo_policy.currentText(),
            "namespace": ns,
            "entity_id": self.txt_id.text().strip(),
            "lookup_type": self.combo_type.currentData(),
            "last_fetch": None
        }

class ProfileSummaryWidget(QWidget):
    """Displays a table summary of all configured profile lookups."""
    def __init__(self, parent_task_widget):
        super().__init__()
        self.parent_task = parent_task_widget
        
        layout = QVBoxLayout(self)
        layout.setContentsMargins(20, 20, 20, 20)
        
        # Header
        lbl_title = QLabel("Profile Lookups Summary")
        lbl_title.setStyleSheet("font-size: 24px; font-weight: bold; color: white; margin-bottom: 10px;")
        layout.addWidget(lbl_title)
        
        # Table
        self.table = QTableWidget()
        self.table.setColumnCount(4)
        self.table.setHorizontalHeaderLabels(["Name", "Entity ID", "Namespace", "Last Lookup"]) # Columns
        self.table.horizontalHeader().setSectionResizeMode(QHeaderView.Stretch)
        self.table.setAlternatingRowColors(True)
        self.table.setEditTriggers(QTableWidget.NoEditTriggers)
        self.table.setSelectionBehavior(QTableWidget.SelectRows)
        self.table.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Expanding)
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
        tasks = persistence.load_profile_tasks()
        self.table.setRowCount(0)
        self.tasks_map = {} # item -> config
        
        if not tasks:
            return

        self.table.setRowCount(len(tasks))
        for idx, task in enumerate(tasks):
            self.table.setItem(idx, 0, QTableWidgetItem(task.get("name", "Unknown")))
            self.table.setItem(idx, 1, QTableWidgetItem(task.get("entity_id", "N/A")))
            self.table.setItem(idx, 2, QTableWidgetItem(task.get("namespace", "N/A")))
            self.table.setItem(idx, 3, QTableWidgetItem(task.get("last_fetch") or "Never"))
            
            self.tasks_map[idx] = task
            
    def on_row_clicked(self, item):
        row = item.row()
        config = self.tasks_map.get(row)
        if config:
            self.parent_task.load_config(config)

class ProfileDetailWidget(QWidget):
    def __init__(self, parent_task_widget):
        super().__init__()
        self.parent_task = parent_task_widget
        # Use Shared Layout
        self.ui = StandardTaskLayout(self)
        self.layout = QVBoxLayout(self)
        self.layout.setContentsMargins(0, 0, 0, 0)
        self.layout.addWidget(self.ui)
        
        self.service = AEPService()
        self.current_config = None
        self.loaded_data = None # Store current profile data
        
        # Customize Controls (Top Pane)
        layout = self.ui.controls_layout
        
        # Info Label
        self.lbl_info = QLabel("No profile selected.")
        self.lbl_info.setStyleSheet("color: #aaa; font-style: italic; margin-left: 10px;")
        layout.insertWidget(0, self.lbl_info)
        layout.insertStretch(1) 
        
        self.btn_fetch = self.ui.btn_run
        self.btn_fetch.setText("Lookup Profile")
        self.btn_fetch.clicked.connect(self.fetch_profile)
        self.btn_fetch.setEnabled(False)
        
        # Progress bar standard usage
        self.ui.progress_bar.setVisible(False)
        
        self.lbl_status = self.ui.lbl_status
        
        # Create tabs for Profile Info, Segments, and Events
        self.tabs = QTabWidget()
        self.ui.splitter.replaceWidget(1, self.tabs)
        
        # Tab 1: Profile Info
        self.profile_results = ResultsWidget()
        self.profile_results.setMinimumSize(400, 300)
        self.tabs.addTab(self.profile_results, "Profile Info")
        
        # Tab 2: Segments
        self.segments_results = ResultsWidget()
        self.segments_results.setMinimumSize(400, 300)
        self.tabs.addTab(self.segments_results, "Segments")
        
        # Tab 3: Events
        self.events_results = ResultsWidget()
        self.events_results.setMinimumSize(400, 300)
        self.tabs.addTab(self.events_results, "Events")

    def go_back(self):
        self.parent_task.load_config(None)

    def load_config(self, config):
        self.current_config = config
        
        self.profile_results.clear_data()
        self.segments_results.clear_data()
        self.events_results.clear_data()
        
        # Reset tab titles to default
        self.tabs.setTabText(0, "Profile Info")
        self.tabs.setTabText(1, "Segments")
        self.tabs.setTabText(2, "Events")
        
        self.lbl_status.setText("")
        self.loaded_data = None
        
        if not config:
            self.lbl_info.setText("Select a profile task to view.")
            self.btn_fetch.setEnabled(False)
            return
            
        name = config.get("name", "Unnamed")
        ns = config.get("namespace", "?")
        eid = config.get("entity_id", "?")
        ltype = config.get("lookup_type", "profile")
        
        type_label = {
            "events_only": "Experience Events Only",
            "both": "Profile + Experience Events",
        }.get(ltype, "Profile Only")
        self.lbl_info.setText(f"{name} ({ns}: {eid}) - {type_label}")
        self.btn_fetch.setEnabled(True)
        
        # Try to load persisted data
        self.load_persisted_data(config)

    def load_persisted_data(self, config):
        """Loads data from disk if available."""
        last_fetch = config.get("last_fetch")
        data_path = config.get("data_path")
        
        if last_fetch and data_path and os.path.exists(data_path):
            self.lbl_status.setText(f"Loaded data from: {last_fetch}")
            try:
                with open(data_path, 'r') as f:
                    data = json.load(f)
                    self.loaded_data = data
                    self.display_data(data)
            except Exception as e:
                logger.error(f"Failed to load profile data: {e}")
                
    def save_persisted_data(self, config, data):
        """Saves data to disk."""
        try:
            timestamp = int(datetime.datetime.now().timestamp())
            safe_name = "".join([c for c in config.get("name","profile") if c.isalnum() or c in ('-','_')])
            filename = f"{safe_name}_{timestamp}.json"
            
            # Directory
            app_data = os.path.join(os.environ.get('APPDATA', os.path.expanduser('~')), 'AEP_DataExplorer', 'profile_data')
            os.makedirs(app_data, exist_ok=True)
            
            full_path = os.path.join(app_data, filename)
            
            with open(full_path, 'w') as f:
                json.dump(data, f, indent=2) # Pretty print for manual inspection if needed
                
            return full_path
        except Exception as e:
            logger.error(f"Failed to save profile data: {e}")
            return None

    def fetch_profile(self):
        if not self.current_config: return
        
        ns = self.current_config.get("namespace")
        eid = self.current_config.get("entity_id")
        policy = self.current_config.get("merge_policy")
        ltype = self.current_config.get("lookup_type", "profile")
        
        if policy == "Default": policy = None
        
        # Do NOT normalize namespace here — pass it as-is to the API service,
        # which will apply the correct casing per call type (profile vs events).
        
        if not ns or not eid:
            QMessageBox.warning(self, "Invalid Config", "Namespace and Entity ID required.")
            return
            
        self.btn_fetch.setEnabled(False)
        self.btn_fetch.setText("Fetching...")
        self.profile_results.clear_data()
        self.segments_results.clear_data()
        self.events_results.clear_data()
        
        self.worker = ProfileWorker(eid, ns, policy, ltype)
        self.worker.finished.connect(self.on_fetch_success)
        self.worker.error.connect(self.on_fetch_error)
        self.worker.start()
        
    def on_fetch_success(self, data):
        self.btn_fetch.setEnabled(True)
        self.btn_fetch.setText("Lookup Profile")
        
        # Check for None (API error), but allow empty lists (valid for events)
        if data is None:
            QMessageBox.warning(self, "Not Found", "Profile/Events not found.")
            return
            
        # Update Timestamp & Save
        now = datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        
        if self.current_config:
            path = self.save_persisted_data(self.current_config, data)
            
            self.current_config["last_fetch"] = now
            self.current_config["data_path"] = path
            self.update_persistence_timestamp(self.current_config)

        self.ui.set_status(f"Fetch successful at {now}")
        self.display_data(data)

    def populate_events_tab(self, data):
        events_list = []
        if isinstance(data, list):
            events_list = data
        elif isinstance(data, dict) and "children" in data:
            events_list = data["children"]
        elif isinstance(data, dict):
            events_list = [data]
            
        self.events_results.clear_data()
        
        if events_list:
            try:
                try:
                    import pandas as pd
                    df = pd.json_normalize(events_list)
                    if df.shape[1] == 0 and len(events_list) > 0 and 'entity' in events_list[0]:
                        df = pd.json_normalize([e.get('entity', {}) for e in events_list])
                except Exception as norm_error:
                    from logger import logger
                    logger.error(f"json_normalize failed: {norm_error}, using DataFrame constructor")
                    df = pd.DataFrame(events_list)
                
                if df.empty or df.shape[1] == 0:
                    self.events_results.set_status("Event data loaded but has no displayable columns")
                    return
                
                self.events_results.load_data(df)
                self.events_results.show()
                self.events_results.update()
                
                self.tabs.setTabText(2, f"Events ({len(events_list)})")
                self.ui.set_status(f"Loaded {len(events_list)} events")
            except Exception as e:
                from logger import logger
                logger.error(f"Error loading events: {e}", exc_info=True)
                self.events_results.set_status(f"Error: {e}")
        else:
            self.events_results.set_status("No events found")
            self.tabs.setTabText(2, "Events (0)")

    def populate_profile_tab(self, data):
        entity = data
        if isinstance(data, dict) and "entity" in data:
            entity = data["entity"]
        elif isinstance(data, dict):
            for k, v in data.items():
                if isinstance(v, dict) and "entity" in v:
                    entity = v["entity"]
                    break
                    
        self.profile_results.clear_data()
        self.segments_results.clear_data()
                    
        if not entity:
            self.profile_results.set_status("No entity data found")
            return

        segments_data = entity.get("segmentMembership", {}) if isinstance(entity, dict) else {}
        
        flat_data = self.flatten_json(entity)
        if not flat_data and isinstance(entity, dict):
            import json
            flat_data = {"Raw JSON": json.dumps(entity, indent=2)}
            
        flat_data = {k: v for k, v in flat_data.items() if not k.startswith("segmentMembership")}
        
        import pandas as pd
        df_profile = pd.DataFrame(list(flat_data.items()), columns=["Field", "Value"])
        self.profile_results.load_data(df_profile)
        self.tabs.setTabText(0, f"Profile Info ({len(df_profile)})")
        
        segments_list = []
        for ns, segs in segments_data.items():
            for seg_id, details in segs.items():
                segments_list.append({
                    "Segment ID": seg_id,
                    "Status": details.get("status", "unknown"),
                    "Last Qualified": details.get("lastQualificationTime", ""),
                    "Namespace": ns
                })
        
        if segments_list:
            df_segments = pd.DataFrame(segments_list)
            self.segments_results.load_data(df_segments)
            self.tabs.setTabText(1, f"Segments ({len(segments_list)})")
        else:
            self.segments_results.set_status("No segment memberships")
            self.tabs.setTabText(1, "Segments (0)")
        
        self.ui.set_status(f"Loaded profile with {len(df_profile)} attributes and {len(segments_list)} segments")

    def display_data(self, data):
        """Parses and displays the data packet based on lookup type."""
        ltype = self.current_config.get("lookup_type", "profile")
        
        if ltype == "both":
            self.populate_profile_tab(data.get("profile", {}))
            self.populate_events_tab(data.get("events", []))
            self.tabs.setCurrentIndex(0)
        elif ltype == "events_only":
            self.populate_events_tab(data.get("events", []))
            self.tabs.setCurrentIndex(2)
        else:
            self.populate_profile_tab(data.get("profile", {}))
            self.tabs.setCurrentIndex(0)

    def flatten_json(self, y):
        out = {}
        def flatten(x, name=''):
            if isinstance(x, dict):
                for a in x:
                    flatten(x[a], name + a + '.')
            elif isinstance(x, list):
                for i, a in enumerate(x):
                    flatten(a, name + f'[{i}].')
            else:
                out[name[:-1]] = x
        flatten(y)
        return out

    def update_persistence_timestamp(self, config):
        tasks = persistence.load_profile_tasks()
        for i, t in enumerate(tasks):
             if t.get("name") == config.get("name"):
                 tasks[i] = config
                 persistence.save_profile_tasks(tasks)
                 break

    def on_fetch_error(self, msg):
        self.btn_fetch.setEnabled(True)
        self.btn_fetch.setText("Lookup Profile")
        QMessageBox.critical(self, "Error", f"Fetch failed: {msg}")

class TaskProfileWidget(QWidget):
    def __init__(self):
        super().__init__()
        self.layout = QVBoxLayout(self)
        self.layout.setContentsMargins(0, 0, 0, 0)
        
        self.stack = QStackedWidget()
        self.layout.addWidget(self.stack)
        
        # summary View
        self.summary = ProfileSummaryWidget(self)
        self.stack.addWidget(self.summary)
        
        # Detail View
        self.detail = ProfileDetailWidget(self)
        self.stack.addWidget(self.detail)
        
        self.stack.setCurrentWidget(self.summary)

    def load_config(self, config):
        if config:
            self.detail.load_config(config)
            self.stack.setCurrentWidget(self.detail)
        else:
            self.summary.refresh_data()
            self.stack.setCurrentWidget(self.summary)

class ProfileWorker(QThread):
    finished = Signal(object)  # Changed from dict to object to handle both dict and list
    error = Signal(str)
    
    def __init__(self, eid, ns, policy, ltype="profile"):
        super().__init__()
        self.eid = eid
        self.ns = ns
        self.policy = policy
        self.ltype = ltype
        self.service = AEPService()
        
    def run(self):
        try:
            if self.ltype == "both":
                prof = self.service.get_profile(self.eid, self.ns, self.policy, fetch_events=False)
                evts = self.service.get_profile(self.eid, self.ns, self.policy, fetch_events=True)
                data = {"profile": prof, "events": evts}
            elif self.ltype == "events_only":
                evts = self.service.get_profile(self.eid, self.ns, self.policy, fetch_events=True)
                data = {"events": evts}
            else:
                prof = self.service.get_profile(self.eid, self.ns, self.policy, fetch_events=False)
                data = {"profile": prof}
            self.finished.emit(data)
        except Exception as e:
            self.error.emit(str(e))

class MetadataWorker(QThread):
    finished = Signal(list, list) # policies, identities
    
    def run(self):
        service = AEPService()
        policies = []
        identities = []
        try:
            p_data = service.get_merge_policies()
            if isinstance(p_data, list):
                policies = p_data
        except Exception as e: 
            logger.error(f"Failed to fetch policies: {e}")
        
        try:
            i_data = service.get_identities()
            if isinstance(i_data, list):
                identities = i_data
        except Exception as e:
            logger.error(f"Failed to fetch identities: {e}")
        
        self.finished.emit(policies, identities)
