#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Generación de estructura lógica para PDFs sin etiquetar.
Detecta, clasifica y etiqueta bloques de contenido.
"""

from typing import Dict, List, Optional, Tuple, Any
import re
import numpy as np
import cv2
from loguru import logger

class StructureGenerator:
    """
    Clase para generar estructura lógica en PDFs sin etiquetar.
    Construye árbol semántico desde texto visual y clasifica contenido.
    """
    
    def __init__(self, pdf_writer=None):
        """
        Inicializa el generador de estructura.
        
        Args:
            pdf_writer: Instancia opcional de PDFWriter
        """
        self.pdf_writer = pdf_writer
        logger.info("StructureGenerator inicializado")
    
    def set_pdf_writer(self, pdf_writer):
        """Establece el escritor de PDF a utilizar"""
        self.pdf_writer = pdf_writer
    
    def generate_structure(self, pdf_loader) -> bool:
        """
        Genera estructura lógica completa para un documento sin etiquetar.
        
        Args:
            pdf_loader: Instancia de PDFLoader con el documento cargado
            
        Returns:
            bool: True si se generó la estructura
            
        Referencias:
            - Matterhorn: 01-005, 01-006, 09-001
            - Tagged PDF: 3.2.1, 4.1
        """
        try:
            if self.pdf_writer is None:
                logger.error("No hay PDFWriter configurado para aplicar cambios")
                return False
            
            if not pdf_loader or not pdf_loader.doc:
                logger.error("No hay documento cargado para generar estructura")
                return False
            
            # Verificar si ya tiene estructura
            if pdf_loader.has_structure():
                logger.warning("El documento ya tiene estructura lógica")
                return False
            
            logger.info(f"Generando estructura para documento de {pdf_loader.doc.page_count} páginas")
            
            # Crear nodo Document raíz
            structure_tree = {
                "type": "Document",
                "children": []
            }
            
            # Procesar cada página
            for page_num in range(pdf_loader.doc.page_count):
                # Extraer contenido visual de la página
                elements = pdf_loader.get_visual_content(page_num)
                
                # Agrupar elementos en bloques lógicos
                blocks = self._group_elements_into_blocks(elements)
                
                # Clasificar cada bloque
                classified_blocks = self._classify_blocks(blocks)
                
                # Construir estructura de la página
                page_structure = self._build_page_structure(classified_blocks)
                
                # Añadir a la estructura global
                structure_tree["children"].extend(page_structure)
            
            # Aplicar la estructura generada
            self.pdf_writer.update_structure_tree(structure_tree)
            
            logger.success("Estructura generada y aplicada correctamente")
            return True
            
        except Exception as e:
            logger.exception(f"Error al generar estructura: {e}")
            return False
    
    def analyze_page_content(self, pdf_loader, page_num: int) -> Dict:
        """
        Analiza el contenido de una página para generar estructura.
        
        Args:
            pdf_loader: Instancia de PDFLoader con el documento cargado
            page_num: Número de página
            
        Returns:
            Dict: Análisis del contenido
        """
        try:
            if not pdf_loader or not pdf_loader.doc:
                logger.error("No hay documento cargado para analizar")
                return {}
            
            logger.info(f"Analizando contenido de página {page_num}")
            
            # Extraer contenido visual
            elements = pdf_loader.get_visual_content(page_num)
            
            # Agrupar elementos
            blocks = self._group_elements_into_blocks(elements)
            
            # Clasificar bloques
            classified_blocks = self._classify_blocks(blocks)
            
            # Análisis adicional
            analysis = {
                "page_num": page_num,
                "block_count": len(classified_blocks),
                "block_types": {},
                "has_headings": False,
                "has_tables": False,
                "has_lists": False,
                "has_figures": False
            }
            
            # Contar tipos de bloques
            for block in classified_blocks:
                block_type = block.get("type", "unknown")
                if block_type not in analysis["block_types"]:
                    analysis["block_types"][block_type] = 0
                analysis["block_types"][block_type] += 1
            
            # Verificar tipos específicos
            analysis["has_headings"] = any(b.get("type", "").startswith("H") for b in classified_blocks)
            analysis["has_tables"] = "Table" in analysis["block_types"]
            analysis["has_lists"] = "L" in analysis["block_types"]
            analysis["has_figures"] = "Figure" in analysis["block_types"]
            
            return analysis
            
        except Exception as e:
            logger.exception(f"Error al analizar página {page_num}: {e}")
            return {}
    
    def _group_elements_into_blocks(self, elements: List[Dict]) -> List[Dict]:
        """
        Agrupa elementos visuales en bloques lógicos.
        
        Args:
            elements: Lista de elementos visuales
            
        Returns:
            List[Dict]: Lista de bloques lógicos
        """
        # Simulación - en implementación real se agruparían por proximidad y alineación
        blocks = []
        current_block = []
        
        for element in elements:
            if element["type"] == "text":
                # Si ya hay elementos en el bloque actual y hay cambio de línea o estilo
                if current_block and (abs(element["bbox"][1] - current_block[-1]["bbox"][3]) > 2 or
                                     element["font_size"] != current_block[-1]["font_size"]):
                    # Crear nuevo bloque con los elementos acumulados
                    blocks.append({
                        "type": "block",
                        "elements": current_block,
                        "bbox": self._calculate_block_bbox(current_block),
                        "content": " ".join([e["content"] for e in current_block]),
                        "font_size": current_block[0]["font_size"],
                        "is_bold": current_block[0]["is_bold"]
                    })
                    current_block = []
                
                # Añadir elemento al bloque actual
                current_block.append(element)
            elif element["type"] == "image":
                # Las imágenes son bloques independientes
                blocks.append({
                    "type": "image",
                    "elements": [element],
                    "bbox": element["bbox"]
                })
        
        # Añadir el último bloque si hay elementos pendientes
        if current_block:
            blocks.append({
                "type": "block",
                "elements": current_block,
                "bbox": self._calculate_block_bbox(current_block),
                "content": " ".join([e["content"] for e in current_block]),
                "font_size": current_block[0]["font_size"],
                "is_bold": current_block[0]["is_bold"]
            })
        
        return blocks
    
    def _calculate_block_bbox(self, elements: List[Dict]) -> List[float]:
        """
        Calcula el bounding box de un bloque.
        
        Args:
            elements: Lista de elementos en el bloque
            
        Returns:
            List[float]: Bounding box [x0, y0, x1, y1]
        """
        if not elements:
            return [0, 0, 0, 0]
        
        # Inicializar con el primer elemento
        bbox = list(elements[0]["bbox"])
        
        # Actualizar con cada elemento adicional
        for element in elements[1:]:
            elem_bbox = element["bbox"]
            bbox[0] = min(bbox[0], elem_bbox[0])  # x0 (mínimo)
            bbox[1] = min(bbox[1], elem_bbox[1])  # y0 (mínimo)
            bbox[2] = max(bbox[2], elem_bbox[2])  # x1 (máximo)
            bbox[3] = max(bbox[3], elem_bbox[3])  # y1 (máximo)
        
        return bbox
    
    def _classify_blocks(self, blocks: List[Dict]) -> List[Dict]:
        """
        Clasifica bloques según tipo de estructura.
        
        Args:
            blocks: Lista de bloques lógicos
            
        Returns:
            List[Dict]: Lista de bloques clasificados
        """
        classified_blocks = []
        
        for block in blocks:
            if block["type"] == "image":
                # Clasifica como Figure
                block["type"] = "Figure"
                classified_blocks.append(block)
                continue
            
            content = block.get("content", "")
            font_size = block.get("font_size", 0)
            is_bold = block.get("is_bold", False)
            
            # Detectar encabezados por tamaño y estilo
            if font_size > 16:
                block["type"] = "H1"
            elif font_size > 14 and is_bold:
                block["type"] = "H2"
            elif font_size > 12 and is_bold:
                block["type"] = "H3"
            elif self._looks_like_list_item(content):
                block["type"] = "L"
            elif self._looks_like_table(block, blocks):
                block["type"] = "Table"
            else:
                block["type"] = "P"
            
            classified_blocks.append(block)
        
        return classified_blocks
    
    def _looks_like_list_item(self, content: str) -> bool:
        """
        Determina si un texto parece un ítem de lista.
        
        Args:
            content: Texto del bloque
            
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
    
    def _looks_like_table(self, block: Dict, blocks: List[Dict]) -> bool:
        """
        Determina si un bloque parece una tabla.
        
        Args:
            block: Bloque a analizar
            blocks: Lista de todos los bloques
            
        Returns:
            bool: True si parece una tabla
        """
        # Simplificado para esta implementación
        # En implementación real, se analizaría la disposición espacial
        
        # Heurística simple: contenido con múltiples caracteres de tabulación o separadores
        content = block.get("content", "")
        return "|" in content or "\t" in content or content.count("  ") > 3
    
    def _build_page_structure(self, blocks: List[Dict]) -> List[Dict]:
        """
        Construye la estructura de una página.
        
        Args:
            blocks: Lista de bloques clasificados
            
        Returns:
            List[Dict]: Estructura de la página
        """
        structure = []
        list_items = []
        table_rows = []
        
        for i, block in enumerate(blocks):
            block_type = block.get("type", "P")
            
            if block_type == "L":
                # Acumular ítems de lista
                list_items.append(block)
            elif list_items and block_type != "L":
                # Fin de lista, procesar ítems acumulados
                list_structure = self._build_list_structure(list_items)
                structure.append(list_structure)
                list_items = []
                
                # Procesar bloque actual
                structure.append(self._build_block_structure(block))
            elif block_type == "Table" or (table_rows and block_type.startswith("TD")):
                # Acumular filas de tabla
                table_rows.append(block)
            elif table_rows and block_type != "Table" and not block_type.startswith("TD"):
                # Fin de tabla, procesar filas acumuladas
                table_structure = self._build_table_structure(table_rows)
                structure.append(table_structure)
                table_rows = []
                
                # Procesar bloque actual
                structure.append(self._build_block_structure(block))
            else:
                # Bloques normales
                structure.append(self._build_block_structure(block))
        
        # Procesar listas o tablas pendientes
        if list_items:
            list_structure = self._build_list_structure(list_items)
            structure.append(list_structure)
        elif table_rows:
            table_structure = self._build_table_structure(table_rows)
            structure.append(table_structure)
        
        return structure
    
    def _build_block_structure(self, block: Dict) -> Dict:
        """
        Construye la estructura para un bloque.
        
        Args:
            block: Bloque clasificado
            
        Returns:
            Dict: Estructura del bloque
        """
        block_type = block.get("type", "P")
        
        structure = {
            "type": block_type,
            "content": block.get("content", ""),
            "bbox": block.get("bbox", [0, 0, 0, 0])
        }
        
        # Añadir atributos específicos según tipo
        if block_type == "Figure":
            structure["alt"] = ""
        
        return structure
    
    def _build_list_structure(self, list_items: List[Dict]) -> Dict:
        """
        Construye la estructura para una lista.
        
        Args:
            list_items: Lista de bloques de ítems de lista
            
        Returns:
            Dict: Estructura de la lista
        """
        # Determinar si es lista ordenada
        is_ordered = any(re.match(r'^\s*\d+[\.\)\]]\s+', item.get("content", "")) for item in list_items)
        
        list_structure = {
            "type": "L",
            "children": [],
            "bbox": self._calculate_block_bbox([item for item in list_items]),
            "ordered": is_ordered
        }
        
        # Añadir ListNumbering si es ordenada
        if is_ordered:
            numbering_type = self._determine_list_numbering_type(list_items)
            list_structure["list_numbering"] = numbering_type
        
        # Procesar cada ítem
        for item in list_items:
            content = item.get("content", "")
            label, body = self._split_list_item_content(content)
            
            li_structure = {
                "type": "LI",
                "children": [
                    {
                        "type": "Lbl",
                        "content": label
                    },
                    {
                        "type": "LBody",
                        "content": body
                    }
                ]
            }
            
            list_structure["children"].append(li_structure)
        
        return list_structure
    
    def _build_table_structure(self, table_blocks: List[Dict]) -> Dict:
        """
        Construye la estructura para una tabla.
        
        Args:
            table_blocks: Lista de bloques de tabla
            
        Returns:
            Dict: Estructura de la tabla
        """
        table_structure = {
            "type": "Table",
            "children": [],
            "bbox": self._calculate_block_bbox([block for block in table_blocks])
        }
        
        # Simplificado - en implementación real se analizaría la estructura de la tabla
        # y se crearían filas (TR) y celdas (TH, TD) adecuadas
        
        # Simulación de estructura de tabla
        first_row = True
        
        for block in table_blocks:
            content = block.get("content", "")
            
            # Dividir en columnas (simplificado)
            columns = re.split(r'\s{2,}|\t|\|', content)
            columns = [col.strip() for col in columns if col.strip()]
            
            row_structure = {
                "type": "TR",
                "children": []
            }
            
            # Crear celdas
            for col in columns:
                cell_type = "TH" if first_row else "TD"
                
                cell_structure = {
                    "type": cell_type,
                    "content": col
                }
                
                # Añadir Scope a celdas TH
                if cell_type == "TH":
                    cell_structure["scope"] = "Column"
                
                row_structure["children"].append(cell_structure)
            
            table_structure["children"].append(row_structure)
            first_row = False
        
        return table_structure
    
    def _split_list_item_content(self, content: str) -> Tuple[str, str]:
        """
        Separa el contenido de un ítem de lista en etiqueta y cuerpo.
        
        Args:
            content: Texto del ítem
            
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
    
    def _determine_list_numbering_type(self, list_items: List[Dict]) -> str:
        """
        Determina el tipo de numeración para una lista.
        
        Args:
            list_items: Lista de ítems
            
        Returns:
            str: Tipo de numeración
        """
        for item in list_items:
            content = item.get("content", "")
            
            # Determinar tipo por el primer ítem
            if re.match(r'^\s*\d+[\.\)\]]', content):
                return "Decimal"
            elif re.match(r'^\s*[IVXLCDM]+[\.\)\]]', content):
                return "UpperRoman"
            elif re.match(r'^\s*[ivxlcdm]+[\.\)\]]', content):
                return "LowerRoman"
            elif re.match(r'^\s*[A-Z][\.\)\]]', content):
                return "UpperAlpha"
            elif re.match(r'^\s*[a-z][\.\)\]]', content):
                return "LowerAlpha"
        
        return "None"