#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Módulo para corrección automática de enlaces y anotaciones según PDF/UA.

Este módulo implementa correcciones para los siguientes checkpoints Matterhorn:
- 28-011: Una anotación de enlace no está anidada dentro de una etiqueta <Link>
- 28-004: Una anotación no tiene una entrada Contents y no tiene una descripción alternativa
- 28-005: URL con sintaxis incorrecta
- 28-010: Enlaces ambiguos (mismo texto, diferentes destinos)
- 28-007: Texto alternativo faltante para anotaciones

Referencias:
- ISO 14289-1 (PDF/UA-1): 7.18.5 (Links), 7.18.1-4 (Annotations)
- Matterhorn Protocol: Checkpoint 28
- Tagged PDF Best Practice Guide: 4.2.12 (<Link>), 4.2.9 (<Annot>)
"""

from typing import Dict, List, Optional, Any, Tuple, Set, Union
import re
from collections import defaultdict
from loguru import logger
import fitz  # PyMuPDF
from pikepdf import Pdf, Dictionary, Name, String, Array

class LinkFixer:
    """
    Corrige problemas de accesibilidad en enlaces y anotaciones.
    
    Implementa correcciones automáticas para asegurar que los enlaces y anotaciones
    cumplan con los requisitos de PDF/UA, incluyendo estructura correcta, texto 
    alternativo y descripción accesible.
    """
    
    def __init__(self, pdf_writer=None):
        """
        Inicializa el corrector de enlaces.
        
        Args:
            pdf_writer: Instancia de PDFWriter para aplicar cambios al documento
        """
        self.pdf_writer = pdf_writer
        self.pdf_loader = None
        self.structure_manager = None
        self.modified = False
        self.stats = {
            "total_links": 0,
            "total_annotations": 0,
            "links_without_structure": 0,
            "links_without_contents": 0,
            "annotations_without_alt": 0,
            "ambiguous_links": 0,
            "fixed_structure": 0,
            "fixed_contents": 0,
            "fixed_alt": 0,
            "fixed_ambiguous": 0
        }
        logger.info("LinkFixer inicializado")
    
    def set_pdf_writer(self, pdf_writer):
        """Establece el escritor de PDF a utilizar"""
        self.pdf_writer = pdf_writer
        
    def set_structure_manager(self, structure_manager):
        """Establece el gestor de estructura a utilizar"""
        self.structure_manager = structure_manager
    
    def fix_all_links(self, structure_tree: Dict, pdf_loader) -> bool:
        """
        Corrige todos los enlaces y anotaciones en el documento.
        
        Args:
            structure_tree: Diccionario con la estructura lógica del documento
            pdf_loader: Instancia de PDFLoader con el documento cargado
            
        Returns:
            bool: True si se realizaron correcciones, False en caso contrario
            
        Referencias:
            - Matterhorn: 28-004, 28-005, 28-007, 28-010, 28-011
            - Tagged PDF: 4.2.9 (<Annot>), 4.2.12 (<Link>)
        """
        if not structure_tree or not pdf_loader or not self.pdf_writer:
            logger.warning("No se puede corregir enlaces: faltan componentes necesarios")
            return False
        
        self.pdf_loader = pdf_loader
        self.modified = False
        
        # Reiniciar estadísticas
        for key in self.stats:
            self.stats[key] = 0
        
        # 1. Encontrar todas las anotaciones de enlace en el documento
        link_annotations = self._find_all_link_annotations()
        self.stats["total_links"] = len(link_annotations)
        logger.info(f"Encontradas {len(link_annotations)} anotaciones de enlace")
        
        # 2. Encontrar todas las anotaciones no enlace en el documento
        other_annotations = self._find_all_other_annotations()
        self.stats["total_annotations"] = len(other_annotations)
        logger.info(f"Encontradas {len(other_annotations)} anotaciones adicionales")
        
        # 3. Verificar si las anotaciones de enlace están correctamente estructuradas
        link_issues = self._analyze_link_structure(link_annotations, structure_tree)
        
        # 4. Verificar si las demás anotaciones tienen texto alternativo
        annot_issues = self._analyze_annotation_alt_text(other_annotations, structure_tree)
        
        # 5. Corregir los problemas detectados en enlaces
        for issue in link_issues:
            if issue['type'] == 'missing_structure':
                if self._fix_missing_link_structure(issue):
                    self.stats["fixed_structure"] += 1
                    
            elif issue['type'] == 'missing_contents':
                if self._fix_missing_contents(issue):
                    self.stats["fixed_contents"] += 1
                    
            elif issue['type'] == 'ambiguous_links':
                if self._fix_ambiguous_links(issue):
                    self.stats["fixed_ambiguous"] += 1
        
        # 6. Corregir la falta de texto alternativo en anotaciones
        for issue in annot_issues:
            if issue['type'] == 'missing_alt_text':
                if self._fix_missing_alt_text(issue):
                    self.stats["fixed_alt"] += 1
        
        # Registrar estadísticas
        logger.info(f"Estadísticas de corrección: {self.stats}")
        
        return self.modified

    def _find_all_link_annotations(self) -> List[Dict]:
        """
        Encuentra todas las anotaciones de enlace en el documento.
        
        Returns:
            List[Dict]: Lista de anotaciones de enlace con información relevante
        """
        link_annotations = []
        
        try:
            # Recorrer todas las páginas buscando anotaciones de enlace
            for page_idx in range(self.pdf_loader.page_count):
                page = self.pdf_loader.doc[page_idx]
                
                for annot in page.annots():
                    if annot.type[1] == 'Link':  # Comprobar si es una anotación de enlace
                        link_info = {
                            'annot': annot,
                            'page': page_idx,
                            'rect': annot.rect,
                            'structured': False,  # Se verificará más tarde
                            'contents': None,
                            'alt_text': None,
                            'link_type': None,    # 'URI', 'GoTo', 'GoToR', etc.
                            'destination': None,
                            'structure_element': None,
                            'xref': annot.xref if hasattr(annot, 'xref') else None
                        }
                        
                        # Extraer información del enlace
                        if hasattr(annot, 'info') and 'content' in annot.info:
                            link_info['contents'] = annot.info['content']
                        
                        # Extraer tipo de enlace y destino
                        if hasattr(annot, 'uri'):
                            link_info['link_type'] = 'URI'
                            link_info['destination'] = annot.uri
                        elif hasattr(annot, 'dest') and annot.dest:
                            link_info['link_type'] = 'GoTo'
                            link_info['destination'] = str(annot.dest)
                        
                        # Si usamos pikepdf, podemos obtener más información
                        if self.pdf_loader.pikepdf_doc and link_info['xref']:
                            try:
                                # Obtener la anotación desde pikepdf
                                annot_obj = self.pdf_loader.pikepdf_doc.get_object(link_info['xref'])
                                
                                # Extraer Contents
                                if Name.Contents in annot_obj:
                                    link_info['contents'] = str(annot_obj[Name.Contents])
                                
                                # Extraer información de la acción
                                if Name.A in annot_obj:
                                    action = annot_obj[Name.A]
                                    if Name.S in action:
                                        link_info['link_type'] = str(action[Name.S]).replace('/', '')
                                        
                                        if link_info['link_type'] == 'URI' and Name.URI in action:
                                            link_info['destination'] = str(action[Name.URI])
                                        elif link_info['link_type'] in ['GoTo', 'GoToR'] and Name.D in action:
                                            link_info['destination'] = str(action[Name.D])
                            except Exception as e:
                                logger.warning(f"Error al procesar anotación pikepdf: {e}")
                        
                        link_annotations.append(link_info)
                        
        except Exception as e:
            logger.error(f"Error al buscar anotaciones de enlace: {e}")
        
        return link_annotations

    def _find_all_other_annotations(self) -> List[Dict]:
        """
        Encuentra todas las anotaciones que no son enlaces en el documento.
        
        Returns:
            List[Dict]: Lista de anotaciones no enlace con información relevante
        """
        other_annotations = []
        
        try:
            # Recorrer todas las páginas buscando anotaciones que no sean enlaces
            for page_idx in range(self.pdf_loader.page_count):
                page = self.pdf_loader.doc[page_idx]
                
                for annot in page.annots():
                    # Omitir enlaces (ya procesados en _find_all_link_annotations)
                    # Omitir también PrinterMark que no requieren texto alt según PDF/UA
                    if annot.type[1] in ['Link', 'PrinterMark']:
                        continue
                        
                    annot_info = {
                        'annot': annot,
                        'page': page_idx,
                        'rect': annot.rect,
                        'type': annot.type[1],
                        'structured': False,  # Se verificará más tarde
                        'contents': None,
                        'alt_text': None,
                        'structure_element': None,
                        'xref': annot.xref if hasattr(annot, 'xref') else None
                    }
                    
                    # Extraer información de la anotación
                    if hasattr(annot, 'info') and 'content' in annot.info:
                        annot_info['contents'] = annot.info['content']
                    
                    # Si usamos pikepdf, podemos obtener más información
                    if self.pdf_loader.pikepdf_doc and annot_info['xref']:
                        try:
                            # Obtener la anotación desde pikepdf
                            annot_obj = self.pdf_loader.pikepdf_doc.get_object(annot_info['xref'])
                            
                            # Extraer Contents
                            if Name.Contents in annot_obj:
                                annot_info['contents'] = str(annot_obj[Name.Contents])
                                
                            # Extraer descripción alternativa (puede estar en diferentes lugares)
                            if Name.Alt in annot_obj:
                                annot_info['alt_text'] = str(annot_obj[Name.Alt])
                            elif Name.Contents in annot_obj:
                                # Si no hay Alt pero hay Contents, se puede usar como alt_text
                                annot_info['alt_text'] = str(annot_obj[Name.Contents])
                                
                        except Exception as e:
                            logger.warning(f"Error al procesar anotación pikepdf: {e}")
                    
                    other_annotations.append(annot_info)
                        
        except Exception as e:
            logger.error(f"Error al buscar anotaciones: {e}")
        
        return other_annotations
    
    def _analyze_link_structure(self, link_annotations: List[Dict], structure_tree: Dict) -> List[Dict]:
        """
        Analiza la estructura de los enlaces para detectar problemas.
        
        Args:
            link_annotations: Lista de anotaciones de enlace
            structure_tree: Estructura lógica del documento
            
        Returns:
            List[Dict]: Lista de problemas detectados
        """
        issues = []
        
        # Buscar todos los elementos <Link> en la estructura
        link_elements = self._find_link_elements(structure_tree)
        logger.info(f"Encontrados {len(link_elements)} elementos <Link> en la estructura")
        
        # Mapear cada anotación a su elemento <Link> si existe
        for link_annot in link_annotations:
            matching_element = self._find_matching_link_element(link_annot, link_elements)
            
            if matching_element:
                link_annot['structured'] = True
                link_annot['structure_element'] = matching_element
                
                # Verificar si el elemento <Link> tiene un OBJR
                has_objr = self._has_objr(matching_element)
                if not has_objr:
                    issues.append({
                        'type': 'missing_objr',
                        'annotation': link_annot,
                        'element': matching_element
                    })
                
                # Verificar si el elemento <Link> tiene texto alternativo
                alt_text = self._get_element_attribute(matching_element, "alt")
                if not alt_text:
                    issues.append({
                        'type': 'missing_alt_text',
                        'annotation': link_annot,
                        'element': matching_element
                    })
                    self.stats["annotations_without_alt"] += 1
            else:
                # La anotación no tiene un elemento <Link> correspondiente
                self.stats["links_without_structure"] += 1
                issues.append({
                    'type': 'missing_structure',
                    'annotation': link_annot
                })
            
            # Verificar si la anotación tiene Contents
            if not link_annot['contents']:
                self.stats["links_without_contents"] += 1
                issues.append({
                    'type': 'missing_contents',
                    'annotation': link_annot,
                    'element': link_annot.get('structure_element')
                })
        
        # Verificar enlaces ambiguos (mismo texto pero diferentes destinos)
        ambiguous_links = self._detect_ambiguous_links(link_elements)
        for group in ambiguous_links:
            self.stats["ambiguous_links"] += len(group)
            issues.append({
                'type': 'ambiguous_links',
                'links': group
            })
        
        return issues
    
    def _analyze_annotation_alt_text(self, annotations: List[Dict], structure_tree: Dict) -> List[Dict]:
        """
        Analiza si las anotaciones tienen texto alternativo adecuado.
        
        Args:
            annotations: Lista de anotaciones no enlace
            structure_tree: Estructura lógica del documento
            
        Returns:
            List[Dict]: Lista de problemas detectados
        """
        issues = []
        
        # Buscar todos los elementos <Annot> en la estructura
        annot_elements = self._find_annot_elements(structure_tree)
        logger.info(f"Encontrados {len(annot_elements)} elementos <Annot> en la estructura")
        
        # Verificar cada anotación
        for annot in annotations:
            # Si es un widget (campo de formulario), tiene reglas diferentes según PDF/UA
            if annot['type'] == 'Widget':
                # Los widgets no necesitan obligatoriamente texto alt, pero deberían tener TU (tooltip)
                continue
                
            # Buscar el elemento <Annot> correspondiente
            matching_element = self._find_matching_annot_element(annot, annot_elements)
            
            if matching_element:
                annot['structured'] = True
                annot['structure_element'] = matching_element
                
                # Verificar si el elemento <Annot> tiene texto alternativo
                alt_text = self._get_element_attribute(matching_element, "alt")
                if alt_text:
                    annot['alt_text'] = alt_text
            
            # Si la anotación no tiene texto alternativo ni Contents, reportar problema
            if not annot['alt_text'] and not annot['contents']:
                self.stats["annotations_without_alt"] += 1
                issues.append({
                    'type': 'missing_alt_text',
                    'annotation': annot,
                    'element': annot.get('structure_element')
                })
        
        return issues
    
    def _find_link_elements(self, structure_tree: Dict, path: str = "") -> List[Dict]:
        """
        Encuentra todos los elementos <Link> en la estructura lógica.
        
        Args:
            structure_tree: Estructura lógica del documento
            path: Ruta de anidamiento actual
            
        Returns:
            List[Dict]: Lista de elementos <Link> encontrados con información de contexto
        """
        link_elements = []
        
        if not structure_tree:
            return link_elements
            
        # Si es un diccionario con "children", procesar los hijos
        if isinstance(structure_tree, dict):
            # Verificar si es un elemento <Link>
            element_type = structure_tree.get("type", "")
            if element_type == "Link":
                # Añadir información de contexto
                link_info = dict(structure_tree)
                link_info["_path"] = path
                link_elements.append(link_info)
            
            # Buscar en los hijos
            children = structure_tree.get("children", [])
            for i, child in enumerate(children):
                child_path = f"{path}/{i}:{element_type}"
                child_links = self._find_link_elements(child, child_path)
                link_elements.extend(child_links)
        
        # Si es una lista, procesar cada elemento
        elif isinstance(structure_tree, list):
            for i, item in enumerate(structure_tree):
                item_path = f"{path}/{i}"
                item_links = self._find_link_elements(item, item_path)
                link_elements.extend(item_links)
        
        return link_elements
    
    def _find_annot_elements(self, structure_tree: Dict, path: str = "") -> List[Dict]:
        """
        Encuentra todos los elementos <Annot> en la estructura lógica.
        
        Args:
            structure_tree: Estructura lógica del documento
            path: Ruta de anidamiento actual
            
        Returns:
            List[Dict]: Lista de elementos <Annot> encontrados con información de contexto
        """
        annot_elements = []
        
        if not structure_tree:
            return annot_elements
            
        # Si es un diccionario con "children", procesar los hijos
        if isinstance(structure_tree, dict):
            # Verificar si es un elemento <Annot>
            element_type = structure_tree.get("type", "")
            if element_type == "Annot":
                # Añadir información de contexto
                annot_info = dict(structure_tree)
                annot_info["_path"] = path
                annot_elements.append(annot_info)
            
            # Buscar en los hijos
            children = structure_tree.get("children", [])
            for i, child in enumerate(children):
                child_path = f"{path}/{i}:{element_type}"
                child_annots = self._find_annot_elements(child, child_path)
                annot_elements.extend(child_annots)
        
        # Si es una lista, procesar cada elemento
        elif isinstance(structure_tree, list):
            for i, item in enumerate(structure_tree):
                item_path = f"{path}/{i}"
                item_annots = self._find_annot_elements(item, item_path)
                annot_elements.extend(item_annots)
        
        return annot_elements
    
    def _find_matching_link_element(self, link_annot: Dict, link_elements: List[Dict]) -> Optional[Dict]:
        """
        Encuentra el elemento <Link> correspondiente a una anotación de enlace.
        
        Args:
            link_annot: Información de la anotación de enlace
            link_elements: Lista de elementos <Link> en la estructura
            
        Returns:
            Optional[Dict]: Elemento <Link> correspondiente o None si no se encuentra
        """
        # Para encontrar un elemento <Link> correspondiente a una anotación,
        # podemos verificar:
        # 1. Referencias directas mediante OBJR
        # 2. Superposición geométrica en la misma página
        # 3. Posibles referencias mediante MCIDs
        
        # 1. Buscar referencias directas (OBJR)
        for element in link_elements:
            if "element" in element and hasattr(element["element"], "K"):
                # Verificar si K es un Array que contiene referencias a objetos
                k_value = element["element"].K
                if isinstance(k_value, Array):
                    for item in k_value:
                        if isinstance(item, Dictionary) and item.get("Type") == Name.OBJR:
                            # Si hay una referencia al objeto de la anotación
                            if item.get("Obj") and item.get("Obj").objgen[0] == link_annot['xref']:
                                return element
            
            # Buscar en los posibles hijos que sean OBJR
            objr_elements = self._find_objr_elements(element)
            for objr in objr_elements:
                if self._is_same_annotation(objr, link_annot['annot']):
                    return element
        
        # 2. Verificar superposición geométrica en la misma página
        page = link_annot['page']
        rect = link_annot['rect']
        
        for element in link_elements:
            element_page = element.get('page')
            # Solo verificar elementos en la misma página
            if element_page == page:
                # Si el elemento tiene coordenadas, verificar superposición
                if 'rect' in element:
                    element_rect = element['rect']
                    if self._rects_overlap(rect, element_rect):
                        return element
        
        # 3. Utilizar el PDF loader para buscar por MCIDs
        # Esta implementación depende de cómo está organizado el loader
        if hasattr(self.pdf_loader, 'find_structure_element_for_annot'):
            try:
                element = self.pdf_loader.find_structure_element_for_annot(link_annot['annot'])
                if element and element.get("type") == "Link":
                    return element
            except Exception as e:
                logger.debug(f"Error buscando elemento para anotación: {e}")
        
        return None
    
    def _find_matching_annot_element(self, annot: Dict, annot_elements: List[Dict]) -> Optional[Dict]:
        """
        Encuentra el elemento <Annot> correspondiente a una anotación.
        
        Args:
            annot: Información de la anotación
            annot_elements: Lista de elementos <Annot> en la estructura
            
        Returns:
            Optional[Dict]: Elemento <Annot> correspondiente o None si no se encuentra
        """
        # Similar a _find_matching_link_element pero para otros tipos de anotaciones
        # 1. Buscar referencias directas (OBJR)
        for element in annot_elements:
            if "element" in element and hasattr(element["element"], "K"):
                # Verificar si K es un Array que contiene referencias a objetos
                k_value = element["element"].K
                if isinstance(k_value, Array):
                    for item in k_value:
                        if isinstance(item, Dictionary) and item.get("Type") == Name.OBJR:
                            # Si hay una referencia al objeto de la anotación
                            if item.get("Obj") and item.get("Obj").objgen[0] == annot['xref']:
                                return element
        
        # 2. Verificar superposición geométrica en la misma página
        page = annot['page']
        rect = annot['rect']
        
        for element in annot_elements:
            element_page = element.get('page')
            # Solo verificar elementos en la misma página
            if element_page == page:
                # Si el elemento tiene coordenadas, verificar superposición
                if 'rect' in element:
                    element_rect = element['rect']
                    if self._rects_overlap(rect, element_rect):
                        return element
        
        # 3. Utilizar el PDF loader para buscar por MCIDs
        if hasattr(self.pdf_loader, 'find_structure_element_for_annot'):
            try:
                element = self.pdf_loader.find_structure_element_for_annot(annot['annot'])
                if element and element.get("type") == "Annot":
                    return element
            except Exception as e:
                logger.debug(f"Error buscando elemento para anotación: {e}")
        
        return None
    
    def _has_objr(self, element: Dict) -> bool:
        """
        Verifica si un elemento tiene un OBJR (Object Reference).
        
        Args:
            element: Elemento a verificar
            
        Returns:
            bool: True si tiene OBJR, False en caso contrario
        """
        # Un elemento <Link> o <Annot> debería tener un hijo con tipo "OBJR"
        children = element.get("children", [])
        for child in children:
            if isinstance(child, dict) and child.get("type") == "Link-OBJR":
                return True
                
        # Verificar en el elemento pikepdf
        if "element" in element and hasattr(element["element"], "K"):
            k_value = element["element"].K
            if isinstance(k_value, Array):
                for item in k_value:
                    if isinstance(item, Dictionary) and item.get("Type") == Name.OBJR:
                        return True
                        
        return False
    
    def _find_objr_elements(self, element: Dict) -> List[Dict]:
        """
        Encuentra todos los OBJRs dentro de un elemento.
        
        Args:
            element: Elemento a analizar
            
        Returns:
            List[Dict]: Lista de OBJRs encontrados
        """
        objr_elements = []
        
        # Buscar en los hijos directos
        children = element.get("children", [])
        for child in children:
            if isinstance(child, dict) and child.get("type") == "Link-OBJR":
                objr_elements.append(child)
        
        return objr_elements
    
    def _fix_missing_link_structure(self, issue: Dict) -> bool:
        """
        Corrige un enlace que no tiene estructura <Link>.
        
        Args:
            issue: Información del problema a corregir
            
        Returns:
            bool: True si se corrigió, False en caso contrario
        """
        if not self.pdf_writer:
            logger.warning("No se puede corregir: falta pdf_writer")
            return False
            
        try:
            link_annot = issue['annotation']
            page_num = link_annot['page']
            
            # Obtener contenido cercano para determinar dónde añadir el <Link>
            content_near_link = self._get_content_near_annotation(link_annot)
            
            if not content_near_link:
                logger.warning(f"No se encontró contenido cerca del enlace en la página {page_num}")
                return False
            
            # Preparar atributos para el nuevo elemento <Link>
            link_attributes = {}
            
            # Si conocemos el texto del enlace, usarlo para Alt
            if content_near_link.get('text'):
                link_attributes["alt"] = content_near_link['text']
            
            # También usar el destino en Alt o Contents si está disponible
            if link_annot['destination']:
                # Si el texto del enlace ya contiene el destino, no duplicar
                if not content_near_link.get('text') or link_annot['destination'] not in content_near_link.get('text', ''):
                    if "alt" in link_attributes:
                        link_attributes["alt"] += f" (destino: {link_annot['destination']})"
                    else:
                        link_attributes["alt"] = f"Enlace a {link_annot['destination']}"
            
            # Determinar el elemento padre donde insertar el <Link>
            parent_element = content_near_link.get('parent_element')
            
            # Si no encontramos un elemento padre, intentar usar el Structure Manager
            if not parent_element and self.structure_manager:
                # Intentar encontrar un elemento adecuado en la estructura
                page_elements = self._find_page_structure_elements(page_num)
                for elem in page_elements:
                    elem_rect = self._get_element_rect(elem)
                    if elem_rect and self._rects_overlap(link_annot['rect'], elem_rect):
                        parent_element = elem
                        break
            
            if not parent_element:
                logger.warning(f"No se pudo determinar dónde insertar el <Link> en página {page_num}")
                return False
            
            # Si estamos usando Structure Manager, crear el elemento <Link> a través de él
            if self.structure_manager:
                # Crear el elemento <Link>
                tag_data = {
                    "type": "Link",
                    "text": content_near_link.get('text', ''),
                    "attributes": link_attributes
                }
                
                # Añadir el <Link> a la estructura
                success = self.structure_manager.create_tag(
                    parent_id=id(parent_element.get("element")),
                    tag_data=tag_data
                )
                
                if success:
                    # Ahora necesitamos añadir la anotación como un objeto referenciado
                    # Esto depende de la implementación específica del Structure Manager
                    # En un escenario real, esta función existiría
                    if hasattr(self.structure_manager, "add_objr_to_element"):
                        self.structure_manager.add_objr_to_element(success, link_annot['annot'])
                    
                    self.modified = True
                    logger.info(f"Se añadió estructura <Link> para anotación en página {page_num}")
                    return True
            
            # Alternativa: usar directamente el PDF Writer si no hay Structure Manager
            tag_info = {
                "type": "Link",
                "parent_id": id(parent_element.get("element")),
                "content": content_near_link.get('text', ''),
                "attributes": link_attributes
            }
            
            success = self.pdf_writer.add_tag(tag_info)
            
            if success:
                self.modified = True
                logger.info(f"Se añadió estructura <Link> para anotación en página {page_num}")
                return True
            else:
                logger.warning(f"No se pudo añadir estructura <Link> para anotación en página {page_num}")
                return False
                
        except Exception as e:
            logger.error(f"Error al corregir estructura de enlace: {str(e)}")
            return False
    
    def _fix_missing_contents(self, issue: Dict) -> bool:
        """
        Añade una entrada Contents a una anotación de enlace.
        
        Args:
            issue: Información del problema a corregir
            
        Returns:
            bool: True si se corrigió, False en caso contrario
        """
        try:
            link_annot = issue['annotation']
            annot = link_annot['annot']
            page_num = link_annot['page']
            
            # Si hay un elemento <Link> con Alt, usar ese valor
            element = link_annot.get('structure_element')
            alt_text = None
            
            if element:
                alt_text = self._get_element_attribute(element, "alt")
            
            # Si no hay Alt, intentar usar el texto del enlace
            if not alt_text and element:
                alt_text = element.get("text", "")
            
            # Si aún no hay texto, usar el destino del enlace
            if not alt_text and link_annot.get('destination'):
                alt_text = link_annot.get('destination')
            
            # Si todavía no hay texto, usar un texto genérico
            if not alt_text:
                alt_text = "Enlace"
            
            # Actualizar la anotación con Contents
            success = False
            
            # Método 1: Usando pikepdf si está disponible
            if self.pdf_loader.pikepdf_doc and link_annot['xref']:
                try:
                    annot_obj = self.pdf_loader.pikepdf_doc.get_object(link_annot['xref'])
                    annot_obj[Name.Contents] = String(alt_text)
                    success = True
                except Exception as e:
                    logger.warning(f"Error al actualizar Contents con pikepdf: {e}")
            
            # Método 2: Usando PyMuPDF
            if not success:
                try:
                    if hasattr(annot, "set_info"):
                        annot.set_info(content=alt_text)
                        success = True
                    elif hasattr(annot, "update_info"):
                        annot.update_info({"content": alt_text})
                        success = True
                except Exception as e:
                    logger.warning(f"Error al actualizar Contents con PyMuPDF: {e}")
            
            # Método 3: Usar PDF Writer
            if not success and self.pdf_writer:
                try:
                    # Verificar si pdf_writer tiene un método para actualizar anotaciones
                    if hasattr(self.pdf_writer, "update_annotation"):
                        success = self.pdf_writer.update_annotation(link_annot['xref'], "Contents", alt_text)
                except Exception as e:
                    logger.warning(f"Error al actualizar Contents con PDF Writer: {e}")
            
            if success:
                self.modified = True
                logger.info(f"Se añadió Contents a la anotación de enlace en página {page_num}")
                return True
            else:
                logger.warning(f"No se pudo añadir Contents a la anotación en página {page_num}")
                return False
                
        except Exception as e:
            logger.error(f"Error al añadir Contents a la anotación: {str(e)}")
            return False
    
    def _fix_missing_alt_text(self, issue: Dict) -> bool:
        """
        Añade texto alternativo a una anotación.
        
        Args:
            issue: Información del problema a corregir
            
        Returns:
            bool: True si se corrigió, False en caso contrario
        """
        try:
            annot_info = issue['annotation']
            page_num = annot_info['page']
            annot_type = annot_info['type']
            
            # Determinar texto alternativo adecuado
            alt_text = None
            
            # 1. Si tiene Contents, usarlo como texto alternativo
            if annot_info['contents']:
                alt_text = annot_info['contents']
            
            # 2. Si es un enlace y tiene destino, usar esa información
            if annot_type == 'Link' and annot_info.get('destination'):
                alt_text = f"Enlace a {annot_info['destination']}"
            
            # 3. Para otros tipos de anotaciones, crear un texto descriptivo según el tipo
            if not alt_text:
                descriptive_texts = {
                    'Text': 'Nota de texto',
                    'FreeText': 'Texto libre',
                    'Line': 'Línea',
                    'Square': 'Rectángulo',
                    'Circle': 'Círculo',
                    'Polygon': 'Polígono',
                    'PolyLine': 'Línea poligonal',
                    'Highlight': 'Texto resaltado',
                    'Underline': 'Texto subrayado',
                    'Squiggly': 'Texto con subrayado ondulado',
                    'StrikeOut': 'Texto tachado',
                    'Stamp': 'Sello',
                    'Caret': 'Marca de inserción',
                    'Ink': 'Dibujo a mano',
                    'FileAttachment': 'Archivo adjunto',
                    'Sound': 'Sonido',
                    'Movie': 'Vídeo',
                    'Screen': 'Pantalla',
                    '3D': 'Objeto 3D',
                    'Redact': 'Redacción',
                    'Popup': 'Ventana emergente',
                    'RichMedia': 'Contenido multimedia'
                }
                
                alt_text = descriptive_texts.get(annot_type, f"Anotación de tipo {annot_type}")
            
            # Establecer o actualizar el texto alternativo
            success = False
            element = annot_info.get('structure_element')
            
            # Si tiene un elemento de estructura, actualizar ahí el Alt
            if element and self.structure_manager:
                try:
                    # Actualizar atributo Alt en el elemento
                    if hasattr(self.structure_manager, "update_tag_attribute"):
                        success = self.structure_manager.update_tag_attribute(
                            id(element.get("element")),
                            "alt",
                            alt_text
                        )
                except Exception as e:
                    logger.warning(f"Error al actualizar Alt en elemento: {e}")
            
            # Si no hay elemento o no se pudo actualizar, intentar actualizar la anotación directamente
            if not success and annot_info.get('xref') and self.pdf_loader.pikepdf_doc:
                try:
                    # Actualizar directamente en la anotación
                    annot_obj = self.pdf_loader.pikepdf_doc.get_object(annot_info['xref'])
                    annot_obj[Name.Alt] = String(alt_text)
                    success = True
                except Exception as e:
                    logger.warning(f"Error al actualizar Alt con pikepdf: {e}")
            
            # Si aún no se ha actualizado, intentar con el writer
            if not success and self.pdf_writer:
                try:
                    if hasattr(self.pdf_writer, "update_annotation"):
                        success = self.pdf_writer.update_annotation(annot_info['xref'], "Alt", alt_text)
                except Exception as e:
                    logger.warning(f"Error al actualizar Alt con PDF Writer: {e}")
            
            # Como último recurso, actualizar Contents si no hay Alt
            if not success:
                try:
                    annot = annot_info['annot']
                    if hasattr(annot, "set_info"):
                        annot.set_info(content=alt_text)
                        success = True
                    elif hasattr(annot, "update_info"):
                        annot.update_info({"content": alt_text})
                        success = True
                except Exception as e:
                    logger.warning(f"Error al actualizar Contents con PyMuPDF: {e}")
            
            if success:
                self.modified = True
                logger.info(f"Se añadió texto alternativo a la anotación {annot_type} en página {page_num}")
                return True
            else:
                logger.warning(f"No se pudo añadir texto alternativo a la anotación en página {page_num}")
                return False
                
        except Exception as e:
            logger.error(f"Error al añadir texto alternativo: {str(e)}")
            return False
    
    def _fix_ambiguous_links(self, issue: Dict) -> bool:
        """
        Corrige enlaces ambiguos (mismo texto pero diferentes destinos).
        
        Args:
            issue: Información del problema a corregir
            
        Returns:
            bool: True si se corrigió, False en caso contrario
        """
        try:
            ambiguous_links = issue['links']
            
            # Para cada enlace ambiguo, añadir información adicional al Alt
            fixed_count = 0
            
            for link_element in ambiguous_links:
                original_alt = self._get_element_attribute(link_element, "alt")
                destination = None
                
                # Obtener el destino del enlace
                objr_elements = self._find_objr_elements(link_element)
                for objr in objr_elements:
                    if "element" in objr and hasattr(objr["element"], "A"):
                        action = objr["element"].A
                        if action.get("S") == Name.URI:
                            destination = str(action.get("URI", ""))
                        elif action.get("S") in [Name.GoTo, Name.GoToR]:
                            destination = str(action.get("D", ""))
                
                # Si no encontramos el destino con OBJR, buscar en la anotación
                if not destination and "annotation" in link_element:
                    annot = link_element["annotation"]
                    if hasattr(annot, "uri"):
                        destination = annot.uri
                    elif hasattr(annot, "dest"):
                        destination = str(annot.dest)
                
                if destination:
                    # Crear un Alt que incluya información sobre el destino
                    new_alt = original_alt if original_alt else link_element.get("text", "Enlace")
                    new_alt = f"{new_alt} (destino: {destination})"
                    
                    # Actualizar el Alt del elemento <Link>
                    success = False
                    
                    # Método 1: Usando Structure Manager
                    if self.structure_manager:
                        if hasattr(self.structure_manager, "update_tag_attribute"):
                            success = self.structure_manager.update_tag_attribute(
                                id(link_element.get("element")), 
                                "alt", 
                                new_alt
                            )
                    
                    # Método 2: Usando PDF Writer
                    if not success and self.pdf_writer:
                        if hasattr(self.pdf_writer, "update_tag_attribute"):
                            success = self.pdf_writer.update_tag_attribute(
                                id(link_element.get("element")), 
                                "alt", 
                                new_alt
                            )
                    
                    if success:
                        fixed_count += 1
            
            if fixed_count > 0:
                self.modified = True
                logger.info(f"Se corrigieron {fixed_count} enlaces ambiguos")
                return True
            else:
                logger.warning("No se pudieron corregir los enlaces ambiguos")
                return False
                
        except Exception as e:
            logger.error(f"Error al corregir enlaces ambiguos: {str(e)}")
            return False
    
    def _get_content_near_annotation(self, annot_info: Dict) -> Dict:
        """
        Obtiene contenido cercano a una anotación.
        
        Args:
            annot_info: Información de la anotación
            
        Returns:
            Dict: Información sobre el contenido cercano
        """
        try:
            page_num = annot_info['page']
            rect = annot_info['rect']
            
            # Método 1: Usar pdf_loader para obtener el contenido visual
            if hasattr(self.pdf_loader, "get_visual_content"):
                visual_content = self.pdf_loader.get_visual_content(page_num)
                
                # Filtrar elementos de texto que se superponen con el rectángulo de la anotación
                overlapping_content = []
                for item in visual_content:
                    if item['type'] == 'text':
                        item_rect = item['rect']
                        if self._rects_overlap(rect, item_rect):
                            overlapping_content.append(item)
                
                # Si hay contenido superpuesto, combinar el texto
                if overlapping_content:
                    text = " ".join(item['text'] for item in overlapping_content)
                    
                    # Buscar el elemento de estructura que contiene este texto
                    parent_element = None
                    if overlapping_content and 'mcid' in overlapping_content[0]:
                        parent_element = self._find_element_by_mcid(page_num, overlapping_content[0]['mcid'])
                    
                    return {
                        'text': text,
                        'elements': overlapping_content,
                        'parent_element': parent_element
                    }
            
            # Método 2: Usar PyMuPDF para extraer texto directamente
            if self.pdf_loader.doc:
                page = self.pdf_loader.doc[page_num]
                
                # Extraer texto en el área de la anotación
                text = page.get_text("text", clip=rect)
                if text:
                    # Buscar un elemento de estructura cercano para usar como padre
                    parent_element = self._find_nearest_structure_element(page_num, rect)
                    
                    return {
                        'text': text.strip(),
                        'parent_element': parent_element
                    }
            
            return {}
            
        except Exception as e:
            logger.error(f"Error al obtener contenido cercano a la anotación: {str(e)}")
            return {}
    
    def _find_element_by_mcid(self, page_num: int, mcid: int) -> Optional[Dict]:
        """
        Encuentra un elemento de estructura por su MCID en una página.
        
        Args:
            page_num: Número de página
            mcid: ID de contenido marcado
            
        Returns:
            Optional[Dict]: Elemento de estructura o None si no se encuentra
        """
        # Buscar en structure_elements_by_mcid si existe en pdf_loader
        if hasattr(self.pdf_loader, 'structure_elements_by_mcid'):
            key = f"{page_num}:{mcid}"
            if key in self.pdf_loader.structure_elements_by_mcid:
                return self.pdf_loader.structure_elements_by_mcid[key]
        
        # Alternativa: buscar a través del Structure Manager
        if self.structure_manager and hasattr(self.structure_manager, 'find_element_by_mcid'):
            return self.structure_manager.find_element_by_mcid(page_num, mcid)
        
        return None
    
    def _find_nearest_structure_element(self, page_num: int, rect) -> Optional[Dict]:
        """
        Encuentra el elemento de estructura más cercano a un rectángulo en una página.
        
        Args:
            page_num: Número de página
            rect: Rectángulo a considerar
            
        Returns:
            Optional[Dict]: Elemento de estructura más cercano
        """
        # Esta función simula la búsqueda del elemento más cercano
        # En una implementación real, se recorrería la estructura buscando
        # el elemento más cercano en la página
        
        # Buscar todos los elementos en la página
        page_elements = self._find_page_structure_elements(page_num)
        
        # Filtrar elementos que contienen texto
        text_elements = [elem for elem in page_elements if self._is_text_element(elem)]
        
        # Si no hay elementos de texto, usar cualquier elemento en la página
        if not text_elements:
            text_elements = page_elements
        
        # Si aún no hay elementos, devolver None
        if not text_elements:
            return None
        
        # Buscar el elemento más cercano al rectángulo
        closest_element = None
        min_distance = float('inf')
        
        for elem in text_elements:
            elem_rect = self._get_element_rect(elem)
            if elem_rect:
                distance = self._rect_distance(rect, elem_rect)
                if distance < min_distance:
                    min_distance = distance
                    closest_element = elem
        
        return closest_element
    
    def _find_page_structure_elements(self, page_num: int) -> List[Dict]:
        """
        Encuentra todos los elementos de estructura en una página.
        
        Args:
            page_num: Número de página
            
        Returns:
            List[Dict]: Lista de elementos en la página
        """
        # Si pdf_loader tiene una función para obtener elementos por página, usarla
        if hasattr(self.pdf_loader, 'get_page_structure_elements'):
            return self.pdf_loader.get_page_structure_elements(page_num)
        
        # Alternativa: recorrer la estructura completa y filtrar por página
        elements = []
        
        def find_elements_in_page(node):
            if isinstance(node, dict):
                node_page = node.get("page")
                if node_page == page_num:
                    elements.append(node)
                
                # Buscar en los hijos
                for child in node.get("children", []):
                    find_elements_in_page(child)
            elif isinstance(node, list):
                for item in node:
                    find_elements_in_page(item)
        
        # Iniciar búsqueda desde la raíz
        if self.pdf_loader.structure_tree:
            find_elements_in_page(self.pdf_loader.structure_tree)
        
        return elements
    
    def _is_text_element(self, element: Dict) -> bool:
        """
        Determina si un elemento contiene texto.
        
        Args:
            element: Elemento a comprobar
            
        Returns:
            bool: True si el elemento contiene texto
        """
        # Comprobar si tiene texto directamente
        if element.get("text", "").strip():
            return True
        
        # Comprobar tipos comunes de elementos de texto
        element_type = element.get("type", "")
        text_types = ["P", "H1", "H2", "H3", "H4", "H5", "H6", "Span", "Link", "TD", "TH"]
        
        if element_type in text_types:
            return True
        
        return False
    
    def _get_element_rect(self, element: Dict) -> Optional[List]:
        """
        Obtiene el rectángulo de un elemento.
        
        Args:
            element: Elemento a comprobar
            
        Returns:
            Optional[List]: Rectángulo [x1, y1, x2, y2] o None
        """
        # Si el elemento tiene rect directamente
        if "rect" in element:
            return element["rect"]
        
        # Si tiene BBox como atributo
        bbox = self._get_element_attribute(element, "BBox")
        if bbox:
            try:
                # Convertir BBox a lista
                if isinstance(bbox, str):
                    return [float(x) for x in bbox.replace("[", "").replace("]", "").split(",")]
                elif hasattr(bbox, "__iter__"):
                    return list(bbox)
            except:
                pass
        
        return None
    
    def _get_element_attribute(self, element: Dict, attribute: str) -> Optional[str]:
        """
        Obtiene el valor de un atributo de un elemento.
        
        Args:
            element: Elemento de estructura
            attribute: Nombre del atributo
            
        Returns:
            Optional[str]: Valor del atributo o None si no existe
        """
        # Comprobar si el atributo existe directamente en el elemento
        if attribute in element:
            return element[attribute]
            
        # Comprobar si existe en el diccionario de atributos
        if "attributes" in element and attribute in element["attributes"]:
            return element["attributes"][attribute]
            
        # Comprobar en el objeto pikepdf si está disponible
        if "element" in element:
            pikepdf_element = element["element"]
            
            # Convertir primera letra a mayúscula para formato pikepdf
            pikepdf_attr = attribute[0].upper() + attribute[1:]
            
            if hasattr(pikepdf_element, pikepdf_attr):
                value = getattr(pikepdf_element, pikepdf_attr)
                return str(value)
                
            # Comprobar formatos alternativos
            alt_names = [f"/{pikepdf_attr}", attribute, attribute.upper()]
            for name in alt_names:
                if hasattr(pikepdf_element, "__contains__") and name in pikepdf_element:
                    value = pikepdf_element[name]
                    return str(value)
        
        return None
    
    def _rects_overlap(self, rect1, rect2) -> bool:
        """
        Determina si dos rectángulos se superponen.
        
        Args:
            rect1: Primer rectángulo [x1, y1, x2, y2]
            rect2: Segundo rectángulo [x1, y1, x2, y2]
            
        Returns:
            bool: True si los rectángulos se superponen
        """
        # Convertir a listas si son otros tipos (como fitz.Rect)
        rect1_list = list(rect1)
        rect2_list = list(rect2)
        
        # Comprobar superposición
        return not (rect1_list[2] < rect2_list[0] or  # r1 está a la izquierda de r2
                   rect1_list[0] > rect2_list[2] or   # r1 está a la derecha de r2
                   rect1_list[3] < rect2_list[1] or   # r1 está arriba de r2
                   rect1_list[1] > rect2_list[3])     # r1 está debajo de r2
    
    def _rect_distance(self, rect1, rect2) -> float:
        """
        Calcula la distancia entre dos rectángulos.
        
        Args:
            rect1: Primer rectángulo [x1, y1, x2, y2]
            rect2: Segundo rectángulo [x1, y1, x2, y2]
            
        Returns:
            float: Distancia entre los rectángulos (0 si se superponen)
        """
        # Convertir a listas si son otros tipos
        rect1_list = list(rect1)
        rect2_list = list(rect2)
        
        # Si se superponen, la distancia es 0
        if self._rects_overlap(rect1_list, rect2_list):
            return 0
        
        # Calcular distancia en x
        dx = 0
        if rect1_list[2] < rect2_list[0]:  # r1 está a la izquierda de r2
            dx = rect2_list[0] - rect1_list[2]
        elif rect1_list[0] > rect2_list[2]:  # r1 está a la derecha de r2
            dx = rect1_list[0] - rect2_list[2]
        
        # Calcular distancia en y
        dy = 0
        if rect1_list[3] < rect2_list[1]:  # r1 está arriba de r2
            dy = rect2_list[1] - rect1_list[3]
        elif rect1_list[1] > rect2_list[3]:  # r1 está debajo de r2
            dy = rect1_list[1] - rect2_list[3]
        
        # Distancia euclidiana
        return (dx**2 + dy**2)**0.5
    
    def _detect_ambiguous_links(self, link_elements: List[Dict]) -> List[List[Dict]]:
        """
        Detecta enlaces ambiguos (mismo texto pero diferentes destinos).
        
        Args:
            link_elements: Lista de elementos <Link> en la estructura
            
        Returns:
            List[List[Dict]]: Grupos de enlaces ambiguos
        """
        # Agrupar enlaces por texto
        links_by_text = defaultdict(list)
        
        for link in link_elements:
            link_text = link.get("text", "").strip()
            if not link_text:
                continue
                
            links_by_text[link_text].append(link)
        
        # Identificar grupos con el mismo texto pero diferentes destinos
        ambiguous_groups = []
        
        for text, links in links_by_text.items():
            if len(links) <= 1:
                continue
                
            # Obtener destinos únicos
            destinations = set()
            for link in links:
                # Obtener el destino del enlace
                objr_elements = self._find_objr_elements(link)
                for objr in objr_elements:
                    if "element" in objr and hasattr(objr["element"], "A"):
                        action = objr["element"].A
                        if action.get("S") == Name.URI:
                            destinations.add(str(action.get("URI", "")))
                        elif action.get("S") in [Name.GoTo, Name.GoToR]:
                            destinations.add(str(action.get("D", "")))
            
            # Si hay más de un destino, es un grupo ambiguo
            if len(destinations) > 1:
                ambiguous_groups.append(links)
        
        return ambiguous_groups
    
    def _is_same_annotation(self, objr, annot) -> bool:
        """
        Determina si un OBJR se refiere a una anotación específica.
        
        Args:
            objr: Elemento OBJR
            annot: Anotación a comparar
            
        Returns:
            bool: True si el OBJR se refiere a la anotación
        """
        # Identificar la anotación del OBJR
        if "element" in objr and hasattr(objr["element"], "Obj"):
            # Comparar con el xref de la anotación si está disponible
            if hasattr(annot, "xref"):
                return objr["element"].Obj.objgen[0] == annot.xref
        
        # Si hay un objid explícito en el OBJR
        if hasattr(objr, "get") and objr.get("objid") == id(annot):
            return True
            
        return False

def fix_links_in_document(pdf_loader, pdf_writer) -> Tuple[bool, List[Dict]]:
    """
    Corrige todos los enlaces y anotaciones en un documento.
    
    Esta es la función principal que sería llamada desde la interfaz de usuario.
    
    Args:
        pdf_loader: Instancia de PDFLoader con el documento cargado
        pdf_writer: Instancia de PDFWriter para aplicar cambios
        
    Returns:
        Tuple[bool, List[Dict]]: (Éxito, Lista de problemas corregidos)
    """
    if not pdf_loader or not pdf_writer:
        logger.error("No se proporcionaron pdf_loader y pdf_writer válidos")
        return False, []
    
    fixer = LinkFixer(pdf_writer)
    
    # Obtener la estructura del documento
    structure_tree = pdf_loader.structure_tree
    if not structure_tree:
        logger.warning("El documento no tiene estructura lógica")
        return False, []
    
    # Corregir enlaces y anotaciones
    success = fixer.fix_all_links(structure_tree, pdf_loader)
    
    # Devolver información sobre las correcciones realizadas
    corrections = []
    if success:
        corrections = [
            {
                "type": "links_annotations",
                "description": "Se corrigieron enlaces y anotaciones para cumplir con PDF/UA",
                "details": f"Se añadieron {fixer.stats['fixed_structure']} estructuras <Link> faltantes, " +
                          f"se completaron {fixer.stats['fixed_contents']} atributos Contents, " +
                          f"se añadieron {fixer.stats['fixed_alt']} textos alternativos y " +
                          f"se mejoraron {fixer.stats['fixed_ambiguous']} enlaces ambiguos."
            }
        ]
    
    return success, corrections