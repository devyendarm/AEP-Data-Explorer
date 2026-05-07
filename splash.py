import sys
import os
from PySide6.QtWidgets import QApplication, QSplashScreen
from PySide6.QtGui import QPixmap, QPainter, QColor, QFont, QBrush
from PySide6.QtCore import Qt

def get_resource_path(relative_path):
    """ Get absolute path to resource, works for dev and for PyInstaller """
    try:
        # PyInstaller creates a temp folder and stores path in _MEIPASS
        base_path = sys._MEIPASS
    except Exception:
        base_path = os.path.abspath(".")
    return os.path.join(base_path, relative_path)

class AdobeStyleSplash(QSplashScreen):
    def __init__(self):
        # Create a red pixmap
        width, height = 500, 300
        pixmap = QPixmap(width, height)
        
        # Adobe Red color
        adobe_red = QColor("#E1251B") 
        
        # Fill with red
        pixmap.fill(adobe_red)
        
        super().__init__(pixmap, Qt.WindowStaysOnTopHint | Qt.FramelessWindowHint)
        
        # Draw text immediately on the pixmap so it's visible even before showMessage is called
        painter = QPainter(pixmap)
        painter.setRenderHint(QPainter.Antialiasing)
        
        # Draw App Name
        painter.setPen(QColor("white"))
        font = QFont("Segoe UI", 24, QFont.Bold)
        painter.setFont(font)
        
        # Center text
        text = "AEP Data Explorer"
        fm = painter.fontMetrics()
        text_width = fm.horizontalAdvance(text)
        text_height = fm.height()
        
        x = (width - text_width) // 2
        y = (height - text_height) // 2 + fm.ascent() - 10 # Slightly above center
        
        painter.drawText(x, y, text)
        
        # Draw "Loading..." placeholder
        font_small = QFont("Segoe UI", 10)
        painter.setFont(font_small)
        painter.drawText(20, height - 20, "Loading modules...")
        
        painter.end()
        
        self.setPixmap(pixmap)
        self.setWindowFlags(Qt.WindowStaysOnTopHint | Qt.FramelessWindowHint)

    def showMessage(self, message, alignment=Qt.AlignLeft, color=Qt.white):
        """Override to keep the custom drawing and just update the message area."""
        # We need to redraw the base red background and text, then the new message
        # Otherwise the default implementation might clear our custom drawing
        
        pixmap = self.pixmap()
        painter = QPainter(pixmap)
        
        # Clear bottom area for message
        adobe_red = QColor("#E1251B")
        painter.setPen(Qt.NoPen)
        painter.setBrush(QBrush(adobe_red))
        painter.drawRect(0, pixmap.height() - 40, pixmap.width(), 40)
        
        # Draw message
        painter.setPen(color)
        font = QFont("Segoe UI", 10)
        painter.setFont(font)
        painter.drawText(20, pixmap.height() - 20, message)
        
        painter.end()
        self.setPixmap(pixmap)
        self.repaint()
        QApplication.processEvents()

def show_splash():
    """Show Adobe-style red splash screen."""
    splash = AdobeStyleSplash()
    splash.show()
    QApplication.processEvents()
    return splash
