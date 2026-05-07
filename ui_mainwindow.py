from PySide6.QtWidgets import (QMainWindow, QWidget, QVBoxLayout, QHBoxLayout, 
                               QStackedWidget, QLabel, QStatusBar, QPushButton, QTreeWidget,
                               QTreeWidgetItem, QMessageBox, QMenu, QInputDialog)
from ui_create_feed import CreateFeedDialog
from ui_task_ingest import IngestionConfigDialog
import persistence
from PySide6.QtCore import Qt, QSize
from PySide6.QtGui import QIcon
from auth import AEPAuthHandler
from logger import logger
import os
import sys

# Import Task Widgets
from ui_task_pull import TaskPullWidget
from ui_task_ingest import TaskIngestWidget
from ui_task_validate import TaskValidateWidget
from ui_task_profile import TaskProfileWidget, ProfileConfigDialog
from ui_task_profile import TaskProfileWidget, ProfileConfigDialog
from ui_task_segments import TaskSegmentsWidget
from ui_create_segment_feed import CreateSegmentFeedDialog
from ui_task_workflow import TaskWorkflowWidget
from ui_settings import SettingsWidget

class MainWindow(QMainWindow):
    def __init__(self):
        super().__init__()
        self.setWindowTitle("AEP Data Explorer")
        
        # Icon Loading Helper
        def resource_path(relative_path):
             try: base_path = sys._MEIPASS
             except Exception: base_path = os.path.abspath(".")
             return os.path.join(base_path, relative_path)

        self.setWindowIcon(QIcon(resource_path("app_icon.png")))
        self.resize(1200, 800)
        
        # Initialize Auth
        self.auth = AEPAuthHandler()
        
        # Central Widget
        central_widget = QWidget()
        self.setCentralWidget(central_widget)
        
        # Main Layout (Horizontal: Sidebar | Content)
        from PySide6.QtWidgets import QSplitter
        main_layout = QHBoxLayout(central_widget)
        main_layout.setContentsMargins(0, 0, 0, 0)
        main_layout.setSpacing(0)
        
        self.main_splitter = QSplitter(Qt.Horizontal)
        self.main_splitter.setHandleWidth(5) # Standard handle width
        self.main_splitter.setStyleSheet("""
            QSplitter::handle { 
                background-color: #555555; 
                image: none;
                margin: 0px 2px;
            }
            QSplitter::handle:hover {
                background-color: #007acc;
            }
        """)

        # --- Sidebar Container ---
        self.sidebar_container = QWidget()
        self.sidebar_container.setStyleSheet("background-color: #252526;") # Ensure consistent background
        sidebar_layout = QVBoxLayout(self.sidebar_container)
        sidebar_layout.setContentsMargins(0, 0, 0, 0)
        sidebar_layout.setSpacing(0)
        
        # Sidebar Header (Title only)
        sidebar_header = QWidget()
        sidebar_header.setStyleSheet("background-color: #252526;")
        sidebar_header_layout = QHBoxLayout(sidebar_header)
        sidebar_header_layout.setContentsMargins(10, 10, 10, 10)
        
        # App Logo/Title
        self.lbl_app_logo = QLabel("AEP Data Explorer")
        self.lbl_app_logo.setStyleSheet("color: white; font-weight: bold; font-size: 14px;")
        
        # Collapse Button (Small Arrow)
        self.btn_collapse_sidebar = QPushButton("<<")
        self.btn_collapse_sidebar.setFixedWidth(30)
        self.btn_collapse_sidebar.setCursor(Qt.PointingHandCursor)
        self.btn_collapse_sidebar.setStyleSheet("background: transparent; color: #aaa; font-weight: bold;")
        self.btn_collapse_sidebar.clicked.connect(self.toggle_sidebar)
        
        sidebar_header_layout.addWidget(self.lbl_app_logo)
        sidebar_header_layout.addStretch()
        sidebar_header_layout.addWidget(self.btn_collapse_sidebar)
        
        sidebar_layout.addWidget(sidebar_header)
        
        # --- Sidebar Tree Widget ---
        self.sidebar = QTreeWidget()
        self.sidebar.setHeaderHidden(True)
        self.sidebar.itemClicked.connect(self.on_sidebar_clicked)
        self.sidebar.setStyleSheet("border: none; background-color: #252526;")
        self.sidebar.setUniformRowHeights(False)  # Allow custom row heights
        self.sidebar.setIndentation(10)
        self.sidebar.setContextMenuPolicy(Qt.CustomContextMenu)
        self.sidebar.customContextMenuRequested.connect(self.show_context_menu)
        self.sidebar.setVerticalScrollBarPolicy(Qt.ScrollBarAlwaysOff)
        self.sidebar.setHorizontalScrollBarPolicy(Qt.ScrollBarAlwaysOff)
        
        sidebar_layout.addWidget(self.sidebar, 1)
        
        # 1. Datafeeds Section
        self.item_feeds = QTreeWidgetItem(self.sidebar)
        self.item_feeds.setExpanded(True)
        self.item_feeds.setSizeHint(0, QSize(200, 35)) # Compact size
        
        # Custom Widget for Datafeeds Item (Label + Icon Button)
        feed_widget = QWidget()
        fw_layout = QHBoxLayout(feed_widget)
        fw_layout.setContentsMargins(0, 0, 10, 0) # Adjusted right margin to 10 to prevent overlap
        
        lbl_feeds = QLabel("Datafeeds")
        lbl_feeds.setStyleSheet("color: #ccc; font-weight: bold; font-size: 14px; background: transparent;")
        
        # Plus Button with Icon
        btn_add = QPushButton()
        btn_add.setFixedSize(24, 24)
        btn_add.setCursor(Qt.PointingHandCursor)
        btn_add.setIcon(QIcon(resource_path("icon_plus.png")))
        btn_add.setIconSize(QSize(16, 16)) # Slightly smaller icon inside button for padding
        btn_add.setStyleSheet("border: none; background: transparent;")
        btn_add.clicked.connect(self.create_new_feed)
        
        fw_layout.addWidget(lbl_feeds)
        fw_layout.addStretch()
        fw_layout.addWidget(btn_add)
        
        self.sidebar.setItemWidget(self.item_feeds, 0, feed_widget)
        
        # 2. Ingestion Section
        self.item_ingest = QTreeWidgetItem(self.sidebar)
        self.item_ingest.setExpanded(True)
        self.item_ingest.setSizeHint(0, QSize(200, 35))
        
        ingest_widget = QWidget()
        iw_layout = QHBoxLayout(ingest_widget)
        iw_layout.setContentsMargins(0, 0, 10, 0)
        
        lbl_ingest = QLabel("Ingestion")
        lbl_ingest.setStyleSheet("color: #ccc; font-weight: bold; font-size: 14px; background: transparent;")
        
        btn_add_ingest = QPushButton()
        btn_add_ingest.setFixedSize(24, 24)
        btn_add_ingest.setCursor(Qt.PointingHandCursor)
        btn_add_ingest.setIcon(QIcon(resource_path("icon_plus.png")))
        btn_add_ingest.setIconSize(QSize(16, 16))
        btn_add_ingest.setStyleSheet("border: none; background: transparent;")
        btn_add_ingest.clicked.connect(self.create_new_ingestion_task)
        
        iw_layout.addWidget(lbl_ingest)
        iw_layout.addStretch()
        iw_layout.addWidget(btn_add_ingest)
        
        self.sidebar.setItemWidget(self.item_ingest, 0, ingest_widget)

        
        # 3. Local Queries Section
        self.item_queries = QTreeWidgetItem(self.sidebar)
        self.item_queries.setExpanded(True)
        self.item_queries.setSizeHint(0, QSize(200, 35))
        
        query_widget = QWidget()
        qw_layout = QHBoxLayout(query_widget)
        qw_layout.setContentsMargins(0, 0, 10, 0)
        
        lbl_queries = QLabel("Local Queries")
        lbl_queries.setStyleSheet("color: #ccc; font-weight: bold; font-size: 14px; background: transparent;")
        
        btn_add_query = QPushButton()
        btn_add_query.setFixedSize(24, 24)
        btn_add_query.setCursor(Qt.PointingHandCursor)
        btn_add_query.setIcon(QIcon(resource_path("icon_plus.png")))
        btn_add_query.setIconSize(QSize(16, 16))
        btn_add_query.setStyleSheet("border: none; background: transparent;")
        btn_add_query.clicked.connect(self.create_new_local_query)
        
        qw_layout.addWidget(lbl_queries)
        qw_layout.addStretch()
        qw_layout.addWidget(btn_add_query)
        
        self.sidebar.setItemWidget(self.item_queries, 0, query_widget)
        
        # 4. Profile Lookup Section
        self.item_profiles = QTreeWidgetItem(self.sidebar)
        self.item_profiles.setExpanded(True)
        self.item_profiles.setSizeHint(0, QSize(200, 35))
        
        profile_widget = QWidget()
        pw_layout = QHBoxLayout(profile_widget)
        pw_layout.setContentsMargins(0, 0, 10, 0)
        
        lbl_profiles = QLabel("Profile Lookup")
        lbl_profiles.setStyleSheet("color: #ccc; font-weight: bold; font-size: 14px; background: transparent;")
        
        btn_add_profile = QPushButton()
        btn_add_profile.setFixedSize(24, 24)
        btn_add_profile.setCursor(Qt.PointingHandCursor)
        btn_add_profile.setIcon(QIcon(resource_path("icon_plus.png")))
        btn_add_profile.setIconSize(QSize(16, 16))
        btn_add_profile.setStyleSheet("border: none; background: transparent;")
        btn_add_profile.clicked.connect(self.create_new_profile_task)
        
        pw_layout.addWidget(lbl_profiles)
        pw_layout.addStretch()
        pw_layout.addWidget(btn_add_profile)
        
        self.sidebar.setItemWidget(self.item_profiles, 0, profile_widget)
        
        # 5. Segments Section
        self.item_segments = QTreeWidgetItem(self.sidebar)
        self.item_segments.setExpanded(True)
        self.item_segments.setSizeHint(0, QSize(200, 35))
        
        segments_widget = QWidget()
        sw_layout = QHBoxLayout(segments_widget)
        sw_layout.setContentsMargins(0, 0, 10, 0)
        
        lbl_segments = QLabel("Segments")
        lbl_segments.setStyleSheet("color: #ccc; font-weight: bold; font-size: 14px; background: transparent;")
        
        btn_add_segment = QPushButton()
        btn_add_segment.setFixedSize(24, 24)
        btn_add_segment.setCursor(Qt.PointingHandCursor)
        btn_add_segment.setIcon(QIcon(resource_path("icon_plus.png")))
        btn_add_segment.setIconSize(QSize(16, 16))
        btn_add_segment.setStyleSheet("border: none; background: transparent;")
        btn_add_segment.clicked.connect(self.create_new_segment_task)
        
        sw_layout.addWidget(lbl_segments)
        sw_layout.addStretch()
        sw_layout.addWidget(btn_add_segment)
        
        self.sidebar.setItemWidget(self.item_segments, 0, segments_widget)
        
        # 6. Workflows Section
        self.item_workflows = QTreeWidgetItem(self.sidebar)
        self.item_workflows.setExpanded(True)
        self.item_workflows.setSizeHint(0, QSize(200, 35))
        
        workflows_widget = QWidget()
        ww_layout = QHBoxLayout(workflows_widget)
        ww_layout.setContentsMargins(0, 0, 10, 0)
        
        lbl_workflows = QLabel("Workflows")
        lbl_workflows.setStyleSheet("color: #ccc; font-weight: bold; font-size: 14px; background: transparent;")
        
        btn_add_workflow = QPushButton()
        btn_add_workflow.setFixedSize(24, 24)
        btn_add_workflow.setCursor(Qt.PointingHandCursor)
        btn_add_workflow.setIcon(QIcon(resource_path("icon_plus.png")))
        btn_add_workflow.setIconSize(QSize(16, 16))
        btn_add_workflow.setStyleSheet("border: none; background: transparent;")
        btn_add_workflow.clicked.connect(self.create_new_workflow)
        
        ww_layout.addWidget(lbl_workflows)
        ww_layout.addStretch()
        ww_layout.addWidget(btn_add_workflow)
        
        self.sidebar.setItemWidget(self.item_workflows, 0, workflows_widget)
        
        # sidebar_layout.addStretch() # Removed to allow tree to expand
        
        # Bottom Settings Button
        self.btn_settings = QPushButton("  Settings")
        self.btn_settings.setIcon(QIcon(resource_path("icon_plus.png"))) # Placeholder icon
        self.btn_settings.setStyleSheet("""
            QPushButton {
                color: #ccc;
                font-weight: bold;
                font-size: 14px;
                background-color: transparent;
                text-align: left;
                padding: 5px;
                border: none;
            }
            QPushButton:hover {
                background-color: #333;
                color: white;
            }
        """)
        self.btn_settings.setCursor(Qt.PointingHandCursor)
        self.btn_settings.clicked.connect(self.open_settings)
        
        sidebar_layout.addWidget(self.btn_settings)

        # --- Right Content Container ---
        right_container = QWidget()
        right_layout = QVBoxLayout(right_container)
        right_layout.setContentsMargins(0, 0, 0, 0)
        right_layout.setSpacing(0)
        
        # Global Toolbar (Content Header)
        content_header = QWidget()
        content_header.setFixedHeight(50)
        content_header.setStyleSheet("background-color: #1e1e1e; border-bottom: 1px solid #333;")
        ch_layout = QHBoxLayout(content_header)
        ch_layout.setContentsMargins(10, 0, 10, 0)
        
        # Expand Sidebar Button (Visible only when sidebar hidden)
        self.btn_expand_sidebar = QPushButton(">>")
        self.btn_expand_sidebar.setFixedWidth(30)
        self.btn_expand_sidebar.setCursor(Qt.PointingHandCursor)
        self.btn_expand_sidebar.setStyleSheet("background: transparent; color: #aaa; font-weight: bold;")
        self.btn_expand_sidebar.clicked.connect(self.toggle_sidebar)
        self.btn_expand_sidebar.setVisible(False) # Initially hidden
        
        ch_layout.addWidget(self.btn_expand_sidebar)
        
        # Page Title
        self.lbl_page_title = QLabel("Datafeeds")
        self.lbl_page_title.setStyleSheet("color: white; font-size: 16px; font-weight: bold; margin-left: 10px;")
        ch_layout.addWidget(self.lbl_page_title)
        
        ch_layout.addStretch()
        
        # Auth Status
        self.auth_status = QLabel("Checking Auth...")
        self.auth_status.setStyleSheet("color: #888888; font-weight: bold;")
        ch_layout.addWidget(self.auth_status)
        
        right_layout.addWidget(content_header)
        
        # Stacked Widget
        self.content_stack = QStackedWidget()
        right_layout.addWidget(self.content_stack)
        
        # Add Containers to Splitter
        self.main_splitter.addWidget(self.sidebar_container)
        self.main_splitter.addWidget(right_container)
        
        # Set initial sizes (Sidebar: 250, Content: Remaining)
        self.main_splitter.setSizes([250, 950])
        self.main_splitter.setCollapsible(0, True) # Allow sidebar to collapse completely
        
        main_layout.addWidget(self.main_splitter)
        
        # --- Initialize Tasks ---
        self.task_pull = TaskPullWidget()
        self.task_ingest = TaskIngestWidget()
        self.task_validate = TaskValidateWidget()
        self.task_profile = TaskProfileWidget()
        self.task_segments = TaskSegmentsWidget()
        self.task_workflows = TaskWorkflowWidget()
        self.task_settings = SettingsWidget()
        
        self.content_stack.addWidget(self.task_pull)
        self.content_stack.addWidget(self.task_ingest)
        self.content_stack.addWidget(self.task_validate)
        self.content_stack.addWidget(self.task_profile)
        self.content_stack.addWidget(self.task_segments)
        self.content_stack.addWidget(self.task_workflows)
        self.content_stack.addWidget(self.task_settings)
        
        # Connect Settings Signal
        self.task_settings.credentials_saved.connect(self.on_credentials_updated)
        
        # Status Bar
        self.status_bar = QStatusBar()
        self.setStatusBar(self.status_bar)
        
        # Load Initial Feeds and Ingestion Tasks
        self.load_feed_list()
        self.load_ingestion_list()
        self.load_query_list()
        self.load_profile_list()
        self.load_segment_list()
        self.load_workflow_list()
        
        # Check Auth
        self.check_auth()

    def toggle_sidebar(self):
        """Toggles sidebar visibility using splitter sizes."""
        if self.sidebar_container.width() > 0:
            # Collapse
            self._last_sidebar_width = self.sidebar_container.width()
            self.main_splitter.setSizes([0, 1200])
            self.btn_expand_sidebar.setVisible(True)
        else:
            # Expand
            width = getattr(self, '_last_sidebar_width', 250)
            if width == 0: width = 250
            self.main_splitter.setSizes([width, 1200 - width])
            self.btn_expand_sidebar.setVisible(False)

    def create_new_feed(self):
        """Opens dialog to create a new feed configuration."""
        dlg = CreateFeedDialog(self)
        if dlg.exec():
            # Get the feed data from the dialog
            new_feed = dlg.get_data()
            
            # Load existing feeds
            feeds = persistence.load_feeds()
            
            # Add the new feed
            feeds.append(new_feed)
            
            # Save the updated list
            persistence.save_feeds(feeds)
            
            logger.info(f"Created new feed: {new_feed['name']}")
            
            # Refresh Configs (Reload from disk)
            self.load_feed_list()
            
            # Find and select the new feed
            target_name = new_feed['name']
            
            # Expand Datafeeds item
            self.item_feeds.setExpanded(True)
            
            for i in range(self.item_feeds.childCount()):
                child = self.item_feeds.child(i)
                if child.text(0) == target_name:
                    self.sidebar.setCurrentItem(child)
                    self.on_sidebar_clicked(child, 0)
                    break
            
                    self.on_sidebar_clicked(child, 0)
                    break

    def create_new_ingestion_task(self):
        """Opens dialog to create a new ingestion task."""
        dlg = IngestionConfigDialog(self)
        if dlg.exec():
            new_task = dlg.get_data()
            
            tasks = persistence.load_ingestion_tasks()
            tasks.append(new_task)
            persistence.save_ingestion_tasks(tasks)
            
            logger.info(f"Created new ingestion task: {new_task['name']}")
            
            self.load_ingestion_list()
            
            # Select new
            for i in range(self.item_ingest.childCount()):
                child = self.item_ingest.child(i)
                if child.text(0) == new_task["name"]:
                    self.sidebar.setCurrentItem(child)
                    self.on_sidebar_clicked(child, 0)
                    break
    
    def create_new_local_query(self):
        """Create a new local query configuration."""
        name, ok = QInputDialog.getText(self, "New Query", "Query Name:")
        if ok and name.strip():
            # Create default config
            config = {
                "name": name.strip(),
                "sql": "SELECT * FROM local_table LIMIT 100",
                "feeds": [],
                "local_file": None
            }
            
            queries = persistence.load_local_queries()
            queries.append(config)
            persistence.save_local_queries(queries)
            
            self.load_query_list()
            
            # Select new item
            for i in range(self.item_queries.childCount()):
                child = self.item_queries.child(i)
                if child.text(0) == name.strip():
                    self.sidebar.setCurrentItem(child)
                    self.on_sidebar_clicked(child, 0)
                    break

    def load_query_list(self):
        """Loads local query configurations."""
        self.item_queries.takeChildren()
        
        queries = persistence.load_local_queries()
        for q in queries:
            item = QTreeWidgetItem(self.item_queries)
            item.setText(0, q["name"])
            item.setData(0, Qt.UserRole, q)
            
    def create_new_profile_task(self):
        """Create a new profile lookup task using Dialog."""
        dlg = ProfileConfigDialog(self)
        if dlg.exec():
            config = dlg.get_data()
            if not config["name"]: return
            
            tasks = persistence.load_profile_tasks()
            tasks.append(config)
            persistence.save_profile_tasks(tasks)
            
            self.load_profile_list()
            
            # Select new item
            for i in range(self.item_profiles.childCount()):
                child = self.item_profiles.child(i)
                if child.text(0) == config["name"]:
                    self.sidebar.setCurrentItem(child)
                    self.on_sidebar_clicked(child, 0)
                    break

    def edit_profile_task(self, item):
        """Edits an existing profile task."""
        config = item.data(0, Qt.UserRole)
        if not config: return
        
        dlg = ProfileConfigDialog(self)
        dlg.set_data(config)
        
        if dlg.exec():
            new_data = dlg.get_data()
            if not new_data["name"]: return
            
            # Update List
            tasks = persistence.load_profile_tasks()
            for i, t in enumerate(tasks):
                if t["name"] == config["name"]:
                    # Create merged config (preserve id if needed, or replacement)
                    # We preserve 'last_fetch' if not in dialog get_data
                    last_fetch = t.get("last_fetch")
                    tasks[i] = new_data
                    tasks[i]["last_fetch"] = last_fetch
                    break
            
            persistence.save_profile_tasks(tasks)
            self.load_profile_list()
            
            # Re-select
            for i in range(self.item_profiles.childCount()):
                child = self.item_profiles.child(i)
                if child.text(0) == new_data["name"]:
                    self.sidebar.setCurrentItem(child)
                    self.on_sidebar_clicked(child, 0)
                    break

    def load_profile_list(self):
        """Loads profile lookup tasks."""
        self.item_profiles.takeChildren()
        
        tasks = persistence.load_profile_tasks()
        
        for t in tasks:
            item = QTreeWidgetItem(self.item_profiles)
            item.setText(0, t["name"])
            item.setData(0, Qt.UserRole, t)

    def create_new_segment_task(self):
        """Create a new segment feed configuration."""
        dlg = CreateSegmentFeedDialog(self)
        if dlg.exec():
            # Note: The new dialog uses get_config() but let's check wrapper or adapt
            config = dlg.get_config()
            
            if not config or not config["name"]: return

            feeds = persistence.load_segment_feeds()
            feeds.append(config)
            persistence.save_segment_feeds(feeds)
            self.load_segment_list()
            
            for i in range(self.item_segments.childCount()):
                child = self.item_segments.child(i)
                if child.text(0) == config["name"]:
                    self.sidebar.setCurrentItem(child)
                    self.on_sidebar_clicked(child, 0)
                    break

    def edit_segment_task(self, item):
        """Edits an existing segment feed."""
        config = item.data(0, Qt.UserRole)
        if not config: return
        
        dlg = CreateSegmentFeedDialog(self, edit_mode=True, existing_config=config)
        
        if dlg.exec():
            new_data = dlg.get_config()
            if not new_data or not new_data["name"]: return
            
            feeds = persistence.load_segment_feeds()
            for i, t in enumerate(feeds):
                if t["name"] == config["name"]:
                    feeds[i] = new_data
                    break
            
            persistence.save_segment_feeds(feeds)
            self.load_segment_list()
            
            for i in range(self.item_segments.childCount()):
                child = self.item_segments.child(i)
                if child.text(0) == new_data["name"]:
                    self.sidebar.setCurrentItem(child)
                    self.on_sidebar_clicked(child, 0)
                    break
                    break

    def create_new_workflow(self):
        """Create a new workflow configuration."""
        name, ok = QInputDialog.getText(self, "New Workflow", "Workflow Name:")
        if ok and name.strip():
            config = {
                "name": name.strip(),
                "steps": []
            }
            workflows = persistence.load_workflows()
            workflows.append(config)
            persistence.save_workflows(workflows)
            
            self.load_workflow_list()
            
            for i in range(self.item_workflows.childCount()):
                child = self.item_workflows.child(i)
                if child.text(0) == name.strip():
                    self.sidebar.setCurrentItem(child)
                    self.on_sidebar_clicked(child, 0)
                    break

    def load_segment_list(self):
        """Loads segment feeds."""
        self.item_segments.takeChildren()
        feeds = persistence.load_segment_feeds()
        for f in feeds:
            item = QTreeWidgetItem(self.item_segments)
            item.setText(0, f["name"])
            item.setData(0, Qt.UserRole, f)
            item.setData(0, Qt.UserRole, f)

    def load_workflow_list(self):
        """Loads workflow configurations."""
        self.item_workflows.takeChildren()
        workflows = persistence.load_workflows()
        for w in workflows:
            item = QTreeWidgetItem(self.item_workflows)
            item.setText(0, w["name"])
            item.setData(0, Qt.UserRole, w)

    def load_feed_list(self):
        """Loads feed configurations from persistence and populates the tree."""
        # Clear existing children of item_feeds
        self.item_feeds.takeChildren()
        
        feeds = persistence.load_feeds()
        for feed in feeds:
             item = QTreeWidgetItem(self.item_feeds)
             item.setText(0, feed["name"])
             item.setData(0, Qt.UserRole, feed) # Store full config

    def load_ingestion_list(self):
        """Loads ingestion task configurations."""
        self.item_ingest.takeChildren()
        
        tasks = persistence.load_ingestion_tasks()
        for task in tasks:
            item = QTreeWidgetItem(self.item_ingest)
            item.setText(0, task["name"])
            item.setData(0, Qt.UserRole, task)

             
    def on_sidebar_clicked(self, item, column):
        """Handles feed selection in the tree."""
        if item is None: return
        
        # 1. Main Navigation Items
        # 1. Main Navigation Items
        # if item == self.item_ingest: ... -> Ingestion is now a folder
        
        if item == self.item_ingest:
             # Show a summary or empty state?
             # For now, just load None to show "Select a task"
             self.task_ingest.load_config(None)
             self.content_stack.setCurrentWidget(self.task_ingest)
             self.lbl_page_title.setText("Ingestion Tasks")
             return
            
        elif item == self.item_queries:
             self.task_validate.load_config(None) 
             self.content_stack.setCurrentWidget(self.task_validate)
             self.lbl_page_title.setText("Local Queries")
             return

        elif item == self.item_profiles:
             self.task_profile.load_config(None)
             self.content_stack.setCurrentWidget(self.task_profile)
             self.lbl_page_title.setText("Profile Lookup")
             return
             
        elif item == self.item_segments:
             self.task_segments.load_config(None)
             self.content_stack.setCurrentWidget(self.task_segments)
             self.lbl_page_title.setText("Segments")
             return
             
        elif item == self.item_workflows:
             # Just show the canvas
             self.content_stack.setCurrentWidget(self.task_workflows)
             self.lbl_page_title.setText("Workflows")
             return

        # 2. Datafeeds Section
        # If clicked "Datafeeds" header itself
        if item == self.item_feeds:
             self.task_pull.load_feed(None)
             self.content_stack.setCurrentWidget(self.task_pull)
             self.lbl_page_title.setText("Datafeeds Summary")
             return

        # 3. Individual Feed Items (Children of item_feeds)
        if item.parent() == self.item_feeds:
            config = item.data(0, Qt.UserRole)
            if config:
                self.task_pull.load_feed(config)
                self.content_stack.setCurrentWidget(self.task_pull)
                self.lbl_page_title.setText(config["name"])
            else:
                self.task_pull.load_feed(None)
                self.lbl_page_title.setText("Error Loading Feed")
            return
            
        # 4. Local Queries Items
        if item.parent() == self.item_queries:
            config = item.data(0, Qt.UserRole)
            self.task_validate.load_config(config)
            self.content_stack.setCurrentWidget(self.task_validate)
            self.lbl_page_title.setText(config["name"] if config else "Detail")
            return

        # 5. Profile Task Items
        if item.parent() == self.item_profiles:
            config = item.data(0, Qt.UserRole)
            self.task_profile.load_config(config)
            self.content_stack.setCurrentWidget(self.task_profile)
            self.lbl_page_title.setText(config["name"] if config else "Profile Detail")
            return
            
        # 6. Segment Task Items
        if item.parent() == self.item_segments:
            config = item.data(0, Qt.UserRole)
            self.task_segments.load_config(config)
            self.content_stack.setCurrentWidget(self.task_segments)
            self.lbl_page_title.setText(config["name"] if config else "Segment Detail")
            return
            
        # 7. Workflow Items
        if item.parent() == self.item_workflows:
            config = item.data(0, Qt.UserRole)
            # We need to implement load_workflow in task_workflows widget shortly
            # self.task_workflows.load_workflow(config)
            self.content_stack.setCurrentWidget(self.task_workflows)
            self.lbl_page_title.setText(config["name"] if config else "Workflow")
            return

    def show_context_menu(self, position):
        """Shows context menu for sidebar items."""
        item = self.sidebar.itemAt(position)
        if not item:
            return
            
            
        # Context menu for Feed items OR Ingestion items
        if item.parent() == self.item_feeds:
             self.show_feed_context_menu(item, position)
        elif item.parent() == self.item_ingest:
             self.show_ingest_context_menu(item, position)
        elif item.parent() == self.item_queries:
             self.show_query_context_menu(item, position)
        elif item.parent() == self.item_profiles:
             self.show_profile_context_menu(item, position)
        elif item.parent() == self.item_segments:
             self.show_segment_context_menu(item, position)
        elif item.parent() == self.item_workflows:
             self.show_workflow_context_menu(item, position)
             
    def show_feed_context_menu(self, item, position):
        menu = QMenu()
        action_edit = menu.addAction("Edit Datafeed")
        action_edit.triggered.connect(lambda: self.edit_feed(item))
        action_delete = menu.addAction("Delete Datafeed")
        action_delete.triggered.connect(lambda: self.delete_feed(item))
        menu.exec(self.sidebar.viewport().mapToGlobal(position))
        
    def show_ingest_context_menu(self, item, position):
        menu = QMenu()
        action_edit = menu.addAction("Edit Task")
        action_edit.triggered.connect(lambda: self.edit_ingestion_task(item))
        action_delete = menu.addAction("Delete Task")
        action_delete.triggered.connect(lambda: self.delete_ingestion_task(item))
        menu.exec(self.sidebar.viewport().mapToGlobal(position))

    def show_query_context_menu(self, item, position):
        menu = QMenu()
        action_edit = menu.addAction("Edit Query") # Placeholder for rename?
        action_edit.triggered.connect(lambda: self.rename_local_query(item)) # Using rename as edit
        action_delete = menu.addAction("Delete Query")
        action_delete.triggered.connect(lambda: self.delete_local_query(item))
        menu.exec(self.sidebar.viewport().mapToGlobal(position))

    def show_profile_context_menu(self, item, position):
        menu = QMenu()
        action_edit = menu.addAction("Edit Lookup")
        action_edit.triggered.connect(lambda: self.edit_profile_task(item))
        action_delete = menu.addAction("Delete Lookup")
        action_delete.triggered.connect(lambda: self.delete_profile_task(item))
        menu.exec(self.sidebar.viewport().mapToGlobal(position))

    def show_segment_context_menu(self, item, position):
        menu = QMenu()
        action_edit = menu.addAction("Edit Segment")
        action_edit.triggered.connect(lambda: self.edit_segment_task(item))
        action_delete = menu.addAction("Delete Segment")
        action_delete.triggered.connect(lambda: self.delete_segment_task(item))
        menu.exec(self.sidebar.viewport().mapToGlobal(position))
        
    def show_workflow_context_menu(self, item, position):
        menu = QMenu()
        action_delete = menu.addAction("Delete Workflow")
        action_delete.triggered.connect(lambda: self.delete_workflow(item))
        menu.exec(self.sidebar.viewport().mapToGlobal(position))
        
    def delete_workflow(self, item):
        config = item.data(0, Qt.UserRole)
        name = config["name"]
        
        reply = QMessageBox.question(self, "Confirm Delete", 
                                     f"Are you sure you want to delete workflow '{name}'?",
                                     QMessageBox.Yes | QMessageBox.No, QMessageBox.No)
        
        if reply == QMessageBox.Yes:
            workflows = persistence.load_workflows()
            workflows = [w for w in workflows if w["name"] != name]
            persistence.save_workflows(workflows)
            self.load_workflow_list()
            self.task_workflows.clear()
            self.content_stack.setCurrentWidget(self.task_workflows)

    def rename_local_query(self, item):
        """Renames a local query task."""
        config = item.data(0, Qt.UserRole)
        old_name = config.get("name")
        new_name, ok = QInputDialog.getText(self, "Rename Query", "New Name:", text=old_name)
        if ok and new_name.strip():
             queries = persistence.load_local_queries()
             for q in queries:
                 if q["name"] == old_name:
                     q["name"] = new_name.strip()
                     break
             persistence.save_local_queries(queries)
             self.load_query_list()

    def delete_local_query(self, item):
        """Deletes a local query task."""
        config = item.data(0, Qt.UserRole)
        name = config.get("name")
        reply = QMessageBox.question(self, "Confirm Delete", 
                                   f"Are you sure you want to delete query '{name}'?",
                                   QMessageBox.Yes | QMessageBox.No)
        if reply == QMessageBox.Yes:
            queries = persistence.load_local_queries()
            queries = [q for q in queries if q.get("name") != name]
            persistence.save_local_queries(queries)
            self.load_query_list()
            self.task_validate.load_config(None)
            self.lbl_page_title.setText("Local Queries")


    def edit_feed(self, item):
        """Opens dialog to edit the selected feed."""
        config = item.data(0, Qt.UserRole)
        old_name = config.get("name")
        
        dlg = CreateFeedDialog(self)
        dlg.set_data(config)
        
        if dlg.exec():
            new_config = dlg.get_data()
            new_name = new_config.get("name")
            
            # Update Persistence
            feeds = persistence.load_feeds()
            
            # Find and update
            # (Simplistic approach: Remove old, Add new to preserve order or just replace)
            for i, f in enumerate(feeds):
                if f.get("name") == old_name:
                    feeds[i] = new_config
                    break
            else:
                 # Should not happen, but just in case
                 feeds.append(new_config)
            
            persistence.save_feeds(feeds)
            
            # Clear UI Cache to force rebuild with new config
            self.task_pull.clear_feed_cache(old_name)
            
            # Handle Name Change State Migration (Optional but nice)
            if old_name != new_name:
                state = persistence.load_state(old_name)
                if state:
                    persistence.save_state(new_name, state)
                    # We might want to clear the old state, but keeping it is safer for now
                    
            # Refresh UI
            self.load_feed_list()
            
            logger.info(f"Updated feed: {old_name} -> {new_name}")
            
            # Auto-navigate to the updated feed
            target_name = new_name
            # Ensure folder expanded
            self.item_feeds.setExpanded(True)
            
            for i in range(self.item_feeds.childCount()):
                child = self.item_feeds.child(i)
                if child.text(0) == target_name:
                    self.sidebar.setCurrentItem(child)
                    self.on_sidebar_clicked(child, 0)
                    break

    def delete_feed(self, item):
        """Deletes the selected feed."""
        config = item.data(0, Qt.UserRole)
        name = config.get("name")
        
        # Confirmation Dialog
        reply = QMessageBox.question(self, "Delete Datafeed", 
                                     f"Are you sure you want to delete '{name}'?\nThis will remove the configuration.",
                                     QMessageBox.Yes | QMessageBox.No, QMessageBox.No)
                                     
        if reply == QMessageBox.Yes:
            # 1. Update Persistence
            feeds = persistence.load_feeds()
            feeds = [f for f in feeds if f.get("name") != name]
            persistence.save_feeds(feeds)
            
            # Clear UI Cache
            self.task_pull.clear_feed_cache(name)
            
            # 2. Update UI
            # If current view is this feed, switch to Summary
            if self.lbl_page_title.text() == name:
                 self.task_pull.load_feed(None)
                 self.lbl_page_title.setText("Datafeeds Summary")
                 self.sidebar.setCurrentItem(self.item_feeds)
                 
            self.load_feed_list()
            self.load_feed_list()
            logger.info(f"Deleted feed: {name}")

    def edit_ingestion_task(self, item):
        config = item.data(0, Qt.UserRole)
        old_name = config.get("name")
        
        dlg = IngestionConfigDialog(self)
        dlg.set_data(config)
        
        if dlg.exec():
            new_config = dlg.get_data()
            tasks = persistence.load_ingestion_tasks()
            
            for i, t in enumerate(tasks):
                if t.get("name") == old_name:
                    tasks[i] = new_config
                    break
            else:
                tasks.append(new_config)
                
            persistence.save_ingestion_tasks(tasks)
            self.load_ingestion_list()
            logger.info(f"Updated ingestion task: {old_name}")
            
            # Select updated
            self.item_ingest.setExpanded(True)
            for i in range(self.item_ingest.childCount()):
                child = self.item_ingest.child(i)
                if child.text(0) == new_config['name']:
                    self.sidebar.setCurrentItem(child)
                    self.on_sidebar_clicked(child, 0)
                    break

    def delete_ingestion_task(self, item):
        """Deletes the selected ingestion task."""
        config = item.data(0, Qt.UserRole)
        name = config.get("name")
        
        reply = QMessageBox.question(self, "Confirm Delete", 
                                   f"Are you sure you want to delete ingestion task '{name}'?",
                                   QMessageBox.Yes | QMessageBox.No)
        
        if reply == QMessageBox.Yes:
            tasks = persistence.load_ingestion_tasks()
            tasks = [t for t in tasks if t.get("name") != name]
            persistence.save_ingestion_tasks(tasks)
            
            self.load_ingestion_list()
            self.task_ingest.load_config(None) 
            self.lbl_page_title.setText("Ingestion Tasks")
            logger.info(f"Deleted ingestion task: {name}")

    def delete_profile_task(self, item):
        """Deletes the selected profile task."""
        config = item.data(0, Qt.UserRole)
        name = config.get("name")
        
        reply = QMessageBox.question(self, "Confirm Delete", 
                                   f"Are you sure you want to delete profile task '{name}'?",
                                   QMessageBox.Yes | QMessageBox.No)
        
        if reply == QMessageBox.Yes:
            tasks = persistence.load_profile_tasks()
            tasks = [t for t in tasks if t.get("name") != name]
            persistence.save_profile_tasks(tasks)
            
            self.load_profile_list()
            self.task_profile.load_config(None)
            self.lbl_page_title.setText("Profile Lookup")
            logger.info(f"Deleted profile task: {name}")

    def delete_segment_task(self, item):
        """Deletes the selected segment task."""
        config = item.data(0, Qt.UserRole)
        name = config.get("name")
        
        reply = QMessageBox.question(self, "Confirm Delete", 
                                   f"Are you sure you want to delete segment task '{name}'?",
                                   QMessageBox.Yes | QMessageBox.No)
        
        if reply == QMessageBox.Yes:
            tasks = persistence.load_segment_tasks()
            tasks = [t for t in tasks if t.get("name") != name]
            persistence.save_segment_tasks(tasks)
            
            self.load_segment_list()
            self.task_segments.load_config(None)
            self.lbl_page_title.setText("Segments")
            logger.info(f"Deleted segment task: {name}")

    def check_auth(self):
        """Checks for a valid token and updates the UI."""
        try:
            token = self.auth.get_access_token()
            if token:
                self.auth_status.setText("● Connected")
                self.auth_status.setStyleSheet("color: #4caf50; font-weight: bold;") # Green
                self.status_bar.showMessage(f"Connected to Sandbox: {self.auth.config.get('sandbox_name')}")
            else:
                self.auth_status.setText("● Not Connected")
                self.auth_status.setStyleSheet("color: #f44336; font-weight: bold;") # Red
        except Exception as e:
            logger.error(f"Auth check failed: {e}")
            self.auth_status.setText("● Auth Error")
            self.auth_status.setStyleSheet("color: #f44336; font-weight: bold;")
            self.status_bar.showMessage(f"Auth Error: {str(e)}")
    
    def on_credentials_updated(self):
        """Called when user saves new credentials in Settings."""
        logger.info("Credentials updated - reloading authentication...")
        self.auth.reload_config()
        self.check_auth()
        self.status_bar.showMessage("Credentials updated successfully!", 3000)

    def open_settings(self):
        """Switches to Settings view."""
        self.content_stack.setCurrentWidget(self.task_settings)
        self.lbl_page_title.setText("Settings")
        self.sidebar.clearSelection()
