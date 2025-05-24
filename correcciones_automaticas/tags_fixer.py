#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Módulo para corregir etiquetas incorrectas o faltantes en documentos PDF.
Implementa correcciones automáticas según el Matterhorn Protocol y PDF/UA.

Este módulo aborda los siguientes checkpoints Matterhorn:
- 01-001 a 01-007: Etiquetado de contenido real
- 02-001 a 02-004: Mapeo de roles
- 09-001 a 09-008: Etiquetas apropiadas
- 13-001 a 13-010: Gráficos
- 14-001 a 14-007: Encabezados
"""

from typing import Dict, List, Set, Tuple, Optional, Any, Union
import re
from loguru import logger
import pikepdf
from collections import defaultdict

class TagsFixer:
    """
    Clase para corregir etiquetas incorrectas o faltantes en documentos PDF.
    Implementa correcciones automáticas según el Matterhorn Protocol y PDF/UA.
    """
    
    def __init__(self, pdf_writer):
        """
        Inicializa el corrector de etiquetas.
        
        Args:
            pdf_writer: Instancia del escritor de PDF para aplicar cambios
        """
        self.pdf_writer = pdf_writer
        
        # Tipos de estructura válidos en PDF 1.7 / ISO 32000-1
        self.valid_structure_types = [
            "Document", "Part", "Art", "Sect", "Div", "BlockQuote", "Caption",
            "TOC", "TOCI", "Index", "NonStruct", "Private", "P", "H", "H1", "H2",
            "H3", "H4", "H5", "H6", "L", "LI", "Lbl", "LBody", "Table", "TR", "TH",
            "TD", "THead", "TBody", "TFoot", "Span", "Quote", "Note", "Reference",
            "BibEntry", "Code", "Link", "Annot", "Ruby", "Warichu", "RB", "RT", "RP",
            "WT", "WP", "Figure", "Formula", "Form", "TextNode"
        ]
        
        # Mapeo de etiquetas comúnmente mal utilizadas a sus versiones correctas
        self.common_tag_corrections = {
            "Title": "H1",        # Títulos de documento a menudo marcados incorrectamente
            "Heading": "H1",      # Etiqueta genérica de título
            "Header": "H1",       # A menudo confundida con encabezados
            "Text": "P",          # Etiqueta genérica de texto
            "Paragraph": "P",     # Versión completa
            "Image": "Figure",    # Nombre común para imágenes
            "Picture": "Figure",  # Otro nombre común para imágenes
            "Row": "TR",          # Filas de tabla
            "Cell": "TD",         # Celdas de tabla
            "HeaderCell": "TH",   # Celdas de encabezado
            "ListItem": "LI",     # Elemento de lista
            "List": "L",          # Lista
            "Page": "P",          # A veces usado por error
        }
        
        # Etiquetas que requieren atributos específicos
        self.required_attributes = {
            "Figure": ["alt"],
            "Formula": ["alt"],
            "TH": ["scope"],
            "Link": [],  # No necesita alt en PDF/UA-1, pero es recomendado
            "Lbl": [],
            "Note": ["id"],
        }
        
        # Mapeo de relaciones padre-hijo válidas según ISO 32000
        self.valid_parent_child = {
            # Elementos de agrupación
            "Document": ["Part", "Art", "Sect", "Div", "P", "H1", "L", "Table", "Figure", "Formula", "Form", "TOC", "Index"],
            "Part": ["Part", "Art", "Sect", "Div", "P", "H1", "L", "Table", "Figure", "Formula", "Form"],
            "Art": ["Part", "Sect", "Div", "P", "H1", "L", "Table", "Figure", "Formula", "Form"],
            "Sect": ["Part", "Sect", "Div", "P", "H1", "H2", "H3", "H4", "H5", "H6", "L", "Table", "Figure", "Formula", "Form"],
            "Div": ["P", "H1", "H2", "H3", "H4", "H5", "H6", "L", "Table", "Figure", "Formula", "Form", "Div"],
            
            # Elementos especializados
            "BlockQuote": ["P", "H1", "H2", "H3", "H4", "H5", "H6", "L", "Table", "Figure", "Formula", "Form", "Div"],
            "Caption": ["P", "Span", "Quote", "Code"],
            "TOC": ["Caption", "TOCI"],
            "TOCI": ["P", "Reference", "Link", "Lbl", "Span"],
            "Index": ["P", "Reference", "Link", "Lbl", "Span", "L"],
            
            # Listas
            "L": ["Caption", "LI"],
            "LI": ["Lbl", "LBody"],
            "LBody": ["P", "Span", "L", "Table", "Figure", "Formula", "Form", "Div"],
            
            # Tablas
            "Table": ["Caption", "TR", "THead", "TBody", "TFoot"],
            "THead": ["TR"],
            "TBody": ["TR"],
            "TFoot": ["TR"],
            "TR": ["TH", "TD"],
            "TH": ["P", "Span", "L", "Figure", "Formula", "Form", "Div"],
            "TD": ["P", "Span", "L", "Table", "Figure", "Formula", "Form", "Div"],
            
            # Enlaces y anotaciones
            "Link": ["Link-OBJR", "Span"],
            "Reference": ["Lbl", "Span", "Link"],
            "Note": ["Lbl", "P", "Span", "L", "Table", "Figure", "Formula", "Form", "Div"],

            # Contenedores genéricos que pueden contener casi cualquier cosa
            "NonStruct": self.valid_structure_types,
            "Private": self.valid_structure_types
        }
        
        # Inicializar estadísticas de corrección
        self.stats = {
            "role_map_fixes": 0,
            "tag_fixes": 0,
            "parent_child_fixes": 0,
            "heading_sequence_fixes": 0,
            "attribute_fixes": 0
        }
        
        logger.info("TagsFixer inicializado")
    
    def fix_all_tags(self, structure_tree: Dict, pdf_loader) -> bool:
        """
        Corrige todas las etiquetas incorrectas o faltantes en el documento.
        
        Args:
            structure_tree: Árbol de estructura del documento
            pdf_loader: Instancia del cargador de PDF
            
        Returns:
            bool: True si se realizaron correcciones, False en caso contrario
            
        Referencias:
            - Matterhorn: 01-001 a 01-007, 09-001 a 09-008
            - Tagged PDF: 3.2 (Fundamentals), 4.1 y 4.2 (tipos de estructura)
        """
        if not structure_tree or "children" not in structure_tree:
            logger.warning("No hay estructura para corregir etiquetas")
            return False
        
        # Reiniciar estadísticas
        for key in self.stats:
            self.stats[key] = 0
        
        try:
            # Obtener mapa de roles si existe
            role_map = structure_tree.get("role_map", {})
            
            # Corregir el mapa de roles primero
            role_map_modified = self._fix_role_map(role_map)
            
            # Si se modificó el mapa de roles, actualizar en el árbol
            if role_map_modified:
                if hasattr(pdf_loader, "pikepdf_doc") and pdf_loader.pikepdf_doc:
                    self._update_role_map_in_document(pdf_loader.pikepdf_doc, role_map)
                    structure_tree["role_map"] = role_map
            
            # Corregir etiquetas en el árbol de estructura
            modified = self._fix_structure_tree(structure_tree["children"], None, role_map)
            
            # Corregir secuencia de encabezados para evitar saltos
            heading_fixed = self._fix_heading_sequence(structure_tree["children"])
            modified |= heading_fixed
            
            # Corregir atributos requeridos en etiquetas específicas
            attr_fixed = self._fix_required_attributes(structure_tree["children"])
            modified |= attr_fixed
            
            # Registrar correcciones realizadas
            if modified:
                logger.info(f"Correcciones realizadas: "
                           f"RoleMap={self.stats['role_map_fixes']}, "
                           f"Tags={self.stats['tag_fixes']}, "
                           f"ParentChild={self.stats['parent_child_fixes']}, "
                           f"Headings={self.stats['heading_sequence_fixes']}, "
                           f"Attributes={self.stats['attribute_fixes']}")
            else:
                logger.info("No se realizaron correcciones de etiquetas")
                
            return modified
            
        except Exception as e:
            logger.exception(f"Error al corregir etiquetas: {e}")
            return False
    
    def _fix_role_map(self, role_map: Dict) -> bool:
        """
        Corrige el mapa de roles para asegurar que cumpla con las normativas.
        
        Args:
            role_map: Diccionario con mapeos de roles personalizados
            
        Returns:
            bool: True si se realizaron correcciones, False en caso contrario
            
        Referencias:
            - Matterhorn: 02-001 a 02-004 (mapeo de roles)
            - Tagged PDF: 3.6 (mapeo de roles)
        """
        if not role_map:
            return False
        
        modified = False
        invalid_mappings = []
        
        # Comprobar cada mapeo
        for custom_type, standard_type in list(role_map.items()):
            # Normalizar tipos si tienen prefijo "/"
            if isinstance(custom_type, str) and custom_type.startswith("/"):
                normalized_custom = custom_type[1:]
            else:
                normalized_custom = custom_type
                
            if isinstance(standard_type, str) and standard_type.startswith("/"):
                normalized_standard = standard_type[1:]
            else:
                normalized_standard = standard_type
            
            # Checkpoint 02-004: Remapeo de tipos estándar (no permitido)
            if normalized_custom in self.valid_structure_types:
                if normalized_custom != normalized_standard:
                    logger.warning(f"Eliminando mapeo incorrecto de tipo estándar: {normalized_custom} -> {normalized_standard}")
                    invalid_mappings.append(custom_type)
                    self.stats["role_map_fixes"] += 1
                    modified = True
                    continue
            
            # Checkpoint 02-001: Verificar que el mapeo termina en un tipo estándar
            terminal_type = self._find_terminal_type(normalized_standard, role_map)
            if terminal_type not in self.valid_structure_types:
                # Corregir el mapeo a un tipo estándar apropiado
                corrected_type = self._find_appropriate_standard_type(normalized_custom)
                logger.info(f"Corrigiendo mapeo de '{normalized_custom}': {normalized_standard} -> {corrected_type}")
                role_map[custom_type] = corrected_type
                self.stats["role_map_fixes"] += 1
                modified = True
        
        # Eliminar mapeos inválidos
        for invalid in invalid_mappings:
            del role_map[invalid]
        
        # Checkpoint 02-003: Detectar y corregir mapeos circulares
        circular_mappings = self._detect_circular_mappings(role_map)
        if circular_mappings:
            for cycle in circular_mappings:
                for tag in cycle[:-1]:  # Todos excepto el último
                    if tag in role_map:
                        # Corregir el mapeo a un tipo estándar apropiado
                        corrected_type = self._find_appropriate_standard_type(tag)
                        logger.info(f"Corrigiendo mapeo circular '{tag}': {role_map[tag]} -> {corrected_type}")
                        role_map[tag] = corrected_type
                        self.stats["role_map_fixes"] += 1
                        modified = True
        
        return modified
    
    def _update_role_map_in_document(self, pikepdf_doc, role_map: Dict):
        """
        Actualiza el mapa de roles en el documento PDF real.
        
        Args:
            pikepdf_doc: Documento PDF de pikepdf
            role_map: Diccionario con mapeos de roles actualizados
        """
        if not hasattr(pikepdf_doc, "Root") or "/StructTreeRoot" not in pikepdf_doc.Root:
            return
        
        struct_root = pikepdf_doc.Root["/StructTreeRoot"]
        
        # Crear RoleMap si no existe
        if "/RoleMap" not in struct_root:
            struct_root.RoleMap = pikepdf.Dictionary({})
        
        # Actualizar mapeos
        for custom_type, standard_type in role_map.items():
            # Asegurar formato correcto para pikepdf
            if isinstance(custom_type, str) and not custom_type.startswith("/"):
                custom_key = f"/{custom_type}"
            else:
                custom_key = custom_type
                
            if isinstance(standard_type, str) and not standard_type.startswith("/"):
                standard_value = f"/{standard_type}"
            else:
                standard_value = standard_type
            
            struct_root.RoleMap[custom_key] = pikepdf.Name(standard_value)
        
        logger.info(f"Mapa de roles actualizado en el documento: {len(role_map)} entradas")
    
    def _fix_structure_tree(self, elements: List[Dict], parent_type: str, role_map: Dict) -> bool:
        """
        Corrige las etiquetas en el árbol de estructura de forma recursiva.
        
        Args:
            elements: Lista de elementos de estructura
            parent_type: Tipo del elemento padre
            role_map: Diccionario con mapeos de roles actualizados
            
        Returns:
            bool: True si se realizaron correcciones, False en caso contrario
        """
        if not elements:
            return False
        
        modified = False
        
        for element in elements:
            element_type = element.get("type", "Unknown")
            
            # Corregir tipos no estándar o desconocidos
            if element_type not in self.valid_structure_types:
                # Verificar si está mapeado a un tipo estándar
                mapped_type = self._find_terminal_type(element_type, role_map)
                
                if mapped_type not in self.valid_structure_types:
                    # Si no está mapeado correctamente, corregir la etiqueta
                    corrected_type = self._find_appropriate_tag(element, parent_type)
                    logger.info(f"Corrigiendo tipo no estándar: '{element_type}' -> '{corrected_type}'")
                    
                    # Actualizar el tipo en el elemento
                    element["type"] = corrected_type
                    
                    # Actualizar en el objeto pikepdf si está disponible
                    if "element" in element and hasattr(element["element"], "S"):
                        element["element"].S = pikepdf.Name(f"/{corrected_type}")
                    
                    self.stats["tag_fixes"] += 1
                    modified = True
            
            # Corregir etiquetas mal utilizadas (por ejemplo, Title -> H1)
            elif element_type in self.common_tag_corrections:
                corrected_type = self.common_tag_corrections[element_type]
                logger.info(f"Corrigiendo etiqueta mal utilizada: '{element_type}' -> '{corrected_type}'")
                
                # Actualizar el tipo en el elemento
                element["type"] = corrected_type
                
                # Actualizar en el objeto pikepdf si está disponible
                if "element" in element and hasattr(element["element"], "S"):
                    element["element"].S = pikepdf.Name(f"/{corrected_type}")
                
                self.stats["tag_fixes"] += 1
                modified = True
            
            # Verificar relación padre-hijo adecuada
            if parent_type and not self._is_valid_parent_child(parent_type, element_type):
                # Reasignar etiqueta para una relación padre-hijo válida
                corrected_type = self._find_valid_child_type(parent_type, element)
                logger.info(f"Corrigiendo relación padre-hijo: '{parent_type}' > '{element_type}' -> '{corrected_type}'")
                
                # Actualizar el tipo en el elemento
                element["type"] = corrected_type
                
                # Actualizar en el objeto pikepdf si está disponible
                if "element" in element and hasattr(element["element"], "S"):
                    element["element"].S = pikepdf.Name(f"/{corrected_type}")
                
                self.stats["parent_child_fixes"] += 1
                modified = True
            
            # Procesar hijos recursivamente
            if "children" in element and element["children"]:
                child_modified = self._fix_structure_tree(element["children"], element["type"], role_map)
                modified |= child_modified
        
        return modified
    
    def _fix_heading_sequence(self, elements: List[Dict], path: str = "") -> bool:
        """
        Corrige la secuencia de encabezados para evitar saltos (Checkpoint 14-003).
        
        Args:
            elements: Lista de elementos de estructura
            path: Ruta de anidamiento actual
            
        Returns:
            bool: True si se realizaron correcciones, False en caso contrario
        """
        if not elements:
            return False
        
        modified = False
        
        # Recolectar todos los encabezados en este nivel
        headings = []
        for i, element in enumerate(elements):
            element_type = element.get("type", "")
            
            # Verificar si es un encabezado numerado (H1-H6)
            if re.match(r'^H\d$', element_type):
                headings.append({
                    "index": i,
                    "type": element_type,
                    "level": int(element_type[1:]),
                    "element": element
                })
        
        # Si hay encabezados, verificar y corregir la secuencia
        if headings:
            # Ordenar por índice para mantener el orden original
            headings.sort(key=lambda h: h["index"])
            
            # Verificar saltos en la secuencia
            for i in range(1, len(headings)):
                prev_level = headings[i-1]["level"]
                curr_level = headings[i]["level"]
                
                # Si hay un salto mayor de 1 nivel
                if curr_level > prev_level + 1:
                    # Corregir al nivel siguiente apropiado
                    corrected_level = prev_level + 1
                    corrected_type = f"H{corrected_level}"
                    
                    logger.info(f"Corrigiendo secuencia de encabezados: {headings[i]['type']} -> {corrected_type}")
                    
                    # Actualizar el tipo en el elemento
                    element = headings[i]["element"]
                    element["type"] = corrected_type
                    
                    # Actualizar en el objeto pikepdf si está disponible
                    if "element" in element and hasattr(element["element"], "S"):
                        element["element"].S = pikepdf.Name(f"/{corrected_type}")
                    
                    self.stats["heading_sequence_fixes"] += 1
                    modified = True
                    
                    # Actualizar el nivel en el registro de headings para los siguientes chequeos
                    headings[i]["level"] = corrected_level
                    headings[i]["type"] = corrected_type
        
        # Procesar hijos recursivamente
        for element in elements:
            if "children" in element and element["children"]:
                child_modified = self._fix_heading_sequence(element["children"], path + "/" + element.get("type", ""))
                modified |= child_modified
        
        return modified
    
    def _fix_required_attributes(self, elements: List[Dict], path: str = "") -> bool:
        """
        Añade atributos requeridos a etiquetas específicas.
        
        Args:
            elements: Lista de elementos de estructura
            path: Ruta de anidamiento actual
            
        Returns:
            bool: True si se realizaron correcciones, False en caso contrario
        """
        if not elements:
            return False
        
        modified = False
        
        for element in elements:
            element_type = element.get("type", "")
            
            # Verificar si el elemento requiere atributos específicos
            if element_type in self.required_attributes:
                required_attrs = self.required_attributes[element_type]
                
                for attr in required_attrs:
                    # Verificar si el atributo ya existe
                    if not self._has_attribute(element, attr):
                        # Añadir atributo faltante con valor predeterminado
                        if attr == "alt":
                            # Para Figure y Formula, añadir Alt genérico
                            if element_type == "Figure":
                                alt_text = self._generate_alt_text(element, "Imagen")
                            elif element_type == "Formula":
                                alt_text = self._generate_alt_text(element, "Fórmula matemática")
                            else:
                                alt_text = f"{element_type}"
                                
                            self._add_attribute(element, "alt", alt_text)
                            logger.info(f"Añadido atributo Alt a {element_type}: '{alt_text[:30]}...' si es largo")
                            self.stats["attribute_fixes"] += 1
                            modified = True
                            
                        elif attr == "scope":
                            # Para TH, determinar Scope basado en posición
                            scope_value = self._determine_th_scope(element)
                            self._add_attribute(element, "scope", scope_value)
                            logger.info(f"Añadido atributo Scope a TH: '{scope_value}'")
                            self.stats["attribute_fixes"] += 1
                            modified = True
                            
                        elif attr == "id":
                            # Generar ID único
                            unique_id = f"{element_type}_{id(element)}"
                            self._add_attribute(element, "id", unique_id)
                            logger.info(f"Añadido atributo ID a {element_type}: '{unique_id}'")
                            self.stats["attribute_fixes"] += 1
                            modified = True
            
            # Procesar hijos recursivamente
            if "children" in element and element["children"]:
                child_modified = self._fix_required_attributes(element["children"], path + "/" + element_type)
                modified |= child_modified
        
        return modified
    
    def _generate_alt_text(self, element: Dict, default_prefix: str) -> str:
        """
        Genera un texto alternativo descriptivo para un elemento.
        
        Args:
            element: Elemento para el que generar el texto Alt
            default_prefix: Prefijo predeterminado para el texto Alt
            
        Returns:
            str: Texto alternativo generado
        """
        # Si hay una leyenda asociada, usarla como base para el texto Alt
        caption_text = self._find_associated_caption(element)
        if caption_text:
            return caption_text
            
        # Si hay texto dentro del elemento, usarlo
        element_text = element.get("text", "").strip()
        if element_text:
            return f"{default_prefix}: {element_text}"
            
        # Si hay hijos con texto, concatenarlos
        child_texts = []
        for child in element.get("children", []):
            child_text = child.get("text", "").strip()
            if child_text:
                child_texts.append(child_text)
                
        if child_texts:
            # Limitar la longitud total
            combined_text = " ".join(child_texts)
            if len(combined_text) > 100:
                combined_text = combined_text[:97] + "..."
            return f"{default_prefix}: {combined_text}"
            
        # Si no hay texto disponible, generar un texto genérico con ID
        element_id = id(element)
        return f"{default_prefix} (ID: {element_id})"
    
    def _find_associated_caption(self, element: Dict) -> str:
        """
        Busca el texto de una leyenda asociada con un elemento.
        
        Args:
            element: Elemento para el que buscar la leyenda
            
        Returns:
            str: Texto de la leyenda o cadena vacía si no se encuentra
        """
        # Verificar si el elemento tiene hijos de tipo Caption
        for child in element.get("children", []):
            if child.get("type") == "Caption":
                # Extraer texto de la Caption
                caption_text = child.get("text", "").strip()
                if caption_text:
                    return caption_text
                    
                # Si la Caption no tiene texto directo, buscar en sus hijos
                for caption_child in child.get("children", []):
                    caption_child_text = caption_child.get("text", "").strip()
                    if caption_child_text:
                        return caption_child_text
        
        # La Caption puede estar como hermano inmediato en lugar de hijo
        if "parent" in element:
            parent = element["parent"]
            if parent and "children" in parent:
                # Encontrar el índice del elemento actual
                element_index = -1
                for i, sibling in enumerate(parent["children"]):
                    if sibling is element:
                        element_index = i
                        break
                        
                if element_index >= 0:
                    # Verificar el elemento anterior o siguiente
                    for offset in [-1, 1]:
                        sibling_index = element_index + offset
                        if 0 <= sibling_index < len(parent["children"]):
                            sibling = parent["children"][sibling_index]
                            if sibling.get("type") == "Caption":
                                caption_text = sibling.get("text", "").strip()
                                if caption_text:
                                    return caption_text
                                
                                # Buscar en hijos de la Caption
                                for caption_child in sibling.get("children", []):
                                    caption_child_text = caption_child.get("text", "").strip()
                                    if caption_child_text:
                                        return caption_child_text
        
        return ""
    
    def _determine_th_scope(self, element: Dict) -> str:
        """
        Determina el valor apropiado para el atributo Scope en una celda TH.
        
        Args:
            element: Elemento TH
            
        Returns:
            str: Valor apropiado para Scope (Row, Column, Both)
        """
        # Buscar el elemento padre TR
        if "parent" in element and element["parent"].get("type") == "TR":
            tr_element = element["parent"]
            
            # Determinar si es la primera fila
            if "parent" in tr_element:
                tr_parent = tr_element["parent"]
                
                # Si el padre es Table, THead, TBody o TFoot
                if tr_parent.get("type") in ["Table", "THead", "TBody", "TFoot"]:
                    # Si es la primera fila dentro de su contenedor
                    if tr_parent["children"][0] is tr_element:
                        # Es probablemente un encabezado de columna
                        return "Column"
            
            # Determinar si es la primera celda de la fila
            if tr_element["children"][0] is element:
                # Es probablemente un encabezado de fila
                return "Row"
            
            # Si es la única celda TH en la fila
            th_cells = [c for c in tr_element.get("children", []) if c.get("type") == "TH"]
            if len(th_cells) == 1 and th_cells[0] is element:
                return "Row"
                
            # Si todas las celdas son TH
            if all(c.get("type") == "TH" for c in tr_element.get("children", [])):
                return "Column"
        
        # Para los casos donde no se puede determinar claramente, usar Column como predeterminado
        # Column es más común y generalmente mejor soportado
        return "Column"
    
    def _find_terminal_type(self, type_name: str, role_map: Dict, visited: Set[str] = None) -> str:
        """
        Encuentra el tipo terminal al seguir una cadena de mapeos.
        
        Args:
            type_name: Nombre del tipo a verificar
            role_map: Diccionario con mapeos de roles
            visited: Conjunto de tipos ya visitados (para detectar ciclos)
            
        Returns:
            str: Tipo terminal
        """
        if visited is None:
            visited = set()
        
        # Eliminar prefijo "/" si está presente
        if isinstance(type_name, str) and type_name.startswith("/"):
            type_name = type_name[1:]
        
        # Si es un tipo estándar, es terminal
        if type_name in self.valid_structure_types:
            return type_name
        
        # Si no está en el mapa, es terminal (aunque no sea estándar)
        if type_name not in role_map:
            return type_name
        
        # Si ya visitamos este tipo, hay un ciclo
        if type_name in visited:
            return "CYCLE"
        
        # Seguir la cadena de mapeo
        visited.add(type_name)
        next_type = role_map[type_name]
        
        # Eliminar prefijo "/" si está presente
        if isinstance(next_type, str) and next_type.startswith("/"):
            next_type = next_type[1:]
            
        return self._find_terminal_type(next_type, role_map, visited)
    
    def _detect_circular_mappings(self, mapping_graph: Dict) -> List[List[str]]:
        """
        Detecta ciclos en el grafo de mapeos.
        
        Args:
            mapping_graph: Diccionario representando el grafo de mapeos
            
        Returns:
            List[List[str]]: Lista de ciclos detectados
        """
        cycles = []
        visited = set()
        path = []
        
        def dfs(node):
            if node in path:
                # Ciclo detectado
                cycle_start = path.index(node)
                cycles.append(path[cycle_start:] + [node])
                return
            
            if node in visited:
                return
                
            visited.add(node)
            path.append(node)
            
            if node in mapping_graph:
                next_node = mapping_graph[node]
                # Eliminar prefijo "/" si está presente
                if isinstance(next_node, str) and next_node.startswith("/"):
                    next_node = next_node[1:]
                dfs(next_node)
                
            path.pop()
        
        # Normalizar claves
        normalized_graph = {}
        for key, value in mapping_graph.items():
            if isinstance(key, str) and key.startswith("/"):
                key = key[1:]
            if isinstance(value, str) and value.startswith("/"):
                value = value[1:]
            normalized_graph[key] = value
        
        for node in normalized_graph:
            if node not in visited:
                dfs(node)
            
        return cycles
    
    def _find_appropriate_standard_type(self, custom_type: str) -> str:
        """
        Encuentra un tipo estándar apropiado para un tipo personalizado.
        
        Args:
            custom_type: Tipo personalizado a mapear
            
        Returns:
            str: Tipo estándar apropiado
        """
        # Normalizar a minúsculas
        lower_type = custom_type.lower() if isinstance(custom_type, str) else ""
        
        # Mapeo de patrones comunes
        patterns = {
            r'h\d+': "H1",            # H7, H8, etc.
            r'head\d*': "H1",         # Head, Head1, etc.
            r'title\d*': "H1",        # Title, Title1, etc.
            r'heading\d*': "H1",      # Heading, Heading1, etc.
            r'subtitle\d*': "H2",     # Subtitle, Subtitle1, etc.
            r'chap\w*': "H1",         # Chapter, Chap, etc.
            r'sect\w*': "Sect",       # Section, Sect, etc.
            r'paragraph': "P",        # Paragraph
            r'para\w*': "P",          # Para, Parag, etc.
            r'text\w*': "P",          # Text, TextBlock, etc.
            r'img\w*': "Figure",      # Img, Image, etc.
            r'pic\w*': "Figure",      # Pic, Picture, etc.
            r'fig\w*': "Figure",      # Fig, Figure, etc.
            r'table\w*': "Table",     # Table, TableData, etc.
            r'row\w*': "TR",          # Row, RowData, etc.
            r'cell\w*': "TD",         # Cell, CellData, etc.
            r'header\w*cell': "TH",   # HeaderCell, etc.
            r'th\w*': "TH",           # Th, ThCell, etc.
            r'td\w*': "TD",           # Td, TdCell, etc.
            r'list\w*': "L",          # List, ListBlock, etc.
            r'item\w*': "LI",         # Item, ListItem, etc.
            r'(bullet|numbered)list': "L",  # BulletList, NumberedList
            r'caption\w*': "Caption", # Caption, CaptionText, etc.
            r'link\w*': "Link",       # Link, LinkText, etc.
            r'note\w*': "Note",       # Note, Footnote, etc.
            r'quote\w*': "Quote",     # Quote, Quotation, etc.
            r'formula\w*': "Formula", # Formula, FormulaBlock, etc.
            r'div\w*': "Div",         # Div, Division, etc.
            r'span\w*': "Span",       # Span, Spanning, etc.
            r'annotation\w*': "Annot", # Annotation, etc.
            r'form\w*': "Form",       # Form, FormField, etc.
            r'reference\w*': "Reference", # Reference, etc.
        }
        
        # Verificar cada patrón
        for pattern, standard_type in patterns.items():
            if re.match(pattern, lower_type):
                return standard_type
        
        # Si no hay coincidencia, usar P como tipo predeterminado seguro
        return "P"
    
    def _find_appropriate_tag(self, element: Dict, parent_type: str) -> str:
        """
        Encuentra una etiqueta apropiada basada en el contenido y contexto.
        
        Args:
            element: Elemento de estructura
            parent_type: Tipo del elemento padre
            
        Returns:
            str: Tipo de etiqueta apropiado
        """
        # Comprobar si el tipo actual ya está en common_tag_corrections
        element_type = element.get("type", "Unknown")
        if element_type in self.common_tag_corrections:
            return self.common_tag_corrections[element_type]
        
        # Analizar contenido para determinar el tipo apropiado
        text = element.get("text", "")
        has_children = bool(element.get("children"))
        
        # Si no tiene texto ni hijos, usar "Div" como contenedor genérico
        if not text and not has_children:
            return "Div"
        
        # Intentar identificar encabezados basados en características
        if self._looks_like_heading(element):
            # Determinar nivel de encabezado basado en contexto
            if parent_type in ["Document", "Part", "Art"]:
                return "H1"
            elif parent_type in ["Sect"]:
                return "H2"
            else:
                return "H3"  # Nivel seguro predeterminado
        
        # Verificar si parece una figura
        if self._looks_like_figure(element):
            return "Figure"
        
        # Verificar si parece una tabla
        if self._looks_like_table(element):
            return "Table"
        
        # Verificar si parece una lista
        if self._looks_like_list(element):
            return "L"
        
        # Verificar si parece un elemento de lista
        if self._looks_like_list_item(element):
            return "LI"
        
        # Verificar tipos específicos para hijos de estructuras específicas
        if parent_type == "Table":
            # Hijo directo de tabla debe ser TR, THead, TBody, TFoot o Caption
            if self._looks_like_table_row(element):
                return "TR"
            elif self._looks_like_caption(element):
                return "Caption"
            else:
                # Predeterminado seguro para tabla
                return "TR"
                
        elif parent_type == "TR":
            # Hijo directo de TR debe ser TH o TD
            if self._looks_like_table_header(element):
                return "TH"
            else:
                return "TD"
                
        elif parent_type == "L":
            # Hijo directo de L debe ser LI o Caption
            if self._looks_like_caption(element):
                return "Caption"
            else:
                return "LI"
                
        elif parent_type == "LI":
            # Hijo directo de LI debe ser Lbl o LBody
            if self._looks_like_label(element):
                return "Lbl"
            else:
                return "LBody"
        
        # Predeterminado para contenido de texto normal
        return "P"
    
    def _find_valid_child_type(self, parent_type: str, element: Dict) -> str:
        """
        Encuentra un tipo válido para un hijo basado en el tipo de padre.
        
        Args:
            parent_type: Tipo del elemento padre
            element: Elemento hijo
            
        Returns:
            str: Tipo válido para el hijo
        """
        element_type = element.get("type", "Unknown")
        
        # Si el padre no está en el mapeo, usar tipo actual
        if parent_type not in self.valid_parent_child:
            return element_type
        
        # Verificar si el tipo actual es válido para este padre
        valid_children = self.valid_parent_child[parent_type]
        if element_type in valid_children:
            return element_type
        
        # Buscar un tipo válido basado en la semántica
        # Primero intentar encontrar un tipo apropiado basado en contenido
        appropriate_type = self._find_appropriate_tag(element, parent_type)
        
        # Verificar si el tipo apropiado es válido para este padre
        if appropriate_type in valid_children:
            return appropriate_type
        
        # Si no es válido, usar un tipo seguro para este padre
        safe_types = ["P", "Span", "Div"]
        for safe_type in safe_types:
            if safe_type in valid_children:
                return safe_type
        
        # Si no hay tipos seguros, usar el primer hijo válido
        if valid_children:
            return valid_children[0]
        
        # Si no hay hijos válidos definidos, usar "Span" como opción segura
        return "Span"
    
    def _is_valid_parent_child(self, parent_type: str, child_type: str) -> bool:
        """
        Verifica si la relación padre-hijo es válida.
        
        Args:
            parent_type: Tipo del elemento padre
            child_type: Tipo del elemento hijo
            
        Returns:
            bool: True si la relación es válida
        """
        # Si el padre no está en el mapeo, permitir cualquier hijo
        if parent_type not in self.valid_parent_child:
            return True
        
        # Verificar si el hijo está permitido en este padre
        valid_children = self.valid_parent_child[parent_type]
        return child_type in valid_children
    
    def _looks_like_heading(self, element: Dict) -> bool:
        """
        Determina si un elemento parece un encabezado.
        
        Args:
            element: Elemento a evaluar
            
        Returns:
            bool: True si parece un encabezado
        """
        # Verificar si el elemento tiene características de encabezado
        text = element.get("text", "")
        
        # Verificar longitud del texto (los encabezados suelen ser cortos)
        if text and len(text.strip()) < 100:
            # Verificar características comunes de encabezados
            if text.strip().endswith(":"):
                return True
            
            # Verificar si comienza con números de sección (1., 1.1, etc.)
            if re.match(r'^\d+(\.\d+)*\.?\s+', text.strip()):
                return True
            
            # Verificar si hay pocos hijos (los encabezados suelen tener estructura simple)
            if len(element.get("children", [])) <= 1:
                # Si el texto es corto (< 50 caracteres) y no parece parte de un párrafo
                # (no termina con punto)
                if len(text.strip()) < 50 and not text.strip().endswith("."):
                    return True
        
        return False
    
    def _looks_like_figure(self, element: Dict) -> bool:
        """
        Determina si un elemento parece una figura.
        
        Args:
            element: Elemento a evaluar
            
        Returns:
            bool: True si parece una figura
        """
        # Verificar si hay texto o hijos con características de figura
        
        # Verificar si hay pocas palabras (típico en figuras)
        text = element.get("text", "")
        if text and len(text.split()) < 10:
            # Verificar si incluye palabras clave comunes en figuras
            lower_text = text.lower()
            figure_keywords = ["fig", "figure", "imagen", "image", "ilustración", 
                              "illustration", "foto", "photo", "gráfico", "graph", 
                              "chart", "diagrama", "diagram"]
            for keyword in figure_keywords:
                if keyword in lower_text:
                    return True
        
        # Verificar si tiene algún MCID en un objeto de imagen
        # (Sería necesario tener acceso a los objetos visuales del PDF)
        
        return False
    
    def _looks_like_table(self, element: Dict) -> bool:
        """
        Determina si un elemento parece una tabla.
        
        Args:
            element: Elemento a evaluar
            
        Returns:
            bool: True si parece una tabla
        """
        # Verificar si los hijos parecen filas de tabla
        children = element.get("children", [])
        if children:
            # Si la mayoría de los hijos son TR o parecen filas, es probable que sea una tabla
            tr_like_children = [c for c in children if c.get("type") == "TR" or self._looks_like_table_row(c)]
            return len(tr_like_children) >= len(children) * 0.5
        
        return False
    
    def _looks_like_table_row(self, element: Dict) -> bool:
        """
        Determina si un elemento parece una fila de tabla.
        
        Args:
            element: Elemento a evaluar
            
        Returns:
            bool: True si parece una fila de tabla
        """
        # Verificar si los hijos parecen celdas de tabla
        children = element.get("children", [])
        if children:
            # Si la mayoría de los hijos son TH/TD o parecen celdas, es probable que sea una fila
            cell_like_children = [c for c in children if c.get("type") in ["TH", "TD"] or 
                                 self._looks_like_table_header(c) or 
                                 self._looks_like_table_cell(c)]
            return len(cell_like_children) >= len(children) * 0.5
        
        return False
    
    def _looks_like_table_header(self, element: Dict) -> bool:
        """
        Determina si un elemento parece un encabezado de tabla.
        
        Args:
            element: Elemento a evaluar
            
        Returns:
            bool: True si parece un encabezado de tabla
        """
        # Implementar lógica para detectar celdas de encabezado
        return False  # Implementar lógica real
    
    def _looks_like_table_cell(self, element: Dict) -> bool:
        """
        Determina si un elemento parece una celda de tabla.
        
        Args:
            element: Elemento a evaluar
            
        Returns:
            bool: True si parece una celda de tabla
        """
        # Implementar lógica para detectar celdas de tabla
        return False  # Implementar lógica real
    
    def _looks_like_list(self, element: Dict) -> bool:
        """
        Determina si un elemento parece una lista.
        
        Args:
            element: Elemento a evaluar
            
        Returns:
            bool: True si parece una lista
        """
        # Verificar si los hijos parecen elementos de lista
        children = element.get("children", [])
        if children:
            # Si la mayoría de los hijos son LI o parecen elementos de lista, es probable que sea una lista
            li_like_children = [c for c in children if c.get("type") == "LI" or self._looks_like_list_item(c)]
            return len(li_like_children) >= len(children) * 0.5
        
        return False
    
    def _looks_like_list_item(self, element: Dict) -> bool:
        """
        Determina si un elemento parece un elemento de lista.
        
        Args:
            element: Elemento a evaluar
            
        Returns:
            bool: True si parece un elemento de lista
        """
        # Implementar lógica para detectar elementos de lista
        text = element.get("text", "")
        if text:
            # Verificar indicadores comunes de elementos de lista
            if re.match(r'^\s*[•\-\*\○\●\■\□\▪\▫\◦\»\~\+]\s+', text):
                return True
            if re.match(r'^\s*\d+[\.\)]\s+', text):
                return True
            if re.match(r'^\s*[a-zA-Z][\.\)]\s+', text):
                return True
        
        return False
    
    def _looks_like_label(self, element: Dict) -> bool:
        """
        Determina si un elemento parece una etiqueta.
        
        Args:
            element: Elemento a evaluar
            
        Returns:
            bool: True si parece una etiqueta
        """
        # Implementar lógica para detectar etiquetas
        text = element.get("text", "")
        if text:
            # Verificar indicadores comunes de etiquetas
            if re.match(r'^\s*[•\-\*\○\●\■\□\▪\▫\◦\»\~\+]$', text):
                return True
            if re.match(r'^\s*\d+[\.\)]$', text):
                return True
            if re.match(r'^\s*[a-zA-Z][\.\)]$', text):
                return True
        
        return False
    
    def _has_attribute(self, element: Dict, attribute: str) -> bool:
        """
        Verifica si un elemento tiene un atributo específico.
        
        Args:
            element: Elemento a verificar
            attribute: Nombre del atributo
            
        Returns:
            bool: True si el elemento tiene el atributo
        """
        # Verificar en el diccionario de atributos
        if "attributes" in element and attribute in element["attributes"]:
            value = element["attributes"][attribute]
            # Considerar vacío como no existente
            return value is not None and value != ""
        
        # Verificar como propiedad directa del elemento (algunos PDFs lo usan así)
        if attribute in element:
            value = element[attribute]
            return value is not None and value != ""
        
        # Verificar en el objeto pikepdf si está disponible
        if "element" in element:
            pikepdf_element = element["element"]
            # Convertir primera letra a mayúscula para formato pikepdf
            pikepdf_attr = attribute[0].upper() + attribute[1:]
            if hasattr(pikepdf_element, pikepdf_attr):
                value = getattr(pikepdf_element, pikepdf_attr)
                return value is not None and value != ""
            
            # También verificar formatos alternativos (Alt, alt, /Alt)
            alt_names = [f"/{pikepdf_attr}", attribute, attribute.upper()]
            for name in alt_names:
                if name in pikepdf_element:
                    value = pikepdf_element[name]
                    return value is not None and value != ""
        
        return False
    
    def _add_attribute(self, element: Dict, attribute: str, value: Any) -> bool:
        """
        Añade un atributo a un elemento.
        
        Args:
            element: Elemento a modificar
            attribute: Nombre del atributo
            value: Valor a asignar
            
        Returns:
            bool: True si se añadió correctamente
        """
        try:
            # Crear diccionario de atributos si no existe
            if "attributes" not in element:
                element["attributes"] = {}
            
            # Añadir atributo al elemento
            element["attributes"][attribute] = value
            
            # Añadir atributo al objeto pikepdf si está disponible
            if "element" in element:
                pikepdf_element = element["element"]
                attr_key = f"/{attribute[0].upper()}{attribute[1:]}" if len(attribute) > 1 else f"/{attribute.upper()}"
                
                # Convertir valor según tipo de atributo
                pikepdf_value = value
                if attribute in ["alt", "actualtext", "lang", "e"]:
                    pikepdf_value = pikepdf.String(value)
                elif attribute in ["scope", "listnumbering"]:
                    pikepdf_value = pikepdf.Name(f"/{value}")
                
                pikepdf_element[attr_key] = pikepdf_value
            
            return True
        except Exception as e:
            logger.error(f"Error al añadir atributo {attribute}: {e}")
            return False
    
    def _determine_th_scope(self, element: Dict) -> str:
        """
        Determina el valor apropiado para el atributo Scope en una celda TH.
        
        Args:
            element: Elemento TH
            
        Returns:
            str: Valor apropiado para Scope (Row, Column, Both)
        """
        # Intentar determinar si es una celda de encabezado de fila o columna
        # Predeterminado a "Column" para mayor compatibilidad
        return "Column"
    
    def _looks_like_caption(self, element):
        """Heurística para detectar si un elemento parece una leyenda de figura o tabla."""
        if "content" in element:
            content = element["content"].lower()
            return content.startswith("figura") or content.startswith("tabla") or "leyenda" in content
        return False