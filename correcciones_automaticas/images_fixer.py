#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Corrección automática de imágenes según PDF/UA.
Añade Alt o ActualText a figuras y procesa imágenes con texto.
"""

from typing import Dict, List, Optional, Tuple, Any
import os
from pathlib import Path
import tempfile
import cv2
import numpy as np
from PIL import Image
import pytesseract
from loguru import logger

class ImagesFixer:
    """
    Clase para corregir etiquetas de imágenes según PDF/UA.
    Añade Alt por nombre de archivo o OCR y aplica ActualText.
    """
    
    def __init__(self, pdf_writer=None):
        """
        Inicializa el corrector de imágenes.
        
        Args:
            pdf_writer: Instancia opcional de PDFWriter
        """
        self.pdf_writer = pdf_writer
        logger.info("ImagesFixer inicializado")
    
    def set_pdf_writer(self, pdf_writer):
        """Establece el escritor de PDF a utilizar"""
        self.pdf_writer = pdf_writer
    
    def fix_all_images(self, structure_tree: Dict, autodetect_text: bool = True) -> bool:
        """
        Corrige todas las imágenes en la estructura.
        
        Args:
            structure_tree: Diccionario representando la estructura lógica
            autodetect_text: Si se debe detectar automáticamente texto en imágenes
            
        Returns:
            bool: True si se realizaron correcciones
            
        Referencias:
            - Matterhorn: 13-004, 13-005, 13-008
            - Tagged PDF: 4.3.1, 5.5.2 (Alt), 5.5.3 (ActualText)
        """
        try:
            if self.pdf_writer is None:
                logger.error("No hay PDFWriter configurado para aplicar correcciones")
                return False
            
            if not structure_tree or not structure_tree.get("children"):
                logger.warning("No hay estructura para corregir imágenes")
                return False
            
            # Buscar todas las figuras en la estructura
            figures = self._find_figures(structure_tree.get("children", []))
            
            if not figures:
                logger.info("No se encontraron figuras para corregir")
                return False
            
            logger.info(f"Encontradas {len(figures)} figuras para procesar")
            
            changes_made = False
            
            # Procesar cada figura
            for figure in figures:
                figure_id = figure.get("id", "unknown")
                
                # Verificar si falta Alt
                if not figure.get("alt"):
                    alt_text = self._generate_alt_text(figure)
                    if alt_text:
                        self.pdf_writer.update_tag_attribute(figure_id, "alt", alt_text)
                        changes_made = True
                        logger.info(f"Añadido Alt a figura {figure_id}")
                
                # Verificar si la imagen contiene texto
                if autodetect_text and self._is_likely_text_image(figure):
                    if not figure.get("actualtext"):
                        actual_text = self._extract_text_from_image(figure)
                        if actual_text:
                            self.pdf_writer.update_tag_attribute(figure_id, "actualtext", actual_text)
                            changes_made = True
                            logger.info(f"Añadido ActualText a figura {figure_id} con texto")
            
            return changes_made
            
        except Exception as e:
            logger.exception(f"Error al corregir imágenes: {e}")
            return False
    
    def add_alt_text(self, figure_id: str, alt_text: str) -> bool:
        """
        Añade texto alternativo a una figura específica.
        
        Args:
            figure_id: Identificador de la figura
            alt_text: Texto alternativo a añadir
            
        Returns:
            bool: True si se realizó la corrección
            
        Referencias:
            - Matterhorn: 13-004
            - Tagged PDF: 5.5.2 (Alt)
        """
        try:
            if self.pdf_writer is None:
                logger.error("No hay PDFWriter configurado para aplicar correcciones")
                return False
            
            logger.info(f"Añadiendo Alt '{alt_text}' a figura {figure_id}")
            return self.pdf_writer.update_tag_attribute(figure_id, "alt", alt_text)
            
        except Exception as e:
            logger.exception(f"Error al añadir Alt a figura {figure_id}: {e}")
            return False
    
    def add_actual_text(self, figure_id: str, actual_text: str) -> bool:
        """
        Añade ActualText a una figura con texto.
        
        Args:
            figure_id: Identificador de la figura
            actual_text: Texto real a añadir
            
        Returns:
            bool: True si se realizó la corrección
            
        Referencias:
            - Matterhorn: 13-008
            - Tagged PDF: 5.5.3 (ActualText)
        """
        try:
            if self.pdf_writer is None:
                logger.error("No hay PDFWriter configurado para aplicar correcciones")
                return False
            
            logger.info(f"Añadiendo ActualText a figura {figure_id}")
            return self.pdf_writer.update_tag_attribute(figure_id, "actualtext", actual_text)
            
        except Exception as e:
            logger.exception(f"Error al añadir ActualText a figura {figure_id}: {e}")
            return False
    
    def ocr_image(self, image_data: bytes, lang: str = "spa") -> str:
        """
        Realiza OCR en una imagen.
        
        Args:
            image_data: Datos binarios de la imagen
            lang: Código de idioma para OCR
            
        Returns:
            str: Texto extraído
        """
        try:
            # Crear archivo temporal para la imagen
            with tempfile.NamedTemporaryFile(suffix=".png", delete=False) as temp_file:
                temp_file.write(image_data)
                temp_path = temp_file.name
            
            # Realizar OCR
            try:
                img = Image.open(temp_path)
                text = pytesseract.image_to_string(img, lang=lang)
                text = text.strip()
                logger.debug(f"OCR realizado con éxito: {len(text)} caracteres")
                return text
            finally:
                # Eliminar archivo temporal
                if os.path.exists(temp_path):
                    os.unlink(temp_path)
                    
        except Exception as e:
            logger.exception(f"Error al realizar OCR: {e}")
            return ""
    
    def _find_figures(self, elements: List[Dict], path: str = "") -> List[Dict]:
        """
        Encuentra todas las figuras en la estructura de forma recursiva.
        
        Args:
            elements: Lista de elementos de estructura
            path: Ruta de anidamiento actual
            
        Returns:
            List[Dict]: Lista de figuras encontradas con información de contexto
        """
        figures = []
        
        for i, element in enumerate(elements):
            element_type = element.get("type", "")
            current_path = f"{path}/{i}:{element_type}"
            
            if element_type == "Figure":
                # Añadir información de contexto a la figura
                element["_path"] = current_path
                figures.append(element)
            
            # Buscar figuras en los hijos
            if element.get("children"):
                child_figures = self._find_figures(element["children"], current_path)
                figures.extend(child_figures)
        
        return figures
    
    def _generate_alt_text(self, figure: Dict) -> str:
        """
        Genera texto alternativo para una figura.
        
        Args:
            figure: Diccionario representando una figura
            
        Returns:
            str: Texto alternativo generado
        """
        # Si hay un nombre o descripción disponible, usarlo
        if figure.get("name"):
            return self._clean_filename_for_alt(figure["name"])
        
        # Si la figura tiene una imagen asociada, intentar generar una descripción
        if figure.get("image_data"):
            # Intentar OCR
            ocr_text = self.ocr_image(figure["image_data"])
            if ocr_text:
                return ocr_text[:250]  # Limitar longitud
        
        # Texto genérico basado en contexto
        return "Imagen"
    
    def _clean_filename_for_alt(self, filename: str) -> str:
        """
        Limpia un nombre de archivo para usar como Alt.
        
        Args:
            filename: Nombre de archivo
            
        Returns:
            str: Texto Alt limpio
        """
        # Eliminar extensión
        if "." in filename:
            filename = filename.rsplit(".", 1)[0]
        
        # Reemplazar guiones bajos y guiones por espacios
        filename = filename.replace("_", " ").replace("-", " ")
        
        # Capitalizar palabras
        words = filename.split()
        if words:
            words = [w.capitalize() for w in words]
            filename = " ".join(words)
        
        return filename
    
    def _is_likely_text_image(self, figure: Dict) -> bool:
        """
        Determina si una imagen probablemente contiene texto.
        
        Args:
            figure: Diccionario representando una figura
            
        Returns:
            bool: True si la imagen probablemente contiene texto
        """
        # Implementación simplificada - en implementación real se analizaría la imagen
        # Usando técnicas de procesamiento de imágenes
        
        # Simulación de detección
        if figure.get("image_data"):
            # Algunas heurísticas podrían incluir:
            # - Detectar bordes horizontales/verticales densos (como líneas de texto)
            # - Analizar histograma de colores (texto suele ser bimodal)
            # - Razón de aspecto y posición en el documento
            return True
        
        return False
    
    def _extract_text_from_image(self, figure: Dict) -> str:
        """
        Extrae texto de una imagen usando OCR.
        
        Args:
            figure: Diccionario representando una figura
            
        Returns:
            str: Texto extraído
        """
        if not figure.get("image_data"):
            return ""
        
        return self.ocr_image(figure["image_data"])