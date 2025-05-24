#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Validación de idioma según PDF/UA.
Verifica declaración de idioma en documento y elementos.

Este módulo implementa validaciones para los siguientes checkpoints Matterhorn:
- 11-001: Idioma natural para texto en el contenido de página
- 11-002: Idioma natural para texto en atributos Alt, ActualText y E
- 11-003: Idioma natural en las entradas del Outline (marcadores)
- 11-004: Idioma natural en la entrada Contents para anotaciones
- 11-005: Idioma natural en la entrada TU para campos de formulario
- 11-006: Idioma natural para metadatos del documento
- 11-007: Idioma natural no es apropiado
"""

from typing import Dict, List, Optional, Set, Tuple, Any
import re
from pathlib import Path
import json
import os
from loguru import logger
from collections import defaultdict
import langcodes  # Biblioteca para validación robusta de códigos de idioma

class LanguageValidator:
    """
    Valida la declaración de idioma según requisitos de PDF/UA.
    Verifica Lang a nivel de documento y elementos.
    """
    
    def __init__(self):
        """Inicializa el validador de idioma"""
        # Cargar definiciones de idiomas válidos
        self.language_codes = self._load_language_codes()
        
        # Idiomas comunes para ayudar con sugerencias cuando se detectan códigos inválidos
        self.common_languages = {
            "en": "English", "es": "Spanish", "fr": "French", "de": "German", 
            "it": "Italian", "pt": "Portuguese", "ru": "Russian", "zh": "Chinese",
            "ja": "Japanese", "ko": "Korean", "ar": "Arabic", "hi": "Hindi"
        }
        
        # Inicializar referencia al PDF loader (se configurará más tarde)
        self.pdf_loader = None
        
        logger.info("LanguageValidator inicializado")
    
    def set_pdf_loader(self, pdf_loader):
        """
        Establece la referencia al cargador de PDF.
        
        Args:
            pdf_loader: Instancia de PDFLoader con el documento cargado
        """
        self.pdf_loader = pdf_loader
        logger.debug("PDFLoader establecido en LanguageValidator")
    
    def validate(self, metadata: Dict, structure_tree: Dict) -> List[Dict]:
        """
        Valida la declaración de idioma en el documento.
        
        Args:
            metadata: Diccionario con metadatos extraídos del PDF
            structure_tree: Diccionario representando la estructura lógica
            
        Returns:
            List[Dict]: Lista de problemas detectados
            
        Referencias:
            - Matterhorn: 11-001 a 11-007 (Declared Natural Language)
            - Tagged PDF: 5.5.1 (Lang)
        """
        issues = []
        
        # Checkpoint 11-006: Verificar idioma a nivel de documento
        if not metadata.get("has_lang", False):
            issues.append({
                "checkpoint": "11-006",
                "severity": "error",
                "description": "No se puede determinar el idioma natural para los metadatos del documento",
                "fix_description": "Establecer el atributo Lang en el diccionario Catalog",
                "fixable": True,
                "page": "all",
                "element_type": "Document"
            })
        elif not self._is_valid_language_code(metadata.get("language", "")):
            issues.append({
                "checkpoint": "11-007",
                "severity": "warning",
                "description": f"El código de idioma del documento '{metadata.get('language', '')}' no es apropiado",
                "fix_description": "Establecer un código de idioma válido (p. ej., 'es-ES', 'en-US')",
                "fixable": True,
                "page": "all",
                "element_type": "Document"
            })
        
        # Si no hay estructura, validar componentes adicionales
        if not structure_tree or not structure_tree.get("children"):
            logger.warning("Documento sin estructura lógica, validando componentes adicionales")
            
            # Validar documento sin estructura
            no_structure_issues = self._validate_document_without_structure()
            issues.extend(no_structure_issues)
            
            logger.info(f"Validación de idioma completada: {len(issues)} problemas encontrados")
            return issues
        
        # Verificar idioma en elementos de estructura
        if structure_tree.get("children"):
            doc_lang = metadata.get("language", "")
            structure_issues = self._validate_element_languages(structure_tree.get("children", []), doc_lang)
            issues.extend(structure_issues)
        
        # Validar componentes adicionales (no en la estructura)
        additional_issues = self._validate_additional_components(doc_lang=metadata.get("language", ""))
        issues.extend(additional_issues)
        
        logger.info(f"Validación de idioma completada: {len(issues)} problemas encontrados")
        return issues
    
    def _validate_element_languages(self, elements: List[Dict], parent_lang: str, path: str = "", page: int = None) -> List[Dict]:
        """
        Valida los idiomas de los elementos de forma recursiva.
        
        Args:
            elements: Lista de elementos de estructura
            parent_lang: Idioma del elemento padre
            path: Ruta de anidamiento actual
            page: Número de página actual
            
        Returns:
            List[Dict]: Lista de problemas detectados
        """
        issues = []
        
        for i, element in enumerate(elements):
            element_type = element.get("type", "")
            element_page = element.get("page", page)
            current_path = f"{path}/{i}:{element_type}"
            
            # Obtener ID del elemento si existe
            element_id = None
            if "element" in element:
                element_id = id(element["element"])
            
            # Determinar el idioma del elemento actual
            element_lang = self._get_element_language(element)
            
            # Si no tiene idioma propio, hereda del padre
            effective_lang = element_lang if element_lang else parent_lang
            
            # Checkpoint 11-001: Texto en página sin idioma determinable
            if (element_type in ["P", "Span", "H1", "H2", "H3", "H4", "H5", "H6"] and 
                element.get("text") and len(element.get("text", "").strip()) > 0 and 
                not effective_lang):
                issues.append({
                    "checkpoint": "11-001",
                    "severity": "error",
                    "description": f"No se puede determinar el idioma natural para el texto en '{element_type}'",
                    "fix_description": "Establecer el atributo Lang para este elemento o un ancestro",
                    "fixable": True,
                    "page": element_page,
                    "path": current_path,
                    "element_id": element_id,
                    "element_type": element_type
                })
            
            # Checkpoint 11-002: Alt, ActualText o E sin idioma determinable
            if ((self._has_attribute(element, "alt") or 
                 self._has_attribute(element, "actualtext") or 
                 self._has_attribute(element, "e")) and 
                not effective_lang):
                issues.append({
                    "checkpoint": "11-002",
                    "severity": "error",
                    "description": f"No se puede determinar el idioma natural para Alt, ActualText o E en elemento {element_type}",
                    "fix_description": "Establecer el atributo Lang en el elemento",
                    "fixable": True,
                    "page": element_page,
                    "path": current_path,
                    "element_id": element_id,
                    "element_type": element_type
                })
            
            # Checkpoint 11-007: Código de idioma no apropiado
            if element_lang and not self._is_valid_language_code(element_lang):
                issues.append({
                    "checkpoint": "11-007",
                    "severity": "warning",
                    "description": f"El código de idioma '{element_lang}' en elemento {element_type} no es apropiado",
                    "fix_description": "Establecer un código de idioma válido (p. ej., 'es-ES', 'en-US')",
                    "fixable": True,
                    "page": element_page,
                    "path": current_path,
                    "element_id": element_id,
                    "element_type": element_type
                })
            
            # Verificar hijos recursivamente
            if element.get("children"):
                child_issues = self._validate_element_languages(
                    element["children"], 
                    effective_lang, 
                    current_path, 
                    element_page
                )
                issues.extend(child_issues)
        
        return issues
    
    def _validate_document_without_structure(self) -> List[Dict]:
        """
        Valida aspectos de idioma en un documento sin estructura.
        
        Returns:
            List[Dict]: Lista de problemas detectados
        """
        issues = []
        
        # Si no hay pdf_loader, no podemos hacer más validaciones
        if not self.pdf_loader or not self.pdf_loader.doc:
            return issues
        
        # Intentar detectar texto sin estructura para validar idioma
        for page_num in range(self.pdf_loader.doc.page_count):
            page = self.pdf_loader.doc[page_num]
            
            # Extraer bloques de texto
            blocks = page.get_text("dict", flags=0)["blocks"]
            for block in blocks:
                if block["type"] == 0:  # Bloque de texto
                    # Checkpoint 11-001: Texto sin idioma determinable
                    issues.append({
                        "checkpoint": "11-001",
                        "severity": "error",
                        "description": "Texto sin estructura con idioma indeterminable",
                        "fix_description": "Añadir estructura etiquetada con atributo Lang",
                        "fixable": True,
                        "page": page_num,
                        "element_type": "Text"
                    })
                    break  # Un solo problema por página es suficiente
        
        return issues
    
    def _validate_additional_components(self, doc_lang: str) -> List[Dict]:
        """
        Valida idioma en componentes adicionales (marcadores, anotaciones, formularios).
        
        Args:
            doc_lang: Idioma del documento
            
        Returns:
            List[Dict]: Lista de problemas detectados
        """
        issues = []
        
        # Si no hay pdf_loader, no podemos validar estos componentes
        if not self.pdf_loader or not self.pdf_loader.doc:
            return issues
        
        # Checkpoint 11-003: Verificar idioma en marcadores (Outline)
        outline_issues = self._validate_outline_language(doc_lang)
        issues.extend(outline_issues)
        
        # Checkpoint 11-004 y 11-005: Verificar idioma en anotaciones y campos de formulario
        annotations_issues = self._validate_annotations_language(doc_lang)
        issues.extend(annotations_issues)
        
        return issues
    
    def _validate_outline_language(self, doc_lang: str) -> List[Dict]:
        """
        Valida el idioma en los marcadores (Outline).
        
        Args:
            doc_lang: Idioma del documento
            
        Returns:
            List[Dict]: Lista de problemas detectados
        """
        issues = []
        
        try:
            # Verificar si hay marcadores
            toc = self.pdf_loader.doc.get_toc()
            if not toc:
                return issues
            
            has_lang = bool(doc_lang)
            
            # Si hay marcadores pero no hay idioma de documento, reportar problema
            if not has_lang:
                issues.append({
                    "checkpoint": "11-003",
                    "severity": "warning",
                    "description": "No se puede determinar el idioma natural en los marcadores (Outline)",
                    "fix_description": "Establecer un idioma para el documento",
                    "fixable": True,
                    "page": "all",
                    "element_type": "Outline"
                })
        except Exception as e:
            logger.error(f"Error al validar idioma en marcadores: {e}")
        
        return issues
    
    def _validate_annotations_language(self, doc_lang: str) -> List[Dict]:
        """
        Valida el idioma en anotaciones y campos de formulario.
        
        Args:
            doc_lang: Idioma del documento
            
        Returns:
            List[Dict]: Lista de problemas detectados
        """
        issues = []
        
        try:
            # Recorrer todas las páginas buscando anotaciones
            for page_num in range(self.pdf_loader.doc.page_count):
                page = self.pdf_loader.doc[page_num]
                
                # Verificar anotaciones en la página
                for annot in page.annots():
                    annot_type = annot.type[1]  # Obtener subtipo de anotación
                    
                    # Checkpoint 11-004: Anotaciones con Contents sin idioma determinable
                    if "content" in annot.info and annot.info["content"] and not doc_lang:
                        issues.append({
                            "checkpoint": "11-004",
                            "severity": "warning",
                            "description": f"No se puede determinar el idioma natural en el contenido de la anotación ({annot_type})",
                            "fix_description": "Establecer un idioma para el documento o la anotación",
                            "fixable": True,
                            "page": page_num,
                            "element_type": f"Annotation:{annot_type}"
                        })
                    
                    # Checkpoint 11-005: Campos de formulario (Widget) sin idioma determinable
                    if annot_type == "Widget":
                        # Intentar obtener el valor de TU (texto de interfaz de usuario)
                        has_tu = False
                        if hasattr(annot, "xref"):
                            xref = annot.xref
                            obj = self.pdf_loader.doc.xref_object(xref)
                            if obj and "TU" in obj:
                                has_tu = True
                                
                                # Si tiene TU pero no hay idioma de documento
                                if has_tu and not doc_lang:
                                    issues.append({
                                        "checkpoint": "11-005",
                                        "severity": "warning",
                                        "description": "No se puede determinar el idioma natural en la entrada TU para campo de formulario",
                                        "fix_description": "Establecer un idioma para el documento o el campo",
                                        "fixable": True,
                                        "page": page_num,
                                        "element_type": "FormField"
                                    })
        except Exception as e:
            logger.error(f"Error al validar idioma en anotaciones: {e}")
        
        return issues
    
    def _get_element_language(self, element: Dict) -> Optional[str]:
        """
        Obtiene el idioma asignado a un elemento.
        
        Args:
            element: Elemento de estructura
            
        Returns:
            Optional[str]: Código de idioma o None si no está definido
        """
        # Verificar si el elemento tiene atributo Lang directo
        if "lang" in element:
            return element["lang"]
        
        # Verificar si está en atributos
        if "attributes" in element and "lang" in element["attributes"]:
            return element["attributes"]["lang"]
        
        # Verificar objeto pikepdf si está disponible
        if "element" in element and hasattr(element["element"], "Lang"):
            return str(element["element"].Lang)
            
        return None
    
    def _has_attribute(self, element: Dict, attr_name: str) -> bool:
        """
        Verifica si un elemento tiene un atributo específico.
        
        Args:
            element: Elemento de estructura
            attr_name: Nombre del atributo a verificar
            
        Returns:
            bool: True si el elemento tiene el atributo
        """
        # Normalizar nombre de atributo a minúsculas
        attr_name = attr_name.lower()
        
        # Verificar si el atributo está directamente en el elemento
        if attr_name in element:
            return bool(element[attr_name])
        
        # Verificar si está en el diccionario de atributos
        if "attributes" in element and attr_name in element["attributes"]:
            return bool(element["attributes"][attr_name])
        
        # Verificar en el objeto pikepdf si está disponible
        if "element" in element:
            pikepdf_element = element["element"]
            # Convertir primera letra a mayúscula para formato pikepdf
            pikepdf_attr = attr_name[0].upper() + attr_name[1:]
            if hasattr(pikepdf_element, pikepdf_attr):
                return True
            # También verificar formatos alternativos (Alt, alt, /Alt)
            alt_names = [f"/{pikepdf_attr}", attr_name, attr_name.upper()]
            for name in alt_names:
                if name in pikepdf_element:
                    return True
                    
        return False
    
    def _is_valid_language_code(self, lang_code: str) -> bool:
        """
        Verifica si un código de idioma es válido según BCP 47.
        
        Args:
            lang_code: Código de idioma a verificar
            
        Returns:
            bool: True si el código es válido
        """
        if not lang_code:
            return False
        
        try:
            # Intentar validar con langcodes (BCP 47 compliant)
            return langcodes.tag_is_valid(lang_code)
        except (ImportError, Exception):
            # Fallback a método básico si langcodes no está disponible
            return self._basic_language_validation(lang_code)
    
    def _basic_language_validation(self, lang_code: str) -> bool:
        """
        Método básico de validación de idioma sin dependencias externas.
        
        Args:
            lang_code: Código de idioma a verificar
            
        Returns:
            bool: True si el código parece válido
        """
        # Verificar si está en nuestro conjunto de códigos conocidos
        if lang_code in self.language_codes:
            return True
        
        # Formato básico: xx o xx-XX
        pattern = r'^[a-z]{2,3}(-[A-Z]{2,3})?$'
        return bool(re.match(pattern, lang_code))
    
    def _load_language_codes(self) -> Set[str]:
        """
        Carga un conjunto de códigos de idioma válidos.
        
        Returns:
            Set[str]: Conjunto de códigos de idioma válidos
        """
        # Intentar cargar desde archivo JSON si existe
        lang_file = Path(__file__).parent.parent.parent / "resources" / "language_codes.json"
        
        if lang_file.exists():
            try:
                with open(lang_file, "r", encoding="utf-8") as f:
                    return set(json.load(f))
            except Exception as e:
                logger.error(f"Error al cargar códigos de idioma: {e}")
        
        # Conjunto básico de códigos comunes si no se puede cargar el archivo
        return {
            "en", "en-US", "en-GB", "es", "es-ES", "es-MX", "fr", "fr-FR", "fr-CA", 
            "de", "de-DE", "it", "it-IT", "pt", "pt-BR", "pt-PT", "ru", "ru-RU", 
            "zh", "zh-CN", "zh-TW", "ja", "ja-JP", "ko", "ko-KR", "ar", "ar-SA", 
            "hi", "hi-IN", "bn", "bn-IN", "nl", "nl-NL", "tr", "tr-TR", "pl", "pl-PL",
            "uk", "uk-UA", "vi", "vi-VN", "th", "th-TH", "cs", "cs-CZ", "fi", "fi-FI",
            "sv", "sv-SE", "no", "no-NO", "da", "da-DK", "hu", "hu-HU", "he", "he-IL",
            "id", "id-ID", "ms", "ms-MY", "ca", "ca-ES", "eu", "eu-ES", "gl", "gl-ES",
            "ro", "ro-RO", "bg", "bg-BG", "sr", "sr-RS", "hr", "hr-HR", "el", "el-GR"
        }
    
    def get_language_suggestions(self, invalid_code: str) -> List[str]:
        """
        Sugiere códigos de idioma válidos para un código inválido.
        
        Args:
            invalid_code: Código de idioma inválido
            
        Returns:
            List[str]: Lista de sugerencias de códigos válidos
        """
        suggestions = []
        
        # Si está vacío, sugerir códigos comunes
        if not invalid_code:
            return ["en-US", "es-ES", "fr-FR", "de-DE"]
        
        # Si tiene guión, separar partes
        parts = invalid_code.split('-')
        
        # Buscar coincidencias parciales para la primera parte (código de idioma)
        if parts[0]:
            # Verificar coincidencias exactas en códigos de 2 o 3 letras
            if parts[0] in self.common_languages:
                base_lang = parts[0]
                suggestions.append(f"{base_lang}")
                suggestions.append(f"{base_lang}-{base_lang.upper()}")
                
                # Añadir códigos de región comunes para este idioma
                if base_lang == "en":
                    suggestions.extend(["en-US", "en-GB"])
                elif base_lang == "es":
                    suggestions.extend(["es-ES", "es-MX"])
                elif base_lang == "fr":
                    suggestions.extend(["fr-FR", "fr-CA"])
                elif base_lang == "pt":
                    suggestions.extend(["pt-BR", "pt-PT"])
                elif base_lang == "zh":
                    suggestions.extend(["zh-CN", "zh-TW"])
        
        # Si no encontramos sugerencias basadas en el código, dar opciones comunes
        if not suggestions:
            suggestions = ["en-US", "es-ES", "fr-FR", "de-DE"]
        
        return suggestions