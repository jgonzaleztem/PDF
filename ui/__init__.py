# pdfua_editor/ui/__init__.py
"""
Componentes de la interfaz gráfica de usuario (PySide6).
"""

from .main_window import MainWindow
from .pdf_viewer import PDFViewer
from .editor_view import EditorView
from .accessibility_wizard import AccessibilityWizard
from .report_view import ReportView
from .problems_panel import ProblemsPanel

__all__ = [
    "MainWindow",
    "PDFViewer",
    "EditorView",
    "AccessibilityWizard",
    "ReportView",
    "ProblemsPanel",
]