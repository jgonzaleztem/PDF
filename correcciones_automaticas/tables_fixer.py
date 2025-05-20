#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Corrección automática de tablas según PDF/UA.
Añade Scope, Headers y estructura lógica a tablas.
"""

from typing import Dict, List, Optional, Any
from loguru import logger

class TablesFixer:
    """
    Clase para corregir tablas según PDF/UA.
    Añade Scope en TH, genera estructura THead/TBody y reestructura tablas.
    """
    
    def __init__(self, pdf_writer=None):
        """
        Inicializa el corrector de tablas.
        
        Args:
            pdf_writer: Instancia opcional de PDFWriter
        """
        self.pdf_writer = pdf_writer
        logger.info("TablesFixer inicializado")
    
    def set_pdf_writer(self, pdf_writer):
        """Establece el escritor de PDF a utilizar"""
        self.pdf_writer = pdf_writer
    
    def fix_all_tables(self, structure_tree: Dict) -> bool:
        """
        Corrige todas las tablas en la estructura.
        
        Args:
            structure_tree: Diccionario representando la estructura lógica
            
        Returns:
            bool: True si se realizaron correcciones
            
        Referencias:
            - Matterhorn: 15-001, 15-003, 15-005
            - Tagged PDF: 4.2.6, 5.4.1 (Scope, Headers)
        """
        try:
            if self.pdf_writer is None:
                logger.error("No hay PDFWriter configurado para aplicar correcciones")
                return False
            
            if not structure_tree or not structure_tree.get("children"):
                logger.warning("No hay estructura para corregir tablas")
                return False
            
            # Buscar todas las tablas en la estructura
            tables = self._find_tables(structure_tree.get("children", []))
            
            if not tables:
                logger.info("No se encontraron tablas para corregir")
                return False
            
            logger.info(f"Encontradas {len(tables)} tablas para procesar")
            
            changes_made = False
            
            # Procesar cada tabla
            for table in tables:
                table_fixed = False
                
                # Añadir Scope a celdas TH si es necesario
                scope_fixed = self._fix_th_scope(table)
                if scope_fixed:
                    table_fixed = True
                
                # Generar estructura THead/TBody si es apropiado
                thead_fixed = self._add_thead_tbody(table)
                if thead_fixed:
                    table_fixed = True
                
                # Otras correcciones de tabla
                table_structure_fixed = self._fix_table_structure(table)
                if table_structure_fixed:
                    table_fixed = True
                
                changes_made = changes_made or table_fixed
            
            return changes_made
            
        except Exception as e:
            logger.exception(f"Error al corregir tablas: {e}")
            return False
    
    def add_scope_attribute(self, th_id: str, scope_value: str) -> bool:
        """
        Añade atributo Scope a una celda TH.
        
        Args:
            th_id: Identificador de la celda TH
            scope_value: Valor del atributo Scope ('Row' o 'Column')
            
        Returns:
            bool: True si se realizó la corrección
            
        Referencias:
            - Matterhorn: 15-003
            - Tagged PDF: 5.4.1 (Scope)
        """
        try:
            if self.pdf_writer is None:
                logger.error("No hay PDFWriter configurado para aplicar correcciones")
                return False
            
            logger.info(f"Añadiendo Scope='{scope_value}' a celda TH {th_id}")
            return self.pdf_writer.update_tag_attribute(th_id, "scope", scope_value)
            
        except Exception as e:
            logger.exception(f"Error al añadir Scope a celda TH {th_id}: {e}")
            return False
    
    def add_headers_id_attributes(self, table_id: str, cell_mappings: Dict[str, List[str]]) -> bool:
        """
        Añade atributos Headers e ID para relaciones complejas en tabla.
        
        Args:
            table_id: Identificador de la tabla
            cell_mappings: Diccionario con mapeos de celdas y sus cabeceras
            
        Returns:
            bool: True si se realizaron correcciones
            
        Referencias:
            - Matterhorn: 15-005
            - Tagged PDF: 5.4.1 (Headers, ID)
        """
        try:
            if self.pdf_writer is None:
                logger.error("No hay PDFWriter configurado para aplicar correcciones")
                return False
            
            changes_made = False
            
            # Aplicar ID a celdas cabecera
            for cell_id, headers in cell_mappings.items():
                # Añadir atributo Headers con referencias a IDs
                if headers:
                    headers_str = " ".join(headers)
                    self.pdf_writer.update_tag_attribute(cell_id, "headers", headers_str)
                    logger.info(f"Añadido Headers='{headers_str}' a celda {cell_id}")
                    changes_made = True
            
            return changes_made
            
        except Exception as e:
            logger.exception(f"Error al añadir Headers/ID a tabla {table_id}: {e}")
            return False
    
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
                element["_path"] = current_path
                tables.append(element)
            
            # Buscar tablas en los hijos
            if element.get("children"):
                child_tables = self._find_tables(element["children"], current_path)
                tables.extend(child_tables)
        
        return tables
    
    def _fix_th_scope(self, table: Dict) -> bool:
        """
        Añade atributo Scope a celdas TH.
        
        Args:
            table: Diccionario representando una tabla
            
        Returns:
            bool: True si se realizaron correcciones
        """
        changes_made = False
        
        # Extraer filas
        rows = []
        for child in table.get("children", []):
            if child.get("type") == "TR":
                rows.append(child)
            elif child.get("type") in ["THead", "TBody", "TFoot"]:
                for subchild in child.get("children", []):
                    if subchild.get("type") == "TR":
                        rows.append(subchild)
        
        # Procesar celdas TH
        for row_idx, row in enumerate(rows):
            cells = [cell for cell in row.get("children", []) if cell.get("type") in ["TH", "TD"]]
            
            for cell_idx, cell in enumerate(cells):
                if cell.get("type") == "TH" and not cell.get("scope"):
                    # Determinar si es cabecera de fila o columna
                    scope_value = self._determine_scope_value(row_idx, cell_idx, rows)
                    
                    # Añadir Scope
                    cell_id = cell.get("id", f"unknown-{row_idx}-{cell_idx}")
                    self.add_scope_attribute(cell_id, scope_value)
                    changes_made = True
        
        return changes_made
    
    def _determine_scope_value(self, row_idx: int, cell_idx: int, rows: List[Dict]) -> str:
        """
        Determina el valor apropiado para el atributo Scope.
        
        Args:
            row_idx: Índice de la fila
            cell_idx: Índice de la celda
            rows: Lista de filas
            
        Returns:
            str: Valor para Scope ('Row' o 'Column')
        """
        # Heurística para determinar si es cabecera de fila o columna
        if row_idx == 0:
            # Primera fila, probablemente cabecera de columna
            return "Column"
        elif cell_idx == 0:
            # Primera columna, probablemente cabecera de fila
            return "Row"
        
        # Analizar contexto para decidir
        # Si hay más TH en la misma fila, probablemente sean cabeceras de columna
        # Si hay más TH en la misma columna, probablemente sean cabeceras de fila
        row_th_count = len([c for c in rows[row_idx].get("children", []) if c.get("type") == "TH"])
        
        # Contar TH en la misma columna
        col_th_count = 0
        for r in rows:
            cells = [c for c in r.get("children", []) if c.get("type") in ["TH", "TD"]]
            if cell_idx < len(cells) and cells[cell_idx].get("type") == "TH":
                col_th_count += 1
        
        return "Column" if row_th_count >= col_th_count else "Row"
    
    def _add_thead_tbody(self, table: Dict) -> bool:
        """
        Genera estructura THead/TBody si es apropiado.
        
        Args:
            table: Diccionario representando una tabla
            
        Returns:
            bool: True si se realizaron correcciones
        """
        # Verificar si ya tiene THead/TBody
        children_types = [child.get("type", "") for child in table.get("children", [])]
        if "THead" in children_types or "TBody" in children_types:
            return False
        
        # Verificar que haya filas directas
        rows = [child for child in table.get("children", []) if child.get("type") == "TR"]
        if not rows:
            return False
        
        # Determinar si la primera fila es de cabeceras
        first_row = rows[0]
        cells = [cell for cell in first_row.get("children", []) if cell.get("type") in ["TH", "TD"]]
        is_header_row = all(cell.get("type") == "TH" for cell in cells)
        
        if not is_header_row:
            return False
        
        # La estructura necesita actualización
        table_id = table.get("id", "unknown")
        
        # Crear nueva estructura (simulado)
        logger.info(f"Se restructurará la tabla {table_id} para añadir THead/TBody")
        
        # En implementación real, se modificaría la estructura
        return True
    
    def _fix_table_structure(self, table: Dict) -> bool:
        """
        Corrige problemas estructurales en la tabla.
        
        Args:
            table: Diccionario representando una tabla
            
        Returns:
            bool: True si se realizaron correcciones
        """
        changes_made = False
        
        # Simulación de correcciones estructurales
        logger.debug(f"Verificando estructura de tabla {table.get('id', 'unknown')}")
        
        # Verificar que todas las filas tengan el mismo número de celdas
        # y aplicar colspan/rowspan según sea necesario
        
        return changes_made