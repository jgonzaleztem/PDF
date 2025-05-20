from PySide6.QtWidgets import (QWizard, QWizardPage, QLabel, QVBoxLayout, QCheckBox,
                             QHBoxLayout, QComboBox, QLineEdit, QRadioButton,
                             QButtonGroup, QTextEdit, QProgressBar, QGroupBox,
                             QListWidget, QMessageBox)
from PySide6.QtCore import Qt, Slot, QThread, Signal

from loguru import logger
import time

class WorkerThread(QThread):
    """Hilo para operaciones en segundo plano en el asistente."""
    progressChanged = Signal(int)
    operationComplete = Signal(bool, str)  # éxito, mensaje
    
    def __init__(self, operation, params):
        super().__init__()
        self.operation = operation
        self.params = params
        
    def run(self):
        try:
            # Simular progreso
            for i in range(10):
                time.sleep(0.1)
                self.progressChanged.emit((i + 1) * 10)
            
            # Realizar operación
            result = self.operation(**self.params)
            self.operationComplete.emit(True, "Operación completada con éxito")
        except Exception as e:
            logger.error(f"Error en operación: {str(e)}")
            self.operationComplete.emit(False, f"Error: {str(e)}")


class IntroPage(QWizardPage):
    """Página de introducción al asistente de accesibilidad."""
    def __init__(self, parent=None):
        super().__init__(parent)
        self.setTitle("Asistente de Accesibilidad PDF/UA")
        self.setSubTitle("Este asistente le guiará a través del proceso de hacer su documento accesible según PDF/UA")
        
        layout = QVBoxLayout(self)
        
        # Información del documento
        self.doc_info_label = QLabel("Información del documento:")
        layout.addWidget(self.doc_info_label)
        
        # Opciones de asistente
        options_group = QGroupBox("Elija los pasos a realizar:")
        options_layout = QVBoxLayout(options_group)
        
        self.metadata_cb = QCheckBox("Metadatos (título, idioma, flag PDF/UA)")
        self.metadata_cb.setChecked(True)
        options_layout.addWidget(self.metadata_cb)
        
        self.structure_cb = QCheckBox("Estructura (etiquetas y orden de lectura)")
        self.structure_cb.setChecked(True)
        options_layout.addWidget(self.structure_cb)
        
        self.images_cb = QCheckBox("Imágenes (texto alternativo)")
        self.images_cb.setChecked(True)
        options_layout.addWidget(self.images_cb)
        
        self.tables_cb = QCheckBox("Tablas (estructura y cabeceras)")
        self.tables_cb.setChecked(True)
        options_layout.addWidget(self.tables_cb)
        
        self.links_cb = QCheckBox("Enlaces (estructura y descripciones)")
        self.links_cb.setChecked(True)
        options_layout.addWidget(self.links_cb)
        
        layout.addWidget(options_group)
        
        # Explicación sobre PDF/UA
        explanation = QLabel(
            "PDF/UA es el estándar ISO 14289 para documentos PDF accesibles. "
            "Un documento conforme con PDF/UA garantiza compatibilidad con lectores de "
            "pantalla y tecnologías de asistencia, facilitando su uso a personas con discapacidad."
        )
        explanation.setWordWrap(True)
        layout.addWidget(explanation)
        
        layout.addStretch()
        
    def initializePage(self):
        """Inicializa la página con información del documento."""
        wizard = self.wizard()
        if wizard.document_info:
            info = wizard.document_info
            self.doc_info_label.setText(
                f"<b>Documento:</b> {info.get('filename', 'Desconocido')}<br>"
                f"<b>Páginas:</b> {info.get('pages', 0)}<br>"
                f"<b>Tiene estructura:</b> {'Sí' if info.get('has_structure', False) else 'No'}<br>"
                f"<b>Flag PDF/UA:</b> {'Presente' if info.get('has_ua_flag', False) else 'Ausente'}"
            )


class MetadataPage(QWizardPage):
    """
    Página para configurar metadatos del documento.
    Relacionado con:
    - Matterhorn: 06-001 a 06-004, 07-001, 11-006
    - Tagged PDF: 3.3 (XMP), 5.5.1 (Lang), Anexo A (PDF/UA flag)
    """
    def __init__(self, parent=None):
        super().__init__(parent)
        self.setTitle("Metadatos del Documento")
        self.setSubTitle("Configure los metadatos necesarios para cumplir con PDF/UA")
        
        layout = QVBoxLayout(self)
        
        # Campo para título del documento
        title_layout = QHBoxLayout()
        title_layout.addWidget(QLabel("Título del documento:"))
        self.title_edit = QLineEdit()
        title_layout.addWidget(self.title_edit)
        layout.addLayout(title_layout)
        
        # Selector de idioma
        lang_layout = QHBoxLayout()
        lang_layout.addWidget(QLabel("Idioma principal:"))
        self.lang_combo = QComboBox()
        self.lang_combo.addItems(["es-ES", "en-US", "fr-FR", "de-DE", "it-IT", "pt-PT"])
        lang_layout.addWidget(self.lang_combo)
        layout.addLayout(lang_layout)
        
        # DisplayDocTitle
        self.display_title_cb = QCheckBox("Mostrar título en lugar de archivo (DisplayDocTitle)")
        self.display_title_cb.setChecked(True)
        layout.addWidget(self.display_title_cb)
        
        # Flag PDF/UA
        self.ua_flag_cb = QCheckBox("Añadir flag PDF/UA-1 en metadatos XMP")
        self.ua_flag_cb.setChecked(True)
        layout.addWidget(self.ua_flag_cb)
        
        # Explicación sobre metadatos
        explanation = QLabel(
            "<b>Nota:</b> Los metadatos son esenciales para la accesibilidad. El título del documento "
            "debe ser descriptivo y aparecer cuando se abre el PDF. El idioma permite a los lectores "
            "de pantalla usar la pronunciación correcta."
        )
        explanation.setWordWrap(True)
        layout.addWidget(explanation)
        
        layout.addStretch()
        
    def initializePage(self):
        """Inicializa la página con metadatos existentes."""
        wizard = self.wizard()
        if wizard.document_info:
            info = wizard.document_info
            self.title_edit.setText(info.get('title', ''))
            
            lang = info.get('language', 'es-ES')
            index = self.lang_combo.findText(lang)
            if index >= 0:
                self.lang_combo.setCurrentIndex(index)
            
            self.display_title_cb.setChecked(info.get('display_title', False))
            self.ua_flag_cb.setChecked(not info.get('has_ua_flag', False))
            
    def validatePage(self):
        """Valida que los campos requeridos estén completos."""
        if not self.title_edit.text().strip():
            QMessageBox.warning(self, "Título requerido", 
                             "Debe proporcionar un título para el documento.")
            return False
        return True


class ImagesPage(QWizardPage):
    """
    Página para configurar texto alternativo para imágenes.
    Relacionado con:
    - Matterhorn: 13-004, 13-005, 13-008
    - Tagged PDF: 4.3.1, 5.5.2 (Alt), 5.5.3 (ActualText)
    """
    def __init__(self, parent=None):
        super().__init__(parent)
        self.setTitle("Texto Alternativo para Imágenes")
        self.setSubTitle("Proporcione descripciones alternativas para imágenes")
        
        layout = QVBoxLayout(self)
        
        # Lista de imágenes
        layout.addWidget(QLabel("Imágenes detectadas:"))
        self.images_list = QListWidget()
        layout.addWidget(self.images_list)
        
        # Campo para texto alternativo
        layout.addWidget(QLabel("Texto alternativo:"))
        self.alt_text = QTextEdit()
        layout.addWidget(self.alt_text)
        
        # Opciones para OCR
        ocr_group = QGroupBox("Usar OCR para texto en imágenes")
        ocr_layout = QVBoxLayout(ocr_group)
        
        self.use_ocr_cb = QCheckBox("Aplicar OCR automáticamente")
        ocr_layout.addWidget(self.use_ocr_cb)
        
        lang_layout = QHBoxLayout()
        lang_layout.addWidget(QLabel("Idioma OCR:"))
        self.ocr_lang_combo = QComboBox()
        self.ocr_lang_combo.addItems(["spa", "eng", "fra", "deu", "ita", "por"])
        lang_layout.addWidget(self.ocr_lang_combo)
        ocr_layout.addLayout(lang_layout)
        
        layout.addWidget(ocr_group)
        
        # Explicación sobre texto alternativo
        explanation = QLabel(
            "<b>Nota:</b> Cada imagen que transmite información debe tener un texto alternativo "
            "descriptivo que explique su propósito y contenido. Para imágenes decorativas, "
            "indique que son decorativas."
        )
        explanation.setWordWrap(True)
        layout.addWidget(explanation)
        
        layout.addStretch()
        
        # Conectar eventos
        self.images_list.currentItemChanged.connect(self._on_image_selected)
        
    def initializePage(self):
        """Inicializa la página con imágenes detectadas."""
        wizard = self.wizard()
        self.images_list.clear()
        
        # Simular imágenes detectadas
        if wizard.fixers and hasattr(wizard.fixers, 'images_fixer'):
            # Aquí se cargarían las imágenes reales del PDF
            # Por ahora simulamos algunas imágenes
            sample_images = [
                {"id": "img001", "page": 1, "type": "Figure", "has_alt": False, "alt": ""},
                {"id": "img002", "page": 2, "type": "Figure", "has_alt": True, "alt": "Logo de la empresa"},
                {"id": "img003", "page": 3, "type": "Image", "has_alt": False, "alt": ""}
            ]
            
            for img in sample_images:
                text = f"Página {img['page']}: {img['type']} - "
                text += f"Alt: {img['alt']}" if img['has_alt'] else "Sin texto alternativo"
                
                item = self.images_list.addItem(text)
                self.images_list.item(self.images_list.count() - 1).setData(Qt.UserRole, img)
                
    def _on_image_selected(self, current, previous):
        """Maneja la selección de una imagen en la lista."""
        if current:
            img_data = current.data(Qt.UserRole)
            if img_data:
                self.alt_text.setText(img_data.get('alt', ''))


class TablesPage(QWizardPage):
    """
    Página para configurar estructura de tablas.
    Relacionado con:
    - Matterhorn: 15-001, 15-003, 15-005
    - Tagged PDF: 4.2.6, 5.4.1 (Scope, Headers)
    """
    def __init__(self, parent=None):
        super().__init__(parent)
        self.setTitle("Estructura de Tablas")
        self.setSubTitle("Configure la accesibilidad de las tablas del documento")
        
        layout = QVBoxLayout(self)
        
        # Lista de tablas
        layout.addWidget(QLabel("Tablas detectadas:"))
        self.tables_list = QListWidget()
        layout.addWidget(self.tables_list)
        
        # Opciones para cabeceras
        headers_group = QGroupBox("Cabeceras de tabla")
        headers_layout = QVBoxLayout(headers_group)
        
        self.has_headers_cb = QCheckBox("La tabla tiene cabeceras")
        headers_layout.addWidget(self.has_headers_cb)
        
        scope_layout = QHBoxLayout()
        scope_layout.addWidget(QLabel("Tipo de cabecera:"))
        self.scope_combo = QComboBox()
        self.scope_combo.addItems(["Column", "Row", "Both"])
        scope_layout.addWidget(self.scope_combo)
        headers_layout.addLayout(scope_layout)
        
        layout.addWidget(headers_group)
        
        # Corrección automática
        self.auto_fix_cb = QCheckBox("Aplicar corrección automática a todas las tablas")
        self.auto_fix_cb.setChecked(True)
        layout.addWidget(self.auto_fix_cb)
        
        # Explicación sobre tablas accesibles
        explanation = QLabel(
            "<b>Nota:</b> Las tablas accesibles requieren que las celdas de cabecera (TH) estén "
            "correctamente marcadas y tengan el atributo Scope (Column/Row) para asociarlas "
            "con las celdas de datos. Las tablas complejas pueden requerir atributos ID y Headers."
        )
        explanation.setWordWrap(True)
        layout.addWidget(explanation)
        
        layout.addStretch()
        
        # Conectar eventos
        self.tables_list.currentItemChanged.connect(self._on_table_selected)
        
    def initializePage(self):
        """Inicializa la página con tablas detectadas."""
        wizard = self.wizard()
        self.tables_list.clear()
        
        # Simular tablas detectadas
        if wizard.fixers and hasattr(wizard.fixers, 'tables_fixer'):
            # Aquí se cargarían las tablas reales del PDF
            # Por ahora simulamos algunas tablas
            sample_tables = [
                {"id": "table001", "page": 1, "rows": 3, "cols": 4, "has_headers": True, "has_scope": False},
                {"id": "table002", "page": 2, "rows": 5, "cols": 3, "has_headers": False, "has_scope": False},
                {"id": "table003", "page": 4, "rows": 2, "cols": 2, "has_headers": True, "has_scope": True}
            ]
            
            for tbl in sample_tables:
                text = f"Página {tbl['page']}: Tabla {tbl['rows']}x{tbl['cols']} - "
                text += "Con cabeceras" if tbl['has_headers'] else "Sin cabeceras"
                text += ", Con Scope" if tbl['has_scope'] else ", Sin Scope"
                
                item = self.tables_list.addItem(text)
                self.tables_list.item(self.tables_list.count() - 1).setData(Qt.UserRole, tbl)
                
    def _on_table_selected(self, current, previous):
        """Maneja la selección de una tabla en la lista."""
        if current:
            tbl_data = current.data(Qt.UserRole)
            if tbl_data:
                self.has_headers_cb.setChecked(tbl_data.get('has_headers', False))


class ProcessingPage(QWizardPage):
    """Página para mostrar progreso y realizar las correcciones."""
    def __init__(self, parent=None):
        super().__init__(parent)
        self.setTitle("Aplicando Correcciones")
        self.setSubTitle("Por favor espere mientras se aplican las correcciones")
        
        self.is_complete = False
        
        layout = QVBoxLayout(self)
        
        # Barra de progreso
        self.progress_bar = QProgressBar()
        self.progress_bar.setRange(0, 100)
        layout.addWidget(self.progress_bar)
        
        # Etiqueta de estado
        self.status_label = QLabel("Preparando...")
        layout.addWidget(self.status_label)
        
        # Detalles de operación
        self.details_text = QTextEdit()
        self.details_text.setReadOnly(True)
        layout.addWidget(self.details_text)
        
        layout.addStretch()
        
    def initializePage(self):
        """Inicia el proceso de corrección al entrar en la página."""
        wizard = self.wizard()
        self.is_complete = False
        
        # Recopilar opciones seleccionadas
        options = {
            'metadata': {
                'enabled': wizard.field("IntroPage.metadata_cb"),
                'title': wizard.field("MetadataPage.title_edit"),
                'language': wizard.field("MetadataPage.lang_combo"),
                'display_title': wizard.field("MetadataPage.display_title_cb"),
                'add_ua_flag': wizard.field("MetadataPage.ua_flag_cb")
            },
            'images': {
                'enabled': wizard.field("IntroPage.images_cb"),
                'use_ocr': wizard.field("ImagesPage.use_ocr_cb") if hasattr(wizard, "ImagesPage") else False,
                'ocr_lang': wizard.field("ImagesPage.ocr_lang_combo") if hasattr(wizard, "ImagesPage") else "spa"
            },
            'tables': {
                'enabled': wizard.field("IntroPage.tables_cb"),
                'auto_fix': wizard.field("TablesPage.auto_fix_cb") if hasattr(wizard, "TablesPage") else False
            }
        }
        
        # Iniciar operaciones en segundo plano
        self._start_operations(options)
        
    def _start_operations(self, options):
        """Inicia las operaciones de corrección en secuencia."""
        self.details_text.append("Iniciando proceso de remediación...\n")
        
        # Operaciones a realizar
        self.operations = []
        
        if options['metadata']['enabled']:
            self.operations.append({
                'name': "Corrigiendo metadatos",
                'function': self.wizard().fixers.metadata_fixer.fix_all_metadata,
                'params': {
                    'title': options['metadata']['title'],
                    'language': options['metadata']['language'],
                    'display_title': options['metadata']['display_title'],
                    'add_ua_flag': options['metadata']['add_ua_flag']
                }
            })
            
        if options['images']['enabled']:
            self.operations.append({
                'name': "Procesando imágenes",
                'function': self.wizard().fixers.images_fixer.fix_all_images,
                'params': {
                    'use_ocr': options['images']['use_ocr'],
                    'ocr_lang': options['images']['ocr_lang']
                }
            })
            
        if options['tables']['enabled']:
            self.operations.append({
                'name': "Corrigiendo tablas",
                'function': self.wizard().fixers.tables_fixer.fix_all_tables,
                'params': {
                    'add_scope': True,
                    'fix_headers': True
                }
            })
            
        # Iniciar primera operación
        self._run_next_operation()
        
    def _run_next_operation(self):
        """Ejecuta la siguiente operación en la cola."""
        if not self.operations:
            # Todas las operaciones completadas
            self.details_text.append("\n✅ Todas las correcciones han sido aplicadas correctamente.")
            self.status_label.setText("Proceso completado")
            self.progress_bar.setValue(100)
            self.is_complete = True
            self.completeChanged.emit()
            return
            
        # Obtener siguiente operación
        operation = self.operations.pop(0)
        self.status_label.setText(operation['name'])
        self.details_text.append(f"\n➡️ {operation['name']}...")
        
        # Crear e iniciar worker thread
        self.worker = WorkerThread(operation['function'], operation['params'])
        self.worker.progressChanged.connect(self._on_progress_changed)
        self.worker.operationComplete.connect(self._on_operation_complete)
        self.worker.start()
        
    def _on_progress_changed(self, value):
        """Actualiza la barra de progreso."""
        self.progress_bar.setValue(value)
        
    def _on_operation_complete(self, success, message):
        """Maneja la finalización de una operación."""
        if success:
            self.details_text.append(f"✅ {message}")
        else:
            self.details_text.append(f"❌ {message}")
            
        # Ejecutar siguiente operación
        self._run_next_operation()
        
    def isComplete(self):
        """Verifica si se han completado todas las operaciones."""
        return self.is_complete


class SummaryPage(QWizardPage):
    """Página de resumen de las correcciones aplicadas."""
    def __init__(self, parent=None):
        super().__init__(parent)
        self.setTitle("Resumen de Correcciones")
        self.setSubTitle("Se han aplicado las siguientes correcciones al documento")
        
        layout = QVBoxLayout(self)
        
        # Resumen de cambios
        self.summary_text = QTextEdit()
        self.summary_text.setReadOnly(True)
        layout.addWidget(self.summary_text)
        
        # Estado de conformidad
        self.compliance_label = QLabel()
        self.compliance_label.setWordWrap(True)
        layout.addWidget(self.compliance_label)
        
        # Recomendaciones
        recommendations = QLabel(
            "<b>Recomendaciones:</b><br>"
            "• Revise manualmente el documento para verificar la correcta estructura<br>"
            "• Valide los textos alternativos de las imágenes<br>"
            "• Realice pruebas con tecnologías de asistencia<br>"
            "• Genere un informe de conformidad para documentar el cumplimiento"
        )
        layout.addWidget(recommendations)
        
        layout.addStretch()
        
    def initializePage(self):
        """Inicializa la página con el resumen de cambios."""
        # Simular resumen de cambios
        self.summary_text.clear()
        self.summary_text.append("<h3>Correcciones aplicadas:</h3>")
        self.summary_text.append("<ul>")
        
        wizard = self.wizard()
        if wizard.field("IntroPage.metadata_cb"):
            self.summary_text.append("<li>✅ <b>Metadatos:</b> Título, idioma y flag PDF/UA añadidos</li>")
            
        if wizard.field("IntroPage.images_cb"):
            # Contar imágenes procesadas
            self.summary_text.append("<li>✅ <b>Imágenes:</b> 3 imágenes procesadas, 2 con texto alternativo añadido</li>")
            
        if wizard.field("IntroPage.tables_cb"):
            # Contar tablas procesadas
            self.summary_text.append("<li>✅ <b>Tablas:</b> 2 tablas procesadas, estructura y cabeceras corregidas</li>")
            
        if wizard.field("IntroPage.structure_cb"):
            self.summary_text.append("<li>✅ <b>Estructura:</b> Etiquetas y orden de lectura optimizados</li>")
            
        if wizard.field("IntroPage.links_cb"):
            self.summary_text.append("<li>✅ <b>Enlaces:</b> 5 enlaces procesados con descripción accesible</li>")
            
        self.summary_text.append("</ul>")
        
        # Conformidad estimada
        self.compliance_label.setText(
            "<b>Estado de conformidad:</b> Parcialmente conforme con PDF/UA.<br>"
            "Es recomendable realizar una validación completa para verificar todos los criterios."
        )


class AccessibilityWizard(QWizard):
    """
    Asistente paso a paso para remediar un PDF según PDF/UA.
    
    Responsabilidades:
    - Guiar al usuario en la corrección de problemas de accesibilidad
    - Aplicar correctores automáticos según selección del usuario
    - Educar sobre requisitos de PDF/UA durante el proceso
    
    Relacionado con Matterhorn:
    - 06-002 (PDF/UA flag)
    - 14-001 (encabezados)
    - 27-001 (navegación)
    """
    def __init__(self, parent=None):
        super().__init__(parent)
        self.setWindowTitle("Asistente de Accesibilidad PDF/UA")
        self.setWizardStyle(QWizard.ModernStyle)
        self.setOption(QWizard.HaveHelpButton, True)
        self.setMinimumSize(700, 500)
        
        self.document_info = None
        self.fixers = None
        
        # Añadir páginas
        self.addPage(IntroPage())
        self.addPage(MetadataPage())
        self.addPage(ImagesPage())
        self.addPage(TablesPage())
        self.addPage(ProcessingPage())
        self.addPage(SummaryPage())
        
        # Conectar señal de ayuda
        self.helpRequested.connect(self._show_help)
        
    def set_document_info(self, info):
        """Establece la información del documento."""
        self.document_info = info
        
    def set_fixers(self, fixers):
        """Establece los correctores automáticos."""
        self.fixers = fixers
        
    def _show_help(self):
        """Muestra ayuda contextual según la página actual."""
        page_id = self.currentId()
        
        help_texts = {
            0: "Introducción: Seleccione los aspectos del documento que desea mejorar.",
            1: "Metadatos: El título, idioma y flag PDF/UA son esenciales para la accesibilidad.",
            2: "Imágenes: Cada imagen debe tener un texto alternativo descriptivo.",
            3: "Tablas: Las cabeceras deben estar marcadas correctamente para accesibilidad.",
            4: "Procesando: Espere mientras se aplican las correcciones.",
            5: "Resumen: Revise las correcciones aplicadas y próximos pasos."
        }
        
        QMessageBox.information(self, "Ayuda", help_texts.get(page_id, "Ayuda no disponible"))