from PySide6.QtWidgets import (QWidget, QVBoxLayout, QHBoxLayout, QTableView, 
                               QLineEdit, QPushButton, QHeaderView, QLabel, QFileDialog,
                               QDialog, QComboBox, QScrollArea, QFrame, QRadioButton, QButtonGroup, QMessageBox)
from PySide6.QtCore import Qt, QSortFilterProxyModel, Signal
from PySide6.QtGui import QStandardItemModel, QStandardItem
from logger import logger

class CustomProxyModel(QSortFilterProxyModel):
    """
    Custom Proxy Model to support Multi-Column Filtering.
    """
    def __init__(self):
        super().__init__()
        self.filters = {} # {column_index: (operator, value)}

    def set_filters(self, filters):
        """
        Updates the filters.
        filters: dict {col_index: {'op': 'Contains'|'Equals', 'val': 'text'}}
        """
        self.filters = filters
        self.invalidateFilter()

    def filterAcceptsRow(self, source_row, source_parent):
        # 1. Check Global Search (Base Class Logic) - Optional, but let's keep it separate
        # Actually, base class uses filterRegExp on filterKeyColumn. 
        # If we want BOTH global search AND advanced filter, we need to handle both.
        
        # Let's check Global Search first (if set via setFilterFixedString)
        # We can re-use base class logic if we didn't override, but since we are, 
        # we might need to implement global search manually or call super() if we set the filter key to -1.
        # However, super().filterAcceptsRow() checks the regex against the column set by filterKeyColumn.
        # If filterKeyColumn is -1, it checks all.
        
        if not super().filterAcceptsRow(source_row, source_parent):
            return False

        # 2. Check Advanced Filters
        if not self.filters:
            return True

        model = self.sourceModel()
        
        for col_idx, criteria in self.filters.items():
            index = model.index(source_row, col_idx, source_parent)
            data = model.data(index)
            
            if data is None:
                data = ""
            else:
                data = str(data)
            
            op = criteria['op']
            val = criteria['val'].lower()
            data_lower = data.lower()
            
            if op == "Contains":
                if val not in data_lower:
                    return False
            elif op == "Equals":
                if val != data_lower:
                    return False
            elif op == "Starts With":
                if not data_lower.startswith(val):
                    return False
            elif op == "Ends With":
                if not data_lower.endswith(val):
                    return False
                    
        return True

class AdvancedFilterDialog(QDialog):
    """
    Popup dialog for defining multiple filters.
    """
    def __init__(self, columns, initial_filters=None, parent=None):
        super().__init__(parent)
        self.setWindowTitle("Advanced Filter")
        self.resize(800, 500)
        self.columns = columns
        self.filters = [] # List of filter widgets
        self.initial_filters = initial_filters or {}
        
        layout = QVBoxLayout(self)
        
        # Scroll Area for Filters
        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        self.filter_container = QWidget()
        self.filter_layout = QVBoxLayout(self.filter_container)
        self.filter_layout.addStretch()
        scroll.setWidget(self.filter_container)
        layout.addWidget(scroll)
        
        # Add Filter Button
        btn_add = QPushButton("+ Add Filter")
        btn_add.clicked.connect(self.add_filter_row)
        layout.addWidget(btn_add)
        
        # Buttons
        btn_box = QHBoxLayout()
        btn_apply = QPushButton("Apply")
        btn_apply.clicked.connect(self.accept)
        btn_cancel = QPushButton("Cancel")
        btn_cancel.clicked.connect(self.reject)
        
        btn_box.addStretch()
        btn_box.addWidget(btn_cancel)
        btn_box.addWidget(btn_apply)
        layout.addLayout(btn_box)
        
        # Populate initial rows
        if self.initial_filters:
            for col_name, criteria in self.initial_filters.items():
                if col_name in self.columns:
                    self.add_filter_row(col_name=col_name, op=criteria.get('op'), val=criteria.get('val'))
        else:
            # Add one empty row
            self.add_filter_row()

    def add_filter_row(self, col_name=None, op=None, val=None):
        row_widget = QFrame()
        row_layout = QHBoxLayout(row_widget)
        row_layout.setContentsMargins(0, 5, 0, 5)
        
        # Column Combo
        combo_col = QComboBox()
        combo_col.addItems(self.columns)
        if col_name:
            combo_col.setCurrentText(col_name)
        row_layout.addWidget(combo_col, 1) # Stretch 1
        
        # Operator Combo
        combo_op = QComboBox()
        combo_op.addItems(["Contains", "Equals", "Starts With", "Ends With"])
        if op:
            combo_op.setCurrentText(op)
        row_layout.addWidget(combo_op, 1) # Stretch 1
        
        # Value Input
        txt_val = QLineEdit()
        txt_val.setPlaceholderText("Value")
        if val:
            txt_val.setText(val)
        row_layout.addWidget(txt_val, 2) # Stretch 2 for value
        
        # Remove Button
        btn_remove = QPushButton("X")
        btn_remove.setFixedWidth(30)
        btn_remove.setStyleSheet("background-color: #d32f2f; color: white; border: none; border-radius: 4px;")
        btn_remove.clicked.connect(lambda: self.remove_filter_row(row_widget))
        row_layout.addWidget(btn_remove)
        
        # Insert before stretch
        self.filter_layout.insertWidget(self.filter_layout.count()-1, row_widget)
        self.filters.append({
            'widget': row_widget,
            'col': combo_col,
            'op': combo_op,
            'val': txt_val
        })

    def remove_filter_row(self, widget):
        widget.deleteLater()
        self.filters = [f for f in self.filters if f['widget'] != widget]

    def get_filters(self):
        """Returns dict of filters ready for ProxyModel."""
        result = {}
        for f in self.filters:
            col_name = f['col'].currentText()
            # result key is column name directly for matching with active_filters structure?
            # Wait, get_filters previously implementation returned {col_idx: ...} but Dialog works with names.
            # But ResultsWidget converted it.
            # Let's return {col_idx: ...} to maintain compatibility with ResultsWidget call site OR match expected output.
            
            # Previous implementation (step 542):
            # col_idx = self.columns.index(col_name)
            # result[col_idx] = ...
            
            # But wait, looking at my planned change for ResultsWidget, 
            # I can just return the raw Dict {col_name: {op, val}} and let ResultsWidget handle it,
            # OR honestly it's easier if Dialog returns what ResultsWidget gave it: map of names.
            
            # Returning name-based is more robust if columns shift, but here columns are passed in.
            
            op = f['op'].currentText()
            val = f['val'].text().strip()
            
            if val:
                idx = self.columns.index(col_name)
                result[idx] = {'op': op, 'val': val}
                
        return result

class ResultsWidget(QWidget):
    """
    Reusable component for displaying data with:
    - Sortable/Filterable Table (Server-Side)
    - Real-time Search (Server-Side)
    - Advanced Filtering (Server-Side)
    - Export to Excel (All vs Visible)
    - Pagination (via DataManager)
    """
    
    toggle_fullscreen = Signal(bool)

    def __init__(self):
        super().__init__()
        self.layout = QVBoxLayout(self)
        self.layout.setContentsMargins(0, 0, 0, 0)
        self.layout.setSpacing(10)

        # --- Toolbar ---
        toolbar = QHBoxLayout()
        
        # Search Bar
        self.search_input = QLineEdit()
        self.search_input.setPlaceholderText("Global Search...")
        self.search_input.textChanged.connect(self.on_search_changed)
        toolbar.addWidget(self.search_input)
        
        # Advanced Filter Button
        self.btn_adv_filter = QPushButton("Advanced Filter")
        self.btn_adv_filter.clicked.connect(self.open_advanced_filter)
        self.btn_adv_filter.setEnabled(False) # Disable until data loaded
        toolbar.addWidget(self.btn_adv_filter)
        
        # Last Run Label
        self.lbl_last_run = QLabel("")
        self.lbl_last_run.setStyleSheet("color: #888; font-size: 11px; margin-left: 10px;")
        toolbar.addWidget(self.lbl_last_run)
        
        toolbar.addStretch()
        
        # Export Options
        self.radio_group = QButtonGroup(self)
        self.radio_all = QRadioButton("Export All")
        self.radio_visible = QRadioButton("Export Visible")
        self.radio_all.setChecked(True)
        self.radio_group.addButton(self.radio_all)
        self.radio_group.addButton(self.radio_visible)
        
        toolbar.addWidget(self.radio_all)
        toolbar.addWidget(self.radio_visible)
        
        # Export Button
        self.btn_export_excel = QPushButton("Export to Excel")
        self.btn_export_excel.clicked.connect(self.export_excel)
        self.btn_export_excel.setEnabled(False) # Disable until data loaded
        toolbar.addWidget(self.btn_export_excel)

        # Expand Button
        # self.btn_expand removed (Moved to Global Main Window Toolbar)
        
        self.layout.addLayout(toolbar)

        # --- Table View ---
        self.table_view = QTableView()
        # Disable client-side sorting to handle it manually (Server-Side)
        self.table_view.setSortingEnabled(False) 
        self.table_view.horizontalHeader().setSectionResizeMode(QHeaderView.Interactive)
        self.table_view.horizontalHeader().setSectionsMovable(True)
        self.table_view.setAlternatingRowColors(True)
        
        # Connect Header Click for Sort
        self.table_view.horizontalHeader().sectionClicked.connect(self.on_header_clicked)
        
        self.layout.addWidget(self.table_view)
        
        # --- Pagination Controls ---
        self.pagination_layout = QHBoxLayout()
        
        self.btn_prev = QPushButton("Previous")
        self.btn_prev.clicked.connect(self.prev_page)
        self.btn_prev.setEnabled(False)
        
        self.lbl_page = QLabel("Page 0 of 0")
        self.lbl_page.setAlignment(Qt.AlignCenter)
        
        self.btn_next = QPushButton("Next")
        self.btn_next.clicked.connect(self.next_page)
        self.btn_next.setEnabled(False)
        
        self.pagination_layout.addWidget(self.btn_prev)
        self.pagination_layout.addWidget(self.lbl_page)
        self.pagination_layout.addWidget(self.btn_next)
        
        self.layout.addLayout(self.pagination_layout)

        # --- Data Model ---
        self.source_model = QStandardItemModel()
        # We don't need ProxyModel for filtering anymore if doing it server-side, 
        # but keeping it for now doesn't hurt (it just won't filter anything if we don't set it).
        # Actually, let's remove it to avoid confusion and double filtering.
        self.table_view.setModel(self.source_model)
        
        # State
        self.current_df = None
        self.current_columns = []
        self.data_manager = None
        
        # Pagination State
        self.current_page = 1
        self.page_size = 100
        self.total_rows = 0
        
        # Query State
        self.sort_col_name = None
        self.sort_asc = True
        self.search_text = None
        self.active_filters = None

    def load_manager(self, data_manager):
        """Loads data using the DataManager (DuckDB backed)."""
        self.data_manager = data_manager
        self.current_page = 1
        self.total_rows = data_manager.total_rows
        self.current_columns = data_manager.get_columns()
        
        # Disable client-side sorting (handled by DB)
        self.table_view.setSortingEnabled(False)
        
        # Reset Query State
        self.sort_col_name = None
        self.sort_asc = True
        self.search_text = None
        self.active_filters = None
        self.search_input.clear()
        
        self.refresh_view()
        
        self.btn_adv_filter.setEnabled(True)
        self.btn_export_excel.setEnabled(True)

    def refresh_view(self, reset_scroll=False):
        if not self.data_manager:
            return
            
        # Capture State (Column Widths & Horizontal Scroll)
        h_scroll = self.table_view.horizontalScrollBar().value()
        v_scroll = self.table_view.verticalScrollBar().value()
        
        col_widths = {}
        # Note: We capture based on visual index or logical? 
        # setColumnWidth uses logical index.
        if self.source_model.columnCount() > 0:
            for i in range(self.source_model.columnCount()):
                col_widths[i] = self.table_view.columnWidth(i)

        # Fetch Page with all params
        df, filtered_count = self.data_manager.get_data(
            page=self.current_page, 
            page_size=self.page_size,
            filters=self.active_filters,
            sort_by=self.sort_col_name,
            sort_asc=self.sort_asc,
            search_text=self.search_text
        )
        
        # Update Total Rows based on filter (if filtered)
        current_total = filtered_count
        
        self.load_data_internal(df)
        
        # Restore State
        if self.source_model.columnCount() > 0:
            for i, width in col_widths.items():
                if i < self.source_model.columnCount():
                    self.table_view.setColumnWidth(i, width)
        
        # Restore Scroll
        self.table_view.horizontalScrollBar().setValue(h_scroll)
        
        if not reset_scroll:
            self.table_view.verticalScrollBar().setValue(v_scroll)
        else:
            self.table_view.verticalScrollBar().setValue(0)

        # Update Pagination Controls
        total_pages = (current_total + self.page_size - 1) // self.page_size
        if total_pages == 0: total_pages = 1
        
        # Ensure current page is valid
        if self.current_page > total_pages:
            self.current_page = 1 
        
        self.lbl_page.setText(f"Page {self.current_page} of {total_pages} (Rows: {current_total})")
        
        self.btn_prev.setEnabled(self.current_page > 1)
        self.btn_next.setEnabled(self.current_page < total_pages)
        
        # Update Header Sort Indicator manually
        if self.sort_col_name and self.sort_col_name in self.current_columns:
            idx = self.current_columns.index(self.sort_col_name)
            order = Qt.AscendingOrder if self.sort_asc else Qt.DescendingOrder
            self.table_view.horizontalHeader().setSortIndicator(idx, order)

    def on_header_clicked(self, logicalIndex):
        # Only handle manual sort if manager is active
        if not self.data_manager or not self.current_columns:
            return
            
        col_name = self.current_columns[logicalIndex]
        
        if self.sort_col_name == col_name:
            self.sort_asc = not self.sort_asc
        else:
            self.sort_col_name = col_name
            self.sort_asc = True
            
        self.refresh_view()

    def prev_page(self):
        if self.current_page > 1:
            self.current_page -= 1
            self.refresh_view(reset_scroll=True)

    def next_page(self):
        self.current_page += 1
        self.refresh_view(reset_scroll=True)

    def load_data(self, df):
        """Legacy method for direct DataFrame loading."""
        self.data_manager = None
        self.total_rows = len(df)
        self.current_page = 1
        
        # Enable client-side sorting for in-memory data
        self.table_view.setSortingEnabled(True)
        
        self.load_data_internal(df)
        self.lbl_page.setText("All Data (In-Memory)")
        self.btn_prev.setEnabled(False)
        self.btn_next.setEnabled(False)

    def load_data_internal(self, df):
        """Internal method to populate the model from a DF."""
        import pandas as pd
        if df is None:
            df = pd.DataFrame()
            
        self.current_df = df
        if not self.current_columns and not df.empty:
            self.current_columns = df.columns.tolist()
            
        self.source_model.clear()
        
        # Set Headers
        if self.current_columns:
            self.source_model.setHorizontalHeaderLabels(self.current_columns)
        
        # Set Data
        if not df.empty:
            for row in df.itertuples(index=False):
                items = [QStandardItem(str(field)) for field in row]
                self.source_model.appendRow(items)
            
        self.btn_adv_filter.setEnabled(True)
        self.btn_export_excel.setEnabled(True)
        logger.info(f"Loaded {len(df)} rows into view.")

    def on_search_changed(self, text):
        """Updates the global search."""
        self.search_text = text.strip() if text.strip() else None
        self.current_page = 1 # Reset to page 1 on search
        self.refresh_view(reset_scroll=True)

    def open_advanced_filter(self):
        if not self.current_columns:
            return
            
        dlg = AdvancedFilterDialog(self.current_columns, initial_filters=self.active_filters, parent=self)
        if dlg.exec():
            # Get filters from dialog
            # Dialog returns {col_idx: {op, val}}
            # We need to map col_idx to col_name for DataManager
            raw_filters = dlg.get_filters()
            
            # Convert to {col_name: {op, val}}
            self.active_filters = {}
            for col_idx, criteria in raw_filters.items():
                if 0 <= col_idx < len(self.current_columns):
                    col_name = self.current_columns[col_idx]
                    self.active_filters[col_name] = criteria
            
            self.current_page = 1
            self.refresh_view(reset_scroll=True)

    def export_excel(self):
        if self.current_df is None:
            return
            
        path, _ = QFileDialog.getSaveFileName(self, "Save Excel", "", "Excel Files (*.xlsx)")
        if not path:
            return

        try:
            import pandas as pd
            # Create a copy to avoid modifying the view's data
            export_df = self.current_df.copy()
            
            # Fix Timezone Issue for Excel
            for col in export_df.columns:
                if pd.api.types.is_datetime64_any_dtype(export_df[col]):
                    export_df[col] = export_df[col].dt.tz_localize(None)
            
            if self.radio_visible.isChecked():
                # Export Visible (Current Page)
                export_df.to_excel(path, index=False)
                QMessageBox.information(self, "Export Successful", f"Current page saved to {path}")
            else:
                # Export All
                if self.data_manager:
                    # Use DataManager for full export (supports filtering)
                    self.data_manager.export_to_file(
                        path, 
                        filters=self.active_filters, 
                        search_text=self.search_text
                    )
                    QMessageBox.information(self, "Export Successful", f"Full dataset saved to {path}")
                else:
                    # Fallback for in-memory only (e.g. validation results)
                    export_df.to_excel(path, index=False)
                    QMessageBox.information(self, "Export Successful", f"Data saved to {path}")
            
        except Exception as e:
            QMessageBox.critical(self, "Export Failed", str(e))

    # Expand/Collapse logic moved to MainWindow

    def set_last_run_time(self, time_str):
        if time_str:
            self.lbl_last_run.setText(f"Last Run: {time_str}")
        else:
            self.lbl_last_run.setText("")

    def set_status(self, message):
        """Sets the status message (reusing the last run label)."""
        self.lbl_last_run.setText(message)

    def clear_data(self):
        """Clears the table and resets state."""
        self.source_model.clear()
        self.current_df = None
        self.data_manager = None
        self.current_columns = []
        self.current_page = 1
        self.total_rows = 0
        self.lbl_page.setText("Page 0 of 0")
        self.btn_adv_filter.setEnabled(False)
        self.btn_export_excel.setEnabled(False)
        self.lbl_last_run.setText("")
