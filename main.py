import sys
import os
from PySide6.QtWidgets import QApplication
from PySide6.QtGui import QIcon
from logger import logger

# Import splash FIRST before heavy modules
from splash import show_splash

def get_resource_path(relative_path):
    """ Get absolute path to resource, works for dev and for PyInstaller """
    try:
        # PyInstaller creates a temp folder and stores path in _MEIPASS
        base_path = sys._MEIPASS
    except Exception:
        base_path = os.path.abspath(".")

    return os.path.join(base_path, relative_path)

def main():
    try:
        # Set App User Model ID for Windows Taskbar Icon
        import ctypes
        myappid = 'com.aep.dataexplorer.1.0'
        ctypes.windll.shell32.SetCurrentProcessExplicitAppUserModelID(myappid)
        
        # Create app FIRST
        app = QApplication(sys.argv)
        app.setApplicationName("AEP Data Explorer")
        
        # Load Icons (Do this early so splash and main window get it)
        icon_path = get_resource_path("app_icon.ico")
        if os.path.exists(icon_path):
            app.setWindowIcon(QIcon(icon_path))
        
        # Show splash immediately
        splash = show_splash()
        splash.showMessage("Loading modules...", 0x0084, 0xFFFFFF)
        app.processEvents()
        
        # NOW import heavy modules
        from ui_mainwindow import MainWindow
        
        splash.showMessage("Initializing application...", 0x0084, 0xFFFFFF)
        app.processEvents()
        
        # Load Stylesheet
        style_path = get_resource_path("styles.qss")
        if os.path.exists(style_path):
            with open(style_path, "r") as f:
                app.setStyleSheet(f.read())
            logger.info(f"Stylesheet loaded from {style_path}")
        
        splash.showMessage("Starting application...", 0x0084, 0xFFFFFF)
        app.processEvents()
        
        window = MainWindow()
        window.show()
        
        # Close splash after window is shown
        splash.finish(window)
        
        sys.exit(app.exec())
        
    except Exception as e:
        logger.error(f"Application failed to start: {e}", exc_info=True)
        # Ensure splash is closed on error so we see the traceback/error (or at least app exits)
        if 'splash' in locals():
            splash.close()
        raise
        


if __name__ == "__main__":
    main()
