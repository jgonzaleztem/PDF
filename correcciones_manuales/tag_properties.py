# pdfua_editor/correcciones_manuales/tag_properties.py

from PySide6.QtWidgets import (QWidget, QVBoxLayout, QGridLayout, QLabel, 
                              QLineEdit, QComboBox, QGroupBox, QPushButton,
                              QScrollArea, QCheckBox)
from PySide6.QtCore import Qt, Signal
from loguru import logger
from pikepdf import Name, String

# Lista de tipos de etiquetas estándar en PDF/UA
PDF_STANDARD_TAGS = ["Document", "Part", "Art", "Sect", "Div", "P", 
                     "H1", "H2", "H3", "H4", "H5", "H6", 
                     "L", "LI", "Lbl", "LBody", 
                     "Table", "TR", "TH", "TD", "THead", "TBody", "TFoot", 
                     "Figure", "Formula", "Form", 
                     "Link", "Note", "Reference", "BibEntry", 
                     "Quote", "BlockQuote", "Caption", 
                     "TOC", "TOCI", "Index", "NonStruct", "Private"]

class TagPropertiesEditor(QScrollArea):
    """Editor de propiedades para etiquetas PDF/UA."""
    
    propertiesChanged = Signal(object, dict)  # ID del elemento, propiedades cambiadas
    nodeTypeChanged = Signal(object, str)     # ID del elemento, nuevo tipo
    contentChanged = Signal(object, str)      # ID del elemento, nuevo contenido
    
    def __init__(self, parent=None):
        super().__init__(parent)
        
        self.setWidgetResizable(True)
        self.current_element_id = None
        self.current_element = None
        self.structure_manager = None
        
        # Widget contenedor
        container = QWidget()
        self.setWidget(container)
        
        # Layout principal
        self.main_layout = QVBoxLayout(container)
        
        # Mensaje para cuando no hay selección
        self.no_selection_label = QLabel("Seleccione un elemento de la estructura para ver sus propiedades.")
        self.no_selection_label.setAlignment(Qt.AlignCenter)
        self.no_selection_label.setWordWrap(True)
        self.main_layout.addWidget(self.no_selection_label)
        
        # Contenedor para propiedades (inicialmente oculto)
        self.properties_container = QWidget()
        self.properties_layout = QVBoxLayout(self.properties_container)
        self.properties_container.setVisible(False)
        self.main_layout.addWidget(self.properties_container)
        
        # Inicializar campos de propiedades comunes
        self._init_common_properties()
        
        # Espacio flexible
        self.main_layout.addStretch()
    
    def _init_common_properties(self):
        """Inicializa los campos para propiedades comunes."""
        # Grupo de propiedades generales
        general_group = QGroupBox("Propiedades generales")
        general_layout = QGridLayout()
        
        # Tipo de elemento
        general_layout.addWidget(QLabel("Tipo:"), 0, 0)
        self.type_label = QLineEdit()
        self.type_label.setReadOnly(True)
        general_layout.addWidget(self.type_label, 0, 1)
        
        # Selector de tipo
        general_layout.addWidget(QLabel("Cambiar a:"), 1, 0)
        self.type_selector = QComboBox()
        self.type_selector.addItems(PDF_STANDARD_TAGS)
        general_layout.addWidget(self.type_selector, 1, 1)
        
        # Texto de contenido
        general_layout.addWidget(QLabel("Contenido:"), 2, 0)
        self.content_edit = QLineEdit()
        general_layout.addWidget(self.content_edit, 2, 1)
        
        # Idioma
        general_layout.addWidget(QLabel("Idioma (Lang):"), 3, 0)
        self.lang_edit = QLineEdit()
        self.lang_edit.setPlaceholderText("es-ES, en-US, fr-FR...")
        general_layout.addWidget(self.lang_edit, 3, 1)
        
        general_group.setLayout(general_layout)
        self.properties_layout.addWidget(general_group)
        
        # Grupo de propiedades específicas (se mostrarán según el tipo)
        self.specific_group = QGroupBox("Propiedades específicas")
        self.specific_layout = QGridLayout(self.specific_group)
        
        # Propiedad Alt (para Figure)
        self.alt_label = QLabel("Texto alternativo (Alt):")
        self.alt_edit = QLineEdit()
        self.specific_layout.addWidget(self.alt_label, 0, 0)
        self.specific_layout.addWidget(self.alt_edit, 0, 1)
        
        # Propiedad ActualText (para cualquier elemento)
        self.actualtext_label = QLabel("Texto de reemplazo (ActualText):")
        self.actualtext_edit = QLineEdit()
        self.specific_layout.addWidget(self.actualtext_label, 1, 0)
        self.specific_layout.addWidget(self.actualtext_edit, 1, 1)
        
        # Propiedad Scope (para TH)
        self.scope_label = QLabel("Ámbito (Scope):")
        self.scope_combo = QComboBox()
        self.scope_combo.addItems(["Row", "Column", "Both", "None"])
        self.specific_layout.addWidget(self.scope_label, 2, 0)
        self.specific_layout.addWidget(self.scope_combo, 2, 1)
        
        # Propiedad ListNumbering (para L)
        self.listnumbering_label = QLabel("Numeración de lista:")
        self.listnumbering_combo = QComboBox()
        self.listnumbering_combo.addItems(["None", "Decimal", "UpperRoman", "LowerRoman", "UpperAlpha", "LowerAlpha"])
        self.specific_layout.addWidget(self.listnumbering_label, 3, 0)
        self.specific_layout.addWidget(self.listnumbering_combo, 3, 1)
        
        # Botón de aplicar cambios
        self.apply_button = QPushButton("Aplicar cambios")
        self.apply_button.clicked.connect(self._on_apply_changes)
        self.specific_layout.addWidget(self.apply_button, 4, 0, 1, 2)
        
        self.properties_layout.addWidget(self.specific_group)
        
        # Ocultar todos los campos específicos inicialmente
        self._show_specific_properties([])
    
    def _show_specific_properties(self, properties_to_show):
        """Muestra u oculta propiedades específicas según la lista proporcionada."""
        # Ocultar todas las propiedades específicas
        properties = {
            'alt': (self.alt_label, self.alt_edit),
            'actualtext': (self.actualtext_label, self.actualtext_edit),
            'scope': (self.scope_label, self.scope_combo),
            'listnumbering': (self.listnumbering_label, self.listnumbering_combo)
        }
        
        for prop_name, widgets in properties.items():
            for widget in widgets:
                widget.setVisible(prop_name in properties_to_show)
    
    def set_structure_manager(self, structure_manager):
        """Establece el gestor de estructura."""
        self.structure_manager = structure_manager
    
    def set_node(self, element_id):
        """Configura el editor con las propiedades del elemento seleccionado."""
        if not self.structure_manager:
            return
            
        # Obtener el elemento
        # Intentar convertir a entero si es una cadena
        if isinstance(element_id, str):
            try:
                element_id = int(element_id)
            except ValueError:
                pass
                
        self.current_element = self.structure_manager.get_node(element_id)
        self.current_element_id = element_id
        
        if not self.current_element:
            self.no_selection_label.setVisible(True)
            self.properties_container.setVisible(False)
            return
            
        # Mostrar el contenedor de propiedades
        self.no_selection_label.setVisible(False)
        self.properties_container.setVisible(True)
        
        # Configurar propiedades generales
        element_type = self.current_element.get("type", "Unknown")
        self.type_label.setText(element_type)
        self.type_selector.setCurrentText(element_type)
        
        # Configurar contenido
        self.content_edit.setText(self.current_element.get("text", ""))
        
        # Configurar propiedades específicas
        pikepdf_element = self.current_element.get("element")
        if pikepdf_element:
            try:
                # Idioma
                lang = ""
                if hasattr(pikepdf_element, "Lang"):
                    lang = str(pikepdf_element.Lang)
                elif "/Lang" in pikepdf_element:
                    lang = str(pikepdf_element["/Lang"])
                self.lang_edit.setText(lang)
                
                # Determinar qué propiedades específicas mostrar
                properties_to_show = []
                
                # Alt para Figure
                if element_type == "Figure":
                    properties_to_show.append('alt')
                    alt_text = ""
                    if hasattr(pikepdf_element, "Alt"):
                        alt_text = str(pikepdf_element.Alt)
                    elif "/Alt" in pikepdf_element:
                        alt_text = str(pikepdf_element["/Alt"])
                    self.alt_edit.setText(alt_text)
                
                # ActualText para cualquier elemento
                properties_to_show.append('actualtext')
                actual_text = ""
                if hasattr(pikepdf_element, "ActualText"):
                    actual_text = str(pikepdf_element.ActualText)
                elif "/ActualText" in pikepdf_element:
                    actual_text = str(pikepdf_element["/ActualText"])
                self.actualtext_edit.setText(actual_text)
                
                # Scope para TH
                if element_type == "TH":
                    properties_to_show.append('scope')
                    scope = "None"
                    if hasattr(pikepdf_element, "Scope"):
                        scope = str(pikepdf_element.Scope)
                        if scope.startswith("/"):
                            scope = scope[1:]  # Quitar el "/" inicial
                    elif "/Scope" in pikepdf_element:
                        scope = str(pikepdf_element["/Scope"])
                        if scope.startswith("/"):
                            scope = scope[1:]  # Quitar el "/" inicial
                    self.scope_combo.setCurrentText(scope)
                
                # ListNumbering para L
                if element_type == "L":
                    properties_to_show.append('listnumbering')
                    list_numbering = "None"
                    if hasattr(pikepdf_element, "ListNumbering"):
                        list_numbering = str(pikepdf_element.ListNumbering)
                        if list_numbering.startswith("/"):
                            list_numbering = list_numbering[1:]  # Quitar el "/" inicial
                    elif "/ListNumbering" in pikepdf_element:
                        list_numbering = str(pikepdf_element["/ListNumbering"])
                        if list_numbering.startswith("/"):
                            list_numbering = list_numbering[1:]  # Quitar el "/" inicial
                    self.listnumbering_combo.setCurrentText(list_numbering)
                
                # Mostrar solo las propiedades relevantes
                self._show_specific_properties(properties_to_show)
                
            except Exception as e:
                logger.error(f"Error al obtener propiedades del elemento: {str(e)}")
                # Aún así, mostrar las propiedades básicas
                self._show_specific_properties([])
        else:
            # No hay elemento pikepdf, mostrar solo las propiedades básicas
            self._show_specific_properties([])
    
    def _on_apply_changes(self):
        """Aplica los cambios realizados a las propiedades."""
        if not self.current_element_id or not self.structure_manager:
            return
            
        try:
            # Verificar si hay cambio de tipo
            new_type = self.type_selector.currentText()
            current_type = self.type_label.text()
            
            if new_type != current_type:
                # Validar el cambio de tipo
                validation = self.structure_manager.validate_node_type_change(
                    self.current_element_id, new_type)
                
                if validation.get("valid", False):
                    self.nodeTypeChanged.emit(self.current_element_id, new_type)
                else:
                    logger.warning(f"Cambio de tipo no válido: {validation.get('reason', 'Razón desconocida')}")
                    # Restablecer selector al tipo actual
                    self.type_selector.setCurrentText(current_type)
            
            # Verificar cambios en el contenido
            new_content = self.content_edit.text()
            old_content = self.current_element.get("text", "")
            
            if new_content != old_content:
                self.contentChanged.emit(self.current_element_id, new_content)
            
            # Recopilar cambios en propiedades
            changes = {}
            
            # Idioma
            new_lang = self.lang_edit.text().strip()
            pikepdf_element = self.current_element["element"]
            old_lang = ""
            
            if hasattr(pikepdf_element, "Lang"):
                old_lang = str(pikepdf_element.Lang)
            elif "/Lang" in pikepdf_element:
                old_lang = str(pikepdf_element["/Lang"])
                
            if new_lang != old_lang:
                changes["Lang"] = new_lang if new_lang else None
            
            # Alt para Figure
            if self.current_element.get("type") == "Figure" and self.alt_label.isVisible():
                new_alt = self.alt_edit.text().strip()
                old_alt = ""
                
                if hasattr(pikepdf_element, "Alt"):
                    old_alt = str(pikepdf_element.Alt)
                elif "/Alt" in pikepdf_element:
                    old_alt = str(pikepdf_element["/Alt"])
                    
                if new_alt != old_alt:
                    changes["Alt"] = new_alt if new_alt else None
            
            # ActualText para cualquier elemento
            if self.actualtext_label.isVisible():
                new_actualtext = self.actualtext_edit.text().strip()
                old_actualtext = ""
                
                if hasattr(pikepdf_element, "ActualText"):
                    old_actualtext = str(pikepdf_element.ActualText)
                elif "/ActualText" in pikepdf_element:
                    old_actualtext = str(pikepdf_element["/ActualText"])
                    
                if new_actualtext != old_actualtext:
                    changes["ActualText"] = new_actualtext if new_actualtext else None
            
            # Scope para TH
            if self.current_element.get("type") == "TH" and self.scope_label.isVisible():
                new_scope = self.scope_combo.currentText()
                if new_scope == "None":
                    new_scope = None
                    
                old_scope = "None"
                if hasattr(pikepdf_element, "Scope"):
                    old_scope = str(pikepdf_element.Scope)
                    if old_scope.startswith("/"):
                        old_scope = old_scope[1:]  # Quitar el "/" inicial
                elif "/Scope" in pikepdf_element:
                    old_scope = str(pikepdf_element["/Scope"])
                    if old_scope.startswith("/"):
                        old_scope = old_scope[1:]  # Quitar el "/" inicial
                    
                if new_scope != old_scope:
                    changes["Scope"] = new_scope
            
            # ListNumbering para L
            if self.current_element.get("type") == "L" and self.listnumbering_label.isVisible():
                new_listnumbering = self.listnumbering_combo.currentText()
                if new_listnumbering == "None":
                    new_listnumbering = None
                    
                old_listnumbering = "None"
                if hasattr(pikepdf_element, "ListNumbering"):
                    old_listnumbering = str(pikepdf_element.ListNumbering)
                    if old_listnumbering.startswith("/"):
                        old_listnumbering = old_listnumbering[1:]
                elif "/ListNumbering" in pikepdf_element:
                    old_listnumbering = str(pikepdf_element["/ListNumbering"])
                    if old_listnumbering.startswith("/"):
                        old_listnumbering = old_listnumbering[1:]
                    
                if new_listnumbering != old_listnumbering:
                    changes["ListNumbering"] = new_listnumbering
            
            # Emitir señal con cambios
            if changes:
                self.propertiesChanged.emit(self.current_element_id, changes)
            
            logger.info(f"Cambios aplicados: {changes}")
            
        except Exception as e:
            logger.error(f"Error al aplicar cambios: {e}")