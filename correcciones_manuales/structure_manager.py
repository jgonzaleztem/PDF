# pdfua_editor/correcciones_manuales/structure_manager.py

from loguru import logger
from pikepdf import Pdf, Name, Dictionary, Array, String

class StructureManager:
    """Gestiona la estructura lógica del documento PDF."""
    
    def __init__(self):
        self.pdf_loader = None
        self.structure_tree = None
        self.modified = False
        self.changes_history = []
        self.current_history_pos = -1
        
    def set_pdf_loader(self, pdf_loader):
        """Establece el cargador de PDF."""
        self.pdf_loader = pdf_loader
        self.structure_tree = pdf_loader.structure_tree
        self.modified = False
        self.changes_history = []
        self.current_history_pos = -1
        
    def get_structure_tree(self):
        """Devuelve la estructura jerárquica del documento."""
        return self.structure_tree
        
    def get_element_node_type(self, element):
        """Obtiene el tipo de un elemento de estructura."""
        if isinstance(element, dict) and "type" in element:
            return element["type"]
        return None
        
    def get_element_text(self, element):
        """Obtiene el texto asociado a un elemento."""
        if isinstance(element, dict) and "text" in element:
            return element["text"]
        return ""
    
    def get_element_attribute(self, element, attribute):
        """Obtiene un atributo específico de un elemento."""
        if not isinstance(element, dict) or "element" not in element:
            return None
            
        pikepdf_element = element["element"]
        attr_name = Name(f"/{attribute}")
        
        if attr_name in pikepdf_element:
            value = pikepdf_element[attr_name]
            if isinstance(value, String):
                return str(value)
            elif isinstance(value, Name):
                return str(value)[1:]  # Quitar el "/" inicial
            return value
        
        return None
    
    def validate_node_type_change(self, element_id, new_type):
        """Valida si un cambio de tipo de nodo es válido según la estructura PDF/UA."""
        element = self.get_node(element_id)
        if not element:
            return {"valid": False, "reason": "Elemento no encontrado"}
            
        current_type = self.get_element_node_type(element)
        parent = self.get_parent_node(element_id)
        parent_type = self.get_element_node_type(parent) if parent else None
        
        # Validaciones específicas de PDF/UA
        # P no puede ser hijo directo de P
        if new_type == "P" and parent_type == "P":
            return {"valid": False, "reason": "Un párrafo no puede ser hijo directo de otro párrafo"}
            
        # Elementos bloque no pueden ser hijos de elementos inline
        if new_type in ["H1", "H2", "H3", "H4", "H5", "H6", "P", "L", "Table", "Figure"] and parent_type in ["Span", "Quote", "Link"]:
            return {"valid": False, "reason": f"Un elemento bloque no puede ser hijo de {parent_type}"}
            
        # TH/TD solo pueden ser hijos de TR
        if new_type in ["TH", "TD"] and parent_type != "TR":
            return {"valid": False, "reason": f"Una celda solo puede ser hija de una fila (TR)"}
            
        # TR solo puede ser hijo de Table, THead, TBody o TFoot
        if new_type == "TR" and parent_type not in ["Table", "THead", "TBody", "TFoot"]:
            return {"valid": False, "reason": f"Una fila solo puede ser hija de una tabla o sección de tabla"}
            
        # LI solo puede ser hijo de L
        if new_type == "LI" and parent_type != "L":
            return {"valid": False, "reason": f"Un ítem de lista solo puede ser hijo de una lista (L)"}
            
        return {"valid": True}
    
    def update_node_type(self, element_id, new_type):
        """Actualiza el tipo de un nodo de estructura."""
        element = self.get_node(element_id)
        if not element or "element" not in element:
            return False
            
        pikepdf_element = element["element"]
        old_type = str(pikepdf_element.get(Name.S, ""))[1:]
        
        # Registrar para deshacer
        self._record_change("update_type", element_id, {"old_type": old_type, "new_type": new_type})
        
        # Actualizar tipo en el objeto pikepdf
        pikepdf_element.S = Name(f"/{new_type}")
        
        # Actualizar el nodo en la estructura interna
        element["type"] = new_type
        
        self.modified = True
        return True
    
    def update_node_attribute(self, element_id, attr_name, attr_value):
        """Actualiza un atributo de un nodo de estructura."""
        element = self.get_node(element_id)
        if not element or "element" not in element:
            return False
            
        pikepdf_element = element["element"]
        attr_key = Name(f"/{attr_name}")
        
        # Guardar valor anterior para deshacer
        old_value = pikepdf_element.get(attr_key, None)
        self._record_change("update_attribute", element_id, {
            "attr_name": attr_name,
            "old_value": old_value,
            "new_value": attr_value
        })
        
        # Actualizar o eliminar el atributo
        if attr_value is None or attr_value == "":
            if attr_key in pikepdf_element:
                del pikepdf_element[attr_key]
        else:
            # Convertir el valor según el tipo apropiado
            if attr_name in ["Alt", "ActualText", "Lang", "E"]:
                pikepdf_element[attr_key] = String(attr_value)
            elif attr_name in ["Scope", "ListNumbering"]:
                pikepdf_element[attr_key] = Name(f"/{attr_value}")
            else:
                # Para otros atributos, intentar determinar el tipo
                pikepdf_element[attr_key] = attr_value
                
        self.modified = True
        return True
    
    def update_node_content(self, element_id, content):
        """Actualiza el contenido textual de un nodo."""
        element = self.get_node(element_id)
        if not element or "element" not in element:
            return False
            
        pikepdf_element = element["element"]
        
        # Guardar contenido anterior para deshacer
        old_content = ""
        if Name.K in pikepdf_element and isinstance(pikepdf_element.K, String):
            old_content = str(pikepdf_element.K)
            
        self._record_change("update_content", element_id, {
            "old_content": old_content,
            "new_content": content
        })
        
        # Actualizar contenido si es posible
        if content:
            pikepdf_element.K = String(content)
        elif Name.K in pikepdf_element and isinstance(pikepdf_element.K, String):
            del pikepdf_element.K
            
        # Actualizar también la estructura interna
        element["text"] = content
        
        self.modified = True
        return True
    
    def get_node(self, element_id):
        """Busca un nodo por su ID."""
        def find_node(node):
            if isinstance(node, dict) and "element" in node and id(node["element"]) == element_id:
                return node
                
            if isinstance(node, dict) and "children" in node:
                for child in node["children"]:
                    result = find_node(child)
                    if result:
                        return result
            
            return None
            
        return find_node(self.structure_tree)
    
    def get_parent_node(self, element_id):
        """Obtiene el nodo padre de un elemento."""
        def find_parent(node, target_id):
            if isinstance(node, dict) and "children" in node:
                for child in node["children"]:
                    if isinstance(child, dict) and "element" in child and id(child["element"]) == target_id:
                        return node
                        
                    result = find_parent(child, target_id)
                    if result:
                        return result
                        
            return None
            
        return find_parent(self.structure_tree, element_id)
    
    def _record_change(self, action, element_id, data):
        """Registra un cambio para poder deshacerlo/rehacerlo."""
        # Si hay cambios después de la posición actual, eliminarlos
        if self.current_history_pos < len(self.changes_history) - 1:
            self.changes_history = self.changes_history[:self.current_history_pos + 1]
            
        # Añadir el nuevo cambio
        self.changes_history.append({
            "action": action,
            "element_id": element_id,
            "data": data
        })
        
        self.current_history_pos = len(self.changes_history) - 1
    
    def undo(self):
        """Deshace el último cambio."""
        if self.current_history_pos < 0:
            return False  # No hay cambios para deshacer
            
        change = self.changes_history[self.current_history_pos]
        element_id = change["element_id"]
        element = self.get_node(element_id)
        
        if not element:
            self.current_history_pos -= 1
            return False  # Elemento no encontrado
            
        pikepdf_element = element["element"]
        
        # Deshacer según el tipo de acción
        if change["action"] == "update_type":
            old_type = change["data"]["old_type"]
            pikepdf_element.S = Name(f"/{old_type}")
            element["type"] = old_type
        
        elif change["action"] == "update_attribute":
            attr_name = change["data"]["attr_name"]
            old_value = change["data"]["old_value"]
            attr_key = Name(f"/{attr_name}")
            
            if old_value is None:
                if attr_key in pikepdf_element:
                    del pikepdf_element[attr_key]
            else:
                pikepdf_element[attr_key] = old_value
        
        elif change["action"] == "update_content":
            old_content = change["data"]["old_content"]
            if old_content:
                pikepdf_element.K = String(old_content)
                element["text"] = old_content
            elif Name.K in pikepdf_element and isinstance(pikepdf_element.K, String):
                del pikepdf_element.K
                element["text"] = ""
                
        self.current_history_pos -= 1
        return True
    
    def redo(self):
        """Rehace el último cambio deshecho."""
        if self.current_history_pos >= len(self.changes_history) - 1:
            return False  # No hay cambios para rehacer
            
        self.current_history_pos += 1
        change = self.changes_history[self.current_history_pos]
        element_id = change["element_id"]
        element = self.get_node(element_id)
        
        if not element:
            return False  # Elemento no encontrado
            
        pikepdf_element = element["element"]
        
        # Rehacer según el tipo de acción
        if change["action"] == "update_type":
            new_type = change["data"]["new_type"]
            pikepdf_element.S = Name(f"/{new_type}")
            element["type"] = new_type
        
        elif change["action"] == "update_attribute":
            attr_name = change["data"]["attr_name"]
            new_value = change["data"]["new_value"]
            attr_key = Name(f"/{attr_name}")
            
            if new_value is None or new_value == "":
                if attr_key in pikepdf_element:
                    del pikepdf_element[attr_key]
            else:
                if attr_name in ["Alt", "ActualText", "Lang", "E"]:
                    pikepdf_element[attr_key] = String(new_value)
                elif attr_name in ["Scope", "ListNumbering"]:
                    pikepdf_element[attr_key] = Name(f"/{new_value}")
                else:
                    pikepdf_element[attr_key] = new_value
        
        elif change["action"] == "update_content":
            new_content = change["data"]["new_content"]
            if new_content:
                pikepdf_element.K = String(new_content)
                element["text"] = new_content
            elif Name.K in pikepdf_element and isinstance(pikepdf_element.K, String):
                del pikepdf_element.K
                element["text"] = ""
                
        return True
    
    def apply_changes(self):
        """Aplica todos los cambios realizados al PDF."""
        if not self.modified or not self.pdf_loader or not self.pdf_loader.pikepdf_doc:
            return False
            
        try:
            # Guardar el documento modificado
            output_path = self.pdf_loader.file_path + ".modified.pdf"
            self.pdf_loader.pikepdf_doc.save(output_path, linearize=False)
            
            # Recargar el documento para continuar trabajando con él
            self.pdf_loader.load_document(output_path)
            
            # Reiniciar estado
            self.modified = False
            self.changes_history = []
            self.current_history_pos = -1
            
            return True
        except Exception as e:
            logger.error(f"Error applying changes: {e}")
            return False