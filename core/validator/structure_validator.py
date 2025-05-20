#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Validación de estructura lógica según PDF/UA.
Verifica jerarquía, tipos de etiqueta y semántica.

Este módulo implementa validaciones para los siguientes checkpoints Matterhorn:
- 01-001 a 01-007: Estructura real etiquetada
- 02-001 a 02-004: Mapeo de roles
- 09-001 a 09-008: Etiquetas apropiadas
- 13-004: Texto alternativo para figuras
- 14-001 a 14-007: Encabezados
- 15-003: Tablas y celdas de cabecera
- 16-001 a 16-003: Listas
"""

from typing import Dict, List, Optional, Any, Set, Tuple
from collections import defaultdict
import re
from loguru import logger

class StructureValidator:
    """
    Valida la estructura lógica del documento según requisitos de PDF/UA.
    Verifica jerarquía, tipos de etiqueta y relaciones semánticas.
    """
    
    def __init__(self):
        """Inicializa el validador de estructura"""
        # Tipos de estructura válidos en PDF 1.7 / ISO 32000-1
        self.valid_structure_types = [
            "Document", "Part", "Art", "Sect", "Div", "BlockQuote", "Caption",
            "TOC", "TOCI", "Index", "NonStruct", "Private", "P", "H", "H1", "H2",
            "H3", "H4", "H5", "H6", "L", "LI", "Lbl", "LBody", "Table", "TR", "TH",
            "TD", "THead", "TBody", "TFoot", "Span", "Quote", "Note", "Reference",
            "BibEntry", "Code", "Link", "Annot", "Ruby", "Warichu", "RB", "RT", "RP",
            "WT", "WP", "Figure", "Formula", "Form"
        ]
        
        # Tipos que pueden estar vacíos
        self.can_be_empty = ["TD", "LI", "Span", "Div", "Document", "NonStruct", "Private"]
        
        # Mapa de relaciones padre-hijo válidas - orientativo según ISO 32000-1
        self.valid_parent_child = {
            # Elementos de agrupación
            "Document": ["Part", "Art", "Sect", "Div", "P", "H1", "L", "Table", "Figure", "Formula", "Form", "TOC", "Index"],
            "Part": ["Part", "Art", "Sect", "Div", "P", "H1", "L", "Table", "Figure", "Formula", "Form"],
            "Art": ["Part", "Sect", "Div", "P", "H1", "L", "Table", "Figure", "Formula", "Form"],
            "Sect": ["Part", "Sect", "Div", "P", "H1", "H2", "H3", "H4", "H5", "H6", "L", "Table", "Figure", "Formula", "Form"],
            "Div": ["P", "H1", "H2", "H3", "H4", "H5", "H6", "L", "Table", "Figure", "Formula", "Form", "Div"],
            
            # Elementos especializados
            "BlockQuote": ["P", "H1", "H2", "H3", "H4", "H5", "H6", "L", "Table", "Figure", "Formula", "Form", "Div"],
            "Caption": ["P", "Span", "Quote", "Code"],
            "TOC": ["Caption", "TOCI"],
            "TOCI": ["P", "Reference", "Link", "Lbl", "Span"],
            "Index": ["P", "Reference", "Link", "Lbl", "Span", "L"],
            
            # Listas
            "L": ["Caption", "LI"],
            "LI": ["Lbl", "LBody"],
            "LBody": ["P", "Span", "L", "Table", "Figure", "Formula", "Form", "Div"],
            
            # Tablas
            "Table": ["Caption", "TR", "THead", "TBody", "TFoot"],
            "THead": ["TR"],
            "TBody": ["TR"],
            "TFoot": ["TR"],
            "TR": ["TH", "TD"],
            "TH": ["P", "Span", "L", "Figure", "Formula", "Form", "Div"],
            "TD": ["P", "Span", "L", "Table", "Figure", "Formula", "Form", "Div"],
            
            # Enlaces y anotaciones
            "Link": ["Link-OBJR", "Span"],
            "Reference": ["Lbl", "Span", "Link"],
            "Note": ["Lbl", "P", "Span", "L", "Table", "Figure", "Formula", "Form", "Div"],

            # Contenedores genéricos que pueden contener casi cualquier cosa
            "NonStruct": self.valid_structure_types,
            "Private": self.valid_structure_types
        }
        
        # Tipos que requieren atributos específicos
        self.required_attributes = {
            "Figure": ["alt"],
            "Formula": ["alt"],
            "TH": ["scope"],
            "Link": [],  # En PDF/UA no requiere alt obligatorio, pero es recomendado
            "Lbl": [],
            "Note": ["id"],
        }
        
        # Inicializar referencia al PDF loader (se configurará más tarde)
        self.pdf_loader = None
        
        logger.info("StructureValidator inicializado")
    
    def set_pdf_loader(self, pdf_loader):
        """
        Establece la referencia al cargador de PDF.
        
        Args:
            pdf_loader: Instancia de PDFLoader con el documento cargado
        """
        self.pdf_loader = pdf_loader
        logger.debug("PDFLoader establecido en StructureValidator")
    
    def validate(self, structure_tree: Dict, role_map: Dict = None) -> List[Dict]:
        """
        Valida la estructura lógica completa.
        
        Args:
            structure_tree: Diccionario representando la estructura lógica
            role_map: Diccionario con mapeos de roles personalizados
            
        Returns:
            List[Dict]: Lista de problemas detectados
            
        Referencias:
            - Matterhorn: 01-001 a 01-007, 09-001 a 09-008
            - Tagged PDF: 3.2 (Fundamentals), 4.1 y 4.2 (tipos de estructura)
        """
        issues = []
        
        # Verificar si existe estructura lógica y tiene contenido
        if not structure_tree or not structure_tree.get("children"):
            # Checkpoint 01-005: Contenido no está etiquetado ni es artefacto
            issues.append({
                "checkpoint": "01-005",
                "severity": "error",
                "description": "El documento no contiene estructura lógica",
                "fix_description": "Añadir estructura lógica al documento",
                "fixable": True,
                "page": "all"
            })
            logger.warning("Documento sin estructura lógica")
            return issues
        
        # Validar mapa de roles si existe
        if role_map:
            role_map_issues = self._validate_role_map(role_map)
            issues.extend(role_map_issues)
        
        # Validar orden de lectura global - Checkpoint 09-001
        reading_order_issues = self._validate_reading_order(structure_tree.get("children", []))
        issues.extend(reading_order_issues)
        
        # Validar estructura completa recursivamente
        tree_issues = self._validate_tree(structure_tree.get("children", []))
        issues.extend(tree_issues)
        
        # Validar encabezados globalmente (secuencia)
        heading_issues = self._validate_heading_sequence(structure_tree.get("children", []))
        issues.extend(heading_issues)
        
        # Validar presencia de Document como nodo raíz
        root_issues = self._validate_root_structure(structure_tree.get("children", []))
        issues.extend(root_issues)
        
        # Validar elementos que podrían necesitar estar marcados como artefactos
        artifact_issues = self._validate_artifacts(structure_tree.get("children", []))
        issues.extend(artifact_issues)
        
        logger.info(f"Validación de estructura completada: {len(issues)} problemas encontrados")
        return issues
    
    def _validate_role_map(self, role_map: Dict) -> List[Dict]:
        """
        Valida el mapa de roles.
        
        Args:
            role_map: Diccionario con mapeos de roles personalizados
            
        Returns:
            List[Dict]: Lista de problemas detectados
            
        Referencias:
            - Matterhorn: 02-001 a 02-004 (Role Mapping)
            - Tagged PDF: 3.6 (Role maps)
        """
        issues = []
        
        # Verificar si hay mapeo de roles
        if not role_map:
            return issues
        
        # Guardar mapeos para verificación de ciclos
        mapping_graph = {}
        
        # Verificar cada mapeo
        for custom_type, standard_type in role_map.items():
            # Eliminar prefijo "/" si está presente (común en PDFs)
            if isinstance(custom_type, str) and custom_type.startswith("/"):
                custom_type = custom_type[1:]
            if isinstance(standard_type, str) and standard_type.startswith("/"):
                standard_type = standard_type[1:]
                
            # Guardar para verificación de ciclos
            mapping_graph[custom_type] = standard_type
            
            # Checkpoint 02-001: Mapeo no termina en tipo estándar
            terminal_type = self._find_terminal_type(standard_type, role_map)
            
            if terminal_type not in self.valid_structure_types:
                issues.append({
                    "checkpoint": "02-001",
                    "severity": "error",
                    "description": f"El mapeo de la etiqueta no estándar '{custom_type}' no termina con un tipo estándar",
                    "fix_description": f"Cambiar el mapeo de '{custom_type}' a un tipo estándar válido",
                    "fixable": True,
                    "details": {
                        "custom_type": custom_type,
                        "mapped_to": standard_type,
                        "terminal_type": terminal_type
                    }
                })
            
            # Checkpoint 02-004: Remapeo de tipos estándar
            if custom_type in self.valid_structure_types:
                issues.append({
                    "checkpoint": "02-004",
                    "severity": "error",
                    "description": f"El tipo estándar '{custom_type}' ha sido remapeado",
                    "fix_description": "Eliminar el remapeo de tipos estándar",
                    "fixable": True,
                    "details": {
                        "custom_type": custom_type,
                        "mapped_to": standard_type
                    }
                })
        
        # Checkpoint 02-003: Mapeos circulares
        cycles = self._detect_circular_mappings(mapping_graph)
        for cycle in cycles:
            cycle_str = " -> ".join(cycle)
            issues.append({
                "checkpoint": "02-003",
                "severity": "error",
                "description": f"Existe un mapeo circular: {cycle_str}",
                "fix_description": "Eliminar el mapeo circular",
                "fixable": True,
                "details": {
                    "cycle": cycle
                }
            })
        
        # Checkpoint 02-002: Mapeos semánticamente inapropiados
        # Esta validación requiere intervención humana, pero podemos detectar casos obvios
        for custom_type, standard_type in role_map.items():
            if isinstance(custom_type, str) and custom_type.startswith("/"):
                custom_type = custom_type[1:]
            if isinstance(standard_type, str) and standard_type.startswith("/"):
                standard_type = standard_type[1:]
                
            # Detectar casos obvios como mapear un tipo que sugiere encabezado a otra cosa
            if (isinstance(custom_type, str) and ("head" in custom_type.lower() or 
                "title" in custom_type.lower() or 
                re.match(r'h\d+', custom_type.lower()))) and (
                not (standard_type.startswith("H") or 
                "head" in str(standard_type).lower() or 
                "title" in str(standard_type).lower())):
                
                issues.append({
                    "checkpoint": "02-002",
                    "severity": "warning",
                    "description": f"El mapeo de '{custom_type}' a '{standard_type}' podría ser semánticamente inapropiado",
                    "fix_description": "Revisar y corregir el mapeo semántico",
                    "fixable": True,
                    "details": {
                        "custom_type": custom_type,
                        "mapped_to": standard_type,
                        "expected_type": "H1-H6 o similar"
                    }
                })
        
        return issues
    
    def _find_terminal_type(self, type_name: str, role_map: Dict, visited: Set[str] = None) -> str:
        """
        Encuentra el tipo terminal al seguir una cadena de mapeos.
        
        Args:
            type_name: Nombre del tipo a verificar
            role_map: Diccionario con mapeos de roles
            visited: Conjunto de tipos ya visitados (para detectar ciclos)
            
        Returns:
            str: Tipo terminal
        """
        if visited is None:
            visited = set()
        
        # Eliminar prefijo "/" si está presente
        if isinstance(type_name, str) and type_name.startswith("/"):
            type_name = type_name[1:]
        
        # Si es un tipo estándar, es terminal
        if type_name in self.valid_structure_types:
            return type_name
        
        # Si no está en el mapa, es terminal (aunque no sea estándar)
        if type_name not in role_map:
            return type_name
        
        # Si ya visitamos este tipo, hay un ciclo
        if type_name in visited:
            return "CYCLE"
        
        # Seguir la cadena de mapeo
        visited.add(type_name)
        next_type = role_map[type_name]
        
        # Eliminar prefijo "/" si está presente
        if isinstance(next_type, str) and next_type.startswith("/"):
            next_type = next_type[1:]
            
        return self._find_terminal_type(next_type, role_map, visited)
    
    def _detect_circular_mappings(self, mapping_graph: Dict) -> List[List[str]]:
        """
        Detecta ciclos en el grafo de mapeos.
        
        Args:
            mapping_graph: Diccionario representando el grafo de mapeos
            
        Returns:
            List[List[str]]: Lista de ciclos detectados
        """
        cycles = []
        visited = set()
        path = []
        
        def dfs(node):
            if node in path:
                # Ciclo detectado
                cycle_start = path.index(node)
                cycles.append(path[cycle_start:] + [node])
                return
            
            if node in visited:
                return
                
            visited.add(node)
            path.append(node)
            
            if node in mapping_graph:
                next_node = mapping_graph[node]
                dfs(next_node)
                
            path.pop()
        
        for node in mapping_graph:
            dfs(node)
            
        return cycles
    
    def _validate_tree(self, elements: List[Dict], parent_type: str = None, path: str = "", 
                       seen_ids: Set[str] = None) -> List[Dict]:
        """
        Valida la estructura del árbol de forma recursiva.
        
        Args:
            elements: Lista de elementos de estructura
            parent_type: Tipo del elemento padre
            path: Ruta de anidamiento actual
            seen_ids: Conjunto de IDs ya vistos (para detectar duplicados)
            
        Returns:
            List[Dict]: Lista de problemas detectados
        """
        issues = []
        
        if not elements:
            return issues
        
        if seen_ids is None:
            seen_ids = set()
        
        # Mix de H y H1-H6 en el documento
        h_tags = False
        h_numbered_tags = False
        
        for i, element in enumerate(elements):
            element_type = element.get("type", "unknown")
            element_id = element.get("id", "")
            element_page = element.get("page", 0)
            new_path = f"{path}/{i}:{element_type}"
            
            # Verificar duplicación de IDs
            if element_id and element_id in seen_ids:
                issues.append({
                    "checkpoint": "01-006",
                    "severity": "error",
                    "description": f"ID duplicado: '{element_id}'",
                    "fix_description": "Asignar un ID único al elemento",
                    "fixable": True,
                    "page": element_page,
                    "path": new_path
                })
            elif element_id:
                seen_ids.add(element_id)
            
            # Detectar mix de H y H1-H6 (se reportará a nivel global)
            if element_type == "H":
                h_tags = True
            elif re.match(r'^H\d$', element_type):
                h_numbered_tags = True
            
            # Checkpoint 01-006: Tipo de estructura no estándar o desconocido
            role_mapped_type = None
            if element_type not in self.valid_structure_types:
                role_map = {}
                # Obtener el mapa de roles desde pdf_loader si está disponible
                if self.pdf_loader and hasattr(self.pdf_loader, "structure_tree") and self.pdf_loader.structure_tree:
                    role_map = self.pdf_loader.structure_tree.get("role_map", {})
                
                role_mapped_type = self._find_terminal_type(element_type, role_map)
                
                if role_mapped_type not in self.valid_structure_types:
                    issues.append({
                        "checkpoint": "01-006",
                        "severity": "error",
                        "description": f"Tipo de estructura desconocido: '{element_type}'",
                        "fix_description": "Mapear el tipo personalizado a un tipo estándar",
                        "fixable": True,
                        "page": element_page,
                        "path": new_path,
                        "element_id": id(element.get("element")) if "element" in element else None,
                        "element_type": element_type
                    })
            
            # Checkpoint 09-003: Tipo de estructura no semánticamente apropiado
            # Esta validación requiere intervención humana, pero podemos detectar casos obvios
            content = element.get("text", "")
            if content and len(content) > 0:
                # Verificar tipos que suelen tener contenido específico
                if element_type == "Figure" and len(content.strip()) > 50:
                    issues.append({
                        "checkpoint": "09-003",
                        "severity": "warning",
                        "description": f"Posible etiqueta Figure incorrecta: contiene mucho texto",
                        "fix_description": "Verificar si debe ser un párrafo (P) u otro tipo",
                        "fixable": True,
                        "page": element_page,
                        "path": new_path,
                        "element_id": id(element.get("element")) if "element" in element else None,
                        "element_type": element_type
                    })
                elif (element_type == "P" and len(content.strip()) < 10 and 
                      content.strip().endswith(":") and not element.get("children")):
                    issues.append({
                        "checkpoint": "09-003",
                        "severity": "warning",
                        "description": f"Posible etiqueta P incorrecta: parece un encabezado",
                        "fix_description": "Verificar si debe ser un encabezado (H1-H6)",
                        "fixable": True,
                        "page": element_page,
                        "path": new_path,
                        "element_id": id(element.get("element")) if "element" in element else None,
                        "element_type": element_type
                    })
            
            # Checkpoint 01-006: Elemento vacío que debería tener contenido
            if (not element.get("text") and 
                not element.get("children") and 
                element_type not in self.can_be_empty):
                issues.append({
                    "checkpoint": "01-006",
                    "severity": "warning",
                    "description": f"Elemento de estructura '{element_type}' vacío",
                    "fix_description": f"Eliminar el elemento vacío o añadir contenido",
                    "fixable": True,
                    "page": element_page,
                    "path": new_path,
                    "element_id": id(element.get("element")) if "element" in element else None,
                    "element_type": element_type
                })
            
            # Checkpoint 09-002: Anidamiento semántico incorrecto
            # Usar el tipo role-mapped si existe
            check_type = role_mapped_type if role_mapped_type else element_type
            if not self._is_valid_parent_child(parent_type, check_type):
                issues.append({
                    "checkpoint": "09-002",
                    "severity": "error",
                    "description": f"Anidamiento inapropiado: '{check_type}' dentro de '{parent_type}'",
                    "fix_description": f"Corregir la estructura anidando los elementos correctamente",
                    "fixable": True,
                    "page": element_page,
                    "path": new_path,
                    "element_id": id(element.get("element")) if "element" in element else None,
                    "element_type": element_type
                })
            
            # Checkpoint 13-004: Falta alt en Figure
            if element_type == "Figure" and not self._has_attribute(element, "alt"):
                issues.append({
                    "checkpoint": "13-004",
                    "severity": "error",
                    "description": "Falta texto alternativo en etiqueta <Figure>",
                    "fix_description": "Añadir texto alternativo (Alt) a la figura",
                    "fixable": True,
                    "page": element_page,
                    "path": new_path,
                    "element_id": id(element.get("element")) if "element" in element else None,
                    "element_type": element_type
                })
            
            # Checkpoint 15-003: Falta scope en TH
            if element_type == "TH" and not self._has_attribute(element, "scope"):
                issues.append({
                    "checkpoint": "15-003",
                    "severity": "error",
                    "description": "Celda de cabecera <TH> sin atributo Scope",
                    "fix_description": "Añadir atributo Scope a la celda de cabecera",
                    "fixable": True,
                    "page": element_page,
                    "path": new_path,
                    "element_id": id(element.get("element")) if "element" in element else None,
                    "element_type": element_type
                })
            
            # Checkpoint 16-001: Lista ordenada sin ListNumbering
            if element_type == "L":
                list_items = [c for c in element.get("children", []) if c.get("type") == "LI"]
                if list_items:
                    # Detectar si parece ser una lista ordenada
                    first_labels = []
                    for li in list_items[:min(3, len(list_items))]:
                        for child in li.get("children", []):
                            if child.get("type") == "Lbl":
                                lbl_content = child.get("text", "").strip()
                                first_labels.append(lbl_content)
                                break
                    
                    # Verificar si parece numerada (1., 2., etc.)
                    appears_numbered = False
                    if first_labels and len(first_labels) > 1:
                        if all(re.match(r'^\d+[\.\)]', l) for l in first_labels):
                            appears_numbered = True
                        elif all(re.match(r'^[a-zA-Z][\.\)]', l) for l in first_labels):
                            appears_numbered = True
                        elif all(re.match(r'^[ivxlcdmIVXLCDM]+[\.\)]', l) for l in first_labels):
                            appears_numbered = True
                    
                    if appears_numbered and not self._has_attribute(element, "list_numbering"):
                        issues.append({
                            "checkpoint": "16-001",
                            "severity": "error",
                            "description": "Lista ordenada sin atributo ListNumbering",
                            "fix_description": "Añadir atributo ListNumbering a la lista ordenada",
                            "fixable": True,
                            "page": element_page,
                            "path": new_path,
                            "element_id": id(element.get("element")) if "element" in element else None,
                            "element_type": element_type
                        })
            
            # Checkpoint 16-002: ListNumbering con valor incorrecto
            if element_type == "L" and self._has_attribute(element, "list_numbering"):
                valid_values = ["Decimal", "UpperRoman", "LowerRoman", "UpperAlpha", "LowerAlpha"]
                list_numbering = self._get_attribute_value(element, "list_numbering")
                
                if list_numbering not in valid_values:
                    issues.append({
                        "checkpoint": "16-002",
                        "severity": "error",
                        "description": f"Valor de ListNumbering no válido: '{list_numbering}'",
                        "fix_description": "Usar un valor válido para ListNumbering",
                        "fixable": True,
                        "page": element_page,
                        "path": new_path,
                        "element_id": id(element.get("element")) if "element" in element else None,
                        "element_type": element_type
                    })
            
            # Checkpoint 09-005: Elementos de lista no conformes con ISO 32000-1
            if element_type == "L":
                for child in element.get("children", []):
                    if child.get("type") != "LI" and child.get("type") != "Caption":
                        issues.append({
                            "checkpoint": "09-005",
                            "severity": "error",
                            "description": f"Estructura de lista incorrecta: <L> contiene '{child.get('type')}' en lugar de <LI>",
                            "fix_description": "Corregir la estructura de la lista",
                            "fixable": True,
                            "page": element_page,
                            "path": new_path,
                            "element_id": id(element.get("element")) if "element" in element else None,
                            "element_type": element_type
                        })
            
            # Checkpoint 09-004: Elementos de tabla no conformes con ISO 32000-1
            if element_type == "Table":
                for child in element.get("children", []):
                    child_type = child.get("type", "")
                    if child_type not in ["TR", "THead", "TBody", "TFoot", "Caption"]:
                        issues.append({
                            "checkpoint": "09-004",
                            "severity": "error",
                            "description": f"Estructura de tabla incorrecta: <Table> contiene '{child_type}' no válido",
                            "fix_description": "Corregir la estructura de la tabla",
                            "fixable": True,
                            "page": element_page,
                            "path": new_path,
                            "element_id": id(element.get("element")) if "element" in element else None,
                            "element_type": element_type
                        })
            
            # Validar hijos recursivamente
            if element.get("children"):
                child_issues = self._validate_tree(element["children"], element_type, new_path, seen_ids)
                issues.extend(child_issues)
        
        # Reportar mix de H y H1-H6 si se detectaron ambos
        if h_tags and h_numbered_tags:
            issues.append({
                "checkpoint": "14-007",
                "severity": "error",
                "description": "Documento usa tanto etiquetas <H> como <H#>",
                "fix_description": "Usar consistentemente <H1>-<H6> para todos los encabezados",
                "fixable": True,
                "path": path,
                "page": "all"
            })
        
        return issues
    
    def _validate_reading_order(self, elements: List[Dict]) -> List[Dict]:
        """
        Valida el orden de lectura global.
        
        Args:
            elements: Lista de elementos de estructura
            
        Returns:
            List[Dict]: Lista de problemas detectados
        """
        issues = []
        
        # Esta validación es compleja y generalmente requiere intervención humana
        # Podemos detectar algunos casos obvios, pero un análisis completo
        # requeriría comprender el diseño visual del documento
        
        # Verificar si hay elementos que podrían estar en orden incorrecto
        # Por ejemplo, elementos con coordenadas que sugieren una lectura no lineal
        
        # Recopilar posiciones y páginas de los elementos
        positioned_elements = []
        
        def collect_positioned_elements(elements, page=None):
            for element in elements:
                curr_page = element.get("page", page)
                if "bbox" in element:
                    positioned_elements.append({
                        "type": element.get("type", ""),
                        "bbox": element["bbox"],
                        "page": curr_page,
                        "id": element.get("id", ""),
                        "element_id": id(element.get("element")) if "element" in element else None
                    })
                
                if element.get("children"):
                    collect_positioned_elements(element["children"], curr_page)
        
        collect_positioned_elements(elements)
        
        # Agrupar por página
        elements_by_page = defaultdict(list)
        for elem in positioned_elements:
            if elem["page"] is not None:
                elements_by_page[elem["page"]].append(elem)
        
        # Verificar orden en cada página
        for page, page_elements in elements_by_page.items():
            if len(page_elements) < 2:
                continue
                
            # Ordenar elementos por posición Y (de arriba a abajo)
            sorted_by_y = sorted(page_elements, key=lambda e: e["bbox"][1])
            
            # Detectar posible orden de lectura incorrecto
            # Por ejemplo, si tenemos elementos que no siguen la secuencia vertical pero
            # están cerca en el árbol de estructura
            for i in range(len(sorted_by_y) - 1):
                elem1 = sorted_by_y[i]
                elem2 = sorted_by_y[i + 1]
                
                # Si el elemento 2 está a la izquierda del elemento 1 pero mucho más abajo,
                # podría indicar un orden de lectura incorrecto (columnas)
                if (elem2["bbox"][0] < elem1["bbox"][0] and 
                    elem2["bbox"][1] - elem1["bbox"][3] > 20):  # 20 es un umbral arbitrario
                    
                    issues.append({
                        "checkpoint": "09-001",
                        "severity": "warning",
                        "description": "Posible orden de lectura incorrecto",
                        "fix_description": "Verificar y corregir el orden de los elementos para seguir el flujo natural de lectura",
                        "fixable": True,
                        "page": page,
                        "element_id": elem1["element_id"],
                        "element_type": elem1["type"],
                        "details": {
                            "element1": elem1["id"],
                            "element2": elem2["id"],
                            "element1_type": elem1["type"],
                            "element2_type": elem2["type"]
                        }
                    })
                    # Reportar solo un problema para evitar sobrecarga
                    break
        
        return issues
    
    def _validate_heading_sequence(self, elements: List[Dict]) -> List[Dict]:
        """
        Valida la secuencia de encabezados en todo el documento.
        
        Args:
            elements: Lista de elementos de estructura
            
        Returns:
            List[Dict]: Lista de problemas detectados
        """
        issues = []
        
        # Recopilar todos los encabezados en orden de aparición
        headings = []
        
        def collect_headings(elements, path=""):
            for i, element in enumerate(elements):
                element_type = element.get("type", "")
                element_page = element.get("page", 0)
                current_path = f"{path}/{i}:{element_type}"
                
                if element_type.startswith("H") and len(element_type) == 2 and element_type[1].isdigit():
                    headings.append({
                        "level": int(element_type[1]),
                        "page": element_page,
                        "path": current_path,
                        "id": element.get("id", ""),
                        "element_id": id(element.get("element")) if "element" in element else None,
                        "element_type": element_type
                    })
                
                if element.get("children"):
                    collect_headings(element["children"], current_path)
        
        collect_headings(elements)
        
        # No hay encabezados, nada que verificar
        if not headings:
            return issues
        
        # Checkpoint 14-002: Primer encabezado no es H1
        if headings[0]["level"] != 1:
            issues.append({
                "checkpoint": "14-002",
                "severity": "warning",
                "description": f"El primer encabezado no es <H1>, es <H{headings[0]['level']}>",
                "fix_description": "Cambiar el primer encabezado a <H1>",
                "fixable": True,
                "page": headings[0]["page"],
                "path": headings[0]["path"],
                "element_id": headings[0]["element_id"],
                "element_type": headings[0]["element_type"]
            })
        
        # Checkpoint 14-003: Niveles de encabezado saltados
        last_level = headings[0]["level"]
        for i, heading in enumerate(headings[1:], 1):
            current_level = heading["level"]
            
            if current_level > last_level + 1:
                issues.append({
                    "checkpoint": "14-003",
                    "severity": "error",
                    "description": f"Nivel de encabezado saltado: de <H{last_level}> a <H{current_level}>",
                    "fix_description": f"Usar <H{last_level + 1}> en lugar de <H{current_level}>",
                    "fixable": True,
                    "page": heading["page"],
                    "path": heading["path"],
                    "element_id": heading["element_id"],
                    "element_type": heading["element_type"]
                })
            
            last_level = current_level
        
        return issues
    
    def _validate_root_structure(self, elements: List[Dict]) -> List[Dict]:
        """
        Valida la estructura raíz del documento.
        
        Args:
            elements: Lista de elementos de estructura
            
        Returns:
            List[Dict]: Lista de problemas detectados
        """
        issues = []
        
        # Verificar si hay un nodo Document
        has_document = False
        for element in elements:
            if element.get("type") == "Document":
                has_document = True
                break
        
        if not has_document:
            issues.append({
                "checkpoint": "01-006",
                "severity": "warning",
                "description": "La estructura no tiene un nodo Document raíz",
                "fix_description": "Añadir un nodo Document como raíz de la estructura",
                "fixable": True,
                "page": "all"
            })
        
        return issues
    
    def _validate_artifacts(self, elements: List[Dict]) -> List[Dict]:
        """
        Valida elementos que podrían necesitar estar marcados como artefactos.
        
        Args:
            elements: Lista de elementos de estructura
            
        Returns:
            List[Dict]: Lista de problemas detectados
        """
        issues = []
        
        # Recopilar elementos que podrían ser artefactos
        potential_artifacts = []
        
        def collect_potential_artifacts(elements):
            for element in elements:
                # Elementos cercanos a los bordes de la página podrían ser artefactos
                if "bbox" in element and element.get("page") is not None:
                    bbox = element["bbox"]
                    content = element.get("text", "")
                    
                    # Verificar si podría ser un encabezado o pie de página
                    # (Muy cerca del borde superior o inferior)
                    page_height = 792  # Altura estándar de página A4 en puntos
                    
                    if bbox[1] < 50 or bbox[3] > (page_height - 50):
                        # Verificar si contiene texto típico de encabezado/pie
                        if content:
                            # Patrones comunes en encabezados/pies
                            if (re.search(r'\b(?:pág|page)\.?\s*\d+\b', content, re.I) or
                                re.search(r'\d+\s*(?:de|of)\s*\d+', content) or
                                re.search(r'\d{1,2}/\d{1,2}/\d{2,4}', content)):
                                
                                potential_artifacts.append({
                                    "type": element.get("type", ""),
                                    "page": element.get("page"),
                                    "bbox": bbox,
                                    "content": content,
                                    "id": element.get("id", ""),
                                    "element_id": id(element.get("element")) if "element" in element else None,
                                    "reason": "Posible encabezado/pie de página"
                                })
                
                if element.get("children"):
                    collect_potential_artifacts(element["children"])
        
        collect_potential_artifacts(elements)
        
        # Reportar posibles artefactos
        for artifact in potential_artifacts:
            issues.append({
                "checkpoint": "18-001",
                "severity": "warning",
                "description": f"Posible artefacto de paginación etiquetado como contenido real: {artifact['reason']}",
                "fix_description": "Marcar como artefacto de tipo Header o Footer",
                "fixable": True,
                "page": artifact["page"],
                "element_id": artifact["element_id"],
                "element_type": artifact["type"],
                "details": {
                    "content": artifact["content"][:50] + ("..." if len(artifact["content"]) > 50 else "")
                }
            })
        
        return issues
    
    def _is_valid_parent_child(self, parent_type: str, child_type: str) -> bool:
        """
        Verifica si la relación padre-hijo es semánticamente válida.
        
        Args:
            parent_type: Tipo del elemento padre
            child_type: Tipo del elemento hijo
            
        Returns:
            bool: True si la relación es válida
        """
        # Si no hay padre, cualquier elemento es válido en la raíz
        if not parent_type:
            return True
        
        # Si el padre es NonStruct o Private, permite cualquier hijo
        if parent_type in ["NonStruct", "Private"]:
            return True
        
        # Si el padre está en el mapa de relaciones, verificar si el hijo es válido
        if parent_type in self.valid_parent_child:
            valid_children = self.valid_parent_child[parent_type]
            return child_type in valid_children or "any" in valid_children
        
        # Por defecto, permitir la relación
        # Muchos PDFs no siguen reglas estrictas de anidamiento
        return True
    
    def _has_attribute(self, element: Dict, attribute: str) -> bool:
        """
        Verifica si un elemento tiene un atributo específico.
        
        Args:
            element: Elemento a verificar
            attribute: Nombre del atributo
            
        Returns:
            bool: True si el elemento tiene el atributo
        """
        # Verificar en el diccionario de atributos
        if "attributes" in element and attribute in element["attributes"]:
            value = element["attributes"][attribute]
            # Considerar vacío como no existente
            return value is not None and value != ""
        
        # Verificar como propiedad directa del elemento (algunos PDFs lo usan así)
        if attribute in element:
            value = element[attribute]
            return value is not None and value != ""
        
        # Verificar en el objeto pikepdf si está disponible
        if "element" in element:
            pikepdf_element = element["element"]
            # Convertir primera letra a mayúscula para formato pikepdf
            pikepdf_attr = attribute[0].upper() + attribute[1:]
            if hasattr(pikepdf_element, pikepdf_attr):
                value = getattr(pikepdf_element, pikepdf_attr)
                return value is not None and value != ""
            
            # También verificar formatos alternativos (Alt, alt, /Alt)
            alt_names = [f"/{pikepdf_attr}", attribute, attribute.upper()]
            for name in alt_names:
                if name in pikepdf_element:
                    value = pikepdf_element[name]
                    return value is not None and value != ""
        
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
        # Verificar en el diccionario de atributos
        if "attributes" in element and attribute in element["attributes"]:
            return element["attributes"][attribute]
        
        # Verificar como propiedad directa del elemento
        if attribute in element:
            return element[attribute]
        
        # Verificar en el objeto pikepdf si está disponible
        if "element" in element:
            pikepdf_element = element["element"]
            # Convertir primera letra a mayúscula para formato pikepdf
            pikepdf_attr = attribute[0].upper() + attribute[1:]
            if hasattr(pikepdf_element, pikepdf_attr):
                return getattr(pikepdf_element, pikepdf_attr)
            
            # También verificar formatos alternativos (Alt, alt, /Alt)
            alt_names = [f"/{pikepdf_attr}", attribute, attribute.upper()]
            for name in alt_names:
                if name in pikepdf_element:
                    return pikepdf_element[name]
        
        return None