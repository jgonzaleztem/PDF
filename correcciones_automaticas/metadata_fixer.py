#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Corrección automática de metadatos según PDF/UA.
Añade título, idioma, flag PDF/UA y configuración ViewerPreferences.
"""

from typing import Dict, Optional
from loguru import logger

class MetadataFixer:
    """
    Clase para corregir metadatos según PDF/UA.
    Añade título, idioma, flag PDF/UA y configuración DisplayDocTitle.
    """
    
    def __init__(self, pdf_writer=None):
        """
        Inicializa el corrector de metadatos.
        
        Args:
            pdf_writer: Instancia opcional de PDFWriter
        """
        self.pdf_writer = pdf_writer
        logger.info("MetadataFixer inicializado")
    
    def set_pdf_writer(self, pdf_writer):
        """Establece el escritor de PDF a utilizar"""
        self.pdf_writer = pdf_writer
    
    def fix_all_metadata(self, metadata: Dict, filename: str = None) -> bool:
        """
        Corrige todos los problemas de metadatos.
        
        Args:
            metadata: Diccionario con metadatos actuales
            filename: Nombre del archivo para usar como título si es necesario
            
        Returns:
            bool: True si se realizaron correcciones
            
        Referencias:
            - Matterhorn: 06-001 a 06-004, 07-001 a 07-002, 11-006
            - Tagged PDF: 3.3 (Document level attributes), 5.5.1 (Lang), Anexo A (PDF/UA flag)
        """
        try:
            if self.pdf_writer is None:
                logger.error("No hay PDFWriter configurado para aplicar correcciones")
                return False
            
            updated_metadata = {}
            changes_made = False
            
            # Verificar y corregir título
            if not metadata.get("title") or not metadata.get("dc_title", False):
                suggested_title = self._suggest_title(metadata, filename)
                updated_metadata["title"] = suggested_title
                logger.info(f"Título sugerido: {suggested_title}")
                changes_made = True
            
            # Verificar y corregir idioma
            if not metadata.get("has_lang", False):
                suggested_language = self._suggest_language(metadata)
                updated_metadata["language"] = suggested_language
                logger.info(f"Idioma sugerido: {suggested_language}")
                changes_made = True
            
            # Verificar y corregir DisplayDocTitle
            if not metadata.get("display_doc_title", False):
                updated_metadata["display_doc_title"] = True
                logger.info("DisplayDocTitle será establecido a True")
                changes_made = True
            
            # Aplicar cambios si se han realizado
            if changes_made:
                logger.info("Aplicando correcciones de metadatos")
                self.pdf_writer.update_metadata(updated_metadata)
                
                # Añadir flag PDF/UA si no existe
                if not metadata.get("pdf_ua_flag", False):
                    logger.info("Añadiendo flag PDF/UA")
                    self.pdf_writer.add_pdf_ua_flag()
            
            return changes_made
            
        except Exception as e:
            logger.exception(f"Error al corregir metadatos: {e}")
            return False
    
    def fix_title(self, metadata: Dict, new_title: Optional[str] = None) -> bool:
        """
        Corrige el título del documento.
        
        Args:
            metadata: Diccionario con metadatos actuales
            new_title: Nuevo título a establecer (opcional)
            
        Returns:
            bool: True si se realizó la corrección
            
        Referencias:
            - Matterhorn: 06-003, 06-004
            - Tagged PDF: 3.3 (Document level attributes)
        """
        try:
            if self.pdf_writer is None:
                logger.error("No hay PDFWriter configurado para aplicar correcciones")
                return False
            
            title = new_title if new_title else self._suggest_title(metadata)
            
            logger.info(f"Estableciendo título: {title}")
            return self.pdf_writer.update_metadata({"title": title})
            
        except Exception as e:
            logger.exception(f"Error al corregir título: {e}")
            return False
    
    def fix_language(self, metadata: Dict, language: Optional[str] = None) -> bool:
        """
        Corrige el idioma del documento.
        
        Args:
            metadata: Diccionario con metadatos actuales
            language: Código de idioma a establecer (opcional)
            
        Returns:
            bool: True si se realizó la corrección
            
        Referencias:
            - Matterhorn: 11-006
            - Tagged PDF: 5.5.1 (Lang)
        """
        try:
            if self.pdf_writer is None:
                logger.error("No hay PDFWriter configurado para aplicar correcciones")
                return False
            
            lang = language if language else self._suggest_language(metadata)
            
            logger.info(f"Estableciendo idioma: {lang}")
            return self.pdf_writer.update_metadata({"language": lang})
            
        except Exception as e:
            logger.exception(f"Error al corregir idioma: {e}")
            return False
    
    def fix_display_doc_title(self, metadata: Dict) -> bool:
        """
        Establece DisplayDocTitle a True.
        
        Args:
            metadata: Diccionario con metadatos actuales
            
        Returns:
            bool: True si se realizó la corrección
            
        Referencias:
            - Matterhorn: 07-001, 07-002
            - Tagged PDF: 3.3 (Document level attributes)
        """
        try:
            if self.pdf_writer is None:
                logger.error("No hay PDFWriter configurado para aplicar correcciones")
                return False
            
            if metadata.get("display_doc_title", False):
                logger.info("DisplayDocTitle ya está configurado correctamente")
                return False
            
            logger.info("Estableciendo DisplayDocTitle=true")
            return self.pdf_writer.update_metadata({"display_doc_title": True})
            
        except Exception as e:
            logger.exception(f"Error al corregir DisplayDocTitle: {e}")
            return False
    
    def add_pdf_ua_flag(self, metadata: Dict) -> bool:
        """
        Añade el flag PDF/UA.
        
        Args:
            metadata: Diccionario con metadatos actuales
            
        Returns:
            bool: True si se realizó la corrección
            
        Referencias:
            - Matterhorn: 06-002
            - Tagged PDF: Anexo A (PDF/UA flag)
        """
        try:
            if self.pdf_writer is None:
                logger.error("No hay PDFWriter configurado para aplicar correcciones")
                return False
            
            if metadata.get("pdf_ua_flag", False):
                logger.info("El flag PDF/UA ya existe")
                return False
            
            logger.info("Añadiendo flag PDF/UA")
            return self.pdf_writer.add_pdf_ua_flag()
            
        except Exception as e:
            logger.exception(f"Error al añadir flag PDF/UA: {e}")
            return False
    
    def _suggest_title(self, metadata: Dict, filename: Optional[str] = None) -> str:
        """
        Sugiere un título para el documento.
        
        Args:
            metadata: Diccionario con metadatos actuales
            filename: Nombre del archivo para usar como título si es necesario
            
        Returns:
            str: Título sugerido
        """
        # Si hay un título existente, utilizarlo
        if metadata.get("title"):
            return metadata["title"]
        
        # Si se proporciona un nombre de archivo, utilizarlo sin extensión
        if filename:
            return self._clean_filename_for_title(filename)
        
        # Usar nombre de archivo de los metadatos si está disponible
        if metadata.get("filename"):
            return self._clean_filename_for_title(metadata["filename"])
        
        # Título genérico
        return "Documento PDF"
    
    def _clean_filename_for_title(self, filename: str) -> str:
        """
        Limpia un nombre de archivo para usar como título.
        
        Args:
            filename: Nombre de archivo
            
        Returns:
            str: Título limpio
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
    
    def _suggest_language(self, metadata: Dict) -> str:
        """
        Sugiere un idioma para el documento.
        
        Args:
            metadata: Diccionario con metadatos actuales
            
        Returns:
            str: Código de idioma sugerido
        """
        # Si hay un idioma existente, utilizarlo
        if metadata.get("language"):
            return metadata["language"]
        
        # Por defecto, español
        return "es-ES"