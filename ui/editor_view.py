# pdfua_editor/ui/editor_view.py

from PySide6.QtWidgets import (QWidget, QSplitter, QVBoxLayout, QHBoxLayout, 
                              QPushButton, QMessageBox, QApplication, QLabel)
from PySide6.QtCore import Qt, Signal, QTimer
from loguru import logger

from correcciones_manuales.structure_view import StructureView
from correcciones_manuales.tag_properties import TagPropertiesEditor

class EditorView(QWidget):
    """
    Vista combinada para edición de estructura del PDF que incluye el árbol de estructura 
    y el editor de propiedades de etiquetas.
    """
    
    structureChanged = Signal()  # Emitida cuando la estructura cambia
    nodeSelected = Signal(object)   # ID del nodo seleccionado
    
    def __init__(self, parent=None):
        super().__init__(parent)
        
        self.structure_manager = None
        self.current_node_id = None
        
        self._init_ui()
        self._connect_signals()
    
    def _init_ui(self):
        """Inicializa la interfaz de usuario."""
        main_layout = QVBoxLayout(self)
        main_layout.setContentsMargins(5, 5, 5, 5)
        
        # Título de la sección
        title_label = QLabel("Editor de Estructura")
        title_label.setStyleSheet("QLabel { font-weight: bold; font-size: 14px; margin-bottom: 5px; }")
        main_layout.addWidget(title_label)
        
        # Crear un splitter horizontal para dividir la vista
        self.splitter = QSplitter(Qt.Horizontal)
        
        # Panel izquierdo - Vista del árbol de estructura
        self.structure_view = StructureView()
        self.splitter.addWidget(self.structure_view)
        
        # Panel derecho - Editor de propiedades de etiquetas
        self.tag_properties = TagPropertiesEditor()
        self.splitter.addWidget(self.tag_properties)
        
        # Establecer tamaños iniciales (60% árbol, 40% propiedades)
        self.splitter.setSizes([350, 250])
        
        # Añadir splitter al layout principal
        main_layout.addWidget(self.splitter)
        
        # Barra de botones para acciones globales
        buttons_layout = QHBoxLayout()
        
        self.refresh_btn = QPushButton("Actualizar")
        self.refresh_btn.setToolTip("Actualizar vista de estructura")
        self.refresh_btn.clicked.connect(self.refresh_structure_view)
        buttons_layout.addWidget(self.refresh_btn)
        
        self.apply_btn = QPushButton("Aplicar Cambios")
        self.apply_btn.setToolTip("Aplicar cambios realizados a la estructura")
        self.apply_btn.clicked.connect(self._on_apply_clicked)
        self.apply_btn.setEnabled(False)
        buttons_layout.addWidget(self.apply_btn)
        
        self.undo_btn = QPushButton("Deshacer")
        self.undo_btn.setToolTip("Deshacer último cambio")
        self.undo_btn.clicked.connect(self._on_undo_clicked)
        self.undo_btn.setEnabled(False)
        buttons_layout.addWidget(self.undo_btn)
        
        self.redo_btn = QPushButton("Rehacer")
        self.redo_btn.setToolTip("Rehacer último cambio deshecho")
        self.redo_btn.clicked.connect(self._on_redo_clicked)
        self.redo_btn.setEnabled(False)
        buttons_layout.addWidget(self.redo_btn)
        
        buttons_layout.addStretch()
        
        # Etiqueta de estado
        self.status_label = QLabel("Listo")
        self.status_label.setStyleSheet("QLabel { color: #666; font-size: 10px; }")
        buttons_layout.addWidget(self.status_label)
        
        main_layout.addLayout(buttons_layout)
        
        # Timer para actualizar estado de botones
        self.update_timer = QTimer()
        self.update_timer.timeout.connect(self._update_buttons_state)
        self.update_timer.start(1000)  # Actualizar cada segundo
    
    def _connect_signals(self):
        """Conecta las señales entre los componentes."""
        # Conexiones del árbol de estructura
        self.structure_view.nodeSelected.connect(self._on_node_selected)
        
        # Conexiones del editor de propiedades
        self.tag_properties.propertiesChanged.connect(self._on_properties_changed)
        self.tag_properties.nodeTypeChanged.connect(self._on_node_type_changed)
        self.tag_properties.contentChanged.connect(self._on_content_changed)
    
    def set_structure_manager(self, structure_manager):
        """Establece el gestor de estructura."""
        self.structure_manager = structure_manager
        
        # Pasar referencia a los componentes
        self.structure_view.set_structure_manager(structure_manager)
        self.tag_properties.set_structure_manager(structure_manager)
        
        # Actualizar vista inicial
        self.refresh_structure_view()
        
        # Habilitar/deshabilitar botones según el estado
        self._update_buttons_state()
        
        logger.info("Structure manager establecido en EditorView")
    
    def refresh_structure_view(self):
        """Actualiza la vista del árbol de estructura."""
        if not self.structure_manager:
            logger.warning("No hay structure manager para actualizar vista")
            return
        
        try:
            # Actualizar vista del árbol
            self.structure_view.refresh_view()
            
            # Mantener la selección actual si existe y es válida
            if self.current_node_id:
                node = self.structure_manager.get_node(self.current_node_id)
                if node:
                    self.structure_view.select_node(self.current_node_id)
                    self.tag_properties.set_node(self.current_node_id)
                else:
                    # El nodo ya no existe, limpiar selección
                    self.current_node_id = None
                    self.tag_properties.set_node(None)
            
            # Actualizar estado de los botones
            self._update_buttons_state()
            
            self.status_label.setText("Estructura actualizada")
            
            logger.debug("Vista de estructura actualizada")
            
        except Exception as e:
            logger.error(f"Error al actualizar vista de estructura: {e}")
            self.status_label.setText("Error al actualizar")
    
    def select_node(self, node_id):
        """Selecciona un nodo en la vista de estructura."""
        if not node_id or not self.structure_manager:
            return
            
        try:
            # Verificar que el nodo existe
            node = self.structure_manager.get_node(node_id)
            if node:
                self.structure_view.select_node(node_id)
                self.tag_properties.set_node(node_id)
                self.current_node_id = node_id
                
                # Emitir señal de selección
                self.nodeSelected.emit(node_id)
                
                logger.debug(f"Nodo seleccionado: {node_id}")
            else:
                logger.warning(f"Intento de seleccionar nodo inexistente: {node_id}")
                
        except Exception as e:
            logger.error(f"Error al seleccionar nodo {node_id}: {e}")
    
    def _on_node_selected(self, node_id):
        """Maneja la selección de un nodo en la vista de estructura."""
        try:
            # Actualizar editor de propiedades
            self.tag_properties.set_node(node_id)
            self.current_node_id = node_id
            
            # Emitir señal para otros componentes (como el visor PDF)
            self.nodeSelected.emit(node_id)
            
            # Actualizar etiqueta de estado
            if node_id and self.structure_manager:
                node = self.structure_manager.get_node(node_id)
                if node:
                    node_type = node.get("type", "Unknown")
                    self.status_label.setText(f"Seleccionado: {node_type}")
                else:
                    self.status_label.setText("Nodo no encontrado")
            else:
                self.status_label.setText("Ningún nodo seleccionado")
                
        except Exception as e:
            logger.error(f"Error al manejar selección de nodo: {e}")
            self.status_label.setText("Error en selección")
    
    def _on_properties_changed(self, node_id, properties):
        """Maneja cambios en las propiedades del nodo."""
        if not self.structure_manager or not node_id:
            return
        
        try:
            # Aplicar cada atributo
            for attr_name, attr_value in properties.items():
                success = self.structure_manager.update_tag_attribute(node_id, attr_name, attr_value)
                if not success:
                    logger.error(f"Error al actualizar atributo {attr_name}")
                    return
            
            # Emitir señal de cambio en estructura
            self.structureChanged.emit()
            
            # Actualizar estado
            self._update_buttons_state()
            self.status_label.setText("Propiedades actualizadas")
            
            logger.debug(f"Propiedades actualizadas para nodo {node_id}")
            
        except Exception as e:
            logger.error(f"Error al actualizar propiedades: {e}")
            self.status_label.setText("Error al actualizar propiedades")
    
    def _on_node_type_changed(self, node_id, new_type):
        """Maneja el cambio de tipo de nodo."""
        if not self.structure_manager or not node_id:
            return
        
        try:
            # Validar el nuevo tipo
            if not new_type or not new_type.strip():
                logger.warning("Tipo de nodo vacío, ignorando cambio")
                return
            
            # Aplicar cambio de tipo
            success = self.structure_manager.update_node_type(node_id, new_type)
            
            if success:
                # Emitir señal de cambio en estructura
                self.structureChanged.emit()
                
                # Actualizar vista para reflejar el cambio
                self.refresh_structure_view()
                
                # Reseleccionar el nodo para mantener la selección
                self.select_node(node_id)
                
                self.status_label.setText(f"Tipo cambiado a {new_type}")
                logger.info(f"Tipo de nodo {node_id} cambiado a {new_type}")
            else:
                logger.error(f"Error al cambiar tipo de nodo a {new_type}")
                self.status_label.setText("Error al cambiar tipo")
            
            # Actualizar estado de botones
            self._update_buttons_state()
            
        except Exception as e:
            logger.error(f"Error al cambiar tipo de nodo: {e}")
            self.status_label.setText("Error al cambiar tipo")
    
    def _on_content_changed(self, node_id, new_content):
        """Maneja cambios en el contenido del nodo."""
        if not self.structure_manager or not node_id:
            return
        
        try:
            # Aplicar cambio de contenido
            success = self.structure_manager.update_node_content(node_id, new_content)
            
            if success:
                # Emitir señal de cambio en estructura
                self.structureChanged.emit()
                
                # Actualizar vista para reflejar el cambio
                self.refresh_structure_view()
                
                # Reseleccionar el nodo para mantener la selección
                self.select_node(node_id)
                
                self.status_label.setText("Contenido actualizado")
                logger.debug(f"Contenido de nodo {node_id} actualizado")
            else:
                logger.error("Error al actualizar contenido de nodo")
                self.status_label.setText("Error al actualizar contenido")
            
            # Actualizar estado de botones
            self._update_buttons_state()
            
        except Exception as e:
            logger.error(f"Error al actualizar contenido: {e}")
            self.status_label.setText("Error al actualizar contenido")
    
    def _on_apply_clicked(self):
        """Aplica los cambios al PDF."""
        if not self.structure_manager:
            QMessageBox.warning(self, "Advertencia", 
                            "No hay gestor de estructura disponible.")
            return
        
        try:
            # Verificar si hay cambios pendientes
            if not self.structure_manager.modified:
                QMessageBox.information(self, "Información", 
                                    "No hay cambios pendientes para aplicar.")
                return
            
            # Mostrar diálogo de confirmación
            response = QMessageBox.question(
                self, "Aplicar cambios", 
                "¿Está seguro de que desea aplicar los cambios a la estructura del PDF?",
                QMessageBox.Yes | QMessageBox.No,
                QMessageBox.Yes
            )
            
            if response != QMessageBox.Yes:
                return
            
            logger.info("Iniciando proceso de aplicación de cambios...")
            QApplication.setOverrideCursor(Qt.WaitCursor)
            
            # Aplicar cambios
            success = self.structure_manager.apply_changes()
            
            QApplication.restoreOverrideCursor()
            
            if success:
                logger.info("Cambios aplicados correctamente")
                QMessageBox.information(self, "Cambios Aplicados", 
                                    "Los cambios han sido aplicados correctamente.")
                
                # Actualizar la vista después de aplicar cambios
                self.refresh_structure_view()
                self.status_label.setText("Cambios aplicados")
            else:
                logger.warning("No se pudieron aplicar los cambios")
                QMessageBox.warning(self, "Advertencia", 
                                "No se pudieron aplicar los cambios.")
                self.status_label.setText("Error al aplicar cambios")
                
        except Exception as e:
            QApplication.restoreOverrideCursor()
            logger.error(f"Error al aplicar cambios: {str(e)}", exc_info=True)
            QMessageBox.critical(self, "Error", f"Error al aplicar cambios:\n{str(e)}")
            self.status_label.setText("Error al aplicar cambios")
    
    def _on_undo_clicked(self):
        """Deshace el último cambio."""
        if not self.structure_manager:
            return
        
        try:
            if self.structure_manager.undo():
                # Actualizar vista
                self.refresh_structure_view()
                
                # Emitir señal de cambio
                self.structureChanged.emit()
                
                # Limpiar selección actual ya que puede haber cambiado
                self.current_node_id = None
                self.tag_properties.set_node(None)
                
                # Actualizar estado de los botones
                self._update_buttons_state()
                
                self.status_label.setText("Acción deshecha")
                logger.info("Operación deshecha correctamente")
            else:
                logger.info("No hay más acciones para deshacer")
                self.status_label.setText("No hay más acciones para deshacer")
                
        except Exception as e:
            logger.error(f"Error al deshacer: {e}")
            self.status_label.setText("Error al deshacer")
    
    def _on_redo_clicked(self):
        """Rehace el último cambio deshecho."""
        if not self.structure_manager:
            return
        
        try:
            if self.structure_manager.redo():
                # Actualizar vista
                self.refresh_structure_view()
                
                # Emitir señal de cambio
                self.structureChanged.emit()
                
                # Limpiar selección actual ya que puede haber cambiado
                self.current_node_id = None
                self.tag_properties.set_node(None)
                
                # Actualizar estado de los botones
                self._update_buttons_state()
                
                self.status_label.setText("Acción rehecha")
                logger.info("Operación rehecha correctamente")
            else:
                logger.info("No hay más acciones para rehacer")
                self.status_label.setText("No hay más acciones para rehacer")
                
        except Exception as e:
            logger.error(f"Error al rehacer: {e}")
            self.status_label.setText("Error al rehacer")
    
    def _update_buttons_state(self):
        """Actualiza el estado de los botones según el estado del gestor."""
        if not self.structure_manager:
            self.apply_btn.setEnabled(False)
            self.undo_btn.setEnabled(False)
            self.redo_btn.setEnabled(False)
            return
        
        try:
            # Botón de aplicar - habilitado si hay cambios
            self.apply_btn.setEnabled(getattr(self.structure_manager, 'modified', False))
            
            # Botones de deshacer/rehacer
            self.undo_btn.setEnabled(self.structure_manager.can_undo())
            self.redo_btn.setEnabled(self.structure_manager.can_redo())
            
        except Exception as e:
            logger.error(f"Error al actualizar estado de botones: {e}")
    
    def get_selected_node_id(self):
        """Obtiene el ID del nodo actualmente seleccionado."""
        return self.current_node_id
    
    def has_unsaved_changes(self):
        """Verifica si hay cambios sin guardar."""
        if not self.structure_manager:
            return False
        
        return getattr(self.structure_manager, 'modified', False)
    
    def get_structure_statistics(self):
        """Obtiene estadísticas de la estructura actual."""
        if not self.structure_manager:
            return {}
        
        try:
            return self.structure_manager.get_statistics()
        except Exception as e:
            logger.error(f"Error al obtener estadísticas: {e}")
            return {}
    
    def validate_current_structure(self):
        """Valida la estructura actual y retorna problemas encontrados."""
        if not self.structure_manager:
            return ["No hay gestor de estructura disponible"]
        
        try:
            return self.structure_manager.validate_structure()
        except Exception as e:
            logger.error(f"Error al validar estructura: {e}")
            return [f"Error en validación: {str(e)}"]
    
    def export_structure_info(self):
        """Exporta información de la estructura para depuración."""
        if not self.structure_manager:
            return None
        
        try:
            info = {
                "statistics": self.get_structure_statistics(),
                "validation_issues": self.validate_current_structure(),
                "has_changes": self.has_unsaved_changes(),
                "selected_node": self.current_node_id,
                "can_undo": self.structure_manager.can_undo(),
                "can_redo": self.structure_manager.can_redo()
            }
            
            return info
            
        except Exception as e:
            logger.error(f"Error al exportar información de estructura: {e}")
            return None