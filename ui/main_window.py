# pdfua_editor/ui/main_window.py

import os
import sys
from pathlib import Path
from typing import Dict, List, Optional, Any, Union

from PySide6.QtWidgets import (
    QMainWindow, QWidget, QVBoxLayout, QHBoxLayout, QToolBar, QFileDialog, QMessageBox, QDockWidget, QTabWidget, QSplitter, QStatusBar,
    QLabel, QSizePolicy, QComboBox, QToolButton, QMenu, QProgressDialog, QApplication
)
from PySide6.QtCore import Qt, QSize, QTimer, QSettings, Signal, Slot, QUrl
from PySide6.QtGui import QIcon, QDesktopServices, QAction
import qtawesome as qta
from loguru import logger

# Importar componentes de la interfaz
from ui.pdf_viewer import PDFViewer
from ui.editor_view import EditorView
from ui.problems_panel import ProblemsPanel
from ui.report_view import ReportView
from ui.accessibility_wizard import AccessibilityWizard

# Importar componentes del núcleo
from core.pdf_loader import PDFLoader
from core.pdf_writer import PDFWriter
from core.reporter import PDFUAReporter

# Importar manejador de estructura
from correcciones_manuales.structure_manager import StructureManager

# Correctores automáticos
from correcciones_automaticas.metadata_fixer import MetadataFixer
from correcciones_automaticas.images_fixer import ImagesFixer
from correcciones_automaticas.tables_fixer import TablesFixer
from correcciones_automaticas.lists_fixer import ListsFixer
from correcciones_automaticas.artifacts_fixer import ArtifactsFixer
from correcciones_automaticas.tags_fixer import TagsFixer
from correcciones_automaticas.link_fixer import LinkFixer
from correcciones_automaticas.reading_order import ReadingOrderFixer
from correcciones_automaticas.structure_generator import StructureGenerator
from correcciones_automaticas.forms_fixer import FormsFixer
from correcciones_automaticas.contrast_fixer import ContrastFixer

# Módulos para validación
from core.validator.metadata_validator import MetadataValidator
from core.validator.structure_validator import StructureValidator
from core.validator.tables_validator import TablesValidator
from core.validator.contrast_validator import ContrastValidator
from core.validator.language_validator import LanguageValidator
from core.validator.matterhorn_checker import MatterhornChecker

# Importar utilidades
from utils.ui_utils import (setup_logger, set_application_style, create_splash_screen,
                           create_dark_light_palette, get_theme_color, show_error_message,
                           show_info_message, show_warning_message, show_question_message)

class MainWindow(QMainWindow):
    """
    Ventana principal de la aplicación PDF/UA Editor.
    Coordina todos los componentes y funcionalidades para la edición y corrección
    de documentos PDF accesibles según el estándar PDF/UA.
    """
    
    # Señales
    documentLoaded = Signal(bool)  # True si se cargó correctamente
    documentSaved = Signal(str)    # Ruta donde se guardó
    validationCompleted = Signal(list)  # Lista de problemas encontrados
    
    def __init__(self):
        """Inicializa la ventana principal."""
        super().__init__()
        
        # Inicializar componentes core
        self.pdf_loader = PDFLoader()
        self.pdf_writer = PDFWriter()
        self.pdf_writer.set_pdf_loader(self.pdf_loader)
        self.structure_manager = StructureManager()
        self.structure_manager.set_pdf_loader(self.pdf_loader)
        self.reporter = PDFUAReporter()
        
        # Inicializar validadores
        self.metadata_validator = MetadataValidator()
        self.structure_validator = StructureValidator()
        self.tables_validator = TablesValidator()
        self.contrast_validator = ContrastValidator()
        self.language_validator = LanguageValidator()
        self.matterhorn_checker = MatterhornChecker()
        
        # Inicializar correctores automáticos
        self.metadata_fixer = MetadataFixer(self.pdf_writer)
        self.images_fixer = ImagesFixer(self.pdf_writer)
        self.tables_fixer = TablesFixer(self.pdf_writer)
        self.lists_fixer = ListsFixer(self.pdf_writer)
        self.artifacts_fixer = ArtifactsFixer(self.pdf_writer)
        self.tags_fixer = TagsFixer(self.pdf_writer)
        self.link_fixer = LinkFixer(self.pdf_writer)
        self.reading_order_fixer = ReadingOrderFixer(self.pdf_writer)
        self.structure_generator = StructureGenerator(self.pdf_writer)
        self.forms_fixer = FormsFixer(self.pdf_writer)
        self.contrast_fixer = ContrastFixer(self.pdf_writer)
        
        # Variables de estado
        self.current_file_path = None
        self.has_unsaved_changes = False
        
        # Configurar la interfaz
        self._setup_ui()
        
        # Cargar configuración
        self._load_settings()
        
        logger.info("MainWindow inicializada")

    def _setup_ui(self):
        """Configura la interfaz de usuario."""
        # Configurar ventana
        self.setWindowTitle("PDF/UA Editor")
        self.setMinimumSize(1200, 800)
        
        # Crear widgets centrales
        self.central_widget = QWidget()
        self.central_layout = QHBoxLayout(self.central_widget)
        self.central_layout.setContentsMargins(0, 0, 0, 0)
        self.setCentralWidget(self.central_widget)
        
        # Crear splitter principal
        self.main_splitter = QSplitter(Qt.Horizontal)
        self.central_layout.addWidget(self.main_splitter)
        
        # Panel de edición (izquierda)
        self.editor_view = EditorView()
        self.editor_view.set_structure_manager(self.structure_manager)
        self.main_splitter.addWidget(self.editor_view)
        
        # Visor de PDF (derecha)
        self.pdf_viewer = PDFViewer()
        self.main_splitter.addWidget(self.pdf_viewer)
        
        # Establecer proporciones iniciales
        self.main_splitter.setSizes([400, 800])
        
        # Crear dock para problemas
        self.problems_dock = QDockWidget("Problemas de accesibilidad", self)
        self.problems_dock.setAllowedAreas(Qt.BottomDockWidgetArea)
        self.problems_panel = ProblemsPanel()
        self.problems_dock.setWidget(self.problems_panel)
        self.addDockWidget(Qt.BottomDockWidgetArea, self.problems_dock)
        
        # Crear dock para informe
        self.report_dock = QDockWidget("Informe de conformidad", self)
        self.report_dock.setAllowedAreas(Qt.RightDockWidgetArea)
        self.report_view = ReportView()
        self.report_view.set_reporter(self.reporter)
        self.report_dock.setWidget(self.report_view)
        self.addDockWidget(Qt.RightDockWidgetArea, self.report_dock)
        self.report_dock.hide()  # Inicialmente oculto
        
        # Configurar barra de herramientas
        self._setup_toolbar()
        
        # Configurar menús
        self._setup_menus()
        
        # Configurar barra de estado
        self._setup_statusbar()
        
        # Conectar señales
        self._connect_signals()

    def _setup_toolbar(self):
        """Configura la barra de herramientas."""
        # Barra de herramientas principal
        self.main_toolbar = QToolBar("Herramientas principales")
        self.main_toolbar.setIconSize(QSize(24, 24))
        self.main_toolbar.setMovable(False)
        self.addToolBar(self.main_toolbar)
        
        # Acciones de archivo
        self.action_open = QAction(qta.icon("fa5s.folder-open"), "Abrir", self)
        self.action_open.setStatusTip("Abrir un archivo PDF")
        self.action_open.triggered.connect(self._on_open_file)
        self.main_toolbar.addAction(self.action_open)
        
        self.action_save = QAction(qta.icon("fa5s.save"), "Guardar", self)
        self.action_save.setStatusTip("Guardar cambios en el PDF")
        self.action_save.triggered.connect(self._on_save_file)
        self.action_save.setEnabled(False)
        self.main_toolbar.addAction(self.action_save)
        
        self.action_save_as = QAction(qta.icon("fa5s.file-export"), "Guardar como", self)
        self.action_save_as.setStatusTip("Guardar como un nuevo archivo PDF")
        self.action_save_as.triggered.connect(self._on_save_file_as)
        self.action_save_as.setEnabled(False)
        self.main_toolbar.addAction(self.action_save_as)
        
        self.main_toolbar.addSeparator()
        
        # Acciones de análisis
        self.action_analyze = QAction(qta.icon("fa5s.search"), "Analizar", self)
        self.action_analyze.setStatusTip("Analizar accesibilidad del documento")
        self.action_analyze.triggered.connect(self._on_analyze_document)
        self.action_analyze.setEnabled(False)
        self.main_toolbar.addAction(self.action_analyze)
        
        self.action_report = QAction(qta.icon("fa5s.file-alt"), "Generar informe", self)
        self.action_report.setStatusTip("Generar informe de conformidad PDF/UA")
        self.action_report.triggered.connect(self._on_generate_report)
        self.action_report.setEnabled(False)
        self.main_toolbar.addAction(self.action_report)
        
        self.main_toolbar.addSeparator()
        
        # Acciones de corrección
        self.action_fix_all = QAction(qta.icon("fa5s.magic"), "Reparar todo", self)
        self.action_fix_all.setStatusTip("Aplicar todas las correcciones automáticas")
        self.action_fix_all.triggered.connect(self._on_fix_all)
        self.action_fix_all.setEnabled(False)
        self.main_toolbar.addAction(self.action_fix_all)
        
        # Menú desplegable para correctores específicos
        self.fix_menu_button = QToolButton()
        self.fix_menu_button.setIcon(qta.icon("fa5s.tools"))
        self.fix_menu_button.setText("Reparar...")
        self.fix_menu_button.setToolTip("Aplicar correcciones específicas")
        self.fix_menu_button.setPopupMode(QToolButton.InstantPopup)
        self.fix_menu = QMenu()
        
        # Acciones de corrección específicas
        self.action_fix_metadata = QAction("Metadatos", self)
        self.action_fix_metadata.triggered.connect(self._on_fix_metadata)
        self.fix_menu.addAction(self.action_fix_metadata)
        
        self.action_fix_images = QAction("Imágenes", self)
        self.action_fix_images.triggered.connect(self._on_fix_images)
        self.fix_menu.addAction(self.action_fix_images)
        
        self.action_fix_tables = QAction("Tablas", self)
        self.action_fix_tables.triggered.connect(self._on_fix_tables)
        self.fix_menu.addAction(self.action_fix_tables)
        
        self.action_fix_lists = QAction("Listas", self)
        self.action_fix_lists.triggered.connect(self._on_fix_lists)
        self.fix_menu.addAction(self.action_fix_lists)
        
        self.action_fix_artifacts = QAction("Artefactos", self)
        self.action_fix_artifacts.triggered.connect(self._on_fix_artifacts)
        self.fix_menu.addAction(self.action_fix_artifacts)
        
        self.action_fix_tags = QAction("Etiquetas", self)
        self.action_fix_tags.triggered.connect(self._on_fix_tags)
        self.fix_menu.addAction(self.action_fix_tags)
        
        self.action_fix_links = QAction("Enlaces", self)
        self.action_fix_links.triggered.connect(self._on_fix_links)
        self.fix_menu.addAction(self.action_fix_links)
        
        self.action_fix_reading_order = QAction("Orden de lectura", self)
        self.action_fix_reading_order.triggered.connect(self._on_fix_reading_order)
        self.fix_menu.addAction(self.action_fix_reading_order)
        
        self.action_fix_forms = QAction("Formularios", self)
        self.action_fix_forms.triggered.connect(self._on_fix_forms)
        self.fix_menu.addAction(self.action_fix_forms)
        
        self.action_fix_contrast = QAction("Contraste", self)
        self.action_fix_contrast.triggered.connect(self._on_fix_contrast)
        self.fix_menu.addAction(self.action_fix_contrast)
        
        self.fix_menu.addSeparator()
        
        self.action_structure_generator = QAction("Generar estructura", self)
        self.action_structure_generator.triggered.connect(self._on_generate_structure)
        self.fix_menu.addAction(self.action_structure_generator)
        
        self.fix_menu_button.setMenu(self.fix_menu)
        self.fix_menu_button.setEnabled(False)
        self.main_toolbar.addWidget(self.fix_menu_button)
        
        self.main_toolbar.addSeparator()
        
        # Acciones de asistente
        self.action_wizard = QAction(qta.icon("fa5s.magic"), "Asistente de accesibilidad", self)
        self.action_wizard.setStatusTip("Abrir asistente paso a paso de accesibilidad")
        self.action_wizard.triggered.connect(self._on_open_wizard)
        self.action_wizard.setEnabled(False)
        self.main_toolbar.addAction(self.action_wizard)

    def _setup_menus(self):
        """Configura los menús de la aplicación."""
        # Menú Archivo
        file_menu = self.menuBar().addMenu("&Archivo")
        file_menu.addAction(self.action_open)
        file_menu.addAction(self.action_save)
        file_menu.addAction(self.action_save_as)
        file_menu.addSeparator()
        
        self.action_export_report = QAction("&Exportar informe...", self)
        self.action_export_report.setStatusTip("Exportar informe de conformidad")
        self.action_export_report.triggered.connect(self._on_export_report)
        self.action_export_report.setEnabled(False)
        file_menu.addAction(self.action_export_report)
        
        file_menu.addSeparator()
        
        self.action_exit = QAction("&Salir", self)
        self.action_exit.setStatusTip("Salir de la aplicación")
        self.action_exit.triggered.connect(self.close)
        file_menu.addAction(self.action_exit)
        
        # Menú Editar
        edit_menu = self.menuBar().addMenu("&Editar")
        
        self.action_undo = QAction(qta.icon("fa5s.undo"), "&Deshacer", self)
        self.action_undo.setStatusTip("Deshacer último cambio")
        self.action_undo.triggered.connect(self._on_undo)
        self.action_undo.setEnabled(False)
        edit_menu.addAction(self.action_undo)
        
        self.action_redo = QAction(qta.icon("fa5s.redo"), "&Rehacer", self)
        self.action_redo.setStatusTip("Rehacer último cambio deshecho")
        self.action_redo.triggered.connect(self._on_redo)
        self.action_redo.setEnabled(False)
        edit_menu.addAction(self.action_redo)
        
        edit_menu.addSeparator()
        
        self.action_apply_changes = QAction(qta.icon("fa5s.check"), "&Aplicar cambios", self)
        self.action_apply_changes.setStatusTip("Aplicar cambios realizados")
        self.action_apply_changes.triggered.connect(self._on_apply_changes)
        self.action_apply_changes.setEnabled(False)
        edit_menu.addAction(self.action_apply_changes)
        
        # Menú Ver
        view_menu = self.menuBar().addMenu("&Ver")
        
        self.action_toggle_problems = self.problems_dock.toggleViewAction()
        self.action_toggle_problems.setText("Panel de problemas")
        self.action_toggle_problems.setStatusTip("Mostrar/ocultar panel de problemas")
        view_menu.addAction(self.action_toggle_problems)
        
        self.action_toggle_report = self.report_dock.toggleViewAction()
        self.action_toggle_report.setText("Informe de conformidad")
        self.action_toggle_report.setStatusTip("Mostrar/ocultar informe de conformidad")
        view_menu.addAction(self.action_toggle_report)
        
        view_menu.addSeparator()
        
        self.action_zoom_in = QAction(qta.icon("fa5s.search-plus"), "Acercar", self)
        self.action_zoom_in.setStatusTip("Aumentar zoom del documento")
        self.action_zoom_in.triggered.connect(self._on_zoom_in)
        view_menu.addAction(self.action_zoom_in)
        
        self.action_zoom_out = QAction(qta.icon("fa5s.search-minus"), "Alejar", self)
        self.action_zoom_out.setStatusTip("Disminuir zoom del documento")
        self.action_zoom_out.triggered.connect(self._on_zoom_out)
        view_menu.addAction(self.action_zoom_out)
        
        # Menú Herramientas
        tools_menu = self.menuBar().addMenu("&Herramientas")
        tools_menu.addAction(self.action_analyze)
        tools_menu.addAction(self.action_report)
        tools_menu.addSeparator()
        tools_menu.addAction(self.action_fix_all)
        
        fix_submenu = tools_menu.addMenu("Reparar específico")
        for action in self.fix_menu.actions():
            fix_submenu.addAction(action)
        
        tools_menu.addSeparator()
        tools_menu.addAction(self.action_wizard)
        tools_menu = self.menuBar().findChild(QMenu, "tools_menu")
        if tools_menu:
            tools_menu.addSeparator()
        
            self.action_optimize = QAction("Optimizar PDF", self)
            self.action_optimize.setStatusTip("Optimizar el PDF para reducir tamaño")
            self.action_optimize.triggered.connect(self.optimize_pdf)
            self.action_optimize.setEnabled(False)
            tools_menu.addAction(self.action_optimize)
        
            self.action_check_conformance = QAction("Verificar conformidad PDF/UA", self)
            self.action_check_conformance.setStatusTip("Realizar una verificación completa de conformidad PDF/UA")
            self.action_check_conformance.triggered.connect(self.check_conformance)
            self.action_check_conformance.setEnabled(False)
            tools_menu.addAction(self.action_check_conformance)
        
        # Menú Ayuda
        help_menu = self.menuBar().addMenu("A&yuda")
        
        self.action_doc_matterhorn = QAction("Protocolo Matterhorn", self)
        self.action_doc_matterhorn.setStatusTip("Abrir documentación de Matterhorn Protocol")
        self.action_doc_matterhorn.triggered.connect(lambda: self._open_documentation("matterhorn"))
        help_menu.addAction(self.action_doc_matterhorn)
        
        self.action_doc_tagged_pdf = QAction("Tagged PDF Best Practice", self)
        self.action_doc_tagged_pdf.setStatusTip("Abrir documentación de Tagged PDF Best Practice")
        self.action_doc_tagged_pdf.triggered.connect(lambda: self._open_documentation("tagged_pdf"))
        help_menu.addAction(self.action_doc_tagged_pdf)
        
        help_menu.addSeparator()
        
        self.action_about = QAction("&Acerca de", self)
        self.action_about.setStatusTip("Información sobre la aplicación")
        self.action_about.triggered.connect(self._on_about)
        help_menu.addAction(self.action_about)
        
        

    def _setup_statusbar(self):
        """Configura la barra de estado."""
        self.statusbar = QStatusBar()
        self.setStatusBar(self.statusbar)
        
        # Etiqueta de estado
        self.status_label = QLabel("Listo")
        self.statusbar.addWidget(self.status_label, 1)
        
        # Etiqueta de página actual
        self.page_label = QLabel("Página: -/-")
        self.statusbar.addPermanentWidget(self.page_label)
        
        # Selector de zoom
        self.zoom_combo = QComboBox()
        self.zoom_combo.addItems(["25%", "50%", "75%", "100%", "125%", "150%", "200%", "Ajustar a ventana"])
        self.zoom_combo.setCurrentText("100%")
        self.zoom_combo.currentTextChanged.connect(self._on_zoom_changed)
        self.statusbar.addPermanentWidget(self.zoom_combo)

    def _connect_signals(self):
        """Conecta señales entre componentes."""
        # Visor de PDF
        self.pdf_viewer.pageChanged.connect(self._on_page_changed)
        self.pdf_viewer.elementSelected.connect(self._on_element_selected)

        # Editor
        self.editor_view.structureChanged.connect(self._on_structure_changed)
        self.editor_view.nodeSelected.connect(self._on_node_selected)

        # Panel de problemas
        self.problems_panel.problemSelected.connect(self._on_problem_selected)
        self.problems_panel.fixRequested.connect(self._on_fix_requested)

    def _on_open_file(self):
        """Manejador para abrir un archivo."""
        # Verificar cambios no guardados
        if self.has_unsaved_changes:
            response = QMessageBox.question(
                self,
                "Cambios no guardados",
                "Hay cambios sin guardar. ¿Desea guardarlos antes de abrir otro archivo?",
                QMessageBox.Save | QMessageBox.Discard | QMessageBox.Cancel,
                QMessageBox.Save
            )
            
            if response == QMessageBox.Save:
                if not self._on_save_file():
                    return  # Cancelar si no se pudo guardar
            elif response == QMessageBox.Cancel:
                return  # Cancelar apertura
        
        # Seleccionar archivo
        file_path, _ = QFileDialog.getOpenFileName(
            self,
            "Abrir archivo PDF",
            "",
            "Archivos PDF (*.pdf)"
        )
        
        if not file_path:
            return
        
        # Cargar archivo
        self._load_file(file_path)

    def _load_file(self, file_path: str) -> bool:
        """
        Carga un archivo PDF utilizando múltiples bibliotecas para diferentes
        aspectos de análisis.

        Args:
            file_path: Ruta al archivo PDF a cargar
        
        Returns:
            bool: True si la carga es exitosa
        """
        try:
            # Mostrar diálogo de progreso
            progress = QProgressDialog("Cargando documento...", "Cancelar", 0, 100, self)
            progress.setWindowTitle("Cargando")
            progress.setWindowModality(Qt.WindowModal)
            progress.setValue(10)
            progress.show()
        
            # Cargar el documento
            if not self.pdf_loader.load_document(file_path):
                QMessageBox.critical(self, "Error", "No se pudo cargar el documento PDF.")
                progress.close()
                return False
        
            progress.setValue(40)
        
            # Actualizar referencias en los componentes
            self.pdf_writer.set_pdf_loader(self.pdf_loader)
            self.structure_manager.set_pdf_loader(self.pdf_loader)
        
            # Establecer la referencia al PDF en los validadores
            self.metadata_validator.set_pdf_loader(self.pdf_loader)
            self.structure_validator.set_pdf_loader(self.pdf_loader)
            self.tables_validator.set_pdf_loader(self.pdf_loader)
            self.contrast_validator.set_pdf_loader(self.pdf_loader)
            self.language_validator.set_pdf_loader(self.pdf_loader)
        
            progress.setValue(60)
            
            # Mostrar en visor
            progress.setValue(80)
            self.pdf_viewer.load_document(self.pdf_loader.doc)
        
            # Actualizar editor con estructura
            self.editor_view.set_structure_manager(self.structure_manager)
            self.editor_view.refresh_structure_view()
            
            # Actualizar estado de la aplicación
            self.current_file_path = file_path
            self.has_unsaved_changes = False
            self.setWindowTitle(f"PDF/UA Editor - {os.path.basename(file_path)}")
            
            # Habilitar acciones
            self._update_ui_state(True)
            
            # Actualizar información del documento
            document_info = {
                "filename": os.path.basename(file_path),
                "path": file_path,
                "pages": self.pdf_loader.page_count,
                "has_structure": self.pdf_loader.structure_tree is not None,
                "metadata": self.pdf_loader.get_metadata() if hasattr(self.pdf_loader, "get_metadata") else {}
            }
            
            # Mostrar mensaje en la barra de estado
            self.status_label.setText(f"Documento cargado: {os.path.basename(file_path)}")
            
            progress.setValue(100)
            progress.close()
            
            # Analizar automáticamente
            QTimer.singleShot(100, self._on_analyze_document)
            
            return True
            
        except Exception as e:
            progress.close()
            logger.exception(f"Error al cargar archivo: {e}")
            QMessageBox.critical(self, "Error", f"Error al cargar el documento: {str(e)}")
            return False

    def _on_save_file(self) -> bool:
        """
        Manejador para guardar el archivo actual.
        
        Returns:
            bool: True si se guardó correctamente
        """
        if not self.current_file_path:
            return self._on_save_file_as()
        
        return self._save_file(self.current_file_path)

    def _on_save_file_as(self) -> bool:
        """
        Manejador para guardar como un nuevo archivo.
        
        Returns:
            bool: True si se guardó correctamente
        """
        # Seleccionar ubicación para guardar
        file_path, _ = QFileDialog.getSaveFileName(
            self,
            "Guardar como",
            self.current_file_path if self.current_file_path else "",
            "Archivos PDF (*.pdf)"
        )
        
        if not file_path:
            return False
        
        # Asegurar extensión .pdf
        if not file_path.lower().endswith(".pdf"):
            file_path += ".pdf"
        
        return self._save_file(file_path)

    def _save_file(self, file_path: str) -> bool:
        """
        Guarda el archivo en la ubicación especificada.
        
        Args:
            file_path: Ruta donde guardar el archivo
            
        Returns:
            bool: True si se guardó correctamente
        """
        # Mostrar diálogo de progreso
        progress = QProgressDialog("Guardando documento...", "Cancelar", 0, 100, self)
        progress.setWindowTitle("Guardando")
        progress.setWindowModality(Qt.WindowModal)
        progress.setValue(10)
        progress.show()
        
        try:
            # Aplicar todos los cambios pendientes
            if self.structure_manager:
                self.structure_manager.apply_changes()
            
            progress.setValue(50)
            
            # Guardar el documento
            if not self.pdf_writer.save_document(file_path):
                QMessageBox.critical(self, "Error", "No se pudo guardar el documento.")
                progress.close()
                return False
            
            progress.setValue(90)
            
            # Actualizar estado
            self.current_file_path = file_path
            self.has_unsaved_changes = False
            self.setWindowTitle(f"PDF/UA Editor - {os.path.basename(file_path)}")
            
            # Actualizar mensaje en la barra de estado
            self.status_label.setText(f"Documento guardado: {os.path.basename(file_path)}")
            
            progress.setValue(100)
            progress.close()
            
            return True
            
        except Exception as e:
            progress.close()
            logger.exception(f"Error al guardar archivo: {e}")
            QMessageBox.critical(self, "Error", f"Error al guardar el documento: {str(e)}")
            return False

    def _on_analyze_document(self):
        """Manejador para analizar el documento."""
        if not self.pdf_loader:
            return
        
        # Mostrar diálogo de progreso
        progress = QProgressDialog("Analizando documento...", "Cancelar", 0, 100, self)
        progress.setWindowTitle("Analizando")
        progress.setWindowModality(Qt.WindowModal)
        progress.setValue(10)
        progress.show()
        
        try:
            # Recopilar problemas de todos los validadores
            issues = []
            
            # Obtener metadatos del documento
            metadata = self.pdf_loader.get_metadata() if hasattr(self.pdf_loader, "get_metadata") else {}
            
            # Validar metadatos
            progress.setValue(20)
            metadata_issues = self.metadata_validator.validate(metadata)
            issues.extend(metadata_issues)
            
            # Validar estructura
            progress.setValue(40)
            if self.pdf_loader.structure_tree:
                structure_issues = self.structure_validator.validate(self.pdf_loader.structure_tree)
                issues.extend(structure_issues)
                
                # Validar tablas
                tables_issues = self.tables_validator.validate(self.pdf_loader.structure_tree)
                issues.extend(tables_issues)
            else:
                # No hay estructura, reportar problema general
                issues.append({
                    "checkpoint": "01-005",
                    "severity": "error",
                    "description": "El documento no contiene estructura lógica",
                    "fix_description": "Generar estructura lógica para el documento",
                    "fixable": True,
                    "page": "all"
                })
            
            # Validar contraste
            progress.setValue(60)
            contrast_issues = self.contrast_validator.validate(self.pdf_loader)
            issues.extend(contrast_issues)
            
            # Validar idioma
            progress.setValue(80)
            language_issues = self.language_validator.validate(
                metadata,
                self.pdf_loader.structure_tree
            )
            issues.extend(language_issues)
            
            # Categorizar por Matterhorn
            issues_by_checkpoint = self.matterhorn_checker.categorize_issues(issues)
            
            # Actualizar panel de problemas
            self.problems_panel.set_issues(issues)
            
            # Mostrar panel de problemas
            self.problems_dock.show()
            
            # Habilitar acciones
            self.action_report.setEnabled(True)
            self.action_export_report.setEnabled(True)
            
            # Guardar problemas para informe
            self.reporter.set_document_info({
                "filename": os.path.basename(self.current_file_path) if self.current_file_path else "Sin título",
                "path": self.current_file_path,
                "pages": self.pdf_loader.page_count,
                "has_structure": self.pdf_loader.structure_tree is not None
            })
            self.reporter.add_issues(issues)
            
            # Actualizar mensaje en la barra de estado
            error_count = len([i for i in issues if i.get("severity") == "error"])
            warning_count = len([i for i in issues if i.get("severity") == "warning"])
            
            self.status_label.setText(
                f"Análisis completado: {error_count} errores, {warning_count} advertencias"
            )
            
            progress.setValue(100)
            progress.close()
            
        except Exception as e:
            progress.close()
            logger.exception(f"Error al analizar documento: {e}")
            QMessageBox.critical(self, "Error", f"Error al analizar el documento: {str(e)}")

    def _on_generate_report(self):
        """Manejador para generar informe de conformidad."""
        if not self.reporter:
            return
        
        try:
            # Generar resumen
            self.reporter.generate_summary()
            
            # Generar informe HTML
            html_content = self.reporter.generate_html_report()
            
            # Mostrar en el visor de informe
            self.report_view.set_html_content(html_content)
            
            # Mostrar dock de informe
            self.report_dock.show()
            
        except Exception as e:
            logger.exception(f"Error al generar informe: {e}")
            QMessageBox.critical(self, "Error", f"Error al generar informe: {str(e)}")

    def _on_export_report(self):
        """Manejador para exportar informe."""
        if not self.reporter:
            return
        
        # Seleccionar formato y ubicación
        file_path, selected_filter = QFileDialog.getSaveFileName(
            self,
            "Exportar informe",
            f"{os.path.splitext(os.path.basename(self.current_file_path))[0]}_informe" if self.current_file_path else "informe",
            "Documentos PDF (*.pdf);;Documentos HTML (*.html);;Archivos de texto (*.txt);;Archivos JSON (*.json)"
        )
        
        if not file_path:
            return
        
        # Determinar formato según filtro seleccionado
        if "PDF" in selected_filter:
            # Asegurar extensión
            if not file_path.lower().endswith(".pdf"):
                file_path += ".pdf"
            
            # Generar PDF
            result = self.reporter.generate_pdf_report(file_path)
            format_name = "PDF"
            
        elif "HTML" in selected_filter:
            # Asegurar extensión
            if not file_path.lower().endswith(".html"):
                file_path += ".html"
            
            # Generar HTML
            html_content = self.reporter.generate_html_report(file_path)
            result = bool(html_content)
            format_name = "HTML"
            
        elif "texto" in selected_filter:
            # Asegurar extensión
            if not file_path.lower().endswith(".txt"):
                file_path += ".txt"
            
            # Generar texto
            text_content = self.reporter.generate_text_report(file_path)
            result = bool(text_content)
            format_name = "texto"
            
        elif "JSON" in selected_filter:
            # Asegurar extensión
            if not file_path.lower().endswith(".json"):
                file_path += ".json"
            
            # Exportar JSON
            result = self.reporter.export_json(file_path)
            format_name = "JSON"
            
        else:
            QMessageBox.warning(self, "Formato no soportado", "El formato seleccionado no es compatible.")
            return
        
        # Mostrar resultado
        if result:
            QMessageBox.information(
                self,
                "Exportación exitosa",
                f"El informe se ha exportado correctamente en formato {format_name}:\n{file_path}"
            )
        else:
            QMessageBox.critical(
                self,
                "Error de exportación",
                f"No se pudo exportar el informe en formato {format_name}."
            )

    def _on_fix_all(self):
        """Manejador para aplicar todas las correcciones automáticas."""
        if not self.pdf_loader or not self.pdf_writer:
            return
        
        # Mostrar confirmación
        response = QMessageBox.question(
            self,
            "Aplicar todas las correcciones",
            "¿Desea aplicar todas las correcciones automáticas disponibles?\n\n"
            "Esto intentará corregir metadatos, imágenes, tablas, listas, artefactos, etiquetas y más.",
            QMessageBox.Yes | QMessageBox.No,
            QMessageBox.Yes
        )
        
        if response != QMessageBox.Yes:
            return
        
        # Mostrar diálogo de progreso
        progress = QProgressDialog("Aplicando correcciones...", "Cancelar", 0, 100, self)
        progress.setWindowTitle("Reparando")
        progress.setWindowModality(Qt.WindowModal)
        progress.setValue(10)
        progress.show()
        
        try:
            # Verificar si el documento tiene estructura
            if not self.pdf_loader.structure_tree:
                progress.setLabelText("Generando estructura lógica...")
                self.structure_generator.generate_structure(self.pdf_loader)
            
            # Obtener metadatos del documento
            metadata = self.pdf_loader.get_metadata() if hasattr(self.pdf_loader, "get_metadata") else {}
            
            # Aplicar correcciones
            progress.setLabelText("Corrigiendo metadatos...")
            progress.setValue(20)
            self.metadata_fixer.fix_all_metadata(metadata, os.path.basename(self.current_file_path))
            
            progress.setLabelText("Corrigiendo imágenes...")
            progress.setValue(30)
            self.images_fixer.fix_all_images(self.pdf_loader.structure_tree)
            
            progress.setLabelText("Corrigiendo tablas...")
            progress.setValue(40)
            self.tables_fixer.fix_all_tables(self.pdf_loader.structure_tree)
            
            progress.setLabelText("Corrigiendo listas...")
            progress.setValue(50)
            self.lists_fixer.fix_all_lists(self.pdf_loader.structure_tree)
            
            progress.setLabelText("Corrigiendo artefactos...")
            progress.setValue(60)
            self.artifacts_fixer.fix_all_artifacts(self.pdf_loader)
            
            progress.setLabelText("Corrigiendo etiquetas...")
            progress.setValue(70)
            self.tags_fixer.fix_all_tags(self.pdf_loader.structure_tree, self.pdf_loader)
            
            progress.setLabelText("Corrigiendo enlaces...")
            progress.setValue(80)
            self.link_fixer.fix_all_links(self.pdf_loader.structure_tree, self.pdf_loader)
            
            progress.setLabelText("Corrigiendo orden de lectura...")
            progress.setValue(90)
            self.reading_order_fixer.fix_reading_order(self.pdf_loader.structure_tree, self.pdf_loader)
            
            # Actualizar UI
            self.editor_view.refresh_structure_view()
            self.has_unsaved_changes = True
            
            # Actualizar mensaje en la barra de estado
            self.status_label.setText("Correcciones automáticas aplicadas")
            
            progress.setValue(100)
            progress.close()
            
            # Reanalizar
            QTimer.singleShot(100, self._on_analyze_document)
            
        except Exception as e:
            progress.close()
            logger.exception(f"Error al aplicar correcciones: {e}")
            QMessageBox.critical(self, "Error", f"Error al aplicar correcciones: {str(e)}")

    def _on_fix_metadata(self):
        """Manejador para corregir metadatos."""
        if not self.metadata_fixer:
            return
        
        try:
            metadata = self.pdf_loader.get_metadata() if hasattr(self.pdf_loader, "get_metadata") else {}
            result = self.metadata_fixer.fix_all_metadata(
                metadata,
                os.path.basename(self.current_file_path)
            )
            
            if result:
                self.has_unsaved_changes = True
                self.status_label.setText("Metadatos corregidos")
                QMessageBox.information(self, "Corrección completada", "Los metadatos se han corregido correctamente.")
            else:
                QMessageBox.information(self, "Sin cambios", "No fue necesario corregir los metadatos.")
            
        except Exception as e:
            logger.exception(f"Error al corregir metadatos: {e}")
            QMessageBox.critical(self, "Error", f"Error al corregir metadatos: {str(e)}")

    def _on_fix_images(self):
        """Manejador para corregir imágenes."""
        if not self.images_fixer or not self.pdf_loader.structure_tree:
            QMessageBox.warning(self, "No hay estructura", "El documento no tiene estructura para corregir imágenes.")
            return
        
        try:
            result = self.images_fixer.fix_all_images(self.pdf_loader.structure_tree)
            
            if result:
                self.has_unsaved_changes = True
                self.status_label.setText("Imágenes corregidas")
                self.editor_view.refresh_structure_view()
                QMessageBox.information(self, "Corrección completada", "Las imágenes se han corregido correctamente.")
            else:
                QMessageBox.information(self, "Sin cambios", "No fue necesario corregir las imágenes.")
            
        except Exception as e:
            logger.exception(f"Error al corregir imágenes: {e}")
            QMessageBox.critical(self, "Error", f"Error al corregir imágenes: {str(e)}")

    def _on_fix_tables(self):
        """Manejador para corregir tablas."""
        if not self.tables_fixer or not self.pdf_loader.structure_tree:
            QMessageBox.warning(self, "No hay estructura", "El documento no tiene estructura para corregir tablas.")
            return
        
        try:
            result = self.tables_fixer.fix_all_tables(self.pdf_loader.structure_tree)
            
            if result:
                self.has_unsaved_changes = True
                self.status_label.setText("Tablas corregidas")
                self.editor_view.refresh_structure_view()
                QMessageBox.information(self, "Corrección completada", "Las tablas se han corregido correctamente.")
            else:
                QMessageBox.information(self, "Sin cambios", "No fue necesario corregir las tablas.")
            
        except Exception as e:
            logger.exception(f"Error al corregir tablas: {e}")
            QMessageBox.critical(self, "Error", f"Error al corregir tablas: {str(e)}")

    def _on_fix_lists(self):
        """Manejador para corregir listas."""
        if not self.lists_fixer or not self.pdf_loader.structure_tree:
            QMessageBox.warning(self, "No hay estructura", "El documento no tiene estructura para corregir listas.")
            return
        
        try:
            result = self.lists_fixer.fix_all_lists(self.pdf_loader.structure_tree)
            
            if result:
                self.has_unsaved_changes = True
                self.status_label.setText("Listas corregidas")
                self.editor_view.refresh_structure_view()
                QMessageBox.information(self, "Corrección completada", "Las listas se han corregido correctamente.")
            else:
                QMessageBox.information(self, "Sin cambios", "No fue necesario corregir las listas.")
            
        except Exception as e:
            logger.exception(f"Error al corregir listas: {e}")
            QMessageBox.critical(self, "Error", f"Error al corregir listas: {str(e)}")

    def _on_fix_artifacts(self):
        """Manejador para corregir artefactos."""
        if not self.artifacts_fixer:
            return
        
        try:
            result = self.artifacts_fixer.fix_all_artifacts(self.pdf_loader)
            
            if result:
                self.has_unsaved_changes = True
                self.status_label.setText("Artefactos corregidos")
                self.editor_view.refresh_structure_view()
                QMessageBox.information(self, "Corrección completada", "Los artefactos se han corregido correctamente.")
            else:
                QMessageBox.information(self, "Sin cambios", "No fue necesario corregir los artefactos.")
            
        except Exception as e:
            logger.exception(f"Error al corregir artefactos: {e}")
            QMessageBox.critical(self, "Error", f"Error al corregir artefactos: {str(e)}")

    def _on_fix_tags(self):
        """Manejador para corregir etiquetas."""
        if not self.tags_fixer or not self.pdf_loader.structure_tree:
            QMessageBox.warning(self, "No hay estructura", "El documento no tiene estructura para corregir etiquetas.")
            return
        
        try:
            result = self.tags_fixer.fix_all_tags(self.pdf_loader.structure_tree, self.pdf_loader)
            
            if result:
                self.has_unsaved_changes = True
                self.status_label.setText("Etiquetas corregidas")
                self.editor_view.refresh_structure_view()
                QMessageBox.information(self, "Corrección completada", "Las etiquetas se han corregido correctamente.")
            else:
                QMessageBox.information(self, "Sin cambios", "No fue necesario corregir las etiquetas.")
            
        except Exception as e:
            logger.exception(f"Error al corregir etiquetas: {e}")
            QMessageBox.critical(self, "Error", f"Error al corregir etiquetas: {str(e)}")

    def _on_fix_links(self):
        """Manejador para corregir enlaces."""
        if not self.link_fixer or not self.pdf_loader.structure_tree:
            QMessageBox.warning(self, "No hay estructura", "El documento no tiene estructura para corregir enlaces.")
            return
        
        try:
            result = self.link_fixer.fix_all_links(self.pdf_loader.structure_tree, self.pdf_loader)
            
            if result:
                self.has_unsaved_changes = True
                self.status_label.setText("Enlaces corregidos")
                self.editor_view.refresh_structure_view()
                QMessageBox.information(self, "Corrección completada", "Los enlaces se han corregido correctamente.")
            else:
                QMessageBox.information(self, "Sin cambios", "No fue necesario corregir los enlaces.")
            
        except Exception as e:
            logger.exception(f"Error al corregir enlaces: {e}")
            QMessageBox.critical(self, "Error", f"Error al corregir enlaces: {str(e)}")

    def _on_fix_reading_order(self):
        """Manejador para corregir orden de lectura."""
        if not self.reading_order_fixer or not self.pdf_loader.structure_tree:
            QMessageBox.warning(self, "No hay estructura", "El documento no tiene estructura para corregir el orden de lectura.")
            return
        
        try:
            result = self.reading_order_fixer.fix_reading_order(self.pdf_loader.structure_tree, self.pdf_loader)
            
            if result:
                self.has_unsaved_changes = True
                self.status_label.setText("Orden de lectura corregido")
                self.editor_view.refresh_structure_view()
                QMessageBox.information(self, "Corrección completada", "El orden de lectura se ha corregido correctamente.")
            else:
                QMessageBox.information(self, "Sin cambios", "No fue necesario corregir el orden de lectura.")
            
        except Exception as e:
            logger.exception(f"Error al corregir orden de lectura: {e}")
            QMessageBox.critical(self, "Error", f"Error al corregir orden de lectura: {str(e)}")

    def _on_fix_forms(self):
        """Manejador para corregir formularios."""
        if not self.forms_fixer or not self.pdf_loader.structure_tree:
            QMessageBox.warning(self, "No hay estructura", "El documento no tiene estructura para corregir formularios.")
            return
        
        try:
            result = self.forms_fixer.fix_all_forms(self.pdf_loader.structure_tree, self.pdf_loader)
            
            if result:
                self.has_unsaved_changes = True
                self.status_label.setText("Formularios corregidos")
                self.editor_view.refresh_structure_view()
                QMessageBox.information(self, "Corrección completada", "Los formularios se han corregido correctamente.")
            else:
                QMessageBox.information(self, "Sin cambios", "No fue necesario corregir los formularios.")
            
        except Exception as e:
            logger.exception(f"Error al corregir formularios: {e}")
            QMessageBox.critical(self, "Error", f"Error al corregir formularios: {str(e)}")

    def _on_fix_contrast(self):
        """Manejador para corregir contraste."""
        if not self.contrast_fixer:
            return
        
        try:
            result = self.contrast_fixer.fix_all_contrast(self.pdf_loader)
            
            if result:
                self.has_unsaved_changes = True
                self.status_label.setText("Contraste corregido")
                QMessageBox.information(self, "Corrección completada", "El contraste se ha corregido correctamente.")
            else:
                QMessageBox.information(self, "Sin cambios", "No fue necesario corregir el contraste.")
            
        except Exception as e:
            logger.exception(f"Error al corregir contraste: {e}")
            QMessageBox.critical(self, "Error", f"Error al corregir contraste: {str(e)}")

    def _on_generate_structure(self):
        """Manejador para generar estructura lógica."""
        if not self.structure_generator:
            return
        
        # Verificar si ya tiene estructura
        if self.pdf_loader.structure_tree:
            response = QMessageBox.question(
                self,
                "Estructura existente",
                "El documento ya tiene estructura lógica. ¿Desea reemplazarla?",
                QMessageBox.Yes | QMessageBox.No,
                QMessageBox.No
            )
            
            if response != QMessageBox.Yes:
                return
        
        # Mostrar diálogo de progreso
        progress = QProgressDialog("Generando estructura lógica...", "Cancelar", 0, 100, self)
        progress.setWindowTitle("Generando estructura")
        progress.setWindowModality(Qt.WindowModal)
        progress.setValue(10)
        progress.show()
        
        try:
            result = self.structure_generator.generate_structure(self.pdf_loader)
            
            progress.setValue(90)
            
            if result:
                self.has_unsaved_changes = True
                self.status_label.setText("Estructura lógica generada")
                self.editor_view.refresh_structure_view()
                QMessageBox.information(self, "Generación completada", "La estructura lógica se ha generado correctamente.")
            else:
                QMessageBox.warning(self, "Error", "No se pudo generar la estructura lógica.")
            
            progress.setValue(100)
            progress.close()
            
            # Reanalizar
            QTimer.singleShot(100, self._on_analyze_document)
            
        except Exception as e:
            progress.close()
            logger.exception(f"Error al generar estructura: {e}")
            QMessageBox.critical(self, "Error", f"Error al generar estructura: {str(e)}")

    def _on_open_wizard(self):
        """Manejador para abrir el asistente de accesibilidad."""
        try:
            # Crear asistente
            wizard = AccessibilityWizard(self)
            
            # Configurar componentes
            metadata = self.pdf_loader.get_metadata() if hasattr(self.pdf_loader, "get_metadata") else {}
            wizard.set_document_info({
                "filename": os.path.basename(self.current_file_path) if self.current_file_path else "Sin título",
                "path": self.current_file_path,
                "pages": self.pdf_loader.page_count,
                "has_structure": self.pdf_loader.structure_tree is not None,
                "metadata": metadata
            })
            
            # Configurar correctores
            wizard.set_fixers({
                "metadata": self.metadata_fixer,
                "images": self.images_fixer,
                "tables": self.tables_fixer,
                "lists": self.lists_fixer,
                "artifacts": self.artifacts_fixer,
                "tags": self.tags_fixer,
                "links": self.link_fixer,
                "reading_order": self.reading_order_fixer,
                "forms": self.forms_fixer,
                "contrast": self.contrast_fixer,
                "structure_generator": self.structure_generator
            })
            
            # Mostrar asistente
            if wizard.exec_():
                # Si se realizaron cambios
                self.has_unsaved_changes = True
                self.editor_view.refresh_structure_view()
                
                # Reanalizar
                QTimer.singleShot(100, self._on_analyze_document)
            
        except Exception as e:
            logger.exception(f"Error al abrir asistente: {e}")
            QMessageBox.critical(self, "Error", f"Error al abrir asistente: {str(e)}")

    def _on_page_changed(self, page_num: int, total_pages: int):
        """
        Manejador para cambio de página en el visor.
        
        Args:
            page_num: Número de página actual (base 1)
            total_pages: Número total de páginas
        """
        self.page_label.setText(f"Página: {page_num}/{total_pages}")

    def _on_element_selected(self, element_id):
        """
        Maneja la selección de un elemento en el visor PDF.

        Args:
            element_id: ID del elemento seleccionado
        """
        # Seleccionar el nodo en el editor
        self.editor_view.select_node(element_id)

    def _on_structure_changed(self):
        """Manejador para cambios en la estructura."""
        self.has_unsaved_changes = True
        self.status_label.setText("Estructura modificada (sin guardar)")
        self._update_ui_state(True)

    def _on_node_selected(self, node_id):
        """
        Maneja la selección de un nodo en el editor.

        Args:
            node_id: ID del nodo seleccionado
        """
        # Resaltar el elemento en el visor
        self.pdf_viewer.select_element(node_id)

    def _on_problem_selected(self, problem: dict):
        """
        Manejador para selección de problema en el panel.
        
        Args:
            problem: Información del problema seleccionado
        """
        # Ir a la página del problema
        page = problem.get("page")
        if page is not None and page != "all" and isinstance(page, int):
            self.pdf_viewer.go_to_page(page)

    def _on_fix_requested(self, problem: dict):
        """
        Manejador para solicitud de corrección de problema.
        
        Args:
            problem: Información del problema a corregir
        """
        checkpoint = problem.get("checkpoint", "")
        
        # Determinar qué corrector usar según el checkpoint
        if checkpoint.startswith("06-") or checkpoint.startswith("07-") or checkpoint.startswith("11-006"):
            # Metadatos
            self._on_fix_metadata()
        elif checkpoint.startswith("13-"):
            # Imágenes
            self._on_fix_images()
        elif checkpoint.startswith("15-"):
            # Tablas
            self._on_fix_tables()
        elif checkpoint.startswith("16-"):
            # Listas
            self._on_fix_lists()
        elif checkpoint.startswith("18-") or checkpoint == "01-005":
            # Artefactos
            self._on_fix_artifacts()
        elif checkpoint.startswith("01-") or checkpoint.startswith("09-") or checkpoint.startswith("14-"):
            # Etiquetas
            self._on_fix_tags()
        elif checkpoint.startswith("28-"):
            # Enlaces
            self._on_fix_links()
        elif checkpoint == "09-001" or checkpoint == "09-004":
            # Orden de lectura
            self._on_fix_reading_order()
        elif checkpoint.startswith("24-") or checkpoint.startswith("28-005") or checkpoint.startswith("28-010"):
            # Formularios
            self._on_fix_forms()
        elif checkpoint.startswith("04-"):
            # Contraste
            self._on_fix_contrast()
        else:
            # General
            self._on_fix_all()

    def _on_apply_changes(self):
        """Manejador para aplicar cambios manuales."""
        if not self.structure_manager:
            return
        
        result = self.structure_manager.apply_changes()
        
        if result:
            self.status_label.setText("Cambios aplicados")
            QMessageBox.information(self, "Cambios aplicados", "Los cambios se han aplicado correctamente.")
            # Reanalizar
            QTimer.singleShot(100, self._on_analyze_document)
        else:
            QMessageBox.warning(self, "Error", "No se pudieron aplicar los cambios.")

    def _on_undo(self):
        """Manejador para deshacer cambios."""
        if not self.structure_manager:
            return
        
        result = self.structure_manager.undo()
        
        if result:
            self.editor_view.refresh_structure_view()
            self.status_label.setText("Acción deshecha")
        else:
            QMessageBox.information(self, "Información", "No hay cambios para deshacer.")

    def _on_redo(self):
        """Manejador para rehacer cambios."""
        if not self.structure_manager:
            return
        
        result = self.structure_manager.redo()
        
        if result:
            self.editor_view.refresh_structure_view()
            self.status_label.setText("Acción rehecha")
        else:
            QMessageBox.information(self, "Información", "No hay cambios para rehacer.")

    def _on_zoom_in(self):
        """Manejador para aumentar zoom."""
        self.pdf_viewer.zoom_in()
        
        # Actualizar combo de zoom
        current_zoom = self.pdf_viewer.get_zoom_level()
        self.zoom_combo.setCurrentText(f"{int(current_zoom * 100)}%")

    def _on_zoom_out(self):
        """Manejador para disminuir zoom."""
        self.pdf_viewer.zoom_out()
        
        # Actualizar combo de zoom
        current_zoom = self.pdf_viewer.get_zoom_level()
        self.zoom_combo.setCurrentText(f"{int(current_zoom * 100)}%")

    def _on_zoom_changed(self, zoom_text: str):
        """
        Manejador para cambio en el combo de zoom.
        
        Args:
            zoom_text: Texto del zoom seleccionado
        """
        if zoom_text == "Ajustar a ventana":
            self.pdf_viewer.fit_to_width()
        else:
            # Extraer valor numérico
            try:
                zoom_value = int(zoom_text.replace("%", "")) / 100
                self.pdf_viewer.set_zoom_level(zoom_value)
            except ValueError:
                pass

    def _on_about(self):
        """Muestra información sobre la aplicación."""
        QMessageBox.about(
            self,
            "Acerca de PDF/UA Editor",
            "<h3>PDF/UA Editor</h3>"
            "<p>Versión 1.0</p>"
            "<p>Herramienta para verificar y corregir accesibilidad en documentos PDF "
            "según la normativa PDF/UA (ISO 14289-1) y el Protocolo Matterhorn.</p>"
            "<p>© 2023</p>"
        )

    def _open_documentation(self, doc_type: str):
        """
        Abre la documentación correspondiente.
        
        Args:
            doc_type: Tipo de documentación a abrir
        """
        # Determinar URL
        if doc_type == "matterhorn":
            # Abrir documentación de Matterhorn
            QDesktopServices.openUrl(QUrl("https://www.pdfa.org/resource/matterhorn-protocol/"))
        elif doc_type == "tagged_pdf":
            # Abrir documentación de Tagged PDF
            QDesktopServices.openUrl(QUrl("https://www.pdfa.org/resource/tagged-pdf-best-practice-guide-syntax/"))

    def _update_ui_state(self, document_loaded: bool):
        """
        Actualiza el estado de la interfaz según si hay documento cargado.
        
        Args:
            document_loaded: True si hay documento cargado
        """
        # Acciones de archivo
        self.action_save.setEnabled(document_loaded)
        self.action_save_as.setEnabled(document_loaded)
        
        # Acciones de análisis
        self.action_analyze.setEnabled(document_loaded)
        
        # Acciones de corrección
        self.action_fix_all.setEnabled(document_loaded)
        self.fix_menu_button.setEnabled(document_loaded)
        
        # Acciones de asistente
        self.action_wizard.setEnabled(document_loaded)
        
        # Acciones de edición
        self.action_apply_changes.setEnabled(document_loaded)
        
        # Actualizar acciones adicionales
        if hasattr(self, 'action_optimize'):
            self.action_optimize.setEnabled(document_loaded)
    
        if hasattr(self, 'action_check_conformance'):
            self.action_check_conformance.setEnabled(document_loaded)
        
        # Actualizar estado de deshacer/rehacer
        if self.structure_manager:
            can_undo = hasattr(self.structure_manager, 'can_undo') and self.structure_manager.can_undo()
            can_redo = hasattr(self.structure_manager, 'can_redo') and self.structure_manager.can_redo()
            self.action_undo.setEnabled(can_undo)
            self.action_redo.setEnabled(can_redo)
        

    def _load_settings(self):
        """Carga la configuración de la aplicación."""
        settings = QSettings("PDF/UA Editor", "Settings")
        
        # Restaurar geometría
        geometry = settings.value("geometry")
        if geometry:
            self.restoreGeometry(geometry)
        
        # Restaurar estado
        state = settings.value("windowState")
        if state:
            self.restoreState(state)

    def _save_settings(self):
        """Guarda la configuración de la aplicación."""
        settings = QSettings("PDF/UA Editor", "Settings")
        
        # Guardar geometría
        settings.setValue("geometry", self.saveGeometry())
        
        # Guardar estado
        settings.setValue("windowState", self.saveState())

    def closeEvent(self, event):
        """
        Manejador para el evento de cierre de ventana.
        
        Args:
            event: Evento de cierre
        """
        # Verificar cambios no guardados
        if self.has_unsaved_changes:
            response = QMessageBox.question(
                self,
                "Cambios no guardados",
                "Hay cambios sin guardar. ¿Desea guardarlos antes de salir?",
                QMessageBox.Save | QMessageBox.Discard | QMessageBox.Cancel,
                QMessageBox.Save
            )
            
            if response == QMessageBox.Save:
                if not self._on_save_file():
                    event.ignore()
                    return
            elif response == QMessageBox.Cancel:
                event.ignore()
                return
        
        # Guardar configuración
        self._save_settings()
        
        # Liberar recursos
        if hasattr(self.pdf_loader, 'close'):
            self.pdf_loader.close()
        
        event.accept()
        
    def refresh_ui(self):
        """Actualiza toda la interfaz de usuario después de cambios importantes."""
        # Actualizar el visor
        if self.pdf_loader and self.pdf_loader.doc:
            # Refrescar la página actual
            current_page = self.pdf_viewer.get_current_page()
            self.pdf_viewer.load_document(self.pdf_loader.doc)
            self.pdf_viewer.go_to_page(current_page)
        
        # Actualizar el editor de estructura
        self.editor_view.refresh_structure_view()
        
        # Actualizar estado de deshacer/rehacer
        self._update_undo_redo_state()

    def _update_undo_redo_state(self):
        """Actualiza el estado de los botones de deshacer/rehacer."""
        if self.structure_manager:
            can_undo = hasattr(self.structure_manager, 'can_undo') and self.structure_manager.can_undo()
            can_redo = hasattr(self.structure_manager, 'can_redo') and self.structure_manager.can_redo()
            self.action_undo.setEnabled(can_undo)
            self.action_redo.setEnabled(can_redo)

    def highlight_problems_in_viewer(self, problem_elements):
        """
        Resalta elementos problemáticos en el visor PDF.
        
        Args:
            problem_elements: Lista de elementos a resaltar
        """
        if not self.pdf_viewer:
            return
        
        # Convertir los elementos a formato de resaltado
        highlight_elements = []
        for elem in problem_elements:
            # Extraer información necesaria para resaltado
            if "element_id" in elem and "page" in elem:
                highlight_elem = {
                    "id": elem["element_id"],
                    "page": elem["page"] if isinstance(elem["page"], int) else 0,
                    "type": elem.get("element_type", "unknown"),
                    "rect": elem.get("rect", [0, 0, 1, 1]),  # Coordenadas relativas
                    "severity": elem.get("severity", "warning")
                }
                highlight_elements.append(highlight_elem)
        
        # Resaltar en el visor
        if highlight_elements:
            self.pdf_viewer.highlight_elements(highlight_elements)

    def run_batch_process(self, title, steps, on_complete=None):
        """
        Ejecuta un proceso por lotes con diálogo de progreso.
        
        Args:
            title: Título del proceso
            steps: Lista de tuplas (mensaje, función_a_ejecutar)
            on_complete: Función a ejecutar al completar (opcional)
        """
        # Crear diálogo de progreso
        progress = QProgressDialog(steps[0][0], "Cancelar", 0, len(steps), self)
        progress.setWindowTitle(title)
        progress.setWindowModality(Qt.WindowModal)
        progress.setValue(0)
        progress.show()
        
        try:
            results = []
            
            # Ejecutar cada paso
            for i, (message, func) in enumerate(steps):
                if progress.wasCanceled():
                    break
                    
                progress.setLabelText(message)
                result = func()
                results.append(result)
                
                progress.setValue(i + 1)
                QApplication.processEvents()  # Asegurar que la interfaz responda
            
            progress.setValue(len(steps))
            
            # Ejecutar función de finalización si existe
            if on_complete and not progress.wasCanceled():
                on_complete(results)
                
        except Exception as e:
            logger.exception(f"Error en proceso por lotes: {e}")
            QMessageBox.critical(self, "Error", f"Error al ejecutar el proceso: {str(e)}")
        finally:
            progress.close()

    def optimize_pdf(self):
        """Optimiza el PDF eliminando elementos innecesarios y reduciendo tamaño."""
        if not self.pdf_loader or not self.pdf_writer:
            return
        
        # Mostrar confirmación
        response = QMessageBox.question(
            self,
            "Optimizar PDF",
            "¿Desea optimizar el PDF para reducir su tamaño?\n\n"
            "Esto puede eliminar elementos innecesarios y comprimir imágenes.",
            QMessageBox.Yes | QMessageBox.No,
            QMessageBox.Yes
        )
        
        if response != QMessageBox.Yes:
            return
        
        try:
            # Iniciar proceso de optimización
            self.run_batch_process(
                "Optimizando PDF",
                [
                    ("Comprimiendo imágenes...", lambda: self.pdf_writer.compress_images()),
                    ("Eliminando elementos innecesarios...", lambda: self.pdf_writer.remove_unused_objects()),
                    ("Optimizando estructura...", lambda: self.pdf_writer.optimize_structure())
                ],
                on_complete=lambda results: self._on_optimization_complete(results)
            )
            
        except Exception as e:
            logger.exception(f"Error al optimizar PDF: {e}")
            QMessageBox.critical(self, "Error", f"Error al optimizar el PDF: {str(e)}")

    def _on_optimization_complete(self, results):
        """Manejador para finalización de optimización."""
        # Marcar como modificado
        self.has_unsaved_changes = True
        
        # Refrescar interfaz
        self.refresh_ui()
        
        # Mostrar información de optimización
        if all(results):
            QMessageBox.information(
                self,
                "Optimización completada",
                "El PDF ha sido optimizado correctamente.\n\n"
                "Guarde el documento para aplicar los cambios permanentemente."
            )
        else:
            QMessageBox.warning(
                self,
                "Optimización parcial",
                "La optimización se completó parcialmente.\n\n"
                "Algunos pasos de optimización no pudieron completarse."
            )

    def check_conformance(self):
        """Verifica conformidad completa con PDF/UA."""
        if not self.pdf_loader:
            return
        
        # Iniciar proceso de verificación completa
        self.run_batch_process(
            "Verificando conformidad PDF/UA",
            [
                ("Analizando estructura...", lambda: self.structure_validator.validate(self.pdf_loader.structure_tree)),
                ("Analizando metadatos...", lambda: self.metadata_validator.validate(self.pdf_loader.get_metadata())),
                ("Analizando tablas...", lambda: self.tables_validator.validate(self.pdf_loader.structure_tree)),
                ("Analizando contraste...", lambda: self.contrast_validator.validate(self.pdf_loader)),
                ("Analizando idioma...", lambda: self.language_validator.validate(
                    self.pdf_loader.get_metadata(), 
                    self.pdf_loader.structure_tree
                )),
                ("Evaluando conformidad...", lambda: self.matterhorn_checker.get_pdf_ua_conformance_status([]))
            ],
            on_complete=lambda results: self._on_conformance_check_complete(results)
        )

    def _on_conformance_check_complete(self, results):
        """Manejador para finalización de verificación de conformidad."""
        if not results or len(results) < 6:
            QMessageBox.warning(self, "Verificación incompleta", "No se pudo completar la verificación de conformidad.")
            return
        
        # Recopilar todos los problemas
        issues = []
        for i in range(5):  # Los primeros 5 resultados son listas de problemas
            if isinstance(results[i], list):
                issues.extend(results[i])
        
        # Obtener estado de conformidad
        conformance_status = results[5]
        
        # Actualizar panel de problemas
        self.problems_panel.set_issues(issues)
        
        # Mostrar panel de problemas
        self.problems_dock.show()
        
        # Actualizar reporte
        self.reporter.set_document_info({
            "filename": os.path.basename(self.current_file_path) if self.current_file_path else "Sin título",
            "path": self.current_file_path,
            "pages": self.pdf_loader.page_count,
            "has_structure": self.pdf_loader.structure_tree is not None
        })
        self.reporter.add_issues(issues)
        
        # Actualizar mensaje en la barra de estado
        error_count = len([i for i in issues if i.get("severity") == "error"])
        warning_count = len([i for i in issues if i.get("severity") == "warning"])
        
        self.status_label.setText(
            f"Verificación completada: {error_count} errores, {warning_count} advertencias"
        )
        
        # Mostrar resultados de conformidad
        is_conformant = conformance_status.get("is_conformant", False)
        if is_conformant:
            QMessageBox.information(
                self,
                "Conformidad PDF/UA",
                "¡El documento cumple con los requisitos de PDF/UA!\n\n"
                "No se han detectado problemas que impidan la conformidad."
            )
        else:
            blocking_count = len(conformance_status.get("blocking_checkpoints", []))
            QMessageBox.warning(
                self,
                "Conformidad PDF/UA",
                f"El documento NO cumple con los requisitos de PDF/UA.\n\n"
                f"Se han detectado {error_count} errores en {blocking_count} checkpoints que impiden la conformidad.\n"
                f"Consulte el panel de problemas para más detalles."
            )
        
        # Generar informe
        self._on_generate_report()

    def show_problems_in_document(self, category=None, severity=None):
        """
        Muestra y resalta problemas en el documento según filtros.
        
        Args:
            category: Categoría de problemas a mostrar (opcional)
            severity: Severidad de problemas a mostrar (opcional)
        """
        if not hasattr(self, 'problems_panel') or not self.problems_panel:
            return
        
        # Obtener problemas actuales
        all_issues = self.problems_panel.get_issues()
        
        # Filtrar según criterios
        filtered_issues = []
        for issue in all_issues:
            if category and issue.get('checkpoint', '').split('-')[0] != category:
                continue
            if severity and issue.get('severity') != severity:
                continue
            filtered_issues.append(issue)
        
        # Extraer elementos para resaltar
        elements_to_highlight = []
        for issue in filtered_issues:
            if issue.get('element_id') and issue.get('page') != 'all':
                elements_to_highlight.append({
                    'id': issue.get('element_id'),
                    'page': issue.get('page', 0),
                    'type': issue.get('element_type', ''),
                    'severity': issue.get('severity', 'warning')
                })
        
        # Resaltar en el visor
        if elements_to_highlight:
            self.pdf_viewer.highlight_elements(elements_to_highlight)
            
            # Ir a la primera página con problemas
            if elements_to_highlight[0].get('page') is not None:
                self.pdf_viewer.go_to_page(elements_to_highlight[0].get('page'))
        
        # Mostrar mensaje
        count = len(filtered_issues)
        if count > 0:
            self.status_label.setText(f"Mostrando {count} problemas")
        else:
            self.status_label.setText("No se encontraron problemas con los filtros actuales")
            QMessageBox.information(
                self,
                "Filtro de problemas",
                "No se encontraron problemas que cumplan con los criterios de filtro."
            )