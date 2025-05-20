#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Módulo para guardar y aplicar cambios a documentos PDF.
Permite modificar estructura, metadatos y contenido.
"""

import os
import tempfile
import shutil
from pathlib import Path
from typing import Dict, List, Tuple, Optional, Any, Union
from datetime import datetime
import uuid

import fitz  # PyMuPDF
import pikepdf
from loguru import logger

class PDFWriter:
    """
    Clase para guardar y aplicar cambios a documentos PDF.
    Permite modificar estructura, metadatos y exportar el documento modificado.
    """
    
    def __init__(self, pdf_loader=None):
        """
        Inicializa el escritor de PDF.
        
        Args:
            pdf_loader: Instancia opcional de PDFLoader con el documento ya cargado
        """
        self.pdf_loader = pdf_loader
        self.modifications = []
        self.temp_file = None
        self.modified_document = None
        logger.info("PDFWriter inicializado")
    
    def set_pdf_loader(self, pdf_loader):
        """Establece el cargador de PDF a utilizar"""
        self.pdf_loader = pdf_loader
    
    def update_metadata(self, metadata: Dict) -> bool:
        """
        Actualiza los metadatos del documento.
        
        Args:
            metadata: Diccionario con metadatos a actualizar
            
        Returns:
            bool: True si la operación es exitosa
            
        Referencias:
            - Matterhorn: 06-001 a 06-004 (metadatos XMP), 07-001, 07-002 (DisplayDocTitle)
            - Tagged PDF: 3.3 (Document level attributes), Anexo A (PDF/UA flag)
        """
        try:
            if self.pdf_loader is None or self.pdf_loader.pikepdf_doc is None:
                logger.error("No hay documento cargado para actualizar metadatos")
                return False
            
            # Registrar modificación para aplicar al guardar
            self.modifications.append({
                "type": "metadata",
                "data": metadata,
                "timestamp": datetime.now().isoformat()
            })
            
            logger.info(f"Metadatos preparados para actualización: {list(metadata.keys())}")
            return True
            
        except Exception as e:
            logger.exception(f"Error al preparar actualización de metadatos: {e}")
            return False
    
    def update_structure_tree(self, structure_tree: Dict) -> bool:
        """
        Actualiza la estructura lógica del documento.
        
        Args:
            structure_tree: Diccionario representando la estructura lógica a aplicar
            
        Returns:
            bool: True si la operación es exitosa
            
        Referencias:
            - Matterhorn: 01-001 a 01-007 (structure tree)
            - Tagged PDF: 3.2 (Fundamentals)
        """
        try:
            if self.pdf_loader is None or self.pdf_loader.pikepdf_doc is None:
                logger.error("No hay documento cargado para actualizar estructura")
                return False
            
            # Registrar modificación para aplicar al guardar
            self.modifications.append({
                "type": "structure_tree",
                "data": structure_tree,
                "timestamp": datetime.now().isoformat()
            })
            
            logger.info("Estructura lógica preparada para actualización")
            return True
            
        except Exception as e:
            logger.exception(f"Error al preparar actualización de estructura: {e}")
            return False
    
    def add_tag(self, tag_info: Dict) -> bool:
        """
        Añade una etiqueta estructural al documento.
        
        Args:
            tag_info: Información de la etiqueta a añadir (type, parent_id, content, attributes)
            
        Returns:
            bool: True si la operación es exitosa
            
        Referencias:
            - Matterhorn: 01-006 (estructura semántica)
            - Tagged PDF: 4.1 y 4.2 (tipos de estructura)
        """
        try:
            # Validar la información de la etiqueta
            required_fields = ["type", "parent_id"]
            for field in required_fields:
                if field not in tag_info:
                    logger.error(f"Falta campo requerido: {field}")
                    return False
            
            # Registrar modificación para aplicar al guardar
            self.modifications.append({
                "type": "add_tag",
                "data": tag_info,
                "timestamp": datetime.now().isoformat()
            })
            
            logger.info(f"Etiqueta {tag_info.get('type')} preparada para añadir a {tag_info.get('parent_id')}")
            return True
            
        except Exception as e:
            logger.exception(f"Error al preparar adición de etiqueta: {e}")
            return False
    
    def update_tag(self, tag_id: str, tag_info: Dict) -> bool:
        """
        Actualiza una etiqueta estructural existente.
        
        Args:
            tag_id: ID de la etiqueta a actualizar
            tag_info: Nueva información para la etiqueta (type, content, attributes)
            
        Returns:
            bool: True si la operación es exitosa
        """
        try:
            # Verificar que la etiqueta existe
            if self.pdf_loader and self.pdf_loader.structure_tree:
                element = self.pdf_loader.find_structure_element_by_id(tag_id)
                if not element:
                    logger.error(f"La etiqueta con ID {tag_id} no existe")
                    return False
            
            # Registrar modificación para aplicar al guardar
            self.modifications.append({
                "type": "update_tag",
                "data": {
                    "tag_id": tag_id,
                    "tag_info": tag_info
                },
                "timestamp": datetime.now().isoformat()
            })
            
            logger.info(f"Etiqueta {tag_id} preparada para actualizar")
            return True
            
        except Exception as e:
            logger.exception(f"Error al preparar actualización de etiqueta: {e}")
            return False
    
    def delete_tag(self, tag_id: str) -> bool:
        """
        Elimina una etiqueta estructural existente.
        
        Args:
            tag_id: ID de la etiqueta a eliminar
            
        Returns:
            bool: True si la operación es exitosa
        """
        try:
            # Verificar que la etiqueta existe
            if self.pdf_loader and self.pdf_loader.structure_tree:
                element = self.pdf_loader.find_structure_element_by_id(tag_id)
                if not element:
                    logger.error(f"La etiqueta con ID {tag_id} no existe")
                    return False
            
            # Registrar modificación para aplicar al guardar
            self.modifications.append({
                "type": "delete_tag",
                "data": {
                    "tag_id": tag_id
                },
                "timestamp": datetime.now().isoformat()
            })
            
            logger.info(f"Etiqueta {tag_id} preparada para eliminar")
            return True
            
        except Exception as e:
            logger.exception(f"Error al preparar eliminación de etiqueta: {e}")
            return False
    
    def move_tag(self, tag_id: str, new_parent_id: str, position: int = -1) -> bool:
        """
        Mueve una etiqueta estructural a un nuevo padre.
        
        Args:
            tag_id: ID de la etiqueta a mover
            new_parent_id: ID del nuevo padre
            position: Posición en la lista de hijos (-1 para el final)
            
        Returns:
            bool: True si la operación es exitosa
        """
        try:
            # Verificar que ambas etiquetas existen
            if self.pdf_loader and self.pdf_loader.structure_tree:
                element = self.pdf_loader.find_structure_element_by_id(tag_id)
                new_parent = self.pdf_loader.find_structure_element_by_id(new_parent_id)
                
                if not element:
                    logger.error(f"La etiqueta con ID {tag_id} no existe")
                    return False
                
                if not new_parent:
                    logger.error(f"El padre con ID {new_parent_id} no existe")
                    return False
                
                # Verificar que no se crea un ciclo
                if self._would_create_cycle(tag_id, new_parent_id):
                    logger.error("Esta operación crearía un ciclo en la estructura")
                    return False
            
            # Registrar modificación para aplicar al guardar
            self.modifications.append({
                "type": "move_tag",
                "data": {
                    "tag_id": tag_id,
                    "new_parent_id": new_parent_id,
                    "position": position
                },
                "timestamp": datetime.now().isoformat()
            })
            
            logger.info(f"Etiqueta {tag_id} preparada para mover a {new_parent_id}")
            return True
            
        except Exception as e:
            logger.exception(f"Error al preparar movimiento de etiqueta: {e}")
            return False
    
    def update_tag_attribute(self, tag_id: str, attribute: str, value: Any) -> bool:
        """
        Actualiza un atributo de una etiqueta específica.
        
        Args:
            tag_id: Identificador de la etiqueta
            attribute: Nombre del atributo
            value: Valor a establecer
            
        Returns:
            bool: True si la operación es exitosa
            
        Referencias:
            - Matterhorn: Según atributo (13-004 para Alt, 15-003 para Scope, etc.)
            - Tagged PDF: 5.1-5.5 (atributos y propiedades)
        """
        try:
            # Verificar que la etiqueta existe
            if self.pdf_loader and self.pdf_loader.structure_tree:
                element = self.pdf_loader.find_structure_element_by_id(tag_id)
                if not element:
                    logger.error(f"La etiqueta con ID {tag_id} no existe")
                    return False
            
            # Validar el atributo
            if not self._is_valid_attribute(attribute):
                logger.warning(f"Atributo no estándar: {attribute}")
            
            # Registrar modificación para aplicar al guardar
            self.modifications.append({
                "type": "update_tag_attribute",
                "data": {
                    "tag_id": tag_id,
                    "attribute": attribute,
                    "value": value
                },
                "timestamp": datetime.now().isoformat()
            })
            
            logger.info(f"Atributo {attribute} de etiqueta {tag_id} preparado para actualizar a {value}")
            return True
            
        except Exception as e:
            logger.exception(f"Error al preparar actualización de atributo: {e}")
            return False
    
    def delete_tag_attribute(self, tag_id: str, attribute: str) -> bool:
        """
        Elimina un atributo de una etiqueta.
        
        Args:
            tag_id: Identificador de la etiqueta
            attribute: Nombre del atributo a eliminar
            
        Returns:
            bool: True si la operación es exitosa
        """
        try:
            # Verificar que la etiqueta existe
            if self.pdf_loader and self.pdf_loader.structure_tree:
                element = self.pdf_loader.find_structure_element_by_id(tag_id)
                if not element:
                    logger.error(f"La etiqueta con ID {tag_id} no existe")
                    return False
                
                # Verificar que el atributo existe
                if "attributes" not in element or attribute not in element["attributes"]:
                    logger.warning(f"El atributo {attribute} no existe en la etiqueta {tag_id}")
            
            # Registrar modificación para aplicar al guardar
            self.modifications.append({
                "type": "delete_tag_attribute",
                "data": {
                    "tag_id": tag_id,
                    "attribute": attribute
                },
                "timestamp": datetime.now().isoformat()
            })
            
            logger.info(f"Atributo {attribute} de etiqueta {tag_id} preparado para eliminar")
            return True
            
        except Exception as e:
            logger.exception(f"Error al preparar eliminación de atributo: {e}")
            return False
    
    def add_pdf_ua_flag(self) -> bool:
        """
        Añade el flag PDF/UA al documento.
        
        Returns:
            bool: True si la operación es exitosa
            
        Referencias:
            - Matterhorn: 06-002 (PDF/UA identifier)
            - Tagged PDF: Anexo A (PDF/UA flag)
        """
        try:
            # Preparar datos del flag PDF/UA
            metadata = {
                "pdfuaid:part": "1"
            }
            
            # Registrar modificación
            self.modifications.append({
                "type": "pdf_ua_flag",
                "data": metadata,
                "timestamp": datetime.now().isoformat()
            })
            
            logger.info("Flag PDF/UA preparado para añadir")
            return True
            
        except Exception as e:
            logger.exception(f"Error al preparar flag PDF/UA: {e}")
            return False
    
    def save_document(self, output_path: str) -> bool:
        """
        Aplica todas las modificaciones pendientes y guarda el documento.
        
        Args:
            output_path: Ruta donde guardar el documento modificado
            
        Returns:
            bool: True si el guardado es exitoso
        """
        try:
            if self.pdf_loader is None or self.pdf_loader.pikepdf_doc is None:
                logger.error("No hay documento cargado para guardar")
                return False
            
            logger.info(f"Aplicando {len(self.modifications)} modificaciones al documento")
            
            # Crear una copia del documento original
            with pikepdf.open(self.pdf_loader.file_path) as original_pdf:
                # Guardar una copia en memoria para aplicar modificaciones
                self.modified_document = pikepdf.Pdf.open(original_pdf)
                
                # Aplicar modificaciones
                self._apply_all_modifications()
                
                # Guardar el documento modificado
                self.modified_document.save(output_path, linearize=False, object_stream_mode=pikepdf.ObjectStreamMode.generate)
                
                logger.success(f"Documento guardado exitosamente en: {output_path}")
                
                # Limpiar modificaciones aplicadas
                self.modifications = []
                
                return True
            
        except Exception as e:
            logger.exception(f"Error al guardar el documento: {e}")
            return False
        finally:
            # Liberar recursos
            if self.modified_document:
                self.modified_document = None
    
    def _apply_all_modifications(self):
        """Aplica todas las modificaciones pendientes al documento."""
        # Ordenar modificaciones por timestamp para mantener el orden
        sorted_mods = sorted(self.modifications, key=lambda x: x["timestamp"])
        
        # Aplicar cada modificación en orden
        for mod in sorted_mods:
            mod_type = mod["type"]
            mod_data = mod["data"]
            
            logger.debug(f"Aplicando modificación: {mod_type}")
            
            if mod_type == "metadata":
                self._apply_metadata_changes(mod_data)
            elif mod_type == "pdf_ua_flag":
                self._apply_pdf_ua_flag()
            elif mod_type == "structure_tree":
                self._apply_structure_tree_changes(mod_data)
            elif mod_type == "add_tag":
                self._apply_add_tag(mod_data)
            elif mod_type == "update_tag":
                self._apply_update_tag(mod_data["tag_id"], mod_data["tag_info"])
            elif mod_type == "delete_tag":
                self._apply_delete_tag(mod_data["tag_id"])
            elif mod_type == "move_tag":
                self._apply_move_tag(mod_data["tag_id"], mod_data["new_parent_id"], mod_data["position"])
            elif mod_type == "update_tag_attribute":
                self._apply_update_tag_attribute(mod_data["tag_id"], mod_data["attribute"], mod_data["value"])
            elif mod_type == "delete_tag_attribute":
                self._apply_delete_tag_attribute(mod_data["tag_id"], mod_data["attribute"])
            else:
                logger.warning(f"Tipo de modificación desconocido: {mod_type}")
    
    def _apply_metadata_changes(self, metadata: Dict):
        """
        Aplica cambios en los metadatos.
        
        Args:
            metadata: Diccionario con metadatos a actualizar
        """
        try:
            # Actualizar metadatos XMP
            with self.modified_document.open_metadata() as meta:
                # Actualizar título
                if "title" in metadata:
                    meta["dc:title"] = metadata["title"]
                
                # Actualizar otros metadatos XMP
                xmp_fields = {
                    "author": "dc:creator",
                    "subject": "dc:subject",
                    "keywords": "pdf:Keywords"
                }
                
                for field, xmp_field in xmp_fields.items():
                    if field in metadata and metadata[field]:
                        meta[xmp_field] = metadata[field]
            
            # Actualizar idioma a nivel de documento
            if "language" in metadata and metadata["language"]:
                self.modified_document.Root.Lang = pikepdf.String(metadata["language"])
            
            # Configurar DisplayDocTitle
            if "display_doc_title" in metadata and metadata["display_doc_title"]:
                if "ViewerPreferences" not in self.modified_document.Root:
                    self.modified_document.Root.ViewerPreferences = pikepdf.Dictionary({})
                
                self.modified_document.Root.ViewerPreferences.DisplayDocTitle = pikepdf.Boolean(True)
            
            logger.info("Metadatos actualizados correctamente")
            
        except Exception as e:
            logger.error(f"Error al aplicar cambios de metadatos: {e}")
            raise
    
    def _apply_pdf_ua_flag(self):
        """Aplica el flag PDF/UA al documento."""
        try:
            with self.modified_document.open_metadata() as meta:
                # Añadir identificador PDF/UA
                meta.load_from_docinfo(self.modified_document.docinfo)
                meta["pdfuaid:part"] = "1"
                
                # Asegurar que se tiene el namespace correcto
                ns = {
                    "pdfuaid": "http://www.aiim.org/pdfua/ns/id/"
                }
                meta.register_namespace("pdfuaid", ns["pdfuaid"])
            
            logger.info("Flag PDF/UA aplicado correctamente")
            
        except Exception as e:
            logger.error(f"Error al aplicar flag PDF/UA: {e}")
            raise
    
    def _apply_structure_tree_changes(self, structure_tree: Dict):
        """
        Aplica cambios en el árbol de estructura.
        
        Args:
            structure_tree: Nuevo árbol de estructura
        """
        try:
            # Verificar si existe StructTreeRoot
            has_struct_tree = "StructTreeRoot" in self.modified_document.Root
            
            # Si no existe, crear uno nuevo
            if not has_struct_tree:
                self.modified_document.Root.StructTreeRoot = pikepdf.Dictionary({
                    "Type": pikepdf.Name("StructTreeRoot")
                })
            
            # Actualizar mapa de roles si existe
            if "role_map" in structure_tree:
                self._update_role_map(structure_tree["role_map"])
            
            # Aplicar cambios en la estructura
            # Esta función es compleja y requiere una implementación detallada
            # por lo que aquí se muestra una versión simplificada
            logger.info("Estructura actualizada (simulado)")
            
        except Exception as e:
            logger.error(f"Error al aplicar cambios en estructura: {e}")
            raise
    
    def _update_role_map(self, role_map: Dict):
        """
        Actualiza el mapa de roles en el documento.
        
        Args:
            role_map: Diccionario con mapeos de roles
        """
        try:
            # Crear RoleMap si no existe
            if "RoleMap" not in self.modified_document.Root.StructTreeRoot:
                self.modified_document.Root.StructTreeRoot.RoleMap = pikepdf.Dictionary({})
            
            # Actualizar mapeos
            for custom_type, standard_type in role_map.items():
                self.modified_document.Root.StructTreeRoot.RoleMap[custom_type] = pikepdf.Name(standard_type)
            
            logger.info(f"Mapa de roles actualizado: {len(role_map)} entradas")
            
        except Exception as e:
            logger.error(f"Error al actualizar mapa de roles: {e}")
            raise
    
    def _apply_add_tag(self, tag_info: Dict):
        """
        Añade una nueva etiqueta al documento.
        
        Args:
            tag_info: Información de la etiqueta a añadir
        """
        # Esta función requiere una implementación compleja que manipule directamente
        # la estructura interna del PDF, creando nuevos objetos y actualizando referencias
        logger.info(f"Etiqueta {tag_info.get('type')} añadida (simulado)")
    
    def _apply_update_tag(self, tag_id: str, tag_info: Dict):
        """
        Actualiza una etiqueta existente.
        
        Args:
            tag_id: ID de la etiqueta a actualizar
            tag_info: Nueva información para la etiqueta
        """
        # Esta función requiere una implementación compleja que manipule directamente
        # la estructura interna del PDF, modificando objetos existentes
        logger.info(f"Etiqueta {tag_id} actualizada (simulado)")
    
    def _apply_delete_tag(self, tag_id: str):
        """
        Elimina una etiqueta existente.
        
        Args:
            tag_id: ID de la etiqueta a eliminar
        """
        # Esta función requiere una implementación compleja que manipule directamente
        # la estructura interna del PDF, eliminando objetos y actualizando referencias
        logger.info(f"Etiqueta {tag_id} eliminada (simulado)")
    
    def _apply_move_tag(self, tag_id: str, new_parent_id: str, position: int):
        """
        Mueve una etiqueta a un nuevo padre.
        
        Args:
            tag_id: ID de la etiqueta a mover
            new_parent_id: ID del nuevo padre
            position: Posición en la lista de hijos
        """
        # Esta función requiere una implementación compleja que manipule directamente
        # la estructura interna del PDF, modificando referencias entre objetos
        logger.info(f"Etiqueta {tag_id} movida a {new_parent_id} (simulado)")
    
    def _apply_update_tag_attribute(self, tag_id: str, attribute: str, value: Any):
        """
        Actualiza un atributo de una etiqueta.
        
        Args:
            tag_id: ID de la etiqueta
            attribute: Nombre del atributo
            value: Nuevo valor
        """
        # Esta función requiere una implementación compleja que manipule directamente
        # la estructura interna del PDF, modificando diccionarios de atributos
        logger.info(f"Atributo {attribute} de etiqueta {tag_id} actualizado a {value} (simulado)")
    
    def _apply_delete_tag_attribute(self, tag_id: str, attribute: str):
        """
        Elimina un atributo de una etiqueta.
        
        Args:
            tag_id: ID de la etiqueta
            attribute: Nombre del atributo a eliminar
        """
        # Esta función requiere una implementación compleja que manipule directamente
        # la estructura interna del PDF, modificando diccionarios de atributos
        logger.info(f"Atributo {attribute} de etiqueta {tag_id} eliminado (simulado)")
    
    def _would_create_cycle(self, tag_id: str, new_parent_id: str) -> bool:
        """
        Verifica si mover una etiqueta crearía un ciclo en la estructura.
        
        Args:
            tag_id: ID de la etiqueta a mover
            new_parent_id: ID del nuevo padre
            
        Returns:
            bool: True si se crearía un ciclo
        """
        # Verificar si el nuevo padre es descendiente de la etiqueta
        if tag_id == new_parent_id:
            return True
            
        if not self.pdf_loader or not self.pdf_loader.structure_tree:
            return False
            
        # Buscar el elemento a mover
        element = self.pdf_loader.find_structure_element_by_id(tag_id)
        if not element or "children" not in element:
            return False
            
        # Función auxiliar para buscar recursivamente
        def is_descendant(children, target_id):
            for child in children:
                if child.get("id") == target_id:
                    return True
                    
                if "children" in child and is_descendant(child["children"], target_id):
                    return True
                    
            return False
            
        return is_descendant(element.get("children", []), new_parent_id)
    
    def _is_valid_attribute(self, attribute: str) -> bool:
        """
        Verifica si un atributo es válido según PDF 1.7.
        
        Args:
            attribute: Nombre del atributo
            
        Returns:
            bool: True si el atributo es válido
        """
        # Lista de atributos válidos según PDF 1.7 y PDF/UA
        valid_attributes = [
            # Atributos de diseño
            "placement", "writing_mode", "background_color", "border_color", "border_style",
            "border_thickness", "color", "padding", "spacing", "text_align", "text_indent",
            "width", "height", "bbox", "block_align", "inline_align", "line_height",
            "baseline_shift", "text_decoration_type", "text_decoration_color", "text_decoration_thickness",
            
            # Atributos de lista
            "list_numbering",
            
            # Atributos de tabla
            "colspan", "rowspan", "headers", "scope", "summary",
            
            # Atributos de texto
            "actual_text", "alt", "e", "lang",
            
            # Atributos de formulario
            "print_field", "tu"
        ]
        
        # Normalizar atributo (convertir a minúsculas, eliminar guiones)
        normalized = attribute.lower().replace("-", "_")
        
        return normalized in valid_attributes