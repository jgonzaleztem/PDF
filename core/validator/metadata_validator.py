# core/validator/metadata_validator.py

from typing import Dict, List, Optional, Any
import re
from loguru import logger

class MetadataValidator:
    """
    Validador de metadatos según los requisitos de PDF/UA y Matterhorn Protocol.
    
    Checkpoints relacionados:
    - 06-001: Document does not contain an XMP metadata stream
    - 06-002: The XMP metadata stream does not include the PDF/UA identifier
    - 06-003: XMP metadata stream does not contain dc:title
    - 06-004: dc:title does not clearly identify the document
    - 07-001: ViewerPreferences dictionary does not contain a DisplayDocTitle entry
    - 07-002: ViewerPreferences dictionary contains a DisplayDocTitle entry with value of false
    - 11-006: Natural language for document metadata cannot be determined
    - 11-007: Natural language is not appropriate
    """
    
    def __init__(self):
        """Inicializa el validador de metadatos."""
        self.pdf_loader = None
        
        # Códigos de idioma válidos (ISO 639-1 y extensiones comunes)
        self.valid_language_codes = {
            'es', 'es-ES', 'es-MX', 'es-AR', 'es-CO', 'es-CL', 'es-PE', 'es-VE',
            'en', 'en-US', 'en-GB', 'en-CA', 'en-AU',
            'fr', 'fr-FR', 'fr-CA',
            'de', 'de-DE', 'de-AT', 'de-CH',
            'it', 'it-IT',
            'pt', 'pt-PT', 'pt-BR',
            'ru', 'ru-RU',
            'zh', 'zh-CN', 'zh-TW',
            'ja', 'ja-JP',
            'ko', 'ko-KR',
            'ar', 'ar-SA',
            'ca', 'ca-ES',
            'eu', 'eu-ES',
            'gl', 'gl-ES'
        }
        
        logger.info("MetadataValidator inicializado")
    
    def set_pdf_loader(self, pdf_loader):
        """
        Establece la referencia al cargador de PDF.
        
        Args:
            pdf_loader: Instancia de PDFLoader
        """
        self.pdf_loader = pdf_loader
        logger.debug("PDFLoader establecido en MetadataValidator")
    
    def validate(self, metadata: Dict) -> List[Dict]:
        """
        Valida los metadatos del documento según PDF/UA.
        
        Args:
            metadata: Diccionario con metadatos del documento
            
        Returns:
            List[Dict]: Lista de problemas encontrados
        """
        issues = []
        
        try:
            # Checkpoint 06-001: Verificar presencia de metadatos XMP
            if not metadata.get("has_xmp", False):
                issues.append({
                    "checkpoint": "06-001",
                    "severity": "error",
                    "description": "El documento no contiene un flujo de metadatos XMP",
                    "fix_description": "Añadir metadatos XMP al documento",
                    "fixable": True,
                    "page": "all"
                })
            else:
                # Checkpoint 06-002: Verificar identificador PDF/UA en XMP
                if not metadata.get("pdf_ua_flag", False):
                    issues.append({
                        "checkpoint": "06-002",
                        "severity": "error",
                        "description": "Los metadatos XMP no incluyen el identificador PDF/UA",
                        "fix_description": "Añadir identificador PDF/UA (pdfuaid:part=1) a los metadatos XMP",
                        "fixable": True,
                        "page": "all"
                    })
                
                # Checkpoint 06-003: Verificar presencia de dc:title
                xmp_title = metadata.get("xmp_title", "")
                info_title = metadata.get("info_title", "")
                
                if not xmp_title and not info_title:
                    issues.append({
                        "checkpoint": "06-003",
                        "severity": "error",
                        "description": "Los metadatos XMP no contienen dc:title",
                        "fix_description": "Añadir título al documento en los metadatos XMP",
                        "fixable": True,
                        "page": "all"
                    })
                else:
                    # Checkpoint 06-004: Verificar calidad del título
                    title_to_check = xmp_title or info_title
                    title_issues = self._validate_title_quality(title_to_check, metadata.get("filename", ""))
                    issues.extend(title_issues)
            
            # Checkpoint 07-001 y 07-002: Verificar ViewerPreferences
            viewer_prefs_issues = self._validate_viewer_preferences(metadata)
            issues.extend(viewer_prefs_issues)
            
            # Checkpoint 11-006 y 11-007: Verificar idioma del documento
            language_issues = self._validate_document_language(metadata)
            issues.extend(language_issues)
            
            # Validaciones adicionales de calidad
            quality_issues = self._validate_metadata_quality(metadata)
            issues.extend(quality_issues)
            
        except Exception as e:
            logger.error(f"Error durante validación de metadatos: {e}")
            issues.append({
                "checkpoint": "general",
                "severity": "error",
                "description": f"Error durante validación de metadatos: {str(e)}",
                "fix_description": "Revisar la estructura de metadatos del documento",
                "fixable": False,
                "page": "all"
            })
        
        logger.info(f"Validación de metadatos completada: {len(issues)} problemas encontrados")
        return issues
    
    def _validate_title_quality(self, title: str, filename: str) -> List[Dict]:
        """
        Valida la calidad del título del documento.
        
        Args:
            title: Título del documento
            filename: Nombre del archivo
            
        Returns:
            List[Dict]: Lista de problemas encontrados
        """
        issues = []
        
        if not title or not title.strip():
            issues.append({
                "checkpoint": "06-004",
                "severity": "warning",
                "description": "El título del documento está vacío",
                "fix_description": "Establecer un título descriptivo para el documento",
                "fixable": True,
                "page": "all"
            })
            return issues
        
        title = title.strip()
        
        # Verificar si el título es solo el nombre del archivo
        if filename and title.lower() == filename.lower():
            issues.append({
                "checkpoint": "06-004",
                "severity": "warning",
                "description": "El título es idéntico al nombre del archivo",
                "fix_description": "Establecer un título más descriptivo que el nombre del archivo",
                "fixable": True,
                "page": "all"
            })
        
        # Verificar si el título es demasiado genérico
        generic_titles = [
            "documento", "document", "untitled", "sin título", "nuevo documento",
            "pdf", "archivo", "file", "temp", "temporal"
        ]
        
        if title.lower() in generic_titles:
            issues.append({
                "checkpoint": "06-004",
                "severity": "warning",
                "description": f"El título '{title}' es demasiado genérico",
                "fix_description": "Establecer un título específico que identifique claramente el documento",
                "fixable": True,
                "page": "all"
            })
        
        # Verificar longitud del título
        if len(title) < 3:
            issues.append({
                "checkpoint": "06-004",
                "severity": "warning",
                "description": "El título es demasiado corto",
                "fix_description": "Establecer un título más descriptivo",
                "fixable": True,
                "page": "all"
            })
        elif len(title) > 200:
            issues.append({
                "checkpoint": "06-004",
                "severity": "warning",
                "description": "El título es excesivamente largo",
                "fix_description": "Acortar el título manteniendo la información esencial",
                "fixable": True,
                "page": "all"
            })
        
        # Verificar caracteres problemáticos
        if re.search(r'[<>:"\\|?*\x00-\x1f]', title):
            issues.append({
                "checkpoint": "06-004",
                "severity": "warning",
                "description": "El título contiene caracteres problemáticos",
                "fix_description": "Eliminar caracteres especiales del título",
                "fixable": True,
                "page": "all"
            })
        
        return issues
    
    def _validate_viewer_preferences(self, metadata: Dict) -> List[Dict]:
        """
        Valida las preferencias del visor.
        
        Args:
            metadata: Metadatos del documento
            
        Returns:
            List[Dict]: Lista de problemas encontrados
        """
        issues = []
        
        # Checkpoint 07-001: Verificar presencia de ViewerPreferences
        if not metadata.get("has_viewer_preferences", False):
            issues.append({
                "checkpoint": "07-001",
                "severity": "error",
                "description": "El diccionario ViewerPreferences no existe",
                "fix_description": "Añadir diccionario ViewerPreferences al documento",
                "fixable": True,
                "page": "all"
            })
        else:
            # Checkpoint 07-002: Verificar DisplayDocTitle
            display_doc_title = metadata.get("display_doc_title")
            
            if display_doc_title is None:
                issues.append({
                    "checkpoint": "07-001",
                    "severity": "error",
                    "description": "ViewerPreferences no contiene entrada DisplayDocTitle",
                    "fix_description": "Añadir entrada DisplayDocTitle=true al diccionario ViewerPreferences",
                    "fixable": True,
                    "page": "all"
                })
            elif not display_doc_title:
                issues.append({
                    "checkpoint": "07-002",
                    "severity": "error",
                    "description": "DisplayDocTitle está establecido como false",
                    "fix_description": "Establecer DisplayDocTitle=true en ViewerPreferences",
                    "fixable": True,
                    "page": "all"
                })
        
        return issues
    
    def _validate_document_language(self, metadata: Dict) -> List[Dict]:
        """
        Valida el idioma del documento.
        
        Args:
            metadata: Metadatos del documento
            
        Returns:
            List[Dict]: Lista de problemas encontrados
        """
        issues = []
        
        # Checkpoint 11-006: Verificar presencia de idioma
        if not metadata.get("has_lang", False):
            issues.append({
                "checkpoint": "11-006",
                "severity": "error",
                "description": "No se puede determinar el idioma natural para los metadatos del documento",
                "fix_description": "Establecer el atributo Lang en el diccionario Catalog",
                "fixable": True,
                "page": "all"
            })
        else:
            # Checkpoint 11-007: Verificar validez del código de idioma
            language = metadata.get("language", "")
            if language:
                language_issues = self._validate_language_code(language)
                issues.extend(language_issues)
            else:
                issues.append({
                    "checkpoint": "11-006",
                    "severity": "error",
                    "description": "El atributo Lang está presente pero vacío",
                    "fix_description": "Establecer un código de idioma válido (ej: es-ES, en-US)",
                    "fixable": True,
                    "page": "all"
                })
        
        return issues
    
    def _validate_language_code(self, language_code: str) -> List[Dict]:
        """
        Valida un código de idioma.
        
        Args:
            language_code: Código de idioma a validar
            
        Returns:
            List[Dict]: Lista de problemas encontrados
        """
        issues = []
        
        if not language_code or not language_code.strip():
            issues.append({
                "checkpoint": "11-007",
                "severity": "error",
                "description": "Código de idioma vacío",
                "fix_description": "Establecer un código de idioma válido",
                "fixable": True,
                "page": "all"
            })
            return issues
        
        language_code = language_code.strip()
        
        # Verificar formato básico
        if not re.match(r'^[a-zA-Z]{2}(-[a-zA-Z]{2})?$', language_code):
            issues.append({
                "checkpoint": "11-007",
                "severity": "error",
                "description": f"Formato de código de idioma inválido: '{language_code}'",
                "fix_description": "Usar formato ISO 639-1 (ej: es, en) o ISO 639-1 + ISO 3166-1 (ej: es-ES, en-US)",
                "fixable": True,
                "page": "all"
            })
            return issues
        
        # Verificar si es un código conocido
        if language_code.lower() not in [code.lower() for code in self.valid_language_codes]:
            issues.append({
                "checkpoint": "11-007",
                "severity": "warning",
                "description": f"Código de idioma no reconocido: '{language_code}'",
                "fix_description": "Verificar que el código de idioma sea correcto según ISO 639-1",
                "fixable": True,
                "page": "all"
            })
        
        return issues
    
    def _validate_metadata_quality(self, metadata: Dict) -> List[Dict]:
        """
        Realiza validaciones adicionales de calidad de metadatos.
        
        Args:
            metadata: Metadatos del documento
            
        Returns:
            List[Dict]: Lista de problemas encontrados
        """
        issues = []
        
        # Verificar metadatos básicos recomendados
        recommended_fields = {
            "author": "Autor del documento",
            "subject": "Tema o descripción del documento", 
            "keywords": "Palabras clave del documento"
        }
        
        for field, description in recommended_fields.items():
            value = metadata.get(field, "")
            if not value or not value.strip():
                issues.append({
                    "checkpoint": "metadata-quality",
                    "severity": "info",
                    "description": f"Campo recomendado ausente: {description}",
                    "fix_description": f"Añadir {description.lower()} en los metadatos",
                    "fixable": True,
                    "page": "all"
                })
        
        # Verificar coherencia entre metadatos Info y XMP
        info_title = metadata.get("info_title", "")
        xmp_title = metadata.get("xmp_title", "")
        
        if info_title and xmp_title and info_title != xmp_title:
            issues.append({
                "checkpoint": "metadata-consistency",
                "severity": "warning",
                "description": "Inconsistencia entre título en metadatos Info y XMP",
                "fix_description": "Sincronizar los títulos en metadatos Info y XMP",
                "fixable": True,
                "page": "all"
            })
        
        # Verificar campos con contenido sospechoso
        suspicious_patterns = [
            r'^\s*$',  # Solo espacios
            r'^untitled',  # Sin título
            r'^document\d*$',  # Document + número
            r'^test',  # Documento de prueba
        ]
        
        for field in ["title", "author", "subject"]:
            value = metadata.get(field, "")
            if value:
                for pattern in suspicious_patterns:
                    if re.match(pattern, value.lower()):
                        issues.append({
                            "checkpoint": "metadata-quality",
                            "severity": "info",
                            "description": f"Valor genérico en campo {field}: '{value}'",
                            "fix_description": f"Establecer un valor más específico para {field}",
                            "fixable": True,
                            "page": "all"
                        })
                        break
        
        return issues
    
    def get_metadata_recommendations(self, metadata: Dict) -> List[str]:
        """
        Obtiene recomendaciones para mejorar los metadatos.
        
        Args:
            metadata: Metadatos actuales
            
        Returns:
            List[str]: Lista de recomendaciones
        """
        recommendations = []
        
        # Verificar completitud de metadatos
        if not metadata.get("title"):
            recommendations.append("Añadir un título descriptivo al documento")
        
        if not metadata.get("author"):
            recommendations.append("Especificar el autor del documento")
        
        if not metadata.get("subject"):
            recommendations.append("Añadir una descripción del contenido del documento")
        
        if not metadata.get("keywords"):
            recommendations.append("Incluir palabras clave para facilitar la búsqueda")
        
        # Verificar configuración PDF/UA
        if not metadata.get("pdf_ua_flag"):
            recommendations.append("Añadir identificador PDF/UA a los metadatos XMP")
        
        if not metadata.get("display_doc_title"):
            recommendations.append("Configurar DisplayDocTitle=true en ViewerPreferences")
        
        if not metadata.get("has_lang"):
            recommendations.append("Establecer el idioma del documento en el Catalog")
        
        return recommendations
    
    def generate_metadata_report(self, metadata: Dict) -> Dict:
        """
        Genera un informe completo de los metadatos.
        
        Args:
            metadata: Metadatos del documento
            
        Returns:
            Dict: Informe de metadatos
        """
        issues = self.validate(metadata)
        recommendations = self.get_metadata_recommendations(metadata)
        
        # Contar problemas por severidad
        error_count = len([i for i in issues if i.get("severity") == "error"])
        warning_count = len([i for i in issues if i.get("severity") == "warning"])
        info_count = len([i for i in issues if i.get("severity") == "info"])
        
        # Determinar estado de conformidad
        is_compliant = error_count == 0
        
        return {
            "is_compliant": is_compliant,
            "total_issues": len(issues),
            "error_count": error_count,
            "warning_count": warning_count,
            "info_count": info_count,
            "issues": issues,
            "recommendations": recommendations,
            "metadata_completeness": self._calculate_completeness(metadata),
            "pdf_ua_ready": self._is_pdf_ua_ready(metadata)
        }
    
    def _calculate_completeness(self, metadata: Dict) -> float:
        """Calcula el porcentaje de completitud de metadatos."""
        required_fields = ["title", "author", "subject", "language", "pdf_ua_flag", "display_doc_title"]
        present_fields = 0
        
        for field in required_fields:
            if metadata.get(field):
                present_fields += 1
        
        return (present_fields / len(required_fields)) * 100
    
    def _is_pdf_ua_ready(self, metadata: Dict) -> bool:
        """Verifica si los metadatos están listos para PDF/UA."""
        required_for_pdfua = [
            metadata.get("has_xmp", False),
            metadata.get("pdf_ua_flag", False),
            bool(metadata.get("title", "")),
            metadata.get("display_doc_title", False),
            metadata.get("has_lang", False)
        ]
        
        return all(required_for_pdfua)