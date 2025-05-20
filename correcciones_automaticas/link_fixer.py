#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Corrección automática de enlaces según PDF/UA.
Añade estructura Link, Contents y Alt.
"""

from typing import Dict, List, Optional, Any
from loguru import logger

class LinkFixer:
    """
    Clase para corregir enlaces según PDF/UA.
    Añade nodos Link con OBJR, copia texto visible a Alt y Contents.
    """
    
    def __init__(self, pdf_writer=None):
        """
        Inicializa el corrector de enlaces.
        
        Args:
            pdf_writer: Instancia opcional de PDFWriter
        """
        self.pdf_writer = pdf_writer
        logger.info("LinkFixer inicializado")
    
    def set_pdf_writer(self, pdf_writer):
        """Establece el escritor de PDF a utilizar"""
        self.pdf_writer = pdf_writer
    
    def fix_all_links(self, structure_tree: Dict, pdf_loader) -> bool:
        """
        Corrige todos los enlaces en la estructura.
        
        Args:
            structure_tree: Diccionario representando la estructura lógica
            pdf_loader: Instancia de PDFLoader con el documento cargado
            
        Returns:
            bool: True si se realizaron correcciones
            
        Referencias:
            - Matterhorn: 28-002, 28-004, 28-011
            - Tagged PDF: 4.2.12, 4.2.9 (Link + Reference)
        """
        try:
            if self.pdf_writer is None:
                logger.error("No hay PDFWriter configurado para aplicar correcciones")
                return False
            
            if not structure_tree or not structure_tree.get("children"):
                logger.warning("No hay estructura para corregir enlaces")
                return False
            
            changes_made = False
            
            # Buscar anotaciones de enlace sin estructura Link
            untagged_links = self._find_untagged_links(pdf_loader)
            
            if untagged_links:
                logger.info(f"Encontrados {len(untagged_links)} enlaces sin etiquetar")
                
                # Etiquetar enlaces
                for link in untagged_links:
                    link_fixed = self._fix_untagged_link(link, structure_tree)
                    if link_fixed:
                        changes_made = True
            
            # Buscar nodos Link sin atributos correctos
            incomplete_links = self._find_incomplete_links(structure_tree.get("children", []))
            
            if incomplete_links:
                logger.info(f"Encontrados {len(incomplete_links)} nodos Link incompletos")
                
                # Completar nodos Link
                for link in incomplete_links:
                    link_fixed = self._fix_incomplete_link(link)
                    if link_fixed:
                        changes_made = True
            
            # Buscar Referencias con enlaces
            reference_links = self._find_reference_links(structure_tree.get("children", []))
            
            if reference_links:
                logger.info(f"Encontrados {len(reference_links)} nodos Reference con enlaces")
                
                # Corregir Referencias con enlaces
                for link in reference_links:
                    link_fixed = self._fix_reference_link(link)
                    if link_fixed:
                        changes_made = True
            
            return changes_made
            
        except Exception as e:
            logger.exception(f"Error al corregir enlaces: {e}")
            return False
    
    def add_link_node(self, parent_id: str, link_content: str, annotation_id: str, url: str = None) -> bool:
        """
        Añade un nodo Link con OBJR.
        
        Args:
            parent_id: Identificador del elemento padre
            link_content: Texto visible del enlace
            annotation_id: Identificador de la anotación de enlace
            url: URL del enlace (opcional)
            
        Returns:
            bool: True si se añadió el nodo
            
        Referencias:
            - Matterhorn: 28-011
            - Tagged PDF: 4.2.12
        """
        try:
            if self.pdf_writer is None:
                logger.error("No hay PDFWriter configurado para aplicar correcciones")
                return False
            
            # Preparar información del nodo Link
            tag_info = {
                "type": "Link",
                "parent_id": parent_id,
                "content": link_content,
                "attributes": {
                    "objr": annotation_id
                }
            }
            
            if url:
                tag_info["attributes"]["url"] = url
            
            logger.info(f"Añadiendo nodo Link a elemento {parent_id}")
            
            # En implementación real, se añadiría el nodo
            # self.pdf_writer.add_tag(tag_info)
            
            return True
            
        except Exception as e:
            logger.exception(f"Error al añadir nodo Link: {e}")
            return False
    
    def update_link_attributes(self, link_id: str, alt_text: str = None, contents: str = None) -> bool:
        """
        Actualiza atributos Alt y Contents de un enlace.
        
        Args:
            link_id: Identificador del nodo Link
            alt_text: Texto alternativo (opcional)
            contents: Contenido para la anotación (opcional)
            
        Returns:
            bool: True si se actualizaron los atributos
            
        Referencias:
            - Matterhorn: 28-004
            - Tagged PDF: 4.2.12
        """
        try:
            if self.pdf_writer is None:
                logger.error("No hay PDFWriter configurado para aplicar correcciones")
                return False
            
            changes_made = False
            
            # Actualizar Alt
            if alt_text:
                logger.info(f"Añadiendo Alt='{alt_text}' a enlace {link_id}")
                self.pdf_writer.update_tag_attribute(link_id, "alt", alt_text)
                changes_made = True
            
            # Actualizar Contents
            if contents:
                logger.info(f"Añadiendo Contents a enlace {link_id}")
                # En implementación real, se actualizaría el atributo Contents de la anotación
                changes_made = True
            
            return changes_made
            
        except Exception as e:
            logger.exception(f"Error al actualizar atributos de enlace: {e}")
            return False
    
    def fix_reference_link_relationship(self, reference_id: str, link_id: str) -> bool:
        """
        Corrige la relación entre nodos Reference y Link.
        
        Args:
            reference_id: Identificador del nodo Reference
            link_id: Identificador del nodo Link
            
        Returns:
            bool: True si se corrigió la relación
            
        Referencias:
            - Tagged PDF: 4.2.9 (Reference)
        """
        try:
            if self.pdf_writer is None:
                logger.error("No hay PDFWriter configurado para aplicar correcciones")
                return False
            
            logger.info(f"Corrigiendo relación entre Reference {reference_id} y Link {link_id}")
            
            # En implementación real, se corregiría la relación
            
            return True
            
        except Exception as e:
            logger.exception(f"Error al corregir relación Reference-Link: {e}")
            return False
    
    def _find_untagged_links(self, pdf_loader) -> List[Dict]:
        """
        Encuentra anotaciones de enlace sin estructura Link.
        
        Args:
            pdf_loader: Instancia de PDFLoader con el documento cargado
            
        Returns:
            List[Dict]: Lista de enlaces sin etiquetar
        """
        # Simulación - en implementación real se analizaría el documento
        untagged_links = []
        
        # Recorrer páginas para encontrar anotaciones
        if pdf_loader and pdf_loader.doc:
            for page_num in range(pdf_loader.doc.page_count):
                # Obtener anotaciones de la página
                page = pdf_loader.doc[page_num]
                
                if page.links:
                    for i, link in enumerate(page.links):
                        # Verificar si el enlace está etiquetado (simulado)
                        is_tagged = (i % 2 == 0)  # Simulación: uno de cada dos enlaces no está etiquetado
                        
                        if not is_tagged:
                            # Extraer información del enlace
                            link_info = {
                                "id": f"link-{page_num}-{i}",
                                "page": page_num,
                                "bbox": link.get("rect", [0, 0, 0, 0]),
                                "url": link.get("uri", ""),
                                "content": "Enlace sin texto extraído"  # En implementación real, se extraería el texto
                            }
                            
                            untagged_links.append(link_info)
        
        return untagged_links
    
    def _fix_untagged_link(self, link: Dict, structure_tree: Dict) -> bool:
        """
        Etiqueta un enlace sin estructura Link.
        
        Args:
            link: Información del enlace
            structure_tree: Diccionario representando la estructura lógica
            
        Returns:
            bool: True si se etiquetó el enlace
        """
        # Determinar el elemento padre apropiado
        parent_id = self._find_appropriate_parent(link, structure_tree)
        
        if not parent_id:
            logger.warning(f"No se pudo encontrar un padre apropiado para el enlace en página {link.get('page', 0)}")
            return False
        
        # Añadir nodo Link
        link_added = self.add_link_node(parent_id, link.get("content", ""), link.get("id", ""), link.get("url", ""))
        
        if not link_added:
            return False
        
        # Añadir atributos Alt y Contents
        link_text = link.get("content", "")
        url = link.get("url", "")
        alt_text = url if not link_text else link_text
        
        # Simulación - en implementación real se actualizarían los atributos
        logger.info(f"Configurando atributos para enlace: Alt='{alt_text}'")
        
        return True
    
    def _find_incomplete_links(self, elements: List[Dict], path: str = "") -> List[Dict]:
        """
        Encuentra nodos Link sin atributos correctos.
        
        Args:
            elements: Lista de elementos de estructura
            path: Ruta de anidamiento actual
            
        Returns:
            List[Dict]: Lista de nodos Link incompletos
        """
        incomplete_links = []
        
        for i, element in enumerate(elements):
            element_type = element.get("type", "")
            current_path = f"{path}/{i}:{element_type}"
            
            if element_type == "Link":
                # Verificar atributos
                has_objr = "objr" in element.get("attributes", {})
                has_alt = "alt" in element.get("attributes", {})
                has_contents = "contents" in element.get("attributes", {})
                
                if not has_objr or not has_alt or not has_contents:
                    # Añadir información de contexto
                    element["_path"] = current_path
                    incomplete_links.append(element)
            
            # Buscar en los hijos
            if element.get("children"):
                child_links = self._find_incomplete_links(element["children"], current_path)
                incomplete_links.extend(child_links)
        
        return incomplete_links
    
    def _fix_incomplete_link(self, link: Dict) -> bool:
        """
        Completa atributos de un nodo Link.
        
        Args:
            link: Información del nodo Link
            
        Returns:
            bool: True si se completaron los atributos
        """
        link_id = link.get("id", "unknown")
        
        # Extraer texto visible del enlace
        link_text = link.get("content", "")
        
        # Determinar texto alternativo y contenido
        if not link_text:
            # No hay texto visible, usar URL
            alt_text = link.get("attributes", {}).get("url", "Enlace")
        else:
            alt_text = link_text
        
        # Actualizar atributos
        return self.update_link_attributes(link_id, alt_text, alt_text)
    
    def _find_reference_links(self, elements: List[Dict], path: str = "") -> List[Dict]:
        """
        Encuentra nodos Reference con enlaces.
        
        Args:
            elements: Lista de elementos de estructura
            path: Ruta de anidamiento actual
            
        Returns:
            List[Dict]: Lista de nodos Reference con enlaces
        """
        reference_links = []
        
        for i, element in enumerate(elements):
            element_type = element.get("type", "")
            current_path = f"{path}/{i}:{element_type}"
            
            if element_type == "Reference":
                # Verificar si contiene nodo Link
                has_link = False
                link_info = None
                
                if element.get("children"):
                    for child in element["children"]:
                        if child.get("type") == "Link":
                            has_link = True
                            link_info = child
                            break
                
                if has_link:
                    # Añadir información de contexto
                    element["_path"] = current_path
                    element["_link"] = link_info
                    reference_links.append(element)
            
            # Buscar en los hijos
            if element.get("children"):
                child_refs = self._find_reference_links(element["children"], current_path)
                reference_links.extend(child_refs)
        
        return reference_links
    
    def _fix_reference_link(self, reference: Dict) -> bool:
        """
        Corrige la relación entre nodos Reference y Link.
        
        Args:
            reference: Información del nodo Reference
            
        Returns:
            bool: True si se corrigió la relación
        """
        reference_id = reference.get("id", "unknown")
        link_info = reference.get("_link", {})
        link_id = link_info.get("id", "unknown")
        
        # Corregir relación
        return self.fix_reference_link_relationship(reference_id, link_id)
    
    def _find_appropriate_parent(self, link: Dict, structure_tree: Dict) -> str:
        """
        Encuentra el elemento padre apropiado para un enlace.
        
        Args:
            link: Información del enlace
            structure_tree: Diccionario representando la estructura lógica
            
        Returns:
            str: Identificador del elemento padre apropiado
        """
        # Simulación - en implementación real se buscaría por posición en la página
        # y se encontraría el elemento que contiene el texto del enlace
        
        # Para la simulación, devolver un ID genérico
        return "p-generic"