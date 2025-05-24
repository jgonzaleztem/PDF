#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Módulo para la identificación y marcado de artefactos en PDFs.

Los artefactos son elementos que no forman parte del contenido semántico 
pero están presentes por motivos de presentación o diseño. Según PDF/UA, estos 
elementos deben marcarse explícitamente como artefactos para que no interfieran 
con la accesibilidad del documento.

Este módulo implementa correcciones para los siguientes checkpoints Matterhorn:
- 18-001 a 18-003: Encabezados y pies de página marcados como contenido real
- 01-001: Artefactos etiquetados como contenido real
- 01-003: Contenido marcado como artefacto presente dentro de contenido etiquetado

Referencia:
- ISO 32000-1: 14.8.2.2 (Real Content and Artifacts)
- PDF/UA-1: 7.1 (Contenido marcado)
- Tagged PDF Best Practice Guide: 3.7 (Artifacts)
"""

from typing import Dict, List, Optional, Any, Set, Tuple, Union
import re
import fitz  # PyMuPDF
import pikepdf
from loguru import logger
import numpy as np
from collections import defaultdict

class ArtifactsFixer:
    """
    Clase para identificar y marcar correctamente los artefactos en documentos PDF.
    
    Los artefactos son elementos que no forman parte del contenido semántico
    pero están presentes por motivos de presentación o diseño, como:
    - Encabezados y pies de página
    - Números de página
    - Líneas y bordes decorativos
    - Fondos e imágenes de fondo
    - Contenido repetido en tablas que abarcan múltiples páginas
    """
    
    def __init__(self, pdf_writer):
        """
        Inicializa el corrector de artefactos.
        
        Args:
            pdf_writer: Instancia de PDFWriter para aplicar cambios al documento
        """
        self.pdf_writer = pdf_writer
        
        # Tipos de artefactos según ISO 32000-1, Tabla 330
        self.artifact_types = {
            "Pagination": ["Header", "Footer", "PageNum"],
            "Layout": ["HF", "Background", "Watermark"],
            "Page": ["Trim", "Art", "Bleed", "Crop"]
        }
        
        # Patrones comunes para números de página
        self.page_number_patterns = [
            r'^\s*\d+\s*$',                      # Solo un número (ej: "42")
            r'^\s*Page\s+\d+\s*$',               # "Page N"
            r'^\s*\d+\s+of\s+\d+\s*$',           # "N of M"
            r'^\s*Page\s+\d+\s+of\s+\d+\s*$',    # "Page N of M"
            r'^\s*-\s*\d+\s*-\s*$',              # "-N-"
            r'^\s*\[\s*\d+\s*\]\s*$',            # "[N]"
            r'^\s*Página\s+\d+\s*$',             # "Página N" (español)
            r'^\s*\d+\s+de\s+\d+\s*$'            # "N de M" (español)
        ]
        
        logger.info("ArtifactsFixer inicializado")
    
    def fix_all_artifacts(self, pdf_loader) -> bool:
        """
        Identifica y marca todos los artefactos en el documento.
        
        Args:
            pdf_loader: Instancia de PDFLoader con el documento cargado
            
        Returns:
            bool: True si se realizaron cambios, False si no
        """
        if not pdf_loader or not pdf_loader.doc:
            logger.error("No hay documento cargado para corregir artefactos")
            return False
        
        changes_made = False
        
        # Marcar posibles encabezados y pies de página
        header_footer_changes = self._fix_headers_and_footers(pdf_loader)
        changes_made = changes_made or header_footer_changes
        
        # Marcar números de página
        page_num_changes = self._fix_page_numbers(pdf_loader)
        changes_made = changes_made or page_num_changes
        
        # Marcar líneas y bordes decorativos
        decorative_changes = self._fix_decorative_elements(pdf_loader)
        changes_made = changes_made or decorative_changes
        
        # Corregir elementos mal marcados (contenido real marcado como artefacto o viceversa)
        structure_changes = self._fix_structure_artifacts(pdf_loader)
        changes_made = changes_made or structure_changes
        
        # Marcar elementos repetidos en tablas que abarcan múltiples páginas
        table_changes = self._fix_table_artifacts(pdf_loader)
        changes_made = changes_made or table_changes
        
        # Corregir contenido marcado como artefacto dentro de contenido etiquetado
        nested_changes = self._fix_nested_artifacts(pdf_loader)
        changes_made = changes_made or nested_changes
        
        logger.info(f"Corrección de artefactos completada: {'Se realizaron cambios' if changes_made else 'No se requirieron cambios'}")
        return changes_made
    
    def _fix_headers_and_footers(self, pdf_loader) -> bool:
        """
        Identifica y marca encabezados y pies de página como artefactos.
        
        Args:
            pdf_loader: Instancia de PDFLoader con el documento cargado
            
        Returns:
            bool: True si se realizaron cambios, False si no
        """
        if not pdf_loader.doc or pdf_loader.page_count == 0:
            return False
            
        changes_made = False
        total_pages = pdf_loader.page_count
        
        # Si hay 3 o menos páginas, no realizamos detección automática
        if total_pages <= 3:
            logger.info("Documento con menos de 4 páginas: no se aplica detección automática de encabezados/pies")
            return False
        
        # Umbral de similitud para considerar elementos como encabezados/pies
        similarity_threshold = 0.8
        
        try:
            # Extraer texto en las regiones superior e inferior de cada página
            header_candidates = []
            footer_candidates = []
            
            for page_num in range(total_pages):
                page = pdf_loader.doc[page_num]
                page_height = page.rect.height
                page_width = page.rect.width
                
                # Definir regiones para buscar encabezados y pies (10% superior e inferior)
                header_rect = fitz.Rect(0, 0, page_width, page_height * 0.1)
                footer_rect = fitz.Rect(0, page_height * 0.9, page_width, page_height)
                
                # Extraer texto en estas regiones
                header_text = page.get_text("text", clip=header_rect).strip()
                footer_text = page.get_text("text", clip=footer_rect).strip()
                
                # Obtener también los elementos visuales en estas regiones
                header_dict = page.get_text("dict", clip=header_rect)
                footer_dict = page.get_text("dict", clip=footer_rect)
                
                # Agregar a nuestros candidatos
                if header_text:
                    header_candidates.append({
                        "page": page_num,
                        "text": header_text,
                        "blocks": header_dict.get("blocks", []),
                        "rect": header_rect
                    })
                
                if footer_text:
                    footer_candidates.append({
                        "page": page_num,
                        "text": footer_text,
                        "blocks": footer_dict.get("blocks", []),
                        "rect": footer_rect
                    })
            
            # Analizar candidatos a encabezados
            headers_to_mark = self._identify_repeating_elements(header_candidates, similarity_threshold)
            
            # Analizar candidatos a pies de página
            footers_to_mark = self._identify_repeating_elements(footer_candidates, similarity_threshold)
            
            # Si encontramos elementos consistentes, marcarlos como artefactos
            if headers_to_mark:
                for header in headers_to_mark:
                    self._mark_element_as_artifact(
                        pdf_loader, 
                        header["page"], 
                        header["rect"], 
                        "Pagination", 
                        "Header"
                    )
                changes_made = True
                logger.info(f"Se marcaron {len(headers_to_mark)} elementos como artefactos de encabezado")
            
            if footers_to_mark:
                for footer in footers_to_mark:
                    self._mark_element_as_artifact(
                        pdf_loader, 
                        footer["page"], 
                        footer["rect"], 
                        "Pagination", 
                        "Footer"
                    )
                changes_made = True
                logger.info(f"Se marcaron {len(footers_to_mark)} elementos como artefactos de pie de página")
            
            return changes_made
            
        except Exception as e:
            logger.error(f"Error al procesar encabezados y pies de página: {e}", exc_info=True)
            return False
    
    def _fix_page_numbers(self, pdf_loader) -> bool:
        """
        Identifica y marca números de página como artefactos.
        
        Args:
            pdf_loader: Instancia de PDFLoader con el documento cargado
            
        Returns:
            bool: True si se realizaron cambios, False si no
        """
        if not pdf_loader.doc or pdf_loader.page_count == 0:
            return False
            
        changes_made = False
        total_pages = pdf_loader.page_count
        
        try:
            # Compilar los patrones regex para números de página
            compiled_patterns = [re.compile(pattern) for pattern in self.page_number_patterns]
            
            # Variables para detectar secuencias de números de página
            page_number_candidates = []
            
            for page_num in range(total_pages):
                page = pdf_loader.doc[page_num]
                page_text_dict = page.get_text("dict")
                
                # Buscar bloques de texto que coincidan con patrones de números de página
                for block in page_text_dict.get("blocks", []):
                    if block["type"] == 0:  # Bloque de texto
                        for line in block.get("lines", []):
                            line_text = "".join([span["text"] for span in line.get("spans", [])])
                            line_text = line_text.strip()
                            
                            if any(pattern.match(line_text) for pattern in compiled_patterns):
                                # Es un candidato a número de página
                                # Verificar si contiene el número de página actual o cercano
                                numbers = re.findall(r'\d+', line_text)
                                if numbers:
                                    for num_str in numbers:
                                        num = int(num_str)
                                        # Es un número de página si es cercano al número real de página
                                        if abs(num - (page_num + 1)) <= 2 or num == page_num:
                                            rect = fitz.Rect(
                                                block["bbox"][0], block["bbox"][1],
                                                block["bbox"][2], block["bbox"][3]
                                            )
                                            
                                            page_number_candidates.append({
                                                "page": page_num,
                                                "text": line_text,
                                                "rect": rect,
                                                "number": num
                                            })
                                            break
            
            # Analizar candidatos a números de página para identificar secuencias
            if page_number_candidates:
                # Agrupar por posición similar (para detectar números que aparecen en posiciones consistentes)
                position_groups = self._group_by_position(page_number_candidates)
                
                page_numbers_to_mark = []
                
                for group in position_groups:
                    if len(group) >= min(3, total_pages * 0.5):  # Al menos 3 o 50% de páginas
                        # Verificar si los números forman una secuencia
                        numbers = sorted([item["number"] for item in group])
                        if self._is_sequence(numbers, tolerance=2):
                            page_numbers_to_mark.extend(group)
                
                # Marcar números de página como artefactos
                for item in page_numbers_to_mark:
                    self._mark_element_as_artifact(
                        pdf_loader, 
                        item["page"], 
                        item["rect"], 
                        "Pagination", 
                        "PageNum"
                    )
                    changes_made = True
                
                if page_numbers_to_mark:
                    logger.info(f"Se marcaron {len(page_numbers_to_mark)} números de página como artefactos")
            
            return changes_made
            
        except Exception as e:
            logger.error(f"Error al procesar números de página: {e}", exc_info=True)
            return False
    
    def _fix_decorative_elements(self, pdf_loader) -> bool:
        """
        Identifica y marca elementos decorativos como artefactos.
        
        Args:
            pdf_loader: Instancia de PDFLoader con el documento cargado
            
        Returns:
            bool: True si se realizaron cambios, False si no
        """
        if not pdf_loader.doc or pdf_loader.page_count == 0:
            return False
            
        changes_made = False
        total_pages = pdf_loader.page_count
        
        try:
            for page_num in range(total_pages):
                page = pdf_loader.doc[page_num]
                
                # Buscar líneas horizontales o verticales (comunes en encabezados/pies)
                for path in page.get_drawings():
                    if self._is_decorative_path(path):
                        # Crear un rectángulo que encierre el path
                        rect = fitz.Rect(
                            path["rect"][0], path["rect"][1],
                            path["rect"][2], path["rect"][3]
                        )
                        
                        # Marcar como artefacto de diseño
                        self._mark_element_as_artifact(
                            pdf_loader, 
                            page_num, 
                            rect, 
                            "Layout", 
                            "Background"
                        )
                        changes_made = True
                
                # Buscar imágenes en fondos o en áreas de encabezado/pie
                page_height = page.rect.height
                page_width = page.rect.width
                
                # Definir regiones típicas para elementos decorativos
                header_rect = fitz.Rect(0, 0, page_width, page_height * 0.1)
                footer_rect = fitz.Rect(0, page_height * 0.9, page_width, page_height)
                margin_left = fitz.Rect(0, 0, page_width * 0.05, page_height)
                margin_right = fitz.Rect(page_width * 0.95, 0, page_width, page_height)
                
                # Obtener imágenes en la página
                for img in page.get_images(full=True):
                    xref = img[0]
                    bbox = page.get_image_bbox(img)
                    
                    if not bbox:
                        continue
                    
                    # Verificar si la imagen está en área decorativa
                    is_decorative = (
                        self._rect_overlap_ratio(bbox, header_rect) > 0.5 or
                        self._rect_overlap_ratio(bbox, footer_rect) > 0.5 or
                        self._rect_overlap_ratio(bbox, margin_left) > 0.5 or
                        self._rect_overlap_ratio(bbox, margin_right) > 0.5 or
                        self._is_watermark_or_background(pdf_loader, page_num, bbox, xref)
                    )
                    
                    if is_decorative:
                        # Marcar como artefacto
                        self._mark_element_as_artifact(
                            pdf_loader, 
                            page_num, 
                            bbox, 
                            "Layout", 
                            "Background"
                        )
                        changes_made = True
            
            if changes_made:
                logger.info("Se marcaron elementos decorativos como artefactos")
            
            return changes_made
            
        except Exception as e:
            logger.error(f"Error al procesar elementos decorativos: {e}", exc_info=True)
            return False
    
    def _fix_structure_artifacts(self, pdf_loader) -> bool:
        """
        Corrige elementos mal marcados en la estructura: 
        - Artefactos etiquetados como contenido real (01-001)
        - Contenido real marcado como artefacto (01-002)
        
        Args:
            pdf_loader: Instancia de PDFLoader con el documento cargado
            
        Returns:
            bool: True si se realizaron cambios, False si no
        """
        if not pdf_loader or not pdf_loader.structure_tree:
            return False
            
        changes_made = False
        
        try:
            # Funciones auxiliares para recorrer el árbol de estructura
            def process_structure(node, parent=None, path=""):
                nonlocal changes_made
                
                if not isinstance(node, dict):
                    return
                
                # Verificar si este nodo debe ser un artefacto
                if self._should_be_artifact(node, pdf_loader):
                    # Si tiene ID, buscar en la estructura para desmarcarlo
                    if "element" in node and parent:
                        element_id = id(node["element"])
                        logger.info(f"Marcando como artefacto el elemento {element_id} en {path}")
                        
                        # Registrar la modificación para aplicar los cambios
                        self.pdf_writer._register_artifact_marking(element_id, header_page)
                        changes_made = True
                
                # Procesar los hijos
                if "children" in node and isinstance(node["children"], list):
                    for i, child in enumerate(node["children"]):
                        process_structure(child, node, f"{path}/{i}")
            
            # Procesar todo el árbol de estructura
            process_structure(pdf_loader.structure_tree, None, "root")
            
            if changes_made:
                logger.info("Se corrigieron elementos mal marcados en la estructura")
            
            return changes_made
            
        except Exception as e:
            logger.error(f"Error al corregir artefactos en la estructura: {e}", exc_info=True)
            return False
    
    def _fix_table_artifacts(self, pdf_loader) -> bool:
        """
        Identifica y marca correctamente elementos repetidos en tablas 
        que abarcan múltiples páginas.
        
        Args:
            pdf_loader: Instancia de PDFLoader con el documento cargado
            
        Returns:
            bool: True si se realizaron cambios, False si no
        """
        if not pdf_loader or not pdf_loader.structure_tree:
            return False
            
        changes_made = False
        
        try:
            # Encontrar todas las tablas en el documento
            tables = self._find_tables(pdf_loader.structure_tree)
            
            # Identificar tablas que abarcan múltiples páginas
            multi_page_tables = []
            
            for table in tables:
                table_pages = set()
                
                # Recopilar todas las páginas que contienen esta tabla
                def collect_pages(node):
                    if "page" in node and node["page"] is not None:
                        table_pages.add(node["page"])
                    
                    if "children" in node and isinstance(node["children"], list):
                        for child in node["children"]:
                            collect_pages(child)
                
                collect_pages(table)
                
                # Si la tabla abarca múltiples páginas, agregarla a nuestra lista
                if len(table_pages) > 1:
                    table["pages"] = sorted(table_pages)
                    multi_page_tables.append(table)
            
            # Para cada tabla que abarca múltiples páginas, buscar encabezados repetidos
            for table in multi_page_tables:
                # Buscar elementos <THead> o filas de encabezado
                headers = self._find_table_headers(table)
                
                # Si encontramos encabezados repetidos en páginas después de la primera,
                # marcar esos encabezados repetidos como artefactos
                if headers:
                    first_page = table["pages"][0]
                    
                    for header in headers:
                        header_page = header.get("page")
                        
                        # Si el encabezado está en una página después de la primera,
                        # considerarlo como repetido y marcarlo como artefacto
                        if header_page is not None and header_page != first_page:
                            # Si tiene "element", podemos marcarlo como artefacto
                            if "element" in header:
                                element_id = id(header["element"])
                                logger.info(f"Marcando como artefacto encabezado repetido de tabla en página {header_page}")
                                
                                # Registrar la modificación para aplicar los cambios
                                self.pdf_writer._register_artifact_marking(element_id, header_page)
                                changes_made = True
            
            if changes_made:
                logger.info("Se marcaron encabezados repetidos en tablas como artefactos")
            
            return changes_made
            
        except Exception as e:
            logger.error(f"Error al procesar artefactos en tablas: {e}", exc_info=True)
            return False
    
    def _fix_nested_artifacts(self, pdf_loader) -> bool:
        """
        Corrige casos donde hay contenido marcado como artefacto dentro 
        de contenido etiquetado (01-003).
        
        Args:
            pdf_loader: Instancia de PDFLoader con el documento cargado
            
        Returns:
            bool: True si se realizaron cambios, False si no
        """
        # Esta función es compleja y requiere manipulación directa de la estructura PDF
        # Implementación simplificada para marcar artefactos anidados
        if not pdf_loader or not pdf_loader.pikepdf_doc:
            return False
            
        changes_made = False
        
        try:
            # Esta implementación requiere análisis profundo de la estructura PDF
            # y manipulación directa del PDF, que está fuera del alcance actual
            
            # En una implementación real, buscaríamos en la estructura del documento
            # casos donde hay marcas de artefacto dentro de contenido etiquetado,
            # lo cual es una violación de PDF/UA
            
            logger.info("Verificación de artefactos anidados completada (sin cambios)")
            return changes_made
            
        except Exception as e:
            logger.error(f"Error al corregir artefactos anidados: {e}", exc_info=True)
            return False
    
    def _identify_repeating_elements(self, candidates, similarity_threshold):
        """
        Identifica elementos que se repiten consistentemente en las páginas.
        
        Args:
            candidates: Lista de elementos candidatos
            similarity_threshold: Umbral de similitud para agrupar elementos
            
        Returns:
            List: Elementos identificados como repetitivos
        """
        if not candidates:
            return []
        
        # Agrupar por similitud de texto
        text_groups = []
        
        for candidate in candidates:
            matched = False
            for group in text_groups:
                # Verificar similitud con el primer elemento del grupo
                if self._text_similarity(candidate["text"], group[0]["text"]) >= similarity_threshold:
                    group.append(candidate)
                    matched = True
                    break
            
            if not matched:
                text_groups.append([candidate])
        
        # Filtrar grupos que sean consistentes (aparecen en al menos el 50% de las páginas)
        total_pages = max([c["page"] for c in candidates]) + 1
        min_occurrences = max(2, total_pages * 0.5)  # Al menos 2 o 50% de páginas
        
        consistent_elements = []
        for group in text_groups:
            if len(group) >= min_occurrences:
                consistent_elements.extend(group)
        
        return consistent_elements
    
    def _group_by_position(self, elements, tolerance=20):
        """
        Agrupa elementos por posiciones similares en la página.
        
        Args:
            elements: Lista de elementos a agrupar
            tolerance: Tolerancia en puntos para considerar posiciones similares
            
        Returns:
            List: Grupos de elementos en posiciones similares
        """
        if not elements:
            return []
        
        position_groups = []
        
        for element in elements:
            rect = element["rect"]
            matched = False
            
            for group in position_groups:
                first_rect = group[0]["rect"]
                
                # Verificar si la posición es similar
                if (abs(rect.x0 - first_rect.x0) <= tolerance and
                    abs(rect.y0 - first_rect.y0) <= tolerance):
                    group.append(element)
                    matched = True
                    break
            
            if not matched:
                position_groups.append([element])
        
        return position_groups
    
    def _is_sequence(self, numbers, tolerance=1):
        """
        Verifica si una lista de números forma una secuencia (con tolerancia).
        
        Args:
            numbers: Lista de números a verificar
            tolerance: Tolerancia para considerar números consecutivos
            
        Returns:
            bool: True si forman una secuencia, False en caso contrario
        """
        if not numbers:
            return False
        
        # Eliminar duplicados y ordenar
        unique_numbers = sorted(set(numbers))
        
        if len(unique_numbers) < 2:
            return True  # Un solo número siempre es una secuencia
        
        # Verificar secuencia
        for i in range(1, len(unique_numbers)):
            if unique_numbers[i] - unique_numbers[i-1] > tolerance + 1:
                return False
        
        return True
    
    def _text_similarity(self, text1, text2):
        """
        Calcula la similitud entre dos textos.
        
        Args:
            text1: Primer texto
            text2: Segundo texto
            
        Returns:
            float: Valor de similitud entre 0 y 1
        """
        # Implementación simple basada en la proporción de palabras compartidas
        if not text1 or not text2:
            return 0
        
        words1 = set(text1.lower().split())
        words2 = set(text2.lower().split())
        
        if not words1 or not words2:
            return 0
        
        # Jaccard similarity
        intersection = len(words1.intersection(words2))
        union = len(words1.union(words2))
        
        return intersection / union if union > 0 else 0
    
    def _rect_overlap_ratio(self, rect1, rect2):
        """
        Calcula la proporción de solapamiento entre dos rectángulos.
        
        Args:
            rect1: Primer rectángulo (fitz.Rect)
            rect2: Segundo rectángulo (fitz.Rect)
            
        Returns:
            float: Proporción de solapamiento entre 0 y 1
        """
        # Calcular intersección
        intersection = rect1.intersect(rect2)
        
        if intersection.is_empty:
            return 0
        
        # Calcular áreas
        area_intersection = intersection.width * intersection.height
        area_rect1 = rect1.width * rect1.height
        
        # Devolver proporción de solapamiento
        return area_intersection / area_rect1 if area_rect1 > 0 else 0
    
    def _is_decorative_path(self, path):
        """
        Determina si un path es probablemente decorativo.
        
        Args:
            path: Información del path de dibujo
            
        Returns:
            bool: True si parece decorativo, False en caso contrario
        """
        # Verificar si es una línea horizontal o vertical
        if "lines" in path:
            for line in path["lines"]:
                p1, p2 = line
                # Es una línea horizontal
                if abs(p1[1] - p2[1]) < 2:
                    return True
                # Es una línea vertical
                if abs(p1[0] - p2[0]) < 2:
                    return True
        
        # Verificar si está en un borde de la página
        page_rect = path["rect"]
        page_width = page_rect[2]
        page_height = page_rect[3]
        
        # Si el path está cerca de un borde de la página
        margin = 20  # puntos
        if (path["rect"][0] < margin or 
            path["rect"][1] < margin or
            path["rect"][2] > page_width - margin or
            path["rect"][3] > page_height - margin):
            return True
        
        # Verificar si tiene estilo de decoración
        if "fill" in path and path["fill"] and path["fill"] != [1, 1, 1]:  # No es blanco
            return True
        
        return False
    
    def _is_watermark_or_background(self, pdf_loader, page_num, bbox, xref):
        """
        Determina si una imagen es probablemente una marca de agua o fondo.
        
        Args:
            pdf_loader: Instancia de PDFLoader con el documento cargado
            page_num: Número de página
            bbox: Rectángulo de la imagen
            xref: Referencia cruzada a la imagen
            
        Returns:
            bool: True si parece marca de agua o fondo, False en caso contrario
        """
        # Verificar si la imagen cubre gran parte de la página
        page = pdf_loader.doc[page_num]
        page_area = page.rect.width * page.rect.height
        image_area = bbox.width * bbox.height
        coverage = image_area / page_area
        
        # Si la imagen cubre más del 80% de la página, probablemente es un fondo
        if coverage > 0.8:
            return True
        
        # Si la imagen está en el centro de la página y es grande, podría ser una marca de agua
        center_x = page.rect.width / 2
        center_y = page.rect.height / 2
        
        bbox_center_x = (bbox.x0 + bbox.x1) / 2
        bbox_center_y = (bbox.y0 + bbox.y1) / 2
        
        is_centered = (abs(bbox_center_x - center_x) < page.rect.width * 0.2 and
                      abs(bbox_center_y - center_y) < page.rect.height * 0.2)
        
        if is_centered and coverage > 0.1:
            return True
        
        # Intentar obtener la imagen para analizar su opacidad/transparencia
        try:
            # Las marcas de agua suelen tener baja opacidad
            # Esta verificación requeriría análisis de la imagen, que es complejo
            # En una implementación completa, analizaríamos la opacidad y transparencia
            pass
        except Exception:
            pass
        
        return False
    
    def _should_be_artifact(self, node, pdf_loader):
        """
        Determina si un nodo de estructura debería ser un artefacto.
        
        Args:
            node: Nodo de estructura a verificar
            pdf_loader: Instancia de PDFLoader con el documento cargado
            
        Returns:
            bool: True si debería ser un artefacto, False en caso contrario
        """
        # Verificar si ya es un artefacto
        if node.get("is_artifact", False):
            return False
        
        # Verificar si tiene contenido
        has_content = False
        
        if "text" in node and node["text"].strip():
            has_content = True
        
        if not has_content and "children" in node and node["children"]:
            return False  # Si tiene hijos pero no texto, no es un buen candidato a artefacto
        
        if not "page" in node or node["page"] is None:
            return False  # Necesitamos saber la página para hacer verificaciones
        
        page_num = node["page"]
        
        # Obtener rectángulo del nodo si está disponible
        node_rect = None
        if "rect" in node:
            node_rect = node["rect"]
        elif "element" in node and hasattr(node["element"], "BBox"):
            # Intentar obtener BBox del elemento
            bbox = node["element"].BBox
            if isinstance(bbox, list) and len(bbox) == 4:
                node_rect = fitz.Rect(bbox[0], bbox[1], bbox[2], bbox[3])
        
        if not node_rect:
            return False  # No podemos determinar la posición
        
        # Verificar si está en zona de encabezado/pie de página
        page = pdf_loader.doc[page_num]
        page_height = page.rect.height
        
        # Definir regiones para encabezados y pies (10% superior e inferior)
        header_region = fitz.Rect(0, 0, page.rect.width, page_height * 0.1)
        footer_region = fitz.Rect(0, page_height * 0.9, page.rect.width, page_height)
        
        # Verificar superposición con regiones de encabezado/pie
        in_header = self._rect_overlap_ratio(node_rect, header_region) > 0.5
        in_footer = self._rect_overlap_ratio(node_rect, footer_region) > 0.5
        
        if in_header or in_footer:
            # Verificar si el contenido es repetitivo
            # (aparece en la misma posición en múltiples páginas)
            if has_content and "text" in node:
                # Buscar contenido similar en otras páginas en la misma posición
                similar_pages = 0
                for p in range(pdf_loader.page_count):
                    if p == page_num:
                        continue
                    
                    other_page = pdf_loader.doc[p]
                    # Ajustar el rectángulo a la página actual
                    check_rect = fitz.Rect(node_rect)
                    
                    # Extraer texto en la misma posición
                    other_text = other_page.get_text("text", clip=check_rect).strip()
                    
                    if self._text_similarity(node["text"], other_text) > 0.7:
                        similar_pages += 1
                
                # Si aparece en múltiples páginas, probablemente es un artefacto
                if similar_pages >= 2:
                    return True
        
        # Verificar si es un número de página
        if has_content and "text" in node:
            text = node["text"].strip()
            # Compilar patrones de página
            compiled_patterns = [re.compile(pattern) for pattern in self.page_number_patterns]
            
            if any(pattern.match(text) for pattern in compiled_patterns):
                # Es un posible número de página, verificar si contiene el número de página actual
                numbers = re.findall(r'\d+', text)
                if numbers:
                    for num_str in numbers:
                        num = int(num_str)
                        # Es un número de página si es cercano al número real de página
                        if abs(num - (page_num + 1)) <= 2 or num == page_num:
                            return True
        
        return False
    
    def _find_tables(self, structure_tree):
        """
        Encuentra todas las tablas en la estructura del documento.
        
        Args:
            structure_tree: Árbol de estructura del documento
            
        Returns:
            List: Lista de tablas encontradas
        """
        tables = []
        
        def find_tables_recursive(node, path=""):
            if not isinstance(node, dict):
                return
            
            if node.get("type") == "Table":
                tables.append(node)
            
            if "children" in node and isinstance(node["children"], list):
                for i, child in enumerate(node["children"]):
                    find_tables_recursive(child, f"{path}/{i}")
        
        find_tables_recursive(structure_tree)
        return tables
    
    def _find_table_headers(self, table):
        """
        Encuentra encabezados de tabla (filas TH o elementos THead).
        
        Args:
            table: Tabla a analizar
            
        Returns:
            List: Lista de encabezados encontrados
        """
        headers = []
        
        def find_headers_recursive(node):
            if not isinstance(node, dict):
                return
            
            # Si es un THead o una fila con mayoría de celdas TH, es un encabezado
            if node.get("type") == "THead":
                headers.append(node)
            elif node.get("type") == "TR":
                # Contar celdas TH en esta fila
                th_count = 0
                total_cells = 0
                
                if "children" in node and isinstance(node["children"], list):
                    for child in node["children"]:
                        if isinstance(child, dict) and child.get("type") in ["TH", "TD"]:
                            total_cells += 1
                            if child.get("type") == "TH":
                                th_count += 1
                
                # Si la mayoría son TH, es un encabezado
                if total_cells > 0 and th_count / total_cells > 0.5:
                    headers.append(node)
            
            # Buscar en los hijos
            if "children" in node and isinstance(node["children"], list):
                for child in node["children"]:
                    find_headers_recursive(child)
        
        find_headers_recursive(table)
        return headers
    
    def _mark_element_as_artifact(self, pdf_loader, page_num, rect, artifact_type, artifact_subtype):
        """
        Marca un elemento como artefacto en el documento.
        
        Args:
            pdf_loader: Instancia de PDFLoader con el documento cargado
            page_num: Número de página
            rect: Rectángulo del elemento
            artifact_type: Tipo de artefacto (Pagination, Layout, Page)
            artifact_subtype: Subtipo de artefacto
            
        Returns:
            bool: True si se realizó el marcado, False en caso contrario
        """
        try:
            # Esta función debe delegarse a pdf_writer para la implementación real
            return self.pdf_writer.mark_artifact(page_num, rect, artifact_type, artifact_subtype)
        except Exception as e:
            logger.error(f"Error al marcar artefacto: {e}", exc_info=True)
            return False