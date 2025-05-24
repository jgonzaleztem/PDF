#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Módulo para corregir metadatos de documentos PDF según la normativa PDF/UA.
Implementa correcciones automáticas para los requisitos establecidos en:
- ISO 14289-1 (PDF/UA-1)
- Matterhorn Protocol (checkpoints 06-001 a 06-004, 07-001, 07-002, 11-006)
- Tagged PDF Best Practice Guide

Este módulo corrige:
- Metadatos XMP faltantes
- Flag PDF/UA
- Título del documento (dc:title)
- DisplayDocTitle
- Idioma del documento (Lang)
- Otros metadatos complementarios
"""

import re
import os
from datetime import datetime
from typing import Dict, Any, Optional, Tuple, List, Set
import langcodes  # Para validar códigos de idioma
from pathlib import Path
from loguru import logger

class MetadataFixer:
    """
    Clase para corregir metadatos en documentos PDF según PDF/UA.
    
    Implementa correcciones para los checkpoints del Matterhorn Protocol:
    - 06-001: Document does not contain an XMP metadata stream
    - 06-002: The XMP metadata stream does not include the PDF/UA identifier
    - 06-003: XMP metadata stream does not contain dc:title
    - 06-004: dc:title does not clearly identify the document
    - 07-001: ViewerPreferences dictionary does not contain a DisplayDocTitle entry
    - 07-002: ViewerPreferences dictionary contains a DisplayDocTitle entry with value of false
    - 11-006: Natural language for document metadata cannot be determined
    """
    
    def __init__(self, pdf_writer=None):
        """
        Inicializa el corrector de metadatos.
        
        Args:
            pdf_writer: Instancia opcional de PDFWriter para aplicar cambios
        """
        self.pdf_writer = pdf_writer
        
        # Cargar códigos de idioma ISO válidos
        self.valid_language_codes = self._load_language_codes()
        
        # Códigos ISO de idioma comunes para sugerencias
        self.common_languages = {
            "es": "es-ES", 
            "en": "en-US", 
            "fr": "fr-FR", 
            "de": "de-DE", 
            "it": "it-IT", 
            "pt": "pt-PT", 
            "ru": "ru-RU", 
            "zh": "zh-CN", 
            "ja": "ja-JP", 
            "ar": "ar-SA",
            "ca": "ca-ES"
        }
        
        # Títulos genéricos que deben ser reemplazados (ampliado)
        self.generic_titles = [
            "untitled", "sin título", "document", "documento", 
            "pdf document", "pdf", "new document", "documento nuevo",
            "documento pdf", "archivo pdf", "pdf file", "sin nombre",
            "doc", "noname", "no name", "unnamed"
        ]
        
        logger.info("MetadataFixer inicializado")
    
    def set_pdf_writer(self, pdf_writer):
        """Establece la instancia de PDFWriter a utilizar."""
        self.pdf_writer = pdf_writer
        logger.debug("PDFWriter actualizado en MetadataFixer")
    
    def fix_all_metadata(self, metadata: Dict, filename: str = "") -> bool:
        """
        Corrige todos los problemas de metadatos en un documento.
        
        Args:
            metadata: Diccionario con metadatos actuales del PDF
            filename: Nombre del archivo para generar título sugerido
            
        Returns:
            bool: True si se realizaron cambios
        """
        if not self.pdf_writer:
            logger.error("No hay PDFWriter configurado para aplicar cambios")
            return False
            
        logger.info(f"Iniciando corrección de metadatos para '{filename}'")
        
        # Preparar diccionario para modificaciones
        updated_metadata = {}
        changes_made = False
        need_pdf_ua_flag = False
        
        # 1. Corregir título (06-003, 06-004)
        if self.fix_title(metadata, updated_metadata, filename):
            changes_made = True
            
        # 2. Verificar flag PDF/UA (06-002)
        if self.fix_pdf_ua_flag(metadata, updated_metadata):
            changes_made = True
            need_pdf_ua_flag = True  # Marcar que necesitamos añadir explícitamente el flag
            # Eliminar esta clave para que no se procese como un metadato regular
            if "pdf_ua_flag" in updated_metadata:
                del updated_metadata["pdf_ua_flag"]
            
        # 3. Corregir DisplayDocTitle (07-001, 07-002)
        if self.fix_display_doc_title(metadata, updated_metadata):
            changes_made = True
            
        # 4. Corregir idioma del documento (11-006)
        if self.fix_document_language(metadata, updated_metadata):
            changes_made = True
        
        # 5. Complementar otros metadatos (autor, productor)
        if self.complement_metadata(metadata, updated_metadata):
            changes_made = True
            
        # 6. Corregir el orden de tabulación en páginas con anotaciones
        tab_order_fixed = self.pdf_writer.fix_tab_order()
        if tab_order_fixed:
            changes_made = True
        
        # Si hay cambios, aplicarlos al documento
        if changes_made:
            success = True
            
            # Aplicar cambios de metadatos si hay alguno
            if updated_metadata:
                logger.info(f"Aplicando {len(updated_metadata)} correcciones de metadatos")
                success = self.pdf_writer.update_metadata(updated_metadata)
            
            # Añadir explícitamente el flag PDF/UA si es necesario (como una operación separada)
            if need_pdf_ua_flag and success:
                logger.info("Aplicando flag PDF/UA explícitamente")
                success = self.pdf_writer.add_pdf_ua_flag()
            
            if success:
                logger.success("Metadatos corregidos exitosamente")
                return True
            else:
                logger.error("Error al aplicar correcciones de metadatos")
                return False
        else:
            logger.info("No se requieren correcciones de metadatos")
            return False
    
    def fix_title(self, current_metadata: Dict, updated_metadata: Dict, filename: str = "") -> bool:
        """
        Corrige problemas con el título del documento (checkpoints 06-003, 06-004).
        
        Args:
            current_metadata: Metadatos actuales
            updated_metadata: Metadatos a actualizar
            filename: Nombre del archivo para título sugerido
            
        Returns:
            bool: True si se realizaron cambios
        """
        title = current_metadata.get("title", "").strip()
        has_title = title != ""
        
        # Evaluar calidad del título existente
        if has_title:
            title_quality = self._evaluate_title_quality(title)
            if title_quality >= 0.7:  # Umbral para calidad aceptable
                return False  # El título es adecuado, no requiere cambios
        
        # Generar título sugerido a partir del nombre de archivo
        suggested_title = self._generate_title_from_filename(filename)
        
        # Actualizar título
        updated_metadata["title"] = suggested_title
        logger.info(f"Título corregido: '{suggested_title}'")
        return True
    
    def fix_pdf_ua_flag(self, current_metadata: Dict, updated_metadata: Dict) -> bool:
        """
        Añade flag PDF/UA a los metadatos (checkpoint 06-002).
        
        Args:
            current_metadata: Metadatos actuales
            updated_metadata: Metadatos a actualizar
            
        Returns:
            bool: True si se realizaron cambios
        """
        if not current_metadata.get("pdf_ua_flag", False):
            # Añadir flag PDF/UA
            updated_metadata["pdf_ua_flag"] = True
            logger.info("Flag PDF/UA añadido a metadatos XMP")
            return True
            
        # Verificar valor del flag (debe ser "1" según PDF/UA-1)
        pdf_ua_version = current_metadata.get("pdf_ua_version", "")
        if pdf_ua_version != "1":
            updated_metadata["pdf_ua_flag"] = True
            logger.info(f"Corregido valor de flag PDF/UA: '{pdf_ua_version}' -> '1'")
            return True
            
        return False
    
    def fix_display_doc_title(self, current_metadata: Dict, updated_metadata: Dict) -> bool:
        """
        Corrige DisplayDocTitle en diccionario ViewerPreferences (checkpoints 07-001, 07-002).
        
        Args:
            current_metadata: Metadatos actuales
            updated_metadata: Metadatos a actualizar
            
        Returns:
            bool: True si se realizaron cambios
        """
        # Verificar ViewerPreferences y DisplayDocTitle
        has_viewer_prefs = current_metadata.get("has_viewer_preferences", False)
        display_doc_title = current_metadata.get("display_doc_title", False)
        
        if not has_viewer_prefs or not display_doc_title:
            # Configurar DisplayDocTitle=true
            updated_metadata["display_doc_title"] = True
            logger.info("DisplayDocTitle configurado como true")
            return True
            
        return False
    
    def fix_document_language(self, current_metadata: Dict, updated_metadata: Dict) -> bool:
        """
        Corrige el idioma del documento (checkpoint 11-006).
        
        Args:
            current_metadata: Metadatos actuales
            updated_metadata: Metadatos a actualizar
            
        Returns:
            bool: True si se realizaron cambios
        """
        has_lang = current_metadata.get("has_lang", False)
        language = current_metadata.get("language", "")
        
        if not has_lang or not self._is_valid_language_code(language):
            # Obtener mejor sugerencia de idioma
            suggested_language = self._suggest_language(language)
            
            # Actualizar idioma
            updated_metadata["language"] = suggested_language
            logger.info(f"Idioma del documento configurado como '{suggested_language}'")
            return True
            
        return False
    
    def complement_metadata(self, current_metadata: Dict, updated_metadata: Dict) -> bool:
        """
        Complementa otros metadatos útiles pero no obligatorios para PDF/UA.
        
        Args:
            current_metadata: Metadatos actuales
            updated_metadata: Metadatos a actualizar
            
        Returns:
            bool: True si se realizaron cambios
        """
        changes_made = False
        
        # Añadir productor si no existe
        if not current_metadata.get("producer", ""):
            updated_metadata["producer"] = "PDF/UA Editor v1.0"
            changes_made = True
            
        # Añadir creator si no existe
        if not current_metadata.get("creator", ""):
            updated_metadata["creator"] = "PDF/UA Editor"
            changes_made = True
            
        # Fechas de creación y modificación
        if not current_metadata.get("creation_date", ""):
            updated_metadata["creation_date"] = datetime.now().strftime("%Y-%m-%dT%H:%M:%S")
            changes_made = True
            
        # La fecha de modificación siempre se actualiza
        updated_metadata["modification_date"] = datetime.now().strftime("%Y-%m-%dT%H:%M:%S")
        
        if changes_made:
            logger.info("Metadatos complementarios actualizados")
            
        return changes_made
    
    def _evaluate_title_quality(self, title: str) -> float:
        """
        Evalúa la calidad del título del documento.
        
        Args:
            title: Título a evaluar
            
        Returns:
            float: Puntuación de calidad (0.0-1.0)
        """
        if not title:
            return 0.0
            
        # Verificar si es un título genérico
        if title.lower() in self.generic_titles:
            return 0.1
            
        # Evaluar longitud (penalizar títulos demasiado cortos o largos)
        length_score = 0.0
        if len(title) < 3:
            length_score = 0.1
        elif len(title) < 10:
            length_score = 0.4
        elif len(title) < 100:
            length_score = min(len(title) / 50.0, 1.0)
        else:
            length_score = 0.7
        
        # Evaluar diversidad de palabras (penalizar títulos con pocas palabras distintas)
        words = title.split()
        unique_words = len(set(w.lower() for w in words))
        diversity_score = min(unique_words / 5.0, 1.0)
        
        # Evaluar formato (penalizar títulos en mayúsculas o minúsculas)
        format_score = 0.7
        if title.isupper():
            format_score = 0.4
        elif title.islower():
            format_score = 0.5
        elif title[0].isupper():
            format_score = 1.0
        
        # Combinar puntuaciones
        quality_score = (length_score * 0.4 + diversity_score * 0.4 + format_score * 0.2)
        
        return quality_score
    
    def _generate_title_from_filename(self, filename: str) -> str:
        """
        Genera un título sugerido a partir del nombre de archivo.
        
        Args:
            filename: Nombre del archivo
            
        Returns:
            str: Título sugerido
        """
        if not filename:
            return "Documento PDF"
            
        # Eliminar extensión y convertir a título legible
        base_name = os.path.splitext(filename)[0]
        
        # Reemplazar guiones y subrayados por espacios
        readable_name = base_name.replace('-', ' ').replace('_', ' ')
        
        # Capitalizar palabras para un título adecuado
        title = ' '.join(word.capitalize() for word in readable_name.split())
        
        # Si el título es muy corto, añadir sufijo
        if len(title) < 3:
            title = f"{title} - Documento PDF"
            
        return title
    
    def _is_valid_language_code(self, language_code: str) -> bool:
        """
        Verifica si un código de idioma es válido según BCP 47.
        
        Args:
            language_code: Código de idioma a verificar
            
        Returns:
            bool: True si el código es válido
        """
        if not language_code:
            return False
        
        try:
            # Usar langcodes para verificar validez
            return langcodes.tag_is_valid(language_code)
        except (ImportError, Exception):
            # Método alternativo si langcodes no está disponible
            return self._basic_language_validation(language_code)
    
    def _basic_language_validation(self, language_code: str) -> bool:
        """
        Método básico para validar código de idioma sin dependencias externas.
        
        Args:
            language_code: Código de idioma a verificar
            
        Returns:
            bool: True si el formato es válido
        """
        # Verificar si está en nuestro conjunto de códigos conocidos
        if language_code in self.valid_language_codes:
            return True
            
        # Formato básico: xx o xx-XX
        pattern = r'^[a-z]{2,3}(-[A-Z]{2,3})?$'
        return bool(re.match(pattern, language_code))
    
    def _suggest_language(self, current_language: str = "") -> str:
        """
        Sugiere un código de idioma válido basado en el actual (si existe).
        
        Args:
            current_language: Código de idioma actual
            
        Returns:
            str: Código de idioma sugerido
        """
        # Si no hay idioma actual, usar español como predeterminado
        if not current_language:
            return "es-ES"
        
        # Si el idioma actual es uno de los comunes pero sin región, sugerir versión completa
        current_lower = current_language.lower()
        if current_lower in self.common_languages:
            return self.common_languages[current_lower]
        
        # Buscar similitudes para idiomas comunes
        for code, full_code in self.common_languages.items():
            if current_lower.startswith(code) or code in current_lower:
                return full_code
        
        # Si no se encuentra ninguna correspondencia, devolver un código válido
        return "es-ES"  # Español por defecto
    
    def _load_language_codes(self) -> Set[str]:
        """
        Carga un conjunto de códigos de idioma válidos.
        
        Returns:
            Set[str]: Conjunto de códigos de idioma válidos
        """
        # Intentar cargar desde archivo JSON si existe
        lang_file = Path(__file__).parent.parent / "resources" / "language_codes.json"
        
        if lang_file.exists():
            try:
                import json
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
            return ["es-ES", "en-US", "fr-FR", "de-DE"]
        
        # Si tiene guión, separar partes
        parts = invalid_code.split('-')
        
        # Buscar coincidencias parciales para la primera parte (código de idioma)
        if parts[0]:
            # Verificar coincidencias exactas en códigos de 2 o 3 letras
            if parts[0] in self.common_languages:
                base_lang = parts[0]
                suggestions.append(f"{base_lang}")
                suggestions.append(self.common_languages[base_lang])
                
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
            suggestions = ["es-ES", "en-US", "fr-FR", "de-DE"]
        
        return suggestions

    def generate_pdf_ua_metadata(self, title: str, language: str = "es-ES") -> Dict:
        """
        Genera un conjunto completo de metadatos compatibles con PDF/UA.
        
        Args:
            title: Título del documento
            language: Código de idioma del documento
            
        Returns:
            Dict: Metadatos completos para PDF/UA
        """
        # Asegurar que el título e idioma sean válidos
        if not title:
            title = "Documento PDF"
            
        if not self._is_valid_language_code(language):
            language = "es-ES"
            
        # Crear metadata completo para PDF/UA
        metadata = {
            "title": title,
            "pdf_ua_flag": True,
            "display_doc_title": True,
            "language": language,
            "creator": "PDF/UA Editor",
            "producer": "PDF/UA Editor v1.0",
            "creation_date": datetime.now().strftime("%Y-%m-%dT%H:%M:%S"),
            "modification_date": datetime.now().strftime("%Y-%m-%dT%H:%M:%S")
        }
        
        return metadata
        
    def generate_pdf_ua_xmp_namespace(self) -> Dict:
        """
        Genera un diccionario con el namespace de PDF/UA para XMP.
        
        Returns:
            Dict: Namespace de PDF/UA para XMP
        """
        # Namespace de PDF/UA según Tagged PDF Best Practice Guide
        ns_pdf_ua = {
            "pdfuaid": "http://www.aiim.org/pdfua/ns/id/"
        }
        
        return ns_pdf_ua
    
    def create_pdf_ua_flag_xml(self) -> str:
        """
        Crea el XML para el flag PDF/UA en XMP.
        
        Returns:
            str: Fragmento XML con el flag PDF/UA
        """
        # Basado en el ejemplo de Tagged PDF Best Practice Guide Annex A
        xmp_fragment = """
        <rdf:Description rdf:about=""
            xmlns:pdfuaid="http://www.aiim.org/pdfua/ns/id/">
            <pdfuaid:part>1</pdfuaid:part>
        </rdf:Description>
        """
        return xmp_fragment