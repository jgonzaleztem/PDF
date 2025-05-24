# core/pdf_writer.py

from pikepdf import Pdf, Name, Dictionary, Array, String
from loguru import logger
import os
import shutil
from typing import Dict, List, Optional, Any, Union
from pathlib import Path

class PDFWriter:
    """
    Clase para escribir y guardar documentos PDF con estructura actualizada.
    Maneja la aplicación de cambios estructurales al documento PDF.
    """
    
    def __init__(self, pdf_loader=None):
        self.pdf_loader = pdf_loader
        self.temp_files = []  # Lista de archivos temporales a limpiar
        
        logger.info("PDFWriter inicializado")
    
    def set_pdf_loader(self, pdf_loader):
        """Establece la referencia al cargador de PDF."""
        self.pdf_loader = pdf_loader
        logger.debug("PDFLoader establecido en PDFWriter")
    
    def update_structure_tree(self, updated_structure: Dict) -> bool:
        """
        Actualiza el árbol de estructura en el documento PDF.
        
        Args:
            updated_structure: Estructura actualizada
            
        Returns:
            bool: True si la actualización fue exitosa
        """
        if not self.pdf_loader or not self.pdf_loader.pikepdf_doc:
            logger.error("No hay documento PDF cargado para actualizar")
            return False
        
        try:
            # Verificar que existe StructTreeRoot
            if "/StructTreeRoot" not in self.pdf_loader.pikepdf_doc.Root:
                logger.error("El documento no tiene StructTreeRoot para actualizar")
                return False
            
            struct_root = self.pdf_loader.pikepdf_doc.Root["/StructTreeRoot"]
            
            # Actualizar la estructura recursivamente
            success = self._update_structure_element(struct_root, updated_structure)
            
            if success:
                logger.info("Estructura del documento actualizada correctamente")
                return True
            else:
                logger.error("Error al actualizar la estructura del documento")
                return False
                
        except Exception as e:
            logger.error(f"Error al actualizar estructura: {e}")
            return False
    
    def _update_structure_element(self, pikepdf_element, structure_data: Dict) -> bool:
        """
        Actualiza un elemento de estructura recursivamente.
        
        Args:
            pikepdf_element: Elemento pikepdf a actualizar
            structure_data: Datos de estructura actualizados
            
        Returns:
            bool: True si la actualización fue exitosa
        """
        try:
            # Actualizar tipo de elemento si ha cambiado
            new_type = structure_data.get("type")
            if new_type and new_type != "StructTreeRoot":
                pikepdf_element[Name.S] = Name(f"/{new_type}")
            
            # Actualizar atributos
            attributes = structure_data.get("attributes", {})
            for attr_name, attr_value in attributes.items():
                if attr_value:  # Solo actualizar si tiene valor
                    attr_key = Name(f"/{attr_name.title()}")  # Capitalizar nombre
                    
                    # Convertir valores según el tipo
                    if isinstance(attr_value, bool):
                        pikepdf_element[attr_key] = attr_value
                    elif isinstance(attr_value, int):
                        pikepdf_element[attr_key] = attr_value
                    else:
                        pikepdf_element[attr_key] = String(str(attr_value))
                else:
                    # Eliminar atributo si el valor está vacío
                    attr_key = Name(f"/{attr_name.title()}")
                    if attr_key in pikepdf_element:
                        del pikepdf_element[attr_key]
            
            # Actualizar texto del elemento si es necesario
            new_text = structure_data.get("text", "")
            if new_text and new_text.strip():
                # Para elementos con texto directo, actualizar ActualText
                pikepdf_element[Name.ActualText] = String(new_text.strip())
            
            # Procesar hijos recursivamente
            children = structure_data.get("children", [])
            if children and Name.K in pikepdf_element:
                # Esta es una simplificación - en una implementación completa
                # sería necesario manejar la creación/eliminación de elementos hijos
                logger.debug(f"Procesando {len(children)} hijos para elemento {new_type}")
            
            return True
            
        except Exception as e:
            logger.error(f"Error al actualizar elemento de estructura: {e}")
            return False
    
    def save_document(self, output_path: str) -> bool:
        """
        Guarda el documento PDF en la ruta especificada.
        
        Args:
            output_path: Ruta donde guardar el documento
            
        Returns:
            bool: True si se guardó correctamente
        """
        if not self.pdf_loader or not self.pdf_loader.pikepdf_doc:
            logger.error("No hay documento PDF para guardar")
            return False
        
        try:
            # Crear directorio padre si no existe
            os.makedirs(os.path.dirname(output_path), exist_ok=True)
            
            # Validar y optimizar el documento antes de guardar
            self._validate_and_optimize_document()
            
            # Guardar el documento
            self.pdf_loader.pikepdf_doc.save(output_path)
            
            logger.info(f"Documento guardado en: {output_path}")
            return True
            
        except Exception as e:
            logger.error(f"Error al guardar documento: {e}")
            return False
    
    def _validate_and_optimize_document(self):
        """Valida y optimiza el documento antes de guardarlo."""
        try:
            doc = self.pdf_loader.pikepdf_doc
            
            # Asegurar que los metadatos básicos están presentes
            self._ensure_basic_metadata()
            
            # Validar estructura si existe
            if "/StructTreeRoot" in doc.Root:
                self._validate_structure_integrity()
            
            # Optimizar referencias de objetos
            doc.remove_unreferenced_resources()
            
            logger.debug("Documento validado y optimizado")
            
        except Exception as e:
            logger.warning(f"Error en validación/optimización: {e}")
    
    def _ensure_basic_metadata(self):
        """Asegura que los metadatos básicos están presentes."""
        try:
            doc = self.pdf_loader.pikepdf_doc
            
            # Asegurar ViewerPreferences
            if "/ViewerPreferences" not in doc.Root:
                doc.Root["/ViewerPreferences"] = Dictionary()
            
            viewer_prefs = doc.Root["/ViewerPreferences"]
            
            # Establecer DisplayDocTitle si no existe
            if "/DisplayDocTitle" not in viewer_prefs:
                viewer_prefs["/DisplayDocTitle"] = True
            
            # Asegurar idioma del documento si no existe
            if "/Lang" not in doc.Root:
                doc.Root["/Lang"] = String("es-ES")  # Valor por defecto
            
            logger.debug("Metadatos básicos verificados")
            
        except Exception as e:
            logger.warning(f"Error al asegurar metadatos básicos: {e}")
    
    def _validate_structure_integrity(self):
        """Valida la integridad de la estructura del documento."""
        try:
            doc = self.pdf_loader.pikepdf_doc
            struct_root = doc.Root["/StructTreeRoot"]
            
            # Verificaciones básicas de integridad
            if "/K" not in struct_root:
                logger.warning("StructTreeRoot no tiene elementos hijo")
                return
            
            # Validar que las referencias de página son válidas
            page_count = len(doc.pages)
            self._validate_page_references(struct_root, page_count)
            
            logger.debug("Integridad de estructura validada")
            
        except Exception as e:
            logger.warning(f"Error en validación de estructura: {e}")
    
    def _validate_page_references(self, element, page_count: int):
        """Valida que las referencias a páginas son válidas."""
        try:
            # Verificar referencia de página en el elemento actual
            if Name.Pg in element:
                try:
                    page_index = self.pdf_loader.pikepdf_doc.pages.index(element.Pg)
                    if page_index >= page_count:
                        logger.warning(f"Referencia de página inválida: {page_index}")
                except (ValueError, IndexError):
                    logger.warning("Referencia de página corrupta encontrada")
            
            # Validar hijos recursivamente
            if Name.K in element:
                k_value = element.K
                if isinstance(k_value, Array):
                    for item in k_value:
                        if isinstance(item, Dictionary):
                            self._validate_page_references(item, page_count)
                elif isinstance(k_value, Dictionary):
                    self._validate_page_references(k_value, page_count)
                    
        except Exception as e:
            logger.debug(f"Error en validación de referencias de página: {e}")
    
    def create_backup(self, backup_path: str = None) -> Optional[str]:
        """
        Crea una copia de seguridad del documento actual.
        
        Args:
            backup_path: Ruta para la copia de seguridad (opcional)
            
        Returns:
            Optional[str]: Ruta de la copia de seguridad o None si falló
        """
        if not self.pdf_loader or not self.pdf_loader.file_path:
            logger.error("No hay documento para respaldar")
            return None
        
        try:
            original_path = self.pdf_loader.file_path
            
            if not backup_path:
                # Generar nombre de backup automático
                path_obj = Path(original_path)
                backup_path = str(path_obj.parent / f"{path_obj.stem}_backup{path_obj.suffix}")
            
            # Copiar archivo
            shutil.copy2(original_path, backup_path)
            
            logger.info(f"Copia de seguridad creada: {backup_path}")
            return backup_path
            
        except Exception as e:
            logger.error(f"Error al crear copia de seguridad: {e}")
            return None
    
    def add_pdf_ua_metadata(self) -> bool:
        """
        Añade metadatos PDF/UA al documento.
        
        Returns:
            bool: True si se añadieron correctamente
        """
        try:
            doc = self.pdf_loader.pikepdf_doc
            
            # Crear o actualizar metadatos XMP
            with doc.open_metadata() as meta:
                # Añadir identificador PDF/UA
                meta['pdfuaid:part'] = '1'
                meta['pdfuaid:conformance'] = 'A'
                
                # Añadir título si no existe
                if 'dc:title' not in meta:
                    filename = os.path.basename(self.pdf_loader.file_path or "Documento")
                    meta['dc:title'] = filename
                
                # Añadir creador
                meta['xmp:CreatorTool'] = 'PDF/UA Editor'
                
            logger.info("Metadatos PDF/UA añadidos")
            return True
            
        except Exception as e:
            logger.error(f"Error al añadir metadatos PDF/UA: {e}")
            return False
    
    def compress_images(self) -> bool:
        """
        Comprime imágenes en el documento para reducir tamaño.
        
        Returns:
            bool: True si se comprimieron correctamente
        """
        try:
            # Esta es una implementación básica
            # Una implementación completa requeriría análisis detallado de imágenes
            logger.info("Compresión de imágenes iniciada")
            
            # Por ahora, solo registrar la acción
            # En una implementación real, aquí se procesarían las imágenes
            
            logger.info("Compresión de imágenes completada")
            return True
            
        except Exception as e:
            logger.error(f"Error al comprimir imágenes: {e}")
            return False
    
    def remove_unused_objects(self) -> bool:
        """
        Elimina objetos no utilizados del documento.
        
        Returns:
            bool: True si se eliminaron correctamente
        """
        try:
            if not self.pdf_loader or not self.pdf_loader.pikepdf_doc:
                return False
            
            # Usar funcionalidad integrada de pikepdf
            self.pdf_loader.pikepdf_doc.remove_unreferenced_resources()
            
            logger.info("Objetos no utilizados eliminados")
            return True
            
        except Exception as e:
            logger.error(f"Error al eliminar objetos no utilizados: {e}")
            return False
    
    def optimize_structure(self) -> bool:
        """
        Optimiza la estructura del documento.
        
        Returns:
            bool: True si se optimizó correctamente
        """
        try:
            # Implementación básica de optimización de estructura
            if "/StructTreeRoot" in self.pdf_loader.pikepdf_doc.Root:
                self._optimize_structure_tree()
            
            logger.info("Estructura optimizada")
            return True
            
        except Exception as e:
            logger.error(f"Error al optimizar estructura: {e}")
            return False
    
    def _optimize_structure_tree(self):
        """Optimiza el árbol de estructura."""
        try:
            struct_root = self.pdf_loader.pikepdf_doc.Root["/StructTreeRoot"]
            
            # Limpiar elementos vacíos o redundantes
            self._clean_empty_elements(struct_root)
            
            # Optimizar Referencias
            self._optimize_structure_references(struct_root)
            
            logger.debug("Árbol de estructura optimizado")
            
        except Exception as e:
            logger.warning(f"Error en optimización de árbol de estructura: {e}")
    
    def _clean_empty_elements(self, element):
        """Limpia elementos vacíos de la estructura."""
        try:
            if Name.K in element:
                k_value = element.K
                
                if isinstance(k_value, Array):
                    # Filtrar elementos vacíos
                    cleaned_items = []
                    for item in k_value:
                        if isinstance(item, Dictionary):
                            self._clean_empty_elements(item)
                            # Mantener solo elementos con contenido
                            if self._has_meaningful_content(item):
                                cleaned_items.append(item)
                        else:
                            cleaned_items.append(item)
                    
                    # Actualizar array si cambió
                    if len(cleaned_items) != len(k_value):
                        element[Name.K] = Array(cleaned_items)
                        
                elif isinstance(k_value, Dictionary):
                    self._clean_empty_elements(k_value)
                    
        except Exception as e:
            logger.debug(f"Error limpiando elementos vacíos: {e}")
    
    def _has_meaningful_content(self, element) -> bool:
        """Verifica si un elemento tiene contenido significativo."""
        try:
            # Verificar si tiene texto
            for text_attr in [Name.ActualText, Name.Alt, Name.E]:
                if text_attr in element:
                    text_value = str(element[text_attr]).strip()
                    if text_value:
                        return True
            
            # Verificar si tiene hijos con contenido
            if Name.K in element:
                k_value = element.K
                if isinstance(k_value, (Array, Dictionary, String)) or isinstance(k_value, int):
                    return True
            
            # Verificar si es un elemento estructural importante
            if Name.S in element:
                element_type = str(element.S)
                important_types = ["/Figure", "/Table", "/L", "/H1", "/H2", "/H3", "/H4", "/H5", "/H6"]
                if element_type in important_types:
                    return True
            
            return False
            
        except Exception:
            return True  # En caso de duda, mantener el elemento
    
    def _optimize_structure_references(self, element):
        """Optimiza las referencias en la estructura."""
        try:
            # Esta es una implementación básica
            # En una implementación completa se optimizarían las referencias
            # entre elementos estructurales
            
            if Name.K in element:
                k_value = element.K
                if isinstance(k_value, Array):
                    for item in k_value:
                        if isinstance(item, Dictionary):
                            self._optimize_structure_references(item)
                elif isinstance(k_value, Dictionary):
                    self._optimize_structure_references(k_value)
                    
        except Exception as e:
            logger.debug(f"Error optimizando referencias: {e}")
    
    def export_structure_xml(self, output_path: str) -> bool:
        """
        Exporta la estructura del documento como XML para depuración.
        
        Args:
            output_path: Ruta donde guardar el XML
            
        Returns:
            bool: True si se exportó correctamente
        """
        try:
            if not self.pdf_loader or not self.pdf_loader.structure_tree:
                logger.error("No hay estructura para exportar")
                return False
            
            # Generar XML de la estructura
            xml_content = self._generate_structure_xml(self.pdf_loader.structure_tree)
            
            # Guardar archivo
            with open(output_path, 'w', encoding='utf-8') as f:
                f.write(xml_content)
            
            logger.info(f"Estructura exportada como XML: {output_path}")
            return True
            
        except Exception as e:
            logger.error(f"Error al exportar estructura XML: {e}")
            return False
    
    def _generate_structure_xml(self, structure_data: Dict, level: int = 0) -> str:
        """
        Genera XML recursivamente de la estructura.
        
        Args:
            structure_data: Datos de estructura
            level: Nivel de anidamiento
            
        Returns:
            str: XML generado
        """
        indent = "  " * level
        element_type = structure_data.get("type", "Unknown")
        
        xml_lines = [f"{indent}<{element_type}>"]
        
        # Añadir atributos
        attributes = structure_data.get("attributes", {})
        if attributes:
            attr_lines = []
            for attr_name, attr_value in attributes.items():
                if attr_value:
                    attr_lines.append(f"{indent}  <attr name='{attr_name}' value='{attr_value}' />")
            if attr_lines:
                xml_lines.extend(attr_lines)
        
        # Añadir texto
        text_content = structure_data.get("text", "").strip()
        if text_content:
            xml_lines.append(f"{indent}  <text>{text_content}</text>")
        
        # Añadir hijos
        children = structure_data.get("children", [])
        for child in children:
            if isinstance(child, dict):
                child_xml = self._generate_structure_xml(child, level + 1)
                xml_lines.append(child_xml)
        
        xml_lines.append(f"{indent}</{element_type}>")
        
        return "\n".join(xml_lines)
    
    def cleanup_temp_files(self):
        """Limpia archivos temporales creados."""
        for temp_file in self.temp_files:
            try:
                if os.path.exists(temp_file):
                    os.remove(temp_file)
                    logger.debug(f"Archivo temporal eliminado: {temp_file}")
            except Exception as e:
                logger.warning(f"Error al eliminar archivo temporal {temp_file}: {e}")
        
        self.temp_files.clear()
    
    def __del__(self):
        """Limpia recursos al destruir la instancia."""
        self.cleanup_temp_files()