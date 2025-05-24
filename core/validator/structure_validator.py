# core/validator/structure_validator.py

from typing import Dict, List, Optional, Any, Set, Tuple
import re
from loguru import logger

class StructureValidator:
    """
    Validador de estructura lógica según PDF/UA y Matterhorn Protocol.
    
    Checkpoints relacionados:
    - 01-001: Artifact is tagged as real content
    - 01-002: Real content is marked as artifact
    - 01-005: Content is neither marked as Artifact nor tagged as real content
    - 01-006: The structure type and attributes are not semantically appropriate
    - 09-001: Tags are not in logical reading order
    - 09-002: Structure elements are nested in a semantically inappropriate manner
    - 14-003: Numbered heading levels in descending sequence are skipped
    """
    
    def __init__(self):
        """Inicializa el validador de estructura."""
        self.pdf_loader = None
        
        # Tipos de elementos estándar PDF
        self.standard_structure_types = {
            # Elementos de agrupación
            'Document', 'Part', 'Art', 'Sect', 'Div', 'BlockQuote', 'Caption', 'TOC', 'TOCI', 'Index', 'NonStruct', 'Private',
            
            # Elementos de párrafo
            'P', 'H', 'H1', 'H2', 'H3', 'H4', 'H5', 'H6',
            
            # Elementos de lista
            'L', 'LI', 'Lbl', 'LBody',
            
            # Elementos de tabla
            'Table', 'TR', 'TH', 'TD', 'THead', 'TBody', 'TFoot',
            
            # Elementos inline  
            'Span', 'Quote', 'Note', 'Reference', 'BibEntry', 'Code', 'Link', 'Annot',
            
            # Elementos de ilustración
            'Figure', 'Formula', 'Form'
        }
        
        # Elementos que pueden contener otros elementos
        self.container_elements = {
            'Document', 'Part', 'Art', 'Sect', 'Div', 'BlockQuote', 'Caption', 'TOC', 'Index',
            'L', 'LI', 'LBody', 'Table', 'TR', 'TH', 'TD', 'THead', 'TBody', 'TFoot'
        }
        
        # Elementos que típicamente son hojas (no contienen otros elementos estructurales)
        self.leaf_elements = {
            'P', 'H1', 'H2', 'H3', 'H4', 'H5', 'H6', 'Span', 'Quote', 'Note', 'Reference', 
            'BibEntry', 'Code', 'Link', 'Annot', 'Figure', 'Formula', 'Lbl'
        }
        
        # Relaciones padre-hijo válidas
        self.valid_parent_child = {
            'Document': {'Part', 'Art', 'Sect', 'Div', 'P', 'H1', 'H2', 'H3', 'H4', 'H5', 'H6', 'L', 'Table', 'Figure', 'BlockQuote', 'TOC', 'Index'},
            'Part': {'Art', 'Sect', 'Div', 'P', 'H1', 'H2', 'H3', 'H4', 'H5', 'H6', 'L', 'Table', 'Figure'},
            'Art': {'Sect', 'Div', 'P', 'H1', 'H2', 'H3', 'H4', 'H5', 'H6', 'L', 'Table', 'Figure'},
            'Sect': {'Div', 'P', 'H1', 'H2', 'H3', 'H4', 'H5', 'H6', 'L', 'Table', 'Figure'},
            'Div': {'P', 'H1', 'H2', 'H3', 'H4', 'H5', 'H6', 'L', 'Table', 'Figure', 'Div'},
            'L': {'LI'},
            'LI': {'Lbl', 'LBody'},
            'LBody': {'P', 'L', 'Table', 'Figure'},
            'Table': {'TR', 'THead', 'TBody', 'TFoot', 'Caption'},
            'THead': {'TR'},
            'TBody': {'TR'},
            'TFoot': {'TR'},
            'TR': {'TH', 'TD'},
            'TH': {'P', 'Span', 'Link'},
            'TD': {'P', 'Span', 'Link', 'L', 'Figure'},
            'P': {'Span', 'Link', 'Note', 'Reference'},
            'BlockQuote': {'P', 'L'},
            'Caption': {'P', 'Span'},
            'TOC': {'TOCI'},
            'TOCI': {'P', 'Span', 'Link'}
        }
        
        logger.info("StructureValidator inicializado")
    
    def set_pdf_loader(self, pdf_loader):
        """
        Establece la referencia al cargador de PDF.
        
        Args:
            pdf_loader: Instancia de PDFLoader
        """
        self.pdf_loader = pdf_loader
        logger.debug("PDFLoader establecido en StructureValidator")
    
    def validate(self, structure_tree: Dict) -> List[Dict]:
        """
        Valida la estructura lógica del documento.
        
        Args:
            structure_tree: Árbol de estructura del documento
            
        Returns:
            List[Dict]: Lista de problemas encontrados
        """
        issues = []
        
        if not structure_tree:
            issues.append({
                "checkpoint": "01-005",
                "severity": "error",
                "description": "El documento no tiene estructura lógica",
                "fix_description": "Generar estructura lógica para el documento",
                "fixable": True,
                "page": "all"
            })
            return issues
        
        try:
            # Validar estructura general
            general_issues = self._validate_general_structure(structure_tree)
            issues.extend(general_issues)
            
            # Validar jerarquía de encabezados
            heading_issues = self._validate_heading_hierarchy(structure_tree)
            issues.extend(heading_issues)
            
            # Validar anidamiento semántico
            nesting_issues = self._validate_semantic_nesting(structure_tree)
            issues.extend(nesting_issues)
            
            # Validar orden de lectura
            reading_order_issues = self._validate_reading_order(structure_tree)
            issues.extend(reading_order_issues)
            
            # Validar elementos específicos
            specific_issues = self._validate_specific_elements(structure_tree)
            issues.extend(specific_issues)
            
        except Exception as e:
            logger.error(f"Error durante validación de estructura: {e}")
            issues.append({
                "checkpoint": "general",
                "severity": "error",
                "description": f"Error durante validación de estructura: {str(e)}",
                "fix_description": "Revisar la estructura del documento",
                "fixable": False,
                "page": "all"
            })
        
        logger.info(f"Validación de estructura completada: {len(issues)} problemas encontrados")
        return issues
    
    def _validate_general_structure(self, structure_tree: Dict) -> List[Dict]:
        """
        Valida la estructura general del documento.
        
        Args:
            structure_tree: Árbol de estructura
            
        Returns:
            List[Dict]: Lista de problemas encontrados
        """
        issues = []
        
        # Verificar que hay contenido real etiquetado
        has_real_content = self._has_real_content(structure_tree)
        if not has_real_content:
            issues.append({
                "checkpoint": "01-005",
                "severity": "error",
                "description": "No se encontró contenido real etiquetado en el documento",
                "fix_description": "Etiquetar el contenido real del documento",
                "fixable": True,
                "page": "all"
            })
        
        # Verificar profundidad de anidamiento
        max_depth = self._calculate_max_depth(structure_tree)
        if max_depth > 10:  # Umbral razonable
            issues.append({
                "checkpoint": "09-002",
                "severity": "warning",
                "description": f"Estructura excesivamente anidada (profundidad: {max_depth})",
                "fix_description": "Simplificar la estructura del documento",
                "fixable": True,
                "page": "all"
            })
        
        return issues
    
    def _validate_heading_hierarchy(self, structure_tree: Dict) -> List[Dict]:
        """
        Valida la jerarquía de encabezados.
        
        Args:
            structure_tree: Árbol de estructura
            
        Returns:
            List[Dict]: Lista de problemas encontrados
        """
        issues = []
        
        # Extraer todos los encabezados en orden
        headings = self._extract_headings(structure_tree)
        
        if not headings:
            return issues
        
        # Validar secuencia de niveles
        prev_level = 0
        for i, heading in enumerate(headings):
            current_level = heading['level']
            
            # Checkpoint 14-003: Verificar saltos de nivel
            if current_level > prev_level + 1:
                issues.append({
                    "checkpoint": "14-003",
                    "severity": "error",
                    "description": f"Salto de nivel de encabezado: de H{prev_level} a H{current_level}",
                    "fix_description": f"Corregir la jerarquía de encabezados (usar H{prev_level + 1} en lugar de H{current_level})",
                    "fixable": True,
                    "page": heading.get('page', 'unknown'),
                    "element_id": heading.get('element_id'),
                    "details": {
                        "heading_text": heading.get('text', ''),
                        "expected_level": prev_level + 1,
                        "actual_level": current_level
                    }
                })
            
            # Verificar que los encabezados tienen texto
            if not heading.get('text', '').strip():
                issues.append({
                    "checkpoint": "01-006",
                    "severity": "warning",
                    "description": f"Encabezado H{current_level} sin texto",
                    "fix_description": "Añadir texto descriptivo al encabezado",
                    "fixable": True,
                    "page": heading.get('page', 'unknown'),
                    "element_id": heading.get('element_id')
                })
            
            prev_level = max(prev_level, current_level)
        
        return issues
    
    def _validate_semantic_nesting(self, structure_tree: Dict) -> List[Dict]:
        """
        Valida el anidamiento semántico de elementos.
        
        Args:
            structure_tree: Árbol de estructura
            
        Returns:
            List[Dict]: Lista de problemas encontrados
        """
        issues = []
        
        def validate_node(node, parent_type=None, path=""):
            if not isinstance(node, dict):
                return
            
            node_type = node.get('type', '')
            children = node.get('children', [])
            
            # Checkpoint 01-006: Verificar tipos semánticamente apropiados
            if node_type not in self.standard_structure_types and node_type != 'StructTreeRoot':
                issues.append({
                    "checkpoint": "01-006",
                    "severity": "warning",
                    "description": f"Tipo de estructura no estándar: '{node_type}'",
                    "fix_description": "Usar un tipo de estructura estándar de PDF",
                    "fixable": True,
                    "page": node.get('page', 'unknown'),
                    "element_id": id(node.get('element')) if node.get('element') else None
                })
            
            # Checkpoint 09-002: Verificar anidamiento apropiado
            if parent_type and parent_type in self.valid_parent_child:
                valid_children = self.valid_parent_child[parent_type]
                if node_type not in valid_children and node_type not in ['StructTreeRoot', 'TextContent', 'MCID']:
                    issues.append({
                        "checkpoint": "09-002",
                        "severity": "warning",
                        "description": f"Anidamiento inapropiado: '{node_type}' dentro de '{parent_type}'",
                        "fix_description": f"Revisar la estructura - '{node_type}' no debería estar dentro de '{parent_type}'",
                        "fixable": True,
                        "page": node.get('page', 'unknown'),
                        "element_id": id(node.get('element')) if node.get('element') else None
                    })
            
            # Validar elementos específicos
            specific_issues = self._validate_element_specific_rules(node, parent_type)
            issues.extend(specific_issues)
            
            # Procesar hijos recursivamente
            for i, child in enumerate(children):
                child_path = f"{path}/child[{i}]"
                validate_node(child, node_type, child_path)
        
        validate_node(structure_tree)
        return issues
    
    def _validate_element_specific_rules(self, node: Dict, parent_type: str) -> List[Dict]:
        """
        Valida reglas específicas para ciertos tipos de elementos.
        
        Args:
            node: Nodo a validar
            parent_type: Tipo del elemento padre
            
        Returns:
            List[Dict]: Lista de problemas encontrados
        """
        issues = []
        node_type = node.get('type', '')
        
        # Validar listas
        if node_type == 'L':
            list_issues = self._validate_list_element(node)
            issues.extend(list_issues)
        
        # Validar elementos de lista
        elif node_type == 'LI':
            li_issues = self._validate_list_item_element(node)
            issues.extend(li_issues)
        
        # Validar tablas
        elif node_type == 'Table':
            table_issues = self._validate_table_element(node)
            issues.extend(table_issues)
        
        # Validar filas de tabla
        elif node_type == 'TR':
            tr_issues = self._validate_table_row_element(node)
            issues.extend(tr_issues)
        
        # Validar celdas de tabla
        elif node_type in ['TH', 'TD']:
            cell_issues = self._validate_table_cell_element(node)
            issues.extend(cell_issues)
        
        # Validar figuras
        elif node_type == 'Figure':
            figure_issues = self._validate_figure_element(node)
            issues.extend(figure_issues)
        
        # Validar enlaces
        elif node_type == 'Link':
            link_issues = self._validate_link_element(node)
            issues.extend(link_issues)
        
        return issues
    
    def _validate_list_element(self, node: Dict) -> List[Dict]:
        """Valida elementos de lista."""
        issues = []
        children = node.get('children', [])
        
        # Verificar que contiene elementos LI
        li_children = [child for child in children if child.get('type') == 'LI']
        non_li_children = [child for child in children if child.get('type') != 'LI']
        
        if not li_children:
            issues.append({
                "checkpoint": "09-002",
                "severity": "error",
                "description": "Lista (L) sin elementos de lista (LI)",
                "fix_description": "Añadir elementos LI a la lista o cambiar el tipo de estructura",
                "fixable": True,
                "page": node.get('page', 'unknown'),
                "element_id": id(node.get('element')) if node.get('element') else None
            })
        
        if non_li_children:
            non_li_types = [child.get('type') for child in non_li_children]
            issues.append({
                "checkpoint": "09-002",
                "severity": "warning",
                "description": f"Lista contiene elementos que no son LI: {non_li_types}",
                "fix_description": "Mover elementos no-LI fuera de la lista o reestructurar",
                "fixable": True,
                "page": node.get('page', 'unknown'),
                "element_id": id(node.get('element')) if node.get('element') else None
            })
        
        return issues
    
    def _validate_list_item_element(self, node: Dict) -> List[Dict]:
        """Valida elementos de elemento de lista."""
        issues = []
        children = node.get('children', [])
        
        # LI debería contener Lbl y/o LBody
        has_lbl = any(child.get('type') == 'Lbl' for child in children)
        has_lbody = any(child.get('type') == 'LBody' for child in children)
        
        if not has_lbl and not has_lbody:
            # Si no tiene Lbl ni LBody, debería tener contenido directo
            has_direct_content = bool(node.get('text', '').strip())
            if not has_direct_content:
                issues.append({
                    "checkpoint": "09-002",
                    "severity": "warning",
                    "description": "Elemento de lista (LI) sin contenido estructurado (Lbl/LBody) ni texto directo",
                    "fix_description": "Añadir etiqueta (Lbl) y/o cuerpo (LBody) al elemento de lista",
                    "fixable": True,
                    "page": node.get('page', 'unknown'),
                    "element_id": id(node.get('element')) if node.get('element') else None
                })
        
        return issues
    
    def _validate_table_element(self, node: Dict) -> List[Dict]:
        """Valida elementos de tabla."""
        issues = []
        children = node.get('children', [])
        
        # Verificar que contiene filas o grupos de filas
        table_content = [child for child in children if child.get('type') in ['TR', 'THead', 'TBody', 'TFoot']]
        
        if not table_content:
            issues.append({
                "checkpoint": "09-002",
                "severity": "error",
                "description": "Tabla sin filas (TR) o grupos de filas",
                "fix_description": "Añadir filas (TR) a la tabla",
                "fixable": True,
                "page": node.get('page', 'unknown'),
                "element_id": id(node.get('element')) if node.get('element') else None
            })
        
        return issues
    
    def _validate_table_row_element(self, node: Dict) -> List[Dict]:
        """Valida elementos de fila de tabla."""
        issues = []
        children = node.get('children', [])
        
        # Verificar que contiene celdas
        cells = [child for child in children if child.get('type') in ['TH', 'TD']]
        
        if not cells:
            issues.append({
                "checkpoint": "09-002",
                "severity": "error",
                "description": "Fila de tabla (TR) sin celdas (TH/TD)",
                "fix_description": "Añadir celdas (TH o TD) a la fila",
                "fixable": True,
                "page": node.get('page', 'unknown'),
                "element_id": id(node.get('element')) if node.get('element') else None
            })
        
        return issues
    
    def _validate_table_cell_element(self, node: Dict) -> List[Dict]:
        """Valida elementos de celda de tabla."""
        issues = []
        node_type = node.get('type', '')
        attributes = node.get('attributes', {})
        
        # Verificar atributos de celdas de cabecera
        if node_type == 'TH':
            if 'scope' not in attributes or not attributes['scope']:
                issues.append({
                    "checkpoint": "15-003",
                    "severity": "error",
                    "description": "Celda de cabecera (TH) sin atributo Scope",
                    "fix_description": "Añadir atributo Scope (Row, Col, Both) a la celda de cabecera",
                    "fixable": True,
                    "page": node.get('page', 'unknown'),
                    "element_id": id(node.get('element')) if node.get('element') else None
                })
        
        # Verificar contenido de celda
        has_content = bool(node.get('text', '').strip()) or bool(node.get('children', []))
        if not has_content:
            issues.append({
                "checkpoint": "01-006",
                "severity": "info",
                "description": f"Celda de tabla ({node_type}) vacía",
                "fix_description": "Añadir contenido a la celda o usar elemento estructural apropiado",
                "fixable": True,
                "page": node.get('page', 'unknown'),
                "element_id": id(node.get('element')) if node.get('element') else None
            })
        
        return issues
    
    def _validate_figure_element(self, node: Dict) -> List[Dict]:
        """Valida elementos de figura."""
        issues = []
        attributes = node.get('attributes', {})
        
        # Verificar texto alternativo
        if 'alt' not in attributes or not attributes['alt']:
            issues.append({
                "checkpoint": "13-004",
                "severity": "error",
                "description": "Figura sin texto alternativo (Alt)",
                "fix_description": "Añadir texto alternativo descriptivo a la figura",
                "fixable": True,
                "page": node.get('page', 'unknown'),
                "element_id": id(node.get('element')) if node.get('element') else None
            })
        
        return issues
    
    def _validate_link_element(self, node: Dict) -> List[Dict]:
        """Valida elementos de enlace."""
        issues = []
        
        # Verificar que tiene contenido
        has_text = bool(node.get('text', '').strip())
        has_children = bool(node.get('children', []))
        
        if not has_text and not has_children:
            issues.append({
                "checkpoint": "01-006",
                "severity": "warning",
                "description": "Enlace sin texto descriptivo",
                "fix_description": "Añadir texto descriptivo al enlace",
                "fixable": True,
                "page": node.get('page', 'unknown'),
                "element_id": id(node.get('element')) if node.get('element') else None
            })
        
        return issues
    
    def _validate_reading_order(self, structure_tree: Dict) -> List[Dict]:
        """
        Valida el orden de lectura lógico.
        
        Args:
            structure_tree: Árbol de estructura
            
        Returns:
            List[Dict]: Lista de problemas encontrados
        """
        issues = []
        
        # Esta es una validación básica del orden de lectura
        # Una implementación completa requeriría análisis más sofisticado
        
        elements_by_page = self._group_elements_by_page(structure_tree)
        
        for page_num, elements in elements_by_page.items():
            # Verificar orden de encabezados en la página
            headings = [elem for elem in elements if elem['type'].startswith('H')]
            
            if len(headings) > 1:
                # Verificar que los encabezados aparecen en orden lógico
                for i in range(1, len(headings)):
                    prev_level = int(headings[i-1]['type'][1:]) if headings[i-1]['type'][1:].isdigit() else 1
                    curr_level = int(headings[i]['type'][1:]) if headings[i]['type'][1:].isdigit() else 1
                    
                    # Permitir mismo nivel o nivel inferior, pero detectar saltos grandes
                    if curr_level > prev_level + 2:
                        issues.append({
                            "checkpoint": "09-001",
                            "severity": "warning",
                            "description": f"Posible problema de orden de lectura: H{prev_level} seguido de H{curr_level}",
                            "fix_description": "Revisar el orden lógico de los encabezados",
                            "fixable": True,
                            "page": page_num
                        })
        
        return issues
    
    def _validate_specific_elements(self, structure_tree: Dict) -> List[Dict]:
        """
        Realiza validaciones específicas adicionales.
        
        Args:
            structure_tree: Árbol de estructura
            
        Returns:
            List[Dict]: Lista de problemas encontrados
        """
        issues = []
        
        # Contar tipos de elementos
        element_counts = self._count_element_types(structure_tree)
        
        # Verificar que hay contenido estructurado
        content_elements = element_counts.get('P', 0) + element_counts.get('Figure', 0) + element_counts.get('Table', 0)
        if content_elements == 0:
            issues.append({
                "checkpoint": "01-005",
                "severity": "warning",
                "description": "Documento sin elementos de contenido estructurado (P, Figure, Table)",
                "fix_description": "Añadir estructura semántica al contenido del documento",
                "fixable": True,
                "page": "all"
            })
        
        # Verificar balance de la estructura
        if element_counts.get('Div', 0) > content_elements * 2:
            issues.append({
                "checkpoint": "01-006",
                "severity": "info",
                "description": "Uso excesivo de elementos Div - considere usar elementos más específicos",
                "fix_description": "Reemplazar algunos elementos Div con elementos semánticamente más apropiados",
                "fixable": True,
                "page": "all"
            })
        
        return issues
    
    # Métodos auxiliares
    
    def _has_real_content(self, structure_tree: Dict) -> bool:
        """Verifica si la estructura contiene contenido real."""
        def check_node(node):
            if isinstance(node, dict):
                node_type = node.get('type', '')
                
                # Tipos que indican contenido real
                content_types = {'P', 'H1', 'H2', 'H3', 'H4', 'H5', 'H6', 'Figure', 'Table', 'L'}
                if node_type in content_types:
                    return True
                
                # Verificar si tiene texto
                if node.get('text', '').strip():
                    return True
                
                # Verificar hijos
                for child in node.get('children', []):
                    if check_node(child):
                        return True
            
            return False
        
        return check_node(structure_tree)
    
    def _calculate_max_depth(self, structure_tree: Dict, current_depth: int = 0) -> int:
        """Calcula la profundidad máxima de anidamiento."""
        max_depth = current_depth
        
        if isinstance(structure_tree, dict):
            children = structure_tree.get('children', [])
            for child in children:
                child_depth = self._calculate_max_depth(child, current_depth + 1)
                max_depth = max(max_depth, child_depth)
        
        return max_depth
    
    def _extract_headings(self, structure_tree: Dict) -> List[Dict]:
        """Extrae todos los encabezados en orden de lectura."""
        headings = []
        
        def extract_from_node(node, path=""):
            if isinstance(node, dict):
                node_type = node.get('type', '')
                
                if node_type.startswith('H') and node_type[1:].isdigit():
                    level = int(node_type[1:])
                    headings.append({
                        'type': node_type,
                        'level': level,
                        'text': node.get('text', ''),
                        'page': node.get('page'),
                        'element_id': id(node.get('element')) if node.get('element') else None,
                        'path': path
                    })
                
                # Procesar hijos
                children = node.get('children', [])
                for i, child in enumerate(children):
                    child_path = f"{path}/child[{i}]" if path else f"child[{i}]"
                    extract_from_node(child, child_path)
        
        extract_from_node(structure_tree)
        return headings
    
    def _group_elements_by_page(self, structure_tree: Dict) -> Dict[int, List[Dict]]:
        """Agrupa elementos por página."""
        elements_by_page = {}
        
        def collect_elements(node):
            if isinstance(node, dict):
                page = node.get('page')
                if page is not None:
                    if page not in elements_by_page:
                        elements_by_page[page] = []
                    elements_by_page[page].append(node)
                
                # Procesar hijos
                for child in node.get('children', []):
                    collect_elements(child)
        
        collect_elements(structure_tree)
        return elements_by_page
    
    def _count_element_types(self, structure_tree: Dict) -> Dict[str, int]:
        """Cuenta elementos por tipo."""
        counts = {}
        
        def count_node(node):
            if isinstance(node, dict):
                node_type = node.get('type', '')
                counts[node_type] = counts.get(node_type, 0) + 1
                
                # Procesar hijos
                for child in node.get('children', []):
                    count_node(child)
        
        count_node(structure_tree)
        return counts