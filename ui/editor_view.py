# pdfua_editor/ui/editor_view.py

from PySide6.QtWidgets import (QWidget, QSplitter, QVBoxLayout, QHBoxLayout, 
                              QPushButton, QMessageBox, QApplication)
from PySide6.QtCore import Qt, Signal
from loguru import logger

from correcciones_manuales.structure_view import StructureView
from correcciones_manuales.tag_properties import TagPropertiesEditor

class EditorView(QWidget):
    """
    Vista combinada para edición de estructura del PDF que incluye el árbol de estructura 
    y el editor de propiedades de etiquetas.
    """
    
    structureChanged = Signal()  # Emitida cuando la estructura cambia
    nodeSelected = Signal(str)   # ID del nodo seleccionado
    
    def __init__(self, parent=None):
        super().__init__(parent)
        
        self.structure_manager = None
        self.current_node_id = None
        
        self._init_ui()
    
    def _init_ui(self):
        """Inicializa la interfaz de usuario."""
        main_layout = QVBoxLayout(self)
        
        # Crear un splitter horizontal para dividir la vista
        self.splitter = QSplitter(Qt.Horizontal)
        
        # Panel izquierdo - Vista del árbol de estructura
        self.structure_view = StructureView()
        self.structure_view.nodeSelected.connect(self._on_node_selected)
        self.splitter.addWidget(self.structure_view)
        
        # Panel derecho - Editor de propiedades de etiquetas
        self.tag_properties = TagPropertiesEditor()
        self.tag_properties.propertiesChanged.connect(self._on_properties_changed)
        self.tag_properties.nodeTypeChanged.connect(self._on_node_type_changed)
        self.tag_properties.contentChanged.connect(self._on_content_changed)
        self.splitter.addWidget(self.tag_properties)
        
        # Establecer tamaños iniciales
        self.splitter.setSizes([int(self.width() * 0.4), int(self.width() * 0.6)])
        
        # Añadir splitter al layout principal
        main_layout.addWidget(self.splitter)
        
        # Barra de botones para acciones globales
        buttons_layout = QHBoxLayout()
        
        self.apply_btn = QPushButton("Aplicar Cambios")
        self.apply_btn.clicked.connect(self._on_apply_clicked)
        buttons_layout.addWidget(self.apply_btn)
        
        self.undo_btn = QPushButton("Deshacer")
        self.undo_btn.clicked.connect(self._on_undo_clicked)
        buttons_layout.addWidget(self.undo_btn)
        
        self.redo_btn = QPushButton("Rehacer")
        self.redo_btn.clicked.connect(self._on_redo_clicked)
        buttons_layout.addWidget(self.redo_btn)
        
        main_layout.addLayout(buttons_layout)
    
    def set_structure_manager(self, structure_manager):
        """Establece el gestor de estructura."""
        self.structure_manager = structure_manager
        self.structure_view.set_structure_manager(structure_manager)
        self.tag_properties.set_structure_manager(structure_manager)
    
    def refresh_structure_view(self):
        """Actualiza la vista del árbol de estructura."""
        if self.structure_manager:
            self.structure_view.refresh_view()
            
            # Mantener la selección actual si existe
            if self.current_node_id:
                self.structure_view.select_node(self.current_node_id)
    
    def select_node(self, node_id):
        """Selecciona un nodo en la vista de estructura."""
        if not node_id or not self.structure_manager:
            return
            
        # Verificar que el nodo existe
        if self.structure_manager.get_node(node_id):
            self.structure_view.select_node(node_id)
            self.tag_properties.set_node(node_id)
            self.current_node_id = node_id
        else:
            logger.warning(f"Intento de seleccionar nodo inexistente: {node_id}")
    
    def _on_node_selected(self, node_id):
        """Maneja la selección de un nodo en la vista de estructura."""
        self.tag_properties.set_node(node_id)
        self.current_node_id = node_id
        self.nodeSelected.emit(node_id)
    
    def _on_properties_changed(self, node_id, properties):
        """Maneja cambios en las propiedades del nodo."""
        if not self.structure_manager or not node_id:
            return
            
        for attr_name, attr_value in properties.items():
            self.structure_manager.update_node_attribute(node_id, attr_name, attr_value)
            
        self.structureChanged.emit()
    
    def _on_node_type_changed(self, node_id, new_type):
        """Maneja el cambio de tipo de nodo."""
        if not self.structure_manager or not node_id:
            return
            
        # La validación ya se realizó en TagPropertiesEditor
        self.structure_manager.update_node_type(node_id, new_type)
        self.structureChanged.emit()
        
        # Actualizar editor de propiedades con nuevo tipo
        self.tag_properties.set_node(node_id)
    
    def _on_content_changed(self, node_id, new_content):
        """Maneja cambios en el contenido del nodo."""
        if not self.structure_manager or not node_id:
            return
            
        self.structure_manager.update_node_content(node_id, new_content)
        self.structureChanged.emit()
    
    def _on_apply_clicked(self):
        """Aplica los cambios al PDF."""
        if not self.structure_manager:
            return
            
        try:
            QApplication.setOverrideCursor(Qt.WaitCursor)
            success = self.structure_manager.apply_changes()
            QApplication.restoreOverrideCursor()
            
            if success:
                QMessageBox.information(self, "Cambios Aplicados", 
                                      "Los cambios han sido aplicados correctamente.")
                
                # Actualizar la vista después de aplicar cambios
                self.refresh_structure_view()
            else:
                QMessageBox.warning(self, "Advertencia", 
                                  "No se pudieron aplicar los cambios o no había cambios para aplicar.")
                
        except Exception as e:
            QApplication.restoreOverrideCursor()
            logger.error(f"Error al aplicar cambios: {str(e)}")
            QMessageBox.critical(self, "Error", 
                              f"Error al aplicar cambios:\n{str(e)}")
    
    def _on_undo_clicked(self):
        """Deshace el último cambio."""
        if not self.structure_manager:
            return
            
        if self.structure_manager.undo():
            self.refresh_structure_view()
            self.structureChanged.emit()
        else:
            logger.info("No hay más acciones para deshacer")
    
    def _on_redo_clicked(self):
        """Rehace el último cambio deshecho."""
        if not self.structure_manager:
            return
            
        if self.structure_manager.redo():
            self.refresh_structure_view()
            self.structureChanged.emit()
        else:
            logger.info("No hay más acciones para rehacer")