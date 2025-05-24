# pdfua_editor/correcciones_automaticas/lists_fixer.py

from loguru import logger
from typing import Dict, List, Optional, Tuple, Any
import re
from collections import defaultdict

class ListsFixer:
    """
    Corrector automático para listas en documentos PDF para cumplir con los estándares PDF/UA.
    
    Responsabilidades:
    - Detectar contenido que debería estructurarse como lista
    - Corregir listas mal formadas (estructura incorrecta)
    - Añadir atributos necesarios (ListNumbering)
    - Gestionar diferentes tipos de listas (numeradas, viñetas, etc.)
    
    Referencias:
    - Matterhorn Protocol: 16-001, 16-002
    - Tagged PDF Best Practice Guide: 4.2.5 <L> (List), <LI> (List Item), <LBody> (List Body)
    - PDF/UA (ISO 14289-1): 7.5 Listas
    """
    
    def __init__(self, pdf_writer=None):
        """
        Inicializa el corrector de listas.
        
        Args:
            pdf_writer: Instancia de PDFWriter para aplicar cambios
        """
        self.pdf_writer = pdf_writer
        
        # Patrones para detectar elementos de lista
        self.bullet_patterns = [
            r'^\s*[•⦿⦾⚫◦◆◊▪▫►▻▶▷◉○⚬●■□]+\s',  # Viñetas comunes
            r'^\s*[-–—]\s',                     # Guiones como viñetas
            r'^\s*[*]\s'                        # Asteriscos como viñetas
        ]
        
        self.numbered_patterns = [
            r'^\s*(\d+)[\.\)]\s',                # Números seguidos de punto o paréntesis
            r'^\s*[a-zA-Z][\.\)]\s',             # Letras seguidas de punto o paréntesis
            r'^\s*[ivxlcdmIVXLCDM]+[\.\)]\s',    # Números romanos seguidos de punto o paréntesis
        ]
        
        # Mapeo de estilos de numeración a valores de ListNumbering
        self.list_numbering_map = {
            'decimal': 'Decimal',
            'lower-alpha': 'LowerAlpha',
            'upper-alpha': 'UpperAlpha',
            'lower-roman': 'LowerRoman',
            'upper-roman': 'UpperRoman',
            'none': 'None'
        }
        
        logger.info("ListsFixer inicializado")
    
    def set_pdf_writer(self, pdf_writer):
        """
        Establece la referencia al escritor de PDF.
        
        Args:
            pdf_writer: Instancia de PDFWriter para aplicar cambios
        """
        self.pdf_writer = pdf_writer
        
    def fix_all_lists(self, structure_tree: Dict) -> bool:
        """
        Corrige todos los problemas de listas en la estructura del documento.
        
        Args:
            structure_tree: Diccionario representando la estructura lógica del documento
            
        Returns:
            bool: True si se realizaron correcciones, False si no fue necesario
        """
        if not structure_tree or not structure_tree.get("children"):
            logger.warning("No hay estructura para corregir listas")
            return False
            
        # Contador de cambios realizados
        changes_made = 0
        
        # 1. Corregir listas ya existentes en el documento
        changes = self._fix_existing_lists(structure_tree.get("children", []))
        changes_made += changes
        
        # 2. Detectar y crear listas nuevas donde sea apropiado
        detected_changes = self._detect_and_create_lists(structure_tree.get("children", []))
        changes_made += detected_changes
        
        logger.info(f"Corrección de listas completada: {changes_made} cambios realizados")
        return changes_made > 0
    
    def _fix_existing_lists(self, elements: List[Dict], parent_path: str = "") -> int:
        """
        Corrige las listas existentes en la estructura.
        
        Args:
            elements: Lista de elementos de estructura
            parent_path: Ruta de anidamiento actual para rastreo
            
        Returns:
            int: Número de correcciones realizadas
        """
        changes_made = 0
        
        for i, element in enumerate(elements):
            element_type = element.get("type", "")
            current_path = f"{parent_path}/{i}:{element_type}"
            
            # Si es una lista, verificar y corregir su estructura
            if element_type == "L":
                changes = self._fix_list_structure(element, current_path)
                changes_made += changes
                
                # Verificar atributo ListNumbering para listas numeradas
                if self._is_numbered_list(element):
                    if not self._has_list_numbering_attribute(element):
                        changes += self._add_list_numbering_attribute(element)
                        changes_made += 1
            
            # Procesar elementos hijos recursivamente
            if element.get("children"):
                child_changes = self._fix_existing_lists(element["children"], current_path)
                changes_made += child_changes
        
        return changes_made
    
    def _fix_list_structure(self, list_element: Dict, path: str) -> int:
        """
        Corrige la estructura de una lista existente.
        
        Args:
            list_element: Elemento de estructura de tipo L
            path: Ruta de anidamiento para rastreo
            
        Returns:
            int: Número de correcciones realizadas
        """
        changes_made = 0
        children = list_element.get("children", [])
        
        # Si la lista no tiene hijos, no hay nada que corregir
        if not children:
            return 0
            
        # Una lista debe contener elementos LI (excepto posiblemente Caption como primer elemento)
        has_caption = False
        first_child_type = children[0].get("type", "")
        if first_child_type == "Caption":
            has_caption = True
            # La caption está bien, comprobar el resto
            children = children[1:]
            
        # Verificar que todos los elementos restantes son LI
        problematic_indexes = []
        for i, child in enumerate(children):
            if child.get("type") != "LI":
                problematic_indexes.append(i + (1 if has_caption else 0))
        
        # Si hay elementos problemáticos, corregirlos
        if problematic_indexes:
            logger.info(f"Lista en {path} tiene {len(problematic_indexes)} elementos no-LI que serán corregidos")
            for idx in sorted(problematic_indexes, reverse=True):  # Procesar de atrás hacia adelante para evitar cambios en índices
                # Convertir elemento problemático en un LI con estructura adecuada
                problem_element = list_element["children"][idx]
                # Crear nueva estructura
                corrected_element = self._create_list_item_structure(problem_element)
                # Reemplazar el elemento problemático
                list_element["children"][idx] = corrected_element
                changes_made += 1
        
        # Verificar ahora cada LI para asegurar que tiene Lbl y LBody cuando sea necesario
        for i, li in enumerate(children):
            if li.get("type") == "LI":
                li_path = f"{path}/LI[{i}]"
                li_changes = self._fix_list_item_structure(li, li_path)
                changes_made += li_changes
                
        return changes_made
    
    def _fix_list_item_structure(self, li_element: Dict, path: str) -> int:
        """
        Corrige la estructura de un elemento de lista.
        
        Args:
            li_element: Elemento de estructura de tipo LI
            path: Ruta de anidamiento para rastreo
            
        Returns:
            int: Número de correcciones realizadas
        """
        changes_made = 0
        children = li_element.get("children", [])
        
        # Si el LI no tiene hijos, no hay nada que corregir
        if not children:
            return 0
        
        # Un LI debe tener Lbl y LBody como hijos
        has_lbl = any(child.get("type") == "Lbl" for child in children)
        has_lbody = any(child.get("type") == "LBody" for child in children)
        
        # Si no tiene Lbl, intentar detectar y crear uno
        if not has_lbl:
            # Buscar texto que pueda ser una viñeta o número
            if children and "text" in children[0]:
                text = children[0].get("text", "")
                label_match = self._extract_list_label(text)
                if label_match:
                    # Crear etiqueta Lbl con el marcador detectado
                    lbl_element = {
                        "type": "Lbl",
                        "text": label_match[0],
                        "children": []
                    }
                    # Actualizar el texto del primer elemento sin el marcador
                    children[0]["text"] = text[len(label_match[0]):].lstrip()
                    # Insertar Lbl como primer hijo
                    li_element["children"].insert(0, lbl_element)
                    has_lbl = True
                    changes_made += 1
                    logger.debug(f"Creada etiqueta Lbl en {path} con texto '{label_match[0]}'")
        
        # Si no tiene LBody, crear uno para encapsular el contenido
        if not has_lbody:
            # Recolectar todos los elementos que no son Lbl
            non_lbl_items = [child for child in children if child.get("type") != "Lbl"]
            if non_lbl_items:
                # Crear elemento LBody para encapsular contenido
                lbody_element = {
                    "type": "LBody",
                    "children": non_lbl_items
                }
                # Eliminar elementos que ahora están en LBody
                new_children = [child for child in children if child.get("type") == "Lbl"]
                new_children.append(lbody_element)
                li_element["children"] = new_children
                has_lbody = True
                changes_made += 1
                logger.debug(f"Creada etiqueta LBody en {path} para encapsular {len(non_lbl_items)} elementos")
        
        return changes_made
    
    def _detect_and_create_lists(self, elements: List[Dict], parent_path: str = "") -> int:
        """
        Detecta y crea listas donde sea apropiado basado en texto y estructura.
        
        Args:
            elements: Lista de elementos de estructura
            parent_path: Ruta de anidamiento actual para rastreo
            
        Returns:
            int: Número de listas creadas
        """
        changes_made = 0
        
        # Lista de párrafos consecutivos que podrían formar una lista
        potential_list_items = []
        potential_list_type = None
        
        # Examinar secuencias de párrafos que parecen elementos de lista
        i = 0
        while i < len(elements):
            element = elements[i]
            element_type = element.get("type", "")
            current_path = f"{parent_path}/{i}:{element_type}"
            
            # Procesar hijos recursivamente primero
            if element.get("children"):
                child_changes = self._detect_and_create_lists(element["children"], current_path)
                changes_made += child_changes
            
            # Buscar párrafos que parezcan elementos de lista
            if element_type == "P":
                text = element.get("text", "")
                list_type, label = self._identify_list_item_type(text)
                
                if list_type:
                    # Si es el primer elemento o continúa una lista del mismo tipo
                    if not potential_list_items or potential_list_type == list_type:
                        potential_list_items.append((i, element, list_type, label))
                        potential_list_type = list_type
                    else:
                        # Diferentes tipos, procesar la lista acumulada y empezar una nueva
                        if potential_list_items:
                            changes = self._convert_paragraphs_to_list(elements, potential_list_items, potential_list_type)
                            changes_made += changes
                            # Recalcular índices después de modificaciones
                            i = potential_list_items[0][0]  # Volver al inicio de la lista convertida
                            # Reiniciar para nueva lista
                            potential_list_items = [(i, element, list_type, label)]
                            potential_list_type = list_type
                else:
                    # No es un elemento de lista, procesar la lista acumulada si existe
                    if potential_list_items:
                        changes = self._convert_paragraphs_to_list(elements, potential_list_items, potential_list_type)
                        changes_made += changes
                        # Recalcular índices después de modificaciones
                        i = potential_list_items[0][0]  # Volver al inicio de la lista convertida
                        potential_list_items = []
                        potential_list_type = None
            else:
                # No es un párrafo, procesar la lista acumulada si existe
                if potential_list_items:
                    changes = self._convert_paragraphs_to_list(elements, potential_list_items, potential_list_type)
                    changes_made += changes
                    # Recalcular índices después de modificaciones
                    i = potential_list_items[0][0]  # Volver al inicio de la lista convertida
                    potential_list_items = []
                    potential_list_type = None
            
            i += 1
        
        # Procesar cualquier lista restante al final
        if potential_list_items:
            changes = self._convert_paragraphs_to_list(elements, potential_list_items, potential_list_type)
            changes_made += changes
            
        return changes_made
    
    def _identify_list_item_type(self, text: str) -> Tuple[Optional[str], Optional[str]]:
        """
        Identifica si un texto parece un elemento de lista y de qué tipo.
        
        Args:
            text: Texto para analizar
            
        Returns:
            Tuple[Optional[str], Optional[str]]: Tipo de lista y etiqueta, o (None, None) si no es un elemento de lista
        """
        # Verificar patrones de viñetas
        for pattern in self.bullet_patterns:
            match = re.match(pattern, text)
            if match:
                bullet = match.group(0)
                return ("bullet", bullet)
                
        # Verificar patrones numerados
        for pattern in self.numbered_patterns:
            match = re.match(pattern, text)
            if match:
                number = match.group(0)
                # Determinar subtipo de lista numerada
                if re.match(r'^\s*\d+[\.\)]\s', number):
                    return ("numbered-decimal", number)
                elif re.match(r'^\s*[a-z][\.\)]\s', number):
                    return ("numbered-lower-alpha", number)
                elif re.match(r'^\s*[A-Z][\.\)]\s', number):
                    return ("numbered-upper-alpha", number)
                elif re.match(r'^\s*[ivxlcdm]+[\.\)]\s', number):
                    return ("numbered-lower-roman", number)
                elif re.match(r'^\s*[IVXLCDM]+[\.\)]\s', number):
                    return ("numbered-upper-roman", number)
                else:
                    return ("numbered-other", number)
        
        return (None, None)
    
    def _extract_list_label(self, text: str) -> Optional[List[str]]:
        """
        Extrae la etiqueta de un texto que parece un elemento de lista.
        
        Args:
            text: Texto para analizar
            
        Returns:
            Optional[List[str]]: Grupos capturados o None si no hay coincidencia
        """
        # Verificar patrones de viñetas
        for pattern in self.bullet_patterns:
            match = re.match(pattern, text)
            if match:
                return match.groups() if match.groups() else [match.group(0)]
                
        # Verificar patrones numerados
        for pattern in self.numbered_patterns:
            match = re.match(pattern, text)
            if match:
                return match.groups() if match.groups() else [match.group(0)]
                
        return None
    
    def _convert_paragraphs_to_list(self, parent_elements: List[Dict], list_items: List[Tuple], list_type: str) -> int:
        """
        Convierte una secuencia de párrafos en una estructura de lista.
        
        Args:
            parent_elements: Lista de elementos donde reemplazar párrafos por lista
            list_items: Lista de tuplas (índice, elemento, tipo_lista, etiqueta)
            list_type: Tipo de lista para determinar atributos
            
        Returns:
            int: 1 si se realizó la conversión, 0 si no
        """
        if not list_items or len(list_items) < 2:
            # Solo consideramos listas de al menos dos elementos
            return 0
            
        # Extraer índices y elementos
        indices = [item[0] for item in list_items]
        paragraphs = [item[1] for item in list_items]
        labels = [item[3] for item in list_items]
        
        # Crear estructura de lista
        list_element = {
            "type": "L",
            "children": []
        }
        
        # Determinar si necesita atributo ListNumbering
        if list_type.startswith("numbered-"):
            numbering_type = list_type.split("-")[1]
            if numbering_type in self.list_numbering_map:
                list_element["attributes"] = {
                    "ListNumbering": self.list_numbering_map[numbering_type]
                }
        
        # Crear elementos LI para cada párrafo
        for paragraph, label in zip(paragraphs, labels):
            text = paragraph.get("text", "")
            # Eliminar el marcador de la lista del texto
            content_text = text[len(label):].lstrip() if label else text
            
            # Crear elemento LI con estructura correcta
            li_element = {
                "type": "LI",
                "children": [
                    {
                        "type": "Lbl",
                        "text": label,
                        "children": []
                    },
                    {
                        "type": "LBody",
                        "children": [
                            {
                                "type": "P",
                                "text": content_text,
                                "children": paragraph.get("children", [])
                            }
                        ]
                    }
                ]
            }
            
            list_element["children"].append(li_element)
        
        # Eliminar los párrafos originales (de atrás hacia adelante para evitar cambios en índices)
        for idx in sorted(indices, reverse=True):
            parent_elements.pop(idx)
            
        # Insertar la nueva lista en la posición del primer párrafo
        parent_elements.insert(indices[0], list_element)
        
        logger.info(f"Convertida secuencia de {len(list_items)} párrafos a lista {list_type}")
        return 1
    
    def _create_list_item_structure(self, element: Dict) -> Dict:
        """
        Crea una estructura de elemento de lista a partir de un elemento existente.
        
        Args:
            element: Elemento a convertir en elemento de lista
            
        Returns:
            Dict: Estructura corregida como elemento de lista
        """
        # Extraer texto y verificar si contiene un marcador de lista
        text = element.get("text", "")
        list_type, label = self._identify_list_item_type(text)
        
        if list_type and label:
            # Eliminar el marcador de la lista del texto
            content_text = text[len(label):].lstrip()
            
            # Crear nueva estructura de LI
            li_element = {
                "type": "LI",
                "children": [
                    {
                        "type": "Lbl",
                        "text": label,
                        "children": []
                    },
                    {
                        "type": "LBody",
                        "children": [
                            {
                                "type": "P" if element.get("type") != "P" else element.get("type"),
                                "text": content_text,
                                "children": element.get("children", [])
                            }
                        ]
                    }
                ]
            }
            
            # Copiar atributos si existen
            if "attributes" in element:
                li_element["attributes"] = element["attributes"].copy()
            
            # Copiar elemento pikepdf si existe
            if "element" in element:
                li_element["element"] = element["element"]
            
            return li_element
        else:
            # Si no hay marcador detectable, simplemente encapsular en estructura LI
            li_element = {
                "type": "LI",
                "children": [
                    {
                        "type": "LBody",
                        "children": [element]
                    }
                ]
            }
            
            return li_element
    
    def _is_numbered_list(self, list_element: Dict) -> bool:
        """
        Determina si una lista es numerada basada en sus elementos.
        
        Args:
            list_element: Elemento de lista a verificar
            
        Returns:
            bool: True si parece una lista numerada
        """
        children = list_element.get("children", [])
        li_elements = [child for child in children if child.get("type") == "LI"]
        
        if not li_elements:
            return False
            
        # Examinar los primeros elementos para ver si tienen números
        numbered_count = 0
        for li in li_elements[:min(3, len(li_elements))]:
            li_children = li.get("children", [])
            
            # Buscar elementos Lbl
            for child in li_children:
                if child.get("type") == "Lbl":
                    lbl_text = child.get("text", "")
                    # Verificar si el texto parece un número, letra o romano
                    if re.match(r'^\s*\d+[\.\)]', lbl_text) or \
                       re.match(r'^\s*[a-zA-Z][\.\)]', lbl_text) or \
                       re.match(r'^\s*[ivxlcdmIVXLCDM]+[\.\)]', lbl_text):
                        numbered_count += 1
                    break
        
        # Considerar numerada si más de la mitad de los elementos examinados tienen números
        return numbered_count > len(li_elements[:min(3, len(li_elements))]) / 2
    
    def _has_list_numbering_attribute(self, list_element: Dict) -> bool:
        """
        Verifica si un elemento de lista tiene el atributo ListNumbering.
        
        Args:
            list_element: Elemento de lista a verificar
            
        Returns:
            bool: True si tiene el atributo ListNumbering
        """
        # Verificar en el diccionario de atributos
        if "attributes" in list_element and "ListNumbering" in list_element["attributes"]:
            return True
            
        # Verificar en el objeto pikepdf si está disponible
        if "element" in list_element:
            pikepdf_element = list_element["element"]
            # Diferentes formas en que puede aparecer el atributo
            for attr_name in ["ListNumbering", "listnumbering", "/ListNumbering"]:
                if hasattr(pikepdf_element, attr_name) or attr_name in pikepdf_element:
                    return True
                    
        return False
    
    def _add_list_numbering_attribute(self, list_element: Dict) -> bool:
        """
        Añade el atributo ListNumbering a una lista numerada.
        
        Args:
            list_element: Elemento de lista a modificar
            
        Returns:
            bool: True si se añadió el atributo, False si no
        """
        numbering_style = self._determine_numbering_style(list_element)
        
        if not numbering_style:
            return False
            
        # Añadir atributo al diccionario de atributos
        if "attributes" not in list_element:
            list_element["attributes"] = {}
            
        list_element["attributes"]["ListNumbering"] = numbering_style
        
        # Si hay un objeto pikepdf, actualizar también
        if "element" in list_element and self.pdf_writer:
            self.pdf_writer.update_tag_attribute(
                id(list_element["element"]), 
                "ListNumbering", 
                numbering_style
            )
            
        logger.debug(f"Añadido atributo ListNumbering={numbering_style} a una lista")
        return True
    
    def _determine_numbering_style(self, list_element: Dict) -> Optional[str]:
        """
        Determina el estilo de numeración apropiado para una lista.
        
        Args:
            list_element: Elemento de lista a analizar
            
        Returns:
            Optional[str]: Valor para ListNumbering o None si no se puede determinar
        """
        children = list_element.get("children", [])
        li_elements = [child for child in children if child.get("type") == "LI"]
        
        if not li_elements:
            return None
            
        # Recolectar etiquetas para análisis
        labels = []
        for li in li_elements:
            li_children = li.get("children", [])
            
            # Buscar elementos Lbl
            for child in li_children:
                if child.get("type") == "Lbl":
                    lbl_text = child.get("text", "")
                    labels.append(lbl_text.strip())
                    break
        
        if not labels:
            return None
            
        # Analizar etiquetas para determinar estilo
        decimal_count = len([lbl for lbl in labels if re.match(r'^\d+[\.\)]', lbl)])
        lower_alpha_count = len([lbl for lbl in labels if re.match(r'^[a-z][\.\)]', lbl)])
        upper_alpha_count = len([lbl for lbl in labels if re.match(r'^[A-Z][\.\)]', lbl)])
        lower_roman_count = len([lbl for lbl in labels if re.match(r'^[ivxlcdm]+[\.\)]', lbl)])
        upper_roman_count = len([lbl for lbl in labels if re.match(r'^[IVXLCDM]+[\.\)]', lbl)])
        
        # Determinar el tipo más común
        counts = [
            (decimal_count, "Decimal"),
            (lower_alpha_count, "LowerAlpha"),
            (upper_alpha_count, "UpperAlpha"),
            (lower_roman_count, "LowerRoman"),
            (upper_roman_count, "UpperRoman")
        ]
        
        if not any(c[0] for c in counts):
            return "None"  # No se detectó un estilo estándar
            
        # Devolver el estilo más común
        _, style = max(counts, key=lambda x: x[0])
        return style