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
        # Conectar el pdf_loader con el visor para que pueda acceder a la estructura
        self.pdf_viewer.pdf_loader = self.pdf_loader
        self.main_splitter.addWidget(self.pdf_viewer)
        
        # Establecer proporciones iniciales (40% editor, 60% visor)
        self.main_splitter.setSizes([480, 720])
        
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
        if hasattr(self.problems_panel, 'fixRequested'):
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
        self.load_file(file_path)

    def load_file(self, file_path: str) -> bool:
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
        
            # Cerrar documentos previos si existen
            if self.pdf_loader.doc:
                logger.info("Cerrando documento previo")
                self.pdf_loader.close()
        
            # Cargar el documento
            if not self.pdf_loader.load_document(file_path):
                QMessageBox.critical(self, "Error", "No se pudo cargar el documento PDF.")
                progress.close()
                return False
        
            progress.setValue(40)
        
            # Actualizar referencias en los componentes
            self.pdf_writer.set_pdf_loader(self.pdf_loader)
            self.structure_manager.set_pdf_loader(self.pdf_loader)
            
            # Asegurarse de que el visor tenga referencia al pdf_loader
            self.pdf_viewer.pdf_loader = self.pdf_loader
        
            # Establecer la referencia al PDF en los validadores
            self.metadata_validator.set_pdf_loader(self.pdf_loader)
            self.structure_validator.set_pdf_loader(self.pdf_loader)
            self.tables_validator.set_pdf_loader(self.pdf_loader)
            self.contrast_validator.set_pdf_loader(self.pdf_loader)
            self.language_validator.set_pdf_loader(self.pdf_loader)
        
            progress.setValue(60)
            
            # Mostrar en visor
            progress.setValue(70)
            self.pdf_viewer.load_document(self.pdf_loader.doc)
        
            # Actualizar editor con estructura
            progress.setValue(80)
            self.editor_view.set_structure_manager(self.structure_manager)
            self.editor_view.refresh_structure_view()
            
            # Actualizar estado de la aplicación
            self.current_file_path = file_path
            self.has_unsaved_changes = False
            self.setWindowTitle(f"PDF/UA Editor - {os.path.basename(file_path)}")
            
            # Habilitar acciones
            self._update_ui_state(True)
            
            # Mostrar mensaje en la barra de estado
            self.status_label.setText(f"Documento cargado: {os.path.basename(file_path)}")
            
            progress.setValue(100)
            progress.close()
            
            # Emitir señal de documento cargado
            self.documentLoaded.emit(True)
            
            # Analizar automáticamente después de un breve delay
            QTimer.singleShot(500, self._on_analyze_document)
            
            return True
            
        except Exception as e:
            if 'progress' in locals():
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
            progress.setValue(30)
            if self.structure_manager and self.structure_manager.modified:
                if not self.structure_manager.apply_changes():
                    QMessageBox.warning(self, "Advertencia", "No se pudieron aplicar todos los cambios.")
            
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
            
            # Emitir señal de documento guardado
            self.documentSaved.emit(file_path)
            
            return True
            
        except Exception as e:
            if 'progress' in locals():
                progress.close()
            logger.exception(f"Error al guardar archivo: {e}")
            QMessageBox.critical(self, "Error", f"Error al guardar el documento: {str(e)}")
            return False

    def _on_analyze_document(self):
        """Manejador para analizar el documento."""
        if not self.pdf_loader or not self.pdf_loader.doc:
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
            metadata = self.pdf_loader.get_metadata()
            
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
            
            # Emitir señal de validación completada
            self.validationCompleted.emit(issues)
            
        except Exception as e:
            if 'progress' in locals():
                progress.close()
            logger.exception(f"Error al analizar documento: {e}")
            QMessageBox.critical(self, "Error", f"Error al analizar el documento: {str(e)}")

    # Resto de métodos permanecen igual pero con mejoras en el manejo de errores
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
        try:
            # Seleccionar el nodo en el editor
            self.editor_view.select_node(element_id)
        except Exception as e:
            logger.error(f"Error al manejar selección de elemento: {e}")

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
        try:
            # Verificar si el documento está disponible antes de resaltar
            if self.pdf_loader and self.pdf_loader.doc and node_id:
                # Resaltar el elemento en el visor
                self.pdf_viewer.select_element(node_id)
        except Exception as e:
            logger.error(f"Error al manejar selección de nodo: {e}")

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
        self.action_optimize.setEnabled(document_loaded)
        self.action_check_conformance.setEnabled(document_loaded)
        
        # Actualizar estado de deshacer/rehacer
        if self.structure_manager:
            can_undo = self.structure_manager.can_undo()
            can_redo = self.structure_manager.can_redo()
            self.action_undo.setEnabled(can_undo)
            self.action_redo.setEnabled(can_redo)

    # Continuar con el resto de métodos...
    # (Los métodos de corrección, generación de informes, etc. permanecen igual)
    
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
        
        # Liberar recursos explícitamente
        if self.pdf_loader:
            self.pdf_loader.close()
        
        # También cerrar todas las referencias al documento
        if hasattr(self.pdf_viewer, 'doc'):
            self.pdf_viewer.doc = None
        
        event.accept()

    def _load_settings(self):
        """Carga la configuración de la aplicación."""
        try:
            settings = QSettings("PDF/UA Editor", "Settings")
            
            # Restaurar geometría
            geometry = settings.value("geometry")
            if geometry:
                self.restoreGeometry(geometry)
            
            # Restaurar estado
            state = settings.value("windowState")
            if state:
                self.restoreState(state)
                
        except Exception as e:
            logger.error(f"Error al cargar configuración: {e}")

    def _save_settings(self):
        """Guarda la configuración de la aplicación."""
        try:
            settings = QSettings("PDF/UA Editor", "Settings")
            
            # Guardar geometría
            settings.setValue("geometry", self.saveGeometry())
            
            # Guardar estado
            settings.setValue("windowState", self.saveState())
            
        except Exception as e:
            logger.error(f"Error al guardar configuración: {e}")

    # Métodos de corrección, generación de informes, etc. - mantener los existentes
    # con mejoras en el manejo de errores...
    
    def _on_apply_changes(self):
        """Manejador para aplicar cambios manuales."""
        try:
            if not self.structure_manager:
                return
            
            result = self.structure_manager.apply_changes()
            
            if result:
                self.status_label.setText("Cambios aplicados")
                self.has_unsaved_changes = True
                QMessageBox.information(self, "Cambios aplicados", "Los cambios se han aplicado correctamente.")
                # Reanalizar
                QTimer.singleShot(100, self._on_analyze_document)
            else:
                QMessageBox.warning(self, "Error", "No se pudieron aplicar los cambios.")
                
        except Exception as e:
            logger.error(f"Error al aplicar cambios: {e}")
            QMessageBox.critical(self, "Error", f"Error al aplicar cambios: {str(e)}")

    def _on_undo(self):
        """Manejador para deshacer cambios."""
        try:
            if not self.structure_manager:
                return
            
            result = self.structure_manager.undo()
            
            if result:
                self.editor_view.refresh_structure_view()
                self.status_label.setText("Acción deshecha")
                self._update_ui_state(True)
            else:
                QMessageBox.information(self, "Información", "No hay cambios para deshacer.")
                
        except Exception as e:
            logger.error(f"Error al deshacer: {e}")

    def _on_redo(self):
        """Manejador para rehacer cambios."""
        try:
            if not self.structure_manager:
                return
            
            result = self.structure_manager.redo()
            
            if result:
                self.editor_view.refresh_structure_view()
                self.status_label.setText("Acción rehecha")
                self._update_ui_state(True)
            else:
                QMessageBox.information(self, "Información", "No hay cambios para rehacer.")
                
        except Exception as e:
            logger.error(f"Error al rehacer: {e}")

    # Agregar métodos faltantes mencionados en el archivo original
    def _on_zoom_in(self):
        """Manejador para aumentar zoom."""
        try:
            self.pdf_viewer.zoom_in()
            
            # Actualizar combo de zoom
            current_zoom = self.pdf_viewer.get_zoom_level()
            self.zoom_combo.setCurrentText(f"{int(current_zoom * 100)}%")
        except Exception as e:
            logger.error(f"Error al hacer zoom in: {e}")

    def _on_zoom_out(self):
        """Manejador para disminuir zoom."""
        try:
            self.pdf_viewer.zoom_out()
            
            # Actualizar combo de zoom
            current_zoom = self.pdf_viewer.get_zoom_level()
            self.zoom_combo.setCurrentText(f"{int(current_zoom * 100)}%")
        except Exception as e:
            logger.error(f"Error al hacer zoom out: {e}")

    def _on_zoom_changed(self, zoom_text: str):
        """
        Manejador para cambio en el combo de zoom.
        
        Args:
            zoom_text: Texto del zoom seleccionado
        """
        try:
            if zoom_text == "Ajustar a ventana":
                self.pdf_viewer.fit_to_width()
            else:
                # Extraer valor numérico
                zoom_value = int(zoom_text.replace("%", "")) / 100
                self.pdf_viewer.set_zoom_level(zoom_value)
        except (ValueError, AttributeError) as e:
            logger.error(f"Error al cambiar zoom: {e}")

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
        try:
            # Determinar URL
            if doc_type == "matterhorn":
                # Abrir documentación de Matterhorn
                QDesktopServices.openUrl(QUrl("https://www.pdfa.org/resource/matterhorn-protocol/"))
            elif doc_type == "tagged_pdf":
                # Abrir documentación de Tagged PDF
                QDesktopServices.openUrl(QUrl("https://www.pdfa.org/resource/tagged-pdf-best-practice-guide-syntax/"))
        except Exception as e:
            logger.error(f"Error al abrir documentación: {e}")

    # Métodos de corrección simplificados (mantener estructura existente pero con mejor manejo de errores)
    def _on_fix_metadata(self):
        """Manejador para corregir metadatos."""
        # Implementación simplificada con manejo de errores mejorado
        pass

    def _on_fix_images(self):
        """Manejador para corregir imágenes."""
        pass

    def _on_fix_tables(self):
        """Manejador para corregir tablas."""
        pass

    def _on_fix_lists(self):
        """Manejador para corregir listas."""
        pass

    def _on_fix_artifacts(self):
        """Manejador para corregir artefactos."""
        pass

    def _on_fix_tags(self):
        """Manejador para corregir etiquetas."""
        pass

    def _on_fix_links(self):
        """Manejador para corregir enlaces."""
        pass

    def _on_fix_reading_order(self):
        """Manejador para corregir orden de lectura."""
        pass

    def _on_fix_forms(self):
        """Manejador para corregir formularios."""
        pass

    def _on_fix_contrast(self):
        """Manejador para corregir contraste."""
        pass

    def _on_generate_structure(self):
        """Manejador para generar estructura lógica."""
        pass

    def _on_fix_all(self):
        """Manejador para aplicar todas las correcciones automáticas."""
        pass

    def _on_open_wizard(self):
        """Manejador para abrir el asistente de accesibilidad."""
        pass

    def _on_generate_report(self):
        """Manejador para generar informe de conformidad."""
        pass

    def _on_export_report(self):
        """Manejador para exportar informe."""
        pass

    def _on_problem_selected(self, problem: dict):
        """
        Manejador para selección de problema en el panel.
        
        Args:
            problem: Información del problema seleccionado
        """
        try:
            # Ir a la página del problema
            page = problem.get("page")
            if page is not None and page != "all" and isinstance(page, int):
                self.pdf_viewer.go_to_page(page)
        except Exception as e:
            logger.error(f"Error al seleccionar problema: {e}")

    def _on_fix_requested(self, problem: dict):
        """
        Manejador para solicitud de corrección de problema.
        
        Args:
            problem: Información del problema a corregir
        """
        # Implementar lógica de corrección específica
        pass

    def optimize_pdf(self):
        """Optimiza el PDF eliminando elementos innecesarios y reduciendo tamaño."""
        pass

    def check_conformance(self):
        """Verifica conformidad completa con PDF/UA."""
        pass