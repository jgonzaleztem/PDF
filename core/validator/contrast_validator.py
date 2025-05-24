#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Validación de contraste según PDF/UA y WCAG.
Detecta problemas de contraste en texto y elementos visuales.

Este módulo se relaciona con:
- Matterhorn: Checkpoint 04-001 (Color and Contrast)
- Tagged PDF: 5.1.1 (Layout attributes - Color, BackgroundColor)
- WCAG 2.1: 1.4.3 (Contrast Minimum), 1.4.11 (Non-text Contrast)
"""

from typing import Dict, List, Optional, Tuple, Set, Any
import re
import math
from loguru import logger

# Importar utilidades de color del proyecto
from utils.color_utils import (
    normalize_color, calculate_contrast_ratio, is_wcag_aa_compliant, is_wcag_aaa_compliant,
    suggest_accessible_colors, extract_color, rgb_to_hex, get_contrast_level_description,
    get_color_visibility
)

class ContrastValidator:
    """
    Valida el contraste del documento según requisitos de PDF/UA y WCAG.
    Detecta problemas de contraste en texto y elementos visuales.
    """
    
    def __init__(self):
        """Inicializa el validador de contraste"""
        # Niveles de conformidad WCAG
        self.min_contrast_ratio_normal = 4.5  # WCAG AA para texto normal
        self.min_contrast_ratio_large = 3.0   # WCAG AA para texto grande
        self.min_contrast_ratio_normal_aaa = 7.0  # WCAG AAA para texto normal
        self.min_contrast_ratio_large_aaa = 4.5   # WCAG AAA para texto grande
        
        # Umbrales de tamaño de texto
        self.large_text_threshold_pt = 18.0   # 18pt = texto grande
        self.large_text_bold_threshold_pt = 14.0  # 14pt bold = texto grande
        
        # Umbral para considerar que un color es parte del fondo
        self.background_area_threshold = 0.5  # 50% del área del elemento
        
        # Diccionarios para almacenar información de la página
        self.page_bg_colors = {}  # Colores de fondo por página
        
        # Inicializar referencia al PDF loader
        self.pdf_loader = None
        
        logger.info("ContrastValidator inicializado")
    
    def set_pdf_loader(self, pdf_loader):
        """
        Establece la referencia al cargador de PDF.
        
        Args:
            pdf_loader: Instancia de PDFLoader con el documento cargado
        """
        self.pdf_loader = pdf_loader
        logger.debug("PDFLoader establecido en ContrastValidator")
    
    def validate(self, pdf_loader=None) -> List[Dict]:
        """
        Valida el contraste en todo el documento.
        
        Args:
            pdf_loader: Instancia de PDFLoader con el documento cargado (opcional)
            
        Returns:
            List[Dict]: Lista de problemas de contraste detectados
            
        Referencias:
            - Matterhorn: 04-001 (Color and Contrast)
            - Tagged PDF: 5.1.1 (Layout attributes - Color, BackgroundColor)
            - WCAG 2.1: 1.4.3 (Contrast Minimum), 1.4.11 (Non-text Contrast)
        """
        issues = []
        
        # Usar el PDF loader proporcionado o el establecido previamente
        if pdf_loader:
            self.pdf_loader = pdf_loader
            
        # Verificar si hay documento cargado
        if not self.pdf_loader or not self.pdf_loader.doc:
            logger.error("No hay documento cargado para validar contraste")
            return issues
        
        # Analizar colores de fondo de cada página
        self._analyze_page_backgrounds()
        
        # Analizar cada página del documento
        for page_num in range(self.pdf_loader.doc.page_count):
            try:
                page_issues = self._validate_page_contrast(page_num)
                issues.extend(page_issues)
            except Exception as e:
                logger.error(f"Error al validar contraste en página {page_num}: {e}")
                # Continuar con la siguiente página en caso de error
        
        # Validar la información transmitida solo por color/contraste
        color_meaning_issues = self._validate_color_meaning()
        issues.extend(color_meaning_issues)
        
        logger.info(f"Validación de contraste completada: {len(issues)} problemas encontrados")
        return issues
    
    def _analyze_page_backgrounds(self):
        """
        Analiza los colores de fondo de cada página.
        Este análisis es importante para determinar el color de fondo
        real sobre el que se renderiza cada elemento de texto.
        """
        self.page_bg_colors = {}
        
        if not self.pdf_loader or not self.pdf_loader.doc:
            return
            
        # Recorrer cada página
        for page_num in range(self.pdf_loader.doc.page_count):
            page = self.pdf_loader.doc[page_num]
            
            # Extraer elementos visuales grandes que pueden ser fondos
            page_elements = self._get_page_visual_elements(page_num)
            
            # Determinar color de fondo predeterminado (blanco si no se especifica)
            default_bg = (255, 255, 255)  # Blanco por defecto
            
            # Buscar elementos de fondo
            background_elements = []
            for elem in page_elements:
                # Elementos muy grandes probablemente son fondos
                if elem.get('type') in ['rect', 'path', 'image']:
                    rect = elem.get('rect', [0, 0, 0, 0])
                    
                    # Calcular área como porcentaje de la página
                    elem_width = rect[2] - rect[0]
                    elem_height = rect[3] - rect[1]
                    page_width = page.rect.width
                    page_height = page.rect.height
                    
                    area_ratio = (elem_width * elem_height) / (page_width * page_height)
                    
                    # Si cubre más del 50% de la página, probablemente es fondo
                    if area_ratio > 0.5:
                        background_elements.append(elem)
            
            # Determinar colores de fondo basándose en elementos encontrados
            if background_elements:
                # Ordenar por z-index (elementos más abajo son más probables fondos)
                background_elements.sort(key=lambda e: e.get('z_index', 0))
                
                # Tomar el color del elemento inferior (más al fondo)
                bg_color = background_elements[0].get('color', default_bg)
                if isinstance(bg_color, str):
                    bg_color = extract_color(bg_color) or default_bg
            else:
                # Si no hay elementos de fondo, usar blanco
                bg_color = default_bg
            
            # Almacenar color de fondo para esta página
            self.page_bg_colors[page_num] = bg_color
    
    def _get_page_visual_elements(self, page_num: int) -> List[Dict]:
        """
        Obtiene elementos visuales de una página.
        
        Args:
            page_num: Número de página (base 0)
            
        Returns:
            List[Dict]: Lista de elementos visuales con sus propiedades
        """
        if not self.pdf_loader:
            return []
            
        try:
            # Usar método de pdf_loader si está disponible
            if hasattr(self.pdf_loader, 'get_visual_content'):
                return self.pdf_loader.get_visual_content(page_num)
                
            # Alternativa si el método no está disponible
            page = self.pdf_loader.doc[page_num]
            elements = []
            
            # Extraer formas (paths, rectángulos, etc)
            for drawing in page.get_drawings():
                for item in drawing["items"]:
                    if item["type"] == "f":  # Fill
                        elements.append({
                            "type": "rect" if len(item["rect"]) == 4 else "path",
                            "rect": item["rect"][0:4] if len(item["rect"]) >= 4 else [0, 0, 0, 0],
                            "color": drawing.get("color", (255, 255, 255)),
                            "z_index": drawing.get("layer", 0)
                        })
            
            # Extraer texto
            blocks = page.get_text("dict")["blocks"]
            for block in blocks:
                if block["type"] == 0:  # Bloque de texto
                    for line in block["lines"]:
                        for span in line["spans"]:
                            elements.append({
                                "type": "text",
                                "rect": [span["bbox"][0], span["bbox"][1], span["bbox"][2], span["bbox"][3]],
                                "text": span["text"],
                                "font": span["font"],
                                "size": span["size"],
                                "color": span["color"],
                                "flags": span.get("flags", 0),
                                "is_bold": bool(span.get("flags", 0) & 2),  # bit 1 es negrita
                                "background_color": None  # No tenemos esta info en el diccionario
                            })
            
            # Extraer imágenes
            for img_index, img in enumerate(page.get_images(full=True)):
                xref = img[0]
                bbox = page.get_image_bbox(img)
                if bbox:
                    elements.append({
                        "type": "image",
                        "rect": [bbox.x0, bbox.y0, bbox.x1, bbox.y1],
                        "xref": xref,
                        "width": img[2],
                        "height": img[3],
                        "colorspace": img[5]
                    })
                    
            return elements
        except Exception as e:
            logger.error(f"Error al obtener elementos visuales de página {page_num}: {e}")
            return []
    
    def _find_background_color(self, element: Dict, page_num: int) -> Tuple[int, int, int]:
        """
        Determina el color de fondo para un elemento.
        
        Args:
            element: Elemento visual a analizar
            page_num: Número de página
            
        Returns:
            Tuple[int, int, int]: Color de fondo RGB
        """
        # Si el elemento ya tiene un color de fondo definido, usarlo
        if element.get("background_color"):
            bg_color = element["background_color"]
            if isinstance(bg_color, str):
                bg_color = extract_color(bg_color)
                if bg_color:
                    return bg_color
        
        # Obtener colores de todos los elementos que podrían estar detrás
        if page_num in self.page_bg_colors:
            return self.page_bg_colors[page_num]
            
        # Si no hay información, devolver blanco por defecto
        return (255, 255, 255)  # Blanco
    
    def _validate_page_contrast(self, page_num: int) -> List[Dict]:
        """
        Valida el contraste en una página específica.
        
        Args:
            page_num: Número de página (base 0)
            
        Returns:
            List[Dict]: Lista de problemas de contraste detectados
        """
        issues = []
        
        try:
            # Extraer elementos visuales de la página
            elements = self._get_page_visual_elements(page_num)
            
            # Procesar cada elemento
            for element in elements:
                # Solo nos interesan los elementos de texto
                if element["type"] != "text":
                    continue
                
                # Ignorar texto invisible
                if element.get("flags", 0) & 16 > 0:  # bit 4 es invisible
                    continue
                    
                # Extraer propiedades del texto
                text = element.get("text", "").strip()
                if not text:  # Ignorar texto vacío
                    continue
                    
                # Obtener colores de texto y fondo
                raw_color = element.get("color")
                text_color = normalize_color(raw_color)
                if text_color is None:
                    logger.warning(f"Color de texto inválido: {raw_color}")
                    text_color = (0, 0, 0)
                
                # Determinar color de fondo
                bg_color = self._find_background_color(element, page_num)
                
                # Calcular ratio de contraste
                contrast_ratio = calculate_contrast_ratio(text_color, bg_color)
                
                # Determinar si el texto es grande según WCAG
                font_size = element.get("size", 0)
                is_bold = element.get("is_bold", False)
                
                is_large_text = (
                    font_size >= self.large_text_threshold_pt or 
                    (is_bold and font_size >= self.large_text_bold_threshold_pt)
                )
                
                # Verificar si cumple con WCAG AA
                threshold = self.min_contrast_ratio_large if is_large_text else self.min_contrast_ratio_normal
                is_compliant = contrast_ratio >= threshold
                
                # Si no cumple, reportar problema
                if not is_compliant:
                    # Obtener sugerencias de mejora
                    suggestions = suggest_accessible_colors(text_color, bg_color)
                    
                    text_display = text[:30] + "..." if len(text) > 30 else text
                    
                    issue = {
                        "checkpoint": "04-001",
                        "severity": "warning",
                        "description": f"Contraste insuficiente en texto: '{text_display}'",
                        "fix_description": "Aumentar el contraste entre el texto y el fondo",
                        "details": {
                            "text": text,
                            "ratio": contrast_ratio,
                            "required": threshold,
                            "text_color": rgb_to_hex(text_color),
                            "bg_color": rgb_to_hex(bg_color),
                            "font_size": font_size,
                            "is_bold": is_bold,
                            "element_type": element.get("type", ""),
                            "suggestions": [
                                {
                                    "text_color": s.get("text_hex"),
                                    "bg_color": s.get("bg_hex"),
                                    "ratio": s.get("ratio")
                                } for s in suggestions.get("suggestions", [])
                            ]
                        },
                        "element_id": self._find_element_id(element, page_num),
                        "fixable": True,
                        "page": page_num
                    }
                    issues.append(issue)
            
            return issues
            
        except Exception as e:
            logger.error(f"Error al validar contraste en página {page_num}: {e}")
            return []
    
    def _find_element_id(self, element: Dict, page_num: int) -> Optional[str]:
        """
        Intenta encontrar el ID del elemento estructural correspondiente.
        
        Args:
            element: Elemento visual
            page_num: Número de página
            
        Returns:
            Optional[str]: ID del elemento o None si no se encuentra
        """
        if not self.pdf_loader or not self.pdf_loader.structure_tree:
            return None
            
        # Extraer coordenadas del elemento
        element_rect = element.get("rect", [0, 0, 0, 0])
        
        # Intentar encontrar el elemento estructural que corresponde a estas coordenadas
        def find_matching_element(node, path=""):
            if not isinstance(node, dict):
                return None
                
            # Verificar si este nodo corresponde a la página
            node_page = node.get("page")
            if node_page is not None and node_page != page_num:
                return None
                
            # Verificar si tiene coordenadas y coinciden aproximadamente
            if "bbox" in node:
                node_rect = node["bbox"]
                
                # Verificar si los rectángulos se solapan significativamente
                overlap_x = max(0, min(element_rect[2], node_rect[2]) - max(element_rect[0], node_rect[0]))
                overlap_y = max(0, min(element_rect[3], node_rect[3]) - max(element_rect[1], node_rect[1]))
                
                element_area = (element_rect[2] - element_rect[0]) * (element_rect[3] - element_rect[1])
                node_area = (node_rect[2] - node_rect[0]) * (node_rect[3] - node_rect[1])
                overlap_area = overlap_x * overlap_y
                
                # Si el área de solapamiento es al menos el 70% del área del elemento
                if element_area > 0 and overlap_area / element_area > 0.7:
                    # Verificar si contiene el mismo texto
                    element_text = element.get("text", "").strip()
                    node_text = node.get("text", "").strip()
                    
                    # Si el texto coincide
                    if element_text and node_text and element_text in node_text:
                        if "element" in node:
                            return str(id(node["element"]))
            
            # Buscar en los hijos
            if "children" in node:
                for child in node["children"]:
                    result = find_matching_element(child, path + "/child")
                    if result:
                        return result
                        
            return None
            
        # Buscar en el árbol de estructura
        return find_matching_element(self.pdf_loader.structure_tree)
    
    def _validate_color_meaning(self) -> List[Dict]:
        """
        Valida que la información transmitida por color también se
        transmita por otros medios (texto o estructura).
        
        Returns:
            List[Dict]: Lista de problemas detectados
        """
        issues = []
        
        if not self.pdf_loader or not self.pdf_loader.doc:
            return issues
            
        # Esta validación requiere análisis en elementos que usan color para transmitir información
        # Por ejemplo, texto que cambia de color para indicar importancia, o elementos coloreados
        # en una leyenda que no tienen texto que los identifique.
        
        # Buscar patrones comunes donde el color transmite información sin apoyo textual
        color_patterns = self._find_color_meaning_patterns()
        
        # Reportar cada patrón encontrado
        for pattern in color_patterns:
            issues.append({
                "checkpoint": "04-001",
                "severity": "warning",
                "description": f"Información transmitida sólo por color: {pattern['description']}",
                "fix_description": "Añadir texto o estructura que transmita la misma información",
                "details": pattern,
                "fixable": True,
                "page": pattern.get("page", 0)
            })
            
        return issues
    
    def _find_color_meaning_patterns(self) -> List[Dict]:
        """
        Busca patrones donde el color transmite información sin apoyo textual.
        
        Returns:
            List[Dict]: Lista de patrones detectados
        """
        patterns = []
        
        if not self.pdf_loader or not self.pdf_loader.doc:
            return patterns
            
        # Analizar cada página
        for page_num in range(self.pdf_loader.doc.page_count):
            try:
                page = self.pdf_loader.doc[page_num]
                
                # Extraer elementos visuales
                elements = self._get_page_visual_elements(page_num)
                
                # Detectar leyendas de colores sin texto descriptivo
                legend_pattern = self._detect_color_legends(elements, page_num)
                if legend_pattern:
                    patterns.extend(legend_pattern)
                    
                # Detectar grupos de texto con el mismo estilo pero diferentes colores
                colored_text_patterns = self._detect_colored_text_groups(elements, page_num)
                if colored_text_patterns:
                    patterns.extend(colored_text_patterns)
                    
            except Exception as e:
                logger.error(f"Error al analizar patrones de color en página {page_num}: {e}")
                
        return patterns
    
    def _detect_color_legends(self, elements: List[Dict], page_num: int) -> List[Dict]:
        """
        Detecta leyendas de colores sin texto descriptivo.
        
        Args:
            elements: Lista de elementos visuales
            page_num: Número de página
            
        Returns:
            List[Dict]: Patrones de leyenda detectados
        """
        patterns = []
        
        # Buscar grupos de rectángulos pequeños con diferentes colores cercanos entre sí
        colored_rects = [e for e in elements if e.get("type") in ["rect", "path"] and e.get("color")]
        
        # Si hay pocos rectángulos, no analizamos
        if len(colored_rects) < 3:
            return patterns
            
        # Agrupar rectángulos cercanos
        rect_groups = []
        processed = set()
        
        for i, rect1 in enumerate(colored_rects):
            if i in processed:
                continue
                
            group = [rect1]
            processed.add(i)
            rect1_center = [
                (rect1["rect"][0] + rect1["rect"][2]) / 2,
                (rect1["rect"][1] + rect1["rect"][3]) / 2
            ]
            
            for j, rect2 in enumerate(colored_rects):
                if j in processed:
                    continue
                    
                rect2_center = [
                    (rect2["rect"][0] + rect2["rect"][2]) / 2,
                    (rect2["rect"][1] + rect2["rect"][3]) / 2
                ]
                
                # Calcular distancia entre centros
                distance = math.sqrt(
                    (rect1_center[0] - rect2_center[0])**2 + 
                    (rect1_center[1] - rect2_center[1])**2
                )
                
                # Si están cerca, incluir en el grupo
                if distance < 100:  # Umbral arbitrario, ajustar según necesidades
                    group.append(rect2)
                    processed.add(j)
            
            if len(group) >= 3:
                rect_groups.append(group)
        
        # Analizar cada grupo como posible leyenda
        for group in rect_groups:
            # Verificar si tienen diferentes colores
            colors = set()
            for rect in group:
                if isinstance(rect.get("color"), tuple):
                    colors.add(rect.get("color"))
                    
            # Si tienen diferentes colores, podría ser una leyenda
            if len(colors) >= 3:
                # Buscar texto cercano que podría describir la leyenda
                has_descriptive_text = False
                
                for rect in group:
                    rect_center = [
                        (rect["rect"][0] + rect["rect"][2]) / 2,
                        (rect["rect"][1] + rect["rect"][3]) / 2
                    ]
                    
                    # Buscar texto cercano
                    for elem in elements:
                        if elem.get("type") == "text":
                            text_center = [
                                (elem["rect"][0] + elem["rect"][2]) / 2,
                                (elem["rect"][1] + elem["rect"][3]) / 2
                            ]
                            
                            # Calcular distancia
                            distance = math.sqrt(
                                (rect_center[0] - text_center[0])**2 + 
                                (rect_center[1] - text_center[1])**2
                            )
                            
                            # Si hay texto cerca, asumimos que describe el color
                            if distance < 30:  # Umbral arbitrario
                                has_descriptive_text = True
                                break
                
                # Si no hay texto descriptivo, reportar como problema
                if not has_descriptive_text:
                    patterns.append({
                        "type": "color_legend",
                        "description": "Leyenda de colores sin texto descriptivo",
                        "page": page_num,
                        "colors": [rgb_to_hex(c) for c in colors if isinstance(c, tuple)],
                        "location": [
                            min(r["rect"][0] for r in group),
                            min(r["rect"][1] for r in group),
                            max(r["rect"][2] for r in group),
                            max(r["rect"][3] for r in group)
                        ]
                    })
        
        return patterns
    
    def _detect_colored_text_groups(self, elements: List[Dict], page_num: int) -> List[Dict]:
        """
        Detecta grupos de texto con el mismo estilo pero diferentes colores.
        
        Args:
            elements: Lista de elementos visuales
            page_num: Número de página
            
        Returns:
            List[Dict]: Patrones de texto coloreado detectados
        """
        patterns = []
        
        # Agrupar texto por fuente y tamaño
        text_groups = {}
        
        for elem in elements:
            if elem.get("type") == "text":
                font = elem.get("font", "")
                size = elem.get("size", 0)
                
                key = f"{font}_{size}"
                if key not in text_groups:
                    text_groups[key] = []
                    
                text_groups[key].append(elem)
        
        # Analizar cada grupo
        for font_size, group in text_groups.items():
            # Si el grupo es muy pequeño, ignorarlo
            if len(group) < 3:
                continue
                
            # Contar diferentes colores en el grupo
            colors = {}
            for elem in group:
                color = elem.get("color")
                if isinstance(color, tuple):
                    color_str = rgb_to_hex(color)
                    if color_str not in colors:
                        colors[color_str] = []
                    colors[color_str].append(elem.get("text", ""))
            
            # Si hay varios colores diferentes
            if len(colors) >= 3:
                # Verificar si hay alguna estructura que explique los colores
                has_structural_explanation = self._check_structural_explanation(group, page_num)
                
                # Si no hay explicación estructural, reportar como problema
                if not has_structural_explanation:
                    patterns.append({
                        "type": "colored_text",
                        "description": "Texto con diferentes colores sin explicación estructural",
                        "page": page_num,
                        "font_size": font_size,
                        "colors": list(colors.keys()),
                        "samples": {color: texts[:3] for color, texts in colors.items()}
                    })
        
        return patterns
    
    def _check_structural_explanation(self, text_elements: List[Dict], page_num: int) -> bool:
        """
        Verifica si hay una explicación estructural para diferentes colores de texto.
        
        Args:
            text_elements: Lista de elementos de texto
            page_num: Número de página
            
        Returns:
            bool: True si hay una explicación estructural
        """
        if not self.pdf_loader or not self.pdf_loader.structure_tree:
            return False
            
        # Para cada elemento de texto, intentar encontrar su etiqueta estructural
        structural_types = {}
        
        for elem in text_elements:
            element_id = self._find_element_id(elem, page_num)
            if element_id:
                # Buscar el tipo de etiqueta
                def find_tag_type(node):
                    if isinstance(node, dict) and "element" in node and str(id(node["element"])) == element_id:
                        return node.get("type", "")
                        
                    if isinstance(node, dict) and "children" in node:
                        for child in node["children"]:
                            result = find_tag_type(child)
                            if result:
                                return result
                                
                    return None
                
                tag_type = find_tag_type(self.pdf_loader.structure_tree)
                if tag_type:
                    color = elem.get("color")
                    if isinstance(color, tuple):
                        color_str = rgb_to_hex(color)
                        if color_str not in structural_types:
                            structural_types[color_str] = set()
                        structural_types[color_str].add(tag_type)
        
        # Si cada color corresponde a un tipo de etiqueta diferente, hay explicación estructural
        if len(structural_types) >= 2:
            # Verificar si hay al menos un tipo exclusivo para cada color
            type_sets = list(structural_types.values())
            for i, types1 in enumerate(type_sets):
                for j, types2 in enumerate(type_sets):
                    if i != j and not types1.isdisjoint(types2):
                        return False
                        
            return True
            
        return False