"""
UI Dialog for creating/editing Segment Feeds

Allows users to configure segment feeds with:
- Feed Name
- Segment ID
- Namespace (optional)
"""

from PySide6.QtWidgets import (QDialog, QVBoxLayout, QHBoxLayout, QLabel, 
                               QLineEdit, QPushButton, QFormLayout, QMessageBox)
from PySide6.QtCore import Qt


class CreateSegmentFeedDialog(QDialog):
    """Dialog for creating or editing a Segment Feed configuration."""
    
    def __init__(self, parent=None, edit_mode=False, existing_config=None):
        super().__init__(parent)
        self.edit_mode = edit_mode
        self.existing_config = existing_config or {}
        
        self.setWindowTitle("Edit Segment Feed" if edit_mode else "Create Segment Feed")
        self.setModal(True)
        self.setMinimumWidth(500)
        
        self.setup_ui()
        
        if edit_mode and existing_config:
            self.load_existing_config()
    
    def setup_ui(self):
        layout = QVBoxLayout(self)
        layout.setSpacing(20)
        layout.setContentsMargins(30, 30, 30, 30)
        
        # Title
        title = QLabel("Edit Segment Feed" if self.edit_mode else "Create New Segment Feed")
        title.setStyleSheet("font-size: 18px; font-weight: bold; color: white;")
        layout.addWidget(title)
        
        # Form
        form_layout = QFormLayout()
        form_layout.setSpacing(15)
        form_layout.setLabelAlignment(Qt.AlignRight)
        
        # Feed Name
        self.txt_feed_name = QLineEdit()
        self.txt_feed_name.setPlaceholderText("e.g., High Value Customers")
        self.txt_feed_name.setStyleSheet("""
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
        
        # Segment ID
        self.txt_segment_id = QLineEdit()
        self.txt_segment_id.setPlaceholderText("e.g., 12345678-abcd-1234-abcd-123456789012")
        self.txt_segment_id.setStyleSheet("""
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
        
        # Namespace (Optional)
        self.txt_namespace = QLineEdit()
        self.txt_namespace.setPlaceholderText("e.g., ECID, email, crmId (Matches {namespace} in template)")
        self.txt_namespace.setStyleSheet("""
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
        
        form_layout.addRow("Feed Name:", self.txt_feed_name)
        form_layout.addRow("Segment ID:", self.txt_segment_id)
        form_layout.addRow("Identity Namespace:", self.txt_namespace)
        
        layout.addLayout(form_layout)
        
        # Info Label
        info_label = QLabel(
            "The Segment ID and Namespace will replace {segment_id} and {namespace} "
            "placeholders in your Segment Query Template (Settings)."
        )
        info_label.setStyleSheet("color: #999; font-size: 11px;")
        info_label.setWordWrap(True)
        layout.addWidget(info_label)
        
        # Buttons
        btn_layout = QHBoxLayout()
        btn_layout.addStretch()
        
        btn_cancel = QPushButton("Cancel")
        btn_cancel.setFixedWidth(100)
        btn_cancel.setCursor(Qt.PointingHandCursor)
        btn_cancel.setStyleSheet("""
            QPushButton {
                background-color: #6c757d;
                color: white;
                font-weight: bold;
                padding: 8px;
                border-radius: 4px;
            }
            QPushButton:hover { background-color: #5a6268; }
        """)
        btn_cancel.clicked.connect(self.reject)
        
        btn_save = QPushButton("Save" if self.edit_mode else "Create")
        btn_save.setFixedWidth(100)
        btn_save.setCursor(Qt.PointingHandCursor)
        btn_save.setStyleSheet("""
            QPushButton {
                background-color: #007acc;
                color: white;
                font-weight: bold;
                padding: 8px;
                border-radius: 4px;
            }
            QPushButton:hover { background-color: #0098ff; }
        """)
        btn_save.clicked.connect(self.save_feed)
        
        btn_layout.addWidget(btn_cancel)
        btn_layout.addWidget(btn_save)
        
        layout.addLayout(btn_layout)
    
    def load_existing_config(self):
        """Load existing configuration into form fields."""
        self.txt_feed_name.setText(self.existing_config.get("name", ""))
        self.txt_segment_id.setText(self.existing_config.get("segment_id", ""))
        self.txt_namespace.setText(self.existing_config.get("namespace", ""))
    
    def save_feed(self):
        """Validate and save the feed configuration."""
        feed_name = self.txt_feed_name.text().strip()
        segment_id = self.txt_segment_id.text().strip()
        namespace = self.txt_namespace.text().strip()
        
        # Validation
        if not feed_name:
            QMessageBox.warning(self, "Validation Error", "Feed Name is required.")
            return
        
        if not segment_id:
            QMessageBox.warning(self, "Validation Error", "Segment ID is required.")
            return
        
        # Store configuration
        self.feed_config = {
            "name": feed_name,
            "segment_id": segment_id,
            "namespace": namespace if namespace else None
        }
        
        self.accept()
    
    def get_config(self):
        """Return the configured feed settings."""
        return getattr(self, 'feed_config', None)
