#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Validación de metadatos según PDF/UA.
Verifica título, idioma, XMP y otros requisitos según Matterhorn Protocol.

Este módulo implementa validaciones para los siguientes checkpoints Matterhorn:
- 06-001 a 06-004: Metadatos XMP (existencia, PDF/UA flag, title)
- 07-001 a 07-002: Diccionario ViewerPreferences (DisplayDocTitle)
- 11-006 a 11-007: Idioma declarado

Referencias:
- ISO 14289-1 (PDF/UA-1)
- Matterhorn Protocol 1.1
- Tagged PDF Best Practice Guide
"""

from typing import Dict, List, Optional, Any, Set, Tuple
import re
from collections import defaultdict
from loguru import logger

class MetadataValidator:
    """
    Valida los metadatos del documento según requisitos de PDF/UA.
    Verifica título, idioma, identificador PDF/UA y otras propiedades
    según los checkpoints definidos en Matterhorn Protocol.
    """
    
    def __init__(self):
        """Inicializa el validador de metadatos"""
        self.pdf_loader = None
        self.language_codes = set([
            "aa", "ab", "ae", "af", "ak", "am", "an", "ar", "as", "av", "ay", "az", 
            "ba", "be", "bg", "bh", "bi", "bm", "bn", "bo", "br", "bs", 
            "ca", "ce", "ch", "co", "cr", "cs", "cu", "cv", "cy", 
            "da", "de", "dv", "dz", 
            "ee", "el", "en", "eo", "es", "et", "eu", 
            "fa", "ff", "fi", "fj", "fo", "fr", "fy", 
            "ga", "gd", "gl", "gn", "gu", "gv", 
            "ha", "he", "hi", "ho", "hr", "ht", "hu", "hy", "hz", 
            "ia", "id", "ie", "ig", "ii", "ik", "io", "is", "it", "iu", 
            "ja", "jv", 
            "ka", "kg", "ki", "kj", "kk", "kl", "km", "kn", "ko", "kr", "ks", "ku", "kv", "kw", "ky", 
            "la", "lb", "lg", "li", "ln", "lo", "lt", "lu", "lv", 
            "mg", "mh", "mi", "mk", "ml", "mn", "mr", "ms", "mt", "my", 
            "na", "nb", "nd", "ne", "ng", "nl", "nn", "no", "nr", "nv", "ny", 
            "oc", "oj", "om", "or", "os", 
            "pa", "pi", "pl", "ps", "pt", 
            "qu", 
            "rm", "rn", "ro", "ru", "rw", 
            "sa", "sc", "sd", "se", "sg", "si", "sk", "sl", "sm", "sn", "so", "sq", "sr", "ss", "st", "su", "sv", "sw", 
            "ta", "te", "tg", "th", "ti", "tk", "tl", "tn", "to", "tr", "ts", "tt", "tw", "ty", 
            "ug", "uk", "ur", "uz", 
            "ve", "vi", "vo", 
            "wa", "wo", 
            "xh", 
            "yi", "yo", 
            "za", "zh", "zu"
        ])
        # Añadir códigos específicos de país también (ej: es-ES, en-US)
        for lang in list(self.language_codes):
            # Añadir formas comunes con países
            country_codes = ["US", "GB", "CA", "AU", "FR", "DE", "ES", "MX", "BR", "PT", "CN", "TW", "JP", "KR", "RU"]
            for country in country_codes:
                self.language_codes.add(f"{lang}-{country}")

        logger.info("MetadataValidator inicializado")
    
    def set_pdf_loader(self, pdf_loader):
        """
        Establece la referencia al cargador de PDF.
        
        Args:
            pdf_loader: Instancia de PDFLoader con el documento cargado
        """
        self.pdf_loader = pdf_loader
        logger.debug("PDFLoader establecido en MetadataValidator")
    
    def validate(self, metadata: Dict) -> List[Dict]:
        """
        Valida los metadatos del documento según requisitos de PDF/UA.
        
        Args:
            metadata: Diccionario con metadatos extraídos del PDF
            
        Returns:
            List[Dict]: Lista de problemas detectados
            
        Referencias:
            - Matterhorn: 06-001 a 06-004 (metadatos), 07-001 a 07-002 (diccionario)
            - Tagged PDF: 3.3 (Document level attributes), Anexo A (PDF/UA flag)
        """
        issues = []
        
        # 1. Verificar existencia de metadatos XMP
        if not metadata.get("has_xmp", False):
            issues.append(self._create_issue(
                "06-001", 
                "error",
                "El documento no contiene un flujo de metadatos XMP",
                "Añadir metadatos XMP al documento",
                True
            ))
            # Si no hay XMP, muchas otras validaciones no son posibles
            # pero seguimos para detectar los demás problemas
        
        # 2. Verificar flag PDF/UA en metadatos XMP
        if not metadata.get("pdf_ua_flag", False):
            issues.append(self._create_issue(
                "06-002", 
                "error",
                "Los metadatos XMP no incluyen el identificador PDF/UA",
                "Añadir identificador PDF/UA (pdfuaid:part=1) a los metadatos XMP",
                True
            ))
        elif metadata.get("pdf_ua_version") != "1":
            issues.append(self._create_issue(
                "06-002", 
                "error",
                f"Versión incorrecta de PDF/UA: {metadata.get('pdf_ua_version', 'desconocida')}",
                "Establecer identificador PDF/UA como 'pdfuaid:part=1'",
                True
            ))
        
        # 3. Verificar título del documento (06-003, 06-004)
        self._validate_title(metadata, issues)
        
        # 4. Verificar DisplayDocTitle en diccionario ViewerPreferences (07-001, 07-002)
        self._validate_display_doc_title(metadata, issues)
        
        # 5. Verificar idioma del documento (11-006, 11-007)
        self._validate_language(metadata, issues)
        
        # 6. Verificar otros metadatos importantes (PDF/A, versión, productor)
        self._validate_additional_metadata(metadata, issues)
        
        logger.info(f"Validación de metadatos completada: {len(issues)} problemas encontrados")
        return issues
    
    def _validate_title(self, metadata: Dict, issues: List[Dict]):
        """
        Valida el título del documento según checkpoints 06-003 y 06-004.
        
        Args:
            metadata: Diccionario con metadatos
            issues: Lista de problemas a la que se añadirán los detectados
        """
        # Verificar existencia de dc:title en metadatos XMP
        if not metadata.get("dc_title", False):
            issues.append(self._create_issue(
                "06-003", 
                "error",
                "Los metadatos XMP no contienen dc:title",
                "Añadir título al documento en los metadatos XMP",
                True
            ))
        
        # Verificar si el título está vacío o no es descriptivo
        title = metadata.get("title", "")
        if not title:
            issues.append(self._create_issue(
                "06-004", 
                "warning",
                "El título del documento está vacío",
                "Establecer un título descriptivo para el documento",
                True
            ))
        elif title.lower() in ["untitled", "sin título", "document", "documento", "pdf document", "new document"]:
            issues.append(self._create_issue(
                "06-004", 
                "warning",
                f"El título del documento no es descriptivo: '{title}'",
                "Establecer un título que identifique claramente el contenido del documento",
                True
            ))
        elif len(title) < 3:
            issues.append(self._create_issue(
                "06-004", 
                "warning",
                f"El título del documento es demasiado corto: '{title}'",
                "Establecer un título más descriptivo",
                True
            ))
            
        # Verificar consistencia entre metadatos
        doc_info_title = metadata.get("info_title", "")
        xmp_title = metadata.get("xmp_title", "")
        
        if doc_info_title and xmp_title and doc_info_title != xmp_title:
            issues.append(self._create_issue(
                "06-003", 
                "warning",
                "El título en Info Dictionary y XMP metadata son diferentes",
                "Asegurar que el título sea consistente en todas las ubicaciones de metadatos",
                True,
                details={
                    "info_title": doc_info_title,
                    "xmp_title": xmp_title
                }
            ))
    
    def _validate_display_doc_title(self, metadata: Dict, issues: List[Dict]):
        """
        Valida DisplayDocTitle según checkpoints 07-001 y 07-002.
        
        Args:
            metadata: Diccionario con metadatos
            issues: Lista de problemas a la que se añadirán los detectados
        """
        # 07-001: Verificar si existe ViewerPreferences
        if not metadata.get("has_viewer_preferences", False):
            issues.append(self._create_issue(
                "07-001", 
                "error",
                "El diccionario ViewerPreferences no está presente",
                "Añadir diccionario ViewerPreferences con entrada DisplayDocTitle",
                True
            ))
            return  # No podemos verificar DisplayDocTitle si no existe ViewerPreferences
        
        # 07-002: Verificar DisplayDocTitle
        if not metadata.get("display_doc_title", False):
            # Diferenciar entre ausencia o valor falso
            if "display_doc_title" in metadata:
                issues.append(self._create_issue(
                    "07-002", 
                    "error",
                    "El diccionario ViewerPreferences contiene DisplayDocTitle con valor false",
                    "Establecer DisplayDocTitle=true en el diccionario ViewerPreferences",
                    True
                ))
            else:
                issues.append(self._create_issue(
                    "07-001", 
                    "error",
                    "El diccionario ViewerPreferences no contiene una entrada DisplayDocTitle",
                    "Añadir entrada DisplayDocTitle=true al diccionario ViewerPreferences",
                    True
                ))
    
    def _validate_language(self, metadata: Dict, issues: List[Dict]):
        """
        Valida el idioma del documento según checkpoints 11-006 y 11-007.
        
        Args:
            metadata: Diccionario con metadatos
            issues: Lista de problemas a la que se añadirán los detectados
        """
        # 11-006: Verificar si el documento tiene Lang definido
        if not metadata.get("has_lang", False):
            issues.append(self._create_issue(
                "11-006", 
                "error",
                "No se puede determinar el idioma natural para los metadatos del documento",
                "Establecer el atributo Lang en el diccionario Catalog",
                True
            ))
            return  # No podemos verificar la validez del idioma si no está presente
        
        # 11-007: Verificar si el código de idioma es válido
        language = metadata.get("language", "")
        if not self._is_valid_language_code(language):
            issues.append(self._create_issue(
                "11-007", 
                "warning",
                f"El código de idioma del documento '{language}' no es apropiado o no está en formato RFC 3066",
                "Establecer un código de idioma válido (p. ej., 'es-ES', 'en-US')",
                True
            ))
    
    def _validate_additional_metadata(self, metadata: Dict, issues: List[Dict]):
        """
        Valida metadatos adicionales que son importantes para accesibilidad.
        
        Args:
            metadata: Diccionario con metadatos
            issues: Lista de problemas a la que se añadirán los detectados
        """
        # Verificar metadatos PDF/A (complementario a PDF/UA)
        if metadata.get("has_pdfa", False):
            pdfa_version = metadata.get("pdfa_version", "")
            pdfa_conformance = metadata.get("pdfa_conformance", "")
            
            # Verificar compatibilidad de conformance
            if pdfa_conformance and pdfa_conformance not in ["A", "1A", "2A", "3A", "4", "4A"]:
                issues.append(self._create_issue(
                    "06-005", 
                    "info",
                    f"El nivel de conformidad PDF/A '{pdfa_conformance}' podría no ser totalmente compatible con PDF/UA",
                    "Considerar usar nivel de conformidad 'A' para PDF/A junto con PDF/UA",
                    False
                ))
        
        # Verificar Creator y Producer (informativo)
        creator = metadata.get("creator", "")
        producer = metadata.get("producer", "")
        
        if not creator and not producer:
            issues.append(self._create_issue(
                "06-005", 
                "info",
                "No se especifica el software de creación (Creator) ni el de producción (Producer)",
                "Añadir información sobre la herramienta de creación/producción para facilitar el soporte",
                True
            ))
    
    def _is_valid_language_code(self, language_code: str) -> bool:
        """
        Verifica si un código de idioma es válido según RFC 3066.
        
        Args:
            language_code: Código de idioma a verificar
            
        Returns:
            bool: True si el código es válido
        """
        if not language_code:
            return False
            
        # RFC 3066 permite códigos de 2-3 letras (ISO 639) o combinaciones con país
        language_code = language_code.lower()
        
        # Verificar formato básico (xx o xx-XX)
        if not re.match(r'^[a-z]{2,3}(-[a-z]{2,3})?$', language_code, re.IGNORECASE):
            return False
            
        # Verificar si el código base está en nuestra lista de idiomas válidos
        base_code = language_code.split('-')[0] if '-' in language_code else language_code
        if base_code not in self.language_codes and language_code not in self.language_codes:
            return False
            
        return True
    
    def _create_issue(self, checkpoint: str, severity: str, description: str,
                    fix_description: str, fixable: bool, page: Any = "all",
                    details: Dict = None) -> Dict:
        """
        Crea un diccionario de problema estandarizado.
        
        Args:
            checkpoint: ID del checkpoint (ej: '06-001')
            severity: Nivel de severidad (error, warning, info)
            description: Descripción del problema
            fix_description: Descripción de cómo solucionar el problema
            fixable: Si el problema puede corregirse automáticamente
            page: Número de página o "all" para todo el documento
            details: Detalles adicionales específicos (opcional)
            
        Returns:
            Dict: Problema formateado
        """
        issue = {
            "checkpoint": checkpoint,
            "severity": severity,
            "description": description,
            "fix_description": fix_description,
            "fixable": fixable,
            "page": page,
            "category": "Metadata"  # Categoría para agrupación en el panel de problemas
        }
        
        # Añadir detalles si se proporcionan
        if details:
            issue["details"] = details
            
        return issue
    
    def get_required_fixes(self, metadata: Dict) -> Dict:
        """
        Obtiene las correcciones necesarias para los metadatos.
        
        Args:
            metadata: Diccionario con metadatos extraídos del PDF
            
        Returns:
            Dict: Diccionario con las correcciones necesarias
        """
        fixes = {}
        filename = metadata.get("filename", "")
        
        # 1. Correcciones de título
        if not metadata.get("title") or not metadata.get("dc_title", False):
            # Intentar generar un título sugerido a partir del nombre de archivo
            suggested_title = ""
            if filename:
                # Eliminar extensión y convertir a título legible
                base_name = filename.rsplit('.', 1)[0] if '.' in filename else filename
                # Reemplazar guiones y subrayados por espacios
                readable_name = base_name.replace('-', ' ').replace('_', ' ')
                # Capitalizar palabras para un título adecuado
                suggested_title = ' '.join(word.capitalize() for word in readable_name.split())
            
            fixes["title"] = {
                "current": metadata.get("title", ""),
                "suggested": suggested_title or "Documento sin título",
                "required": True
            }
        
        # 2. Correcciones de idioma
        if not metadata.get("has_lang", False):
            # En una implementación real, podríamos detectar el idioma del contenido
            # Por ahora, sugerimos español como predeterminado
            fixes["language"] = {
                "current": metadata.get("language", ""),
                "suggested": "es-ES",  # Podría mejorarse con detección real
                "required": True
            }
        elif not self._is_valid_language_code(metadata.get("language", "")):
            language = metadata.get("language", "")
            # Intentar mapear a un código válido si es posible
            mapped_language = self._map_to_valid_language(language)
            
            fixes["language"] = {
                "current": language,
                "suggested": mapped_language or "es-ES",
                "required": True
            }
        
        # 3. Correcciones de DisplayDocTitle
        if not metadata.get("display_doc_title", False):
            fixes["display_doc_title"] = {
                "current": False,
                "suggested": True,
                "required": True
            }
        
        # 4. Corrección de PDF/UA flag
        if not metadata.get("pdf_ua_flag", False):
            fixes["pdf_ua_flag"] = {
                "current": False,
                "suggested": True,
                "required": True
            }
        
        return fixes
    
    def _map_to_valid_language(self, language: str) -> str:
        """
        Intenta mapear un código de idioma no válido a uno válido.
        
        Args:
            language: Código de idioma a mapear
            
        Returns:
            str: Código de idioma válido o cadena vacía si no es posible mapear
        """
        # Mapeos comunes de códigos erróneos
        mappings = {
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
            "spanish": "es-ES",
            "english": "en-US",
            "french": "fr-FR",
            "german": "de-DE",
            "italian": "it-IT",
            "portuguese": "pt-PT",
            "russian": "ru-RU",
            "chinese": "zh-CN",
            "japanese": "ja-JP",
            "arabic": "ar-SA"
        }
        
        # Convertir a minúsculas para la comparación
        lower_lang = language.lower()
        
        # Verificar mapeos directos
        if lower_lang in mappings:
            return mappings[lower_lang]
        
        # Verificar similitudes para idiomas comunes
        for valid_code in self.language_codes:
            if valid_code.startswith(lower_lang) or lower_lang.startswith(valid_code):
                return valid_code
        
        # No se pudo mapear
        return ""