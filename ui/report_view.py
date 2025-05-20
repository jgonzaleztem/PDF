from PySide6.QtWidgets import (QWidget, QVBoxLayout, QHBoxLayout, QPushButton, 
                             QComboBox, QLabel, QFileDialog)
from PySide6.QtWebEngineWidgets import QWebEngineView
from PySide6.QtCore import QUrl, QTemporaryFile, QDir
from PySide6.QtGui import QDesktopServices

from loguru import logger
import os

class ReportView(QWidget):
    """
    Visor de informes de accesibilidad PDF/UA.
    
    Responsabilidades:
    - Mostrar informes HTML generados por PDFUAReporter
    - Permitir exportar en diferentes formatos
    - Facilitar navegación dentro del informe
    
    Relacionado con Matterhorn:
    - Visualiza todos los 31 checkpoints y sus condiciones de fallo
    """
    def __init__(self, parent=None):
        super().__init__(parent)
        self.report_content = ""
        self.report_file = None
        self.reporter = None
        self._init_ui()
        
    def _init_ui(self):
        main_layout = QVBoxLayout(self)
        
        # Barra de herramientas
        toolbar_layout = QHBoxLayout()
        
        # Selector de formato
        toolbar_layout.addWidget(QLabel("Formato:"))
        self.format_combo = QComboBox()
        self.format_combo.addItems(["HTML", "PDF", "Texto plano"])
        toolbar_layout.addWidget(self.format_combo)
        
        # Botón de exportación
        self.export_btn = QPushButton("Exportar informe")
        self.export_btn.clicked.connect(self._on_export_clicked)
        toolbar_layout.addWidget(self.export_btn)
        
        # Botón de impresión
        self.print_btn = QPushButton("Imprimir")
        self.print_btn.clicked.connect(self._on_print_clicked)
        toolbar_layout.addWidget(self.print_btn)
        
        toolbar_layout.addStretch()
        
        main_layout.addLayout(toolbar_layout)
        
        # Visor web
        self.web_view = QWebEngineView()
        main_layout.addWidget(self.web_view)
        
    def set_html_content(self, html_content):
        """Carga contenido HTML en el visor."""
        self.report_content = html_content
        
        # Crear archivo temporal para el HTML
        temp_file = QTemporaryFile(QDir.tempPath() + "/pdfua_report_XXXXXX.html")
        if temp_file.open():
            temp_file.write(html_content.encode('utf-8'))
            temp_file.close()
            
            # Guardar referencia al archivo temporal
            self.report_file = temp_file.fileName()
            
            # Cargar el archivo en el visor
            self.web_view.load(QUrl.fromLocalFile(self.report_file))
            logger.info(f"Informe cargado desde archivo temporal: {self.report_file}")
        else:
            logger.error("No se pudo crear archivo temporal para el informe HTML")
            # Cargar directamente como datos
            self.web_view.setHtml(html_content)
            
    def set_reporter(self, reporter):
        """Establece la instancia de PDFUAReporter para generar informes."""
        self.reporter = reporter
        
    def _on_export_clicked(self):
        """Maneja el clic en el botón de exportación."""
        if not self.reporter:
            logger.error("No hay reporter disponible para exportar")
            return
            
        # Determinar formato de exportación
        format_idx = self.format_combo.currentIndex()
        
        # Solicitar ubicación de guardado
        file_filter = ""
        if format_idx == 0:  # HTML
            file_filter = "Archivos HTML (*.html)"
            default_ext = ".html"
        elif format_idx == 1:  # PDF
            file_filter = "Archivos PDF (*.pdf)"
            default_ext = ".pdf"
        else:  # Texto plano
            file_filter = "Archivos de texto (*.txt)"
            default_ext = ".txt"
            
        file_path, _ = QFileDialog.getSaveFileName(
            self, "Guardar informe", 
            QDir.homePath() + "/informe_pdfua" + default_ext,
            file_filter
        )
        
        if not file_path:
            return
            
        try:
            # Generar y guardar informe según formato
            if format_idx == 0:  # HTML
                with open(file_path, 'w', encoding='utf-8') as f:
                    f.write(self.report_content)
            elif format_idx == 1:  # PDF
                if self.reporter:
                    self.reporter.generate_pdf_report(file_path)
                else:
                    logger.error("No se puede generar PDF sin reporter")
                    return
            else:  # Texto plano
                if self.reporter:
                    text_report = self.reporter.generate_text_report()
                    with open(file_path, 'w', encoding='utf-8') as f:
                        f.write(text_report)
                else:
                    logger.error("No se puede generar texto sin reporter")
                    return
                    
            logger.info(f"Informe exportado a {file_path}")
            
            # Abrir el archivo exportado
            QDesktopServices.openUrl(QUrl.fromLocalFile(file_path))
            
        except Exception as e:
            logger.error(f"Error al exportar informe: {str(e)}")
            
    def _on_print_clicked(self):
        """Maneja el clic en el botón de impresión."""
        if self.web_view:
            self.web_view.page().printToPdf(
                QDir.homePath() + "/informe_pdfua_impresion.pdf",
                lambda success: self._on_print_finished(success)
            )
            
    def _on_print_finished(self, success):
        """Callback cuando se completa la impresión a PDF."""
        if success:
            pdf_path = QDir.homePath() + "/informe_pdfua_impresion.pdf"
            logger.info(f"Informe impreso a PDF: {pdf_path}")
            QDesktopServices.openUrl(QUrl.fromLocalFile(pdf_path))
        else:
            logger.error("Error al imprimir informe")