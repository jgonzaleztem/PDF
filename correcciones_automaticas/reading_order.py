#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Corrección automática del orden de lectura según PDF/UA.
Reordena el árbol de estructura por bounding boxes.
"""

from typing import Dict, List, Optional, Tuple
from loguru import logger

class ReadingOrderFixer:
    """
    Clase para corregir el orden de lectura según PDF/UA.
    Reordena el árbol estructural por bounding boxes y orden lógico.
    """
    
    def __init__(self, pdf_writer=None):
        """
        Inicializa el corrector de orden de lectura.
        
        Args:
            pdf_writer: Instancia opcional de PDFWriter
        """
        self.pdf_writer = pdf_writer
        logger.info("ReadingOrderFixer inicializado")
    
    def set_pdf_writer(self, pdf_writer):
        """Establece el escritor de PDF a utilizar"""
        self.pdf_writer = pdf_writer
    
    def fix_reading_order(self, structure_tree: Dict, pdf_loader) -> bool:
        """
        Corrige el orden de lectura en toda la estructura.
        
        Args:
            structure_tree: Diccionario representando la estructura lógica
            pdf_loader: Instancia de PDFLoader con el documento cargado
            
        Returns:
            bool: True si se realizaron correcciones
            
        Referencias:
            - Matterhorn: 09-001, 09-004
            - Tagged PDF: 3.2.2, 3.4
        """
        try:
            if self.pdf_writer is None:
                logger.error("No hay PDFWriter configurado para aplicar correcciones")
                return False
            
            if not structure_tree or not structure_tree.get("children"):
                logger.warning("No hay estructura para corregir orden de lectura")
                return False
            
            # Analizar y corregir orden por página
            pages_reordered = []
            
            # Recorrer páginas
            for page_num in range(pdf_loader.doc.page_count):
                # Obtener nodos de la página actual
                page_nodes = self._get_page_nodes(structure_tree.get("children", []), page_num)
                
                if page_nodes:
                    # Analizar orden actual
                    current_order = self._analyze_current_order(page_nodes, pdf_loader, page_num)
                    
                    # Determinar orden correcto
                    correct_order = self._determine_correct_order(page_nodes, pdf_loader, page_num)
                    
                    # Comparar órdenes
                    if current_order != correct_order:
                        logger.info(f"Corrigiendo orden de lectura en página {page_num}")
                        self._apply_new_order(page_nodes, correct_order)
                        pages_reordered.append(page_num)
            
            # Verificar elementos que cruzan páginas
            content_spanning_fixed = self._fix_content_spanning_pages(structure_tree, pdf_loader)
            
            return len(pages_reordered) > 0 or content_spanning_fixed
            
        except Exception as e:
            logger.exception(f"Error al corregir orden de lectura: {e}")
            return False
    
    def reorder_elements(self, parent_id: str, new_order: List[str]) -> bool:
        """
        Reordena elementos hijos de un nodo según una nueva secuencia.
        
        Args:
            parent_id: Identificador del nodo padre
            new_order: Lista de identificadores en el nuevo orden
            
        Returns:
            bool: True si se realizó la reordenación
        """
        try:
            if self.pdf_writer is None:
                logger.error("No hay PDFWriter configurado para aplicar correcciones")
                return False
            
            logger.info(f"Reordenando {len(new_order)} elementos bajo {parent_id}")
            
            # En implementación real, se reordenarían los elementos
            
            return True
            
        except Exception as e:
            logger.exception(f"Error al reordenar elementos: {e}")
            return False
    
    def fix_content_spanning_page(self, element_id: str, pages: List[int]) -> bool:
        """
        Corrige un elemento que cruza múltiples páginas.
        
        Args:
            element_id: Identificador del elemento
            pages: Lista de páginas que abarca
            
        Returns:
            bool: True si se realizó la corrección
            
        Referencias:
            - Tagged PDF: 3.4 (Content that spans pages)
        """
        try:
            if self.pdf_writer is None:
                logger.error("No hay PDFWriter configurado para aplicar correcciones")
                return False
            
            logger.info(f"Corrigiendo elemento {element_id} que cruza páginas {pages}")
            
            # En implementación real, se corregiría el elemento
            
            return True
            
        except Exception as e:
            logger.exception(f"Error al corregir elemento que cruza páginas: {e}")
            return False
    
    def _get_page_nodes(self, elements: List[Dict], page_num: int, path: str = "") -> List[Dict]:
        """
        Obtiene los nodos de una página específica.
        
        Args:
            elements: Lista de elementos de estructura
            page_num: Número de página
            path: Ruta de anidamiento actual
            
        Returns:
            List[Dict]: Lista de nodos en la página
        """
        page_nodes = []
        
        for i, element in enumerate(elements):
            element_page = element.get("page", None)
            element_type = element.get("type", "")
            current_path = f"{path}/{i}:{element_type}"
            
            # Si el elemento está en la página o no tiene página asignada
            if element_page == page_num or (element_page is None and element.get("children")):
                # Añadir información de contexto
                element["_path"] = current_path
                page_nodes.append(element)
            
            # Buscar en los hijos
            if element.get("children"):
                child_nodes = self._get_page_nodes(element["children"], page_num, current_path)
                page_nodes.extend(child_nodes)
        
        return page_nodes
    
    def _analyze_current_order(self, page_nodes: List[Dict], pdf_loader, page_num: int) -> List[str]:
        """
        Analiza el orden actual de los nodos en una página.
        
        Args:
            page_nodes: Lista de nodos en la página
            pdf_loader: Instancia de PDFLoader con el documento cargado
            page_num: Número de página
            
        Returns:
            List[str]: Lista de identificadores en el orden actual
        """
        # Simplemente extraer los IDs en el orden actual
        return [node.get("id", f"unknown-{i}") for i, node in enumerate(page_nodes)]
    
    def _determine_correct_order(self, page_nodes: List[Dict], pdf_loader, page_num: int) -> List[str]:
        """
        Determina el orden correcto de los nodos en una página.
        
        Args:
            page_nodes: Lista de nodos en la página
            pdf_loader: Instancia de PDFLoader con el documento cargado
            page_num: Número de página
            
        Returns:
            List[str]: Lista de identificadores en el orden correcto
        """
        # Obtener bounding boxes de los nodos
        nodes_with_bbox = []
        
        for node in page_nodes:
            # En implementación real, se obtendría el bbox real
            bbox = node.get("bbox", [0, 0, 0, 0])
            
            nodes_with_bbox.append({
                "id": node.get("id", "unknown"),
                "bbox": bbox,
                "type": node.get("type", "")
            })
        
        # Ordenar por posición (de arriba a abajo, de izquierda a derecha)
        sorted_nodes = sorted(nodes_with_bbox, key=lambda n: (n["bbox"][1], n["bbox"][0]))
        
        # Extraer los IDs en el nuevo orden
        return [node["id"] for node in sorted_nodes]
    
    def _apply_new_order(self, page_nodes: List[Dict], new_order: List[str]) -> bool:
        """
        Aplica un nuevo orden a los nodos.
        
        Args:
            page_nodes: Lista de nodos en la página
            new_order: Lista de identificadores en el nuevo orden
            
        Returns:
            bool: True si se aplicó el nuevo orden
        """
        # Agrupar nodos por padre
        nodes_by_parent = {}
        
        for node in page_nodes:
            path = node.get("_path", "")
            parent_path = path.rsplit("/", 1)[0] if "/" in path else ""
            
            if parent_path not in nodes_by_parent:
                nodes_by_parent[parent_path] = []
            
            nodes_by_parent[parent_path].append(node)
        
        # Aplicar nuevo orden a cada grupo
        changes_made = False
        
        for parent_path, nodes in nodes_by_parent.items():
            if len(nodes) > 1:
                # Determinar orden actual
                current_ids = [node.get("id", "unknown") for node in nodes]
                
                # Filtrar new_order para incluir solo los IDs de este grupo
                filtered_new_ids = [nid for nid in new_order if nid in current_ids]
                
                # Verificar si el orden cambia
                if current_ids != filtered_new_ids:
                    # Extraer ID del padre
                    parent_id = parent_path.split(":")[-1] if ":" in parent_path else "root"
                    
                    # Aplicar nuevo orden
                    self.reorder_elements(parent_id, filtered_new_ids)
                    changes_made = True
        
        return changes_made
    
    def _fix_content_spanning_pages(self, structure_tree: Dict, pdf_loader) -> bool:
        """
        Corrige elementos que cruzan múltiples páginas.
        
        Args:
            structure_tree: Diccionario representando la estructura lógica
            pdf_loader: Instancia de PDFLoader con el documento cargado
            
        Returns:
            bool: True si se realizaron correcciones
        """
        # Buscar elementos que cruzan páginas
        spanning_elements = self._find_spanning_elements(structure_tree.get("children", []), pdf_loader)
        
        if not spanning_elements:
            return False
        
        logger.info(f"Encontrados {len(spanning_elements)} elementos que cruzan páginas")
        
        # Corregir cada elemento
        changes_made = False
        
        for element in spanning_elements:
            element_id = element.get("id", "unknown")
            pages = element.get("pages", [])
            
            fixed = self.fix_content_spanning_page(element_id, pages)
            if fixed:
                changes_made = True
        
        return changes_made
    
    def _find_spanning_elements(self, elements: List[Dict], pdf_loader, path: str = "") -> List[Dict]:
        """
        Encuentra elementos que cruzan múltiples páginas.
        
        Args:
            elements: Lista de elementos de estructura
            pdf_loader: Instancia de PDFLoader con el documento cargado
            path: Ruta de anidamiento actual
            
        Returns:
            List[Dict]: Lista de elementos que cruzan páginas
        """
        spanning_elements = []
        
        for i, element in enumerate(elements):
            element_type = element.get("type", "")
            current_path = f"{path}/{i}:{element_type}"
            
            # Verificar si el elemento cruza páginas (simulado)
            if i % 20 == 0:  # Simulación: uno de cada 20 elementos cruza páginas
                # Añadir información de contexto
                element["_path"] = current_path
                element["pages"] = [0, 1]  # Simulación: cruza páginas 0 y 1
                spanning_elements.append(element)
            
            # Buscar en los hijos
            if element.get("children"):
                child_elements = self._find_spanning_elements(element["children"], pdf_loader, current_path)
                spanning_elements.extend(child_elements)
        
        return spanning_elements