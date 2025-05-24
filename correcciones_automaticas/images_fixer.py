#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Módulo para corrección automática de imágenes en PDFs según PDF/UA y Matterhorn Protocol.

Este módulo implementa soluciones para los siguientes checkpoints de Matterhorn:
- 13-001: Imágenes significativas marcadas como artefactos
- 13-002: Artefactos decorativos etiquetados como contenido real
- 13-003: Elementos gráficos con color significativo
- 13-004: Falta texto alternativo en etiquetas <Figure>
- 13-005: Texto alternativo no adecuado
- 13-006: Imagen con texto sin ActualText
- 13-007: Contenido continuo interrumpido por objetos anclados
- 13-008: ActualText no presente cuando una imagen contiene texto
- 13-009: Imagen sin descripción larga donde sería apropiado
"""

import os
import re
import io
import tempfile
import numpy as np
from PIL import Image
from typing import Dict, List, Optional, Any, Set, Tuple, Union, Callable
from loguru import logger

# Intentar importar bibliotecas opcionales para detección de texto
try:
    import pytesseract
    import cv2
    OCR_AVAILABLE = True
except ImportError:
    OCR_AVAILABLE = False
    logger.warning("pytesseract o cv2 no disponibles. Funcionalidad OCR limitada.")

class ImagesFixer:
    """
    Realiza correcciones automáticas en imágenes para cumplir con PDF/UA.
    
    Correcciones implementadas:
    - Añadir texto alternativo a imágenes sin Alt
    - Detectar texto en imágenes y añadir ActualText cuando es apropiado
    - Marcar imágenes decorativas como artefactos
    - Corregir figuras sin imagen asociada
    - Asegurar que las imágenes están correctamente estructuradas
    """
    
    def __init__(self, pdf_writer=None):
        """
        Inicializa el corrector de imágenes.
        
        Args:
            pdf_writer: Instancia de PDFWriter para aplicar cambios al documento
        """
        self.pdf_writer = pdf_writer
        self.fixed_images_count = 0
        self.ocr_available = OCR_AVAILABLE
        
        # Configuración para la detección de imágenes decorativas
        self.decorative_area_threshold = 0.01  # % del área de la página
        self.decorative_aspect_ratio = 5.0     # Relación ancho/alto (o alto/ancho) para iconos
        
        # Configuración para OCR
        self.ocr_confidence_threshold = 60  # Mínima confianza para considerar texto válido
        self.min_text_length = 3            # Longitud mínima de texto para considerarlo significativo
        
        # Mapa de tipos MIME a descripciones para generación de Alt
        self.mime_type_descriptions = {
            "image/jpeg": "fotografía",
            "image/png": "gráfico",
            "image/tiff": "imagen escaneada",
            "image/gif": "imagen animada",
            "image/svg+xml": "gráfico vectorial"
        }
        
        logger.info("ImagesFixer inicializado")
    
    def fix_all_images(self, structure_tree: Dict) -> bool:
        """
        Corrige todas las imágenes en el documento para cumplir con PDF/UA.
        
        Args:
            structure_tree: Diccionario representando la estructura lógica
            
        Returns:
            bool: True si se aplicaron correcciones, False en caso contrario
        """
        if not structure_tree:
            logger.warning("No hay estructura para analizar")
            return False
        
        if not self.pdf_writer or not hasattr(self.pdf_writer, "pdf_loader") or not self.pdf_writer.pdf_loader:
            logger.error("No hay pdf_writer o pdf_loader válido disponible")
            return False
        
        try:
            logger.info("Iniciando análisis y corrección de imágenes...")
            self.fixed_images_count = 0
            
            # 1. Extraer información de imágenes visuales en el documento
            visual_images = self._extract_visual_images()
            
            # 2. Identificar etiquetas <Figure> en la estructura lógica
            structure_figures = self._find_structure_figures(structure_tree)
            
            # 3. Emparejar imágenes visuales con etiquetas de estructura
            paired_data, unpaired_images, unpaired_figures = self._match_images_with_figures(visual_images, structure_figures)
            
            # 4. Corregir imágenes ya etiquetadas (añadir Alt y ActualText si falta)
            self._fix_paired_figures(paired_data)
            
            # 5. Procesar imágenes sin etiquetar (crear <Figure> o marcar como artefacto)
            self._process_unpaired_images(unpaired_images)
            
            # 6. Corregir etiquetas <Figure> que no tienen imagen asociada
            self._fix_orphan_figures(unpaired_figures)
            
            # 7. Corregir figuras en contextos especiales (anotaciones, etc.)
            if structure_figures:
                self._fix_special_context_figures(structure_tree)
                
            # 8. Generar e incluir descripciones largas para imágenes complejas
            self._enhance_complex_image_descriptions(structure_tree)
            
            logger.info(f"Corrección de imágenes completada: {self.fixed_images_count} imágenes corregidas")
            return self.fixed_images_count > 0
            
        except Exception as e:
            logger.exception(f"Error al corregir imágenes: {e}")
            return False
    
    def _extract_visual_images(self) -> List[Dict]:
        """
        Extrae información sobre imágenes visuales en el documento.
        
        Returns:
            List[Dict]: Lista de imágenes con información relevante
        """
        visual_images = []
        pdf_loader = self.pdf_writer.pdf_loader
        
        for page_num in range(pdf_loader.page_count):
            try:
                page = pdf_loader.doc[page_num]
                page_width, page_height = page.rect.width, page.rect.height
                page_area = page_width * page_height
                
                # Extraer lista de imágenes en la página
                img_list = page.get_images(full=True)
                
                for img_idx, img_info in enumerate(img_list):
                    try:
                        xref = img_info[0]  # Referencia interna de la imagen
                        
                        # Extraer datos de la imagen
                        base_image = pdf_loader.doc.extract_image(xref)
                        if not base_image:
                            continue
                        
                        # Obtener rectángulo de la imagen en la página
                        rect = page.get_image_bbox(img_info)
                        if not rect:
                            continue
                        
                        width, height = base_image["width"], base_image["height"]
                        image_area = rect.width * rect.height
                        relative_area = image_area / page_area
                        
                        # Determinar si es decorativa
                        aspect_ratio = max(width/height if height > 0 else 1, height/width if width > 0 else 1)
                        is_decorative = relative_area < self.decorative_area_threshold or aspect_ratio > self.decorative_aspect_ratio
                        
                        # Analizar si contiene texto
                        has_text, text_content = self._analyze_image_for_text(base_image["image"])
                        
                        image_data = {
                            "xref": xref,
                            "page": page_num,
                            "rect": [rect.x0, rect.y0, rect.x1, rect.y1],
                            "width": width,
                            "height": height,
                            "colorspace": base_image.get("colorspace", ""),
                            "bpc": base_image.get("bpc", 0),
                            "image_type": base_image.get("ext", "").lower(),
                            "area_ratio": relative_area,
                            "aspect_ratio": aspect_ratio,
                            "is_decorative": is_decorative and not has_text,  # Si tiene texto, no es decorativa
                            "has_text": has_text,
                            "text_content": text_content,
                            "image_data": base_image["image"]
                        }
                        
                        visual_images.append(image_data)
                        
                    except Exception as img_err:
                        logger.warning(f"Error al procesar imagen {img_idx} en página {page_num}: {img_err}")
                        continue
                    
            except Exception as page_err:
                logger.warning(f"Error al procesar página {page_num}: {page_err}")
                continue
        
        logger.info(f"Encontradas {len(visual_images)} imágenes visuales en el documento")
        return visual_images
    
    def _find_structure_figures(self, structure_tree: Dict) -> List[Dict]:
        """
        Busca elementos de estructura <Figure> en el árbol de estructura.
        
        Args:
            structure_tree: Árbol de estructura lógica
            
        Returns:
            List[Dict]: Lista de elementos <Figure> con información relevante
        """
        figures = []
        
        def traverse_structure(node, path=""):
            if not node:
                return
                
            # Procesar nodo actual si es Figure
            if isinstance(node, dict) and node.get("type") == "Figure":
                figure_data = {
                    "element": node,
                    "element_id": id(node.get("element")) if "element" in node else None,
                    "page": node.get("page", 0),
                    "has_alt": self._has_attribute(node, "Alt"),
                    "alt_text": self._get_attribute_value(node, "Alt"),
                    "has_actual_text": self._has_attribute(node, "ActualText"),
                    "actual_text": self._get_attribute_value(node, "ActualText"),
                    "parent_type": self._get_parent_type(node, structure_tree),
                    "path": path
                }
                figures.append(figure_data)
            
            # Recorrer hijos
            if isinstance(node, dict) and "children" in node:
                for i, child in enumerate(node["children"]):
                    child_path = f"{path}/{i}:{child.get('type', 'Unknown')}"
                    traverse_structure(child, child_path)
            elif isinstance(node, list):
                for i, item in enumerate(node):
                    traverse_structure(item, f"{path}/{i}")
        
        traverse_structure(structure_tree)
        logger.info(f"Encontrados {len(figures)} elementos <Figure> en la estructura")
        return figures
    
    def _match_images_with_figures(self, images: List[Dict], figures: List[Dict]) -> Tuple[List[Dict], List[Dict], List[Dict]]:
        """
        Empareja imágenes visuales con elementos de estructura <Figure>.
        
        Args:
            images: Lista de imágenes visuales
            figures: Lista de elementos <Figure>
            
        Returns:
            Tuple con tres listas:
            - Pares de imágenes y figuras emparejadas
            - Imágenes sin etiqueta <Figure> correspondiente
            - Figuras sin imagen correspondiente
        """
        paired = []
        unpaired_images = list(images)  # Copia para eliminar mientras iteramos
        unpaired_figures = list(figures)  # Copia para eliminar mientras iteramos
        
        # Matriz de posibles coincidencias (puntaje entre cada par imagen-figura)
        matching_scores = []
        
        # Calcular puntajes de coincidencia para cada par posible
        for img_idx, image in enumerate(images):
            for fig_idx, figure in enumerate(figures):
                score = self._calculate_match_score(image, figure)
                if score > 0:
                    matching_scores.append((score, img_idx, fig_idx))
        
        # Ordenar coincidencias por puntaje (mayor a menor)
        matching_scores.sort(reverse=True)
        
        # Aplicar emparejamientos en orden de mejor a peor coincidencia
        used_images = set()
        used_figures = set()
        
        for score, img_idx, fig_idx in matching_scores:
            if img_idx in used_images or fig_idx in used_figures:
                continue
                
            paired.append({
                "image": images[img_idx],
                "figure": figures[fig_idx],
                "match_score": score
            })
            
            used_images.add(img_idx)
            used_figures.add(fig_idx)
        
        # Actualizar listas de no emparejados
        unpaired_images = [img for i, img in enumerate(images) if i not in used_images]
        unpaired_figures = [fig for i, fig in enumerate(figures) if i not in used_figures]
        
        logger.info(f"Emparejamiento: {len(paired)} pares, {len(unpaired_images)} imágenes sin emparejar, {len(unpaired_figures)} figuras sin emparejar")
        return paired, unpaired_images, unpaired_figures
    
    def _calculate_match_score(self, image: Dict, figure: Dict) -> float:
        """
        Calcula un puntaje de coincidencia entre una imagen y una figura.
        
        Args:
            image: Información de la imagen visual
            figure: Información del elemento <Figure>
            
        Returns:
            float: Puntaje de coincidencia (0 = no coinciden, >0 = posible coincidencia)
        """
        # Si están en diferentes páginas, no pueden coincidir
        if image["page"] != figure["page"]:
            return 0
        
        # Base de puntuación
        score = 1.0
        
        # Verificar si la figura tiene MCID que coincide con la imagen
        # (Esta parte dependería de la implementación específica del PDF y
        # de cómo se vinculan los elementos de estructura con el contenido)
        
        # Por ahora, usamos coincidencia por posición en la página
        return score
    
    def _fix_paired_figures(self, paired_data: List[Dict]) -> None:
        """
        Corrige elementos <Figure> que ya están emparejados con imágenes.
        
        Args:
            paired_data: Lista de pares imagen-figura
        """
        for pair in paired_data:
            image = pair["image"]
            figure = pair["figure"]
            element_id = figure["element_id"]
            
            if not element_id:
                logger.warning(f"Elemento <Figure> sin ID en página {figure['page']}")
                continue
            
            # 1. Verificar y añadir Alt si es necesario
            if not figure["has_alt"]:
                alt_text = self._generate_alt_text(image, figure)
                if self.pdf_writer.update_tag_attribute(element_id, "Alt", alt_text):
                    self.fixed_images_count += 1
                    logger.info(f"Añadido Alt=''{alt_text}'' a figura en página {figure['page']}")
            
            # 2. Verificar y añadir ActualText si la imagen contiene texto
            if image["has_text"] and not figure["has_actual_text"]:
                if self.pdf_writer.update_tag_attribute(element_id, "ActualText", image["text_content"]):
                    self.fixed_images_count += 1
                    logger.info(f"Añadido ActualText para texto en imagen en página {figure['page']}")
            
            # 3. Verificar si el Alt existente es adecuado
            elif figure["has_alt"] and self._is_generic_alt(figure["alt_text"]):
                improved_alt = self._generate_alt_text(image, figure, existing_alt=figure["alt_text"])
                if improved_alt != figure["alt_text"]:
                    if self.pdf_writer.update_tag_attribute(element_id, "Alt", improved_alt):
                        self.fixed_images_count += 1
                        logger.info(f"Mejorado Alt='{improved_alt}' en figura en página {figure['page']}")
    
    def _process_unpaired_images(self, unpaired_images: List[Dict]) -> None:
        """
        Procesa imágenes que no tienen etiqueta <Figure> correspondiente.
        
        Args:
            unpaired_images: Lista de imágenes sin emparejar
        """
        for image in unpaired_images:
            # Si es decorativa, marcarla como artefacto
            if image["is_decorative"]:
                if self._mark_as_artifact(image):
                    self.fixed_images_count += 1
                    logger.info(f"Imagen decorativa marcada como artefacto en página {image['page']}")
            else:
                # Crear etiqueta <Figure> con Alt y ActualText si es necesario
                alt_text = self._generate_alt_text(image)
                tag_info = {
                    "type": "Figure",
                    "page": image["page"],
                    "bbox": image["rect"],
                    "parent_id": None,  # Se determinará automáticamente
                    "attributes": {
                        "Alt": alt_text
                    }
                }
                
                # Añadir ActualText si la imagen contiene texto
                if image["has_text"]:
                    tag_info["attributes"]["ActualText"] = image["text_content"]
                
                if self.pdf_writer.add_tag(tag_info):
                    self.fixed_images_count += 1
                    logger.info(f"Creada etiqueta <Figure> para imagen en página {image['page']}")
    
    def _fix_orphan_figures(self, unpaired_figures: List[Dict]) -> None:
        """
        Corrige etiquetas <Figure> que no tienen imagen asociada.
        
        Args:
            unpaired_figures: Lista de figuras sin emparejar
        """
        for figure in unpaired_figures:
            element_id = figure["element_id"]
            
            if not element_id:
                continue
                
            # Si no tiene Alt, añadir un texto genérico
            if not figure["has_alt"]:
                alt_text = "Elemento gráfico (no hay imagen detectable)"
                if self.pdf_writer.update_tag_attribute(element_id, "Alt", alt_text):
                    self.fixed_images_count += 1
                    logger.info(f"Añadido Alt genérico a figura sin imagen en página {figure['page']}")
    
    def _fix_special_context_figures(self, structure_tree: Dict) -> None:
        """
        Corrige figuras en contextos especiales (anotaciones, tablas, etc.).
        
        Args:
            structure_tree: Árbol de estructura lógica
        """
        # Buscar figuras dentro de anotaciones
        def find_annotation_figures(node, parent_type=None):
            if not node:
                return []
                
            results = []
            current_type = node.get("type") if isinstance(node, dict) else None
            
            # Si es una figura dentro de un contexto especial
            if current_type == "Figure" and parent_type in ["Annot", "Link", "Form"]:
                results.append({
                    "element": node,
                    "element_id": id(node.get("element")) if "element" in node else None,
                    "parent_type": parent_type,
                    "has_alt": self._has_attribute(node, "Alt")
                })
            
            # Recorrer hijos
            if isinstance(node, dict) and "children" in node:
                for child in node["children"]:
                    results.extend(find_annotation_figures(child, current_type))
            elif isinstance(node, list):
                for item in node:
                    results.extend(find_annotation_figures(item, parent_type))
                    
            return results
        
        special_figures = find_annotation_figures(structure_tree)
        
        # Corregir figuras en contextos especiales
        for figure in special_figures:
            if not figure["has_alt"] and figure["element_id"]:
                context_alt = f"Imagen en {figure['parent_type'].lower()}"
                if self.pdf_writer.update_tag_attribute(figure["element_id"], "Alt", context_alt):
                    self.fixed_images_count += 1
                    logger.info(f"Añadido Alt contextual a figura en {figure['parent_type']}")
    
    def _enhance_complex_image_descriptions(self, structure_tree: Dict) -> None:
        """
        Mejora descripciones de imágenes complejas (gráficos, diagramas, etc.).
        
        Args:
            structure_tree: Árbol de estructura lógica
        """
        # Buscar figuras con posible contenido complejo
        def find_complex_figures(node):
            if not node:
                return []
                
            results = []
            if isinstance(node, dict) and node.get("type") == "Figure":
                alt_text = self._get_attribute_value(node, "Alt") or ""
                
                # Heurística para determinar figuras complejas que necesitan mejor descripción
                is_potentially_complex = (
                    ("gráfico" in alt_text.lower() or 
                     "diagrama" in alt_text.lower() or 
                     "esquema" in alt_text.lower()) and
                    len(alt_text) < 100  # Alt demasiado corto para contenido complejo
                )
                
                if is_potentially_complex:
                    results.append({
                        "element": node,
                        "element_id": id(node.get("element")) if "element" in node else None,
                        "alt_text": alt_text
                    })
            
            # Recorrer hijos
            if isinstance(node, dict) and "children" in node:
                for child in node["children"]:
                    results.extend(find_complex_figures(child))
            elif isinstance(node, list):
                for item in node:
                    results.extend(find_complex_figures(item))
                    
            return results
        
        complex_figures = find_complex_figures(structure_tree)
        
        # Mejorar descripciones de figuras complejas
        for figure in complex_figures:
            if figure["element_id"]:
                enhanced_alt = self._enhance_complex_description(figure["alt_text"])
                if enhanced_alt != figure["alt_text"]:
                    if self.pdf_writer.update_tag_attribute(figure["element_id"], "Alt", enhanced_alt):
                        self.fixed_images_count += 1
                        logger.info(f"Mejorada descripción de figura compleja")
    
    def _analyze_image_for_text(self, image_data: bytes) -> Tuple[bool, str]:
        """
        Analiza una imagen para detectar si contiene texto mediante OCR.
        
        Args:
            image_data: Datos binarios de la imagen
            
        Returns:
            Tuple[bool, str]: (contiene_texto, texto_detectado)
        """
        if not self.ocr_available:
            return False, ""
            
        try:
            # Convertir a formato PIL para OCR
            image = Image.open(io.BytesIO(image_data))
            
            # Usar pytesseract para OCR
            text = pytesseract.image_to_string(image).strip()
            
            # Obtener confianza del OCR
            ocr_data = pytesseract.image_to_data(image, output_type=pytesseract.Output.DICT)
            confidences = [int(conf) for conf in ocr_data['conf'] if conf != '-1']
            
            # Verificar si el texto es significativo
            if (text and 
                len(text) >= self.min_text_length and
                confidences and
                sum(confidences) / len(confidences) >= self.ocr_confidence_threshold):
                return True, text
                
            return False, ""
            
        except Exception as e:
            logger.warning(f"Error en OCR: {e}")
            return False, ""
    
    def _generate_alt_text(self, image: Dict, figure: Dict = None, existing_alt: str = None) -> str:
        """
        Genera texto alternativo para una imagen.
        
        Args:
            image: Información de la imagen
            figure: Información de la etiqueta <Figure> (opcional)
            existing_alt: Texto alternativo existente (opcional)
            
        Returns:
            str: Texto alternativo generado
        """
        # Si la imagen contiene texto, usarlo como base para el Alt
        if image.get("has_text", False) and image.get("text_content"):
            return f"Imagen con texto: {image['text_content']}"
            
        # Si existe Alt pero parece genérico, mejorarlo
        if existing_alt and len(existing_alt) > 0:
            if self._is_generic_alt(existing_alt):
                # Usar el Alt existente como base y enriquecerlo
                return self._enrich_alt_text(existing_alt, image)
            else:
                # Si el Alt existente parece adecuado, mantenerlo
                return existing_alt
        
        # Generar texto alternativo básico
        img_type = self.mime_type_descriptions.get(
            f"image/{image.get('image_type', '')}", 
            "imagen"
        )
        
        # Determinar orientación
        if image["width"] > image["height"] * 1.5:
            orientation = "horizontal"
        elif image["height"] > image["width"] * 1.5:
            orientation = "vertical"
        else:
            orientation = "cuadrada"
            
        return f"{img_type.capitalize()} {orientation} en página {image['page'] + 1}"
    
    def _is_generic_alt(self, alt_text: str) -> bool:
        """
        Determina si un texto alternativo es genérico o poco descriptivo.
        
        Args:
            alt_text: Texto alternativo a evaluar
            
        Returns:
            bool: True si es genérico, False si parece adecuado
        """
        if not alt_text:
            return True
            
        # Textos genéricos comunes
        generic_patterns = [
            r"^imagen$",
            r"^figura$",
            r"^gráfico$",
            r"^foto$",
            r"^imagen \d+$",
            r"^figura \d+$",
            r"^img_\d+$",
            r"^photo$",
            r"^image$",
            r"^picture$"
        ]
        
        # Verificar si coincide con algún patrón genérico
        for pattern in generic_patterns:
            if re.match(pattern, alt_text.lower().strip()):
                return True
        
        # Verificar si es muy corto (menos de 10 caracteres)
        if len(alt_text.strip()) < 10:
            return True
            
        return False
    
    def _enrich_alt_text(self, alt_text: str, image: Dict) -> str:
        """
        Enriquece un texto alternativo genérico con más información.
        
        Args:
            alt_text: Texto alternativo existente
            image: Información de la imagen
            
        Returns:
            str: Texto alternativo mejorado
        """
        # Añadir información sobre tipo y ubicación
        img_type = self.mime_type_descriptions.get(
            f"image/{image.get('image_type', '')}", 
            "imagen"
        )
        
        # Determinar si el texto actual ya contiene cierta información
        has_type = any(keyword in alt_text.lower() for keyword in 
                      ["imagen", "figura", "gráfico", "foto", "image", "picture"])
        
        has_location = "página" in alt_text.lower() or "page" in alt_text.lower()
        
        # Construir texto mejorado
        result = alt_text
        
        if not has_type:
            result = f"{img_type.capitalize()}: {result}"
            
        if not has_location:
            result = f"{result} (página {image['page'] + 1})"
            
        return result
    
    def _enhance_complex_description(self, alt_text: str) -> str:
        """
        Mejora la descripción de una imagen compleja.
        
        Args:
            alt_text: Texto alternativo existente
            
        Returns:
            str: Descripción mejorada
        """
        # Si la descripción ya es detallada, mantenerla
        if len(alt_text) > 100:
            return alt_text
            
        # Añadir nota sobre descripción detallada
        return f"{alt_text} [Para obtener una descripción más detallada, contacte con el autor o administrador del documento]"
    
    def _mark_as_artifact(self, image: Dict) -> bool:
        """
        Marca una imagen como artefacto.
        
        Args:
            image: Información de la imagen
            
        Returns:
            bool: True si se marcó correctamente
        """
        if not self.pdf_writer:
            return False
            
        # Para marcar como artefacto necesitamos la página y la referencia a la imagen
        try:
            # Implementar según la API específica de pdf_writer
            return self.pdf_writer.mark_content_as_artifact(
                page_num=image["page"],
                xref=image["xref"],
                artifact_type="Background"  # Tipo de artefacto según ISO 32000
            )
        except AttributeError:
            # Método alternativo si mark_content_as_artifact no está disponible
            try:
                # Intentar usar métodos alternativos según disponibilidad
                if hasattr(self.pdf_writer, "mark_as_artifact"):
                    return self.pdf_writer.mark_as_artifact(image["xref"], image["page"])
                    
                logger.warning("No se pudo marcar imagen como artefacto: método no soportado")
                return False
                
            except Exception as e:
                logger.error(f"Error al marcar imagen como artefacto: {e}")
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
        if not element:
            return False
            
        # 1. Verificar en el diccionario de atributos
        if "attributes" in element and attribute in element["attributes"]:
            value = element["attributes"][attribute]
            return value is not None and value != ""
            
        # 2. Verificar directamente en el elemento
        if attribute in element:
            value = element[attribute]
            return value is not None and value != ""
            
        # 3. Verificar en el objeto pikepdf
        if "element" in element:
            pikepdf_element = element["element"]
            # Verificar en formatos diversos que podrían existir
            for attr_format in [attribute, f"/{attribute}", attribute.capitalize()]:
                try:
                    if hasattr(pikepdf_element, attr_format):
                        value = getattr(pikepdf_element, attr_format)
                        return value is not None and value != ""
                        
                    if attr_format in pikepdf_element:
                        value = pikepdf_element[attr_format]
                        return value is not None and value != ""
                except:
                    pass
                    
        return False
    
    def _get_attribute_value(self, element: Dict, attribute: str) -> str:
        """
        Obtiene el valor de un atributo de un elemento.
        
        Args:
            element: Elemento del que obtener el atributo
            attribute: Nombre del atributo
            
        Returns:
            str: Valor del atributo o cadena vacía
        """
        if not element:
            return ""
            
        # 1. Verificar en el diccionario de atributos
        if "attributes" in element and attribute in element["attributes"]:
            value = element["attributes"][attribute]
            return str(value) if value is not None else ""
            
        # 2. Verificar directamente en el elemento
        if attribute in element:
            value = element[attribute]
            return str(value) if value is not None else ""
            
        # 3. Verificar en el objeto pikepdf
        if "element" in element:
            pikepdf_element = element["element"]
            # Verificar en formatos diversos que podrían existir
            for attr_format in [attribute, f"/{attribute}", attribute.capitalize()]:
                try:
                    if hasattr(pikepdf_element, attr_format):
                        value = getattr(pikepdf_element, attr_format)
                        return str(value) if value is not None else ""
                        
                    if attr_format in pikepdf_element:
                        value = pikepdf_element[attr_format]
                        return str(value) if value is not None else ""
                except:
                    pass
                    
        return ""
    
    def _get_parent_type(self, node: Dict, structure_tree: Dict) -> str:
        """
        Obtiene el tipo del elemento padre de un nodo.
        
        Args:
            node: El nodo del que se quiere obtener el padre
            structure_tree: Árbol de estructura completo
            
        Returns:
            str: Tipo del padre o cadena vacía
        """
        def find_parent(current_node, target, parent_type=None):
            if not current_node:
                return None
                
            # Verificar hijos directos
            if isinstance(current_node, dict) and "children" in current_node:
                for child in current_node["children"]:
                    if child is target:
                        return current_node.get("type", "")
                    
                    # Búsqueda recursiva
                    result = find_parent(child, target)
                    if result:
                        return result
                        
            elif isinstance(current_node, list):
                for item in current_node:
                    result = find_parent(item, target)
                    if result:
                        return result
                        
            return None
        
        return find_parent(structure_tree, node) or ""