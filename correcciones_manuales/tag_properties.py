# correcciones_manuales/tag_properties.py

from PySide6.QtWidgets import (QWidget, QVBoxLayout, QHBoxLayout, QFormLayout,
                              QLineEdit, QTextEdit, QComboBox, QLabel, QPushButton,
                              QGroupBox, QScrollArea, QMessageBox, QCheckBox,
                              QSpinBox, QFrame)
from PySide6.QtCore import Qt, Signal, QTimer
from PySide6.QtGui import QFont, QTextOption
from loguru import logger

class TagPropertiesEditor(QWidget):
    """
    Editor de propiedades de etiquetas PDF.
    Permite modificar atributos como Alt, Lang, Scope, etc.
    """
    
    propertiesChanged = Signal(str, dict)  # node_id, properties
    nodeTypeChanged = Signal(str, str)  # node_id, new_type
    contentChanged = Signal(str, str)  # node_id, new_content
    
    def __init__(self, parent=None):
        super().__init__(parent)
        
        self.structure_manager = None
        self.current_node_id = None
        self.current_node = None
        self.updating_ui = False
        
        # Timer para cambios diferidos
        self.change_timer = QTimer()
        self.change_timer.setSingleShot(True)
        self.change_timer.timeout.connect(self._apply_pending_changes)
        
        self.pending_changes = {}
        
        self._init_ui()
    
    def _init_ui(self):
        """Inicializa la interfaz de usuario."""
        # Layout principal con scroll
        main_layout = QVBoxLayout(self)
        
        # Área de scroll
        scroll_area = QScrollArea()
        scroll_area.setWidgetResizable(True)
        scroll_area.setHorizontalScrollBarPolicy(Qt.ScrollBarAsNeeded)
        scroll_area.setVerticalScrollBarPolicy(Qt.ScrollBarAsNeeded)
        
        # Widget contenido
        content_widget = QWidget()
        content_layout = QVBoxLayout(content_widget)
        
        # Información del elemento
        self._create_element_info_section(content_layout)
        
        # Separador
        separator1 = QFrame()
        separator1.setFrameShape(QFrame.HLine)
        separator1.setFrameShadow(QFrame.Sunken)
        content_layout.addWidget(separator1)
        
        # Tipo de elemento
        self._create_element_type_section(content_layout)
        
        # Separador
        separator2 = QFrame()
        separator2.setFrameShape(QFrame.HLine)
        separator2.setFrameShadow(QFrame.Sunken)
        content_layout.addWidget(separator2)
        
        # Contenido de texto
        self._create_text_content_section(content_layout)
        
        # Separador
        separator3 = QFrame()
        separator3.setFrameShape(QFrame.HLine)
        separator3.setFrameShadow(QFrame.Sunken)
        content_layout.addWidget(separator3)
        
        # Atributos comunes
        self._create_common_attributes_section(content_layout)
        
        # Separador
        separator4 = QFrame()
        separator4.setFrameShape(QFrame.HLine)
        separator4.setFrameShadow(QFrame.Sunken)
        content_layout.addWidget(separator4)
        
        # Atributos específicos
        self._create_specific_attributes_section(content_layout)
        
        # Stretch al final
        content_layout.addStretch()
        
        # Configurar scroll area
        scroll_area.setWidget(content_widget)
        main_layout.addWidget(scroll_area)
        
        # Botones de acción
        self._create_action_buttons(main_layout)
        
        # Inicialmente deshabilitado
        self.setEnabled(False)
    
    def _create_element_info_section(self, layout):
        """Crea la sección de información del elemento."""
        info_group = QGroupBox("Información del Elemento")
        info_layout = QFormLayout(info_group)
        
        # ID del elemento (solo lectura)
        self.element_id_label = QLabel("-")
        self.element_id_label.setStyleSheet("QLabel { background-color: #f5f5f5; padding: 4px; }")
        info_layout.addRow("ID:", self.element_id_label)
        
        # Página
        self.page_label = QLabel("-")
        self.page_label.setStyleSheet("QLabel { background-color: #f5f5f5; padding: 4px; }")
        info_layout.addRow("Página:", self.page_label)
        
        # Nivel de anidamiento
        self.depth_label = QLabel("-")
        self.depth_label.setStyleSheet("QLabel { background-color: #f5f5f5; padding: 4px; }")
        info_layout.addRow("Nivel:", self.depth_label)
        
        layout.addWidget(info_group)
    
    def _create_element_type_section(self, layout):
        """Crea la sección de tipo de elemento."""
        type_group = QGroupBox("Tipo de Elemento")
        type_layout = QFormLayout(type_group)
        
        # Combo box para el tipo
        self.type_combo = QComboBox()
        self.type_combo.setEditable(True)
        self.type_combo.addItems([
            "P", "H1", "H2", "H3", "H4", "H5", "H6", "Span", "Div",
            "Figure", "Table", "TR", "TH", "TD", "THead", "TBody", "TFoot",
            "L", "LI", "Lbl", "LBody", "Link", "Quote", "Note", "Code",
            "Form", "Reference", "BibEntry", "Caption", "TOC", "TOCI",
            "Index", "Art", "Sect", "Part", "Document", "NonStruct", "Private"
        ])
        self.type_combo.currentTextChanged.connect(self._on_type_changed)
        type_layout.addRow("Tipo:", self.type_combo)
        
        # Descripción del tipo seleccionado
        self.type_description = QLabel()
        self.type_description.setWordWrap(True)
        self.type_description.setStyleSheet("QLabel { color: #666; font-style: italic; }")
        type_layout.addRow("Descripción:", self.type_description)
        
        layout.addWidget(type_group)
    
    def _create_text_content_section(self, layout):
        """Crea la sección de contenido de texto."""
        text_group = QGroupBox("Contenido de Texto")
        text_layout = QVBoxLayout(text_group)
        
        # Editor de texto
        self.text_edit = QTextEdit()
        self.text_edit.setMaximumHeight(100)
        self.text_edit.setPlaceholderText("Contenido de texto del elemento...")
        self.text_edit.textChanged.connect(self._on_text_changed)
        text_layout.addWidget(self.text_edit)
        
        # Información adicional
        info_label = QLabel("Nota: Este es el texto principal del elemento. Para figuras, use el atributo Alt.")
        info_label.setStyleSheet("QLabel { color: #666; font-size: 10px; }")
        info_label.setWordWrap(True)
        text_layout.addWidget(info_label)
        
        layout.addWidget(text_group)
    
    def _create_common_attributes_section(self, layout):
        """Crea la sección de atributos comunes."""
        common_group = QGroupBox("Atributos Comunes")
        common_layout = QFormLayout(common_group)
        
        # Alt (texto alternativo)
        self.alt_edit = QLineEdit()
        self.alt_edit.setPlaceholderText("Texto alternativo para elementos gráficos...")
        self.alt_edit.textChanged.connect(lambda: self._on_attribute_changed("alt", self.alt_edit.text()))
        common_layout.addRow("Alt:", self.alt_edit)
        
        # ActualText
        self.actual_text_edit = QLineEdit()
        self.actual_text_edit.setPlaceholderText("Texto real para expansión de abreviaciones...")
        self.actual_text_edit.textChanged.connect(lambda: self._on_attribute_changed("actualtext", self.actual_text_edit.text()))
        common_layout.addRow("ActualText:", self.actual_text_edit)
        
        # E (expansion text)
        self.e_edit = QLineEdit()
        self.e_edit.setPlaceholderText("Texto de expansión...")
        self.e_edit.textChanged.connect(lambda: self._on_attribute_changed("e", self.e_edit.text()))
        common_layout.addRow("E:", self.e_edit)
        
        # Lang (idioma)
        self.lang_combo = QComboBox()
        self.lang_combo.setEditable(True)
        self.lang_combo.addItems([
            "", "es-ES", "en-US", "fr-FR", "de-DE", "it-IT", "pt-PT", "pt-BR",
            "ru-RU", "zh-CN", "ja-JP", "ko-KR", "ar-SA", "ca-ES", "eu-ES", "gl-ES"
        ])
        self.lang_combo.currentTextChanged.connect(lambda: self._on_attribute_changed("lang", self.lang_combo.currentText()))
        common_layout.addRow("Lang:", self.lang_combo)
        
        # ID
        self.id_edit = QLineEdit()
        self.id_edit.setPlaceholderText("Identificador único del elemento...")
        self.id_edit.textChanged.connect(lambda: self._on_attribute_changed("id", self.id_edit.text()))
        common_layout.addRow("ID:", self.id_edit)
        
        layout.addWidget(common_group)
    
    def _create_specific_attributes_section(self, layout):
        """Crea la sección de atributos específicos."""
        specific_group = QGroupBox("Atributos Específicos")
        specific_layout = QFormLayout(specific_group)
        
        # Scope (para TH)
        self.scope_combo = QComboBox()
        self.scope_combo.addItems(["", "Row", "Col", "Both"])
        self.scope_combo.currentTextChanged.connect(lambda: self._on_attribute_changed("scope", self.scope_combo.currentText()))
        specific_layout.addRow("Scope (TH):", self.scope_combo)
        
        # Headers (para TD)
        self.headers_edit = QLineEdit()
        self.headers_edit.setPlaceholderText("IDs de cabeceras separados por espacios...")
        self.headers_edit.textChanged.connect(lambda: self._on_attribute_changed("headers", self.headers_edit.text()))
        specific_layout.addRow("Headers (TD):", self.headers_edit)
        
        # ColSpan
        self.colspan_spin = QSpinBox()
        self.colspan_spin.setMinimum(1)
        self.colspan_spin.setMaximum(100)
        self.colspan_spin.setValue(1)
        self.colspan_spin.valueChanged.connect(lambda: self._on_attribute_changed("colspan", str(self.colspan_spin.value()) if self.colspan_spin.value() > 1 else ""))
        specific_layout.addRow("ColSpan:", self.colspan_spin)
        
        # RowSpan
        self.rowspan_spin = QSpinBox()
        self.rowspan_spin.setMinimum(1)
        self.rowspan_spin.setMaximum(100)
        self.rowspan_spin.setValue(1)
        self.rowspan_spin.valueChanged.connect(lambda: self._on_attribute_changed("rowspan", str(self.rowspan_spin.value()) if self.rowspan_spin.value() > 1 else ""))
        specific_layout.addRow("RowSpan:", self.rowspan_spin)
        
        # ListNumbering (para L)
        self.list_numbering_combo = QComboBox()
        self.list_numbering_combo.addItems(["", "Decimal", "UpperRoman", "LowerRoman", "UpperAlpha", "LowerAlpha"])
        self.list_numbering_combo.currentTextChanged.connect(lambda: self._on_attribute_changed("listnumbering", self.list_numbering_combo.currentText()))
        specific_layout.addRow("ListNumbering (L):", self.list_numbering_combo)
        
        layout.addWidget(specific_group)
    
    def _create_action_buttons(self, layout):
        """Crea los botones de acción."""
        buttons_layout = QHBoxLayout()
        
        # Botón de aplicar cambios
        self.apply_btn = QPushButton("Aplicar Cambios")
        self.apply_btn.clicked.connect(self._apply_all_changes)
        self.apply_btn.setEnabled(False)
        buttons_layout.addWidget(self.apply_btn)
        
        # Botón de revertir
        self.revert_btn = QPushButton("Revertir")
        self.revert_btn.clicked.connect(self._revert_changes)
        self.revert_btn.setEnabled(False)
        buttons_layout.addWidget(self.revert_btn)
        
        buttons_layout.addStretch()
        
        # Botón de ayuda
        self.help_btn = QPushButton("Ayuda")
        self.help_btn.clicked.connect(self._show_help)
        buttons_layout.addWidget(self.help_btn)
        
        layout.addLayout(buttons_layout)
    
    def set_structure_manager(self, structure_manager):
        """Establece el gestor de estructura."""
        self.structure_manager = structure_manager
    
    def set_node(self, node_id):
        """Establece el nodo actual para editar."""
        if not self.structure_manager:
            return
        
        self.current_node_id = str(node_id) if node_id else None
        
        if self.current_node_id:
            self.current_node = self.structure_manager.get_node(self.current_node_id)
            if self.current_node:
                self._load_node_data()
                self.setEnabled(True)
            else:
                logger.warning(f"Nodo {self.current_node_id} no encontrado")
                self._clear_form()
                self.setEnabled(False)
        else:
            self._clear_form()
            self.setEnabled(False)
    
    def _load_node_data(self):
        """Carga los datos del nodo actual en el formulario."""
        if not self.current_node:
            return
        
        self.updating_ui = True
        
        try:
            # Información del elemento
            self.element_id_label.setText(str(self.current_node_id))
            self.page_label.setText(str(self.current_node.get("page", "-") + 1))
            # TODO: Calcular nivel de anidamiento
            self.depth_label.setText("-")
            
            # Tipo de elemento
            element_type = self.current_node.get("type", "")
            self.type_combo.setCurrentText(element_type)
            self._update_type_description(element_type)
            
            # Contenido de texto
            text_content = self.current_node.get("text", "")
            self.text_edit.setPlainText(text_content)
            
            # Atributos
            attributes = self.current_node.get("attributes", {})
            
            self.alt_edit.setText(attributes.get("alt", ""))
            self.actual_text_edit.setText(attributes.get("actualtext", ""))
            self.e_edit.setText(attributes.get("e", ""))
            self.lang_combo.setCurrentText(attributes.get("lang", ""))
            self.id_edit.setText(attributes.get("id", ""))
            
            self.scope_combo.setCurrentText(attributes.get("scope", ""))
            self.headers_edit.setText(attributes.get("headers", ""))
            
            # ColSpan y RowSpan
            colspan = attributes.get("colspan", "1")
            try:
                self.colspan_spin.setValue(int(colspan) if colspan else 1)
            except ValueError:
                self.colspan_spin.setValue(1)
            
            rowspan = attributes.get("rowspan", "1")
            try:
                self.rowspan_spin.setValue(int(rowspan) if rowspan else 1)
            except ValueError:
                self.rowspan_spin.setValue(1)
            
            self.list_numbering_combo.setCurrentText(attributes.get("listnumbering", ""))
            
            # Habilitar/deshabilitar controles según el tipo
            self._update_controls_visibility(element_type)
            
        finally:
            self.updating_ui = False
            
        # Limpiar cambios pendientes
        self.pending_changes.clear()
        self._update_buttons_state()
    
    def _clear_form(self):
        """Limpia todos los campos del formulario."""
        self.updating_ui = True
        
        try:
            self.element_id_label.setText("-")
            self.page_label.setText("-")
            self.depth_label.setText("-")
            
            self.type_combo.setCurrentText("")
            self.text_edit.clear()
            
            self.alt_edit.clear()
            self.actual_text_edit.clear()
            self.e_edit.clear()
            self.lang_combo.setCurrentText("")
            self.id_edit.clear()
            
            self.scope_combo.setCurrentText("")
            self.headers_edit.clear()
            self.colspan_spin.setValue(1)
            self.rowspan_spin.setValue(1)
            self.list_numbering_combo.setCurrentText("")
            
        finally:
            self.updating_ui = False
        
        self.pending_changes.clear()
        self._update_buttons_state()
    
    def _update_type_description(self, element_type):
        """Actualiza la descripción del tipo de elemento."""
        descriptions = {
            "P": "Párrafo - Bloque de texto básico",
            "H1": "Encabezado nivel 1 - Título principal",
            "H2": "Encabezado nivel 2 - Subtítulo",
            "H3": "Encabezado nivel 3",
            "H4": "Encabezado nivel 4",
            "H5": "Encabezado nivel 5",
            "H6": "Encabezado nivel 6",
            "Span": "Texto en línea con propiedades específicas",
            "Div": "División o sección genérica",
            "Figure": "Figura, imagen o gráfico (requiere Alt)",
            "Table": "Tabla de datos",
            "TR": "Fila de tabla",
            "TH": "Celda de cabecera de tabla (requiere Scope)",
            "TD": "Celda de datos de tabla",
            "THead": "Grupo de cabeceras de tabla",
            "TBody": "Grupo de cuerpo de tabla",
            "TFoot": "Grupo de pie de tabla",
            "L": "Lista (puede requerir ListNumbering)",
            "LI": "Elemento de lista",
            "Lbl": "Etiqueta de elemento de lista",
            "LBody": "Cuerpo de elemento de lista",
            "Link": "Enlace hipertexto",
            "Quote": "Cita",
            "Note": "Nota o comentario",
            "Code": "Código fuente",
            "Form": "Formulario",
            "Reference": "Referencia bibliográfica",
            "BibEntry": "Entrada bibliográfica",
            "Caption": "Título o leyenda",
            "TOC": "Tabla de contenidos",
            "TOCI": "Elemento de tabla de contenidos",
            "Index": "Índice",
            "Art": "Artículo",
            "Sect": "Sección",
            "Part": "Parte del documento",
            "Document": "Documento completo",
            "NonStruct": "Contenido sin estructura semántica",
            "Private": "Contenido privado o propietario"
        }
        
        description = descriptions.get(element_type, "Tipo de elemento personalizado")
        self.type_description.setText(description)
    
    def _update_controls_visibility(self, element_type):
        """Actualiza la visibilidad de controles según el tipo de elemento."""
        # Habilitar/deshabilitar scope según el tipo
        is_th = element_type == "TH"
        self.scope_combo.setEnabled(is_th)
        
        # Habilitar/deshabilitar headers según el tipo
        is_td = element_type == "TD"
        self.headers_edit.setEnabled(is_td)
        
        # Habilitar/deshabilitar colspan/rowspan para celdas
        is_cell = element_type in ["TH", "TD"]
        self.colspan_spin.setEnabled(is_cell)
        self.rowspan_spin.setEnabled(is_cell)
        
        # Habilitar/deshabilitar ListNumbering para listas
        is_list = element_type == "L"
        self.list_numbering_combo.setEnabled(is_list)
        
        # Resaltar alt para figuras
        is_figure = element_type == "Figure"
        if is_figure:
            self.alt_edit.setStyleSheet("QLineEdit { border: 2px solid orange; }")
        else:
            self.alt_edit.setStyleSheet("")
    
    def _on_type_changed(self, new_type):
        """Maneja el cambio de tipo de elemento."""
        if self.updating_ui:
            return
        
        if not self.current_node_id:
            return
        
        # Validar el nuevo tipo
        if not self._validate_type_change(new_type):
            return
        
        self.pending_changes["type"] = new_type
        self._update_type_description(new_type)
        self._update_controls_visibility(new_type)
        self._update_buttons_state()
        
        # Aplicar cambio con delay
        self.change_timer.start(1000)
    
    def _on_text_changed(self):
        """Maneja el cambio de contenido de texto."""
        if self.updating_ui:
            return
        
        if not self.current_node_id:
            return
        
        new_text = self.text_edit.toPlainText()
        self.pending_changes["text"] = new_text
        self._update_buttons_state()
        
        # Aplicar cambio con delay
        self.change_timer.start(1000)
    
    def _on_attribute_changed(self, attribute_name, value):
        """Maneja el cambio de un atributo."""
        if self.updating_ui:
            return
        
        if not self.current_node_id:
            return
        
        # Guardar cambio pendiente
        if "attributes" not in self.pending_changes:
            self.pending_changes["attributes"] = {}
        
        self.pending_changes["attributes"][attribute_name] = value
        self._update_buttons_state()
        
        # Aplicar cambio con delay
        self.change_timer.start(1000)
    
    def _validate_type_change(self, new_type):
        """Valida si el cambio de tipo es apropiado."""
        if not new_type.strip():
            return False
        
        # Validaciones básicas
        valid_types = [
            "P", "H1", "H2", "H3", "H4", "H5", "H6", "Span", "Div",
            "Figure", "Table", "TR", "TH", "TD", "THead", "TBody", "TFoot",
            "L", "LI", "Lbl", "LBody", "Link", "Quote", "Note", "Code",
            "Form", "Reference", "BibEntry", "Caption", "TOC", "TOCI",
            "Index", "Art", "Sect", "Part", "Document", "NonStruct", "Private"
        ]
        
        # Permitir tipos personalizados pero advertir
        if new_type not in valid_types:
            response = QMessageBox.question(
                self,
                "Tipo personalizado",
                f"'{new_type}' no es un tipo estándar. ¿Desea continuar?",
                QMessageBox.Yes | QMessageBox.No,
                QMessageBox.No
            )
            return response == QMessageBox.Yes
        
        return True
    
    def _apply_pending_changes(self):
        """Aplica los cambios pendientes."""
        if not self.pending_changes or not self.current_node_id:
            return
        
        try:
            # Aplicar cambio de tipo
            if "type" in self.pending_changes:
                new_type = self.pending_changes["type"]
                self.nodeTypeChanged.emit(self.current_node_id, new_type)
            
            # Aplicar cambio de texto
            if "text" in self.pending_changes:
                new_text = self.pending_changes["text"]
                self.contentChanged.emit(self.current_node_id, new_text)
            
            # Aplicar cambios de atributos
            if "attributes" in self.pending_changes:
                attributes = self.pending_changes["attributes"]
                self.propertiesChanged.emit(self.current_node_id, attributes)
            
            # Limpiar cambios pendientes
            self.pending_changes.clear()
            self._update_buttons_state()
            
            logger.debug("Cambios aplicados correctamente")
            
        except Exception as e:
            logger.error(f"Error aplicando cambios: {e}")
            QMessageBox.critical(self, "Error", f"Error al aplicar cambios: {str(e)}")
    
    def _apply_all_changes(self):
        """Aplica todos los cambios inmediatamente."""
        self.change_timer.stop()
        self._apply_pending_changes()
    
    def _revert_changes(self):
        """Revierte los cambios pendientes."""
        self.change_timer.stop()
        self.pending_changes.clear()
        self._load_node_data()
        
        QMessageBox.information(self, "Cambios revertidos", "Los cambios han sido revertidos.")
    
    def _update_buttons_state(self):
        """Actualiza el estado de los botones."""
        has_changes = bool(self.pending_changes)
        self.apply_btn.setEnabled(has_changes)
        self.revert_btn.setEnabled(has_changes)
    
    def _show_help(self):
        """Muestra ayuda sobre los atributos."""
        help_text = """
<h3>Atributos de Etiquetas PDF/UA</h3>

<h4>Atributos Comunes:</h4>
<ul>
<li><b>Alt:</b> Texto alternativo para figuras y elementos gráficos (requerido para Figure)</li>
<li><b>ActualText:</b> Texto real cuando el contenido visual no es legible</li>
<li><b>E:</b> Texto de expansión para abreviaciones</li>
<li><b>Lang:</b> Código de idioma (ej: es-ES, en-US)</li>
<li><b>ID:</b> Identificador único del elemento</li>
</ul>

<h4>Atributos de Tabla:</h4>
<ul>
<li><b>Scope:</b> Alcance de celdas de cabecera (Row, Col, Both)</li>
<li><b>Headers:</b> IDs de cabeceras relacionadas (para TD)</li>
<li><b>ColSpan:</b> Número de columnas que abarca la celda</li>
<li><b>RowSpan:</b> Número de filas que abarca la celda</li>
</ul>

<h4>Atributos de Lista:</h4>
<ul>
<li><b>ListNumbering:</b> Tipo de numeración (Decimal, UpperRoman, etc.)</li>
</ul>

<p><i>Para más información, consulte la documentación de PDF/UA y Tagged PDF.</i></p>
        """
        
        msg = QMessageBox(self)
        msg.setWindowTitle("Ayuda - Atributos de Etiquetas")
        msg.setText(help_text)
        msg.setTextFormat(Qt.RichText)
        msg.exec_()