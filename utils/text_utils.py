# utils/text_utils.py

import re
import unicodedata
from typing import Dict, List, Optional, Tuple, Any, Union
from loguru import logger

def normalize_text(text: str) -> str:
    """
    Normaliza texto eliminando caracteres de control y espacios extra.
    
    Args:
        text: Texto a normalizar
        
    Returns:
        str: Texto normalizado
    """
    if not text:
        return ""
    
    # Eliminar caracteres de control (excepto espacios, tabs, saltos de línea)
    cleaned = ''.join(char for char in text if ord(char) >= 32 or char in '\t\n\r')
    
    # Normalizar espacios en blanco
    cleaned = ' '.join(cleaned.split())
    
    return cleaned

def extract_text_from_mcid(page, mcid: int) -> str:
    """
    Extrae texto de una página PDF usando MCID.
    
    Args:
        page: Página de PyMuPDF
        mcid: Marked Content ID
        
    Returns:
        str: Texto extraído
    """
    try:
        # Extraer bloques de texto con información de MCID
        blocks = page.get_text("dict", flags=0)["blocks"]
        text_parts = []
        
        for block in blocks:
            if block["type"] == 0:  # Bloque de texto
                for line in block["lines"]:
                    for span in line["spans"]:
                        if span.get("mcid") == mcid:
                            text_parts.append(span["text"])
        
        return " ".join(text_parts).strip()
        
    except Exception as e:
        logger.error(f"Error extrayendo texto de MCID {mcid}: {e}")
        return ""

def build_text_mapping(doc) -> Dict[int, Dict[int, str]]:
    """
    Construye un mapeo de MCID a texto para todas las páginas del documento.
    
    Args:
        doc: Documento PyMuPDF
        
    Returns:
        Dict[int, Dict[int, str]]: Mapeo página -> MCID -> texto
    """
    mcid_mapping = {}
    
    try:
        for page_num in range(len(doc)):
            page = doc[page_num]
            mcid_mapping[page_num] = {}
            
            # Extraer bloques de texto con información de MCID
            blocks = page.get_text("dict", flags=0)["blocks"]
            for block in blocks:
                if block["type"] == 0:  # Bloque de texto
                    for line in block["lines"]:
                        for span in line["spans"]:
                            mcid = span.get("mcid", -1)
                            if mcid >= 0:
                                if mcid not in mcid_mapping[page_num]:
                                    mcid_mapping[page_num][mcid] = []
                                mcid_mapping[page_num][mcid].append(span["text"])
            
            # Consolidar texto por MCID
            for mcid in mcid_mapping[page_num]:
                mcid_mapping[page_num][mcid] = " ".join(mcid_mapping[page_num][mcid])
                
        logger.info(f"Mapeo de texto construido para {len(mcid_mapping)} páginas")
        return mcid_mapping
        
    except Exception as e:
        logger.error(f"Error construyendo mapeo de texto: {e}")
        return {}

def extract_element_text_comprehensive(element, page_num: int, mcid_mapping: Dict = None) -> str:
    """
    Extrae texto de un elemento estructural usando múltiples estrategias.
    
    Args:
        element: Elemento pikepdf
        page_num: Número de página
        mcid_mapping: Mapeo pre-construido de MCID a texto
        
    Returns:
        str: Texto extraído
    """
    from pikepdf import Name, String, Array, Dictionary
    
    text_parts = []
    
    try:
        # Estrategia 1: ActualText (tiene prioridad más alta)
        if Name.ActualText in element:
            actual_text = str(element.ActualText)
            if actual_text.strip():
                return normalize_text(actual_text)
        
        # Estrategia 2: Alt text para figuras
        if (element.get(Name.S) == Name.Figure and Name.Alt in element):
            alt_text = str(element.Alt)
            if alt_text.strip():
                return normalize_text(alt_text)
        
        # Estrategia 3: Contenido E (expansion text)
        if Name.E in element:
            e_text = str(element.E)
            if e_text.strip():
                return normalize_text(e_text)
        
        # Estrategia 4: Procesar contenido K
        if Name.K in element:
            k_value = element.K
            text_parts.extend(_extract_text_from_k_value(k_value, page_num, mcid_mapping))
    
    except Exception as e:
        logger.debug(f"Error en extracción comprehensiva de texto: {e}")
    
    # Consolidar y normalizar texto
    final_text = " ".join(text_parts).strip()
    return normalize_text(final_text)

def _extract_text_from_k_value(k_value, page_num: int, mcid_mapping: Dict = None) -> List[str]:
    """
    Extrae texto del valor K de un elemento.
    
    Args:
        k_value: Valor K del elemento
        page_num: Número de página
        mcid_mapping: Mapeo de MCID a texto
        
    Returns:
        List[str]: Lista de textos extraídos
    """
    from pikepdf import Name, String, Array, Dictionary
    
    text_parts = []
    
    try:
        if isinstance(k_value, String):
            text_parts.append(str(k_value))
            
        elif isinstance(k_value, int):
            # Es un MCID
            if mcid_mapping and page_num in mcid_mapping and k_value in mcid_mapping[page_num]:
                mcid_text = mcid_mapping[page_num][k_value]
                if mcid_text:
                    text_parts.append(mcid_text)
                    
        elif isinstance(k_value, Array):
            for item in k_value:
                if isinstance(item, String):
                    text_parts.append(str(item))
                elif isinstance(item, int):
                    if mcid_mapping and page_num in mcid_mapping and item in mcid_mapping[page_num]:
                        mcid_text = mcid_mapping[page_num][item]
                        if mcid_text:
                            text_parts.append(mcid_text)
                elif isinstance(item, Dictionary):
                    # Procesar diccionario (puede ser MCR)
                    if Name.S in item and item.S == Name.MCR:
                        if Name.MCID in item:
                            mcid = item.MCID
                            if mcid_mapping and page_num in mcid_mapping and mcid in mcid_mapping[page_num]:
                                mcid_text = mcid_mapping[page_num][mcid]
                                if mcid_text:
                                    text_parts.append(mcid_text)
                    else:
                        # Recursivamente extraer de otros elementos
                        sub_text = extract_element_text_comprehensive(item, page_num, mcid_mapping)
                        if sub_text:
                            text_parts.append(sub_text)
                            
        elif isinstance(k_value, Dictionary):
            # Procesar como MCR o elemento anidado
            if Name.S in k_value and k_value.S == Name.MCR:
                if Name.MCID in k_value:
                    mcid = k_value.MCID
                    if mcid_mapping and page_num in mcid_mapping and mcid in mcid_mapping[page_num]:
                        mcid_text = mcid_mapping[page_num][mcid]
                        if mcid_text:
                            text_parts.append(mcid_text)
            else:
                # Recursivamente extraer de elemento anidado
                sub_text = extract_element_text_comprehensive(k_value, page_num, mcid_mapping)
                if sub_text:
                    text_parts.append(sub_text)
                    
    except Exception as e:
        logger.debug(f"Error extrayendo texto de valor K: {e}")
    
    return text_parts

def generate_element_display_text(node_data: Dict) -> str:
    """
    Genera texto descriptivo para mostrar en la interfaz basado en el tipo y contenido del nodo.
    
    Args:
        node_data: Datos del nodo estructural
        
    Returns:
        str: Texto descriptivo para mostrar
    """
    element_type = node_data.get("type", "Unknown")
    element_text = node_data.get("text", "").strip()
    attributes = node_data.get("attributes", {})
    
    # Casos especiales por tipo
    if element_type == "StructTreeRoot":
        child_count = len(node_data.get("children", []))
        return f"Document Root ({child_count} children)"
    
    elif element_type in ["H1", "H2", "H3", "H4", "H5", "H6"]:
        if element_text:
            preview = element_text[:50] + "..." if len(element_text) > 50 else element_text
            return f"{element_type}: {preview}"
        else:
            return f"{element_type} (empty)"
    
    elif element_type == "P":
        if element_text:
            preview = element_text[:60] + "..." if len(element_text) > 60 else element_text
            return f"Paragraph: {preview}"
        else:
            return "Paragraph (empty)"
    
    elif element_type == "Figure":
        alt_text = attributes.get("alt", "")
        if alt_text:
            preview = alt_text[:40] + "..." if len(alt_text) > 40 else alt_text
            return f"Figure: {preview}"
        elif element_text:
            preview = element_text[:40] + "..." if len(element_text) > 40 else element_text
            return f"Figure: {preview}"
        else:
            return "Figure (no alt text)"
    
    elif element_type == "Table":
        child_count = len(node_data.get("children", []))
        return f"Table ({child_count} rows)"
    
    elif element_type in ["TH", "TD"]:
        if element_text:
            preview = element_text[:30] + "..." if len(element_text) > 30 else element_text
            return f"{element_type}: {preview}"
        else:
            scope = attributes.get("scope", "")
            headers = attributes.get("headers", "")
            if scope:
                return f"{element_type} (scope: {scope})"
            elif headers:
                return f"{element_type} (headers: {headers[:20]}...)"
            else:
                return f"{element_type} (empty)"
    
    elif element_type == "L":
        child_count = len(node_data.get("children", []))
        list_type = attributes.get("listnumbering", "")
        if list_type:
            return f"List ({list_type}, {child_count} items)"
        else:
            return f"List ({child_count} items)"
    
    elif element_type == "LI":
        if element_text:
            preview = element_text[:40] + "..." if len(element_text) > 40 else element_text
            return f"List Item: {preview}"
        else:
            return "List Item (empty)"
    
    elif element_type == "Link":
        if element_text:
            preview = element_text[:30] + "..." if len(element_text) > 30 else element_text
            return f"Link: {preview}"
        else:
            return "Link (no text)"
    
    elif element_type == "TextContent":
        if element_text:
            preview = element_text[:50] + "..." if len(element_text) > 50 else element_text
            return f"Text: {preview}"
        else:
            return "Text (empty)"
    
    elif element_type == "MCID":
        mcid = node_data.get("mcid", "?")
        if element_text:
            preview = element_text[:40] + "..." if len(element_text) > 40 else element_text
            return f"MCID {mcid}: {preview}"
        else:
            return f"MCID {mcid} (no text)"
    
    elif element_type == "Span":
        if element_text:
            preview = element_text[:40] + "..." if len(element_text) > 40 else element_text
            return f"Span: {preview}"
        else:
            lang = attributes.get("lang", "")
            if lang:
                return f"Span (lang: {lang})"
            else:
                return "Span (empty)"
    
    else:
        # Para otros tipos, mostrar tipo y texto si existe
        if element_text:
            preview = element_text[:40] + "..." if len(element_text) > 40 else element_text
            return f"{element_type}: {preview}"
        else:
            child_count = len(node_data.get("children", []))
            if child_count > 0:
                return f"{element_type} ({child_count} children)"
            else:
                # Mostrar atributos importantes si no hay texto ni hijos
                important_attrs = []
                for attr in ["alt", "lang", "scope", "headers"]:
                    if attr in attributes and attributes[attr]:
                        important_attrs.append(f"{attr}: {attributes[attr][:15]}...")
                
                if important_attrs:
                    return f"{element_type} ({', '.join(important_attrs)})"
                else:
                    return f"{element_type}"

def detect_reading_order_issues(structure_tree: Dict) -> List[Dict]:
    """
    Detecta problemas en el orden de lectura del documento.
    
    Args:
        structure_tree: Árbol de estructura del documento
        
    Returns:
        List[Dict]: Lista de problemas detectados
    """
    issues = []
    
    def analyze_node(node, path="", level=0):
        if not isinstance(node, dict):
            return
        
        node_type = node.get("type", "")
        children = node.get("children", [])
        
        # Detectar saltos de nivel en encabezados
        if node_type.startswith("H") and node_type[1:].isdigit():
            current_level = int(node_type[1:])
            
            # Buscar encabezados hermanos anteriores
            parent_path = "/".join(path.split("/")[:-1]) if "/" in path else ""
            prev_headings = _find_previous_headings(structure_tree, path)
            
            if prev_headings:
                last_heading_level = int(prev_headings[-1]["type"][1:])
                
                # Verificar salto de nivel
                if current_level > last_heading_level + 1:
                    issues.append({
                        "type": "heading_level_skip",
                        "description": f"Salto de nivel de encabezado: de H{last_heading_level} a H{current_level}",
                        "element_path": path,
                        "element_type": node_type,
                        "severity": "warning"
                    })
        
        # Detectar listas mal estructuradas
        if node_type == "L":
            list_items = [child for child in children if child.get("type") == "LI"]
            non_list_items = [child for child in children if child.get("type") != "LI"]
            
            if non_list_items:
                issues.append({
                    "type": "invalid_list_content",
                    "description": f"Lista contiene elementos que no son LI: {[child.get('type') for child in non_list_items]}",
                    "element_path": path,
                    "element_type": node_type,
                    "severity": "error"
                })
        
        # Detectar tablas mal estructuradas
        if node_type == "Table":
            rows = [child for child in children if child.get("type") == "TR"]
            if not rows:
                issues.append({
                    "type": "empty_table",
                    "description": "Tabla sin filas (TR)",
                    "element_path": path,
                    "element_type": node_type,
                    "severity": "error"
                })
        
        # Analizar hijos recursivamente
        for i, child in enumerate(children):
            child_path = f"{path}/child[{i}]" if path else f"child[{i}]"
            analyze_node(child, child_path, level + 1)
    
    analyze_node(structure_tree)
    return issues

def _find_previous_headings(structure_tree: Dict, current_path: str) -> List[Dict]:
    """
    Encuentra encabezados anteriores en el orden de lectura.
    
    Args:
        structure_tree: Árbol de estructura
        current_path: Ruta del elemento actual
        
    Returns:
        List[Dict]: Lista de encabezados anteriores
    """
    headings = []
    
    def collect_headings(node, path=""):
        if not isinstance(node, dict):
            return
        
        node_type = node.get("type", "")
        
        # Si llegamos al elemento actual, parar
        if path == current_path:
            return
        
        # Recopilar encabezados
        if node_type.startswith("H") and node_type[1:].isdigit():
            headings.append({
                "type": node_type,
                "path": path,
                "text": node.get("text", "")
            })
        
        # Procesar hijos
        children = node.get("children", [])
        for i, child in enumerate(children):
            child_path = f"{path}/child[{i}]" if path else f"child[{i}]"
            collect_headings(child, child_path)
    
    collect_headings(structure_tree)
    return headings

def validate_text_content(text: str) -> Dict[str, Any]:
    """
    Valida el contenido de texto para detectar problemas comunes.
    
    Args:
        text: Texto a validar
        
    Returns:
        Dict: Información de validación
    """
    issues = []
    
    if not text or not text.strip():
        return {
            "valid": True,
            "issues": [],
            "stats": {"length": 0, "words": 0, "chars": 0}
        }
    
    # Detectar texto con muchos espacios
    if "  " in text:
        issues.append({
            "type": "multiple_spaces",
            "description": "Texto contiene múltiples espacios consecutivos",
            "severity": "info"
        })
    
    # Detectar texto muy largo (posible problema de extracción)
    if len(text) > 1000:
        issues.append({
            "type": "very_long_text",
            "description": f"Texto muy largo ({len(text)} caracteres) - posible error de extracción",
            "severity": "warning"
        })
    
    # Detectar caracteres de control
    control_chars = [c for c in text if ord(c) < 32 and c not in '\t\n\r']
    if control_chars:
        issues.append({
            "type": "control_characters",
            "description": f"Texto contiene {len(control_chars)} caracteres de control",
            "severity": "warning"
        })
    
    # Detectar posible texto corrupto (muchos caracteres especiales)
    special_char_ratio = sum(1 for c in text if not c.isalnum() and c not in ' \t\n\r.,;:!?-()[]{}') / len(text)
    if special_char_ratio > 0.3:
        issues.append({
            "type": "possibly_corrupted",
            "description": f"Alto ratio de caracteres especiales ({special_char_ratio:.2%}) - posible corrupción",
            "severity": "warning"
        })
    
    # Estadísticas
    words = len(text.split())
    chars = len(text.strip())
    
    return {
        "valid": len([i for i in issues if i["severity"] == "error"]) == 0,
        "issues": issues,
        "stats": {
            "length": len(text),
            "words": words,
            "chars": chars,
            "lines": text.count('\n') + 1
        }
    }