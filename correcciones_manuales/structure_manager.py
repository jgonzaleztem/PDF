# correcciones_manuales/structure_manager.py

from typing import Dict, List, Optional, Any, Union
from loguru import logger
import copy

class StructureManager:
    """
    Controla la estructura lógica del documento en tiempo real.
    Permite modificaciones, deshacer/rehacer y aplicar cambios al PDF.
    """
    
    def __init__(self):
        self.pdf_loader = None
        self.structure_tree = None
        self.original_structure = None
        self.modified = False
        
        # Sistema de deshacer/rehacer
        self.undo_stack = []
        self.redo_stack = []
        self.max_undo_levels = 50
        
        # Mapeo de IDs para búsqueda rápida
        self.elements_by_id = {}
        
        logger.info("StructureManager inicializado")
    
    def set_pdf_loader(self, pdf_loader):
        """Establece el cargador de PDF y carga la estructura."""
        self.pdf_loader = pdf_loader
        
        if pdf_loader and pdf_loader.structure_tree:
            self.structure_tree = copy.deepcopy(pdf_loader.structure_tree)
            self.original_structure = copy.deepcopy(pdf_loader.structure_tree)
            self._build_elements_index()
            logger.info("Estructura cargada en el gestor")
        else:
            self.structure_tree = None
            self.original_structure = None
            self.elements_by_id = {}
            logger.warning("No hay estructura para cargar en el gestor")
    
    def get_structure_tree(self):
        """Obtiene la estructura actual."""
        return self.structure_tree
    
    def get_node(self, node_id):
        """Obtiene un nodo por su ID."""
        try:
            node_id_int = int(node_id) if isinstance(node_id, str) else node_id
            return self.elements_by_id.get(node_id_int)
        except (ValueError, TypeError):
            return self.elements_by_id.get(node_id)
    
    def update_node_type(self, node_id, new_type):
        """Actualiza el tipo de un nodo."""
        node = self.get_node(node_id)
        if not node:
            logger.error(f"Nodo {node_id} no encontrado")
            return False
        
        # Guardar estado para deshacer
        self._save_state("update_node_type")
        
        # Actualizar tipo
        old_type = node.get("type", "")
        node["type"] = new_type
        
        # Marcar como modificado
        self.modified = True
        
        logger.info(f"Tipo de nodo cambiado de '{old_type}' a '{new_type}'")
        return True
    
    def update_node_content(self, node_id, new_content):
        """Actualiza el contenido de texto de un nodo."""
        node = self.get_node(node_id)
        if not node:
            logger.error(f"Nodo {node_id} no encontrado")
            return False
        
        # Guardar estado para deshacer
        self._save_state("update_node_content")
        
        # Actualizar contenido
        old_content = node.get("text", "")
        node["text"] = new_content
        
        # Marcar como modificado
        self.modified = True
        
        logger.info(f"Contenido de nodo actualizado")
        return True
    
    def update_tag_attribute(self, node_id, attribute_name, attribute_value):
        """Actualiza un atributo de una etiqueta."""
        node = self.get_node(node_id)
        if not node:
            logger.error(f"Nodo {node_id} no encontrado")
            return False
        
        # Guardar estado para deshacer
        self._save_state("update_tag_attribute")
        
        # Asegurar que existe el diccionario de atributos
        if "attributes" not in node:
            node["attributes"] = {}
        
        # Actualizar atributo
        old_value = node["attributes"].get(attribute_name, "")
        
        if attribute_value is None or attribute_value == "":
            # Eliminar atributo si el valor está vacío
            if attribute_name in node["attributes"]:
                del node["attributes"][attribute_name]
        else:
            node["attributes"][attribute_name] = attribute_value
        
        # Marcar como modificado
        self.modified = True
        
        logger.info(f"Atributo '{attribute_name}' actualizado de '{old_value}' a '{attribute_value}'")
        return True
    
    def add_element(self, parent_id, element_type, position=-1):
        """Añade un nuevo elemento como hijo de otro."""
        parent_node = self.get_node(parent_id)
        if not parent_node:
            logger.error(f"Nodo padre {parent_id} no encontrado")
            return False
        
        # Guardar estado para deshacer
        self._save_state("add_element")
        
        # Crear nuevo elemento
        new_element = {
            "type": element_type,
            "text": "",
            "page": parent_node.get("page", 0),
            "children": [],
            "attributes": {},
            "element": None  # Se asignará al aplicar cambios
        }
        
        # Añadir a los hijos del padre
        if "children" not in parent_node:
            parent_node["children"] = []
        
        if position < 0 or position >= len(parent_node["children"]):
            parent_node["children"].append(new_element)
        else:
            parent_node["children"].insert(position, new_element)
        
        # Reconstruir índice
        self._build_elements_index()
        
        # Marcar como modificado
        self.modified = True
        
        logger.info(f"Elemento '{element_type}' añadido como hijo de '{parent_node.get('type', 'Unknown')}'")
        return True
    
    def delete_element(self, node_id):
        """Elimina un elemento y todos sus hijos."""
        node = self.get_node(node_id)
        if not node:
            logger.error(f"Nodo {node_id} no encontrado")
            return False
        
        # No permitir eliminar la raíz
        if node.get("type") == "StructTreeRoot":
            logger.error("No se puede eliminar la raíz del documento")
            return False
        
        # Guardar estado para deshacer
        self._save_state("delete_element")
        
        # Encontrar el padre y eliminar el nodo
        parent_found = self._find_and_remove_child(self.structure_tree, node)
        
        if parent_found:
            # Reconstruir índice
            self._build_elements_index()
            
            # Marcar como modificado
            self.modified = True
            
            logger.info(f"Elemento '{node.get('type', 'Unknown')}' eliminado")
            return True
        else:
            logger.error("No se pudo encontrar el nodo padre para eliminar")
            return False
    
    def move_element_up(self, node_id):
        """Mueve un elemento hacia arriba en la lista de hermanos."""
        return self._move_element(node_id, -1)
    
    def move_element_down(self, node_id):
        """Mueve un elemento hacia abajo en la lista de hermanos."""
        return self._move_element(node_id, 1)
    
    def _move_element(self, node_id, direction):
        """Mueve un elemento en la dirección especificada (-1 arriba, 1 abajo)."""
        node = self.get_node(node_id)
        if not node:
            logger.error(f"Nodo {node_id} no encontrado")
            return False
        
        # Encontrar el padre y la posición actual
        parent, current_index = self._find_parent_and_index(self.structure_tree, node)
        
        if not parent or "children" not in parent:
            logger.error("No se pudo encontrar el padre del nodo")
            return False
        
        children = parent["children"]
        new_index = current_index + direction
        
        # Verificar límites
        if new_index < 0 or new_index >= len(children):
            logger.info("El elemento ya está en el límite, no se puede mover más")
            return False
        
        # Guardar estado para deshacer
        self._save_state("move_element")
        
        # Intercambiar elementos
        children[current_index], children[new_index] = children[new_index], children[current_index]
        
        # Marcar como modificado
        self.modified = True
        
        direction_text = "arriba" if direction == -1 else "abajo"
        logger.info(f"Elemento movido {direction_text}")
        return True
    
    def can_undo(self):
        """Verifica si se puede deshacer."""
        return len(self.undo_stack) > 0
    
    def can_redo(self):
        """Verifica si se puede rehacer."""
        return len(self.redo_stack) > 0
    
    def undo(self):
        """Deshace la última operación."""
        if not self.can_undo():
            return False
        
        # Guardar estado actual en redo stack
        current_state = copy.deepcopy(self.structure_tree)
        self.redo_stack.append(current_state)
        
        # Restaurar estado anterior
        previous_state = self.undo_stack.pop()
        self.structure_tree = previous_state
        
        # Reconstruir índice
        self._build_elements_index()
        
        # Marcar como modificado
        self.modified = True
        
        logger.info("Operación deshecha")
        return True
    
    def redo(self):
        """Rehace la última operación deshecha."""
        if not self.can_redo():
            return False
        
        # Guardar estado actual en undo stack
        current_state = copy.deepcopy(self.structure_tree)
        self.undo_stack.append(current_state)
        
        # Restaurar estado siguiente
        next_state = self.redo_stack.pop()
        self.structure_tree = next_state
        
        # Reconstruir índice
        self._build_elements_index()
        
        # Marcar como modificado
        self.modified = True
        
        logger.info("Operación rehecha")
        return True
    
    def apply_changes(self):
        """Aplica los cambios a través del pdf_writer."""
        if not self.modified:
            logger.info("No hay cambios para aplicar")
            return True
        
        if not self.pdf_loader:
            logger.error("No hay pdf_loader disponible para aplicar cambios")
            return False
        
        try:
            # Verificar si hay pdf_writer disponible
            if hasattr(self.pdf_loader, 'pdf_writer') and self.pdf_loader.pdf_writer:
                pdf_writer = self.pdf_loader.pdf_writer
            else:
                # Importar PDFWriter si no está disponible
                from core.pdf_writer import PDFWriter
                pdf_writer = PDFWriter(self.pdf_loader)
            
            # Aplicar la estructura actualizada
            success = pdf_writer.update_structure_tree(self.structure_tree)
            
            if success:
                # Actualizar la estructura original
                self.original_structure = copy.deepcopy(self.structure_tree)
                self.modified = False
                
                # Limpiar stacks de deshacer/rehacer después de aplicar
                self.undo_stack.clear()
                self.redo_stack.clear()
                
                logger.info("Cambios aplicados correctamente")
                return True
            else:
                logger.error("Error al aplicar cambios")
                return False
                
        except Exception as e:
            logger.error(f"Error al aplicar cambios: {e}")
            return False
    
    def revert_changes(self):
        """Revierte todos los cambios a la estructura original."""
        if self.original_structure:
            self.structure_tree = copy.deepcopy(self.original_structure)
            self._build_elements_index()
            self.modified = False
            
            # Limpiar stacks
            self.undo_stack.clear()
            self.redo_stack.clear()
            
            logger.info("Cambios revertidos")
            return True
        else:
            logger.warning("No hay estructura original para revertir")
            return False
    
    def _save_state(self, operation_name):
        """Guarda el estado actual para permitir deshacer."""
        # Guardar estado actual en undo stack
        current_state = copy.deepcopy(self.structure_tree)
        self.undo_stack.append(current_state)
        
        # Limpiar redo stack cuando se hace una nueva operación
        self.redo_stack.clear()
        
        # Limitar tamaño del undo stack
        if len(self.undo_stack) > self.max_undo_levels:
            self.undo_stack.pop(0)
        
        logger.debug(f"Estado guardado para operación: {operation_name}")
    
    def _build_elements_index(self):
        """Construye un índice de elementos por ID para búsqueda rápida."""
        self.elements_by_id = {}
        
        def index_node(node):
            if isinstance(node, dict):
                # Usar ID del elemento o ID del nodo como clave
                if "element" in node and node["element"]:
                    element_id = id(node["element"])
                else:
                    element_id = id(node)
                
                self.elements_by_id[element_id] = node
                
                # Indexar hijos
                if "children" in node:
                    for child in node["children"]:
                        index_node(child)
        
        if self.structure_tree:
            index_node(self.structure_tree)
        
        logger.debug(f"Índice de elementos construido: {len(self.elements_by_id)} elementos")
    
    def _find_and_remove_child(self, parent_node, target_node):
        """Encuentra y elimina un nodo hijo recursivamente."""
        if not isinstance(parent_node, dict) or "children" not in parent_node:
            return False
        
        # Buscar en hijos directos
        children = parent_node["children"]
        for i, child in enumerate(children):
            if child is target_node:
                # Encontrado, eliminar
                children.pop(i)
                return True
        
        # Buscar recursivamente en nietos
        for child in children:
            if self._find_and_remove_child(child, target_node):
                return True
        
        return False
    
    def _find_parent_and_index(self, root_node, target_node):
        """Encuentra el padre de un nodo y su índice en la lista de hijos."""
        if not isinstance(root_node, dict) or "children" not in root_node:
            return None, -1
        
        # Buscar en hijos directos
        children = root_node["children"]
        for i, child in enumerate(children):
            if child is target_node:
                return root_node, i
        
        # Buscar recursivamente
        for child in children:
            parent, index = self._find_parent_and_index(child, target_node)
            if parent:
                return parent, index
        
        return None, -1
    
    def validate_structure(self):
        """Valida la estructura actual para detectar problemas."""
        issues = []
        
        if not self.structure_tree:
            issues.append("No hay estructura para validar")
            return issues
        
        # Validar recursivamente
        def validate_node(node, path=""):
            node_issues = []
            
            if not isinstance(node, dict):
                node_issues.append(f"Nodo inválido en {path}")
                return node_issues
            
            # Verificar campos requeridos
            if "type" not in node:
                node_issues.append(f"Nodo sin tipo en {path}")
            
            # Verificar hijos si existen
            if "children" in node:
                for i, child in enumerate(node["children"]):
                    child_path = f"{path}/child[{i}]"
                    child_issues = validate_node(child, child_path)
                    node_issues.extend(child_issues)
            
            return node_issues
        
        issues.extend(validate_node(self.structure_tree, "root"))
        
        if issues:
            logger.warning(f"Problemas de validación encontrados: {len(issues)}")
        else:
            logger.info("Estructura validada correctamente")
        
        return issues
    
    def get_statistics(self):
        """Obtiene estadísticas de la estructura actual."""
        if not self.structure_tree:
            return {}
        
        stats = {
            "total_elements": 0,
            "elements_by_type": {},
            "max_depth": 0,
            "elements_with_text": 0,
            "elements_with_attributes": 0
        }
        
        def analyze_node(node, depth=0):
            if not isinstance(node, dict):
                return
            
            stats["total_elements"] += 1
            stats["max_depth"] = max(stats["max_depth"], depth)
            
            # Contar por tipo
            node_type = node.get("type", "Unknown")
            stats["elements_by_type"][node_type] = stats["elements_by_type"].get(node_type, 0) + 1
            
            # Verificar texto
            if node.get("text", "").strip():
                stats["elements_with_text"] += 1
            
            # Verificar atributos
            if node.get("attributes"):
                stats["elements_with_attributes"] += 1
            
            # Analizar hijos
            if "children" in node:
                for child in node["children"]:
                    analyze_node(child, depth + 1)
        
        analyze_node(self.structure_tree)
        
        return stats