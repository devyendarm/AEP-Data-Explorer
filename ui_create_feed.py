from PySide6.QtWidgets import (QDialog, QVBoxLayout, QLabel, QLineEdit, 
                               QDialogButtonBox, QFormLayout, QSpinBox)

class CreateFeedDialog(QDialog):
    def __init__(self, parent=None):
        super().__init__(parent)
        self.setWindowTitle("Create New Datafeed")
        self.resize(500, 650)
        
        layout = QVBoxLayout(self)
        
        form_layout = QFormLayout()
        
        self.txt_name = QLineEdit()
        self.txt_name.setPlaceholderText("e.g., Monthly Sales Report")
        form_layout.addRow("Feed Name:", self.txt_name)
        
        # Method Selector (ComboBox)
        from PySide6.QtWidgets import QComboBox, QRadioButton, QButtonGroup, QTextEdit, QGroupBox
        self.combo_method = QComboBox()
        self.combo_method.addItems(["Query Service: Template", "Query Service: Direct SQL", "Data Pull: Dataset Download"])
        self.combo_method.currentIndexChanged.connect(self.toggle_mode)
        form_layout.addRow("Ingestion Method:", self.combo_method)
        
        # Template ID (Hidden if not Template)
        self.txt_template_id = QLineEdit()
        self.txt_template_id.setPlaceholderText("UUID")
        self.lbl_template_id = QLabel("Template ID:")
        form_layout.addRow(self.lbl_template_id, self.txt_template_id)
        
        # SQL Input (Visible if Direct SQL)
        from sql_highlighter import SqlHighlighter
        self.txt_sql = QTextEdit()
        self.txt_sql.setPlaceholderText("SELECT * FROM ...")
        self.txt_sql.setStyleSheet("font-family: Consolas, 'Courier New', monospace; font-size: 13px; color: #d4d4d4; background-color: #1e1e1e;")
        self.sql_highlighter = SqlHighlighter(self.txt_sql.document()) # Keep reference
        self.txt_sql.setVisible(False)
        self.lbl_sql = QLabel("SQL Query:")
        self.lbl_sql.setVisible(False)
        form_layout.addRow(self.lbl_sql, self.txt_sql)
        
        # Dataset ID (Target for Query, Source for Download)
        self.txt_dataset_id = QLineEdit()
        self.txt_dataset_id.setPlaceholderText("UUID")
        self.lbl_dataset_id = QLabel("Dataset ID:")
        form_layout.addRow(self.lbl_dataset_id, self.txt_dataset_id)

        # --- Batch Selection (Only for Dataset Download) ---
        self.batch_group_box = QGroupBox("Batch Selection")
        self.batch_group_box.setVisible(False)
        bg_layout = QVBoxLayout(self.batch_group_box)
        
        self.rb_latest = QRadioButton("Most Recent Batch")
        self.rb_custom = QRadioButton("Custom Batch ID")
        self.rb_latest.setChecked(True)
        
        self.bg_batch = QButtonGroup(self)
        self.bg_batch.addButton(self.rb_latest)
        self.bg_batch.addButton(self.rb_custom)
        
        self.txt_batch_id = QLineEdit()
        self.txt_batch_id.setPlaceholderText("Batch UUID")
        self.txt_batch_id.setVisible(False)
        
        self.rb_custom.toggled.connect(lambda c: self.txt_batch_id.setVisible(c))
        
        bg_layout.addWidget(self.rb_latest)
        bg_layout.addWidget(self.rb_custom)
        bg_layout.addWidget(self.txt_batch_id)
        
        form_layout.addRow(self.batch_group_box)
        
        # Poll Settings (Hidden if Dataset Download)
        self.spin_initial = QSpinBox()
        self.spin_initial.setRange(10, 3600)
        self.spin_initial.setValue(600)
        self.spin_initial.setSuffix(" sec")
        self.lbl_initial = QLabel("Initial Wait:")
        form_layout.addRow(self.lbl_initial, self.spin_initial)
        
        self.spin_subsequent = QSpinBox()
        self.spin_subsequent.setRange(5, 600)
        self.spin_subsequent.setValue(90)
        self.spin_subsequent.setSuffix(" sec")
        self.lbl_subsequent = QLabel("Poll Interval:")
        form_layout.addRow(self.lbl_subsequent, self.spin_subsequent)
        
        layout.addLayout(form_layout)
        
        # Buttons
        self.button_box = QDialogButtonBox(QDialogButtonBox.Ok | QDialogButtonBox.Cancel)
        self.button_box.accepted.connect(self.accept)
        self.button_box.rejected.connect(self.reject)
        layout.addWidget(self.button_box)
        
    def toggle_mode(self, index):
        # 0: Template, 1: Direct SQL, 2: Dataset Download
        
        self.lbl_template_id.setVisible(index == 0)
        self.txt_template_id.setVisible(index == 0)
        
        self.lbl_sql.setVisible(index == 1)
        self.txt_sql.setVisible(index == 1)
        
        self.batch_group_box.setVisible(index == 2)
        
        # Hide Poll settings for Dataset Download AND Direct SQL (both are now direct/synch-ish or manual)
        # 0: Template (Async Poll), 1: Direct SQL (Sync PG), 2: Dataset (Sync/Direct)
        show_poll = (index == 0)
        
        self.lbl_initial.setVisible(show_poll)
        self.spin_initial.setVisible(show_poll)
        self.lbl_subsequent.setVisible(show_poll)
        self.spin_subsequent.setVisible(show_poll)
        
        # Dataset ID field visibility
        # Template (0) -> Target Dataset ID
        # Dataset (2) -> Source Dataset ID
        # Direct (1) -> Hidden (Local output)
        
        show_dataset = (index != 1)
        self.lbl_dataset_id.setVisible(show_dataset)
        self.txt_dataset_id.setVisible(show_dataset)

        if index == 2:
            self.lbl_dataset_id.setText("Source Dataset ID:")
        else:
            self.lbl_dataset_id.setText("Target Dataset ID:")
        
    def get_data(self):
        idx = self.combo_method.currentIndex()
        feed_type = ["template", "direct", "dataset"][idx]
        
        batch_strategy = "latest"
        if self.rb_custom.isChecked():
            batch_strategy = "custom"
            
        return {
            "name": self.txt_name.text().strip(),
            "type": feed_type,
            "template_id": self.txt_template_id.text().strip() if idx == 0 else None,
            "sql_query": self.txt_sql.toPlainText().strip() if idx == 1 else None,
            "dataset_id": self.txt_dataset_id.text().strip(),
            "initial_poll_wait": self.spin_initial.value(),
            "subsequent_poll_wait": self.spin_subsequent.value(),
            # New fields
            "batch_strategy": batch_strategy,
            "custom_batch_id": self.txt_batch_id.text().strip() if batch_strategy == "custom" else None
        }

    def set_data(self, config):
        """Pre-fills the dialog with existing configuration."""
        if not config:
            return
            
        self.txt_name.setText(config.get("name", ""))
        self.txt_dataset_id.setText(config.get("dataset_id", ""))
        self.spin_initial.setValue(config.get("initial_poll_wait", 600))
        self.spin_subsequent.setValue(config.get("subsequent_poll_wait", 90))
        
        t = config.get("type", "template")
        idx = 0
        if t == "direct": idx = 1
        elif t == "dataset": idx = 2
        self.combo_method.setCurrentIndex(idx)
        
        if t == "direct":
            self.txt_sql.setPlainText(config.get("sql_query", ""))
        elif t == "template":
            self.txt_template_id.setText(config.get("template_id", ""))
            
        # Batch settings
        strategy = config.get("batch_strategy", "latest")
        if strategy == "custom":
            self.rb_custom.setChecked(True)
            self.txt_batch_id.setText(config.get("custom_batch_id", ""))
        else:
            self.rb_latest.setChecked(True)
            
        self.toggle_mode(idx)
        self.setWindowTitle("Edit Datafeed")
