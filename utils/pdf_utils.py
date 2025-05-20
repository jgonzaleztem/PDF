"""
Funciones generales para análisis de PDFs y manipulación de elementos.

Relacionado con:
- Matterhorn: Múltiples checkpoints (estructura, etiquetas, orden de lectura)
- Tagged PDF: 3.2.1 (semántica apropiada), 3.2.2 (orden de lectura)
"""

import re
import fitz  # PyMuPDF
import numpy as np
from collections import defaultdict
from typing import Dict, List, Tuple, Optional, Any, Union
from loguru import logger


def extract_text_by_area(page, rect) -> str:
    """
    Extrae texto de un área específica de una página.
    
    Args:
        page (fitz.Page): Objeto página de PyMuPDF
        rect (tuple): Rectángulo (x0, y0, x1, y1)
        
    Returns:
        str: Texto extraído del área
    """
    try:
        # Rectángulo fitz
        rect = fitz.Rect(rect)
        
        # Extraer texto del área
        text = page.get_text("text", clip=rect)
        
        return text.strip()
    except Exception as e:
        logger.error(f"Error al extraer texto por área: {str(e)}")
        return ""


def get_visual_elements(page, include_invisible=False) -> List[Dict]:
    """
    Obtiene elementos visuales de una página (texto, imágenes, enlaces).
    
    Args:
        page (fitz.Page): Objeto página de PyMuPDF
        include_invisible (bool): Si se incluyen elementos invisibles
        
    Returns:
        List[Dict]: Lista de elementos visuales con posición y tipo
    """
    elements = []
    
    try:
        # Obtener bloques de texto
        blocks = page.get_text("dict")["blocks"]
        for block in blocks:
            if block["type"] == 0:  # Bloque de texto
                for line in block["lines"]:
                    for span in line["spans"]:
                        # Verificar si es texto invisible (modo de renderizado 3)
                        is_invisible = span.get("flags", 0) & 16 > 0  # bit 4 es invisible
                        if not is_invisible or include_invisible:
                            elements.append({
                                "type": "text",
                                "rect": [span["bbox"][0], span["bbox"][1], span["bbox"][2], span["bbox"][3]],
                                "text": span["text"],
                                "font": span["font"],
                                "size": span["size"],
                                "color": span["color"],
                                "flags": span.get("flags", 0),
                                "is_bold": bool(span.get("flags", 0) & 2),  # bit 1 es negrita
                                "is_italic": bool(span.get("flags", 0) & 1)  # bit 0 es cursiva
                            })
        
        # Obtener imágenes
        for img_index, img in enumerate(page.get_images(full=True)):
            xref = img[0]
            bbox = page.get_image_bbox(img)
            if bbox:
                elements.append({
                    "type": "image",
                    "rect": [bbox.x0, bbox.y0, bbox.x1, bbox.y1],
                    "xref": xref,
                    "id": f"img{img_index}",
                    "width": img[2],
                    "height": img[3],
                    "colorspace": img[5]
                })
        
        # Obtener enlaces
        for link in page.get_links():
            link_element = {
                "type": "link",
                "rect": [link["from"].x0, link["from"].y0, link["from"].x1, link["from"].y1]
            }
            
            # Añadir destino según tipo de enlace
            if "uri" in link:
                link_element["uri"] = link["uri"]
                link_element["link_type"] = "uri"
            elif "page" in link:
                link_element["page"] = link["page"]
                link_element["link_type"] = "internal"
            
            elements.append(link_element)
        
        # Obtener anotaciones (incluyendo formularios)
        for annot in page.annots():
            annot_type = annot.type[1]
            annot_rect = list(annot.rect)
            
            # Solo incluir anotaciones visibles (no ocultas)
            if annot.flags & 2 == 0:  # bit 1 es Hidden flag
                annot_element = {
                    "type": "annotation",
                    "subtype": annot_type,
                    "rect": annot_rect,
                    "contents": annot.info.get("content", "")
                }
                
                # Extraer información específica según tipo
                if annot_type == "Widget":  # Formulario
                    field_type = annot.widget_type
                    annot_element["field_type"] = field_type
                    annot_element["field_name"] = annot.field_name if hasattr(annot, "field_name") else ""
                    annot_element["field_value"] = annot.field_value if hasattr(annot, "field_value") else ""
                    
                    # Buscar texto alternativo (TU - texto de interfaz de usuario)
                    tu = _get_field_tu(annot)
                    if tu:
                        annot_element["tu"] = tu
                
                elements.append(annot_element)
        
        return elements
    except Exception as e:
        logger.error(f"Error al obtener elementos visuales: {str(e)}")
        return []


def _get_field_tu(annot) -> Optional[str]:
    """
    Extrae el texto de interfaz de usuario (TU) de un campo de formulario.
    Importante para cumplir con 28-005 de Matterhorn.
    
    Args:
        annot: Anotación de formulario
        
    Returns:
        Optional[str]: Texto TU o None
    """
    try:
        if hasattr(annot, "xref"):
            xref = annot.xref
            doc = annot.parent.parent
            
            # Obtener objeto del formulario
            obj = doc.xref_object(xref)
            if obj and "TU" in obj:
                return obj["TU"]
    except Exception as e:
        logger.debug(f"Error al extraer TU: {str(e)}")
    
    return None


def detect_reading_order(elements: List[Dict]) -> List[int]:
    """
    Detecta orden de lectura natural para elementos visuales.
    Importante para cumplir con 09-001 de Matterhorn.
    
    Args:
        elements (list): Lista de elementos visuales con posición
        
    Returns:
        list: Lista de índices de elementos en orden de lectura
    """
    if not elements:
        return []
    
    try:
        # Agrupar elementos por líneas basado en superposición vertical
        y_tolerance = min(10, max(3, _calculate_dynamic_y_tolerance(elements)))
        
        # Ordenar elementos inicialmente por Y (top-to-bottom)
        sorted_elements = sorted(enumerate(elements), key=lambda x: x[1]["rect"][1])
        
        # Agrupar en líneas
        lines = []
        current_line = []
        current_y_min = None
        current_y_max = None
        
        for idx, elem in sorted_elements:
            y_top = elem["rect"][1]
            y_bottom = elem["rect"][3]
            
            # Primera línea o nuevo elemento está en otra línea
            if current_y_min is None or y_top > current_y_max + y_tolerance:
                # Si ya teníamos elementos, guardar línea actual
                if current_line:
                    lines.append(current_line)
                
                # Iniciar nueva línea
                current_line = [(idx, elem)]
                current_y_min = y_top
                current_y_max = y_bottom
            else:
                # Elemento en la misma línea
                current_line.append((idx, elem))
                current_y_min = min(current_y_min, y_top)
                current_y_max = max(current_y_max, y_bottom)
        
        # Añadir última línea
        if current_line:
            lines.append(current_line)
        
        # Ordenar elementos dentro de cada línea por X (left-to-right)
        # y considerar columnas si están presentes
        columns = _detect_columns(elements)
        if len(columns) > 1:
            # Múltiples columnas - agrupar líneas por columna y reordenar
            reading_order = _apply_column_based_order(lines, elements, columns)
        else:
            # Sin columnas - simplemente ordenar líneas de izquierda a derecha
            for i, line in enumerate(lines):
                lines[i] = sorted(line, key=lambda x: x[1]["rect"][0])
            
            # Aplanar la lista de líneas
            reading_order = []
            for line in lines:
                reading_order.extend([idx for idx, _ in line])
        
        return reading_order
    except Exception as e:
        logger.error(f"Error al detectar orden de lectura: {str(e)}")
        return list(range(len(elements)))


def _calculate_dynamic_y_tolerance(elements: List[Dict]) -> float:
    """
    Calcula dinámicamente la tolerancia vertical basada en la altura media 
    de los elementos de texto.
    
    Args:
        elements: Lista de elementos visuales
        
    Returns:
        float: Tolerancia Y calculada
    """
    # Recopilar alturas de texto
    text_heights = []
    for elem in elements:
        if elem["type"] == "text":
            height = elem["rect"][3] - elem["rect"][1]
            if height > 0:
                text_heights.append(height)
    
    # Calcular tolerancia basada en altura promedio
    if text_heights:
        mean_height = sum(text_heights) / len(text_heights)
        # Usar 2/3 de la altura promedio como tolerancia
        return max(3, mean_height * 0.67)
    else:
        return 10  # Valor por defecto


def _detect_columns(elements: List[Dict]) -> List[Tuple[float, float]]:
    """
    Detecta columnas en una página basándose en el análisis de la distribución
    espacial de los elementos.
    
    Args:
        elements: Lista de elementos visuales
        
    Returns:
        List[Tuple[float, float]]: Lista de columnas [(x_min1, x_max1), (x_min2, x_max2), ...]
    """
    if not elements:
        return [(0, 100)]  # Valor por defecto si no hay elementos
    
    try:
        # Extraer márgenes izquierdos y anchos de bloques de texto
        left_margins = []
        right_margins = []
        
        for elem in elements:
            if elem["type"] == "text" and len(elem.get("text", "").strip()) > 0:
                left_margins.append(elem["rect"][0])
                right_margins.append(elem["rect"][2])
        
        if not left_margins:
            return [(0, 100)]  # No hay suficientes elementos
        
        # Obtener límites de la página
        page_left = min(left_margins) if left_margins else 0
        page_right = max(right_margins) if right_margins else 100
        
        # Agrupar márgenes izquierdos usando clustering
        grouped_margins = _cluster_values(left_margins, threshold=20)
        
        # Si tenemos pocos grupos, probablemente no hay columnas
        if len(grouped_margins) <= 1:
            return [(page_left, page_right)]
        
        # Verificar si hay gaps consistentes que indiquen columnas
        columns = []
        prev_right = page_left
        
        # Ordenar los grupos de izquierda a derecha
        grouped_margins.sort()
        
        for margin_group in grouped_margins:
            # Encontrar elementos cuyo margen izquierdo está en este grupo
            col_elements = [e for e in elements if e["type"] == "text" and 
                           abs(e["rect"][0] - margin_group) < 20]
            
            if not col_elements:
                continue
                
            # Encontrar el margen derecho de esta columna
            col_right = max(e["rect"][2] for e in col_elements)
            
            # Añadir columna solo si tiene un ancho razonable
            if col_right - margin_group > 20:
                columns.append((margin_group, col_right))
            
            prev_right = col_right
        
        # Si no se encontraron columnas, usar toda la página
        if not columns:
            return [(page_left, page_right)]
        
        return columns
        
    except Exception as e:
        logger.error(f"Error al detectar columnas: {str(e)}")
        return [(0, 100)]


def _cluster_values(values: List[float], threshold: float) -> List[float]:
    """
    Agrupa valores similares usando un umbral.
    
    Args:
        values: Lista de valores a agrupar
        threshold: Umbral de distancia para considerar en el mismo grupo
        
    Returns:
        List[float]: Representantes de cada grupo
    """
    if not values:
        return []
    
    # Ordenar valores
    sorted_values = sorted(values)
    
    # Inicializar grupos
    groups = []
    current_group = [sorted_values[0]]
    
    # Agrupar valores similares
    for value in sorted_values[1:]:
        if value - current_group[0] < threshold:
            current_group.append(value)
        else:
            # Calcular promedio del grupo actual
            groups.append(sum(current_group) / len(current_group))
            current_group = [value]
    
    # Añadir último grupo
    if current_group:
        groups.append(sum(current_group) / len(current_group))
    
    return groups


def _apply_column_based_order(lines: List[List[Tuple]], elements: List[Dict], 
                            columns: List[Tuple[float, float]]) -> List[int]:
    """
    Reorganiza el orden de lectura considerando estructura de columnas.
    
    Args:
        lines: Líneas de elementos agrupados
        elements: Lista original de elementos
        columns: Definición de columnas [(x_min1, x_max1), (x_min2, x_max2), ...]
        
    Returns:
        List[int]: Índices en orden de lectura
    """
    # Asignar cada línea a su columna principal
    column_lines = [[] for _ in range(len(columns))]
    
    for line in lines:
        # Para cada línea, determinar en qué columna está principalmente
        col_counts = [0] * len(columns)
        
        for idx, elem in line:
            # Rectángulo del elemento
            x_min = elem["rect"][0]
            x_max = elem["rect"][2]
            
            # Verificar solapamiento con cada columna
            for i, (col_min, col_max) in enumerate(columns):
                # Si el elemento está principalmente en esta columna
                if x_min >= col_min and x_max <= col_max:
                    col_counts[i] += 1
                    break
                # Si hay solapamiento parcial, considerar la de mayor área
                elif max(0, min(x_max, col_max) - max(x_min, col_min)) > 0:
                    overlap = max(0, min(x_max, col_max) - max(x_min, col_min))
                    elem_width = x_max - x_min
                    if overlap / elem_width > 0.5:  # >50% en esta columna
                        col_counts[i] += 1
        
        # Asignar la línea a la columna con más elementos
        if sum(col_counts) > 0:
            main_column = col_counts.index(max(col_counts))
            column_lines[main_column].append(line)
        else:
            # Si no se puede determinar, asignar a la columna que mejor se alinee
            middle_x = sum(elem["rect"][0] + elem["rect"][2] for _, elem in line) / (2 * len(line))
            distances = [abs(middle_x - (col[0] + col[1])/2) for col in columns]
            main_column = distances.index(min(distances))
            column_lines[main_column].append(line)
    
    # Reorganizar elementos en orden Z: de arriba a abajo por cada columna
    reading_order = []
    
    for col_idx in range(len(columns)):
        col_elements = []
        
        # Ordenar líneas en la columna por posición vertical
        sorted_lines = sorted(column_lines[col_idx], 
                            key=lambda line: min(elem["rect"][1] for _, elem in line))
        
        # Para cada línea en esta columna
        for line in sorted_lines:
            # Ordenar elementos de la línea de izquierda a derecha
            sorted_line = sorted(line, key=lambda x: x[1]["rect"][0])
            # Añadir índices a la lista final
            col_elements.extend([idx for idx, _ in sorted_line])
        
        reading_order.extend(col_elements)
    
    return reading_order


def analyze_text_style(page, doc=None) -> Dict:
    """
    Analiza estilos de texto en una página para identificar jerarquía visual.
    Útil para detectar encabezados, listas, etc.
    
    Args:
        page (fitz.Page): Objeto página de PyMuPDF
        doc (fitz.Document): Documento completo (opcional)
        
    Returns:
        dict: Información sobre jerarquía visual de la página
    """
    try:
        # Obtener bloques de texto
        blocks = page.get_text("dict")["blocks"]
        
        # Recopilar información de estilos
        styles = {}
        headings = []
        paragraphs = []
        list_items = []
        
        # Patrones para detectar elementos de lista
        list_patterns = [
            r'^\s*[•⦿⦾⦿○●◦▪▫]\s',  # Bullets
            r'^\s*\d+\.\s',         # Números con punto
            r'^\s*\(\d+\)\s',       # Números con paréntesis
            r'^\s*[a-z]\)\s',       # Letras con paréntesis
            r'^\s*[ivxlcdm]+\.\s',  # Números romanos en minúsculas
            r'^\s*[IVXLCDM]+\.\s',  # Números romanos en mayúsculas
        ]
        
        # Calcular estadísticas de tamaño de fuente si hay documento
        font_sizes = []
        if doc:
            for p in range(len(doc)):
                page_dict = doc[p].get_text("dict")
                for block in page_dict["blocks"]:
                    if block["type"] == 0:
                        for line in block["lines"]:
                            for span in line["spans"]:
                                font_sizes.append(span["size"])
        
        avg_font_size = sum(font_sizes) / max(len(font_sizes), 1) if font_sizes else 12
        
        # Analizar bloques
        for block in blocks:
            if block["type"] == 0:  # Bloque de texto
                # Extraer texto del bloque
                block_text = ""
                largest_font = 0
                is_bold = False
                
                for line in block["lines"]:
                    for span in line["spans"]:
                        block_text += span["text"]
                        largest_font = max(largest_font, span["size"])
                        # Detectar negrita por nombre de fuente o flags
                        if "bold" in span["font"].lower() or (span.get("flags", 0) & 2 > 0):
                            is_bold = True
                
                block_text = block_text.strip()
                if not block_text:
                    continue
                
                # Registrar información de estilo
                style_key = f"{largest_font:.1f}"
                if style_key not in styles:
                    styles[style_key] = {
                        "size": largest_font,
                        "count": 0,
                        "text_samples": []
                    }
                
                styles[style_key]["count"] += 1
                if len(styles[style_key]["text_samples"]) < 3:
                    styles[style_key]["text_samples"].append(block_text[:50])
                
                # Heurísticas mejoradas para detectar tipo de elemento
                # Detectar si es encabezado
                is_heading = False
                heading_level = 0
                
                # Por tamaño - comparar con promedio
                if largest_font > avg_font_size * 1.6:
                    is_heading = True
                    heading_level = 1
                elif largest_font > avg_font_size * 1.4:
                    is_heading = True
                    heading_level = 2
                elif largest_font > avg_font_size * 1.2:
                    is_heading = True
                    heading_level = 3
                
                # Por formato - negrita con texto corto
                if is_bold and len(block_text) < 100 and not is_heading:
                    is_heading = True
                    heading_level = min(heading_level if heading_level > 0 else 5, 4)
                
                # Por posición - primer bloque de la página
                page_blocks = [b for b in blocks if b["type"] == 0]
                if page_blocks and page_blocks[0] == block and not is_heading:
                    is_heading = True
                    heading_level = min(heading_level if heading_level > 0 else 5, 1)
                
                # Detectar si es elemento de lista
                is_list_item = False
                for pattern in list_patterns:
                    if re.match(pattern, block_text):
                        is_list_item = True
                        break
                
                # Clasificar bloque
                block_info = {
                    "text": block_text,
                    "font_size": largest_font,
                    "rect": [block["bbox"][0], block["bbox"][1], block["bbox"][2], block["bbox"][3]],
                    "is_bold": is_bold
                }
                
                if is_heading:
                    block_info["level"] = heading_level
                    headings.append(block_info)
                elif is_list_item:
                    list_items.append(block_info)
                else:
                    paragraphs.append(block_info)
        
        # Analizar jerarquía de encabezados usando tamaños relativos
        if headings:
            # Ordenar encabezados por tamaño descendente
            headings.sort(key=lambda x: (
                -x.get("font_size", 0),  # Mayor tamaño primero
                x.get("rect", [0, 0, 0, 0])[1]  # Luego por posición vertical
            ))
            
            # Asignar niveles provisionales si no se asignaron antes
            unique_sizes = sorted(set(h.get("font_size", 0) for h in headings), reverse=True)
            size_levels = {size: i+1 for i, size in enumerate(unique_sizes)}
            
            for heading in headings:
                if "level" not in heading or heading["level"] == 0:
                    heading["level"] = size_levels[heading.get("font_size", 0)]
        
        return {
            "styles": styles,
            "headings": headings,
            "paragraphs": paragraphs,
            "list_items": list_items,
            "avg_font_size": avg_font_size
        }
    except Exception as e:
        logger.error(f"Error al analizar estilos de texto: {str(e)}")
        return {
            "styles": {},
            "headings": [],
            "paragraphs": [],
            "list_items": [],
            "avg_font_size": 12
        }


def detect_tables(page) -> List[Dict]:
    """
    Detecta posibles tablas en una página.
    Relevante para checkpoints 15-001 a 15-005 de Matterhorn.
    
    Args:
        page (fitz.Page): Objeto página de PyMuPDF
        
    Returns:
        list: Lista de posibles tablas con celdas
    """
    tables = []
    
    try:
        # Estrategia 1: Detectar mediante líneas de dibujo
        tables_from_lines = _detect_tables_from_lines(page)
        if tables_from_lines:
            tables.extend(tables_from_lines)
        
        # Estrategia 2: Detectar mediante alineación de texto
        tables_from_text = _detect_tables_from_text_alignment(page)
        if tables_from_text:
            # Verificar si hay solapamiento con tablas ya detectadas
            # y solo añadir si no están duplicadas
            tables.extend([t for t in tables_from_text if not _is_table_duplicate(t, tables)])
        
        # Para cada tabla, extraer texto de las celdas
        for table in tables:
            for cell in table.get("cells", []):
                cell_text = extract_text_by_area(page, cell["rect"])
                cell["text"] = cell_text
        
        return tables
    except Exception as e:
        logger.error(f"Error al detectar tablas: {str(e)}")
        return []


def _detect_tables_from_lines(page) -> List[Dict]:
    """
    Detecta tablas basadas en líneas horizontales y verticales.
    
    Args:
        page (fitz.Page): Objeto página
        
    Returns:
        List[Dict]: Tablas detectadas
    """
    tables = []
    
    # Obtener líneas de la página
    paths = page.get_drawings()
    lines = []
    
    for path in paths:
        for item in path["items"]:
            if item["type"] == "l":  # Línea
                p1 = item["rect"][0:2]  # Punto inicial (x0, y0)
                p2 = item["rect"][2:4]  # Punto final (x1, y1)
                lines.append({
                    "p1": p1,
                    "p2": p2,
                    "is_horizontal": abs(p1[1] - p2[1]) < 2,
                    "is_vertical": abs(p1[0] - p2[0]) < 2,
                    "length": max(abs(p1[0] - p2[0]), abs(p1[1] - p2[1]))
                })
    
    # Si hay pocas líneas, probablemente no hay tablas
    if len(lines) < 4:
        return tables
    
    # Filtrar líneas muy cortas (pueden ser subrayados o adornos)
    avg_line_length = sum(line["length"] for line in lines) / max(1, len(lines))
    lines = [line for line in lines if line["length"] > avg_line_length * 0.3]
    
    # Identificar líneas horizontales y verticales
    h_lines = sorted([l for l in lines if l["is_horizontal"]], key=lambda l: l["p1"][1])
    v_lines = sorted([l for l in lines if l["is_vertical"]], key=lambda l: l["p1"][0])
    
    # Si no hay suficientes líneas en ambas direcciones, no hay tablas
    if len(h_lines) < 2 or len(v_lines) < 2:
        return tables
    
    # Detectar intersecciones de líneas para encontrar celdas
    intersections = _find_line_intersections(h_lines, v_lines)
    
    # Si hay pocas intersecciones, probablemente no hay tablas
    if len(intersections) < 4:
        return tables
    
    # Agrupar intersecciones en rejillas
    grids = _group_intersections_into_grids(intersections)
    
    # Convertir rejillas en tablas
    for grid in grids:
        if len(grid["rows"]) < 2 or len(grid["cols"]) < 2:
            continue
            
        table = {
            "rect": [
                grid["cols"][0] - 1,
                grid["rows"][0] - 1, 
                grid["cols"][-1] + 1,
                grid["rows"][-1] + 1
            ],
            "rows": len(grid["rows"]),
            "cols": len(grid["cols"]),
            "cells": []
        }
        
        # Crear celdas
        for i in range(len(grid["rows"]) - 1):
            for j in range(len(grid["cols"]) - 1):
                cell = {
                    "rect": [
                        grid["cols"][j], 
                        grid["rows"][i], 
                        grid["cols"][j+1], 
                        grid["rows"][i+1]
                    ],
                    "row": i,
                    "col": j
                }
                table["cells"].append(cell)
        
        tables.append(table)
    
    return tables


def _find_line_intersections(h_lines, v_lines, tolerance=2) -> List[Tuple[float, float]]:
    """
    Encuentra puntos de intersección entre líneas horizontales y verticales.
    
    Returns:
        List[Tuple[float, float]]: Lista de puntos de intersección (x, y)
    """
    intersections = []
    
    for h in h_lines:
        h_y = h["p1"][1]  # Coordenada Y de la línea horizontal
        h_x_min = min(h["p1"][0], h["p2"][0])
        h_x_max = max(h["p1"][0], h["p2"][0])
        
        for v in v_lines:
            v_x = v["p1"][0]  # Coordenada X de la línea vertical
            v_y_min = min(v["p1"][1], v["p2"][1])
            v_y_max = max(v["p1"][1], v["p2"][1])
            
            # Verificar si las líneas se cruzan
            if (h_x_min - tolerance <= v_x <= h_x_max + tolerance and 
                v_y_min - tolerance <= h_y <= v_y_max + tolerance):
                intersections.append((v_x, h_y))
    
    return intersections


def _group_intersections_into_grids(intersections, tolerance=5) -> List[Dict]:
    """
    Agrupa intersecciones en rejillas que forman tablas.
    
    Returns:
        List[Dict]: Lista de rejillas, cada una con filas y columnas
    """
    if not intersections:
        return []
    
    # Agrupar coordenadas Y para identificar filas
    y_values = [y for _, y in intersections]
    rows = _cluster_values(y_values, tolerance)
    
    # Agrupar coordenadas X para identificar columnas
    x_values = [x for x, _ in intersections]
    cols = _cluster_values(x_values, tolerance)
    
    # Formar rejillas
    grids = []
    
    # Verificar si hay suficientes filas y columnas para formar una tabla
    if len(rows) >= 2 and len(cols) >= 2:
        # Verificar densidad de intersecciones
        # Una buena tabla debe tener intersecciones en una gran parte de las celdas
        
        # Contar intersecciones para cada par (fila, columna)
        cell_counts = defaultdict(int)
        for x, y in intersections:
            # Encontrar la fila y columna más cercanas
            row_idx = min(range(len(rows)), key=lambda i: abs(rows[i] - y))
            col_idx = min(range(len(cols)), key=lambda i: abs(cols[i] - x))
            cell_counts[(row_idx, col_idx)] += 1
        
        # Calcular densidad: porcentaje de celdas con intersecciones
        total_cells = len(rows) * len(cols)
        filled_cells = len(cell_counts)
        density = filled_cells / total_cells if total_cells > 0 else 0
        
        # Si la densidad es alta, es probablemente una tabla
        if density >= 0.5:  # Al menos 50% de las celdas tiene intersecciones
            grids.append({
                "rows": rows,
                "cols": cols,
                "density": density
            })
    
    return grids


def _detect_tables_from_text_alignment(page) -> List[Dict]:
    """
    Detecta tablas basadas en alineación de texto, útil cuando
    no hay líneas de cuadrícula.
    
    Args:
        page (fitz.Page): Objeto página
        
    Returns:
        List[Dict]: Tablas detectadas
    """
    tables = []
    
    try:
        # Obtener bloques de texto
        blocks = page.get_text("dict")["blocks"]
        text_blocks = [b for b in blocks if b["type"] == 0]
        
        if len(text_blocks) < 4:  # Pocas probabilidades de tabla
            return []
        
        # Extraer líneas de texto
        lines = []
        for block in text_blocks:
            for line in block["lines"]:
                text = "".join(span["text"] for span in line["spans"])
                if text.strip():
                    lines.append({
                        "text": text,
                        "rect": line["bbox"],
                        "spans": len(line["spans"]),
                        "y": line["bbox"][1]  # Coordenada Y superior
                    })
        
        # Agrupar líneas cercanas verticalmente
        line_groups = []
        current_group = []
        
        # Ordenar líneas por Y
        sorted_lines = sorted(lines, key=lambda l: l["y"])
        
        for i, line in enumerate(sorted_lines):
            if i == 0:
                current_group = [line]
            else:
                # Calcular espacio vertical respecto a línea anterior
                prev_line = sorted_lines[i-1]
                gap = line["y"] - (prev_line["rect"][3])  # Distancia entre líneas
                avg_height = (line["rect"][3] - line["rect"][1] + 
                             prev_line["rect"][3] - prev_line["rect"][1]) / 2
                
                # Si el espacio es menor a la altura promedio, pertenece al mismo grupo
                if gap < avg_height * 1.5:
                    current_group.append(line)
                else:
                    # Nuevo grupo
                    if len(current_group) >= 2:  # Solo considerar grupos con múltiples líneas
                        line_groups.append(current_group)
                    current_group = [line]
        
        # Añadir último grupo
        if len(current_group) >= 2:
            line_groups.append(current_group)
        
        # Analizar cada grupo para detectar alineación tabular
        for group in line_groups:
            # Verificar si hay múltiples alineaciones horizontales constantes
            # (Señal de columnas)
            x_positions = []
            
            for line in group:
                for span in line.get("spans", []):
                    x_positions.append(span["bbox"][0])
            
            # Agrupar posiciones X similares
            x_clusters = _cluster_values(x_positions, threshold=10)
            
            # Si hay múltiples columnas, crear tabla
            if len(x_clusters) >= 2:
                # Calcular límites de la tabla
                x_min = min(line["rect"][0] for line in group)
                x_max = max(line["rect"][2] for line in group)
                y_min = min(line["rect"][1] for line in group)
                y_max = max(line["rect"][3] for line in group)
                
                table = {
                    "rect": [x_min, y_min, x_max, y_max],
                    "rows": len(group),
                    "cols": len(x_clusters),
                    "cells": []
                }
                
                # Crear celdas (simplificado - cada línea es una fila)
                for row_idx, line in enumerate(group):
                    col_positions = [x_min] + x_clusters + [x_max]
                    
                    for col_idx in range(len(col_positions) - 1):
                        cell = {
                            "rect": [
                                col_positions[col_idx],
                                line["rect"][1],
                                col_positions[col_idx + 1],
                                line["rect"][3]
                            ],
                            "row": row_idx,
                            "col": col_idx
                        }
                        table["cells"].append(cell)
                
                tables.append(table)
        
        return tables
    except Exception as e:
        logger.error(f"Error al detectar tablas por alineación: {str(e)}")
        return []


def _is_table_duplicate(new_table, existing_tables, overlap_threshold=0.7) -> bool:
    """
    Verifica si una tabla es duplicada (tiene alta superposición con otra).
    
    Args:
        new_table: Nueva tabla a verificar
        existing_tables: Lista de tablas existentes
        overlap_threshold: Umbral de superposición para considerar duplicada
        
    Returns:
        bool: True si la tabla es duplicada
    """
    new_rect = new_table["rect"]
    
    for table in existing_tables:
        old_rect = table["rect"]
        
        # Calcular área de superposición
        x_overlap = max(0, min(new_rect[2], old_rect[2]) - max(new_rect[0], old_rect[0]))
        y_overlap = max(0, min(new_rect[3], old_rect[3]) - max(new_rect[1], old_rect[1]))
        overlap_area = x_overlap * y_overlap
        
        # Calcular áreas
        new_area = (new_rect[2] - new_rect[0]) * (new_rect[3] - new_rect[1])
        old_area = (old_rect[2] - old_rect[0]) * (old_rect[3] - old_rect[1])
        
        # Verificar superposición relativa
        if new_area > 0 and old_area > 0:
            relative_overlap = overlap_area / min(new_area, old_area)
            if relative_overlap > overlap_threshold:
                return True
    
    return False


def detect_lists(page) -> List[Dict]:
    """
    Detecta listas en una página. Relevante para checkpoints 16-001 a 16-003
    de Matterhorn.
    
    Args:
        page (fitz.Page): Objeto página de PyMuPDF
        
    Returns:
        list: Lista de posibles listas detectadas
    """
    lists = []
    
    try:
        # Obtener bloques de texto
        blocks = page.get_text("dict")["blocks"]
        
        # Patrones para detectar elementos de lista
        bullet_patterns = [
            r'^\s*[•⦿⦾⦿○●◦▪▫]\s'  # Bullets
        ]
        
        numbered_patterns = [
            r'^\s*\d+\.\s',         # Números con punto
            r'^\s*\(\d+\)\s',       # Números con paréntesis
            r'^\s*[a-z]\)\s',       # Letras con paréntesis
            r'^\s*[ivxlcdm]+\.\s',  # Números romanos en minúsculas
            r'^\s*[IVXLCDM]+\.\s',  # Números romanos en mayúsculas
        ]
        
        # Buscar líneas consecutivas que podrían ser elementos de lista
        potential_list_items = []
        
        for block in blocks:
            if block["type"] == 0:  # Bloque de texto
                for line in block["lines"]:
                    text = "".join(span["text"] for span in line["spans"])
                    text = text.strip()
                    
                    # Verificar si coincide con algún patrón de lista
                    is_bullet = any(re.match(pattern, text) for pattern in bullet_patterns)
                    is_numbered = any(re.match(pattern, text) for pattern in numbered_patterns)
                    
                    if is_bullet or is_numbered:
                        item = {
                            "text": text,
                            "rect": line["bbox"],
                            "y": line["bbox"][1],  # Posición Y para ordenar
                            "type": "bullet" if is_bullet else "numbered",
                            "indent": line["bbox"][0]  # Nivel de indentación
                        }
                        potential_list_items.append(item)
        
        # Ordenar por posición vertical
        potential_list_items.sort(key=lambda x: x["y"])
        
        # Agrupar elementos en listas
        current_list = []
        current_type = None
        current_indent = None
        
        for item in potential_list_items:
            # Verificar si pertenece a la lista actual
            if (not current_list or 
                (item["type"] == current_type and abs(item["indent"] - current_indent) < 5)):
                # Continúa la lista actual
                if not current_list:
                    current_type = item["type"]
                    current_indent = item["indent"]
                current_list.append(item)
            else:
                # Finaliza lista actual e inicia una nueva
                if len(current_list) >= 2:  # Solo considerar como lista si hay múltiples elementos
                    list_rect = [
                        min(i["rect"][0] for i in current_list),
                        min(i["rect"][1] for i in current_list),
                        max(i["rect"][2] for i in current_list),
                        max(i["rect"][3] for i in current_list)
                    ]
                    
                    lists.append({
                        "rect": list_rect,
                        "type": current_type,
                        "items": current_list,
                        "count": len(current_list)
                    })
                
                # Iniciar nueva lista
                current_list = [item]
                current_type = item["type"]
                current_indent = item["indent"]
        
        # Procesar última lista
        if len(current_list) >= 2:
            list_rect = [
                min(i["rect"][0] for i in current_list),
                min(i["rect"][1] for i in current_list),
                max(i["rect"][2] for i in current_list),
                max(i["rect"][3] for i in current_list)
            ]
            
            lists.append({
                "rect": list_rect,
                "type": current_type,
                "items": current_list,
                "count": len(current_list)
            })
        
        return lists
    except Exception as e:
        logger.error(f"Error al detectar listas: {str(e)}")
        return []


def detect_language(text: str) -> str:
    """
    Detecta el idioma más probable del texto.
    Relevante para checkpoint 11-007 de Matterhorn.
    
    Args:
        text (str): Texto a analizar
        
    Returns:
        str: Código de idioma detectado ('es', 'en', etc.)
    """
    try:
        # Implementación simple basada en n-gramas y palabras comunes
        # En una implementación real, se usaría una biblioteca como langdetect
        
        # Patrones comunes por idioma
        lang_patterns = {
            'es': ['de la', 'el ', 'la ', 'que ', 'en ', 'y ', 'por ', 'con ', 'para ', 'es '],
            'en': ['the ', 'and ', 'of ', 'to ', 'in ', 'is ', 'that ', 'for ', 'it ', 'with '],
            'fr': ['le ', 'la ', 'les ', 'de ', 'et ', 'en ', 'que ', 'une ', 'pour ', 'dans '],
            'de': ['der ', 'die ', 'und ', 'den ', 'in ', 'von ', 'zu ', 'das ', 'mit ', 'dem '],
            'it': ['il ', 'la ', 'di ', 'e ', 'che ', 'in ', 'per ', 'un ', 'del ', 'con ']
        }
        
        # Normalizar texto
        text = text.lower()
        
        # Contar coincidencias por idioma
        lang_scores = {lang: 0 for lang in lang_patterns}
        
        for lang, patterns in lang_patterns.items():
            for pattern in patterns:
                lang_scores[lang] += text.count(pattern)
        
        # Determinar idioma más probable
        max_lang = max(lang_scores, key=lang_scores.get)
        
        # Mapear a códigos de idioma para Lang
        lang_map = {
            'es': 'es-ES',
            'en': 'en-US',
            'fr': 'fr-FR',
            'de': 'de-DE',
            'it': 'it-IT'
        }
        
        return lang_map.get(max_lang, 'en-US')
    except Exception as e:
        logger.error(f"Error al detectar idioma: {str(e)}")
        return 'en-US'  # Valor predeterminado


def analyze_document_language(doc) -> str:
    """
    Analiza e identifica el idioma principal del documento.
    
    Args:
        doc (fitz.Document): Documento PyMuPDF
        
    Returns:
        str: Código de idioma detectado ('es-ES', 'en-US', etc.)
    """
    try:
        # Extraer texto del documento (primeras 5 páginas para rendimiento)
        text = ""
        for page_num in range(min(5, len(doc))):
            text += doc[page_num].get_text("text")
            if len(text) > 10000:  # Limitar a 10K caracteres
                break
        
        return detect_language(text)
    except Exception as e:
        logger.error(f"Error al analizar idioma del documento: {str(e)}")
        return "en-US"  # Valor predeterminado


def check_text_font_consistency(doc) -> Dict:
    """
    Comprueba la consistencia de fuentes en el documento.
    Útil para detectar problemas como mapeo Unicode ausente (10-001).
    
    Args:
        doc (fitz.Document): Documento PyMuPDF
        
    Returns:
        dict: Informe de consistencia de fuentes
    """
    fonts = {}
    issues = []
    
    try:
        # Analizar fuentes en todo el documento
        for page_num in range(len(doc)):
            page = doc[page_num]
            
            # Obtener texto en formato JSON
            text_page = page.get_text("dict")
            
            for block in text_page["blocks"]:
                if block["type"] == 0:  # Bloque de texto
                    for line in block["lines"]:
                        for span in line["spans"]:
                            font_name = span["font"]
                            text = span["text"]
                            
                            # Registrar fuente
                            if font_name not in fonts:
                                fonts[font_name] = {
                                    "count": 0,
                                    "text_samples": [],
                                    "unicode_mapped": True,
                                    "pages": set(),
                                    "sizes": set()
                                }
                            
                            fonts[font_name]["count"] += 1
                            fonts[font_name]["pages"].add(page_num)
                            fonts[font_name]["sizes"].add(span["size"])
                            
                            if len(fonts[font_name]["text_samples"]) < 5:
                                fonts[font_name]["text_samples"].append(text[:20])
                            
                            # Detectar problemas de codificación
                            for char in text:
                                # Caracteres que pueden indicar problemas de mapeo Unicode
                                if (ord(char) < 32 and char not in '\t\n\r') or ord(char) >= 0xFFFD:
                                    fonts[font_name]["unicode_mapped"] = False
                                    issues.append({
                                        "page": page_num,
                                        "font": font_name,
                                        "text": text,
                                        "issue": "Posible falta de mapeo Unicode",
                                        "checkpoint": "10-001"
                                    })
                                    break
        
        # Convertir páginas y tamaños a listas para JSON
        for font_name in fonts:
            fonts[font_name]["pages"] = sorted(list(fonts[font_name]["pages"]))
            fonts[font_name]["sizes"] = sorted(list(fonts[font_name]["sizes"]))
        
        return {
            "fonts": fonts,
            "issues": issues
        }
    except Exception as e:
        logger.error(f"Error al verificar consistencia de fuentes: {str(e)}")
        return {
            "fonts": {},
            "issues": [{"issue": f"Error durante análisis: {str(e)}"}]
        }


def detect_headings(page, doc=None) -> List[Dict]:
    """
    Detecta encabezados en una página basándose en formato visual.
    Relevante para checkpoints 14-001 a 14-007 de Matterhorn.
    
    Args:
        page (fitz.Page): Objeto página de PyMuPDF
        doc (fitz.Document): Documento completo (opcional)
        
    Returns:
        List[Dict]: Lista de encabezados detectados
    """
    try:
        # Usar analyze_text_style para extraer estilos y posible jerarquía
        styles_info = analyze_text_style(page, doc)
        headings = styles_info.get("headings", [])
        
        # Ordenar encabezados por posición vertical
        headings.sort(key=lambda h: h["rect"][1])
        
        # Verificar secuencia de niveles (no debe saltar más de 1 nivel)
        prev_level = 0
        
        for i, heading in enumerate(headings):
            level = heading.get("level", 0)
            
            # El primer encabezado debería ser H1
            if i == 0 and level > 1:
                heading["warning"] = "El primer encabezado debería ser H1"
            
            # No debe saltar niveles (ej: H1 -> H3)
            elif prev_level > 0 and level > prev_level + 1:
                heading["warning"] = f"Nivel saltado: H{prev_level} a H{level}"
            
            prev_level = level
        
        return headings
    except Exception as e:
        logger.error(f"Error al detectar encabezados: {str(e)}")
        return []


def is_artifact(element: Dict) -> bool:
    """
    Determina si un elemento debería ser considerado un artefacto.
    Relevante para checkpoints 01-001, 01-002 de Matterhorn.
    
    Args:
        element: Elemento visual a comprobar
        
    Returns:
        bool: True si debería ser artefacto
    """
    try:
        # Verificar si es texto invisible (no debe etiquetarse)
        if element.get("type") == "text" and element.get("flags", 0) & 16 > 0:
            return True
        
        # Verificar si es un encabezado/pie de página
        if element.get("type") == "text":
            rect = element.get("rect", [0, 0, 0, 0])
            text = element.get("text", "").strip()
            
            # Heurísticas para detectar encabezados/pies
            # 1. Posición: muy arriba o muy abajo en la página
            is_at_top = rect[1] < 50  # menos de 50 puntos desde la parte superior
            is_at_bottom = rect[3] > 750  # más de 750 puntos desde la parte superior
            
            # 2. Contenido típico de encabezados/pies
            contains_page_number = bool(re.search(r'\b(?:page|página)\s*\d+\b', text, re.I))
            is_document_title = len(text) < 100 and text.isupper()  # Texto corto en mayúsculas
            contains_date = bool(re.search(r'\d{1,2}[/.-]\d{1,2}[/.-]\d{2,4}', text))
            
            # Combinar heurísticas
            if (is_at_top or is_at_bottom) and (contains_page_number or is_document_title or contains_date):
                return True
        
        return False
    except Exception as e:
        logger.error(f"Error al determinar si es artefacto: {str(e)}")
        return False