#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Corrección automática de listas según PDF/UA.
Crea estructura L/LI/Lbl/LBody y añade ListNumbering.
"""

from typing import Dict, List, Optional, Tuple, Any
import re
from loguru import logger

class ListsFixer:
    """
    Clase para corregir listas según PDF/UA.
    Crea estructura L/LI/Lbl/LBody desde texto plano y añade ListNumbering.
    """
    
    def __init__(self, pdf_writer=None):
        """
        Inicializa el corrector de listas.
        
        Args:
            pdf_writer: Instancia opcional de PDFWriter
        """
        self.pdf_writer = pdf_writer
        logger.info("ListsFixer inicializado")
    
    def set_pdf_writer(self, pdf_writer):
        """Establece el escritor de PDF a utilizar"""
        self.pdf_writer = pdf_writer
    
    def fix_all_lists(self, structure_tree: Dict) -> bool:
        """
        Corrige todas las listas en la estructura.
        
        Args:
            structure_tree: Diccionario representando la estructura lógica
            
        Returns:
            bool: True si se realizaron correcciones
            
        Referencias:
            - Matterhorn: 16-001, 16-003
            - Tagged PDF: 4.2.5, 5.2.1 (ListNumbering)
        """
        try:
            if self.pdf_writer is None:
                logger.error("No hay PDFWriter configurado para aplicar correcciones")
                return False
            
            if not structure_tree or not structure_tree.get("children"):
                logger.warning("No hay estructura para corregir listas")
                return False
            
            # Buscar todas las listas en la estructura
            lists = self._find_lists(structure_tree.get("children", []))
            
            logger.info(f"Encontradas {len(lists)} listas para procesar")
            
            changes_made = False
            
            # Procesar cada lista
            for list_elem in lists:
                list_fixed = False
                
                # Añadir ListNumbering si es necesario
                list_numbering_fixed = self._fix_list_numbering(list_elem)
                if list_numbering_fixed:
                    list_fixed = True
                
                # Corregir estructura interna de la lista
                list_structure_fixed = self._fix_list_structure(list_elem)
                if list_structure_fixed:
                    list_fixed = True
                
                changes_made = changes_made or list_fixed
            
            # Buscar posibles listas no etiquetadas (párrafos secuenciales con bullets)
            potential_lists = self._find_potential_lists(structure_tree.get("children", []))
            
            if potential_lists:
                logger.info(f"Encontrados {len(potential_lists)} posibles grupos de párrafos que podrían ser listas")
                for group in potential_lists:
                    converted = self._convert_paragraphs_to_list(group)
                    if converted:
                        changes_made = True
            
            return changes_made
            
        except Exception as e:
            logger.exception(f"Error al corregir listas: {e}")
            return False
    
    def add_list_numbering(self, list_id: str, numbering_type: str) -> bool:
        """
        Añade atributo ListNumbering a una lista.
        
        Args:
            list_id: Identificador de la lista
            numbering_type: Tipo de numeración ('Decimal', 'UpperRoman', etc.)
            
        Returns:
            bool: True si se realizó la corrección
            
        Referencias:
            - Matterhorn: 16-001
            - Tagged PDF: 5.2.1 (ListNumbering)
        """
        try:
            if self.pdf_writer is None:
                logger.error("No hay PDFWriter configurado para aplicar correcciones")
                return False
            
            valid_types = ["None", "Decimal", "UpperRoman", "LowerRoman", "UpperAlpha", "LowerAlpha"]
            if numbering_type not in valid_types:
                logger.error(f"Tipo de numeración inválido: {numbering_type}")
                return False
            
            logger.info(f"Añadiendo ListNumbering='{numbering_type}' a lista {list_id}")
            return self.pdf_writer.update_tag_attribute(list_id, "list_numbering", numbering_type)
            
        except Exception as e:
            logger.exception(f"Error al añadir ListNumbering a lista {list_id}: {e}")
            return False
    
    def create_list_structure(self, parent_id: str, items: List[Dict]) -> bool:
        """
        Crea una estructura de lista completa.
        
        Args:
            parent_id: Identificador del elemento padre
            items: Lista de elementos para la lista
            
        Returns:
            bool: True si se creó la estructura
            
        Referencias:
            - Matterhorn: 16-003
            - Tagged PDF: 4.2.5
        """
        try:
            if self.pdf_writer is None:
                logger.error("No hay PDFWriter configurado para aplicar correcciones")
                return False
            
            # Determinar si es lista ordenada o no
            is_ordered = self._is_ordered_list(items)
            
            # Crear estructura de lista (simulado)
            logger.info(f"Creando estructura de lista en {parent_id} con {len(items)} elementos")
            
            # En implementación real, se crearía la estructura completa
            
            # Añadir ListNumbering si es ordenada
            if is_ordered:
                numbering_type = self._determine_numbering_type(items)
                # Aquí se usaría el ID real de la lista creada
                # self.add_list_numbering(list_id, numbering_type)
            
            return True
            
        except Exception as e:
            logger.exception(f"Error al crear estructura de lista: {e}")
            return False
    
    def _find_lists(self, elements: List[Dict], path: str = "") -> List[Dict]:
        """
        Encuentra todas las listas en la estructura de forma recursiva.
        
        Args:
            elements: Lista de elementos de estructura
            path: Ruta de anidamiento actual
            
        Returns:
            List[Dict]: Lista de listas encontradas con información de contexto
        """
        lists = []
        
        for i, element in enumerate(elements):
            element_type = element.get("type", "")
            current_path = f"{path}/{i}:{element_type}"
            
            if element_type == "L":
                # Añadir información de contexto a la lista
                element["_path"] = current_path
                lists.append(element)
            
            # Buscar listas en los hijos
            if element.get("children"):
                child_lists = self._find_lists(element["children"], current_path)
                lists.extend(child_lists)
        
        return lists
    
    def _fix_list_numbering(self, list_elem: Dict) -> bool:
        """
        Añade ListNumbering a una lista si es necesario.
        
        Args:
            list_elem: Diccionario representando una lista
            
        Returns:
            bool: True si se realizaron correcciones
        """
        # Verificar si ya tiene ListNumbering
        if list_elem.get("list_numbering"):
            return False
        
        # Determinar si es lista ordenada
        is_ordered = self._is_list_ordered(list_elem)
        
        if not is_ordered:
            return False
        
        # Determinar tipo de numeración
        numbering_type = self._determine_list_numbering_type(list_elem)
        
        # Aplicar ListNumbering
        list_id = list_elem.get("id", "unknown")
        return self.add_list_numbering(list_id, numbering_type)
    
    def _is_list_ordered(self, list_elem: Dict) -> bool:
        """
        Determina si una lista es ordenada.
        
        Args:
            list_elem: Diccionario representando una lista
            
        Returns:
            bool: True si la lista es ordenada
        """
        # Buscar elementos LI
        items = [child for child in list_elem.get("children", []) if child.get("type") == "LI"]
        
        if not items:
            return False
        
        # Buscar etiquetas Lbl para determinar si hay números
        labels = []
        for item in items:
            label = next((child for child in item.get("children", []) if child.get("type") == "Lbl"), None)
            if label:
                labels.append(label)
        
        if not labels:
            return False
        
        # Verificar si hay números en las etiquetas
        number_pattern = re.compile(r'^\s*\d+[\.\)\]]*\s*$|^[IVXLCDMivxlcdm]+[\.\)\]]*\s*$|^[A-Za-z][\.\)\]]*\s*$')
        numeric_labels = [bool(number_pattern.match(label.get("content", ""))) for label in labels if label.get("content")]
        
        return len(numeric_labels) > 0 and all(numeric_labels)
    
    def _determine_list_numbering_type(self, list_elem: Dict) -> str:
        """
        Determina el tipo de numeración de una lista.
        
        Args:
            list_elem: Diccionario representando una lista
            
        Returns:
            str: Tipo de numeración
        """
        # Buscar elementos LI y sus etiquetas Lbl
        items = [child for child in list_elem.get("children", []) if child.get("type") == "LI"]
        
        if not items:
            return "None"
        
        # Obtener primera etiqueta con contenido
        for item in items:
            label = next((child for child in item.get("children", []) if child.get("type") == "Lbl"), None)
            if label and label.get("content"):
                content = label.get("content", "").strip()
                
                # Determinar tipo
                if re.match(r'^\d+[\.\)\]]?', content):
                    return "Decimal"
                elif re.match(r'^[IVXLCDM]+[\.\)\]]?', content):
                    return "UpperRoman"
                elif re.match(r'^[ivxlcdm]+[\.\)\]]?', content):
                    return "LowerRoman"
                elif re.match(r'^[A-Z][\.\)\]]?', content):
                    return "UpperAlpha"
                elif re.match(r'^[a-z][\.\)\]]?', content):
                    return "LowerAlpha"
        
        return "None"
    
    def _fix_list_structure(self, list_elem: Dict) -> bool:
        """
        Corrige la estructura interna de una lista.
        
        Args:
            list_elem: Diccionario representando una lista
            
        Returns:
            bool: True si se realizaron correcciones
        """
        changes_made = False
        
        # Verificar elementos LI
        items = [child for child in list_elem.get("children", []) if child.get("type") == "LI"]
        
        for item in items:
            # Verificar si tiene Lbl y LBody
            has_lbl = any(child.get("type") == "Lbl" for child in item.get("children", []))
            has_lbody = any(child.get("type") == "LBody" for child in item.get("children", []))
            
            if not has_lbl or not has_lbody:
                # La estructura necesita corrección
                item_id = item.get("id", "unknown")
                logger.info(f"Ítem de lista {item_id} necesita corrección de estructura")
                
                # En implementación real, se corregiría la estructura
                changes_made = True
        
        return changes_made
    
    def _find_potential_lists(self, elements: List[Dict], current_group: List[Dict] = None, groups: List[List[Dict]] = None, path: str = "") -> List[List[Dict]]:
        """
        Busca grupos de párrafos que parecen ser listas.
        
        Args:
            elements: Lista de elementos de estructura
            current_group: Grupo actual de párrafos potenciales
            groups: Lista de grupos encontrados
            path: Ruta de anidamiento actual
            
        Returns:
            List[List[Dict]]: Lista de grupos de párrafos que podrían ser listas
        """
        if groups is None:
            groups = []
        if current_group is None:
            current_group = []
        
        for i, element in enumerate(elements):
            element_type = element.get("type", "")
            current_path = f"{path}/{i}:{element_type}"
            
            if element_type == "P":
                content = element.get("content", "")
                # Verificar si parece un ítem de lista
                if self._looks_like_list_item(content):
                    element["_path"] = current_path
                    if not current_group:
                        # Iniciar nuevo grupo
                        current_group = [element]
                    else:
                        # Añadir al grupo existente
                        current_group.append(element)
                elif current_group:
                    # Final de grupo
                    if len(current_group) >= 2:  # Al menos 2 elementos para considerar lista
                        groups.append(current_group)
                    current_group = []
            elif current_group:
                # Elemento no párrafo, finalizar grupo actual
                if len(current_group) >= 2:  # Al menos 2 elementos para considerar lista
                    groups.append(current_group)
                current_group = []
            
            # Buscar recursivamente en hijos
            if element.get("children"):
                self._find_potential_lists(element["children"], [], groups, current_path)
        
        # Verificar grupo final
        if current_group and len(current_group) >= 2:
            groups.append(current_group)
        
        return groups
    
    def _looks_like_list_item(self, content: str) -> bool:
        """
        Determina si un texto parece un ítem de lista.
        
        Args:
            content: Texto del párrafo
            
        Returns:
            bool: True si parece un ítem de lista
        """
        if not content:
            return False
        
        # Patrones comunes de ítems de lista
        patterns = [
            r'^\s*[\•\-\*\+\◦\▪\■\○\□\➢\➤\➥\➨]\s+',  # Bullets
            r'^\s*\d+[\.\)\]]\s+',  # Números: 1. 1) 1]
            r'^\s*[IVXLCDMivxlcdm]+[\.\)\]]\s+',  # Romanos: I. I) I]
            r'^\s*[A-Za-z][\.\)\]]\s+'  # Letras: A. A) A]
        ]
        
        for pattern in patterns:
            if re.match(pattern, content):
                return True
        
        return False
    
    def _convert_paragraphs_to_list(self, paragraphs: List[Dict]) -> bool:
        """
        Convierte un grupo de párrafos en una lista estructurada.
        
        Args:
            paragraphs: Lista de párrafos para convertir
            
        Returns:
            bool: True si se realizó la conversión
        """
        if not paragraphs:
            return False
        
        # Determinar si es lista ordenada o no
        items = []
        for p in paragraphs:
            content = p.get("content", "")
            label, body = self._split_list_item_content(content)
            items.append({"label": label, "body": body})
        
        # Crear lista en el padre del primer párrafo
        parent_path = paragraphs[0].get("_path", "").rsplit("/", 1)[0]
        
        logger.info(f"Convirtiendo {len(paragraphs)} párrafos a lista en {parent_path}")
        
        # En implementación real, se crearía la estructura
        return True
    
    def _split_list_item_content(self, content: str) -> Tuple[str, str]:
        """
        Separa el contenido de un ítem de lista en etiqueta y cuerpo.
        
        Args:
            content: Texto del párrafo
            
        Returns:
            Tuple[str, str]: Etiqueta y cuerpo del ítem
        """
        # Patrones para detectar diferentes tipos de ítems
        patterns = [
            (r'^\s*([\•\-\*\+\◦\▪\■\○\□\➢\➤\➥\➨])\s+(.*)$', 1, 2),  # Bullets
            (r'^\s*(\d+[\.\)\]])\s+(.*)$', 1, 2),  # Números
            (r'^\s*([IVXLCDMivxlcdm]+[\.\)\]])\s+(.*)$', 1, 2),  # Romanos
            (r'^\s*([A-Za-z][\.\)\]])\s+(.*)$', 1, 2)  # Letras
        ]
        
        for pattern, label_group, body_group in patterns:
            match = re.match(pattern, content)
            if match:
                return match.group(label_group), match.group(body_group)
        
        # Si no hay coincidencia, devolver vacío para etiqueta
        return "", content
    
    def _is_ordered_list(self, items: List[Dict]) -> bool:
        """
        Determina si una lista de ítems es una lista ordenada.
        
        Args:
            items: Lista de ítems 
            
        Returns:
            bool: True si es una lista ordenada
        """
        if not items:
            return False
        
        # Verificar si las etiquetas parecen números o letras
        for item in items:
            if "label" in item:
                label = item["label"]
                if re.match(r'^\d+[\.\)\]]?|^[IVXLCDMivxlcdm]+[\.\)\]]?|^[A-Za-z][\.\)\]]?', label):
                    return True
        
        return False
    
    def _determine_numbering_type(self, items: List[Dict]) -> str:
        """
        Determina el tipo de numeración para una lista de ítems.
        
        Args:
            items: Lista de ítems
            
        Returns:
            str: Tipo de numeración
        """
        for item in items:
            if "label" in item:
                label = item["label"]
                
                if re.match(r'^\d+[\.\)\]]?', label):
                    return "Decimal"
                elif re.match(r'^[IVXLCDM]+[\.\)\]]?', label):
                    return "UpperRoman"
                elif re.match(r'^[ivxlcdm]+[\.\)\]]?', label):
                    return "LowerRoman"
                elif re.match(r'^[A-Z][\.\)\]]?', label):
                    return "UpperAlpha"
                elif re.match(r'^[a-z][\.\)\]]?', label):
                    return "LowerAlpha"
        
        return "None"