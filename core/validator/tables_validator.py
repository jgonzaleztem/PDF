# core/validator/tables_validator.py

from typing import Dict, List, Optional, Any, Set, Tuple
from loguru import logger

class TablesValidator:
    """
    Validador específico para tablas según PDF/UA y Matterhorn Protocol.
    
    Checkpoints relacionados:
    - 15-003: In a table not organized with Headers attributes and IDs, a <TH> cell does not contain a Scope attribute
    - 15-005: A given cell's header cannot be unambiguously determined
    - Validaciones adicionales de estructura de tablas
    """
    
    def __init__(self):
        """Inicializa el validador de tablas."""
        self.pdf_loader = None
        
        # Valores válidos para el atributo Scope
        self.valid_scope_values = {'Row', 'Col', 'Column', 'Both', 'Rowgroup', 'Colgroup'}
        
        logger.info("TablesValidator inicializado")
    
    def set_pdf_loader(self, pdf_loader):
        """
        Establece la referencia al cargador de PDF.
        
        Args:
            pdf_loader: Instancia de PDFLoader
        """
        self.pdf_loader = pdf_loader
        logger.debug("PDFLoader establecido en TablesValidator")
    
    def validate(self, structure_tree: Dict) -> List[Dict]:
        """
        Valida todas las tablas en la estructura del documento.
        
        Args:
            structure_tree: Árbol de estructura del documento
            
        Returns:
            List[Dict]: Lista de problemas encontrados
        """
        issues = []
        
        if not structure_tree:
            return issues
        
        try:
            # Extraer todas las tablas
            tables = self._extract_tables(structure_tree)
            
            if not tables:
                logger.debug("No se encontraron tablas para validar")
                return issues
            
            logger.info(f"Validando {len(tables)} tablas encontradas")
            
            # Validar cada tabla
            for i, table in enumerate(tables):
                table_issues = self._validate_table(table, i)
                issues.extend(table_issues)
            
        except Exception as e:
            logger.error(f"Error durante validación de tablas: {e}")
            issues.append({
                "checkpoint": "general",
                "severity": "error",
                "description": f"Error durante validación de tablas: {str(e)}",
                "fix_description": "Revisar la estructura de las tablas",
                "fixable": False,
                "page": "all"
            })
        
        logger.info(f"Validación de tablas completada: {len(issues)} problemas encontrados")
        return issues
    
    def _extract_tables(self, structure_tree: Dict) -> List[Dict]:
        """
        Extrae todas las tablas del árbol de estructura.
        
        Args:
            structure_tree: Árbol de estructura
            
        Returns:
            List[Dict]: Lista de tablas encontradas
        """
        tables = []
        
        def extract_from_node(node, path=""):
            if isinstance(node, dict):
                node_type = node.get('type', '')
                
                if node_type == 'Table':
                    table_info = {
                        'node': node,
                        'path': path,
                        'page': node.get('page'),
                        'element_id': id(node.get('element')) if node.get('element') else None
                    }
                    tables.append(table_info)
                
                # Procesar hijos recursivamente
                children = node.get('children', [])
                for i, child in enumerate(children):
                    child_path = f"{path}/child[{i}]" if path else f"child[{i}]"
                    extract_from_node(child, child_path)
        
        extract_from_node(structure_tree)
        return tables
    
    def _validate_table(self, table_info: Dict, table_index: int) -> List[Dict]:
        """
        Valida una tabla específica.
        
        Args:
            table_info: Información de la tabla
            table_index: Índice de la tabla (para identificación)
            
        Returns:
            List[Dict]: Lista de problemas encontrados
        """
        issues = []
        table_node = table_info['node']
        table_path = table_info['path']
        table_page = table_info.get('page', 'unknown')
        
        try:
            # Analizar estructura de la tabla
            table_structure = self._analyze_table_structure(table_node)
            
            # Validar estructura básica
            basic_issues = self._validate_basic_table_structure(table_structure, table_info)
            issues.extend(basic_issues)
            
            # Validar celdas de cabecera
            header_issues = self._validate_table_headers(table_structure, table_info)
            issues.extend(header_issues)
            
            # Validar accesibilidad de celdas
            accessibility_issues = self._validate_cell_accessibility(table_structure, table_info)
            issues.extend(accessibility_issues)
            
            # Validar integridad de la tabla
            integrity_issues = self._validate_table_integrity(table_structure, table_info)
            issues.extend(integrity_issues)
            
        except Exception as e:
            logger.error(f"Error validando tabla {table_index}: {e}")
            issues.append({
                "checkpoint": "general",
                "severity": "error",
                "description": f"Error validando tabla {table_index + 1}: {str(e)}",
                "fix_description": "Revisar la estructura de la tabla",
                "fixable": False,
                "page": table_page,
                "element_id": table_info.get('element_id')
            })
        
        return issues
    
    def _analyze_table_structure(self, table_node: Dict) -> Dict:
        """
        Analiza la estructura de una tabla.
        
        Args:
            table_node: Nodo de la tabla
            
        Returns:
            Dict: Análisis de la estructura de la tabla
        """
        structure = {
            'rows': [],
            'header_rows': [],
            'body_rows': [],
            'footer_rows': [],
            'total_rows': 0,
            'max_columns': 0,
            'has_thead': False,
            'has_tbody': False,
            'has_tfooter': False,
            'headers_by_id': {},
            'cells_with_headers_attr': [],
            'caption': None
        }
        
        children = table_node.get('children', [])
        
        for child in children:
            child_type = child.get('type', '')
            
            if child_type == 'Caption':
                structure['caption'] = child
            
            elif child_type == 'THead':
                structure['has_thead'] = True
                thead_rows = self._extract_rows_from_group(child)
                structure['header_rows'].extend(thead_rows)
                structure['rows'].extend(thead_rows)
            
            elif child_type == 'TBody':
                structure['has_tbody'] = True
                tbody_rows = self._extract_rows_from_group(child)
                structure['body_rows'].extend(tbody_rows)
                structure['rows'].extend(tbody_rows)
            
            elif child_type == 'TFoot':
                structure['has_tfooter'] = True
                tfoot_rows = self._extract_rows_from_group(child)
                structure['footer_rows'].extend(tfoot_rows)
                structure['rows'].extend(tfoot_rows)
            
            elif child_type == 'TR':
                # Fila directa en la tabla
                row_info = self._analyze_table_row(child)
                structure['rows'].append(row_info)
                structure['body_rows'].append(row_info)
        
        # Calcular estadísticas
        structure['total_rows'] = len(structure['rows'])
        
        for row in structure['rows']:
            structure['max_columns'] = max(structure['max_columns'], len(row['cells']))
        
        # Indexar celdas por ID para validar referencias Headers
        for row in structure['rows']:
            for cell in row['cells']:
                cell_id = cell.get('attributes', {}).get('id')
                if cell_id:
                    structure['headers_by_id'][cell_id] = cell
                
                headers_attr = cell.get('attributes', {}).get('headers')
                if headers_attr:
                    structure['cells_with_headers_attr'].append(cell)
        
        return structure
    
    def _extract_rows_from_group(self, group_node: Dict) -> List[Dict]:
        """Extrae filas de un grupo de tabla (THead, TBody, TFoot)."""
        rows = []
        children = group_node.get('children', [])
        
        for child in children:
            if child.get('type') == 'TR':
                row_info = self._analyze_table_row(child)
                rows.append(row_info)
        
        return rows
    
    def _analyze_table_row(self, row_node: Dict) -> Dict:
        """
        Analiza una fila de tabla.
        
        Args:
            row_node: Nodo de la fila
            
        Returns:
            Dict: Información de la fila
        """
        row_info = {
            'node': row_node,
            'cells': [],
            'header_cells': [],
            'data_cells': [],
            'page': row_node.get('page')
        }
        
        children = row_node.get('children', [])
        
        for child in children:
            child_type = child.get('type', '')
            
            if child_type in ['TH', 'TD']:
                cell_info = self._analyze_table_cell(child)
                row_info['cells'].append(cell_info)
                
                if child_type == 'TH':
                    row_info['header_cells'].append(cell_info)
                else:
                    row_info['data_cells'].append(cell_info)
        
        return row_info
    
    def _analyze_table_cell(self, cell_node: Dict) -> Dict:
        """
        Analiza una celda de tabla.
        
        Args:
            cell_node: Nodo de la celda
            
        Returns:
            Dict: Información de la celda
        """
        cell_info = {
            'node': cell_node,
            'type': cell_node.get('type', ''),
            'text': cell_node.get('text', '').strip(),
            'attributes': cell_node.get('attributes', {}),
            'page': cell_node.get('page'),
            'element_id': id(cell_node.get('element')) if cell_node.get('element') else None,
            'has_content': False
        }
        
        # Verificar si tiene contenido
        cell_info['has_content'] = bool(cell_info['text']) or bool(cell_node.get('children', []))
        
        return cell_info
    
    def _validate_basic_table_structure(self, structure: Dict, table_info: Dict) -> List[Dict]:
        """
        Valida la estructura básica de la tabla.
        
        Args:
            structure: Estructura analizada de la tabla
            table_info: Información de la tabla
            
        Returns:
            List[Dict]: Lista de problemas encontrados
        """
        issues = []
        table_page = table_info.get('page', 'unknown')
        element_id = table_info.get('element_id')
        
        # Verificar que la tabla tiene filas
        if structure['total_rows'] == 0:
            issues.append({
                "checkpoint": "table-structure",
                "severity": "error",
                "description": "Tabla sin filas",
                "fix_description": "Añadir filas (TR) a la tabla",
                "fixable": True,
                "page": table_page,
                "element_id": element_id
            })
            return issues
        
        # Verificar que las filas tienen celdas
        empty_rows = [i for i, row in enumerate(structure['rows']) if len(row['cells']) == 0]
        if empty_rows:
            issues.append({
                "checkpoint": "table-structure",
                "severity": "warning",
                "description": f"Filas vacías encontradas: {len(empty_rows)} filas sin celdas",
                "fix_description": "Añadir celdas a las filas vacías o eliminar filas innecesarias",
                "fixable": True,
                "page": table_page,
                "element_id": element_id
            })
        
        # Verificar consistencia en número de columnas
        column_counts = [len(row['cells']) for row in structure['rows'] if row['cells']]
        if column_counts:
            min_cols = min(column_counts)
            max_cols = max(column_counts)
            
            if max_cols - min_cols > 1:  # Permitir variación de 1 columna
                issues.append({
                    "checkpoint": "table-structure",
                    "severity": "warning",
                    "description": f"Número inconsistente de columnas: de {min_cols} a {max_cols}",
                    "fix_description": "Revisar la estructura de la tabla para consistencia en columnas",
                    "fixable": True,
                    "page": table_page,
                    "element_id": element_id
                })
        
        # Verificar presencia de caption si es una tabla compleja
        if structure['total_rows'] > 3 or structure['max_columns'] > 3:
            if not structure['caption']:
                issues.append({
                    "checkpoint": "table-accessibility",
                    "severity": "info",
                    "description": "Tabla compleja sin título (Caption)",
                    "fix_description": "Añadir un título descriptivo (Caption) a la tabla",
                    "fixable": True,
                    "page": table_page,
                    "element_id": element_id
                })
        
        return issues
    
    def _validate_table_headers(self, structure: Dict, table_info: Dict) -> List[Dict]:
        """
        Valida las celdas de cabecera de la tabla.
        
        Args:
            structure: Estructura analizada de la tabla
            table_info: Información de la tabla
            
        Returns:
            List[Dict]: Lista de problemas encontrados
        """
        issues = []
        table_page = table_info.get('page', 'unknown')
        element_id = table_info.get('element_id')
        
        # Recopilar todas las celdas TH
        all_th_cells = []
        for row in structure['rows']:
            all_th_cells.extend(row['header_cells'])
        
        if not all_th_cells:
            # Tabla sin celdas de cabecera
            if structure['total_rows'] > 1 or structure['max_columns'] > 1:
                issues.append({
                    "checkpoint": "table-headers",
                    "severity": "warning",
                    "description": "Tabla sin celdas de cabecera (TH)",
                    "fix_description": "Convertir celdas apropiadas a celdas de cabecera (TH)",
                    "fixable": True,
                    "page": table_page,
                    "element_id": element_id
                })
            return issues
        
        # Validar cada celda TH
        for th_cell in all_th_cells:
            th_issues = self._validate_th_cell(th_cell, structure, table_info)
            issues.extend(th_issues)
        
        return issues
    
    def _validate_th_cell(self, th_cell: Dict, structure: Dict, table_info: Dict) -> List[Dict]:
        """
        Valida una celda de cabecera específica.
        
        Args:
            th_cell: Información de la celda TH
            structure: Estructura de la tabla
            table_info: Información de la tabla
            
        Returns:
            List[Dict]: Lista de problemas encontrados
        """
        issues = []
        table_page = table_info.get('page', 'unknown')
        cell_attributes = th_cell.get('attributes', {})
        cell_text = th_cell.get('text', '')
        
        # Checkpoint 15-003: Verificar atributo Scope
        if not self._uses_headers_id_system(structure):
            # Si no usa sistema Headers/ID, debe tener Scope
            scope_value = cell_attributes.get('scope', '').strip()
            
            if not scope_value:
                issues.append({
                    "checkpoint": "15-003",
                    "severity": "error",
                    "description": "Celda de cabecera (TH) sin atributo Scope",
                    "fix_description": "Añadir atributo Scope (Row, Col, Both) a la celda de cabecera",
                    "fixable": True,
                    "page": table_page,
                    "element_id": th_cell.get('element_id'),
                    "details": {
                        "cell_text": cell_text[:50] if cell_text else "(sin texto)",
                        "suggested_scope": self._suggest_scope_value(th_cell, structure)
                    }
                })
            elif scope_value not in self.valid_scope_values:
                issues.append({
                    "checkpoint": "15-003",
                    "severity": "error",
                    "description": f"Valor de Scope inválido: '{scope_value}'",
                    "fix_description": f"Usar un valor válido para Scope: {', '.join(sorted(self.valid_scope_values))}",
                    "fixable": True,
                    "page": table_page,
                    "element_id": th_cell.get('element_id'),
                    "details": {
                        "cell_text": cell_text[:50] if cell_text else "(sin texto)",
                        "invalid_scope": scope_value,
                        "valid_scopes": list(self.valid_scope_values)
                    }
                })
        
        # Verificar que la celda TH tiene contenido descriptivo
        if not th_cell.get('has_content'):
            issues.append({
                "checkpoint": "table-headers",
                "severity": "warning",
                "description": "Celda de cabecera (TH) sin contenido",
                "fix_description": "Añadir texto descriptivo a la celda de cabecera",
                "fixable": True,
                "page": table_page,
                "element_id": th_cell.get('element_id')
            })
        
        # Verificar ID si se usa sistema Headers/ID
        if self._uses_headers_id_system(structure):
            cell_id = cell_attributes.get('id', '').strip()
            if not cell_id:
                issues.append({
                    "checkpoint": "15-005",
                    "severity": "error",
                    "description": "Celda TH sin ID en tabla que usa sistema Headers/ID",
                    "fix_description": "Añadir ID único a la celda de cabecera",
                    "fixable": True,
                    "page": table_page,
                    "element_id": th_cell.get('element_id')
                })
        
        return issues
    
    def _validate_cell_accessibility(self, structure: Dict, table_info: Dict) -> List[Dict]:
        """
        Valida la accesibilidad de las celdas de datos.
        
        Args:
            structure: Estructura analizada de la tabla
            table_info: Información de la tabla
            
        Returns:
            List[Dict]: Lista de problemas encontrados
        """
        issues = []
        table_page = table_info.get('page', 'unknown')
        
        # Validar celdas TD en tablas complejas
        if self._is_complex_table(structure):
            for row in structure['rows']:
                for td_cell in row['data_cells']:
                    td_issues = self._validate_td_cell(td_cell, structure, table_info)
                    issues.extend(td_issues)
        
        # Validar sistema Headers/ID si se usa
        if self._uses_headers_id_system(structure):
            header_id_issues = self._validate_headers_id_system(structure, table_info)
            issues.extend(header_id_issues)
        
        return issues
    
    def _validate_td_cell(self, td_cell: Dict, structure: Dict, table_info: Dict) -> List[Dict]:
        """
        Valida una celda de datos específica.
        
        Args:
            td_cell: Información de la celda TD
            structure: Estructura de la tabla
            table_info: Información de la tabla
            
        Returns:
            List[Dict]: Lista de problemas encontrados
        """
        issues = []
        table_page = table_info.get('page', 'unknown')
        cell_attributes = td_cell.get('attributes', {})
        
        # Si es una tabla compleja y usa Headers/ID, verificar referencia
        if self._is_complex_table(structure) and self._uses_headers_id_system(structure):
            headers_attr = cell_attributes.get('headers', '').strip()
            if not headers_attr:
                issues.append({
                    "checkpoint": "15-005",
                    "severity": "warning",
                    "description": "Celda TD sin atributo Headers en tabla compleja",
                    "fix_description": "Añadir atributo Headers con IDs de las celdas de cabecera relacionadas",
                    "fixable": True,
                    "page": table_page,
                    "element_id": td_cell.get('element_id'),
                    "details": {
                        "cell_text": td_cell.get('text', '')[:50] if td_cell.get('text') else "(sin texto)"
                    }
                })
        
        return issues
    
    def _validate_headers_id_system(self, structure: Dict, table_info: Dict) -> List[Dict]:
        """
        Valida el sistema Headers/ID.
        
        Args:
            structure: Estructura analizada de la tabla
            table_info: Información de la tabla
            
        Returns:
            List[Dict]: Lista de problemas encontrados
        """
        issues = []
        table_page = table_info.get('page', 'unknown')
        
        # Verificar que todas las referencias Headers apuntan a IDs existentes
        for cell in structure['cells_with_headers_attr']:
            headers_attr = cell.get('attributes', {}).get('headers', '')
            referenced_ids = [id_ref.strip() for id_ref in headers_attr.split() if id_ref.strip()]
            
            for ref_id in referenced_ids:
                if ref_id not in structure['headers_by_id']:
                    issues.append({
                        "checkpoint": "15-005",
                        "severity": "error",
                        "description": f"Referencia Headers a ID inexistente: '{ref_id}'",
                        "fix_description": f"Crear celda TH con ID '{ref_id}' o corregir la referencia",
                        "fixable": True,
                        "page": table_page,
                        "element_id": cell.get('element_id'),
                        "details": {
                            "cell_text": cell.get('text', '')[:50] if cell.get('text') else "(sin texto)",
                            "missing_id": ref_id,
                            "available_ids": list(structure['headers_by_id'].keys())
                        }
                    })
        
        return issues
    
    def _validate_table_integrity(self, structure: Dict, table_info: Dict) -> List[Dict]:
        """
        Valida la integridad general de la tabla.
        
        Args:
            structure: Estructura analizada de la tabla
            table_info: Información de la tabla
            
        Returns:
            List[Dict]: Lista de problemas encontrados
        """
        issues = []
        table_page = table_info.get('page', 'unknown')
        element_id = table_info.get('element_id')
        
        # Verificar spanning de celdas (ColSpan, RowSpan)
        spanning_issues = self._validate_cell_spanning(structure, table_info)
        issues.extend(spanning_issues)
        
        # Verificar contenido mínimo
        total_cells_with_content = sum(
            len([cell for cell in row['cells'] if cell.get('has_content')])
            for row in structure['rows']
        )
        
        if total_cells_with_content == 0:
            issues.append({
                "checkpoint": "table-content",
                "severity": "error",
                "description": "Tabla completamente vacía",
                "fix_description": "Añadir contenido a las celdas de la tabla",
                "fixable": True,
                "page": table_page,
                "element_id": element_id
            })
        
        return issues
    
    def _validate_cell_spanning(self, structure: Dict, table_info: Dict) -> List[Dict]:
        """
        Valida el spanning (ColSpan, RowSpan) de celdas.
        
        Args:
            structure: Estructura analizada de la tabla
            table_info: Información de la tabla
            
        Returns:
            List[Dict]: Lista de problemas encontrados
        """
        issues = []
        table_page = table_info.get('page', 'unknown')
        
        for row in structure['rows']:
            for cell in row['cells']:
                attributes = cell.get('attributes', {})
                
                # Validar ColSpan
                colspan = attributes.get('colspan')
                if colspan:
                    try:
                        colspan_value = int(colspan)
                        if colspan_value <= 0 or colspan_value > structure['max_columns']:
                            issues.append({
                                "checkpoint": "table-spanning",
                                "severity": "error",
                                "description": f"Valor ColSpan inválido: {colspan}",
                                "fix_description": f"Usar un valor válido para ColSpan (1 a {structure['max_columns']})",
                                "fixable": True,
                                "page": table_page,
                                "element_id": cell.get('element_id')
                            })
                    except ValueError:
                        issues.append({
                            "checkpoint": "table-spanning",
                            "severity": "error",
                            "description": f"Valor ColSpan no numérico: {colspan}",
                            "fix_description": "Usar un valor numérico para ColSpan",
                            "fixable": True,
                            "page": table_page,
                            "element_id": cell.get('element_id')
                        })
                
                # Validar RowSpan
                rowspan = attributes.get('rowspan')
                if rowspan:
                    try:
                        rowspan_value = int(rowspan)
                        if rowspan_value <= 0 or rowspan_value > structure['total_rows']:
                            issues.append({
                                "checkpoint": "table-spanning",
                                "severity": "error",
                                "description": f"Valor RowSpan inválido: {rowspan}",
                                "fix_description": f"Usar un valor válido para RowSpan (1 a {structure['total_rows']})",
                                "fixable": True,
                                "page": table_page,
                                "element_id": cell.get('element_id')
                            })
                    except ValueError:
                        issues.append({
                            "checkpoint": "table-spanning",
                            "severity": "error",
                            "description": f"Valor RowSpan no numérico: {rowspan}",
                            "fix_description": "Usar un valor numérico para RowSpan",
                            "fixable": True,
                            "page": table_page,
                            "element_id": cell.get('element_id')
                        })
        
        return issues
    
    # Métodos auxiliares
    
    def _uses_headers_id_system(self, structure: Dict) -> bool:
        """Determina si la tabla usa el sistema Headers/ID."""
        return len(structure['cells_with_headers_attr']) > 0 or len(structure['headers_by_id']) > 0
    
    def _is_complex_table(self, structure: Dict) -> bool:
        """Determina si es una tabla compleja."""
        # Criterios para tabla compleja:
        # - Más de una fila de cabecera
        # - Celdas con spanning
        # - Más de 3x3
        
        if structure['total_rows'] > 3 and structure['max_columns'] > 3:
            return True
        
        # Verificar múltiples filas de cabecera
        header_rows_count = len(structure['header_rows'])
        if header_rows_count > 1:
            return True
        
        # Verificar spanning
        for row in structure['rows']:
            for cell in row['cells']:
                attributes = cell.get('attributes', {})
                if attributes.get('colspan') or attributes.get('rowspan'):
                    return True
        
        return False
    
    def _suggest_scope_value(self, th_cell: Dict, structure: Dict) -> str:
        """Sugiere un valor apropiado para el atributo Scope."""
        # Análisis básico para sugerir Scope
        # En una implementación completa, se analizaría la posición de la celda
        
        # Por ahora, sugerencia básica
        if structure['total_rows'] > structure['max_columns']:
            return "Col"  # Tabla más alta que ancha, probablemente cabeceras de columna
        else:
            return "Row"  # Tabla más ancha que alta, probablemente cabeceras de fila