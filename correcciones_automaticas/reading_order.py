#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Módulo para corregir el orden de lectura en documentos PDF.

Implementa algoritmos para analizar y corregir el orden de lectura lógico
en documentos PDF, asegurando el cumplimiento del checkpoint 09-001 del
Matterhorn Protocol y la sección 7.1 de ISO 14289-1 (PDF/UA).

Referencias:
- Matterhorn Protocol 1.1: Checkpoint 09-001
- ISO 14289-1 (PDF/UA): 7.1
- Tagged PDF Best Practice Guide: Syntax: 3.2.2 "Reading order"
"""

from typing import Dict, List, Optional, Tuple, Set, Any, Union
import math
from collections import deque, defaultdict
import re
from loguru import logger
import fitz  # PyMuPDF

class ReadingOrderFixer:
    """
    Clase para analizar y corregir el orden de lectura en documentos PDF.
    
    Proporciona métodos para:
    - Detectar problemas en el orden de lectura
    - Calcular un orden de lectura óptimo
    - Reordenar el árbol estructural según el orden de lectura lógico
    """
    
    def __init__(self, pdf_writer=None):
        """
        Inicializa el corrector de orden de lectura.
        
        Args:
            pdf_writer: Instancia de PDFWriter para aplicar cambios
        """
        self.pdf_writer = pdf_writer
        self.reading_directions = {
            "lr-tb": {"primary": "horizontal", "secondary": "vertical"},  # Izquierda a derecha, arriba a abajo (occidental)
            "rl-tb": {"primary": "horizontal_reversed", "secondary": "vertical"},  # Derecha a izquierda, arriba a abajo (árabe)
            "tb-rl": {"primary": "vertical", "secondary": "horizontal_reversed"},  # Arriba a abajo, derecha a izquierda (chino tradicional)
            "tb-lr": {"primary": "vertical", "secondary": "horizontal"}  # Arriba a abajo, izquierda a derecha (japonés moderno)
        }
        # Tolerancia para agrupar elementos como pertenecientes a la misma línea o columna
        self.position_tolerance = 0.02  # 2% de la dimensión de la página
        # Umbral para considerar dos columnas como separadas
        self.column_threshold = 0.1  # 10% de la anchura de la página
        # Valores de confianza para decisiones algorítmicas
        self.confidence_thresholds = {
            "high": 0.8,
            "medium": 0.5,
            "low": 0.3
        }
        logger.info("ReadingOrderFixer inicializado")
    
    def set_pdf_writer(self, pdf_writer):
        """
        Establece la referencia al escritor de PDF.
        
        Args:
            pdf_writer: Instancia de PDFWriter con el documento cargado
        """
        self.pdf_writer = pdf_writer
        logger.debug("PDFWriter establecido en ReadingOrderFixer")
    
    def fix_reading_order(self, structure_tree: Dict, pdf_loader) -> bool:
        """
        Analiza y corrige el orden de lectura del documento.
        
        Args:
            structure_tree: Diccionario con el árbol estructural del documento
            pdf_loader: Referencia al cargador de PDF con el documento
            
        Returns:
            bool: True si se realizaron cambios, False en caso contrario
            
        Referencias:
            - Matterhorn 09-001: Tags are not in logical reading order
            - PDF/UA-1: 7.1, párrafo 2
        """
        if not pdf_loader or not structure_tree:
            logger.warning("No hay documento cargado o estructura para corregir")
            return False
        
        # Almacenar referencia al PDF para análisis
        self.pdf_loader = pdf_loader
            
        # Detectar problemas de orden de lectura
        issues = self.detect_reading_order_issues(structure_tree)
        
        if not issues:
            logger.info("No se detectaron problemas de orden de lectura")
            return False
            
        logger.info(f"Detectados {len(issues)} problemas de orden de lectura")
        
        # Corregir el orden de lectura según el tipo de documento y estructura
        # Este proceso es complejo y requiere diferentes estrategias
        changes_made = False
        
        # 1. Intentar primero la estrategia basada en detección de columnas y flujos
        changes_made = self._apply_flow_analysis_strategy(structure_tree, issues) or changes_made
        
        # 2. Si no hay suficientes cambios, intentar estrategia basada en posición visual
        if not changes_made or len(issues) > 10:
            changes_made = self._apply_visual_position_strategy(structure_tree, issues) or changes_made
        
        # 3. Si persisten problemas graves, intentar la estrategia de reordenamiento completo
        if sum(1 for issue in issues if issue["severity"] == "error") > 5:
            changes_made = self._apply_full_reordering_strategy(structure_tree) or changes_made
        
        logger.info(f"Corrección de orden de lectura: {'completada' if changes_made else 'no se requirieron cambios'}")
        return changes_made
    
    def detect_reading_order_issues(self, structure_tree: Dict) -> List[Dict]:
        """
        Detecta problemas en el orden de lectura actual.
        
        Args:
            structure_tree: Árbol estructural del documento
            
        Returns:
            List[Dict]: Lista de problemas detectados con metadatos
        """
        issues = []
        
        if not structure_tree or not structure_tree.get("children"):
            return issues
        
        # Determinar el modo de lectura predominante en el documento
        document_lang = self._get_document_language()
        reading_mode = self._determine_reading_mode(document_lang)
        
        # Analizar página por página para detectar inconsistencias
        pages_structure = self._extract_structures_by_page(structure_tree)
        
        for page_num, page_elements in pages_structure.items():
            # Obtener coordenadas visuales de los elementos en la página
            elements_with_positions = self._get_elements_positions(page_num, page_elements)
            
            # Determinar orden visual según dirección de lectura
            visual_order = self._calculate_visual_order(elements_with_positions, reading_mode)
            
            # Comparar orden actual con orden visual ideal
            current_order = {elem["id"]: idx for idx, elem in enumerate(page_elements) if "id" in elem}
            
            for idx, elem_id in enumerate(visual_order):
                if elem_id in current_order and abs(current_order[elem_id] - idx) > 1:
                    # Elemento fuera de orden
                    element = next((e for e in page_elements if e.get("id") == elem_id), None)
                    if element:
                        severity = "error" if abs(current_order[elem_id] - idx) > 3 else "warning"
                        
                        # Determinar el tipo de problema
                        issue_type = "column_order" if self._is_column_order_issue(elements_with_positions, elem_id, idx) else "general_order"
                        
                        issues.append({
                            "page": page_num,
                            "element_id": elem_id,
                            "element_type": element.get("type", "Unknown"),
                            "current_position": current_order[elem_id],
                            "expected_position": idx,
                            "severity": severity,
                            "description": f"Elemento fuera del orden lógico de lectura",
                            "issue_type": issue_type
                        })
        
        # Detectar problemas específicos en tablas
        table_issues = self._detect_table_reading_order_issues(structure_tree)
        issues.extend(table_issues)
        
        # Detectar problemas en listas
        list_issues = self._detect_list_reading_order_issues(structure_tree)
        issues.extend(list_issues)
        
        # Detectar problemas en secciones con múltiples columnas
        column_issues = self._detect_multi_column_issues(structure_tree)
        issues.extend(column_issues)
        
        return issues
    
    def _apply_flow_analysis_strategy(self, structure_tree: Dict, issues: List[Dict]) -> bool:
        """
        Estrategia basada en análisis de flujo de lectura.
        
        Identifica columnas, bloques y direcciones principales de lectura
        para corregir el orden manteniendo la estructura semántica.
        
        Args:
            structure_tree: Árbol estructural del documento
            issues: Problemas de orden de lectura detectados
            
        Returns:
            bool: True si se realizaron cambios
        """
        changes_made = False
        
        # Primero agrupar problemas por página
        issues_by_page = defaultdict(list)
        for issue in issues:
            issues_by_page[issue["page"]].append(issue)
        
        # Procesar cada página con problemas
        for page_num, page_issues in issues_by_page.items():
            # Detectar columnas en la página
            columns = self._detect_columns_in_page(page_num)
            
            if columns:
                logger.info(f"Detectadas {len(columns)} columnas en página {page_num}")
                
                # Reorganizar elementos por columnas
                changes_made = self._reorder_elements_by_columns(page_num, columns) or changes_made
            else:
                # Si no hay columnas claras, reorganizar por bloques de contenido
                blocks = self._detect_content_blocks(page_num)
                if blocks:
                    logger.info(f"Detectados {len(blocks)} bloques de contenido en página {page_num}")
                    changes_made = self._reorder_elements_by_blocks(page_num, blocks) or changes_made
        
        return changes_made
    
    def _apply_visual_position_strategy(self, structure_tree: Dict, issues: List[Dict]) -> bool:
        """
        Estrategia basada en posición visual de los elementos.
        
        Reordena elementos individuales según su posición visual, manteniendo
        la jerarquía de la estructura.
        
        Args:
            structure_tree: Árbol estructural del documento
            issues: Problemas de orden de lectura detectados
            
        Returns:
            bool: True si se realizaron cambios
        """
        changes_made = False
        
        # Procesar cada problema detectado
        for issue in issues:
            element_id = issue["element_id"]
            expected_position = issue["expected_position"]
            
            # Obtener el elemento y su padre
            element = self._find_element_by_id(structure_tree, element_id)
            parent = self._find_parent_element(structure_tree, element_id)
            
            if not element or not parent:
                continue
                
            # Calcular posición actual en los hijos del padre
            siblings = parent.get("children", [])
            current_index = next((i for i, sibling in enumerate(siblings) 
                                if self._get_element_id(sibling) == element_id), -1)
            
            if current_index == -1:
                continue
                
            # Determinar nueva posición basada en orden visual
            # Limitado por el número de hermanos
            new_index = min(expected_position, len(siblings) - 1)
            
            # Evitar cambios muy drásticos en una sola operación
            max_shift = 3
            if abs(new_index - current_index) > max_shift:
                new_index = current_index + (max_shift if new_index > current_index else -max_shift)
            
            # Aplicar movimiento
            if new_index != current_index and 0 <= new_index < len(siblings):
                self._move_element(parent, current_index, new_index)
                changes_made = True
                logger.debug(f"Elemento movido de posición {current_index} a {new_index}")
        
        return changes_made
    
    def _apply_full_reordering_strategy(self, structure_tree: Dict) -> bool:
        """
        Estrategia de reordenamiento completo del árbol.
        
        Esta es la estrategia más invasiva que reconstruye el orden completo
        basándose en un análisis visual detallado, pero manteniendo las relaciones
        jerárquicas existentes.
        
        Args:
            structure_tree: Árbol estructural del documento
            
        Returns:
            bool: True si se realizaron cambios
        """
        changes_made = False
        
        # Determinar el modo de lectura predominante
        document_lang = self._get_document_language()
        reading_mode = self._determine_reading_mode(document_lang)
        
        # Procesar página por página
        pages_structure = self._extract_structures_by_page(structure_tree)
        
        for page_num, page_elements in pages_structure.items():
            # Crear un mapa de elementos por nivel en el árbol
            elements_by_level = self._group_elements_by_hierarchy_level(page_elements)
            
            # Para cada nivel, reordenar según posición visual
            for level, elements in elements_by_level.items():
                elements_with_positions = self._get_elements_positions(page_num, elements)
                visual_order = self._calculate_visual_order(elements_with_positions, reading_mode)
                
                # Aplicar reordenamiento
                level_changes = self._reorder_elements_in_place(elements, visual_order)
                changes_made = changes_made or level_changes
        
        # Tratamiento especial para elementos que atraviesan múltiples páginas
        multipage_changes = self._handle_multipage_elements(structure_tree)
        changes_made = changes_made or multipage_changes
        
        return changes_made
    
    def _detect_columns_in_page(self, page_num: int) -> List[Dict]:
        """
        Detecta columnas en una página basándose en análisis visual.
        
        Args:
            page_num: Número de página a analizar
            
        Returns:
            List[Dict]: Lista de columnas detectadas con sus coordenadas y elementos
        """
        columns = []
        
        # Obtener elementos de la página con sus posiciones
        page_elements = self._get_page_visual_elements(page_num)
        if not page_elements:
            return columns
            
        # Obtener dimensiones de la página
        page = self.pdf_loader.doc[page_num]
        page_width, page_height = page.rect.width, page.rect.height
        
        # Agrupar elementos por posición X (horizontalmente)
        x_positions = [elem["rect"][0] for elem in page_elements]
        x_positions.extend([elem["rect"][2] for elem in page_elements])
        
        # Usar clustering para detectar columnas
        column_boundaries = self._cluster_positions(x_positions, page_width * self.column_threshold)
        
        if len(column_boundaries) <= 1:
            # No se detectaron múltiples columnas
            return columns
            
        # Procesar columnas detectadas
        for i in range(len(column_boundaries) - 1):
            left = column_boundaries[i]
            right = column_boundaries[i + 1]
            
            # Filtrar elementos que pertenecen a esta columna
            column_elements = []
            for elem in page_elements:
                # Un elemento pertenece a la columna si su centro está dentro de los límites
                center_x = (elem["rect"][0] + elem["rect"][2]) / 2
                if left <= center_x <= right:
                    column_elements.append(elem)
            
            if column_elements:
                columns.append({
                    "index": i,
                    "left": left,
                    "right": right,
                    "elements": column_elements
                })
        
        return columns
    
    def _detect_content_blocks(self, page_num: int) -> List[Dict]:
        """
        Detecta bloques de contenido en una página.
        
        Los bloques son conjuntos de elementos que forman una unidad lógica
        y deben mantenerse juntos en el orden de lectura.
        
        Args:
            page_num: Número de página a analizar
            
        Returns:
            List[Dict]: Lista de bloques con sus elementos y coordenadas
        """
        blocks = []
        
        # Obtener elementos visuales de la página
        page_elements = self._get_page_visual_elements(page_num)
        if not page_elements:
            return blocks
            
        # Obtener dimensiones de la página
        page = self.pdf_loader.doc[page_num]
        page_width, page_height = page.rect.width, page.rect.height
        
        # Agrupar elementos por proximidad vertical y horizontal
        # para formar bloques cohesivos
        assigned_elements = set()
        
        for elem in page_elements:
            if elem["id"] in assigned_elements:
                continue
                
            # Crear un nuevo bloque con este elemento
            block = {
                "elements": [elem],
                "rect": list(elem["rect"]),  # [x0, y0, x1, y1]
                "types": [elem.get("type", "Unknown")]
            }
            assigned_elements.add(elem["id"])
            
            # Expandir bloque con elementos cercanos
            block_expanded = True
            while block_expanded:
                block_expanded = False
                
                for other_elem in page_elements:
                    if other_elem["id"] in assigned_elements:
                        continue
                        
                    # Verificar si hay proximidad con el bloque actual
                    if self._is_element_near_block(other_elem, block, page_width, page_height):
                        block["elements"].append(other_elem)
                        block["types"].append(other_elem.get("type", "Unknown"))
                        assigned_elements.add(other_elem["id"])
                        
                        # Actualizar los límites del bloque
                        block["rect"] = [
                            min(block["rect"][0], other_elem["rect"][0]),
                            min(block["rect"][1], other_elem["rect"][1]),
                            max(block["rect"][2], other_elem["rect"][2]),
                            max(block["rect"][3], other_elem["rect"][3])
                        ]
                        
                        block_expanded = True
            
            blocks.append(block)
        
        # Ordenar bloques según el flujo de lectura (arriba a abajo, izquierda a derecha)
        blocks.sort(key=lambda b: (b["rect"][1], b["rect"][0]))
        
        return blocks
    
    def _reorder_elements_by_columns(self, page_num: int, columns: List[Dict]) -> bool:
        """
        Reordena elementos según la estructura de columnas detectada.
        
        Args:
            page_num: Número de página
            columns: Columnas detectadas con sus elementos
            
        Returns:
            bool: True si se realizaron cambios
        """
        changes_made = False
        
        # Si no hay columnas, no hacer nada
        if not columns:
            return False
            
        # Determinar dirección de lectura de columnas (izquierda a derecha normalmente)
        document_lang = self._get_document_language()
        reading_mode = self._determine_reading_mode(document_lang)
        
        # Ordenar columnas según la dirección de lectura
        if reading_mode.get("primary") == "horizontal_reversed":
            # Para idiomas RTL (derecha a izquierda)
            columns.sort(key=lambda c: c["right"], reverse=True)
        else:
            # Para idiomas LTR (izquierda a derecha)
            columns.sort(key=lambda c: c["left"])
        
        # Procesar cada columna y ordenar elementos dentro de ella
        for column in columns:
            column_elements = column["elements"]
            
            # Ordenar elementos en la columna (arriba a abajo)
            column_elements.sort(key=lambda e: e["rect"][1])
            
            # Reordenar elementos en la estructura del árbol
            for i, elem in enumerate(column_elements):
                element_id = elem["id"]
                structure_elem = self._find_element_by_id(self.pdf_loader.structure_tree, element_id)
                parent = self._find_parent_element(self.pdf_loader.structure_tree, element_id)
                
                if not structure_elem or not parent:
                    continue
                    
                # Determinar posición actual y deseada
                siblings = parent.get("children", [])
                current_index = next((idx for idx, sibling in enumerate(siblings) 
                                    if self._get_element_id(sibling) == element_id), -1)
                
                desired_index = current_index
                
                # Buscar elementos anteriores que deberían estar después
                for j in range(current_index):
                    sibling_id = self._get_element_id(siblings[j])
                    
                    # Si este elemento está en la misma columna pero más abajo
                    # o en una columna posterior, debe ir después
                    for col_idx, col in enumerate(columns):
                        if col["index"] > column["index"]:
                            if sibling_id in [e["id"] for e in col["elements"]]:
                                desired_index = j
                                break
                        elif col["index"] == column["index"]:
                            for col_elem in col["elements"]:
                                if col_elem["id"] == sibling_id and col_elem["rect"][1] > elem["rect"][1]:
                                    desired_index = j
                                    break
                
                # Si se necesita mover el elemento
                if desired_index != current_index:
                    self._move_element(parent, current_index, desired_index)
                    changes_made = True
        
        return changes_made
    
    def _reorder_elements_by_blocks(self, page_num: int, blocks: List[Dict]) -> bool:
        """
        Reordena elementos según bloques de contenido detectados.
        
        Args:
            page_num: Número de página
            blocks: Bloques de contenido detectados
            
        Returns:
            bool: True si se realizaron cambios
        """
        changes_made = False
        
        # Si no hay bloques, no hacer nada
        if not blocks:
            return False
            
        # Determinar dirección de lectura
        document_lang = self._get_document_language()
        reading_mode = self._determine_reading_mode(document_lang)
        
        # Ordenar bloques según el flujo de lectura
        if reading_mode.get("primary") == "vertical":
            # Para idiomas con flujo vertical
            blocks.sort(key=lambda b: (b["rect"][0], b["rect"][1]))
        else:
            # Para idiomas con flujo horizontal
            blocks.sort(key=lambda b: (b["rect"][1], b["rect"][0]))
        
        # Procesar cada bloque
        for block_idx, block in enumerate(blocks):
            block_elements = block["elements"]
            
            # Ordenar elementos dentro del bloque
            if reading_mode.get("primary") == "vertical":
                block_elements.sort(key=lambda e: (e["rect"][0], e["rect"][1]))
            else:
                block_elements.sort(key=lambda e: (e["rect"][1], e["rect"][0]))
            
            # Reordenar elementos en la estructura del árbol
            for elem in block_elements:
                element_id = elem["id"]
                structure_elem = self._find_element_by_id(self.pdf_loader.structure_tree, element_id)
                parent = self._find_parent_element(self.pdf_loader.structure_tree, element_id)
                
                if not structure_elem or not parent:
                    continue
                    
                # Calcular la nueva posición basada en el orden de bloques
                siblings = parent.get("children", [])
                current_index = next((idx for idx, sibling in enumerate(siblings) 
                                    if self._get_element_id(sibling) == element_id), -1)
                
                # Para cada hermano anterior, verificar si pertenece a un bloque posterior
                for j in range(current_index):
                    sibling_id = self._get_element_id(siblings[j])
                    
                    # Encontrar a qué bloque pertenece este hermano
                    sibling_block_idx = -1
                    for idx, b in enumerate(blocks):
                        if sibling_id in [e["id"] for e in b["elements"]]:
                            sibling_block_idx = idx
                            break
                    
                    # Si el hermano está en un bloque que debería ir después, mover este elemento
                    if sibling_block_idx > block_idx:
                        # Mover el elemento actual antes de este hermano
                        self._move_element(parent, current_index, j)
                        changes_made = True
                        # Actualizar índice después de mover
                        current_index = j
                        break
        
        return changes_made
    
    def _get_page_visual_elements(self, page_num: int) -> List[Dict]:
        """
        Obtiene elementos visuales de una página con sus posiciones.
        
        Args:
            page_num: Número de página
            
        Returns:
            List[Dict]: Lista de elementos con ID, tipo, rectángulo y posición
        """
        visual_elements = []
        
        # Obtener elementos estructurales de la página
        page_elements = self._get_elements_by_page(self.pdf_loader.structure_tree, page_num)
        
        # Obtener posiciones visuales
        for element in page_elements:
            element_id = self._get_element_id(element)
            if not element_id:
                continue
                
            # Obtener rectángulo del elemento (coordenadas visuales)
            rect = self._get_element_rect(element, page_num)
            if not rect:
                continue
                
            visual_elements.append({
                "id": element_id,
                "type": element.get("type", "Unknown"),
                "rect": rect,  # [x0, y0, x1, y1]
                "text": element.get("text", "")
            })
        
        return visual_elements
    
    def _get_element_rect(self, element: Dict, page_num: int) -> List[float]:
        """
        Obtiene el rectángulo que contiene un elemento en una página.
        
        Args:
            element: Elemento estructural
            page_num: Número de página
            
        Returns:
            List[float]: Coordenadas [x0, y0, x1, y1] o None si no se encuentra
        """
        # Si el elemento ya tiene rect, devolverlo
        if "rect" in element:
            return element["rect"]
            
        # Intentar obtener el rectángulo del elemento usando PyMuPDF
        if "element" in element and hasattr(self.pdf_loader, "doc"):
            try:
                # Intentar extraer mcid (Marked Content ID)
                mcid = -1
                if "mcid" in element:
                    mcid = element["mcid"]
                elif "element" in element:
                    pikepdf_element = element["element"]
                    if hasattr(pikepdf_element, "K") and isinstance(pikepdf_element.K, int):
                        mcid = pikepdf_element.K
                
                # Si tenemos mcid, buscar el contenido marcado en la página
                if mcid >= 0 and page_num < self.pdf_loader.doc.page_count:
                    page = self.pdf_loader.doc[page_num]
                    
                    # Buscar en bloques de texto
                    blocks = page.get_text("dict")["blocks"]
                    for block in blocks:
                        for line in block.get("lines", []):
                            for span in line.get("spans", []):
                                if span.get("mcid") == mcid:
                                    return [span["bbox"][0], span["bbox"][1], 
                                            span["bbox"][2], span["bbox"][3]]
            except Exception as e:
                logger.debug(f"Error al obtener rectángulo para elemento: {e}")
        
        # Si no se pudo obtener por mcid, intentar determinar por los hijos
        child_rects = []
        for child in element.get("children", []):
            child_rect = self._get_element_rect(child, page_num)
            if child_rect:
                child_rects.append(child_rect)
        
        if child_rects:
            # Combinar rectángulos de hijos
            x0 = min(rect[0] for rect in child_rects)
            y0 = min(rect[1] for rect in child_rects)
            x1 = max(rect[2] for rect in child_rects)
            y1 = max(rect[3] for rect in child_rects)
            return [x0, y0, x1, y1]
        
        return None
    
    def _get_elements_by_page(self, structure_tree: Dict, page_num: int) -> List[Dict]:
        """
        Extrae elementos estructurales que pertenecen a una página específica.
        
        Args:
            structure_tree: Árbol estructural del documento
            page_num: Número de página
            
        Returns:
            List[Dict]: Lista de elementos en la página
        """
        page_elements = []
        
        def collect_elements(node):
            if isinstance(node, dict):
                # Verificar si el nodo pertenece a esta página
                node_page = node.get("page")
                if node_page == page_num:
                    page_elements.append(node)
                
                # Procesar hijos
                for child in node.get("children", []):
                    collect_elements(child)
            elif isinstance(node, list):
                for item in node:
                    collect_elements(item)
        
        collect_elements(structure_tree)
        return page_elements
    
    def _get_elements_positions(self, page_num: int, elements: List[Dict]) -> List[Dict]:
        """
        Obtiene las posiciones visuales de elementos en una página.
        
        Args:
            page_num: Número de página
            elements: Lista de elementos a analizar
            
        Returns:
            List[Dict]: Elementos con sus posiciones visuales
        """
        elements_with_positions = []
        
        for element in elements:
            element_id = self._get_element_id(element)
            if not element_id:
                continue
                
            # Obtener rectángulo del elemento
            rect = self._get_element_rect(element, page_num)
            if not rect:
                continue
                
            elements_with_positions.append({
                "id": element_id,
                "element": element,
                "rect": rect,
                "center_x": (rect[0] + rect[2]) / 2,
                "center_y": (rect[1] + rect[3]) / 2
            })
        
        return elements_with_positions
    
    def _calculate_visual_order(self, elements_with_positions: List[Dict], reading_mode: Dict) -> List:
        """
        Calcula el orden visual de los elementos según la dirección de lectura.
        
        Args:
            elements_with_positions: Lista de elementos con posiciones
            reading_mode: Diccionario con dirección primaria y secundaria
            
        Returns:
            List: IDs de elementos en orden visual
        """
        if not elements_with_positions:
            return []
            
        # Ordenar elementos según la dirección de lectura
        primary = reading_mode.get("primary", "horizontal")
        secondary = reading_mode.get("secondary", "vertical")
        
        # Definir funciones de ordenamiento según dirección
        sort_funcs = {
            "horizontal": lambda e: e["center_x"],
            "horizontal_reversed": lambda e: -e["center_x"],
            "vertical": lambda e: e["center_y"],
            "vertical_reversed": lambda e: -e["center_y"]
        }
        
        # Agrupar elementos por líneas o columnas según dirección primaria
        if primary in ["horizontal", "horizontal_reversed"]:
            # Agrupar por líneas (elementos con Y similar)
            lines = self._group_elements_by_axis(elements_with_positions, "y")
            
            # Ordenar elementos dentro de cada línea
            for line in lines:
                line.sort(key=sort_funcs[primary])
            
            # Ordenar líneas
            lines.sort(key=lambda line: sort_funcs[secondary](line[0]))
        else:
            # Agrupar por columnas (elementos con X similar)
            columns = self._group_elements_by_axis(elements_with_positions, "x")
            
            # Ordenar elementos dentro de cada columna
            for column in columns:
                column.sort(key=sort_funcs[primary])
            
            # Ordenar columnas
            columns.sort(key=lambda column: sort_funcs[secondary](column[0]))
            
            # Asignar líneas para compatibilidad con el código siguiente
            lines = columns
        
        # Formar orden final
        visual_order = []
        for line in lines:
            for element in line:
                visual_order.append(element["id"])
        
        return visual_order
    
    def _group_elements_by_axis(self, elements: List[Dict], axis: str) -> List[List[Dict]]:
        """
        Agrupa elementos por su posición en un eje (x o y).
        
        Args:
            elements: Lista de elementos con posiciones
            axis: Eje de agrupación ('x' o 'y')
            
        Returns:
            List[List[Dict]]: Grupos de elementos en líneas o columnas
        """
        if not elements:
            return []
            
        # Determinar la clave y tolerancia para agrupación
        if axis == "y":
            center_key = "center_y"
            extent_keys = ("rect", 1, 3)  # y0, y1
        else:
            center_key = "center_x"
            extent_keys = ("rect", 0, 2)  # x0, x1
        
        # Calcular un valor de tolerancia adaptativo
        positions = [e[center_key] for e in elements]
        min_pos, max_pos = min(positions), max(positions)
        range_size = max_pos - min_pos
        
        # Ajustar tolerancia según el rango
        if range_size > 0:
            # Usar percentil para adaptarse al documento
            positions.sort()
            gaps = [positions[i+1] - positions[i] for i in range(len(positions)-1)]
            if gaps:
                # Usar la mediana de las diferencias como guía
                gaps.sort()
                median_gap = gaps[len(gaps)//2]
                tolerance = max(median_gap * 1.5, range_size * 0.02)
            else:
                tolerance = range_size * 0.05
        else:
            tolerance = 5  # Valor predeterminado en unidades del PDF
        
        # Ordenar elementos por la coordenada del eje
        sorted_elements = sorted(elements, key=lambda e: e[center_key])
        
        # Agrupar elementos
        groups = []
        current_group = [sorted_elements[0]]
        current_max = sorted_elements[0][extent_keys[0]][extent_keys[2]]
        current_min = sorted_elements[0][extent_keys[0]][extent_keys[1]]
        
        for elem in sorted_elements[1:]:
            # Verificar si hay superposición o está dentro de la tolerancia
            elem_max = elem[extent_keys[0]][extent_keys[2]]
            elem_min = elem[extent_keys[0]][extent_keys[1]]
            
            # Si hay superposición o está muy cerca, incluir en el grupo actual
            if (elem_min <= current_max + tolerance and elem_max >= current_min - tolerance) or \
               (abs(elem[center_key] - current_group[-1][center_key]) <= tolerance):
                current_group.append(elem)
                current_max = max(current_max, elem_max)
                current_min = min(current_min, elem_min)
            else:
                # Crear un nuevo grupo
                groups.append(current_group)
                current_group = [elem]
                current_max = elem_max
                current_min = elem_min
        
        # Añadir el último grupo
        if current_group:
            groups.append(current_group)
        
        return groups
    
    def _move_element(self, parent: Dict, from_index: int, to_index: int) -> None:
        """
        Mueve un elemento de una posición a otra dentro del mismo padre.
        
        Args:
            parent: Elemento padre
            from_index: Índice actual
            to_index: Índice destino
        """
        if "children" not in parent or from_index == to_index or \
           from_index < 0 or to_index < 0 or \
           from_index >= len(parent["children"]) or to_index >= len(parent["children"]):
            return
            
        # Aplicar el movimiento en la estructura interna
        element = parent["children"].pop(from_index)
        parent["children"].insert(to_index, element)
        
        # Registrar cambio en el PDFWriter si está disponible
        if self.pdf_writer:
            element_id = self._get_element_id(element)
            parent_id = self._get_element_id(parent)
            
            if element_id and parent_id:
                # Registrar movimiento para que sea aplicado al guardar
                # Aunque el elemento no se mueve a un padre diferente, el writer necesita
                # la información para actualizar el documento PDF
                self.pdf_writer.move_tag(element_id, parent_id, to_index)
    
    def _is_element_near_block(self, element: Dict, block: Dict, page_width: float, page_height: float) -> bool:
        """
        Verifica si un elemento está cerca de un bloque.
        
        Args:
            element: Elemento a verificar
            block: Bloque con coordenadas
            page_width: Ancho de la página
            page_height: Altura de la página
            
        Returns:
            bool: True si el elemento está cerca del bloque
        """
        # Calcular umbrales de proximidad adaptativos
        h_threshold = page_width * 0.05  # 5% del ancho de la página
        v_threshold = page_height * 0.02  # 2% de la altura de la página
        
        # Extraer coordenadas
        e_rect = element["rect"]
        b_rect = block["rect"]
        
        # Verificar solapamiento horizontal
        h_overlap = not (e_rect[2] < b_rect[0] or e_rect[0] > b_rect[2])
        
        # Verificar proximidad vertical
        v_close = abs(e_rect[1] - b_rect[3]) < v_threshold or abs(e_rect[3] - b_rect[1]) < v_threshold
        
        # Verificar proximidad horizontal
        h_close = abs(e_rect[0] - b_rect[2]) < h_threshold or abs(e_rect[2] - b_rect[0]) < h_threshold
        
        # Un elemento está cerca de un bloque si hay solapamiento horizontal y está cerca verticalmente,
        # o si hay solapamiento vertical y está cerca horizontalmente
        v_overlap = not (e_rect[3] < b_rect[1] or e_rect[1] > b_rect[3])
        
        return (h_overlap and v_close) or (v_overlap and h_close)
    
    def _is_column_order_issue(self, elements_with_positions: List[Dict], element_id: str, expected_position: int) -> bool:
        """
        Determina si un problema de orden es debido a columnas.
        
        Args:
            elements_with_positions: Lista de elementos con posiciones
            element_id: ID del elemento con problema
            expected_position: Posición esperada
            
        Returns:
            bool: True si es un problema de orden de columnas
        """
        # Encontrar el elemento y el elemento en la posición esperada
        current_element = next((e for e in elements_with_positions if e["id"] == element_id), None)
        expected_element = elements_with_positions[expected_position] if 0 <= expected_position < len(elements_with_positions) else None
        
        if not current_element or not expected_element:
            return False
            
        # Calcular centros
        current_center_x = current_element["center_x"]
        expected_center_x = expected_element["center_x"]
        
        # Si los centros X difieren significativamente, probablemente es un problema de columnas
        page_width = max(e["rect"][2] for e in elements_with_positions) - min(e["rect"][0] for e in elements_with_positions)
        x_threshold = page_width * 0.2  # 20% del ancho de la página como umbral
        
        return abs(current_center_x - expected_center_x) > x_threshold
    
    def _detect_table_reading_order_issues(self, structure_tree: Dict) -> List[Dict]:
        """
        Detecta problemas específicos de orden de lectura en tablas.
        
        Args:
            structure_tree: Árbol estructural del documento
            
        Returns:
            List[Dict]: Problemas detectados en tablas
        """
        issues = []
        
        # Encontrar todas las tablas en el documento
        tables = self._find_elements_by_type(structure_tree, "Table")
        
        for table in tables:
            table_id = self._get_element_id(table)
            page_num = table.get("page", 0)
            
            # Verificar orden de filas (TR)
            rows = [child for child in table.get("children", []) if child.get("type") == "TR"]
            
            # Añadir también las filas que están en THead, TBody, TFoot
            for section in [child for child in table.get("children", []) 
                           if child.get("type") in ["THead", "TBody", "TFoot"]]:
                section_rows = [child for child in section.get("children", []) if child.get("type") == "TR"]
                # Guardar referencia a la sección para cada fila
                for row in section_rows:
                    row["section"] = section.get("type")
                rows.extend(section_rows)
            
            # Si no hay filas, continuar con la siguiente tabla
            if not rows:
                continue
                
            # Ordenar filas por posición vertical
            rows_with_positions = []
            for row in rows:
                row_rect = self._get_element_rect(row, page_num)
                if row_rect:
                    rows_with_positions.append({
                        "row": row,
                        "rect": row_rect,
                        "center_y": (row_rect[1] + row_rect[3]) / 2
                    })
            
            # Ordenar por posición vertical
            rows_with_positions.sort(key=lambda r: r["center_y"])
            
            # Verificar si el orden actual coincide con el orden visual
            expected_order = [r["row"] for r in rows_with_positions]
            
            # Si las filas están en secciones, respetar el orden de las secciones
            section_order = {"THead": 0, "TBody": 1, "TFoot": 2}
            has_sections = any("section" in row for row in rows)
            
            if has_sections:
                # Agrupar por secciones
                section_rows = defaultdict(list)
                for row_data in rows_with_positions:
                    row = row_data["row"]
                    section = row.get("section", "TBody")  # Default a TBody si no está en una sección
                    section_rows[section].append(row_data)
                
                # Recrear orden esperado respetando secciones
                expected_order = []
                for section in sorted(section_rows.keys(), key=lambda s: section_order.get(s, 1)):
                    # Ordenar dentro de cada sección
                    section_rows[section].sort(key=lambda r: r["center_y"])
                    expected_order.extend([r["row"] for r in section_rows[section]])
            
            # Comparar con orden actual
            current_order = rows
            
            # Detectar filas fuera de orden
            for i, expected_row in enumerate(expected_order):
                current_idx = next((idx for idx, row in enumerate(current_order) 
                                   if row == expected_row), -1)
                
                if current_idx != i and current_idx != -1:
                    # Fila fuera de orden
                    row_id = self._get_element_id(expected_row)
                    
                    issues.append({
                        "page": page_num,
                        "element_id": row_id,
                        "parent_id": table_id,
                        "element_type": "TR",
                        "current_position": current_idx,
                        "expected_position": i,
                        "severity": "error",
                        "description": "Fila de tabla fuera del orden lógico de lectura",
                        "issue_type": "table_row_order"
                    })
        
        return issues
    
    def _detect_list_reading_order_issues(self, structure_tree: Dict) -> List[Dict]:
        """
        Detecta problemas específicos de orden de lectura en listas.
        
        Args:
            structure_tree: Árbol estructural del documento
            
        Returns:
            List[Dict]: Problemas detectados en listas
        """
        issues = []
        
        # Encontrar todas las listas en el documento
        lists = self._find_elements_by_type(structure_tree, "L")
        
        for list_elem in lists:
            list_id = self._get_element_id(list_elem)
            page_num = list_elem.get("page", 0)
            
            # Verificar orden de elementos de lista (LI)
            items = [child for child in list_elem.get("children", []) if child.get("type") == "LI"]
            
            # Si no hay elementos o solo hay uno, continuar con la siguiente lista
            if len(items) <= 1:
                continue
                
            # Ordenar elementos por posición vertical
            items_with_positions = []
            for item in items:
                item_rect = self._get_element_rect(item, page_num)
                if item_rect:
                    items_with_positions.append({
                        "item": item,
                        "rect": item_rect,
                        "center_y": (item_rect[1] + item_rect[3]) / 2
                    })
            
            # Ordenar por posición vertical
            items_with_positions.sort(key=lambda i: i["center_y"])
            
            # Verificar si el orden actual coincide con el orden visual
            expected_order = [i["item"] for i in items_with_positions]
            current_order = items
            
            # Detectar elementos fuera de orden
            for i, expected_item in enumerate(expected_order):
                current_idx = next((idx for idx, item in enumerate(current_order) 
                                   if item == expected_item), -1)
                
                if current_idx != i and current_idx != -1:
                    # Elemento de lista fuera de orden
                    item_id = self._get_element_id(expected_item)
                    
                    issues.append({
                        "page": page_num,
                        "element_id": item_id,
                        "parent_id": list_id,
                        "element_type": "LI",
                        "current_position": current_idx,
                        "expected_position": i,
                        "severity": "error",
                        "description": "Elemento de lista fuera del orden lógico de lectura",
                        "issue_type": "list_item_order"
                    })
        
        return issues
    
    def _detect_multi_column_issues(self, structure_tree: Dict) -> List[Dict]:
        """
        Detecta problemas de orden de lectura en secciones con múltiples columnas.
        
        Args:
            structure_tree: Árbol estructural del documento
            
        Returns:
            List[Dict]: Problemas detectados en secciones con columnas
        """
        issues = []
        
        # Procesar página por página
        pages_structure = self._extract_structures_by_page(structure_tree)
        
        for page_num, page_elements in pages_structure.items():
            # Detectar columnas en la página
            columns = self._detect_columns_in_page(page_num)
            
            if len(columns) <= 1:
                # No hay múltiples columnas en esta página
                continue
                
            # Verificar orden de elementos entre columnas
            for i, column in enumerate(columns[:-1]):
                next_column = columns[i + 1]
                
                # Obtener elementos de ambas columnas
                column_elements = column["elements"]
                next_column_elements = next_column["elements"]
                
                # Verificar si hay elementos de la siguiente columna que aparecen
                # antes que elementos de la columna actual en el árbol estructural
                for elem1 in column_elements:
                    elem1_id = elem1["id"]
                    parent1 = self._find_parent_element(structure_tree, elem1_id)
                    
                    if not parent1:
                        continue
                        
                    siblings = parent1.get("children", [])
                    elem1_idx = next((idx for idx, sibling in enumerate(siblings) 
                                     if self._get_element_id(sibling) == elem1_id), -1)
                    
                    if elem1_idx == -1:
                        continue
                        
                    for elem2 in next_column_elements:
                        elem2_id = elem2["id"]
                        parent2 = self._find_parent_element(structure_tree, elem2_id)
                        
                        if parent1 != parent2:
                            # No comparar elementos con diferentes padres
                            continue
                            
                        elem2_idx = next((idx for idx, sibling in enumerate(siblings) 
                                         if self._get_element_id(sibling) == elem2_id), -1)
                        
                        if elem2_idx != -1 and elem2_idx < elem1_idx:
                            # Elemento de la siguiente columna aparece antes
                            issues.append({
                                "page": page_num,
                                "element_id": elem2_id,
                                "parent_id": self._get_element_id(parent2),
                                "element_type": elem2.get("type", "Unknown"),
                                "current_position": elem2_idx,
                                "expected_position": elem1_idx + 1,
                                "severity": "error",
                                "description": "Elemento de columna posterior aparece antes en el orden de lectura",
                                "issue_type": "column_order"
                            })
        
        return issues
    
    def _extract_structures_by_page(self, structure_tree: Dict) -> Dict[int, List[Dict]]:
        """
        Extrae estructuras organizadas por número de página.
        
        Args:
            structure_tree: Árbol estructural del documento
            
        Returns:
            Dict[int, List[Dict]]: Elementos agrupados por página
        """
        result = defaultdict(list)
        
        def process_node(node):
            if isinstance(node, dict):
                page = node.get("page")
                if page is not None:
                    result[page].append(node)
                
                # Procesar hijos
                for child in node.get("children", []):
                    process_node(child)
            elif isinstance(node, list):
                for item in node:
                    process_node(item)
        
        process_node(structure_tree)
        return result
    
    def _find_elements_by_type(self, structure_tree: Dict, element_type: str) -> List[Dict]:
        """
        Encuentra todos los elementos de un tipo específico en el árbol.
        
        Args:
            structure_tree: Árbol estructural del documento
            element_type: Tipo de elemento a buscar
            
        Returns:
            List[Dict]: Elementos del tipo especificado
        """
        elements = []
        
        def find_elements(node):
            if isinstance(node, dict):
                if node.get("type") == element_type:
                    elements.append(node)
                
                # Procesar hijos
                for child in node.get("children", []):
                    find_elements(child)
            elif isinstance(node, list):
                for item in node:
                    find_elements(item)
        
        find_elements(structure_tree)
        return elements
    
    def _find_element_by_id(self, structure_tree: Dict, element_id: str) -> Dict:
        """
        Busca un elemento por su ID en el árbol estructural.
        
        Args:
            structure_tree: Árbol estructural del documento
            element_id: ID del elemento a buscar
            
        Returns:
            Dict: Elemento encontrado o None
        """
        if not structure_tree or not element_id:
            return None
            
        # Si el árbol tiene un índice por ID, usarlo directamente
        if hasattr(self.pdf_loader, "structure_elements_by_id") and element_id in self.pdf_loader.structure_elements_by_id:
            return self.pdf_loader.structure_elements_by_id[element_id]
        
        # Búsqueda recursiva
        result = [None]  # Usar lista para permitir modificación desde la función anidada
        
        def search_element(node):
            if isinstance(node, dict):
                current_id = self._get_element_id(node)
                if current_id == element_id:
                    result[0] = node
                    return True
                
                # Procesar hijos
                for child in node.get("children", []):
                    if search_element(child):
                        return True
            elif isinstance(node, list):
                for item in node:
                    if search_element(item):
                        return True
            
            return False
        
        search_element(structure_tree)
        return result[0]
    
    def _find_parent_element(self, structure_tree: Dict, element_id: str) -> Dict:
        """
        Busca el elemento padre de un elemento dado por su ID.
        
        Args:
            structure_tree: Árbol estructural del documento
            element_id: ID del elemento hijo
            
        Returns:
            Dict: Elemento padre o None
        """
        if not structure_tree or not element_id:
            return None
        
        result = [None]  # Usar lista para permitir modificación desde la función anidada
        
        def search_parent(node):
            if isinstance(node, dict) and "children" in node:
                for child in node["children"]:
                    if isinstance(child, dict):
                        child_id = self._get_element_id(child)
                        if child_id == element_id:
                            result[0] = node
                            return True
                    
                    # Buscar en niveles más profundos
                    if search_parent(child):
                        return True
            elif isinstance(node, list):
                for item in node:
                    if search_parent(item):
                        return True
            
            return False
        
        search_parent(structure_tree)
        return result[0]
    
    def _get_element_id(self, element: Dict) -> str:
        """
        Obtiene el ID de un elemento estructural.
        
        Args:
            element: Elemento estructural
            
        Returns:
            str: ID del elemento o None
        """
        if not element or not isinstance(element, dict):
            return None
        
        # Si el elemento tiene un ID explícito, usarlo
        if "id" in element:
            return element["id"]
        
        # En caso contrario, usar el ID del objeto pikepdf
        if "element" in element:
            return str(id(element["element"]))
        
        return None
    
    def _get_document_language(self) -> str:
        """
        Determina el idioma predominante del documento.
        
        Returns:
            str: Código de idioma o 'en' por defecto
        """
        default_lang = "en"
        
        if not self.pdf_loader:
            return default_lang
            
        # Intentar obtener del catálogo del PDF
        metadata = {}
        if hasattr(self.pdf_loader, "get_metadata"):
            metadata = self.pdf_loader.get_metadata()
        
        # Verificar idioma en el documento
        lang = metadata.get("language", "")
        if lang:
            return lang
            
        # Si no hay idioma explícito, intentar inferir
        # Esto es una simplificación; un enfoque más robusto analizaría el contenido
        title = metadata.get("title", "")
        if title:
            # Detectar idiomas comunes por palabras clave
            if any(word in title.lower() for word in ["der", "die", "das", "und"]):
                return "de"
            if any(word in title.lower() for word in ["el", "la", "los", "las", "de", "del"]):
                return "es"
            if any(word in title.lower() for word in ["le", "la", "les", "des", "du"]):
                return "fr"
        
        # Por defecto, asumir inglés
        return default_lang
    
    def _determine_reading_mode(self, language_code: str) -> Dict:
        """
        Determina el modo de lectura basado en el idioma.
        
        Args:
            language_code: Código de idioma
            
        Returns:
            Dict: Dirección primaria y secundaria de lectura
        """
        # Extraer código base (sin región)
        base_lang = language_code.split('-')[0].lower() if '-' in language_code else language_code.lower()
        
        # Idiomas RTL (derecha a izquierda)
        rtl_languages = ["ar", "he", "fa", "ur", "yi", "dv", "ha", "ps", "ug"]
        
        # Idiomas verticales tradicionales
        vertical_languages = ["zh", "ja", "ko"]
        
        # Determinar modo según idioma
        if base_lang in rtl_languages:
            return self.reading_directions["rl-tb"]
        elif base_lang in vertical_languages:
            # Por defecto usar tb-rl, pero podría ser tb-lr en algunos casos modernos
            if language_code.lower() in ["ja-jp", "ko-kr"]:
                return self.reading_directions["tb-lr"]
            return self.reading_directions["tb-rl"]
        else:
            # Por defecto usar LTR (izquierda a derecha)
            return self.reading_directions["lr-tb"]
    
    def _group_elements_by_hierarchy_level(self, elements: List[Dict]) -> Dict[int, List[Dict]]:
        """
        Agrupa elementos por su nivel en la jerarquía del árbol.
        
        Args:
            elements: Lista de elementos a agrupar
            
        Returns:
            Dict[int, List[Dict]]: Elementos agrupados por nivel
        """
        elements_by_level = defaultdict(list)
        
        def calculate_level(node, current_level=0):
            if isinstance(node, dict) and "children" in node:
                for child in node["children"]:
                    # Asignar nivel al hijo
                    if isinstance(child, dict):
                        child["_level"] = current_level + 1
                        elements_by_level[current_level + 1].append(child)
                    
                    # Procesar niveles más profundos
                    calculate_level(child, current_level + 1)
        
        # Asumimos que structure_tree es el nodo raíz (nivel 0)
        if hasattr(self.pdf_loader, "structure_tree") and self.pdf_loader.structure_tree:
            self.pdf_loader.structure_tree["_level"] = 0
            elements_by_level[0].append(self.pdf_loader.structure_tree)
            calculate_level(self.pdf_loader.structure_tree)
        
        return elements_by_level
    
    def _reorder_elements_in_place(self, elements: List[Dict], visual_order: List[str]) -> bool:
        """
        Reordena elementos según un orden visual calculado.
        
        Args:
            elements: Lista de elementos a reordenar
            visual_order: IDs de elementos en orden visual deseado
            
        Returns:
            bool: True si se realizaron cambios
        """
        changes_made = False
        
        if not elements or not visual_order:
            return changes_made
            
        # Crear un mapa de elementos por ID
        elements_by_id = {self._get_element_id(elem): elem for elem in elements if self._get_element_id(elem)}
        
        # Filtrar solo los IDs que existen en nuestros elementos
        valid_order = [elem_id for elem_id in visual_order if elem_id in elements_by_id]
        
        # Si no hay suficientes elementos para reordenar, salir
        if len(valid_order) <= 1:
            return changes_made
            
        # Reordenar los elementos
        for i, elem_id in enumerate(valid_order):
            element = elements_by_id[elem_id]
            parent = self._find_parent_element(self.pdf_loader.structure_tree, elem_id)
            
            if not parent:
                continue
                
            # Determinar índice actual y deseado
            siblings = parent.get("children", [])
            current_index = next((idx for idx, sibling in enumerate(siblings) 
                                if self._get_element_id(sibling) == elem_id), -1)
            
            # Calcular el índice deseado
            # (más complejo en la realidad, simplificado aquí)
            target_index = current_index
            
            # Reordenar solo si hay hermanos anteriores que deberían ir después
            for j in range(current_index):
                sibling_id = self._get_element_id(siblings[j])
                if sibling_id in valid_order and valid_order.index(sibling_id) > i:
                    # Este hermano debería ir después del elemento actual
                    target_index = min(target_index, j)
            
            # Si se necesita mover
            if target_index != current_index:
                self._move_element(parent, current_index, target_index)
                changes_made = True
        
        return changes_made
    
    def _handle_multipage_elements(self, structure_tree: Dict) -> bool:
        """
        Corrige el orden de elementos que atraviesan múltiples páginas.
        
        Args:
            structure_tree: Árbol estructural del documento
            
        Returns:
            bool: True si se realizaron cambios
        """
        changes_made = False
        
        # Identificar elementos que aparecen en múltiples páginas
        multipage_elements = defaultdict(dict)
        
        def find_multipage_elements(node, parent=None, path=None):
            if path is None:
                path = []
                
            if isinstance(node, dict):
                node_id = self._get_element_id(node)
                node_type = node.get("type", "")
                page = node.get("page")
                
                if node_id and page is not None:
                    # Registrar este elemento con su página
                    if node_id in multipage_elements:
                        # Elemento ya visto en otra página
                        if page not in multipage_elements[node_id]["pages"]:
                            multipage_elements[node_id]["pages"].append(page)
                    else:
                        multipage_elements[node_id] = {
                            "element": node,
                            "type": node_type,
                            "pages": [page],
                            "parent": parent,
                            "path": path.copy()
                        }
                
                # Procesar hijos
                for i, child in enumerate(node.get("children", [])):
                    child_path = path + [i]
                    find_multipage_elements(child, node, child_path)
            elif isinstance(node, list):
                for i, item in enumerate(node):
                    item_path = path + [i]
                    find_multipage_elements(item, parent, item_path)
        
        find_multipage_elements(structure_tree)
        
        # Filtrar elementos que realmente atraviesan páginas
        multipage_elements = {k: v for k, v in multipage_elements.items() if len(v["pages"]) > 1}
        
        # No hay elementos que atraviesen páginas
        if not multipage_elements:
            return changes_made
            
        # Reordenar elementos para mantener cohesión
        for elem_id, info in multipage_elements.items():
            element = info["element"]
            parent = info["parent"]
            
            if not parent or "children" not in parent:
                continue
                
            # Encontrar fragmentos del elemento en diferentes páginas
            fragments = []
            for page in info["pages"]:
                page_elements = self._get_elements_by_page(structure_tree, page)
                for page_elem in page_elements:
                    if self._get_element_id(page_elem) == elem_id:
                        fragments.append(page_elem)
            
            # Si no hay múltiples fragmentos, continuar
            if len(fragments) <= 1:
                continue
                
            # Ordenar fragmentos por página
            fragments.sort(key=lambda f: f.get("page", 0))
            
            # Verificar si los fragmentos están en orden correcto
            siblings = parent.get("children", [])
            fragment_indices = [next((i for i, sibling in enumerate(siblings) 
                                     if self._get_element_id(sibling) == self._get_element_id(f)), -1) 
                               for f in fragments]
            
            # Verificar si los índices están en orden ascendente
            is_ordered = all(fragment_indices[i] < fragment_indices[i+1] 
                            for i in range(len(fragment_indices)-1))
            
            if not is_ordered:
                # Reordenar fragmentos
                for i, fragment in enumerate(fragments[:-1]):
                    next_fragment = fragments[i+1]
                    
                    # Asegurar que el siguiente fragmento esté después del actual
                    current_idx = next((idx for idx, sibling in enumerate(siblings) 
                                      if self._get_element_id(sibling) == self._get_element_id(fragment)), -1)
                    next_idx = next((idx for idx, sibling in enumerate(siblings) 
                                    if self._get_element_id(sibling) == self._get_element_id(next_fragment)), -1)
                    
                    if current_idx != -1 and next_idx != -1 and next_idx < current_idx:
                        # Mover el fragmento siguiente después del actual
                        self._move_element(parent, next_idx, current_idx + 1)
                        changes_made = True
                        
                        # Actualizar los índices después del movimiento
                        siblings = parent.get("children", [])
        
        return changes_made
    
    def _cluster_positions(self, positions: List[float], threshold: float) -> List[float]:
        """
        Agrupa posiciones similares mediante clustering.
        
        Args:
            positions: Lista de posiciones a agrupar
            threshold: Umbral para considerar dos posiciones como similares
            
        Returns:
            List[float]: Posiciones representativas de cada grupo
        """
        if not positions:
            return []
            
        # Ordenar posiciones
        sorted_positions = sorted(positions)
        
        # Inicializar clusters
        clusters = [[sorted_positions[0]]]
        
        # Agrupar posiciones similares
        for pos in sorted_positions[1:]:
            if pos - clusters[-1][-1] < threshold:
                # Añadir a cluster existente
                clusters[-1].append(pos)
            else:
                # Crear nuevo cluster
                clusters.append([pos])
        
        # Calcular centros de clusters (o usar el mínimo/máximo de cada cluster)
        # En este caso usamos el valor medio de cada cluster
        cluster_centers = [min(cluster) for cluster in clusters]
        
        return cluster_centers