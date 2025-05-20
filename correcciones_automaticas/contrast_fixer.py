#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Corrección automática de contraste según PDF/UA y WCAG.
Detecta y mejora contraste de texto.
"""

from typing import Dict, List, Optional, Tuple
import re
from loguru import logger

from wcag_contrast_ratio import rgb as contrast_ratio


class ContrastFixer:
    """
    Clase para corregir problemas de contraste según PDF/UA y WCAG.
    Detecta texto con bajo contraste y sugiere o aplica colores alternativos.
    """
    
    def __init__(self, pdf_writer=None):
        """
        Inicializa el corrector de contraste.
        
        Args:
            pdf_writer: Instancia opcional de PDFWriter
        """
        self.pdf_writer = pdf_writer
        self.min_contrast_ratio_normal = 4.5  # WCAG AA para texto normal
        self.min_contrast_ratio_large = 3.0   # WCAG AA para texto grande
        self.large_text_threshold = 18        # Tamaño para considerar texto grande (puntos)
        logger.info("ContrastFixer inicializado")
    
    def set_pdf_writer(self, pdf_writer):
        """Establece el escritor de PDF a utilizar"""
        self.pdf_writer = pdf_writer
    
    def fix_all_contrast(self, pdf_loader) -> bool:
        """
        Corrige todos los problemas de contraste en el documento.
        
        Args:
            pdf_loader: Instancia de PDFLoader con el documento cargado
            
        Returns:
            bool: True si se realizaron correcciones
            
        Referencias:
            - Matterhorn: 04-001
            - Tagged PDF: 5.1.1 (Color, BackgroundColor)
        """
        try:
            if self.pdf_writer is None:
                logger.error("No hay PDFWriter configurado para aplicar correcciones")
                return False
            
            if not pdf_loader or not pdf_loader.doc:
                logger.error("No hay documento cargado para corregir contraste")
                return False
            
            # Detectar problemas de contraste
            contrast_issues = self._detect_contrast_issues(pdf_loader)
            
            if not contrast_issues:
                logger.info("No se encontraron problemas de contraste")
                return False
            
            logger.info(f"Encontrados {len(contrast_issues)} problemas de contraste")
            
            # Corregir cada problema
            changes_made = False
            
            for issue in contrast_issues:
                fixed = self._fix_contrast_issue(issue)
                if fixed:
                    changes_made = True
            
            return changes_made
            
        except Exception as e:
            logger.exception(f"Error al corregir problemas de contraste: {e}")
            return False
    
    def add_color_attributes(self, element_id: str, text_color: Tuple[int, int, int], bg_color: Tuple[int, int, int]) -> bool:
        """
        Añade atributos de color a un elemento.
        
        Args:
            element_id: Identificador del elemento
            text_color: Color de texto en formato RGB (0-255)
            bg_color: Color de fondo en formato RGB (0-255)
            
        Returns:
            bool: True si se añadieron los atributos
        """
        try:
            if self.pdf_writer is None:
                logger.error("No hay PDFWriter configurado para aplicar correcciones")
                return False
            
            # Convertir a formato hexadecimal
            text_color_hex = f"#{text_color[0]:02x}{text_color[1]:02x}{text_color[2]:02x}"
            bg_color_hex = f"#{bg_color[0]:02x}{bg_color[1]:02x}{bg_color[2]:02x}"
            
            logger.info(f"Añadiendo Color='{text_color_hex}' y BackgroundColor='{bg_color_hex}' a elemento {element_id}")
            
            # En implementación real, se actualizarían los atributos
            # self.pdf_writer.update_tag_attribute(element_id, "color", text_color_hex)
            # self.pdf_writer.update_tag_attribute(element_id, "background_color", bg_color_hex)
            
            return True
            
        except Exception as e:
            logger.exception(f"Error al añadir atributos de color: {e}")
            return False
    
    def suggest_color_improvements(self, text_color: Tuple[int, int, int], bg_color: Tuple[int, int, int], target_ratio: float = 4.5) -> Dict:
        """
        Sugiere mejoras de colores para cumplir con el ratio de contraste objetivo.
        
        Args:
            text_color: Color de texto actual en formato RGB (0-255)
            bg_color: Color de fondo actual en formato RGB (0-255)
            target_ratio: Ratio de contraste objetivo
            
        Returns:
            Dict: Sugerencias de mejora
        """
        try:
            # Convertir a formato hexadecimal para la biblioteca colorcontrast
            text_color_hex = f"#{text_color[0]:02x}{text_color[1]:02x}{text_color[2]:02x}"
            bg_color_hex = f"#{bg_color[0]:02x}{bg_color[1]:02x}{bg_color[2]:02x}"
            
            # Calcular ratio actual
            current_ratio = contrast_ratio(text_color_hex, bg_color_hex)
            
            # Si ya cumple, no sugerir cambios
            if current_ratio >= target_ratio:
                return {
                    "current_ratio": current_ratio,
                    "target_ratio": target_ratio,
                    "already_compliant": True,
                    "suggestions": []
                }
            
            # Generar sugerencias
            suggestions = []
            
            # Opción 1: Oscurecer el texto
            darker_text = self._darken_color(text_color)
            darker_text_hex = f"#{darker_text[0]:02x}{darker_text[1]:02x}{darker_text[2]:02x}"
            darker_ratio = contrast_ratio(darker_text_hex, bg_color_hex)
            
            if darker_ratio >= target_ratio:
                suggestions.append({
                    "text_color": darker_text,
                    "bg_color": bg_color,
                    "ratio": darker_ratio,
                    "description": "Texto más oscuro"
                })
            
            # Opción 2: Aclarar el fondo
            lighter_bg = self._lighten_color(bg_color)
            lighter_bg_hex = f"#{lighter_bg[0]:02x}{lighter_bg[1]:02x}{lighter_bg[2]:02x}"
            lighter_ratio = contrast_ratio(text_color_hex, lighter_bg_hex)
            
            if lighter_ratio >= target_ratio:
                suggestions.append({
                    "text_color": text_color,
                    "bg_color": lighter_bg,
                    "ratio": lighter_ratio,
                    "description": "Fondo más claro"
                })
            
            # Opción 3: Negro sobre blanco (máximo contraste)
            black_white_ratio = contrast_ratio("#000000", "#ffffff")
            suggestions.append({
                "text_color": (0, 0, 0),
                "bg_color": (255, 255, 255),
                "ratio": black_white_ratio,
                "description": "Negro sobre blanco (máximo contraste)"
            })
            
            return {
                "current_ratio": current_ratio,
                "target_ratio": target_ratio,
                "already_compliant": False,
                "suggestions": suggestions
            }
            
        except Exception as e:
            logger.exception(f"Error al sugerir mejoras de color: {e}")
            return {
                "error": str(e),
                "suggestions": []
            }
    
    def _detect_contrast_issues(self, pdf_loader) -> List[Dict]:
        """
        Detecta problemas de contraste en el documento.
        
        Args:
            pdf_loader: Instancia de PDFLoader con el documento cargado
            
        Returns:
            List[Dict]: Lista de problemas de contraste
        """
        contrast_issues = []
        
        # Recorrer páginas
        for page_num in range(pdf_loader.doc.page_count):
            # Obtener elementos visuales de la página
            elements = pdf_loader.get_visual_content(page_num)
            
            for element in elements:
                if element["type"] == "text":
                    # Verificar contraste (simulado)
                    # En implementación real, se extraerían colores reales
                    text_color = (0, 0, 0)  # Negro por defecto
                    bg_color = (255, 255, 255)  # Blanco por defecto
                    font_size = element.get("font_size", 0)
                    
                    # Simulación de texto con bajo contraste
                    if page_num % 2 == 0 and len(element.get("content", "")) > 20:
                        # Simulación: texto gris claro sobre blanco
                        text_color = (180, 180, 180)
                        
                        # Calcular ratio
                        text_color_hex = f"#{text_color[0]:02x}{text_color[1]:02x}{text_color[2]:02x}"
                        bg_color_hex = f"#{bg_color[0]:02x}{bg_color[1]:02x}{bg_color[2]:02x}"
                        ratio = contrast_ratio(text_color_hex, bg_color_hex)
                        
                        # Determinar umbral según tamaño
                        threshold = self.min_contrast_ratio_large if font_size >= self.large_text_threshold else self.min_contrast_ratio_normal
                        
                        if ratio < threshold:
                            contrast_issues.append({
                                "id": f"contrast-{page_num}-{len(contrast_issues)}",
                                "element_id": element.get("id", f"text-{page_num}-{len(contrast_issues)}"),
                                "page": page_num,
                                "content": element.get("content", "")[:30] + "...",
                                "text_color": text_color,
                                "bg_color": bg_color,
                                "font_size": font_size,
                                "current_ratio": ratio,
                                "required_ratio": threshold
                            })
        
        return contrast_issues
    
    def _fix_contrast_issue(self, issue: Dict) -> bool:
        """
        Corrige un problema de contraste.
        
        Args:
            issue: Información del problema
            
        Returns:
            bool: True si se corrigió el problema
        """
        element_id = issue.get("element_id", "unknown")
        text_color = issue.get("text_color", (0, 0, 0))
        bg_color = issue.get("bg_color", (255, 255, 255))
        target_ratio = issue.get("required_ratio", self.min_contrast_ratio_normal)
        
        # Obtener sugerencias
        suggestions = self.suggest_color_improvements(text_color, bg_color, target_ratio)
        
        if not suggestions.get("suggestions"):
            logger.warning(f"No se pudieron generar sugerencias para el problema de contraste en {element_id}")
            return False
        
        # Usar la primera sugerencia
        suggestion = suggestions["suggestions"][0]
        new_text_color = suggestion["text_color"]
        new_bg_color = suggestion["bg_color"]
        
        # Aplicar cambios
        return self.add_color_attributes(element_id, new_text_color, new_bg_color)
    
    def _darken_color(self, color: Tuple[int, int, int]) -> Tuple[int, int, int]:
        """
        Oscurece un color.
        
        Args:
            color: Color en formato RGB (0-255)
            
        Returns:
            Tuple[int, int, int]: Color oscurecido
        """
        # Reducir cada componente para oscurecer
        return (
            max(0, int(color[0] * 0.7)),
            max(0, int(color[1] * 0.7)),
            max(0, int(color[2] * 0.7))
        )
    
    def _lighten_color(self, color: Tuple[int, int, int]) -> Tuple[int, int, int]:
        """
        Aclara un color.
        
        Args:
            color: Color en formato RGB (0-255)
            
        Returns:
            Tuple[int, int, int]: Color aclarado
        """
        # Aumentar cada componente para aclarar
        return (
            min(255, int(color[0] + (255 - color[0]) * 0.7)),
            min(255, int(color[1] + (255 - color[1]) * 0.7)),
            min(255, int(color[2] + (255 - color[2]) * 0.7))
        )