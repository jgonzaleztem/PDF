#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Utilidad para análisis geométrico de contenido en documentos PDF.
Proporciona funciones para trabajar con cajas delimitadoras (bounding boxes) de elementos,
analizar relaciones espaciales y ayudar a determinar el orden de lectura lógico.

Relacionado con PDF/UA:
- Ayuda a determinar el orden de lectura lógico (Matterhorn 09-001)
- Facilita la detección de elementos relacionados visualmente para correcta estructura
- Permite inferir relaciones semánticas basadas en la disposición espacial
"""

import numpy as np
from typing import Dict, List, Tuple, Optional, Any, Union, Set
from collections import defaultdict
import fitz  # PyMuPDF
import math
import re
from loguru import logger

class BoundingBoxes:
    """
    Proporciona utilidades para analizar cajas delimitadoras de elementos en documentos PDF.
    
    Esta clase facilita:
    - Extraer y normalizar cajas delimitadoras
    - Determinar relaciones espaciales (solapamiento, contención, alineación)
    - Inferir relaciones semánticas basadas en disposición espacial
    - Ayudar a determinar orden de lectura lógico
    """
    
    def __init__(self, pdf_loader=None):
        """
        Inicializa el analizador con un cargador de PDF opcional.
        
        Args:
            pdf_loader: Instancia opcional de PDFLoader con el documento ya cargado
        """
        self.pdf_loader = pdf_loader
        self.page_cache = {}  # Caché de objetos de página
        self.bbox_cache = {}  # Caché de bounding boxes por elemento
        
        # Constantes para análisis de relaciones espaciales
        self.OVERLAP_THRESHOLD = 0.5  # Umbral para considerar que dos cajas se superponen significativamente
        self.ALIGNMENT_THRESHOLD = 3.0  # Umbral en puntos para considerar elementos alineados
        self.LINE_SPACING_FACTOR = 1.2  # Factor para determinar si elementos están en la misma línea
        
        logger.info("BoundingBoxes inicializado")
    
    def set_pdf_loader(self, pdf_loader):
        """
        Establece o actualiza el cargador de PDF.
        
        Args:
            pdf_loader: Instancia de PDFLoader con el documento cargado
        """
        self.pdf_loader = pdf_loader
        self.clear_caches()
        logger.debug("PDFLoader establecido en BoundingBoxes")
    
    def clear_caches(self):
        """Limpia las cachés de páginas y bounding boxes."""
        self.page_cache = {}
        self.bbox_cache = {}
        logger.debug("Cachés limpiadas")
    
    def get_bbox_from_structure_element(self, element: Dict) -> Optional[List[float]]:
        """
        Obtiene la caja delimitadora de un elemento estructural.
        
        Args:
            element: Elemento de estructura del PDF
            
        Returns:
            List[float]: [x0, y0, x1, y1] o None si no se puede determinar
        """
        # Verificar si ya está en caché
        element_id = id(element.get("element")) if "element" in element else None
        if element_id and element_id in self.bbox_cache:
            return self.bbox_cache[element_id]
        
        # Intentar obtener desde el atributo BBox
        if "attributes" in element and "bbox" in element["attributes"]:
            bbox = element["attributes"]["bbox"]
            if isinstance(bbox, list) and len(bbox) == 4:
                if element_id:
                    self.bbox_cache[element_id] = bbox
                return bbox
        
        # Intentar obtener desde el objeto pikepdf
        if "element" in element:
            pikepdf_element = element["element"]
            if hasattr(pikepdf_element, "BBox"):
                bbox = [float(coord) for coord in pikepdf_element.BBox]
                if element_id:
                    self.bbox_cache[element_id] = bbox
                return bbox
        
        # Buscar en la página usando MCID
        page_num = element.get("page")
        mcid = self._get_mcid_from_element(element)
        
        if page_num is not None and mcid is not None:
            bbox = self._get_bbox_from_mcid(page_num, mcid)
            if bbox:
                if element_id:
                    self.bbox_cache[element_id] = bbox
                return bbox
        
        # Último recurso: calcular desde los hijos
        if "children" in element and element["children"]:
            child_bboxes = []
            for child in element["children"]:
                child_bbox = self.get_bbox_from_structure_element(child)
                if child_bbox:
                    child_bboxes.append(child_bbox)
            
            if child_bboxes:
                combined_bbox = self.combine_bboxes(child_bboxes)
                if element_id:
                    self.bbox_cache[element_id] = combined_bbox
                return combined_bbox
        
        logger.warning(f"No se pudo determinar bounding box para elemento {element.get('type', 'desconocido')}")
        return None
    
    def _get_mcid_from_element(self, element: Dict) -> Optional[int]:
        """
        Extrae el MCID (Marked Content ID) de un elemento.
        
        Args:
            element: Elemento de estructura
            
        Returns:
            int: MCID o None si no se encuentra
        """
        if "element" in element:
            pikepdf_element = element["element"]
            if hasattr(pikepdf_element, "K"):
                k_value = pikepdf_element.K
                
                # K puede ser un entero directo (MCID)
                if isinstance(k_value, int):
                    return k_value
                
                # K puede ser un array con múltiples MCIDs o estructuras
                if hasattr(k_value, "__iter__"):
                    for item in k_value:
                        if isinstance(item, int):
                            return item
                        elif hasattr(item, "MCID"):
                            return item.MCID
        
        return None
    
    def _get_bbox_from_mcid(self, page_num: int, mcid: int) -> Optional[List[float]]:
        """
        Obtiene la caja delimitadora de un elemento marcado por su MCID.
        
        Args:
            page_num: Número de página
            mcid: ID de contenido marcado
            
        Returns:
            List[float]: [x0, y0, x1, y1] o None si no se encuentra
        """
        if not self.pdf_loader or not self.pdf_loader.doc:
            logger.warning("No hay documento cargado para buscar bbox por MCID")
            return None
        
        try:
            # Obtener página (usar caché)
            if page_num not in self.page_cache:
                self.page_cache[page_num] = self.pdf_loader.doc[page_num]
            
            page = self.page_cache[page_num]
            
            # Buscar bbox en la página
            for block in page.get_text("dict")["blocks"]:
                for line in block.get("lines", []):
                    for span in line.get("spans", []):
                        if span.get("mcid") == mcid:
                            return [span["bbox"][0], span["bbox"][1], span["bbox"][2], span["bbox"][3]]
            
            # También buscar en imágenes
            for img in page.get_images(full=True):
                xref = img[0]
                img_bbox = page.get_image_bbox(img)
                if img_bbox:
                    # Verificar si esta imagen tiene el MCID buscado
                    # Esto es complejo y podría requerir análisis del stream de la página
                    # Implementación simplificada
                    return [img_bbox.x0, img_bbox.y0, img_bbox.x1, img_bbox.y1]
        
        except Exception as e:
            logger.error(f"Error al buscar bbox por MCID: {e}")
        
        return None
    
    def get_element_visual_content(self, element: Dict) -> List[Dict]:
        """
        Obtiene el contenido visual asociado a un elemento estructural.
        
        Args:
            element: Elemento de estructura
            
        Returns:
            List[Dict]: Lista de elementos visuales (texto, imágenes, etc.)
        """
        visual_content = []
        
        if not self.pdf_loader or not self.pdf_loader.doc:
            return visual_content
        
        # Determinar página
        page_num = element.get("page")
        if page_num is None:
            return visual_content
        
        # Obtener bounding box del elemento
        element_bbox = self.get_bbox_from_structure_element(element)
        if not element_bbox:
            return visual_content
        
        # Obtener todo el contenido de la página
        if page_num not in self.page_cache:
            self.page_cache[page_num] = self.pdf_loader.doc[page_num]
        
        page = self.page_cache[page_num]
        
        # Extraer texto
        for block in page.get_text("dict")["blocks"]:
            for line in block.get("lines", []):
                for span in line.get("spans", []):
                    span_bbox = [span["bbox"][0], span["bbox"][1], span["bbox"][2], span["bbox"][3]]
                    
                    # Verificar si el span está dentro del elemento
                    if self.is_contained(span_bbox, element_bbox, threshold=0.8):
                        visual_content.append({
                            "type": "text",
                            "bbox": span_bbox,
                            "text": span["text"],
                            "font": span.get("font", ""),
                            "size": span.get("size", 0),
                            "mcid": span.get("mcid", -1)
                        })
        
        # Extraer imágenes
        for img in page.get_images(full=True):
            xref = img[0]
            img_bbox = page.get_image_bbox(img)
            if img_bbox:
                img_bbox_list = [img_bbox.x0, img_bbox.y0, img_bbox.x1, img_bbox.y1]
                
                # Verificar si la imagen está dentro del elemento
                if self.is_contained(img_bbox_list, element_bbox, threshold=0.5):
                    visual_content.append({
                        "type": "image",
                        "bbox": img_bbox_list,
                        "xref": xref,
                        "width": img[2],
                        "height": img[3]
                    })
        
        return visual_content
    
    def normalize_bbox(self, bbox: List[float], page_num: int = None) -> List[float]:
        """
        Normaliza una caja delimitadora a coordenadas relativas [0-1].
        
        Args:
            bbox: [x0, y0, x1, y1] en coordenadas absolutas
            page_num: Número de página para normalizar según tamaño
            
        Returns:
            List[float]: [x0, y0, x1, y1] en coordenadas normalizadas
        """
        if not self.pdf_loader or not self.pdf_loader.doc:
            # Si no hay contexto, devolver como está
            return bbox
        
        # Usar primera página si no se especifica
        if page_num is None:
            page_num = 0
        
        try:
            # Obtener página
            if page_num not in self.page_cache:
                self.page_cache[page_num] = self.pdf_loader.doc[page_num]
            
            page = self.page_cache[page_num]
            page_rect = page.rect
            
            # Normalizar
            return [
                bbox[0] / page_rect.width,
                bbox[1] / page_rect.height,
                bbox[2] / page_rect.width,
                bbox[3] / page_rect.height
            ]
        except Exception as e:
            logger.error(f"Error al normalizar bbox: {e}")
            return bbox
    
    def denormalize_bbox(self, bbox: List[float], page_num: int = None) -> List[float]:
        """
        Convierte una caja delimitadora de coordenadas relativas [0-1] a absolutas.
        
        Args:
            bbox: [x0, y0, x1, y1] en coordenadas normalizadas
            page_num: Número de página para normalizar según tamaño
            
        Returns:
            List[float]: [x0, y0, x1, y1] en coordenadas absolutas
        """
        if not self.pdf_loader or not self.pdf_loader.doc:
            # Si no hay contexto, devolver como está
            return bbox
        
        # Usar primera página si no se especifica
        if page_num is None:
            page_num = 0
        
        try:
            # Obtener página
            if page_num not in self.page_cache:
                self.page_cache[page_num] = self.pdf_loader.doc[page_num]
            
            page = self.page_cache[page_num]
            page_rect = page.rect
            
            # Desnormalizar
            return [
                bbox[0] * page_rect.width,
                bbox[1] * page_rect.height,
                bbox[2] * page_rect.width,
                bbox[3] * page_rect.height
            ]
        except Exception as e:
            logger.error(f"Error al desnormalizar bbox: {e}")
            return bbox
    
    def combine_bboxes(self, bboxes: List[List[float]]) -> List[float]:
        """
        Combina múltiples cajas delimitadoras en una sola que las contenga a todas.
        
        Args:
            bboxes: Lista de bounding boxes [x0, y0, x1, y1]
            
        Returns:
            List[float]: Bounding box combinado [x0, y0, x1, y1]
        """
        if not bboxes:
            return [0, 0, 0, 0]
        
        x0 = min(bbox[0] for bbox in bboxes)
        y0 = min(bbox[1] for bbox in bboxes)
        x1 = max(bbox[2] for bbox in bboxes)
        y1 = max(bbox[3] for bbox in bboxes)
        
        return [x0, y0, x1, y1]
    
    def intersect_bboxes(self, bbox1: List[float], bbox2: List[float]) -> List[float]:
        """
        Calcula la intersección de dos cajas delimitadoras.
        
        Args:
            bbox1: Primera caja [x0, y0, x1, y1]
            bbox2: Segunda caja [x0, y0, x1, y1]
            
        Returns:
            List[float]: Caja de intersección o [0,0,0,0] si no hay intersección
        """
        x0 = max(bbox1[0], bbox2[0])
        y0 = max(bbox1[1], bbox2[1])
        x1 = min(bbox1[2], bbox2[2])
        y1 = min(bbox1[3], bbox2[3])
        
        # Verificar si hay intersección
        if x0 >= x1 or y0 >= y1:
            return [0, 0, 0, 0]
        
        return [x0, y0, x1, y1]
    
    def get_bbox_area(self, bbox: List[float]) -> float:
        """
        Calcula el área de una caja delimitadora.
        
        Args:
            bbox: Caja delimitadora [x0, y0, x1, y1]
            
        Returns:
            float: Área de la caja
        """
        width = bbox[2] - bbox[0]
        height = bbox[3] - bbox[1]
        
        if width < 0 or height < 0:
            return 0
        
        return width * height
    
    def get_overlap_area(self, bbox1: List[float], bbox2: List[float]) -> float:
        """
        Calcula el área de superposición entre dos cajas.
        
        Args:
            bbox1: Primera caja [x0, y0, x1, y1]
            bbox2: Segunda caja [x0, y0, x1, y1]
            
        Returns:
            float: Área de superposición
        """
        intersection = self.intersect_bboxes(bbox1, bbox2)
        return self.get_bbox_area(intersection)
    
    def get_overlap_ratio(self, bbox1: List[float], bbox2: List[float]) -> float:
        """
        Calcula la proporción de superposición entre dos cajas.
        
        Args:
            bbox1: Primera caja [x0, y0, x1, y1]
            bbox2: Segunda caja [x0, y0, x1, y1]
            
        Returns:
            float: Proporción del área más pequeña que está superpuesta [0-1]
        """
        area1 = self.get_bbox_area(bbox1)
        area2 = self.get_bbox_area(bbox2)
        
        if area1 == 0 or area2 == 0:
            return 0
        
        overlap_area = self.get_overlap_area(bbox1, bbox2)
        min_area = min(area1, area2)
        
        return overlap_area / min_area
    
    def is_overlapping(self, bbox1: List[float], bbox2: List[float], threshold: float = None) -> bool:
        """
        Determina si dos cajas se superponen significativamente.
        
        Args:
            bbox1: Primera caja [x0, y0, x1, y1]
            bbox2: Segunda caja [x0, y0, x1, y1]
            threshold: Umbral de superposición [0-1] o None para usar el predeterminado
            
        Returns:
            bool: True si se superponen por encima del umbral
        """
        if threshold is None:
            threshold = self.OVERLAP_THRESHOLD
        
        ratio = self.get_overlap_ratio(bbox1, bbox2)
        return ratio >= threshold
    
    def is_contained(self, inner_bbox: List[float], outer_bbox: List[float], threshold: float = 0.9) -> bool:
        """
        Determina si una caja está contenida dentro de otra.
        
        Args:
            inner_bbox: Caja interior [x0, y0, x1, y1]
            outer_bbox: Caja exterior [x0, y0, x1, y1]
            threshold: Umbral de contención [0-1], proporción que debe estar contenida
            
        Returns:
            bool: True si inner_bbox está contenida en outer_bbox por encima del umbral
        """
        inner_area = self.get_bbox_area(inner_bbox)
        if inner_area == 0:
            return False
        
        overlap_area = self.get_overlap_area(inner_bbox, outer_bbox)
        contained_ratio = overlap_area / inner_area
        
        return contained_ratio >= threshold
    
    def are_horizontally_aligned(self, bbox1: List[float], bbox2: List[float], threshold: float = None) -> bool:
        """
        Determina si dos cajas están alineadas horizontalmente.
        
        Args:
            bbox1: Primera caja [x0, y0, x1, y1]
            bbox2: Segunda caja [x0, y0, x1, y1]
            threshold: Umbral en puntos o None para usar el predeterminado
            
        Returns:
            bool: True si están alineadas horizontalmente
        """
        if threshold is None:
            threshold = self.ALIGNMENT_THRESHOLD
        
        # Calcular centros verticales
        center_y1 = (bbox1[1] + bbox1[3]) / 2
        center_y2 = (bbox2[1] + bbox2[3]) / 2
        
        return abs(center_y1 - center_y2) <= threshold
    
    def are_vertically_aligned(self, bbox1: List[float], bbox2: List[float], threshold: float = None) -> bool:
        """
        Determina si dos cajas están alineadas verticalmente.
        
        Args:
            bbox1: Primera caja [x0, y0, x1, y1]
            bbox2: Segunda caja [x0, y0, x1, y1]
            threshold: Umbral en puntos o None para usar el predeterminado
            
        Returns:
            bool: True si están alineadas verticalmente
        """
        if threshold is None:
            threshold = self.ALIGNMENT_THRESHOLD
        
        # Calcular centros horizontales
        center_x1 = (bbox1[0] + bbox1[2]) / 2
        center_x2 = (bbox2[0] + bbox2[2]) / 2
        
        return abs(center_x1 - center_x2) <= threshold
    
    def get_text_direction(self, bbox1: List[float], bbox2: List[float]) -> str:
        """
        Determina la dirección probable de texto entre dos cajas.
        
        Args:
            bbox1: Primera caja [x0, y0, x1, y1]
            bbox2: Segunda caja [x0, y0, x1, y1]
            
        Returns:
            str: 'LR' (izquierda a derecha), 'RL' (derecha a izquierda), 
                 'TB' (arriba a abajo), 'BT' (abajo a arriba)
        """
        # Calcular centros
        center_x1 = (bbox1[0] + bbox1[2]) / 2
        center_y1 = (bbox1[1] + bbox1[3]) / 2
        center_x2 = (bbox2[0] + bbox2[2]) / 2
        center_y2 = (bbox2[1] + bbox2[3]) / 2
        
        # Calcular distancias
        dx = center_x2 - center_x1
        dy = center_y2 - center_y1
        
        # Determinar dirección dominante
        if abs(dx) > abs(dy):
            # Dirección horizontal dominante
            return "LR" if dx > 0 else "RL"
        else:
            # Dirección vertical dominante
            return "TB" if dy > 0 else "BT"
    
    def estimate_reading_order(self, elements: List[Dict], page_num: int = None) -> List[Dict]:
        """
        Estima el orden de lectura lógico para elementos basado en posición espacial.
        
        Args:
            elements: Lista de elementos con atributo 'bbox'
            page_num: Número de página para normalización
            
        Returns:
            List[Dict]: Elementos ordenados según orden de lectura estimado
        """
        if not elements:
            return []
        
        # Extraer bounding boxes
        element_bboxes = []
        for element in elements:
            if 'bbox' in element:
                bbox = element['bbox']
            else:
                bbox = self.get_bbox_from_structure_element(element)
            
            if bbox:
                element_bboxes.append((bbox, element))
        
        # Si no hay bboxes válidos, devolver como está
        if not element_bboxes:
            return elements
        
        # Agrupar por líneas (elementos horizontalmente alineados)
        lines = self._group_by_lines(element_bboxes)
        
        # Ordenar líneas de arriba a abajo
        lines.sort(key=lambda line: min(bbox[1] for bbox, _ in line))
        
        # Ordenar elementos dentro de cada línea de izquierda a derecha
        ordered_elements = []
        for line in lines:
            # Ordenar línea de izquierda a derecha
            sorted_line = sorted(line, key=lambda item: item[0][0])
            ordered_elements.extend([element for _, element in sorted_line])
        
        return ordered_elements
    
    def _group_by_lines(self, element_bboxes: List[Tuple[List[float], Dict]]) -> List[List[Tuple[List[float], Dict]]]:
        """
        Agrupa elementos en líneas basado en alineación horizontal.
        
        Args:
            element_bboxes: Lista de tuplas (bbox, element)
            
        Returns:
            List[List[Tuple]]: Lista de líneas, donde cada línea es una lista de tuplas (bbox, element)
        """
        if not element_bboxes:
            return []
        
        # Calcular alturas promedio
        heights = [bbox[3] - bbox[1] for bbox, _ in element_bboxes]
        avg_height = sum(heights) / len(heights) if heights else 0
        
        # Umbral para determinar si dos elementos están en la misma línea
        line_threshold = avg_height * self.LINE_SPACING_FACTOR
        
        # Inicializar con una línea vacía
        lines = []
        current_line = []
        
        # Ordenar elementos por coordenada Y
        sorted_elements = sorted(element_bboxes, key=lambda item: item[0][1])
        
        for bbox, element in sorted_elements:
            # Calcular centro Y del elemento actual
            center_y = (bbox[1] + bbox[3]) / 2
            
            if not current_line:
                # Primera línea, agregar elemento
                current_line.append((bbox, element))
            else:
                # Calcular centro Y medio de la línea actual
                line_centers = [(box[1] + box[3]) / 2 for box, _ in current_line]
                line_center_y = sum(line_centers) / len(line_centers)
                
                # Verificar si el elemento está en la misma línea
                if abs(center_y - line_center_y) <= line_threshold:
                    current_line.append((bbox, element))
                else:
                    # Nueva línea
                    lines.append(current_line)
                    current_line = [(bbox, element)]
        
        # Agregar última línea si no está vacía
        if current_line:
            lines.append(current_line)
        
        return lines
    
    def get_common_parent(self, element1: Dict, element2: Dict, structure_tree: Dict) -> Optional[Dict]:
        """
        Encuentra el ancestro común más cercano para dos elementos en el árbol de estructura.
        
        Args:
            element1: Primer elemento
            element2: Segundo elemento
            structure_tree: Raíz del árbol de estructura
            
        Returns:
            Dict: Ancestro común o None si no se encuentra
        """
        # Obtener IDs de los elementos
        element1_id = id(element1.get("element")) if "element" in element1 else None
        element2_id = id(element2.get("element")) if "element" in element2 else None
        
        if not element1_id or not element2_id:
            return None
        
        # Obtener rutas desde la raíz hasta cada elemento
        path1 = self._get_path_to_element(structure_tree, element1_id)
        path2 = self._get_path_to_element(structure_tree, element2_id)
        
        if not path1 or not path2:
            return None
        
        # Encontrar último elemento común en ambas rutas
        common_path = []
        for i in range(min(len(path1), len(path2))):
            if path1[i] == path2[i]:
                common_path.append(path1[i])
            else:
                break
        
        if not common_path:
            return None
        
        # Devolver el último elemento común
        return common_path[-1]
    
    def _get_path_to_element(self, node: Dict, element_id: int, path: List[Dict] = None) -> Optional[List[Dict]]:
        """
        Encuentra la ruta desde la raíz hasta un elemento.
        
        Args:
            node: Nodo actual en el recorrido
            element_id: ID del elemento buscado
            path: Ruta acumulada hasta ahora
            
        Returns:
            List[Dict]: Ruta o None si no se encuentra
        """
        if path is None:
            path = []
        
        # Verificar si el nodo actual es el buscado
        current_id = id(node.get("element")) if "element" in node else None
        if current_id == element_id:
            return path + [node]
        
        # Buscar en hijos
        if "children" in node:
            for child in node["children"]:
                child_path = self._get_path_to_element(child, element_id, path + [node])
                if child_path:
                    return child_path
        
        return None
    
    def detect_artifacts(self, page_num: int, structure_elements: List[Dict] = None) -> List[Dict]:
        """
        Detecta posibles artefactos en una página basado en posición y contenido.
        
        Args:
            page_num: Número de página
            structure_elements: Lista opcional de elementos estructurales conocidos
            
        Returns:
            List[Dict]: Lista de artefactos detectados con información
        """
        if not self.pdf_loader or not self.pdf_loader.doc:
            return []
        
        artifacts = []
        
        try:
            # Obtener página
            if page_num not in self.page_cache:
                self.page_cache[page_num] = self.pdf_loader.doc[page_num]
            
            page = self.page_cache[page_num]
            page_rect = page.rect
            
            # Detectar posibles encabezados y pies (basado en posición)
            header_zone = [0, 0, page_rect.width, page_rect.height * 0.1]
            footer_zone = [0, page_rect.height * 0.9, page_rect.width, page_rect.height]
            
            # Extraer todo el contenido visual de la página
            blocks = page.get_text("dict")["blocks"]
            
            # Crear conjunto de IDs de elementos estructurales conocidos
            struct_mcids = set()
            if structure_elements:
                for element in structure_elements:
                    mcid = self._get_mcid_from_element(element)
                    if mcid is not None:
                        struct_mcids.add(mcid)
            
            # Analizar cada bloque de texto
            for block in blocks:
                for line in block.get("lines", []):
                    for span in line.get("spans", []):
                        span_bbox = [span["bbox"][0], span["bbox"][1], span["bbox"][2], span["bbox"][3]]
                        mcid = span.get("mcid", -1)
                        
                        # Ignorar si ya está en la estructura
                        if mcid in struct_mcids:
                            continue
                        
                        # Verificar si está en zona de encabezado o pie
                        in_header = self.is_overlapping(span_bbox, header_zone)
                        in_footer = self.is_overlapping(span_bbox, footer_zone)
                        
                        if in_header or in_footer:
                            # Detectar posible número de página
                            is_page_number = False
                            text = span["text"].strip()
                            
                            # Posible número de página
                            if text.isdigit() or (
                                len(text) <= 10 and 
                                any(marker in text for marker in ["Pág.", "Page", "Página", "-", "/"])
                            ):
                                is_page_number = True
                            
                            artifacts.append({
                                "type": "pagination" if is_page_number else ("header" if in_header else "footer"),
                                "bbox": span_bbox,
                                "text": text,
                                "mcid": mcid,
                                "confidence": 0.9 if is_page_number else 0.7
                            })
            
            # Detectar bordes de página como posibles artefactos
            # Extraer trazos finos que podrían ser bordes
            paths = page.get_drawings()
            for path in paths:
                if "items" in path and path.get("width", 2) < 2:  # Trazar fino
                    # Verificar si está cerca de los bordes
                    path_bbox = path.get("rect")
                    if path_bbox:
                        bbox = [path_bbox[0], path_bbox[1], path_bbox[2], path_bbox[3]]
                        near_edge = (
                            bbox[0] < page_rect.width * 0.05 or
                            bbox[1] < page_rect.height * 0.05 or
                            bbox[2] > page_rect.width * 0.95 or
                            bbox[3] > page_rect.height * 0.95
                        )
                        
                        if near_edge:
                            artifacts.append({
                                "type": "background",
                                "subtype": "border",
                                "bbox": bbox,
                                "confidence": 0.6
                            })
            
            # Detectar objetos pequeños aislados que podrían ser decoraciones
            for img in page.get_images(full=True):
                xref = img[0]
                img_bbox = page.get_image_bbox(img)
                if img_bbox:
                    bbox = [img_bbox.x0, img_bbox.y0, img_bbox.x1, img_bbox.y1]
                    area = self.get_bbox_area(bbox)
                    
                    # Imágenes pequeñas en los bordes podrían ser decoraciones
                    if area < (page_rect.width * page_rect.height * 0.01):
                        near_edge = (
                            bbox[0] < page_rect.width * 0.05 or
                            bbox[1] < page_rect.height * 0.05 or
                            bbox[2] > page_rect.width * 0.95 or
                            bbox[3] > page_rect.height * 0.95
                        )
                        
                        if near_edge:
                            artifacts.append({
                                "type": "background",
                                "subtype": "decoration",
                                "bbox": bbox,
                                "confidence": 0.5
                            })
        
        except Exception as e:
            logger.error(f"Error al detectar artefactos: {e}")
        
        return artifacts
    
    def detect_tables(self, page_num: int) -> List[Dict]:
        """
        Detecta posibles tablas en una página basado en la disposición espacial.
        
        Args:
            page_num: Número de página
            
        Returns:
            List[Dict]: Lista de tablas detectadas con información
        """
        if not self.pdf_loader or not self.pdf_loader.doc:
            return []
        
        tables = []
        
        try:
            # Obtener página
            if page_num not in self.page_cache:
                self.page_cache[page_num] = self.pdf_loader.doc[page_num]
            
            page = self.page_cache[page_num]
            
            # Extraer texto en formato diccionario
            page_dict = page.get_text("dict")
            
            # Extraer bloques de texto
            blocks = page_dict["blocks"]
            
            # Detectar líneas horizontales y verticales (posibles bordes de tabla)
            drawings = page.get_drawings()
            h_lines = []
            v_lines = []
            
            for drawing in drawings:
                if "items" in drawing:
                    for item in drawing["items"]:
                        if item[0] == "l":  # Línea
                            x0, y0, x1, y1 = item[1:5]
                            if abs(y1 - y0) < 2:  # Línea horizontal
                                h_lines.append([min(x0, x1), y0, max(x0, x1), y1])
                            elif abs(x1 - x0) < 2:  # Línea vertical
                                v_lines.append([x0, min(y0, y1), x1, max(y0, y1)])
            
            # Buscar intersecciones de líneas (posibles esquinas de celdas)
            intersections = []
            for h_line in h_lines:
                for v_line in v_lines:
                    if (h_line[0] <= v_line[0] <= h_line[2] and 
                        v_line[1] <= h_line[1] <= v_line[3]):
                        intersections.append((v_line[0], h_line[1]))
            
            # Si hay suficientes intersecciones, es probable que sea una tabla
            if len(intersections) >= 4:
                # Determinar bounding box de la tabla
                if h_lines and v_lines:
                    min_x = min(line[0] for line in v_lines)
                    min_y = min(line[1] for line in h_lines)
                    max_x = max(line[2] for line in v_lines)
                    max_y = max(line[3] for line in h_lines)
                    
                    table_bbox = [min_x, min_y, max_x, max_y]
                    
                    # Determinar filas y columnas
                    h_positions = sorted(set(line[1] for line in h_lines))
                    v_positions = sorted(set(line[0] for line in v_lines))
                    
                    # Calcular número estimado de filas y columnas
                    rows = len(h_positions) - 1
                    cols = len(v_positions) - 1
                    
                    if rows > 0 and cols > 0:
                        # Buscar texto dentro de la tabla
                        cells = []
                        for block in blocks:
                            for line in block.get("lines", []):
                                for span in line.get("spans", []):
                                    span_bbox = [span["bbox"][0], span["bbox"][1], span["bbox"][2], span["bbox"][3]]
                                    
                                    # Verificar si el span está dentro de la tabla
                                    if self.is_contained(span_bbox, table_bbox, threshold=0.8):
                                        # Determinar a qué celda pertenece
                                        row_idx = -1
                                        col_idx = -1
                                        
                                        span_center_y = (span_bbox[1] + span_bbox[3]) / 2
                                        span_center_x = (span_bbox[0] + span_bbox[2]) / 2
                                        
                                        for i in range(len(h_positions) - 1):
                                            if h_positions[i] <= span_center_y <= h_positions[i + 1]:
                                                row_idx = i
                                                break
                                                
                                        for j in range(len(v_positions) - 1):
                                            if v_positions[j] <= span_center_x <= v_positions[j + 1]:
                                                col_idx = j
                                                break
                                        
                                        if row_idx >= 0 and col_idx >= 0:
                                            cells.append({
                                                "row": row_idx,
                                                "col": col_idx,
                                                "text": span["text"],
                                                "bbox": span_bbox
                                            })
                        
                        # Comprobar si hay suficientes celdas para ser una tabla
                        if len(cells) >= (rows * cols / 2):
                            tables.append({
                                "type": "table",
                                "bbox": table_bbox,
                                "rows": rows,
                                "cols": cols,
                                "cells": cells,
                                "confidence": 0.8
                            })
            
            # Método alternativo: detectar tablas sin bordes
            # Buscar alineaciones de texto en rejilla
            text_rows = defaultdict(list)
            
            for block in blocks:
                for line in block.get("lines", []):
                    for span in line.get("spans", []):
                        center_y = (span["bbox"][1] + span["bbox"][3]) / 2
                        rounded_y = round(center_y / 5) * 5  # Agrupar por cercanía
                        text_rows[rounded_y].append({
                            "text": span["text"],
                            "bbox": [span["bbox"][0], span["bbox"][1], span["bbox"][2], span["bbox"][3]]
                        })
            
            # Analizar si los textos forman una rejilla (tabla)
            if len(text_rows) >= 3:  # Al menos 3 filas para considerar una tabla
                sorted_rows = sorted(text_rows.items())
                
                # Contar elementos por fila
                counts = [len(row) for _, row in sorted_rows]
                
                # Si varias filas tienen la misma cantidad de elementos, podría ser una tabla
                if len(set(counts)) <= 3 and max(counts) >= 2:  # Tablas tienen columnas consistentes
                    # Ordenar por posición X en cada fila
                    for y, row in sorted_rows:
                        text_rows[y] = sorted(row, key=lambda span: span["bbox"][0])
                    
                    # Calcular bounding box
                    cells = [span for row in text_rows.values() for span in row]
                    if cells:
                        x_values = [cell["bbox"][i] for cell in cells for i in [0, 2]]
                        y_values = [cell["bbox"][i] for cell in cells for i in [1, 3]]
                        
                        min_x = min(x_values)
                        min_y = min(y_values)
                        max_x = max(x_values)
                        max_y = max(y_values)
                        
                        table_bbox = [min_x, min_y, max_x, max_y]
                        
                        # Verificar si ya detectamos esta tabla
                        is_duplicate = False
                        for existing_table in tables:
                            if self.get_overlap_ratio(table_bbox, existing_table["bbox"]) > 0.7:
                                is_duplicate = True
                                break
                        
                        if not is_duplicate:
                            tables.append({
                                "type": "table",
                                "bbox": table_bbox,
                                "rows": len(sorted_rows),
                                "cols": max(counts),
                                "cells": cells,
                                "confidence": 0.6,
                                "no_borders": True
                            })
        
        except Exception as e:
            logger.error(f"Error al detectar tablas: {e}")
        
        return tables
    
    def detect_columns(self, page_num: int) -> List[Dict]:
        """
        Detecta posibles columnas de texto en una página.
        
        Args:
            page_num: Número de página
            
        Returns:
            List[Dict]: Lista de columnas detectadas con información
        """
        if not self.pdf_loader or not self.pdf_loader.doc:
            return []
        
        columns = []
        
        try:
            # Obtener página
            if page_num not in self.page_cache:
                self.page_cache[page_num] = self.pdf_loader.doc[page_num]
            
            page = self.page_cache[page_num]
            page_rect = page.rect
            
            # Extraer bloques de texto
            blocks = page.get_text("dict")["blocks"]
            
            # Recopilar todos los bloques de texto
            text_blocks = []
            for block in blocks:
                if block.get("type") == 0:  # Bloque de texto
                    text_blocks.append({
                        "bbox": [block["bbox"][0], block["bbox"][1], block["bbox"][2], block["bbox"][3]],
                        "lines": len(block.get("lines", [])),
                        "text": "".join(span["text"] for line in block.get("lines", []) for span in line.get("spans", []))
                    })
            
            if not text_blocks:
                return []
            
            # Agrupar bloques por posición X
            x_positions = defaultdict(list)
            
            for block in text_blocks:
                center_x = (block["bbox"][0] + block["bbox"][2]) / 2
                rounded_x = round(center_x / 10) * 10  # Agrupar por cercanía
                x_positions[rounded_x].append(block)
            
            # Identificar posibles columnas (grupos de bloques alineados verticalmente)
            for x_pos, blocks in x_positions.items():
                if len(blocks) < 2:  # Necesitamos al menos 2 bloques para considerar una columna
                    continue
                
                # Ordenar bloques por posición Y
                blocks_sorted = sorted(blocks, key=lambda b: b["bbox"][1])
                
                # Calcular bounding box de la columna
                col_x0 = min(block["bbox"][0] for block in blocks)
                col_y0 = min(block["bbox"][1] for block in blocks)
                col_x1 = max(block["bbox"][2] for block in blocks)
                col_y1 = max(block["bbox"][3] for block in blocks)
                
                column_bbox = [col_x0, col_y0, col_x1, col_y1]
                column_width = col_x1 - col_x0
                
                # Verificar si el ancho es razonable para una columna
                if column_width < page_rect.width * 0.8:
                    total_lines = sum(block["lines"] for block in blocks)
                    
                    columns.append({
                        "type": "column",
                        "bbox": column_bbox,
                        "blocks": len(blocks),
                        "lines": total_lines,
                        "confidence": min(0.9, 0.5 + (total_lines / 20))  # Mayor confianza con más líneas
                    })
            
            # Verificar si las columnas detectadas tienen sentido en conjunto
            if len(columns) >= 2:
                # Ordenar columnas de izquierda a derecha
                columns.sort(key=lambda col: col["bbox"][0])
                
                # Verificar que las columnas no se superpongan demasiado
                for i in range(len(columns) - 1):
                    col1 = columns[i]
                    col2 = columns[i + 1]
                    
                    overlap = self.get_overlap_ratio(col1["bbox"], col2["bbox"])
                    
                    # Si la superposición es alta, ajustar la confianza hacia abajo
                    if overlap > 0.3:
                        col1["confidence"] *= (1 - overlap)
                        col2["confidence"] *= (1 - overlap)
            
            # Filtrar columnas con baja confianza
            columns = [col for col in columns if col["confidence"] > 0.3]
        
        except Exception as e:
            logger.error(f"Error al detectar columnas: {e}")
        
        return columns
    
    def detect_lists(self, page_num: int) -> List[Dict]:
        """
        Detecta posibles listas en una página basado en patrones de viñetas o numeración.
        
        Args:
            page_num: Número de página
            
        Returns:
            List[Dict]: Lista de listas detectadas con información
        """
        if not self.pdf_loader or not self.pdf_loader.doc:
            return []
        
        lists = []
        
        try:
            # Obtener página
            if page_num not in self.page_cache:
                self.page_cache[page_num] = self.pdf_loader.doc[page_num]
            
            page = self.page_cache[page_num]
            
            # Extraer líneas de texto
            text_lines = []
            for block in page.get_text("dict")["blocks"]:
                if block.get("type") == 0:  # Bloque de texto
                    for line in block.get("lines", []):
                        spans = line.get("spans", [])
                        if spans:
                            text = "".join(span["text"] for span in spans)
                            text_lines.append({
                                "text": text,
                                "bbox": [line["bbox"][0], line["bbox"][1], line["bbox"][2], line["bbox"][3]],
                                "spans": spans
                            })
            
            # Ordenar líneas por posición Y
            text_lines.sort(key=lambda line: line["bbox"][1])
            
            # Patrones para detectar elementos de lista
            bullet_pattern = re.compile(r'^\s*[•⁃⁌⁍∙◦⦿⦾⚫⚬✓✗✘✔✖✕□■○●]\s+')
            numbered_pattern = re.compile(r'^\s*\(?(?:\d+|[a-zA-Z]|[ivxIVX]+)[\.\)]\s+')
            
            # Buscar secuencias de líneas con patrones de lista
            current_list = None
            list_items = []
            
            for i, line in enumerate(text_lines):
                text = line["text"].strip()
                
                # Comprobar si esta línea parece ser un elemento de lista
                is_bullet = bool(bullet_pattern.match(text))
                is_numbered = bool(numbered_pattern.match(text))
                
                if is_bullet or is_numbered:
                    # Extraer el marcador (viñeta o número)
                    match = bullet_pattern.match(text) if is_bullet else numbered_pattern.match(text)
                    marker = text[:match.end()].strip()
                    content = text[match.end():].strip()
                    
                    # Calcular la indentación
                    indentation = line["spans"][0]["bbox"][0]
                    
                    # Iniciar una nueva lista si no hay una actual o si la indentación cambia significativamente
                    if (current_list is None or 
                        abs(indentation - current_list["indentation"]) > 10 or
                        current_list["type"] != ("bullet" if is_bullet else "numbered")):
                        
                        # Finalizar lista anterior si existe
                        if current_list and list_items:
                            # Calcular bounding box de toda la lista
                            list_x0 = min(item["bbox"][0] for item in list_items)
                            list_y0 = min(item["bbox"][1] for item in list_items)
                            list_x1 = max(item["bbox"][2] for item in list_items)
                            list_y1 = max(item["bbox"][3] for item in list_items)
                            
                            lists.append({
                                "type": "list",
                                "list_type": current_list["type"],
                                "bbox": [list_x0, list_y0, list_x1, list_y1],
                                "items": list_items.copy(),
                                "confidence": min(0.9, 0.5 + (len(list_items) * 0.1))
                            })
                        
                        # Iniciar nueva lista
                        current_list = {
                            "type": "bullet" if is_bullet else "numbered",
                            "indentation": indentation
                        }
                        list_items = []
                    
                    # Añadir este elemento a la lista actual
                    list_items.append({
                        "marker": marker,
                        "content": content,
                        "bbox": line["bbox"],
                        "spans": line["spans"]
                    })
                
                # Línea en blanco o texto normal puede finalizar la lista
                elif current_list and (not text or i == len(text_lines) - 1):
                    if list_items:
                        # Calcular bounding box de toda la lista
                        list_x0 = min(item["bbox"][0] for item in list_items)
                        list_y0 = min(item["bbox"][1] for item in list_items)
                        list_x1 = max(item["bbox"][2] for item in list_items)
                        list_y1 = max(item["bbox"][3] for item in list_items)
                        
                        lists.append({
                            "type": "list",
                            "list_type": current_list["type"],
                            "bbox": [list_x0, list_y0, list_x1, list_y1],
                            "items": list_items.copy(),
                            "confidence": min(0.9, 0.5 + (len(list_items) * 0.1))
                        })
                    
                    current_list = None
                    list_items = []
                
                # Continuación de un elemento de lista (línea siguiente indentada)
                elif current_list and list_items and line["bbox"][0] > current_list["indentation"] + 10:
                    # Añadir a la continuación del último elemento
                    list_items[-1]["content"] += " " + text
                    # Actualizar bbox
                    list_items[-1]["bbox"] = [
                        min(list_items[-1]["bbox"][0], line["bbox"][0]),
                        min(list_items[-1]["bbox"][1], line["bbox"][1]),
                        max(list_items[-1]["bbox"][2], line["bbox"][2]),
                        max(list_items[-1]["bbox"][3], line["bbox"][3])
                    ]
                
                # Texto normal finaliza la lista
                elif current_list:
                    if list_items:
                        # Calcular bounding box de toda la lista
                        list_x0 = min(item["bbox"][0] for item in list_items)
                        list_y0 = min(item["bbox"][1] for item in list_items)
                        list_x1 = max(item["bbox"][2] for item in list_items)
                        list_y1 = max(item["bbox"][3] for item in list_items)
                        
                        lists.append({
                            "type": "list",
                            "list_type": current_list["type"],
                            "bbox": [list_x0, list_y0, list_x1, list_y1],
                            "items": list_items.copy(),
                            "confidence": min(0.9, 0.5 + (len(list_items) * 0.1))
                        })
                    
                    current_list = None
                    list_items = []
            
            # Finalizar última lista si existe
            if current_list and list_items:
                # Calcular bounding box de toda la lista
                list_x0 = min(item["bbox"][0] for item in list_items)
                list_y0 = min(item["bbox"][1] for item in list_items)
                list_x1 = max(item["bbox"][2] for item in list_items)
                list_y1 = max(item["bbox"][3] for item in list_items)
                
                lists.append({
                    "type": "list",
                    "list_type": current_list["type"],
                    "bbox": [list_x0, list_y0, list_x1, list_y1],
                    "items": list_items,
                    "confidence": min(0.9, 0.5 + (len(list_items) * 0.1))
                })
            
            # Filtrar listas con muy pocos elementos
            lists = [l for l in lists if len(l["items"]) >= 2]
        
        except Exception as e:
            logger.error(f"Error al detectar listas: {e}")
        
        return lists
    
    def visualize_bboxes(self, page_num: int, bboxes: List[List[float]], colors: List[Tuple[float, float, float]] = None, output_path: str = None):
        """
        Visualiza cajas delimitadoras en una página y guarda la imagen.
        Útil para depuración y verificación de resultados.
        
        Args:
            page_num: Número de página
            bboxes: Lista de bounding boxes [x0, y0, x1, y1]
            colors: Lista de colores RGB (0-1) para cada bbox o None para colores aleatorios
            output_path: Ruta para guardar la imagen o None para mostrarla
            
        Returns:
            None
        """
        if not self.pdf_loader or not self.pdf_loader.doc:
            logger.error("No hay documento cargado para visualizar bboxes")
            return
        
        try:
            # Asegurarse de que tenemos matplotlib
            import matplotlib.pyplot as plt
            from matplotlib.patches import Rectangle
            import matplotlib.colors as mcolors
            
            # Obtener página
            if page_num not in self.page_cache:
                self.page_cache[page_num] = self.pdf_loader.doc[page_num]
            
            page = self.page_cache[page_num]
            
            # Renderizar página
            pix = page.get_pixmap(alpha=False)
            img = np.frombuffer(pix.samples, dtype=np.uint8).reshape(pix.h, pix.w, pix.n)
            
            # Crear figura
            fig, ax = plt.subplots(figsize=(12, 16))
            ax.imshow(img)
            
            # Generar colores aleatorios si no se proporcionan
            if colors is None:
                colors = [list(mcolors.TABLEAU_COLORS.values())[i % len(mcolors.TABLEAU_COLORS)] for i in range(len(bboxes))]
            
            # Dibujar cada bbox
            for i, bbox in enumerate(bboxes):
                color = colors[i] if i < len(colors) else 'red'
                rect = Rectangle((bbox[0], bbox[1]), 
                                 bbox[2] - bbox[0], 
                                 bbox[3] - bbox[1], 
                                 linewidth=1.5, 
                                 edgecolor=color, 
                                 facecolor='none',
                                 alpha=0.7)
                ax.add_patch(rect)
                
                # Añadir número de índice
                ax.text(bbox[0], bbox[1], str(i), 
                        color='white', fontsize=10, 
                        bbox=dict(facecolor=color, alpha=0.7))
            
            # Quitar ejes
            ax.axis('off')
            
            # Guardar o mostrar
            if output_path:
                plt.savefig(output_path, bbox_inches='tight', pad_inches=0.1, dpi=150)
                plt.close(fig)
                logger.info(f"Imagen con bboxes guardada en: {output_path}")
            else:
                plt.show()
        
        except ImportError:
            logger.error("Se requiere matplotlib para visualizar bboxes")
        except Exception as e:
            logger.error(f"Error al visualizar bboxes: {e}")