# correcciones_manuales/structure_view.py

from PySide6.QtWidgets import (QWidget, QVBoxLayout, QHBoxLayout, QTreeWidget, 
                              QTreeWidgetItem, QPushButton, QLineEdit, QLabel,
                              QMenu, QMessageBox, QHeaderView)
from PySide6.QtCore import Qt, Signal, QTimer
from PySide6.QtGui import QAction, QIcon, QFont
from loguru import logger
import qtawesome as qta

class StructureView(QWidget):
    """
    Vista del árbol de estructura lógica del documento PDF.
    Muestra la jerarquía de etiquetas y permite seleccionar elementos.
    """
    
    nodeSelected = Signal(str)  # Emite el ID del nodo seleccionado
    nodeChanged = Signal(str, dict)  # Emite cambios en el nodo
    
    def __init__(self, parent=None):
        super().__init__(parent)
        
        self.structure_manager = None
        self.current_tree_data = None
        self.node_id_mapping = {}  # Mapeo de QTreeWidgetItem a IDs de elementos
        
        self._init_ui()
        self._setup_context_menu()
    
    def _init_ui(self):
        """Inicializa la interfaz de usuario."""
        layout = QVBoxLayout(self)
        
        # Barra de herramientas superior
        toolbar_layout = QHBoxLayout()
        
        # Botón de expandir/colapsar
        self.expand_btn = QPushButton("Expandir Todo")
        self.expand_btn.clicked.connect(self._on_expand_all)
        toolbar_layout.addWidget(self.expand_btn)
        
        self.collapse_btn = QPushButton("Colapsar Todo")
        self.collapse_btn.clicked.connect(self._on_collapse_all)
        toolbar_layout.addWidget(self.collapse_btn)
        
        toolbar_layout.addStretch()
        
        # Campo de búsqueda
        self.search_label = QLabel("Buscar:")
        toolbar_layout.addWidget(self.search_label)
        
        self.search_field = QLineEdit()
        self.search_field.setPlaceholderText("Buscar en estructura...")
        self.search_field.textChanged.connect(self._on_search_text_changed)
        toolbar_layout.addWidget(self.search_field)
        
        layout.addLayout(toolbar_layout)
        
        # Árbol de estructura
        self.tree_widget = QTreeWidget()
        self.tree_widget.setHeaderLabels(["Elemento", "Tipo", "Página", "Texto/Atributos"])
        self.tree_widget.itemSelectionChanged.connect(self._on_selection_changed)
        self.tree_widget.itemDoubleClicked.connect(self._on_item_double_clicked)
        
        # Configurar el árbol
        header = self.tree_widget.header()
        header.setSectionResizeMode(0, QHeaderView.ResizeToContents)
        header.setSectionResizeMode(1, QHeaderView.ResizeToContents)
        header.setSectionResizeMode(2, QHeaderView.ResizeToContents)
        header.setSectionResizeMode(3, QHeaderView.Stretch)
        
        # Habilitar menú contextual
        self.tree_widget.setContextMenuPolicy(Qt.CustomContextMenu)
        self.tree_widget.customContextMenuRequested.connect(self._show_context_menu)
        
        layout.addWidget(self.tree_widget)
        
        # Timer para búsqueda diferida
        self.search_timer = QTimer()
        self.search_timer.setSingleShot(True)
        self.search_timer.timeout.connect(self._perform_search)
    
    def _setup_context_menu(self):
        """Configura el menú contextual."""
        self.context_menu = QMenu(self)
        
        # Acciones del menú contextual
        self.action_add_child = QAction("Añadir hijo", self)
        self.action_add_child.triggered.connect(self._on_add_child)
        self.context_menu.addAction(self.action_add_child)
        
        self.action_delete = QAction("Eliminar", self)
        self.action_delete.triggered.connect(self._on_delete_element)
        self.context_menu.addAction(self.action_delete)
        
        self.context_menu.addSeparator()
        
        self.action_move_up = QAction("Mover arriba", self)
        self.action_move_up.triggered.connect(self._on_move_up)
        self.context_menu.addAction(self.action_move_up)
        
        self.action_move_down = QAction("Mover abajo", self)
        self.action_move_down.triggered.connect(self._on_move_down)
        self.context_menu.addAction(self.action_move_down)
        
        self.context_menu.addSeparator()
        
        self.action_expand_branch = QAction("Expandir rama", self)
        self.action_expand_branch.triggered.connect(self._on_expand_branch)
        self.context_menu.addAction(self.action_expand_branch)
        
        self.action_collapse_branch = QAction("Colapsar rama", self)
        self.action_collapse_branch.triggered.connect(self._on_collapse_branch)
        self.context_menu.addAction(self.action_collapse_branch)
    
    def set_structure_manager(self, structure_manager):
        """Establece el gestor de estructura."""
        self.structure_manager = structure_manager
        self.refresh_view()
    
    def refresh_view(self):
        """Actualiza la vista del árbol desde el gestor de estructura."""
        if not self.structure_manager:
            self.tree_widget.clear()
            return
        
        # Obtener la estructura actual
        structure_tree = self.structure_manager.get_structure_tree()
        if not structure_tree:
            self.tree_widget.clear()
            return
        
        # Guardar estado de expansión antes de limpiar
        expanded_items = self._get_expanded_state()
        
        # Limpiar y reconstruir el árbol
        self.tree_widget.clear()
        self.node_id_mapping.clear()
        self.current_tree_data = structure_tree
        
        # Construir el árbol
        if structure_tree.get("children"):
            for child in structure_tree["children"]:
                self._build_tree_item(child, self.tree_widget)
        
        # Restaurar estado de expansión
        self._restore_expanded_state(expanded_items)
        
        logger.debug("Vista de estructura actualizada")
    
    def _build_tree_item(self, node_data, parent_item):
        """Construye un elemento del árbol recursivamente."""
        if not isinstance(node_data, dict):
            return None
        
        # Crear elemento del árbol
        if isinstance(parent_item, QTreeWidget):
            tree_item = QTreeWidgetItem(parent_item)
        else:
            tree_item = QTreeWidgetItem(parent_item)
        
        # Obtener información del nodo
        element_type = node_data.get("type", "Unknown")
        page_num = node_data.get("page", "")
        element_text = node_data.get("text", "").strip()
        attributes = node_data.get("attributes", {})
        
        # Generar texto descriptivo usando el método del pdf_loader
        if self.structure_manager and hasattr(self.structure_manager, "pdf_loader"):
            display_text = self.structure_manager.pdf_loader.get_element_display_text(node_data)
        else:
            display_text = self._generate_display_text(node_data)
        
        # Configurar columnas
        tree_item.setText(0, display_text)
        tree_item.setText(1, element_type)
        tree_item.setText(2, str(page_num + 1) if isinstance(page_num, int) else str(page_num))
        
        # Generar texto de atributos/contenido para la última columna
        info_parts = []
        if element_text and len(element_text) <= 100:
            info_parts.append(f"Text: {element_text}")
        elif element_text:
            info_parts.append(f"Text: {element_text[:97]}...")
        
        # Añadir atributos importantes
        important_attrs = ["alt", "scope", "headers", "lang", "actualtext"]
        for attr in important_attrs:
            if attr in attributes and attributes[attr]:
                attr_value = str(attributes[attr])
                if len(attr_value) > 50:
                    attr_value = attr_value[:47] + "..."
                info_parts.append(f"{attr.upper()}: {attr_value}")
        
        tree_item.setText(3, " | ".join(info_parts))
        
        # Configurar estilo según el tipo de elemento
        self._set_item_style(tree_item, element_type)
        
        # Generar ID único para el mapeo
        element_id = id(node_data.get("element")) if node_data.get("element") else id(node_data)
        self.node_id_mapping[tree_item] = element_id
        
        # Procesar hijos recursivamente
        children = node_data.get("children", [])
        for child in children:
            self._build_tree_item(child, tree_item)
        
        return tree_item
    
    def _generate_display_text(self, node_data):
        """Genera texto para mostrar basado en el tipo y contenido del nodo."""
        element_type = node_data.get("type", "Unknown")
        element_text = node_data.get("text", "").strip()
        
        if element_type == "StructTreeRoot":
            child_count = len(node_data.get("children", []))
            return f"Document Root ({child_count} children)"
        
        elif element_type in ["H1", "H2", "H3", "H4", "H5", "H6"]:
            if element_text:
                preview = element_text[:40] + "..." if len(element_text) > 40 else element_text
                return f"{element_type}: {preview}"
            else:
                return f"{element_type} (empty)"
        
        elif element_type == "P":
            if element_text:
                preview = element_text[:50] + "..." if len(element_text) > 50 else element_text
                return f"Paragraph: {preview}"
            else:
                return "Paragraph (empty)"
        
        else:
            if element_text:
                preview = element_text[:40] + "..." if len(element_text) > 40 else element_text
                return f"{element_type}: {preview}"
            else:
                child_count = len(node_data.get("children", []))
                if child_count > 0:
                    return f"{element_type} ({child_count} children)"
                else:
                    return f"{element_type}"
    
    def _set_item_style(self, tree_item, element_type):
        """Establece el estilo visual del elemento según su tipo."""
        font = QFont()
        
        # Configurar estilo según el tipo
        if element_type in ["H1", "H2", "H3", "H4", "H5", "H6"]:
            font.setBold(True)
            if element_type == "H1":
                font.setPointSize(12)
            elif element_type == "H2":
                font.setPointSize(11)
        elif element_type == "Figure":
            font.setItalic(True)
        elif element_type in ["Table", "TR", "TH", "TD"]:
            # Color especial para elementos de tabla
            pass
        elif element_type in ["L", "LI"]:
            # Color especial para listas
            pass
        
        tree_item.setFont(0, font)
    
    def select_node(self, node_id):
        """Selecciona un nodo en el árbol por su ID."""
        for tree_item, mapped_id in self.node_id_mapping.items():
            if mapped_id == node_id:
                self.tree_widget.setCurrentItem(tree_item)
                self.tree_widget.scrollToItem(tree_item)
                break
    
    def _get_expanded_state(self):
        """Obtiene el estado de expansión actual del árbol."""
        expanded_items = set()
        
        def collect_expanded(item, path=""):
            if item.isExpanded():
                item_path = f"{path}/{item.text(0)}"
                expanded_items.add(item_path)
            
            for i in range(item.childCount()):
                child = item.child(i)
                collect_expanded(child, f"{path}/{item.text(0)}")
        
        root = self.tree_widget.invisibleRootItem()
        for i in range(root.childCount()):
            collect_expanded(root.child(i))
        
        return expanded_items
    
    def _restore_expanded_state(self, expanded_items):
        """Restaura el estado de expansión del árbol."""
        def restore_item(item, path=""):
            item_path = f"{path}/{item.text(0)}"
            if item_path in expanded_items:
                item.setExpanded(True)
            
            for i in range(item.childCount()):
                child = item.child(i)
                restore_item(child, item_path)
        
        root = self.tree_widget.invisibleRootItem()
        for i in range(root.childCount()):
            restore_item(root.child(i))
    
    def _on_selection_changed(self):
        """Maneja el cambio de selección en el árbol."""
        current_item = self.tree_widget.currentItem()
        if current_item and current_item in self.node_id_mapping:
            node_id = self.node_id_mapping[current_item]
            self.nodeSelected.emit(str(node_id))
    
    def _on_item_double_clicked(self, item, column):
        """Maneja el doble clic en un elemento."""
        if item in self.node_id_mapping:
            node_id = self.node_id_mapping[item]
            # Emitir señal para ir a la página del elemento
            self.nodeSelected.emit(str(node_id))
    
    def _on_expand_all(self):
        """Expande todos los elementos del árbol."""
        self.tree_widget.expandAll()
    
    def _on_collapse_all(self):
        """Colapsa todos los elementos del árbol."""
        self.tree_widget.collapseAll()
    
    def _on_search_text_changed(self, text):
        """Maneja el cambio en el texto de búsqueda."""
        # Usar timer para búsqueda diferida
        self.search_timer.stop()
        self.search_timer.start(300)  # 300ms de delay
    
    def _perform_search(self):
        """Realiza la búsqueda en el árbol."""
        search_text = self.search_field.text().lower().strip()
        
        if not search_text:
            # Mostrar todos los elementos si no hay texto de búsqueda
            self._show_all_items()
            return
        
        # Ocultar todos los elementos inicialmente
        self._hide_all_items()
        
        # Mostrar elementos que coinciden con la búsqueda
        self._search_and_show_items(search_text)
    
    def _show_all_items(self):
        """Muestra todos los elementos del árbol."""
        def show_item(item):
            item.setHidden(False)
            for i in range(item.childCount()):
                show_item(item.child(i))
        
        root = self.tree_widget.invisibleRootItem()
        for i in range(root.childCount()):
            show_item(root.child(i))
    
    def _hide_all_items(self):
        """Oculta todos los elementos del árbol."""
        def hide_item(item):
            item.setHidden(True)
            for i in range(item.childCount()):
                hide_item(item.child(i))
        
        root = self.tree_widget.invisibleRootItem()
        for i in range(root.childCount()):
            hide_item(root.child(i))
    
    def _search_and_show_items(self, search_text):
        """Busca elementos que coinciden con el texto y los muestra junto con sus padres."""
        matches = []
        
        def search_item(item, parent_chain=[]):
            # Verificar si este elemento coincide
            item_text = " ".join([
                item.text(0).lower(),
                item.text(1).lower(),
                item.text(3).lower()
            ])
            
            is_match = search_text in item_text
            
            current_chain = parent_chain + [item]
            
            if is_match:
                matches.extend(current_chain)
            
            # Buscar en hijos
            for i in range(item.childCount()):
                search_item(item.child(i), current_chain)
        
        # Realizar búsqueda
        root = self.tree_widget.invisibleRootItem()
        for i in range(root.childCount()):
            search_item(root.child(i))
        
        # Mostrar elementos que coinciden y sus padres
        for item in set(matches):
            item.setHidden(False)
            item.setExpanded(True)
    
    def _show_context_menu(self, position):
        """Muestra el menú contextual."""
        item = self.tree_widget.itemAt(position)
        if item:
            # Actualizar estado de las acciones según el contexto
            self._update_context_actions(item)
            self.context_menu.exec_(self.tree_widget.mapToGlobal(position))
    
    def _update_context_actions(self, item):
        """Actualiza el estado de las acciones del menú contextual."""
        # Verificar si se puede mover arriba/abajo
        parent = item.parent()
        if parent:
            index = parent.indexOfChild(item)
            self.action_move_up.setEnabled(index > 0)
            self.action_move_down.setEnabled(index < parent.childCount() - 1)
        else:
            # Es un elemento raíz
            root = self.tree_widget.invisibleRootItem()
            index = root.indexOfChild(item)
            self.action_move_up.setEnabled(index > 0)
            self.action_move_down.setEnabled(index < root.childCount() - 1)
        
        # Verificar si se puede eliminar (no eliminar raíz del documento)
        element_type = item.text(1)
        self.action_delete.setEnabled(element_type != "StructTreeRoot")
    
    # Métodos de acción del menú contextual
    def _on_add_child(self):
        """Añade un elemento hijo."""
        current_item = self.tree_widget.currentItem()
        if current_item and current_item in self.node_id_mapping:
            node_id = self.node_id_mapping[current_item]
            # Aquí se podría abrir un diálogo para seleccionar el tipo de elemento
            # Por ahora, emitir señal para que el gestor maneje la adición
            logger.info(f"Solicitar añadir hijo a nodo {node_id}")
    
    def _on_delete_element(self):
        """Elimina el elemento seleccionado."""
        current_item = self.tree_widget.currentItem()
        if current_item and current_item in self.node_id_mapping:
            node_id = self.node_id_mapping[current_item]
            element_type = current_item.text(1)
            
            # Confirmar eliminación
            response = QMessageBox.question(
                self,
                "Eliminar elemento",
                f"¿Está seguro de que desea eliminar el elemento '{element_type}'?",
                QMessageBox.Yes | QMessageBox.No,
                QMessageBox.No
            )
            
            if response == QMessageBox.Yes:
                # Solicitar eliminación al gestor
                if self.structure_manager:
                    self.structure_manager.delete_element(node_id)
    
    def _on_move_up(self):
        """Mueve el elemento hacia arriba."""
        current_item = self.tree_widget.currentItem()
        if current_item and current_item in self.node_id_mapping:
            node_id = self.node_id_mapping[current_item]
            if self.structure_manager:
                self.structure_manager.move_element_up(node_id)
    
    def _on_move_down(self):
        """Mueve el elemento hacia abajo."""
        current_item = self.tree_widget.currentItem()
        if current_item and current_item in self.node_id_mapping:
            node_id = self.node_id_mapping[current_item]
            if self.structure_manager:
                self.structure_manager.move_element_down(node_id)
    
    def _on_expand_branch(self):
        """Expande toda la rama del elemento seleccionado."""
        current_item = self.tree_widget.currentItem()
        if current_item:
            current_item.setExpanded(True)
            self._expand_all_children(current_item)
    
    def _on_collapse_branch(self):
        """Colapsa toda la rama del elemento seleccionado."""
        current_item = self.tree_widget.currentItem()
        if current_item:
            self._collapse_all_children(current_item)
            current_item.setExpanded(False)
    
    def _expand_all_children(self, item):
        """Expande recursivamente todos los hijos de un elemento."""
        for i in range(item.childCount()):
            child = item.child(i)
            child.setExpanded(True)
            self._expand_all_children(child)
    
    def _collapse_all_children(self, item):
        """Colapsa recursivamente todos los hijos de un elemento."""
        for i in range(item.childCount()):
            child = item.child(i)
            self._collapse_all_children(child)
            child.setExpanded(False)