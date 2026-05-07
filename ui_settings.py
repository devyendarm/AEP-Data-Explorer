from PySide6.QtWidgets import (QWidget, QVBoxLayout, QHBoxLayout, QLabel, QLineEdit, 
                               QPushButton, QFormLayout, QMessageBox, QFrame, QTextEdit, QScrollArea)
from PySide6.QtCore import Qt, Signal, QThread
import secure_store
import requests
from aep_query_service import AEPQueryService

class TestConnectionWorker(QThread):
    """Worker thread to test authentication without blocking UI."""
    success = Signal(str)  # Emits success message
    error = Signal(str)    # Emits error message
    
    def __init__(self, client_id, client_secret, org_id, sandbox_name):
        super().__init__()
        self.client_id = client_id
        self.client_secret = client_secret
        self.org_id = org_id
        self.sandbox_name = sandbox_name
    
    def run(self):
        """Attempt to get an access token with provided credentials."""
        try:
            url = "https://ims-na1.adobelogin.com/ims/token/v3"
            scopes = ["openid", "AdobeID", "session", "read_organizations", "additional_info.projectedProductContext"]
            scope_str = ",".join(scopes)
            
            data = {
                "grant_type": "client_credentials",
                "client_id": self.client_id,
                "client_secret": self.client_secret,
                "scope": scope_str
            }
            
            response = requests.post(url, data=data, timeout=10)
            response.raise_for_status()
            
            token_data = response.json()
            if "access_token" in token_data:
                self.success.emit("✅ Connection successful! Credentials are valid.")
            else:
                self.error.emit("❌ Unexpected response from Adobe IMS")
                
        except requests.exceptions.RequestException as e:
            error_msg = str(e)
            if hasattr(e, 'response') and e.response is not None:
                try:
                    error_detail = e.response.json()
                    error_msg = f"❌ Authentication failed: {error_detail.get('error_description', error_msg)}"
                except:
                    error_msg = f"❌ Authentication failed: {e.response.text[:200]}"
            self.error.emit(error_msg)
        except Exception as e:
            self.error.emit(f"❌ Connection error: {str(e)}")

class QueryServiceTestWorker(QThread):
    """Worker thread to test Query Service connection."""
    success = Signal(str)
    error = Signal(str)
    
    def __init__(self, host, port, db, user, password):
        super().__init__()
        self.host = host
        self.port = port
        self.db = db
        self.user = user
        self.password = password
        
    def run(self):
        try:
            qs = AEPQueryService(self.host, self.port, self.db, self.user, self.password)
            success, message = qs.test_connection()
            if success:
                self.success.emit(f"✅ {message}")
            else:
                self.error.emit(f"❌ {message}")
        except Exception as e:
            self.error.emit(f"❌ Connection error: {str(e)}")

class SettingsWidget(QWidget):
    credentials_saved = Signal()  # Signal to notify when credentials are updated
    
    DEFAULT_TEMPLATE = """SELECT
  {namespace},
  cast(key as STRING) AS segment_id,
  value.status AS segment_status,
  value.lastQualificationTime AS segment_lastQualificationTime
FROM
  (
    SELECT
      identityMap.{namespace}[0].id as {namespace},
      explode(segmentMembership.ups)
    FROM {profile_dataset}
      WHERE
        segmentMembership.ups['{segment_id}'].status is not null
        and identityMap.{namespace}[0].id is not null
  )
WHERE key = '{segment_id}'"""

    def __init__(self):
        super().__init__()
        
        # Main Layout (wrapper)
        main_layout = QVBoxLayout(self)
        main_layout.setContentsMargins(0, 0, 0, 0)
        
        # Scroll Area
        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        scroll.setFrameShape(QFrame.NoFrame)
        scroll.setStyleSheet("QScrollArea { background-color: transparent; border: none; }")
        
        # Content Widget
        content_widget = QWidget()
        content_widget.setStyleSheet("background-color: transparent;")
        
        # Form Layout (applied to content widget)
        self.layout = QVBoxLayout(content_widget)
        self.layout.setContentsMargins(40, 40, 40, 40)
        self.layout.setSpacing(20)
        
        scroll.setWidget(content_widget)
        main_layout.addWidget(scroll)
        
        # Title
        lbl_title = QLabel("Settings & Authentication")
        lbl_title.setStyleSheet("font-size: 24px; font-weight: bold; color: white; margin-bottom: 20px;")
        self.layout.addWidget(lbl_title)
        
        # === IMS Section ===
        form_frame = QFrame()
        form_frame.setStyleSheet("""
            QFrame { background-color: #252526; border-radius: 8px; border: 1px solid #333; }
            QLabel { color: #cccccc; font-size: 14px; }
            QLineEdit { 
                background-color: #333333; 
                color: white; 
                border: 1px solid #444; 
                padding: 8px; 
                border-radius: 4px;
                font-size: 13px;
            }
            QLineEdit:focus { border: 1px solid #007acc; }
        """)
        form_layout = QFormLayout(form_frame)
        form_layout.setContentsMargins(30, 30, 30, 30)
        form_layout.setSpacing(20)
        form_layout.setLabelAlignment(Qt.AlignRight)
        
        # Inputs
        self.txt_client_id = QLineEdit()
        self.txt_client_id.setPlaceholderText("Enter Client ID (API Key)")
        self.txt_client_id.setMinimumWidth(400)
        
        self.txt_client_secret = QLineEdit()
        self.txt_client_secret.setEchoMode(QLineEdit.Password)
        self.txt_client_secret.setPlaceholderText("Enter Client Secret")
        
        self.txt_org_id = QLineEdit()
        self.txt_org_id.setPlaceholderText("e.g. 12345678W@AdobeOrg")
        
        self.txt_sandbox = QLineEdit()
        self.txt_sandbox.setPlaceholderText("e.g. prod")
        self.txt_sandbox.setText("prod") # Default
        
        # Add Rows
        form_layout.addRow("Client ID:", self.txt_client_id)
        form_layout.addRow("Client Secret:", self.txt_client_secret)
        form_layout.addRow("Org ID:", self.txt_org_id)
        form_layout.addRow("Sandbox Name:", self.txt_sandbox)
        
        # IMS Buttons
        ims_btn_layout = QHBoxLayout()
        self.btn_test_ims = QPushButton("Test IMS Connection")
        self.btn_test_ims.setStyleSheet(self._get_button_style("#6c757d"))
        self.btn_test_ims.clicked.connect(self.test_ims_connection)
        
        self.btn_save_ims = QPushButton("Save IMS Config")
        self.btn_save_ims.setStyleSheet(self._get_button_style("#007acc"))
        self.btn_save_ims.clicked.connect(self.save_ims)
        
        ims_btn_layout.addWidget(self.btn_test_ims)
        ims_btn_layout.addWidget(self.btn_save_ims)
        form_layout.addRow("", ims_btn_layout)
        
        self.layout.addWidget(form_frame)
        
        # === Query Service Section ===
        qs_title = QLabel("Query Service Credentials (Optional)")
        qs_title.setStyleSheet("font-size: 18px; font-weight: bold; color: white; margin-top: 20px; margin-bottom: 10px;")
        self.layout.addWidget(qs_title)
        
        qs_frame = QFrame()
        qs_frame.setStyleSheet("""
            QFrame { background-color: #252526; border-radius: 8px; border: 1px solid #333; }
            QLabel { color: #cccccc; font-size: 14px; }
            QLineEdit { 
                background-color: #333333; 
                color: white; 
                border: 1px solid #444; 
                padding: 8px; 
                border-radius: 4px;
                font-size: 13px;
            }
            QLineEdit:focus { border: 1px solid #007acc; }
        """)
        qs_layout = QFormLayout(qs_frame)
        qs_layout.setContentsMargins(30, 30, 30, 30)
        qs_layout.setSpacing(20)
        qs_layout.setLabelAlignment(Qt.AlignRight)
        
        # Query Service Inputs
        self.txt_qs_host = QLineEdit()
        self.txt_qs_host.setPlaceholderText("e.g., {ORG_ID}.platform-query.adobe.io")
        self.txt_qs_host.setMinimumWidth(400)
        
        self.txt_qs_port = QLineEdit()
        self.txt_qs_port.setPlaceholderText("80")
        self.txt_qs_port.setText("80")
        self.txt_qs_port.setMaximumWidth(100)
        
        self.txt_qs_database = QLineEdit()
        self.txt_qs_database.setPlaceholderText("prod:all")
        self.txt_qs_database.setText("prod:all")
        
        self.txt_qs_username = QLineEdit()
        self.txt_qs_username.setPlaceholderText("Technical account username")
        
        self.txt_qs_password = QLineEdit()
        self.txt_qs_password.setEchoMode(QLineEdit.Password)
        self.txt_qs_password.setPlaceholderText("Query Service password")
        
        self.txt_qs_profile_dataset = QLineEdit()
        self.txt_qs_profile_dataset.setPlaceholderText("Profile dataset name (for segment queries)")
        
        # Add Query Service Rows
        qs_layout.addRow("Host:", self.txt_qs_host)
        qs_layout.addRow("Port:", self.txt_qs_port)
        qs_layout.addRow("Database:", self.txt_qs_database)
        qs_layout.addRow("Username:", self.txt_qs_username)
        qs_layout.addRow("Password:", self.txt_qs_password)
        qs_layout.addRow("Profile Dataset:", self.txt_qs_profile_dataset)
        
        # QS Buttons
        qs_btn_layout = QHBoxLayout()
        self.btn_test_qs = QPushButton("Test Query Service")
        self.btn_test_qs.setStyleSheet(self._get_button_style("#6c757d"))
        self.btn_test_qs.clicked.connect(self.test_qs_connection)
        
        self.btn_save_qs = QPushButton("Save Query Service")
        self.btn_save_qs.setStyleSheet(self._get_button_style("#007acc"))
        self.btn_save_qs.clicked.connect(self.save_qs)
        
        qs_btn_layout.addWidget(self.btn_test_qs)
        qs_btn_layout.addWidget(self.btn_save_qs)
        qs_layout.addRow("", qs_btn_layout)
        
        self.layout.addWidget(qs_frame)
        
        # === Segment Query Template Section ===
        template_title = QLabel("Segment Query Template")
        template_title.setStyleSheet("font-size: 18px; font-weight: bold; color: white; margin-top: 20px; margin-bottom: 10px;")
        self.layout.addWidget(template_title)
        
        template_desc = QLabel("Define the SQL query template for segment member queries. Use {segment_id} for the Segment ID and {namespace} for the Identity Namespace.")
        template_desc.setStyleSheet("font-size: 12px; color: #999; margin-bottom: 10px;")
        template_desc.setWordWrap(True)
        self.layout.addWidget(template_desc)
        
        template_frame = QFrame()
        template_frame.setStyleSheet("""
            QFrame { background-color: #252526; border-radius: 8px; border: 1px solid #333; }
            QTextEdit { 
                background-color: #1e1e1e; 
                color: #d4d4d4; 
                border: 1px solid #444; 
                padding: 10px; 
                border-radius: 4px;
                font-family: 'Consolas', 'Courier New', monospace;
                font-size: 12px;
            }
            QTextEdit:focus { border: 1px solid #007acc; }
        """)
        template_layout = QVBoxLayout(template_frame)
        template_layout.setContentsMargins(20, 20, 20, 20)
        
        self.txt_segment_query_template = QTextEdit()
        self.txt_segment_query_template.setPlaceholderText(
            self.DEFAULT_TEMPLATE.replace("{segment_id}", "ExampleSegmentID").replace("{namespace}", "ExampleNamespace")
        )
        self.txt_segment_query_template.setMinimumHeight(150)
        
        # Set default template from class constant
        self.txt_segment_query_template.setPlainText(self.DEFAULT_TEMPLATE)
        
        template_layout.addWidget(self.txt_segment_query_template)
        
        # Template Buttons
        tpl_btn_layout = QHBoxLayout()
        
        self.btn_reset_template = QPushButton("Reset Default")
        self.btn_reset_template.setStyleSheet(self._get_button_style("#d32f2f"))
        self.btn_reset_template.clicked.connect(self.reset_template)
        
        self.btn_save_template = QPushButton("Save Template")
        self.btn_save_template.setStyleSheet(self._get_button_style("#007acc"))
        self.btn_save_template.clicked.connect(self.save_template)
        
        tpl_btn_layout.addStretch()
        tpl_btn_layout.addWidget(self.btn_reset_template)
        tpl_btn_layout.addWidget(self.btn_save_template)
        
        template_layout.addLayout(tpl_btn_layout)
        
        self.layout.addWidget(template_frame)
        
        # Status Label
        self.lbl_status = QLabel("")
        self.lbl_status.setAlignment(Qt.AlignCenter)
        self.layout.addWidget(self.lbl_status)
        self.layout.addStretch()
        
        # Load Existing if available
        self.load_current_settings()

    def reset_template(self):
        """Reset segment query template to default."""
        self.txt_segment_query_template.setPlainText(self.DEFAULT_TEMPLATE)
        self.lbl_status.setText("Template reset to default (unsaved).")
        self.lbl_status.setStyleSheet("color: #ffa500;")

    def _get_button_style(self, color):
        return f"""
            QPushButton {{ 
                background-color: {color}; 
                color: white; 
                font-weight: bold; 
                padding: 8px 15px; 
                border-radius: 4px; 
                font-size: 13px; 
            }}
            QPushButton:hover {{ background-color: {color}dd; }}
            QPushButton:disabled {{ background-color: #3a3a3a; color: #666; }}
        """

    def load_current_settings(self):
        creds = secure_store.load_credentials()
        if creds:
            self.txt_client_id.setText(creds.get("client_id", ""))
            self.txt_client_secret.setText(creds.get("client_secret", ""))
            self.txt_org_id.setText(creds.get("org_id", ""))
            self.txt_sandbox.setText(creds.get("sandbox_name", "prod"))
            
            # Load Query Service credentials if available
            qs_creds = creds.get("query_service", {})
            self.txt_qs_host.setText(qs_creds.get("host", ""))
            self.txt_qs_port.setText(str(qs_creds.get("port", 80)))
            self.txt_qs_database.setText(qs_creds.get("database", "prod:all"))
            self.txt_qs_username.setText(qs_creds.get("username", ""))
            self.txt_qs_password.setText(qs_creds.get("password", ""))
            self.txt_qs_profile_dataset.setText(qs_creds.get("profile_dataset", ""))
            
            # Load Segment Query Template if available
            segment_template = creds.get("segment_query_template", "")
            if segment_template and segment_template.strip():
                self.txt_segment_query_template.setPlainText(segment_template)
            else:
                self.txt_segment_query_template.setPlainText(self.DEFAULT_TEMPLATE)
            
            self.lbl_status.setText("Loaded saved credentials.")
            self.lbl_status.setStyleSheet("color: #4caf50;")
            
    def test_ims_connection(self):
        """Test credentials without saving."""
        client_id = self.txt_client_id.text().strip()
        secret = self.txt_client_secret.text().strip()
        org_id = self.txt_org_id.text().strip()
        sandbox = self.txt_sandbox.text().strip()
        
        if not all([client_id, secret, org_id, sandbox]):
            QMessageBox.warning(self, "Validation Error", "All fields are required to test connection.")
            return
        
        # Disable buttons
        self.btn_test_ims.setEnabled(False)
        self.btn_test_ims.setText("Testing...")
        self.lbl_status.setText("Testing connection to Adobe IMS...")
        self.lbl_status.setStyleSheet("color: #ffa500;")
        
        # Create and start worker thread
        self.ims_worker = TestConnectionWorker(client_id, secret, org_id, sandbox)
        self.ims_worker.success.connect(lambda msg: self.on_test_result(True, msg, self.btn_test_ims, "Test IMS Connection"))
        self.ims_worker.error.connect(lambda msg: self.on_test_result(False, msg, self.btn_test_ims, "Test IMS Connection"))
        self.ims_worker.start()

    def test_qs_connection(self):
        """Test Query Service connection."""
        host = self.txt_qs_host.text().strip()
        port = int(self.txt_qs_port.text().strip() or 80)
        db = self.txt_qs_database.text().strip()
        user = self.txt_qs_username.text().strip()
        password = self.txt_qs_password.text().strip()
        
        if not all([host, user, password]):
            QMessageBox.warning(self, "Validation Error", "Host, Username, and Password are required.")
            return
            
        self.btn_test_qs.setEnabled(False)
        self.btn_test_qs.setText("Testing...")
        self.lbl_status.setText("Connecting to Query Service...")
        self.lbl_status.setStyleSheet("color: #ffa500;")
        
        self.qs_worker = QueryServiceTestWorker(host, port, db, user, password)
        self.qs_worker.success.connect(lambda msg: self.on_test_result(True, msg, self.btn_test_qs, "Test Query Service"))
        self.qs_worker.error.connect(lambda msg: self.on_test_result(False, msg, self.btn_test_qs, "Test Query Service"))
        self.qs_worker.start()
        
    def on_test_result(self, success, message, button, button_text):
        button.setEnabled(True)
        button.setText(button_text)
        self.lbl_status.setText(message)
        self.lbl_status.setStyleSheet("color: #4caf50;" if success else "color: #f44336;")
        if success:
            QMessageBox.information(self, "Success", message)
        else:
            QMessageBox.critical(self, "Connection Failed", message)

    def _collect_all_data(self):
        """Collects all data from UI for saving."""
        qs_host = self.txt_qs_host.text().strip()
        qs_port = self.txt_qs_port.text().strip()
        
        query_service = None
        if qs_host:
            query_service = {
                "host": qs_host,
                "port": int(qs_port) if qs_port else 80,
                "database": self.txt_qs_database.text().strip(),
                "username": self.txt_qs_username.text().strip(),
                "password": self.txt_qs_password.text().strip(),
                "profile_dataset": self.txt_qs_profile_dataset.text().strip()
            }
            
        return {
            "client_id": self.txt_client_id.text().strip(),
            "secret": self.txt_client_secret.text().strip(),
            "org_id": self.txt_org_id.text().strip(),
            "sandbox": self.txt_sandbox.text().strip(),
            "query_service": query_service,
            "segment_template": self.txt_segment_query_template.toPlainText().strip()
        }

    def save_ims(self):
        data = self._collect_all_data()
        if not all([data["client_id"], data["secret"], data["org_id"], data["sandbox"]]):
            QMessageBox.warning(self, "Validation Error", "All IMS fields are required.")
            return
        self._perform_save(data, "IMS Credentials saved!")

    def save_qs(self):
        data = self._collect_all_data()
        # QS is optional, but if saving explicitly, check host
        if not data["query_service"] or not data["query_service"]["host"]:
             QMessageBox.warning(self, "Validation Error", "Host is required for Query Service.")
             return
        self._perform_save(data, "Query Service Credentials saved!")

    def save_template(self):
        data = self._collect_all_data()
        self._perform_save(data, "Template saved!")

    def _perform_save(self, data, success_msg):
        if secure_store.save_credentials(
            data["client_id"], data["secret"], data["org_id"], data["sandbox"],
            data["query_service"], data["segment_template"]
        ):
            self.credentials_saved.emit()
            QMessageBox.information(self, "Success", success_msg)
            self.lbl_status.setText(success_msg)
            self.lbl_status.setStyleSheet("color: #4caf50;")
        else:
            QMessageBox.critical(self, "Error", "Failed to save credentials.")

