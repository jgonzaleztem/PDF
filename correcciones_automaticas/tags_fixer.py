#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Corrección automática de etiquetas según PDF/UA.
Reasigna etiquetas incorrectas o faltantes.
"""

from typing import Dict, List, Optional, Any, Tuple
import re
from loguru import logger

class TagsFixer:
    """
    Clase para corregir etiquetas según PDF/UA.
    Reasigna etiquetas incorrectas y añade estructura mínima.
    """
    
    def __init__(self, pdf_writer=None):
        """
        Inicializa el corrector de etiquetas.
        
        Args:
            pdf_writer: Instancia opcional de PDFWriter
        """
        self.pdf_writer = pdf_writer
        # Tipos de estructura válidos en PDF 1.7 / ISO 32000-1
        self.valid_structure_types = [
            "Document", "Part", "Art", "Sect", "Div", "BlockQuote", "Caption",
            "TOC", "TOCI", "Index", "NonStruct", "Private", "P", "H", "H1", "H2",
            "H3", "H4", "H5", "H6", "L", "LI", "Lbl", "LBody", "Table", "TR", "TH",
            "TD", "THead", "TBody", "TFoot", "Span", "Quote", "Note", "Reference",
            "BibEntry", "Code", "Link", "Annot", "Ruby", "Warichu", "RB", "RT", "RP",
            "WT", "WP", "Figure", "Formula", "Form"
        ]
        logger.info("TagsFixer inicializado")
    
    def set_pdf_writer(self, pdf_writer):
        """Establece el escritor de PDF a utilizar"""
        self.pdf_writer = pdf_writer
    
    def fix_all_tags(self, structure_tree: Dict, pdf_loader) -> bool:
        """
        Corrige todas las etiquetas en la estructura.
        
        Args:
            structure_tree: Diccionario representando la estructura lógica
            pdf_loader: Instancia de PDFLoader con el documento cargado
            
        Returns:
            bool: True si se realizaron correcciones
            
        Referencias:
            - Matterhorn: 01-005, 01-006, 09-002, 14-003
            - Tagged PDF: 4.2.1–4.2.4 (tipos y estructura), 3.2.1
        """
        try:
            if self.pdf_writer is None:
                logger.error("No hay PDFWriter configurado para aplicar correcciones")
                return False
            
            changes_made = False
            
            # Si no hay estructura, crear estructura mínima
            if not structure_tree or not structure_tree.get("children"):
                logger.info("Creando estructura mínima para el documento")
                minimal_structure_created = self._create_minimal_structure(pdf_loader)
                if minimal_structure_created:
                    changes_made = True
                return changes_made
            
            # Verificar y corregir estructura actual
            if structure_tree.get("children"):
                # Verificar estructura Document
                if not self._has_document_root(structure_tree):
                    document_fixed = self._add_document_root(structure_tree)
                    if document_fixed:
                        changes_made = True
                
                # Corregir etiquetas en el árbol
                tags_fixed = self._fix_tags_in_tree(structure_tree.get("children", []))
                if tags_fixed:
                    changes_made = True
                
                # Corregir orden de encabezados
                headings_fixed = self._fix_heading_hierarchy(structure_tree.get("children", []))
                if headings_fixed:
                    changes_made = True
                
                # Eliminar elementos vacíos
                empty_fixed = self._remove_empty_elements(structure_tree.get("children", []))
                if empty_fixed:
                    changes_made = True
            
            return changes_made
            
        except Exception as e:
            logger.exception(f"Error al corregir etiquetas: {e}")
            return False
    
    def change_tag_type(self, element_id: str, new_type: str) -> bool:
        """
        Cambia el tipo de una etiqueta.
        
        Args:
            element_id: Identificador del elemento
            new_type: Nuevo tipo de etiqueta
            
        Returns:
            bool: True si se realizó la corrección
            
        Referencias:
            - Matterhorn: 01-006, 09-003
            - Tagged PDF: 4.1.1-4.3.3 (tipos de estructura)
        """
        try:
            if self.pdf_writer is None:
                logger.error("No hay PDFWriter configurado para aplicar correcciones")
                return False
            
            if new_type not in self.valid_structure_types:
                logger.error(f"Tipo de etiqueta inválido: {new_type}")
                return False
            
            logger.info(f"Cambiando tipo de etiqueta de elemento {element_id} a {new_type}")
            
            # En implementación real, se cambiaría el tipo
            # self.pdf_writer.update_tag_attribute(element_id, "type", new_type)
            
            return True
            
        except Exception as e:
            logger.exception(f"Error al cambiar tipo de etiqueta: {e}")
            return False
    
    def add_tag(self, parent_id: str, tag_type: str, content: Optional[str] = None, attributes: Optional[Dict] = None) -> str:
        """
        Añade una nueva etiqueta.
        
        Args:
            parent_id: Identificador del elemento padre
            tag_type: Tipo de etiqueta a añadir
            content: Contenido de la etiqueta (opcional)
            attributes: Atributos adicionales (opcional)
            
        Returns:
            str: Identificador de la etiqueta añadida
            
        Referencias:
            - Matterhorn: 01-005, 01-006
            - Tagged PDF: 4.1.1-4.3.3 (tipos de estructura)
        """
        try:
            if self.pdf_writer is None:
                logger.error("No hay PDFWriter configurado para aplicar correcciones")
                return ""
            
            if tag_type not in self.valid_structure_types:
                logger.error(f"Tipo de etiqueta inválido: {tag_type}")
                return ""
            
            # Preparar información de la etiqueta
            tag_info = {
                "type": tag_type,
                "parent_id": parent_id
            }
            
            if content:
                tag_info["content"] = content
            
            if attributes:
                tag_info.update(attributes)
            
            logger.info(f"Añadiendo etiqueta {tag_type} a elemento {parent_id}")
            
            # En implementación real, se añadiría la etiqueta
            # new_id = self.pdf_writer.add_tag(tag_info)
            
            # Simulación
            new_id = f"new-{tag_type}-{parent_id}"
            
            return new_id
            
        except Exception as e:
            logger.exception(f"Error al añadir etiqueta: {e}")
            return ""
    
    def _create_minimal_structure(self, pdf_loader) -> bool:
        """
        Crea una estructura mínima para un documento sin estructura.
        
        Args:
            pdf_loader: Instancia de PDFLoader con el documento cargado
            
        Returns:
            bool: True si se creó la estructura
        """
        try:
            # Crear estructura mínima (simulado)
            logger.info("Creando estructura Document raíz")
            
            # En implementación real, se crearía la estructura
            # 1. Crear nodo Document
            # 2. Analizar contenido visual de cada página
            # 3. Crear nodos P, H1, etc. según análisis
            
            return True
            
        except Exception as e:
            logger.exception(f"Error al crear estructura mínima: {e}")
            return False
    
    def _has_document_root(self, structure_tree: Dict) -> bool:
        """
        Verifica si la estructura tiene un nodo Document raíz.
        
        Args:
            structure_tree: Diccionario representando la estructura lógica
            
        Returns:
            bool: True si tiene nodo Document
        """
        if not structure_tree.get("children"):
            return False
        
        # Verificar si el primer elemento es Document
        first_element = structure_tree["children"][0]
        return first_element.get("type") == "Document"
    
    def _add_document_root(self, structure_tree: Dict) -> bool:
        """
        Añade un nodo Document raíz si no existe.
        
        Args:
            structure_tree: Diccionario representando la estructura lógica
            
        Returns:
            bool: True si se añadió el nodo
        """
        # Simulación - en implementación real se modificaría la estructura
        logger.info("Añadiendo nodo Document raíz")
        return True
    
    def _fix_tags_in_tree(self, elements: List[Dict], parent_type: str = None, path: str = "") -> bool:
        """
        Corrige etiquetas en el árbol de forma recursiva.
        
        Args:
            elements: Lista de elementos de estructura
            parent_type: Tipo del elemento padre
            path: Ruta de anidamiento actual
            
        Returns:
            bool: True si se realizaron correcciones
        """
        changes_made = False
        
        for i, element in enumerate(elements):
            element_type = element.get("type", "unknown")
            element_id = element.get("id", f"unknown-{i}")
            current_path = f"{path}/{i}:{element_type}"
            
            # Verificar tipo de etiqueta
            if element_type not in self.valid_structure_types:
                # Tipo inválido, determinar tipo apropiado
                appropriate_type = self._determine_appropriate_type(element, parent_type)
                
                if appropriate_type:
                    self.change_tag_type(element_id, appropriate_type)
                    element_type = appropriate_type
                    changes_made = True
            
            # Verificar anidamiento semántico incorrecto
            if not self._is_valid_parent_child(parent_type, element_type):
                # Anidamiento inválido, corregir
                fixed = self._fix_invalid_nesting(element, parent_type, current_path)
                if fixed:
                    changes_made = True
                    # Continuar con siguiente elemento, este ya se corrigió
                    continue
            
            # Verificar y corregir hijos recursivamente
            if element.get("children"):
                child_fixed = self._fix_tags_in_tree(element["children"], element_type, current_path)
                if child_fixed:
                    changes_made = True
        
        return changes_made
    
    def _fix_heading_hierarchy(self, elements: List[Dict], current_level: int = 0, path: str = "") -> bool:
        """
        Corrige jerarquía de encabezados.
        
        Args:
            elements: Lista de elementos de estructura
            current_level: Nivel actual de encabezado
            path: Ruta de anidamiento actual
            
        Returns:
            bool: True si se realizaron correcciones
            
        Referencias:
            - Matterhorn: 14-003
            - Tagged PDF: 4.2.2 (H1-H6)
        """
        changes_made = False
        headings = []
        
        # Recoger encabezados
        for i, element in enumerate(elements):
            element_type = element.get("type", "")
            current_path = f"{path}/{i}:{element_type}"
            
            if element_type.startswith("H") and len(element_type) == 2 and element_type[1].isdigit():
                level = int(element_type[1])
                headings.append({
                    "index": i,
                    "id": element.get("id", f"unknown-{i}"),
                    "level": level,
                    "path": current_path
                })
            
            # Procesar hijos recursivamente
            if element.get("children"):
                child_fixed = self._fix_heading_hierarchy(element["children"], current_level, current_path)
                if child_fixed:
                    changes_made = True
        
        # Verificar y corregir secuencia de encabezados
        for i, heading in enumerate(headings):
            if i == 0 and heading["level"] > 1:
                # Primer encabezado con nivel > 1, cambiar a H1
                logger.info(f"Cambiando encabezado de H{heading['level']} a H1 en {heading['path']}")
                self.change_tag_type(heading["id"], "H1")
                heading["level"] = 1
                changes_made = True
            
            if i > 0:
                prev_level = headings[i-1]["level"]
                curr_level = heading["level"]
                
                if curr_level > prev_level + 1:
                    # Nivel saltado, corregir
                    new_level = prev_level + 1
                    logger.info(f"Cambiando encabezado de H{curr_level} a H{new_level} en {heading['path']}")
                    self.change_tag_type(heading["id"], f"H{new_level}")
                    heading["level"] = new_level
                    changes_made = True
        
        return changes_made
    
    def _remove_empty_elements(self, elements: List[Dict], path: str = "") -> bool:
        """
        Elimina elementos Div y Span vacíos.
        
        Args:
            elements: Lista de elementos de estructura
            path: Ruta de anidamiento actual
            
        Returns:
            bool: True si se realizaron correcciones
        """
        changes_made = False
        elements_to_remove = []
        
        for i, element in enumerate(elements):
            element_type = element.get("type", "")
            element_id = element.get("id", f"unknown-{i}")
            current_path = f"{path}/{i}:{element_type}"
            
            # Verificar si es Div o Span vacío
            if element_type in ["Div", "Span"] and not element.get("content") and not element.get("children"):
                # Sin contenido ni hijos, marcar para eliminar
                elements_to_remove.append((i, element_id))
                logger.info(f"Marcando elemento vacío {element_type} para eliminar en {current_path}")
            
            # Procesar hijos recursivamente
            if element.get("children"):
                child_fixed = self._remove_empty_elements(element["children"], current_path)
                if child_fixed:
                    changes_made = True
        
        # Eliminar elementos marcados (en orden inverso para mantener índices válidos)
        for i, element_id in reversed(elements_to_remove):
            # En implementación real, se eliminaría el elemento
            logger.info(f"Eliminando elemento vacío {element_id}")
            changes_made = True
        
        return changes_made
    
    def _determine_appropriate_type(self, element: Dict, parent_type: str) -> str:
        """
        Determina el tipo apropiado para un elemento.
        
        Args:
            element: Información del elemento
            parent_type: Tipo del elemento padre
            
        Returns:
            str: Tipo apropiado
        """
        content = element.get("content", "")
        
        # Heurística para determinar tipo
        if not content and not element.get("children"):
            return "Div"  # Elemento vacío, Div por defecto
        
        # Por el contenido
        if self._looks_like_heading(content):
            # Determinar nivel de encabezado
            level = self._determine_heading_level(content, element)
            return f"H{level}"
        elif self._looks_like_list(content):
            return "L"
        elif element.get("type") == "image" or "image" in element:
            return "Figure"
        else:
            return "P"  # Párrafo por defecto
    
    def _looks_like_heading(self, content: str) -> bool:
        """
        Determina si un texto parece un encabezado.
        
        Args:
            content: Texto del elemento
            
        Returns:
            bool: True si parece un encabezado
        """
        # Simplificado para esta implementación
        # En implementación real, se analizaría el estilo, tamaño, etc.
        if not content:
            return False
        
        # Heurística simple: texto corto, sin punto final
        return len(content) < 100 and not content.endswith(".")
    
    def _determine_heading_level(self, content: str, element: Dict) -> int:
        """
        Determina el nivel apropiado para un encabezado.
        
        Args:
            content: Texto del encabezado
            element: Información del elemento
            
        Returns:
            int: Nivel de encabezado (1-6)
        """
        # Simplificado para esta implementación
        # En implementación real, se analizaría el estilo, tamaño, etc.
        font_size = element.get("font_size", 0)
        
        if font_size > 18:
            return 1
        elif font_size > 16:
            return 2
        elif font_size > 14:
            return 3
        elif font_size > 12:
            return 4
        else:
            return 5
    
    def _looks_like_list(self, content: str) -> bool:
        """
        Determina si un texto parece un ítem de lista.
        
        Args:
            content: Texto del elemento
            
        Returns:
            bool: True si parece un ítem de lista
        """
        if not content:
            return False
        
        # Patrones comunes de ítems de lista
        patterns = [
            r'^\s*[\•\-\*\+\◦\▪\■\○\□\➢\➤\➥\➨]\s+',  # Bullets
            r'^\s*\d+[\.\)\]]\s+',  # Números: 1. 1) 1]
            r'^\s*[IVXLCDMivxlcdm]+[\.\)\]]\s+',  # Romanos: I. I) I]
            r'^\s*[A-Za-z][\.\)\]]\s+'  # Letras: A. A) A]
        ]
        
        for pattern in patterns:
            if re.match(pattern, content):
                return True
        
        return False
    
    def _is_valid_parent_child(self, parent_type: str, child_type: str) -> bool:
        """
        Verifica si la relación padre-hijo es semánticamente válida.
        
        Args:
            parent_type: Tipo del elemento padre
            child_type: Tipo del elemento hijo
            
        Returns:
            bool: True si la relación es válida
        """
        # Si no hay padre, cualquier elemento es válido en la raíz
        if not parent_type:
            return True
        
        # Definir relaciones inválidas
        invalid_relations = {
            "H1": ["Table", "L", "H1", "H2", "H3", "H4", "H5", "H6"],
            "H2": ["Table", "L", "H1", "H2", "H3", "H4", "H5", "H6"],
            "H3": ["Table", "L", "H1", "H2", "H3", "H4", "H5", "H6"],
            "H4": ["Table", "L", "H1", "H2", "H3", "H4", "H5", "H6"],
            "H5": ["Table", "L", "H1", "H2", "H3", "H4", "H5", "H6"],
            "H6": ["Table", "L", "H1", "H2", "H3", "H4", "H5", "H6"],
            "P": ["Table", "L", "H1", "H2", "H3", "H4", "H5", "H6", "TR", "TD", "TH"],
            "L": ["P", "Table", "H1", "H2", "H3", "H4", "H5", "H6", "TR", "TD", "TH"],
            "LI": ["P", "H1", "H2", "H3", "H4", "H5", "H6", "Table", "TR", "TD", "TH"],
            "Table": ["P", "L", "H1", "H2", "H3", "H4", "H5", "H6"],
            "TR": ["P", "L", "H1", "H2", "H3", "H4", "H5", "H6", "Table", "TR"],
            "TH": ["P", "L", "H1", "H2", "H3", "H4", "H5", "H6", "Table", "TR", "TD", "TH"],
            "TD": ["P", "L", "H1", "H2", "H3", "H4", "H5", "H6", "Table", "TR", "TD", "TH"]
        }
        
        # Definir relaciones válidas específicas
        valid_relations = {
            "L": ["LI"],
            "LI": ["Lbl", "LBody"],
            "Table": ["TR", "THead", "TBody", "TFoot", "Caption"],
            "TR": ["TD", "TH"],
            "THead": ["TR"],
            "TBody": ["TR"],
            "TFoot": ["TR"]
        }
        
        # Si hay una relación específica definida, verificarla
        if parent_type in valid_relations:
            return child_type in valid_relations[parent_type]
        
        # Si hay una relación inválida definida, verificarla
        if parent_type in invalid_relations:
            return child_type not in invalid_relations[parent_type]
        
        # Por defecto, permitir la relación
        return True
    
    def _fix_invalid_nesting(self, element: Dict, parent_type: str, path: str) -> bool:
        """
        Corrige anidamiento inválido.
        
        Args:
            element: Información del elemento
            parent_type: Tipo del elemento padre
            path: Ruta de anidamiento actual
            
        Returns:
            bool: True si se realizó la corrección
        """
        element_type = element.get("type", "unknown")
        element_id = element.get("id", "unknown")
        
        # Simulación - en implementación real se corregiría la estructura
        logger.info(f"Corrigiendo anidamiento inválido: {element_type} dentro de {parent_type} en {path}")
        
        # Posibles estrategias:
        # 1. Insertar elemento intermedio (P dentro de LI)
        # 2. Cambiar tipo del elemento hijo (H1 a P)
        # 3. Mover el elemento fuera del padre actual
        
        return True