# pdfua_editor/correcciones_manuales/structure_view.py

from PySide6.QtWidgets import (QTreeWidget, QTreeWidgetItem, QMenu, QAbstractItemView,
                                QDialog, QVBoxLayout, QLabel, QComboBox, 
                               QDialogButtonBox, QLineEdit, QMessageBox)
from PySide6.QtCore import Qt, Signal, QPoint
from PySide6.QtGui import QIcon, QAction

from loguru import logger

# Iconos para diferentes tipos de etiquetas
TAG_ICONS = {
    "Document": "📄", 
    "H1": "🔥", "H2": "🔥", "H3": "🔥", "H4": "🔥", "H5": "🔥", "H6": "🔥",
    "P": "📝",
    "L": "📋", "LI": "🔹", "Lbl": "🔸", "LBody": "📌",
    "Table": "🔲", "TR": "➖", "TH": "🔳", "TD": "⬜", "THead": "🔝", "TBody": "📊", "TFoot": "🔚",
    "Figure": "🖼️", 
    "Formula": "➗",
    "Form": "📮",
    "Link": "🔗",
    "Note": "📌",
    "Reference": "📎",
    "default": "📑"
}

# Lista de tipos de etiquetas estándar en PDF/UA
PDF_STANDARD_TAGS = ["Document", "Part", "Art", "Sect", "Div", "P", 
                     "H1", "H2", "H3", "H4", "H5", "H6", 
                     "L", "LI", "Lbl", "LBody", 
                     "Table", "TR", "TH", "TD", "THead", "TBody", "TFoot", 
                     "Figure", "Formula", "Form", 
                     "Link", "Note", "Reference", "BibEntry", 
                     "Quote", "BlockQuote", "Caption", 
                     "TOC", "TOCI", "Index", "NonStruct", "Private"]

class StructureTreeModel:
    """Modelo para la estructura de etiquetas del PDF."""
    
    def __init__(self, structure_manager=None):
        self.structure_manager = structure_manager
        self.root = None
        
    def set_structure_manager(self, structure_manager):
        """Establece el gestor de estructura."""
        self.structure_manager = structure_manager
        self.root = structure_manager.get_structure_tree() if structure_manager else None
        
    def get_element_display_text(self, element):
        """Obtiene el texto a mostrar para un elemento."""
        if not element:
            return "Unknown"
            
        element_type = element.get("type", "Unknown")
        element_text = element.get("text", "").strip()
        
        # Truncar texto largo
        if len(element_text) > 30:
            element_text = element_text[:27] + "..."
            
        icon = TAG_ICONS.get(element_type, TAG_ICONS["default"])
        
        if element_text:
            return f"{icon} {element_type}: {element_text}"
        else:
            return f"{icon} {element_type}"
    
    def get_element_tooltip(self, element):
        """Obtiene el tooltip para un elemento."""
        if not element:
            return ""
            
        tooltips = []
        
        # Añadir tipo
        tooltips.append(f"Tipo: {element.get('type', 'Unknown')}")
        
        # Añadir texto si existe
        text = element.get("text", "").strip()
        if text:
            # Truncar texto largo para el tooltip
            if len(text) > 100:
                text = text[:97] + "..."
            tooltips.append(f"Texto: {text}")
            
        # Añadir página
        page = element.get("page", 0)
        tooltips.append(f"Página: {page + 1}")
        
        # Añadir atributos relevantes si existen
        pikepdf_element = element.get("element")
        if pikepdf_element:
            for attr_name in ["Alt", "ActualText", "Lang", "Scope", "ListNumbering"]:
                attr_key = f"/{attr_name}"
                if attr_key in pikepdf_element:
                    attr_value = str(pikepdf_element[attr_key])
                    if attr_value.startswith("/"):  # Es un Name
                        attr_value = attr_value[1:]
                    tooltips.append(f"{attr_name}: {attr_value}")
                    
        return "\n".join(tooltips)

class StructureView(QTreeWidget):
    """Widget para visualizar y gestionar la estructura de etiquetas del PDF."""
    
    nodeSelected = Signal(object)  # Señal emitida con el ID del elemento seleccionado
    
    def __init__(self, parent=None):
        super().__init__(parent)
        
        # Configurar el widget
        self.setHeaderLabel("Estructura del PDF")
        self.setSelectionMode(QAbstractItemView.SingleSelection)
        self.setContextMenuPolicy(Qt.CustomContextMenu)
        self.customContextMenuRequested.connect(self.show_context_menu)
        
        # Modelo
        self.structure_manager = None
        self.tree_model = StructureTreeModel()
        
        # Mapa para asociar elementos de UI con nodos de estructura
        self.item_to_element_map = {}
        
    def set_structure_manager(self, structure_manager):
        """Establece el gestor de estructura y actualiza la vista."""
        self.structure_manager = structure_manager
        self.tree_model.set_structure_manager(structure_manager)
        self.refresh_view()
        
    def refresh_view(self):
        """Actualiza la vista del árbol con la estructura actual."""
        # Limpiar la vista
        self.clear()
        self.item_to_element_map = {}
        
        # Si no hay gestor o estructura, terminar
        if not self.structure_manager:
            return
            
        structure_tree = self.structure_manager.get_structure_tree()
        if not structure_tree:
            return
            
        # Construir el árbol recursivamente
        self.build_tree_recursive(structure_tree, None)
        
        # Expandir el primer nivel
        root_items = [self.topLevelItem(i) for i in range(self.topLevelItemCount())]
        for item in root_items:
            item.setExpanded(True)
    
    def build_tree_recursive(self, node, parent_item):
        """Construye el árbol de forma recursiva."""
        if not node:
            return
            
        # Crear ítem según el tipo de nodo
        if isinstance(node, dict):
            # Si es un nodo de estructura, añadirlo al árbol
            if "type" in node and "element" in node:
                # Crear el ítem
                if parent_item:
                    item = QTreeWidgetItem(parent_item)
                else:
                    item = QTreeWidgetItem(self)
                    
                # Configurar el ítem
                item.setText(0, self.tree_model.get_element_display_text(node))
                item.setToolTip(0, self.tree_model.get_element_tooltip(node))
                
                # Almacenar relación ítem-elemento
                element_id = id(node["element"])
                self.item_to_element_map[id(item)] = element_id
                
                # Procesar hijos recursivamente
                if "children" in node:
                    for child in node["children"]:
                        self.build_tree_recursive(child, item)
        
        # Si es una lista, procesar cada elemento
        elif isinstance(node, list):
            for item in node:
                self.build_tree_recursive(item, parent_item)
    
    def select_node(self, element_id):
        """Selecciona un nodo específico en el árbol."""
        # Intentar convertir a entero si es una cadena
        if isinstance(element_id, str):
            try:
                element_id = int(element_id)
            except ValueError:
                pass
        
        # Buscar el ítem correspondiente al elemento
        for item_id, mapped_element_id in self.item_to_element_map.items():
            if mapped_element_id == element_id:
                # Encontrar el ítem real
                def find_item_by_id(root_item, target_id):
                    if id(root_item) == target_id:
                        return root_item
                        
                    for i in range(root_item.childCount()):
                        child = root_item.child(i)
                        result = find_item_by_id(child, target_id)
                        if result:
                            return result
                            
                    return None
                
                # Buscar en elementos de primer nivel
                for i in range(self.topLevelItemCount()):
                    root_item = self.topLevelItem(i)
                    item = find_item_by_id(root_item, item_id)
                    if item:
                        self.setCurrentItem(item)
                        return True
                        
        return False
    
    def mousePressEvent(self, event):
        """Maneja los eventos de clic del ratón."""
        super().mousePressEvent(event)
        
        # Emitir señal con el elemento seleccionado (si existe)
        item = self.currentItem()
        if item:
            element_id = self.item_to_element_map.get(id(item))
            if element_id:
                self.nodeSelected.emit(element_id)
    
    def show_context_menu(self, position):
        """Muestra el menú contextual para operaciones en nodos."""
        item = self.itemAt(position)
        if not item:
            return
            
        element_id = self.item_to_element_map.get(id(item))
        if not element_id:
            return
            
        # Crear menú
        menu = QMenu(self)
        
        # Añadir acciones
        rename_action = QAction("Cambiar tipo de etiqueta", self)
        rename_action.triggered.connect(lambda: self.request_rename_tag(element_id))
        menu.addAction(rename_action)
        
        add_alt_action = QAction("Añadir/Editar texto alternativo", self)
        add_alt_action.triggered.connect(lambda: self.request_add_alt_text(element_id))
        menu.addAction(add_alt_action)
        
        add_lang_action = QAction("Añadir/Editar atributo de idioma", self)
        add_lang_action.triggered.connect(lambda: self.request_add_language(element_id))
        menu.addAction(add_lang_action)
        
        menu.addSeparator()
        
        delete_action = QAction("Eliminar etiqueta", self)
        delete_action.triggered.connect(lambda: self.request_delete_tag(element_id))
        menu.addAction(delete_action)
        
        menu.addSeparator()
        
        move_up_action = QAction("Mover arriba", self)
        move_up_action.triggered.connect(lambda: self.request_move_tag_up(element_id))
        menu.addAction(move_up_action)
        
        move_down_action = QAction("Mover abajo", self)
        move_down_action.triggered.connect(lambda: self.request_move_tag_down(element_id))
        menu.addAction(move_down_action)
        
        # Mostrar menú
        menu.exec_(self.mapToGlobal(position))
    
    def request_rename_tag(self, element_id):
        """Solicita cambiar el tipo de una etiqueta."""
        if not self.structure_manager:
            return
        
        # Obtener información del elemento actual
        element = self.structure_manager.get_node(element_id)
        if not element:
            return
        
        # Crear un cuadro de diálogo con un selector de tipos de etiqueta
        dialog = QDialog(self)
        dialog.setWindowTitle("Cambiar tipo de etiqueta")
        
        layout = QVBoxLayout(dialog)
        
        type_label = QLabel("Nuevo tipo de etiqueta:")
        layout.addWidget(type_label)
        
        type_combo = QComboBox()
        # Llenar el combo con los tipos de etiquetas estándar
        type_combo.addItems(PDF_STANDARD_TAGS)
        # Establecer el tipo actual como valor por defecto
        current_type = element.get("type", "")
        if current_type in PDF_STANDARD_TAGS:
            type_combo.setCurrentText(current_type)
        layout.addWidget(type_combo)
        
        button_box = QDialogButtonBox(QDialogButtonBox.Ok | QDialogButtonBox.Cancel)
        button_box.accepted.connect(dialog.accept)
        button_box.rejected.connect(dialog.reject)
        layout.addWidget(button_box)
        
        if dialog.exec_() == QDialog.Accepted:
            new_type = type_combo.currentText()
            if new_type != current_type:
                # Validar el cambio
                validation = self.structure_manager.validate_node_type_change(element_id, new_type)
                if validation.get("valid", False):
                    # Actualizar el tipo de etiqueta
                    self.structure_manager.update_node_type(element_id, new_type)
                    # Actualizar la vista
                    self.refresh_view()
                else:
                    # Mostrar mensaje de error
                    QMessageBox.warning(
                        self,
                        "Error de validación",
                        f"No se puede cambiar el tipo de etiqueta: {validation.get('reason', 'Error desconocido')}"
                    )
    
    def request_add_alt_text(self, element_id):
        """Solicita añadir o editar texto alternativo."""
        if not self.structure_manager:
            return
        
        # Obtener información del elemento actual
        element = self.structure_manager.get_node(element_id)
        if not element:
            return
        
        # Obtener el texto alternativo actual (si existe)
        alt_text = ""
        pikepdf_element = element.get("element")
        if pikepdf_element:
            if hasattr(pikepdf_element, "Alt"):
                alt_text = str(pikepdf_element.Alt)
            elif "/Alt" in pikepdf_element:
                alt_text = str(pikepdf_element["/Alt"])
        
        # Crear un cuadro de diálogo para editar el texto alternativo
        dialog = QDialog(self)
        dialog.setWindowTitle("Texto alternativo")
        
        layout = QVBoxLayout(dialog)
        
        label = QLabel("Texto alternativo:")
        layout.addWidget(label)
        
        text_edit = QLineEdit()
        text_edit.setText(alt_text)
        layout.addWidget(text_edit)
        
        button_box = QDialogButtonBox(QDialogButtonBox.Ok | QDialogButtonBox.Cancel)
        button_box.accepted.connect(dialog.accept)
        button_box.rejected.connect(dialog.reject)
        layout.addWidget(button_box)
        
        if dialog.exec_() == QDialog.Accepted:
            new_alt_text = text_edit.text()
            # Actualizar el texto alternativo
            self.structure_manager.update_tag_attribute(element_id, "Alt", new_alt_text)
            # No es necesario actualizar la vista, ya que el Alt no afecta a la apariencia visual
    
    def request_add_language(self, element_id):
        """Solicita añadir o editar atributo de idioma."""
        if not self.structure_manager:
            return
        
        # Obtener información del elemento actual
        element = self.structure_manager.get_node(element_id)
        if not element:
            return
        
        # Obtener el idioma actual (si existe)
        lang = ""
        pikepdf_element = element.get("element")
        if pikepdf_element:
            if hasattr(pikepdf_element, "Lang"):
                lang = str(pikepdf_element.Lang)
            elif "/Lang" in pikepdf_element:
                lang = str(pikepdf_element["/Lang"])
        
        # Crear un cuadro de diálogo para editar el idioma
        dialog = QDialog(self)
        dialog.setWindowTitle("Atributo de idioma")
        
        layout = QVBoxLayout(dialog)
        
        label = QLabel("Idioma (Lang):")
        layout.addWidget(label)
        
        text_edit = QLineEdit()
        text_edit.setText(lang)
        text_edit.setPlaceholderText("es-ES, en-US, fr-FR...")
        layout.addWidget(text_edit)
        
        button_box = QDialogButtonBox(QDialogButtonBox.Ok | QDialogButtonBox.Cancel)
        button_box.accepted.connect(dialog.accept)
        button_box.rejected.connect(dialog.reject)
        layout.addWidget(button_box)
        
        if dialog.exec_() == QDialog.Accepted:
            new_lang = text_edit.text()
            # Actualizar el idioma
            self.structure_manager.update_tag_attribute(element_id, "Lang", new_lang)
            # No es necesario actualizar la vista, ya que el Lang no afecta a la apariencia visual
    
    def request_delete_tag(self, element_id):
        """Solicita eliminar una etiqueta."""
        if not self.structure_manager:
            return
        
        # Preguntar confirmación
        reply = QMessageBox.question(
            self,
            "Confirmar eliminación",
            "¿Está seguro de que desea eliminar esta etiqueta?",
            QMessageBox.Yes | QMessageBox.No,
            QMessageBox.No
        )
        
        if reply == QMessageBox.Yes:
            # Eliminar la etiqueta
            self.structure_manager.delete_tag(element_id)
            # Actualizar la vista
            self.refresh_view()
    
    def request_move_tag_up(self, element_id):
        """Solicita mover una etiqueta hacia arriba."""
        if not self.structure_manager:
            return
        
        # Mover la etiqueta hacia arriba
        self.structure_manager.move_tag_up(element_id)
        # Actualizar la vista
        self.refresh_view()
        # Seleccionar nuevamente la etiqueta
        self.select_node(element_id)
    
    def request_move_tag_down(self, element_id):
        """Solicita mover una etiqueta hacia abajo."""
        if not self.structure_manager:
            return
        
        # Mover la etiqueta hacia abajo
        self.structure_manager.move_tag_down(element_id)
        # Actualizar la vista
        self.refresh_view()
        # Seleccionar nuevamente la etiqueta
        self.select_node(element_id)