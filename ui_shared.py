from PySide6.QtWidgets import (QWidget, QVBoxLayout, QHBoxLayout, QPushButton, 
                               QProgressBar, QLabel, QSplitter)
from PySide6.QtCore import Qt
from ui_results import ResultsWidget

class StandardTaskLayout(QWidget):
    """
    Shared layout component providing a consistent UI structure:
    - Top Toggle Strip (Collapsible)
    - Control Toolbar (Run, Progress, Status)
    - Results Widget (Table)
    """
    def __init__(self, parent=None):
        super().__init__(parent)
        
        self.layout = QVBoxLayout(self)
        self.layout.setContentsMargins(0, 0, 0, 0)
        self.layout.setSpacing(0)
        
        # 1. Top Header Strip (Toggle)
        self.header_strip = QWidget()
        self.header_strip.setFixedHeight(20)
        self.header_strip.setStyleSheet("background-color: #1e1e1e; border-bottom: 1px solid #333;")
        header_layout = QHBoxLayout(self.header_strip)
        header_layout.setContentsMargins(10, 0, 10, 0)
        header_layout.addStretch()
        
        self.btn_toggle = QPushButton("▲") 
        self.btn_toggle.setFixedSize(20, 20)
        self.btn_toggle.setToolTip("Hide Controls")
        self.btn_toggle.setCursor(Qt.PointingHandCursor)
        self.btn_toggle.setStyleSheet("border: none; background: transparent; color: #888; font-weight: bold;")
        self.btn_toggle.clicked.connect(self.toggle_controls)
        header_layout.addWidget(self.btn_toggle)
        
        self.layout.addWidget(self.header_strip)
        
        # 2. Splitter
        self.splitter = QSplitter(Qt.Vertical)
        self.splitter.setHandleWidth(5)
        self.splitter.setStyleSheet("""
            QSplitter::handle { background-color: #444; height: 5px; }
            QSplitter::handle:hover { background-color: #007acc; }
        """)
        
        # 3. Controls Container
        self.controls_widget = QWidget()
        self.controls_widget.setStyleSheet("background-color: #252526; border-bottom: 1px solid #333;")
        self.controls_layout = QHBoxLayout(self.controls_widget)
        self.controls_layout.setContentsMargins(10, 5, 10, 5)
        self.controls_layout.setSpacing(10)
        
        # Standard Elements (Subclasses can add more)
        # Run Button
        self.btn_run = QPushButton("Run")
        self.btn_run.setCursor(Qt.PointingHandCursor)
        self.btn_run.setFixedWidth(140)
        self.btn_run.setStyleSheet("""
            QPushButton { 
                background-color: #007acc; color: white; font-weight: bold; font-size: 13px; 
                border-radius: 4px; padding: 5px 10px; border: none;
            }
            QPushButton:hover { background-color: #005a9e; }
            QPushButton:pressed { background-color: #004578; }
            QPushButton:disabled { background-color: #333; color: #888; }
        """)
        self.controls_layout.addWidget(self.btn_run)
        
        # Progress Bar
        self.progress_bar = QProgressBar()
        self.progress_bar.setTextVisible(True)
        self.progress_bar.setFormat("%p% - Ready")
        self.progress_bar.setFixedWidth(200)
        self.progress_bar.setStyleSheet("""
            QProgressBar { 
                border: 1px solid #444; border-radius: 4px; text-align: center; 
                background-color: #1e1e1e; height: 18px; font-size: 11px; color: #ccc;
            } 
            QProgressBar::chunk { background-color: #007acc; }
        """)
        self.controls_layout.addWidget(self.progress_bar)
        
        # Status Label
        self.lbl_status = QLabel("Ready")
        self.lbl_status.setStyleSheet("color: #aaa; font-size: 12px; font-family: Segoe UI, sans-serif; margin-left: 10px;")
        self.controls_layout.addWidget(self.lbl_status, 1)
        
        self.splitter.addWidget(self.controls_widget)
        
        # 4. Results Widget
        self.results_widget = ResultsWidget()
        self.splitter.addWidget(self.results_widget)
        
        # Defaults
        self.splitter.setSizes([80, 800])
        self.splitter.setCollapsible(0, True)
        
        self.layout.addWidget(self.splitter)
        
    def toggle_controls(self):
        sizes = self.splitter.sizes()
        if sizes[0] > 0:
            self.last_height = sizes[0]
            self.splitter.setSizes([0, sizes[1] + sizes[0]])
            self.btn_toggle.setText("▼")
            self.btn_toggle.setToolTip("Show Controls")
        else:
            h = getattr(self, 'last_height', 80)
            if h == 0: h = 80
            self.splitter.setSizes([h, sizes[1] - h])
            self.btn_toggle.setText("▲")
            self.btn_toggle.setToolTip("Hide Controls")
            
    def set_status(self, text, error=False):
        self.lbl_status.setText(text)
        if error:
            self.lbl_status.setStyleSheet("color: #ff5555; font-size: 12px; margin-left: 10px;")
        else:
             self.lbl_status.setStyleSheet("color: #aaa; font-size: 12px; margin-left: 10px;")

    def set_progress(self, value, text=None):
        self.progress_bar.setValue(value)
        if text: self.progress_bar.setFormat(f"{value}% - {text}")
