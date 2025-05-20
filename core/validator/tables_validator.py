#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Validación de tablas según PDF/UA y Matterhorn Protocol.
Verifica estructura, cabeceras, atributos y relaciones semánticas.

Este módulo implementa validaciones para los siguientes checkpoints Matterhorn:
- 15-001: Filas con celdas de cabecera no etiquetadas como cabeceras
- 15-002: Columnas con celdas de cabecera no etiquetadas como cabeceras
- 15-003: Celdas TH sin atributo Scope en tablas sin Headers/ID
- 15-004: Contenido etiquetado como tabla pero sin estructura de filas/columnas
- 15-005: Cabeceras de celdas que no pueden determinarse inequívocamente
"""

from typing import Dict, List, Optional, Any, Set, Tuple, Union
from collections import defaultdict
import re
from loguru import logger

class TablesValidator:
    """
    Valida las tablas del documento según requisitos de PDF/UA.
    Verifica estructura, cabeceras, relaciones y atributos necesarios.
    """
    
    def __init__(self):
        """Inicializa el validador de tablas"""
        self.pdf_loader = None
        # Definir estructuras de tabla válidas según ISO 32000-1
        self.valid_table_children = ["TR", "THead", "TBody", "TFoot", "Caption"]
        self.valid_row_children = ["TH", "TD"]
        self.valid_header_scopes = ["Row", "Column", "Both"]
        # Umbral para considerar celdas inconsistentes
        self.row_cells_threshold = 0.75  # 75% de celdas deben tener consistencia
        logger.info("TablesValidator inicializado")
    
    def set_pdf_loader(self, pdf_loader):
        """
        Establece la referencia al cargador de PDF.
        
        Args:
            pdf_loader: Instancia de PDFLoader con el documento cargado
        """
        self.pdf_loader = pdf_loader
        logger.debug("PDFLoader establecido en TablesValidator")
    
    def validate(self, structure_tree: Dict) -> List[Dict]:
        """
        Valida todas las tablas en la estructura.
        
        Args:
            structure_tree: Diccionario representando la estructura lógica
            
        Returns:
            List[Dict]: Lista de problemas detectados
            
        Referencias:
            - Matterhorn: 15-001 a 15-005 (tablas)
            - Tagged PDF: 4.2.6 (Table, TR, TH, TD), 5.4 (Table attributes)
        """
        issues = []
        
        # Si no hay estructura, no hay tablas para validar
        if not structure_tree or not structure_tree.get("children"):
            logger.info("No hay estructura para validar tablas")
            return issues
        
        # Encontrar todas las tablas en la estructura
        tables = self._find_tables(structure_tree.get("children", []))
        
        if not tables:
            logger.info("No se encontraron tablas en el documento")
            return issues
        
        logger.info(f"Encontradas {len(tables)} tablas para validar")
        
        # Validar cada tabla
        for table_idx, table in enumerate(tables):
            logger.debug(f"Validando tabla {table_idx+1}/{len(tables)}")
            table_issues = self._validate_table(table)
            issues.extend(table_issues)
        
        logger.info(f"Validación de tablas completada: {len(issues)} problemas encontrados")
        return issues
    
    def _find_tables(self, elements: List[Dict], path: str = "") -> List[Dict]:
        """
        Encuentra todas las tablas en la estructura de forma recursiva.
        
        Args:
            elements: Lista de elementos de estructura
            path: Ruta de anidamiento actual
            
        Returns:
            List[Dict]: Lista de tablas encontradas con información de contexto
        """
        tables = []
        
        for i, element in enumerate(elements):
            element_type = element.get("type", "")
            current_path = f"{path}/{i}:{element_type}"
            
            if element_type == "Table":
                # Añadir información de contexto a la tabla
                table_info = dict(element)
                table_info["_path"] = current_path
                table_info["_index"] = i
                tables.append(table_info)
            
            # Buscar tablas en los hijos
            if element.get("children"):
                child_tables = self._find_tables(element["children"], current_path)
                tables.extend(child_tables)
        
        return tables
    
    def _validate_table(self, table: Dict) -> List[Dict]:
        """
        Valida una tabla específica según criterios PDF/UA.
        
        Args:
            table: Diccionario representando una tabla con información de contexto
            
        Returns:
            List[Dict]: Lista de problemas detectados
        """
        issues = []
        table_path = table.get("_path", "")
        table_page = table.get("page", 0)
        table_id = table.get("id", f"table_{table.get('_index', 0)}")
        
        # Validar existencia de hijos
        if not table.get("children"):
            issues.append({
                "checkpoint": "15-004",
                "severity": "error",
                "description": "Tabla vacía sin estructura interna",
                "fix_description": "Añadir estructura de filas y celdas a la tabla o eliminarla",
                "fixable": True,
                "page": table_page,
                "path": table_path,
                "element_id": table_id,
                "element_type": "Table"
            })
            return issues
        
        # Verificar estructura de la tabla (CHECKPOINT 15-004, relacionado con 09-004)
        structure_issues = self._validate_table_structure(table)
        issues.extend(structure_issues)
        
        # Si hay problemas estructurales graves, no seguir validando
        if any(issue.get("checkpoint") == "15-004" for issue in structure_issues):
            return issues
        
        # Extraer todas las filas (TR) de la tabla, incluyendo las que están en THead/TBody/TFoot
        rows = self._extract_table_rows(table)
        
        if not rows:
            issues.append({
                "checkpoint": "15-004",
                "severity": "error",
                "description": "Tabla sin filas (TR)",
                "fix_description": "Añadir filas (TR) a la tabla",
                "fixable": True,
                "page": table_page,
                "path": table_path,
                "element_id": table_id,
                "element_type": "Table"
            })
            return issues
        
        # Analizar la estructura de filas y columnas
        row_analysis = self._analyze_table_rows(rows)
        
        # Validar consistencia de filas/columnas (CHECKPOINT 15-004)
        consistency_issues = self._validate_row_consistency(row_analysis, table)
        issues.extend(consistency_issues)
        
        # Validar celdas de cabecera (CHECKPOINTS 15-001, 15-002, 15-003)
        header_issues = self._validate_header_cells(row_analysis, table)
        issues.extend(header_issues)
        
        # Validar relaciones cabecera-celda (CHECKPOINT 15-005)
        relation_issues = self._validate_header_cell_relations(row_analysis, table)
        issues.extend(relation_issues)
        
        return issues
    
    def _validate_table_structure(self, table: Dict) -> List[Dict]:
        """
        Valida la estructura básica de la tabla según PDF/UA.
        
        Args:
            table: Información de la tabla
            
        Returns:
            List[Dict]: Problemas detectados en la estructura
        """
        issues = []
        table_path = table.get("_path", "")
        table_page = table.get("page", 0)
        table_id = table.get("id", f"table_{table.get('_index', 0)}")
        
        # Contar tipos de elementos hijo
        children_types = [child.get("type", "") for child in table.get("children", [])]
        
        # Verificar que los hijos son válidos para una tabla
        invalid_children = [t for t in children_types if t not in self.valid_table_children]
        if invalid_children:
            issues.append({
                "checkpoint": "09-004",  # Relacionado con 15-004
                "severity": "error",
                "description": f"Estructura de tabla incorrecta: contiene elementos no válidos: {', '.join(invalid_children)}",
                "fix_description": "Corregir la estructura de la tabla usando elementos válidos (TR, THead, TBody, TFoot, Caption)",
                "fixable": True,
                "page": table_page,
                "path": table_path,
                "element_id": table_id,
                "element_type": "Table",
                "details": {
                    "invalid_elements": invalid_children,
                    "valid_elements": self.valid_table_children
                }
            })
        
        # Verificar si tiene estructura mínima para ser una tabla real
        if not any(t in ["TR", "THead", "TBody", "TFoot"] for t in children_types):
            issues.append({
                "checkpoint": "15-004",
                "severity": "error",
                "description": "Contenido etiquetado como tabla sin estructura de filas",
                "fix_description": "Añadir estructura de filas a la tabla o usar un tipo de estructura más apropiado",
                "fixable": True,
                "page": table_page,
                "path": table_path,
                "element_id": table_id,
                "element_type": "Table"
            })
        
        return issues
    
    def _extract_table_rows(self, table: Dict) -> List[Dict]:
        """
        Extrae todas las filas de la tabla, incluyendo las que están en secciones.
        
        Args:
            table: Información de la tabla
            
        Returns:
            List[Dict]: Lista de filas con información contextual
        """
        rows = []
        row_index = 0
        
        for section_idx, child in enumerate(table.get("children", [])):
            child_type = child.get("type", "")
            
            if child_type == "TR":
                # Es una fila directa
                row_info = dict(child)
                row_info["_section_type"] = "Table"
                row_info["_section_idx"] = section_idx
                row_info["_row_idx"] = row_index
                rows.append(row_info)
                row_index += 1
                
            elif child_type in ["THead", "TBody", "TFoot"]:
                # Es una sección que contiene filas
                section_rows = []
                for sub_idx, subchild in enumerate(child.get("children", [])):
                    if subchild.get("type") == "TR":
                        row_info = dict(subchild)
                        row_info["_section_type"] = child_type
                        row_info["_section_idx"] = section_idx
                        row_info["_sub_idx"] = sub_idx
                        row_info["_row_idx"] = row_index
                        section_rows.append(row_info)
                        row_index += 1
                
                rows.extend(section_rows)
        
        return rows
    
    def _analyze_table_rows(self, rows: List[Dict]) -> Dict:
        """
        Analiza las filas de una tabla para obtener información detallada.
        
        Args:
            rows: Lista de filas con información contextual
            
        Returns:
            Dict: Análisis de la estructura de filas y celdas
        """
        analysis = {
            "row_count": len(rows),
            "rows": [],
            "has_headers": False,
            "has_scope": False,
            "has_headers_id": False,
            "column_count": 0,
            "max_cell_count": 0,
            "min_cell_count": float('inf'),
            "header_rows": [],
            "header_columns": []
        }
        
        # Análisis por fila
        cell_counts = []
        for row_idx, row in enumerate(rows):
            row_analysis = self._analyze_row(row, row_idx)
            analysis["rows"].append(row_analysis)
            
            # Actualizar estadísticas
            cell_counts.append(row_analysis["cell_count"])
            analysis["max_cell_count"] = max(analysis["max_cell_count"], row_analysis["cell_count"])
            analysis["min_cell_count"] = min(analysis["min_cell_count"], row_analysis["cell_count"])
            
            # Actualizar si tiene cabeceras
            if row_analysis["has_headers"]:
                analysis["has_headers"] = True
            
            # Verificar si es una fila de cabecera (todas o mayoría de celdas son TH)
            if row_analysis["header_ratio"] > 0.5:
                analysis["header_rows"].append(row_idx)
            
            # Verificar atributos
            if row_analysis["has_scope"]:
                analysis["has_scope"] = True
            
            if row_analysis["has_headers_id"]:
                analysis["has_headers_id"] = True
        
        # Corregir min_cell_count si no hay celdas
        if analysis["min_cell_count"] == float('inf'):
            analysis["min_cell_count"] = 0
        
        # Determinar número de columnas (moda de conteo de celdas)
        if cell_counts:
            from collections import Counter
            counter = Counter(cell_counts)
            analysis["column_count"] = counter.most_common(1)[0][0]
        
        # Identificar columnas de cabecera
        self._identify_header_columns(analysis)
        
        return analysis
    
    def _analyze_row(self, row: Dict, row_idx: int) -> Dict:
        """
        Analiza una fila para obtener información sobre sus celdas.
        
        Args:
            row: Información de la fila
            row_idx: Índice de la fila
            
        Returns:
            Dict: Análisis de la fila
        """
        cells = [cell for cell in row.get("children", []) if cell.get("type") in self.valid_row_children]
        
        # Contar tipos de celdas
        th_cells = [cell for cell in cells if cell.get("type") == "TH"]
        td_cells = [cell for cell in cells if cell.get("type") == "TD"]
        
        # Verificar atributos Scope en TH
        scope_cells = [cell for cell in th_cells if self._has_attribute(cell, "scope")]
        
        # Verificar atributos Headers/ID
        headers_cells = [cell for cell in cells if self._has_attribute(cell, "headers")]
        id_cells = [cell for cell in cells if self._has_attribute(cell, "id")]
        
        # Calcular ratio de cabeceras
        header_ratio = len(th_cells) / max(len(cells), 1)
        
        # Analizar uso de colspan/rowspan
        colspan_sum = sum(int(self._get_attribute_value(cell, "colspan") or 1) for cell in cells)
        rowspan_sum = sum(int(self._get_attribute_value(cell, "rowspan") or 1) for cell in cells)
        
        return {
            "row_idx": row_idx,
            "cell_count": len(cells),
            "th_count": len(th_cells),
            "td_count": len(td_cells),
            "has_headers": len(th_cells) > 0,
            "has_scope": len(scope_cells) > 0,
            "has_headers_id": len(headers_cells) > 0 or len(id_cells) > 0,
            "scope_ratio": len(scope_cells) / max(len(th_cells), 1),
            "header_ratio": header_ratio,
            "cells": cells,
            "th_cells": th_cells,
            "td_cells": td_cells,
            "colspan_sum": colspan_sum,
            "rowspan_sum": rowspan_sum,
            "is_header_row": header_ratio > 0.5,
            "section_type": row.get("_section_type", "Table")
        }
    
    def _identify_header_columns(self, analysis: Dict):
        """
        Identifica qué columnas contienen mayoritariamente celdas de cabecera.
        
        Args:
            analysis: Análisis previo de la tabla
        """
        # Si no hay filas, no hay columnas
        if not analysis["rows"]:
            return
        
        column_counts = {}
        header_counts = {}
        
        # Contar celdas por columna
        for row in analysis["rows"]:
            cells = row["cells"]
            col_idx = 0
            
            for cell in cells:
                cell_type = cell.get("type", "")
                # Considerar colspan
                colspan = int(self._get_attribute_value(cell, "colspan") or 1)
                
                # Actualizar conteos para cada columna que abarca la celda
                for i in range(colspan):
                    curr_col = col_idx + i
                    column_counts[curr_col] = column_counts.get(curr_col, 0) + 1
                    if cell_type == "TH":
                        header_counts[curr_col] = header_counts.get(curr_col, 0) + 1
                
                col_idx += colspan
        
        # Determinar qué columnas son de cabecera (mayoría de celdas son TH)
        for col_idx in column_counts:
            if header_counts.get(col_idx, 0) / column_counts[col_idx] > 0.5:
                analysis["header_columns"].append(col_idx)
    
    def _validate_row_consistency(self, analysis: Dict, table: Dict) -> List[Dict]:
        """
        Valida la consistencia de las filas en la tabla.
        
        Args:
            analysis: Análisis de la estructura de la tabla
            table: Información de la tabla
            
        Returns:
            List[Dict]: Problemas detectados en la consistencia de filas
        """
        issues = []
        table_path = table.get("_path", "")
        table_page = table.get("page", 0)
        table_id = table.get("id", f"table_{table.get('_index', 0)}")
        
        # Verificar consistencia en número de celdas
        if analysis["row_count"] > 1:
            # Calcular cuántas filas tienen un número consistente de celdas/columnas
            expected_cells = analysis["column_count"]
            consistent_rows = 0
            inconsistent_rows = []
            
            for row_idx, row_data in enumerate(analysis["rows"]):
                # Considerar colspan para calcular celdas efectivas
                effective_cells = row_data["colspan_sum"]
                
                if effective_cells == expected_cells:
                    consistent_rows += 1
                else:
                    inconsistent_rows.append({
                        "row_idx": row_idx,
                        "expected": expected_cells,
                        "actual": effective_cells
                    })
            
            # Si menos del umbral de filas tienen el mismo número de celdas, reportar problema
            consistency_ratio = consistent_rows / analysis["row_count"]
            if consistency_ratio < self.row_cells_threshold and inconsistent_rows:
                issues.append({
                    "checkpoint": "15-004",
                    "severity": "warning",
                    "description": f"Tabla con número inconsistente de celdas en {len(inconsistent_rows)} filas",
                    "fix_description": "Corregir la estructura de la tabla para tener igual número de celdas efectivas en cada fila",
                    "fixable": True,
                    "page": table_page,
                    "path": table_path,
                    "element_id": table_id,
                    "element_type": "Table",
                    "details": {
                        "expected_cells": expected_cells,
                        "consistency_ratio": consistency_ratio,
                        "inconsistent_rows": inconsistent_rows
                    }
                })
        
        return issues
    
    def _validate_header_cells(self, analysis: Dict, table: Dict) -> List[Dict]:
        """
        Valida las celdas de cabecera en la tabla (Checkpoints 15-001, 15-002, 15-003).
        
        Args:
            analysis: Análisis de la estructura de la tabla
            table: Información de la tabla
            
        Returns:
            List[Dict]: Problemas detectados en las celdas de cabecera
        """
        issues = []
        table_path = table.get("_path", "")
        table_page = table.get("page", 0)
        table_id = table.get("id", f"table_{table.get('_index', 0)}")
        
        # Si no hay filas, no hay celdas para validar
        if not analysis["rows"]:
            return issues
        
        # Verificar atributos Scope en celdas TH (Checkpoint 15-003)
        if analysis["has_headers"] and not analysis["has_headers_id"]:
            for row_idx, row_data in enumerate(analysis["rows"]):
                if row_data["has_headers"] and row_data["scope_ratio"] < 1.0:
                    # Identificar celdas TH sin Scope
                    for cell_idx, cell in enumerate(row_data["th_cells"]):
                        if not self._has_attribute(cell, "scope"):
                            cell_id = cell.get("id", f"cell_{row_idx}_{cell_idx}")
                            issues.append({
                                "checkpoint": "15-003",
                                "severity": "error",
                                "description": "Celda de cabecera <TH> sin atributo Scope",
                                "fix_description": f"Añadir atributo Scope a la celda de cabecera (Row, Column o Both)",
                                "fixable": True,
                                "page": table_page,
                                "path": f"{table_path}/row{row_idx}/cell{cell_idx}",
                                "element_id": cell_id,
                                "element_type": "TH"
                            })
        
        # Verificar si hay celdas no marcadas correctamente como cabecera
        # Checkpoint 15-001: Fila con cabecera no etiquetada como cabecera
        for row_idx in analysis["header_rows"]:
            row_data = analysis["rows"][row_idx]
            if row_data["header_ratio"] < 1.0:
                # Hay celdas en esta fila de cabecera que no son TH
                for cell_idx, cell in enumerate(row_data["td_cells"]):
                    # Solo reportar si está en la primera fila o en THead
                    if row_idx == 0 or row_data["section_type"] == "THead":
                        cell_id = cell.get("id", f"cell_{row_idx}_{cell_idx}")
                        issues.append({
                            "checkpoint": "15-001",
                            "severity": "warning",
                            "description": "Celda de cabecera no etiquetada como <TH> en fila de cabecera",
                            "fix_description": "Cambiar la etiqueta de la celda de TD a TH",
                            "fixable": True,
                            "page": table_page,
                            "path": f"{table_path}/row{row_idx}/cell{cell_idx}",
                            "element_id": cell_id,
                            "element_type": "TD"
                        })
        
        # Checkpoint 15-002: Columna con cabecera no etiquetada como cabecera
        for col_idx in analysis["header_columns"]:
            # Buscar celdas TD en columnas de cabecera
            for row_idx, row_data in enumerate(analysis["rows"]):
                if row_idx == 0:
                    continue  # Ya validado en 15-001
                    
                # Encontrar la celda en esta columna
                col_counter = 0
                for cell_idx, cell in enumerate(row_data["cells"]):
                    cell_type = cell.get("type", "")
                    colspan = int(self._get_attribute_value(cell, "colspan") or 1)
                    
                    # Verificar si esta celda abarca la columna de interés
                    if col_counter <= col_idx < col_counter + colspan:
                        if cell_type == "TD":
                            cell_id = cell.get("id", f"cell_{row_idx}_{cell_idx}")
                            issues.append({
                                "checkpoint": "15-002",
                                "severity": "warning",
                                "description": f"Celda de cabecera no etiquetada como <TH> en columna de cabecera",
                                "fix_description": "Cambiar la etiqueta de la celda de TD a TH",
                                "fixable": True,
                                "page": table_page,
                                "path": f"{table_path}/row{row_idx}/cell{cell_idx}",
                                "element_id": cell_id,
                                "element_type": "TD"
                            })
                        break
                    col_counter += colspan
        
        return issues
    
    def _validate_header_cell_relations(self, analysis: Dict, table: Dict) -> List[Dict]:
        """
        Valida las relaciones entre celdas de cabecera y datos (Checkpoint 15-005).
        
        Args:
            analysis: Análisis de la estructura de la tabla
            table: Información de la tabla
            
        Returns:
            List[Dict]: Problemas detectados en las relaciones de cabecera
        """
        issues = []
        table_path = table.get("_path", "")
        table_page = table.get("page", 0)
        table_id = table.get("id", f"table_{table.get('_index', 0)}")
        
        # Verificar relaciones de cabecera-celda solo si hay cabeceras
        if not analysis["has_headers"]:
            return issues
        
        # Si hay cabeceras pero no hay Scope ni Headers/ID, reportar problema
        if analysis["has_headers"] and not analysis["has_scope"] and not analysis["has_headers_id"]:
            issues.append({
                "checkpoint": "15-005",
                "severity": "error",
                "description": "No se puede determinar inequívocamente la cabecera de las celdas",
                "fix_description": "Añadir atributos Scope en celdas TH o relaciones Headers/ID entre celdas",
                "fixable": True,
                "page": table_page,
                "path": table_path,
                "element_id": table_id,
                "element_type": "Table"
            })
        
        # Verificar que los valores de Scope son válidos
        for row_idx, row_data in enumerate(analysis["rows"]):
            for cell_idx, cell in enumerate(row_data["th_cells"]):
                scope_value = self._get_attribute_value(cell, "scope")
                if scope_value and scope_value not in self.valid_header_scopes:
                    cell_id = cell.get("id", f"cell_{row_idx}_{cell_idx}")
                    issues.append({
                        "checkpoint": "15-003",
                        "severity": "error",
                        "description": f"Valor de Scope no válido en celda TH: '{scope_value}'",
                        "fix_description": f"Usar un valor válido para Scope: {', '.join(self.valid_header_scopes)}",
                        "fixable": True,
                        "page": table_page,
                        "path": f"{table_path}/row{row_idx}/cell{cell_idx}",
                        "element_id": cell_id,
                        "element_type": "TH"
                    })
        
        # Verificar integridad de referencias Headers/ID
        if analysis["has_headers_id"]:
            # Recopilar todos los IDs disponibles
            all_ids = {}
            for row_idx, row_data in enumerate(analysis["rows"]):
                for cell_idx, cell in enumerate(row_data["cells"]):
                    cell_id = self._get_attribute_value(cell, "id")
                    if cell_id:
                        all_ids[cell_id] = {"row": row_idx, "col": cell_idx, "cell": cell}
            
            # Verificar que las referencias Headers apuntan a IDs válidos
            for row_idx, row_data in enumerate(analysis["rows"]):
                for cell_idx, cell in enumerate(row_data["cells"]):
                    headers_value = self._get_attribute_value(cell, "headers")
                    if headers_value:
                        # Headers puede ser una cadena de IDs separados por espacios
                        header_ids = headers_value.split()
                        invalid_ids = [h_id for h_id in header_ids if h_id not in all_ids]
                        
                        if invalid_ids:
                            cell_id = cell.get("id", f"cell_{row_idx}_{cell_idx}")
                            issues.append({
                                "checkpoint": "15-005",
                                "severity": "error",
                                "description": f"Referencias inválidas en atributo Headers: {', '.join(invalid_ids)}",
                                "fix_description": "Corregir las referencias del atributo Headers para que apunten a IDs válidos",
                                "fixable": True,
                                "page": table_page,
                                "path": f"{table_path}/row{row_idx}/cell{cell_idx}",
                                "element_id": cell_id,
                                "element_type": cell.get("type", "")
                            })
        
        return issues
    
    def _has_attribute(self, element: Dict, attribute: str) -> bool:
        """
        Verifica si un elemento tiene un atributo específico.
        
        Args:
            element: Elemento a verificar
            attribute: Nombre del atributo
            
        Returns:
            bool: True si el atributo existe y tiene valor
        """
        # Buscar en diferentes ubicaciones posibles del atributo
        # 1. Directamente en el elemento
        if attribute in element and element[attribute]:
            return True
        
        # 2. En el diccionario de atributos
        if "attributes" in element and attribute in element["attributes"] and element["attributes"][attribute]:
            return True
        
        # 3. En el objeto pikepdf original si está disponible
        if "element" in element and hasattr(element["element"], attribute):
            attr_value = getattr(element["element"], attribute)
            return attr_value is not None and attr_value != ""
        
        return False
    
    def _get_attribute_value(self, element: Dict, attribute: str) -> Any:
        """
        Obtiene el valor de un atributo.
        
        Args:
            element: Elemento del que obtener el atributo
            attribute: Nombre del atributo
            
        Returns:
            Any: Valor del atributo o None si no existe
        """
        # 1. Directamente en el elemento
        if attribute in element:
            return element[attribute]
        
        # 2. En el diccionario de atributos
        if "attributes" in element and attribute in element["attributes"]:
            return element["attributes"][attribute]
        
        # 3. En el objeto pikepdf original si está disponible
        if "element" in element and hasattr(element["element"], attribute):
            return getattr(element["element"], attribute)
        
        return None