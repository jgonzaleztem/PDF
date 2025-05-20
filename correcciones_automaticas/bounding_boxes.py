#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Utilidad para análisis geométrico de contenido en PDF.
Proporciona funciones para trabajar con bounding boxes.
"""

from typing import Dict, List, Tuple, Optional
import numpy as np
from loguru import logger

class BoundingBoxes:
    """
    Clase para análisis geométrico de contenido en PDF.
    Proporciona funciones para trabajar con bounding boxes.
    """
    
    @staticmethod
    def calculate_overlap(bbox1: List[float], bbox2: List[float]) -> float:
        """
        Calcula el porcentaje de solapamiento entre dos bounding boxes.
        
        Args:
            bbox1: Primera bounding box [x0, y0, x1, y1]
            bbox2: Segunda bounding box [x0, y0, x1, y1]
            
        Returns:
            float: Porcentaje de solapamiento (0-1)
        """
        try:
            # Calcular coordenadas de intersección
            x_left = max(bbox1[0], bbox2[0])
            y_top = max(bbox1[1], bbox2[1])
            x_right = min(bbox1[2], bbox2[2])
            y_bottom = min(bbox1[3], bbox2[3])
            
            # Verificar si hay intersección
            if x_right < x_left or y_bottom < y_top:
                return 0.0
            
            # Calcular áreas
            intersection_area = (x_right - x_left) * (y_bottom - y_top)
            bbox1_area = (bbox1[2] - bbox1[0]) * (bbox1[3] - bbox1[1])
            bbox2_area = (bbox2[2] - bbox2[0]) * (bbox2[3] - bbox2[1])
            
            # Evitar división por cero
            if bbox1_area == 0 or bbox2_area == 0:
                return 0.0
            
            # Calcular porcentaje de solapamiento (respecto al área más pequeña)
            overlap = intersection_area / min(bbox1_area, bbox2_area)
            
            return overlap
            
        except Exception as e:
            logger.exception(f"Error al calcular solapamiento: {e}")
            return 0.0
    
    @staticmethod
    def are_adjacent(bbox1: List[float], bbox2: List[float], threshold: float = 5.0) -> bool:
        """
        Determina si dos bounding boxes son adyacentes.
        
        Args:
            bbox1: Primera bounding box [x0, y0, x1, y1]
            bbox2: Segunda bounding box [x0, y0, x1, y1]
            threshold: Umbral de distancia para considerar adyacencia
            
        Returns:
            bool: True si son adyacentes
        """
        try:
            # Verificar adyacencia horizontal
            horizontal_adjacent = (
                abs(bbox1[2] - bbox2[0]) < threshold or  # bbox1 a la izquierda de bbox2
                abs(bbox2[2] - bbox1[0]) < threshold      # bbox2 a la izquierda de bbox1
            )
            
            # Verificar adyacencia vertical
            vertical_adjacent = (
                abs(bbox1[3] - bbox2[1]) < threshold or  # bbox1 encima de bbox2
                abs(bbox2[3] - bbox1[1]) < threshold      # bbox2 encima de bbox1
            )
            
            # Verificar solapamiento parcial en una dimensión
            horizontal_overlap = (
                bbox1[0] < bbox2[2] and bbox1[2] > bbox2[0]
            )
            
            vertical_overlap = (
                bbox1[1] < bbox2[3] and bbox1[3] > bbox2[1]
            )
            
            # Son adyacentes si hay solapamiento en una dimensión y adyacencia en la otra
            return (horizontal_overlap and vertical_adjacent) or (vertical_overlap and horizontal_adjacent)
            
        except Exception as e:
            logger.exception(f"Error al determinar adyacencia: {e}")
            return False
    
    @staticmethod
    def get_reading_order(bboxes: List[List[float]]) -> List[int]:
        """
        Determina el orden de lectura para un conjunto de bounding boxes.
        
        Args:
            bboxes: Lista de bounding boxes [[x0, y0, x1, y1], ...]
            
        Returns:
            List[int]: Índices en orden de lectura
        """
        try:
            if not bboxes:
                return []
            
            # Crear array con coordenadas para ordenamiento
            coords = []
            for i, bbox in enumerate(bboxes):
                # Centro del bbox
                center_x = (bbox[0] + bbox[2]) / 2
                center_y = (bbox[1] + bbox[3]) / 2
                coords.append((i, center_y, center_x))
            
            # Ordenar por coordenada Y primero (de arriba a abajo)
            # y luego por coordenada X (de izquierda a derecha)
            def should_group_horizontally(coord1, coord2, y_threshold=10.0):
                return abs(coord1[1] - coord2[1]) < y_threshold
            
            # Ordenar globalmente por Y primero
            coords.sort(key=lambda c: c[1])
            
            # Agrupar elementos en la misma línea y ordenar por X
            ordered_indices = []
            i = 0
            while i < len(coords):
                # Buscar todos los elementos en la misma línea
                line_group = [coords[i]]
                j = i + 1
                while j < len(coords) and should_group_horizontally(coords[i], coords[j]):
                    line_group.append(coords[j])
                    j += 1
                
                # Ordenar la línea por X
                line_group.sort(key=lambda c: c[2])
                
                # Añadir índices ordenados
                ordered_indices.extend([c[0] for c in line_group])
                
                # Continuar desde el siguiente elemento no en la línea
                i = j
            
            return ordered_indices
            
        except Exception as e:
            logger.exception(f"Error al determinar orden de lectura: {e}")
            # En caso de error, devolver orden original
            return list(range(len(bboxes)))
    
    @staticmethod
    def detect_columns(bboxes: List[List[float]], page_width: float) -> List[List[int]]:
        """
        Detecta columnas en una página basándose en bounding boxes.
        
        Args:
            bboxes: Lista de bounding boxes [[x0, y0, x1, y1], ...]
            page_width: Ancho de la página
            
        Returns:
            List[List[int]]: Índices agrupados por columna
        """
        try:
            if not bboxes:
                return []
            
            # Identificar posibles divisiones de columna
            x_positions = []
            for bbox in bboxes:
                x_positions.append(bbox[0])  # x0
                x_positions.append(bbox[2])  # x1
            
            # Encontrar espacios vacíos que podrían indicar divisiones de columna
            x_positions.sort()
            gaps = []
            for i in range(1, len(x_positions)):
                gap = x_positions[i] - x_positions[i-1]
                if gap > page_width * 0.05:  # Umbral: 5% del ancho de página
                    gaps.append((x_positions[i-1], x_positions[i], gap))
            
            # Ordenar por tamaño de gap (descendente)
            gaps.sort(key=lambda g: g[2], reverse=True)
            
            # Tomar los N gaps más grandes como divisiones de columna
            max_columns = 3  # Máximo número de columnas a detectar
            if len(gaps) > max_columns - 1:
                gaps = gaps[:max_columns - 1]
            
            # Ordenar por posición
            gaps.sort(key=lambda g: g[0])
            
            # Definir límites de columnas
            column_boundaries = [0]  # Inicio de la página
            for gap in gaps:
                column_boundaries.append((gap[0] + gap[1]) / 2)  # Punto medio del gap
            column_boundaries.append(page_width)  # Final de la página
            
            # Asignar cada bbox a una columna
            columns = [[] for _ in range(len(column_boundaries) - 1)]
            for i, bbox in enumerate(bboxes):
                center_x = (bbox[0] + bbox[2]) / 2
                for j in range(len(column_boundaries) - 1):
                    if column_boundaries[j] <= center_x < column_boundaries[j + 1]:
                        columns[j].append(i)
                        break
            
            return columns
            
        except Exception as e:
            logger.exception(f"Error al detectar columnas: {e}")
            # En caso de error, devolver todos los elementos en una columna
            return [list(range(len(bboxes)))]
    
    @staticmethod
    def merge_bboxes(bboxes: List[List[float]]) -> List[float]:
        """
        Combina múltiples bounding boxes en una sola que las contenga a todas.
        
        Args:
            bboxes: Lista de bounding boxes [[x0, y0, x1, y1], ...]
            
        Returns:
            List[float]: Bounding box combinada [x0, y0, x1, y1]
        """
        try:
            if not bboxes:
                return [0, 0, 0, 0]
            
            # Inicializar con valores extremos
            x0 = min(bbox[0] for bbox in bboxes)
            y0 = min(bbox[1] for bbox in bboxes)
            x1 = max(bbox[2] for bbox in bboxes)
            y1 = max(bbox[3] for bbox in bboxes)
            
            return [x0, y0, x1, y1]
            
        except Exception as e:
            logger.exception(f"Error al combinar bounding boxes: {e}")
            return [0, 0, 0, 0]
    
    @staticmethod
    def bbox_contains(bbox1: List[float], bbox2: List[float], threshold: float = 0.9) -> bool:
        """
        Determina si una bounding box contiene a otra.
        
        Args:
            bbox1: Bounding box contenedora [x0, y0, x1, y1]
            bbox2: Bounding box potencialmente contenida [x0, y0, x1, y1]
            threshold: Umbral de contención (0-1)
            
        Returns:
            bool: True si bbox1 contiene a bbox2
        """
        try:
            # Calcular coordenadas de intersección
            x_left = max(bbox1[0], bbox2[0])
            y_top = max(bbox1[1], bbox2[1])
            x_right = min(bbox1[2], bbox2[2])
            y_bottom = min(bbox1[3], bbox2[3])
            
            # Verificar si hay intersección
            if x_right < x_left or y_bottom < y_top:
                return False
            
            # Calcular áreas
            intersection_area = (x_right - x_left) * (y_bottom - y_top)
            bbox2_area = (bbox2[2] - bbox2[0]) * (bbox2[3] - bbox2[1])
            
            # Evitar división por cero
            if bbox2_area == 0:
                return False
            
            # Calcular porcentaje de contención
            containment = intersection_area / bbox2_area
            
            return containment >= threshold
            
        except Exception as e:
            logger.exception(f"Error al determinar contención: {e}")
            return False