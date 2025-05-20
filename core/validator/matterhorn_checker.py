#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Módulo para mapear problemas detectados con checkpoints del Matterhorn Protocol.
Proporciona información completa sobre condiciones de fallo según PDF/UA.

Referencias:
- Matterhorn Protocol 1.1 (PDF Association)
- ISO 14289-1 (PDF/UA)
"""

from typing import Dict, List, Optional, Any, Set, Tuple
import json
import os
from pathlib import Path
from collections import defaultdict
import re
from loguru import logger

class MatterhornChecker:
    """
    Clase para mapear problemas detectados con checkpoints de Matterhorn Protocol.
    
    Proporciona métodos para:
    - Obtener información detallada sobre cada checkpoint
    - Categorizar problemas según criterios específicos
    - Determinar conformidad con PDF/UA
    - Generar informes de validación detallados
    """
    
    def __init__(self):
        """Inicializa el verificador de Matterhorn con definiciones completas"""
        # Cargar todas las definiciones de checkpoints y condiciones de fallo
        self.checkpoint_definitions = self._load_checkpoint_definitions()
        self.failure_conditions = self._load_failure_conditions()
        self.checkpoint_groups = self._initialize_checkpoint_groups()
        logger.info("MatterhornChecker inicializado con todas las definiciones")

    def categorize_issues(self, issues: List[Dict]) -> Dict:
        """
        Categoriza los problemas según los checkpoints de Matterhorn.
        
        Args:
            issues: Lista de problemas detectados por diferentes validadores
            
        Returns:
            Dict: Problemas categorizados por checkpoint con detalles completos
        """
        categorized = {}
        
        for issue in issues:
            checkpoint = issue.get("checkpoint", "unknown")
            
            # Inicializar el checkpoint si no existe
            if checkpoint not in categorized:
                categorized[checkpoint] = {
                    "definition": self.get_checkpoint_info(checkpoint),
                    "issues": [],
                    "failure_conditions": self._get_failure_conditions_for_checkpoint(checkpoint),
                    "is_machine_checkable": self._is_checkpoint_machine_checkable(checkpoint),
                    "severity": self._get_checkpoint_severity(checkpoint)
                }
            
            # Agregar el problema a la categoría
            categorized[checkpoint]["issues"].append(issue)
        
        # Determinar la severidad general de cada checkpoint
        for checkpoint, data in categorized.items():
            issues_by_severity = {
                "error": len([i for i in data["issues"] if i.get("severity") == "error"]),
                "warning": len([i for i in data["issues"] if i.get("severity") == "warning"]),
                "info": len([i for i in data["issues"] if i.get("severity") == "info"])
            }
            
            data["issues_summary"] = issues_by_severity
            data["total_issues"] = sum(issues_by_severity.values())
            
            # Determinar la severidad del checkpoint basada en los problemas
            if issues_by_severity["error"] > 0:
                data["overall_severity"] = "error"
            elif issues_by_severity["warning"] > 0:
                data["overall_severity"] = "warning"
            else:
                data["overall_severity"] = "info"
        
        logger.info(f"Problemas categorizados en {len(categorized)} checkpoints")
        return categorized

    def get_checkpoint_info(self, checkpoint_id: str) -> Dict:
        """
        Obtiene información detallada sobre un checkpoint específico.
        
        Args:
            checkpoint_id: Identificador del checkpoint (p. ej., "01-001")
            
        Returns:
            Dict: Información completa del checkpoint incluyendo condiciones de fallo
        """
        # Obtener definición base del checkpoint
        base_info = self.checkpoint_definitions.get(checkpoint_id, {})
        
        if not base_info:
            logger.warning(f"Checkpoint {checkpoint_id} no encontrado")
            return {
                "title": f"Checkpoint desconocido ({checkpoint_id})",
                "description": "No hay información disponible para este checkpoint",
                "section": "Desconocido",
                "machine_checkable": False,
                "group": self._get_checkpoint_group(checkpoint_id),
                "failure_conditions": []
            }
        
        # Añadir condiciones de fallo específicas
        result = dict(base_info)
        result["group"] = self._get_checkpoint_group(checkpoint_id)
        result["failure_conditions"] = self._get_failure_conditions_for_checkpoint(checkpoint_id)
        
        return result

    def get_checkpoint_group_info(self, group_id: str) -> Dict:
        """
        Obtiene información sobre un grupo específico de checkpoints.
        
        Args:
            group_id: Identificador del grupo (p. ej., "01")
            
        Returns:
            Dict: Información del grupo con sus checkpoints
        """
        if group_id not in self.checkpoint_groups:
            logger.warning(f"Grupo de checkpoints {group_id} no encontrado")
            return {
                "title": f"Grupo desconocido ({group_id})",
                "description": "No hay información disponible para este grupo",
                "checkpoints": []
            }
        
        return self.checkpoint_groups[group_id]

    def get_pdf_ua_conformance_status(self, issues: List[Dict]) -> Dict:
        """
        Determina el estado de conformidad con PDF/UA basado en los problemas detectados.
        
        Args:
            issues: Lista de problemas detectados
            
        Returns:
            Dict: Estado de conformidad detallado
        """
        error_count = len([i for i in issues if i.get("severity") == "error"])
        warning_count = len([i for i in issues if i.get("severity") == "warning"])
        info_count = len([i for i in issues if i.get("severity") == "info"])
        
        # Agrupar problemas por checkpoint
        checkpoint_issues = defaultdict(list)
        for issue in issues:
            checkpoint = issue.get("checkpoint", "unknown")
            checkpoint_issues[checkpoint].append(issue)
        
        # Determinar checkpoints bloqueantes (con errores)
        blocking_checkpoints = []
        for checkpoint, checkpoint_issues_list in checkpoint_issues.items():
            if any(issue.get("severity") == "error" for issue in checkpoint_issues_list):
                checkpoint_info = self.get_checkpoint_info(checkpoint)
                blocking_checkpoints.append({
                    "checkpoint": checkpoint,
                    "title": checkpoint_info.get("title", "Desconocido"),
                    "section": checkpoint_info.get("section", "Desconocido"),
                    "issues_count": len(checkpoint_issues_list),
                    "machine_checkable": checkpoint_info.get("machine_checkable", False)
                })
        
        conformance = {
            "is_conformant": error_count == 0,
            "error_count": error_count,
            "warning_count": warning_count,
            "info_count": info_count,
            "total_issues": len(issues),
            "blocking_checkpoints": blocking_checkpoints,
            "fixable_issues_count": len([i for i in issues if i.get("fixable", False)]),
            "checkpoint_summary": self._generate_checkpoint_summary(checkpoint_issues)
        }
        
        return conformance

    def get_all_checkpoints(self) -> Dict:
        """
        Obtiene todos los checkpoints disponibles.
        
        Returns:
            Dict: Todos los checkpoints organizados por grupo
        """
        return {
            "groups": self.checkpoint_groups,
            "checkpoints": self.checkpoint_definitions,
            "failure_conditions": self.failure_conditions
        }

    def validate_against_checkpoint(self, checkpoint_id: str, validation_data: Dict) -> List[Dict]:
        """
        Valida datos específicos contra un checkpoint.
        
        Args:
            checkpoint_id: Identificador del checkpoint
            validation_data: Datos a validar
            
        Returns:
            List[Dict]: Problemas encontrados
        """
        issues = []
        
        # Obtener condiciones de fallo para este checkpoint
        failure_conditions = self._get_failure_conditions_for_checkpoint(checkpoint_id)
        
        # Reglas de validación específicas para cada checkpoint
        if checkpoint_id.startswith("01-"):
            # Checkpoints relacionados con el etiquetado de contenido real
            if checkpoint_id == "01-001":
                # Artifact is tagged as real content
                for element in validation_data.get("elements", []):
                    if element.get("is_artifact", False) and element.get("tagged", False):
                        issues.append(self._create_issue(
                            checkpoint_id,
                            "error",
                            f"Artefacto etiquetado como contenido real: {element.get('type')}",
                            element.get("page", 0),
                            fixable=True,
                            element_id=element.get("id")
                        ))
            
            elif checkpoint_id == "01-002":
                # Real content is marked as artifact
                for element in validation_data.get("elements", []):
                    if not element.get("is_artifact", False) and not element.get("tagged", False):
                        issues.append(self._create_issue(
                            checkpoint_id,
                            "error",
                            f"Contenido real marcado como artefacto: {element.get('type')}",
                            element.get("page", 0),
                            fixable=True,
                            element_id=element.get("id")
                        ))
            
            # Implementar reglas para otros checkpoints según sea necesario
        
        elif checkpoint_id.startswith("06-"):
            # Checkpoints relacionados con metadatos
            metadata = validation_data.get("metadata", {})
            
            if checkpoint_id == "06-001" and not metadata.get("has_xmp", False):
                issues.append(self._create_issue(
                    checkpoint_id,
                    "error",
                    "El documento no contiene un flujo de metadatos XMP",
                    fixable=True
                ))
                
            elif checkpoint_id == "06-002" and not metadata.get("pdf_ua_flag", False):
                issues.append(self._create_issue(
                    checkpoint_id,
                    "error",
                    "Los metadatos XMP no incluyen el identificador PDF/UA",
                    fixable=True
                ))
                
            elif checkpoint_id == "06-003" and not metadata.get("dc_title", False):
                issues.append(self._create_issue(
                    checkpoint_id,
                    "error",
                    "Los metadatos XMP no contienen dc:title",
                    fixable=True
                ))
                
            elif checkpoint_id == "06-004" and not metadata.get("title"):
                issues.append(self._create_issue(
                    checkpoint_id,
                    "warning",
                    "El título del documento está vacío o no identifica claramente el documento",
                    fixable=True
                ))
        
        # Agregar más lógica de validación específica para otros checkpoints
        
        return issues

    def _create_issue(self, checkpoint: str, severity: str, description: str,
                    page: Any = "all", fixable: bool = False, element_id: str = None,
                    details: Dict = None) -> Dict:
        """
        Crea un diccionario de problema estandarizado.
        
        Args:
            checkpoint: ID del checkpoint
            severity: Nivel de severidad (error, warning, info)
            description: Descripción del problema
            page: Número de página o "all" para todo el documento
            fixable: Si el problema puede corregirse automáticamente
            element_id: ID del elemento afectado (opcional)
            details: Detalles adicionales (opcional)
            
        Returns:
            Dict: Problema formateado
        """
        issue = {
            "checkpoint": checkpoint,
            "severity": severity,
            "description": description,
            "page": page,
            "fixable": fixable
        }
        
        # Agregar ID de elemento si está disponible
        if element_id:
            issue["element_id"] = element_id
            
        # Agregar detalles adicionales si están disponibles
        if details:
            issue["details"] = details
            
        # Agregar recomendación de solución
        issue["fix_description"] = self._get_fix_description(checkpoint)
            
        return issue

    def _get_fix_description(self, checkpoint: str) -> str:
        """
        Obtiene una descripción de cómo solucionar un problema basado en el checkpoint.
        
        Args:
            checkpoint: ID del checkpoint
            
        Returns:
            str: Descripción de la solución
        """
        # Mapeo de checkpoints a descripciones de solución
        fix_descriptions = {
            "01-001": "Marcar el elemento como artefacto en lugar de etiquetarlo como contenido real",
            "01-002": "Etiquetar el contenido real con la etiqueta semántica apropiada",
            "01-005": "Marcar el contenido como artefacto o etiquetarlo como contenido real",
            "01-006": "Cambiar el tipo de estructura a uno semánticamente apropiado para el contenido",
            "06-001": "Añadir metadatos XMP al documento",
            "06-002": "Añadir identificador PDF/UA (pdfuaid:part=1) a los metadatos XMP",
            "06-003": "Añadir título al documento en los metadatos XMP",
            "06-004": "Establecer un título descriptivo para el documento",
            "07-001": "Añadir entrada DisplayDocTitle al diccionario ViewerPreferences",
            "07-002": "Establecer DisplayDocTitle=true en el diccionario ViewerPreferences",
            "11-006": "Establecer el atributo Lang en el diccionario Catalog",
            "11-007": "Establecer un código de idioma válido (p. ej., 'es-ES', 'en-US')",
            "13-004": "Añadir texto alternativo (Alt) a la figura",
            "13-008": "Añadir ActualText a la figura que contiene texto",
            "14-003": "Corregir la jerarquía de encabezados para evitar saltos de nivel",
            "15-003": "Añadir atributo Scope a la celda de cabecera (Row o Column)"
        }
        
        return fix_descriptions.get(checkpoint, "Corregir según las especificaciones de PDF/UA")

    def _load_checkpoint_definitions(self) -> Dict:
        """
        Carga las definiciones completas de todos los checkpoints de Matterhorn.
        
        Returns:
            Dict: Definiciones de los checkpoints indexadas por ID
        """
        # Intentar cargar desde archivo JSON si existe
        checkpoint_file = Path(__file__).parent.parent.parent / "resources" / "matterhorn_checkpoints.json"
        
        if checkpoint_file.exists():
            try:
                with open(checkpoint_file, "r", encoding="utf-8") as f:
                    return json.load(f)
            except Exception as e:
                logger.error(f"Error al cargar definiciones de checkpoint: {e}")
        
        # Si no hay archivo o hay error, usar definiciones incorporadas
        definitions = {
            # Checkpoint 01: Real content tagged
            "01-001": {
                "title": "Artifact is tagged as real content",
                "description": "Artefacto está etiquetado como contenido real",
                "section": "UA1:7.1-1",
                "machine_checkable": False
            },
            "01-002": {
                "title": "Real content is marked as artifact",
                "description": "Contenido real está marcado como artefacto",
                "section": "UA1:7.1-1",
                "machine_checkable": False
            },
            "01-003": {
                "title": "Content marked as Artifact is present inside tagged content",
                "description": "Contenido marcado como Artefacto está presente dentro de contenido etiquetado",
                "section": "UA1:7.1-1",
                "machine_checkable": True
            },
            "01-004": {
                "title": "Tagged content is present inside content marked as Artifact",
                "description": "Contenido etiquetado está presente dentro de contenido marcado como Artefacto",
                "section": "UA1:7.1-1",
                "machine_checkable": True
            },
            "01-005": {
                "title": "Content is neither marked as Artifact nor tagged as real content",
                "description": "Contenido no está marcado como Artefacto ni etiquetado como contenido real",
                "section": "UA1:7.1-2",
                "machine_checkable": True
            },
            "01-006": {
                "title": "The structure type and attributes of a structure element are not semantically appropriate",
                "description": "El tipo de estructura y atributos de un elemento de estructura no son semánticamente apropiados",
                "section": "UA1:7.1-2",
                "machine_checkable": False
            },
            "01-007": {
                "title": "Suspects entry has a value of true",
                "description": "La entrada Suspects tiene un valor de true",
                "section": "UA1:7.1-11",
                "machine_checkable": True
            },
            
            # Checkpoint 02: Role Mapping
            "02-001": {
                "title": "Non-standard tag's mapping does not terminate with a standard type",
                "description": "El mapeo de una etiqueta no estándar no termina con un tipo estándar",
                "section": "UA1:7.1-3",
                "machine_checkable": True
            },
            "02-002": {
                "title": "Mapping of non-standard type is semantically inappropriate",
                "description": "El mapeo de un tipo no estándar es semánticamente inapropiado",
                "section": "UA1:7.1-3",
                "machine_checkable": False
            },
            "02-003": {
                "title": "A circular mapping exists",
                "description": "Existe un mapeo circular",
                "section": "UA1:7.1-3",
                "machine_checkable": True
            },
            "02-004": {
                "title": "Standard types are remapped",
                "description": "Los tipos estándar están remapeados",
                "section": "UA1:7.1-4",
                "machine_checkable": True
            },
            
            # Checkpoint 04: Color and Contrast
            "04-001": {
                "title": "Information conveyed by contrast, color, format or layout not reflected in structure",
                "description": "Información transmitida por contraste, color, formato o diseño no reflejada en la estructura",
                "section": "UA1:7.1-6",
                "machine_checkable": False
            },
            
            # Checkpoint 06: Metadata
            "06-001": {
                "title": "Document does not contain an XMP metadata stream",
                "description": "El documento no contiene un flujo de metadatos XMP",
                "section": "UA1:7.1-8",
                "machine_checkable": True
            },
            "06-002": {
                "title": "The XMP metadata stream does not include the PDF/UA identifier",
                "description": "El flujo de metadatos XMP no incluye el identificador PDF/UA",
                "section": "UA1:5",
                "machine_checkable": True
            },
            "06-003": {
                "title": "XMP metadata stream does not contain dc:title",
                "description": "El flujo de metadatos XMP no contiene dc:title",
                "section": "UA1:7.1-8",
                "machine_checkable": True
            },
            "06-004": {
                "title": "dc:title does not clearly identify the document",
                "description": "dc:title no identifica claramente el documento",
                "section": "UA1:7.1-8",
                "machine_checkable": False
            },
            
            # Checkpoint 07: Dictionary
            "07-001": {
                "title": "ViewerPreferences dictionary does not contain a DisplayDocTitle entry",
                "description": "El diccionario ViewerPreferences no contiene una entrada DisplayDocTitle",
                "section": "UA1:7.1-9",
                "machine_checkable": True
            },
            "07-002": {
                "title": "ViewerPreferences dictionary contains a DisplayDocTitle entry with value of false",
                "description": "El diccionario ViewerPreferences contiene una entrada DisplayDocTitle con valor false",
                "section": "UA1:7.1-9",
                "machine_checkable": True
            },
            
            # Checkpoint 09: Appropriate Tags
            "09-001": {
                "title": "Tags are not in logical reading order",
                "description": "Las etiquetas no están en orden lógico de lectura",
                "section": "UA1:7.2-1",
                "machine_checkable": False
            },
            "09-002": {
                "title": "Structure elements are nested in a semantically inappropriate manner",
                "description": "Los elementos de estructura están anidados de manera semánticamente inapropiada",
                "section": "UA1:7.2-1",
                "machine_checkable": False
            },
            
            # Checkpoint 11: Declared Natural Language
            "11-001": {
                "title": "Natural language for text in page content cannot be determined",
                "description": "No se puede determinar el idioma natural para el texto en el contenido de la página",
                "section": "UA1:7.2-3",
                "machine_checkable": True
            },
            "11-002": {
                "title": "Natural language for text in Alt, ActualText and E attributes cannot be determined",
                "description": "No se puede determinar el idioma natural para el texto en atributos Alt, ActualText y E",
                "section": "UA1:7.2-3",
                "machine_checkable": True
            },
            "11-006": {
                "title": "Natural language for document metadata cannot be determined",
                "description": "No se puede determinar el idioma natural para los metadatos del documento",
                "section": "UA1:7.2-3",
                "machine_checkable": True
            },
            "11-007": {
                "title": "Natural language is not appropriate",
                "description": "El idioma natural no es apropiado",
                "section": "UA1:7.2-3",
                "machine_checkable": False
            },
            
            # Checkpoint 13: Graphics
            "13-004": {
                "title": "<Figure> tag alternative or replacement text missing",
                "description": "Falta texto alternativo o de reemplazo en etiqueta <Figure>",
                "section": "UA1:7.3-3",
                "machine_checkable": True
            },
            "13-008": {
                "title": "ActualText not present when a <Figure> is intended to be consumed primarily as text",
                "description": "ActualText no está presente cuando una <Figure> está destinada a ser consumida principalmente como texto",
                "section": "UA1:7.3-4",
                "machine_checkable": False
            },
            
            # Checkpoint 14: Headings
            "14-003": {
                "title": "Numbered heading levels in descending sequence are skipped",
                "description": "Se saltan niveles de encabezado numerados en secuencia descendente",
                "section": "UA1:7.4-1",
                "machine_checkable": True
            },
            
            # Checkpoint 15: Tables
            "15-003": {
                "title": "In a table not organized with Headers attributes and IDs, a <TH> cell does not contain a Scope attribute",
                "description": "En una tabla no organizada con atributos Headers e IDs, una celda <TH> no contiene un atributo Scope",
                "section": "UA1:7.5-2",
                "machine_checkable": True
            },
            "15-005": {
                "title": "A given cell's header cannot be unambiguously determined",
                "description": "La cabecera de una celda determinada no puede determinarse sin ambigüedades",
                "section": "UA1:7.5-2",
                "machine_checkable": False
            },
            
            # Checkpoint 16: Lists
            "16-001": {
                "title": "List is an ordered list, but no value for the ListNumbering attribute is present",
                "description": "La lista es una lista ordenada, pero no hay un valor para el atributo ListNumbering",
                "section": "UA1:7.6-1",
                "machine_checkable": False
            },
            
            # Checkpoint 28: Annotations
            "28-002": {
                "title": "An annotation, other than of subtype Widget, Link and PrinterMark, is not a direct child of an <Annot> structure element",
                "description": "Una anotación, que no sea de subtipo Widget, Link o PrinterMark, no es un hijo directo de un elemento de estructura <Annot>",
                "section": "UA1:7.18.1-2",
                "machine_checkable": True
            },
            "28-004": {
                "title": "An annotation, other than of subtype Widget, does not have a Contents entry and does not have an alternative description",
                "description": "Una anotación, que no sea de subtipo Widget, no tiene una entrada Contents y no tiene una descripción alternativa",
                "section": "UA1:7.18.1-4",
                "machine_checkable": True
            },
            "28-011": {
                "title": "A link annotation is not nested within a <Link> tag",
                "description": "Una anotación de enlace no está anidada dentro de una etiqueta <Link>",
                "section": "UA1:7.18.5-1",
                "machine_checkable": True
            }
        }
        
        return definitions

    def _load_failure_conditions(self) -> Dict:
        """
        Carga todas las condiciones de fallo para todos los checkpoints.
        
        Returns:
            Dict: Condiciones de fallo indexadas por checkpoint
        """
        # Lista completa de todas las condiciones de fallo por checkpoint
        conditions = {}
        
        # Para cada checkpoint en las definiciones, crear una entrada en condiciones
        for checkpoint_id, definition in self.checkpoint_definitions.items():
            checkpoint_group = self._get_checkpoint_group(checkpoint_id)
            checkpoint_number = checkpoint_id.split("-")[1] if "-" in checkpoint_id else "000"
            
            # Determinar si es comprobable por máquina
            machine_checkable = definition.get("machine_checkable", False)
            
            # Crear condición de fallo
            condition = {
                "index": checkpoint_number,
                "failure_condition": definition.get("description", "Desconocido"),
                "section": definition.get("section", ""),
                "type": self._determine_condition_type(checkpoint_id),
                "how": "M" if machine_checkable else "H",
                "see": ""
            }
            
            conditions[checkpoint_id] = condition
        
        return conditions

    def _determine_condition_type(self, checkpoint_id: str) -> str:
        """
        Determina el tipo de condición basado en el checkpoint.
        
        Args:
            checkpoint_id: ID del checkpoint
            
        Returns:
            str: Tipo de condición (Doc, Page, Object, JS, All)
        """
        # Mapeo de checkpoints a tipos de condición
        type_map = {
            # Doc (aspectos del documento en su conjunto)
            "doc": ["06-001", "06-002", "06-003", "06-004", "07-001", "07-002", "11-006"],
            
            # Page (páginas dentro del documento)
            "page": ["03-001", "08-001", "08-002"],
            
            # JS (JavaScript embebido)
            "js": ["03-003", "05-003", "29-001"],
            
            # All (todos los aspectos del documento)
            "all": ["11-007"]
        }
        
        # Determinar tipo basado en mapeo
        for type_name, checkpoints in type_map.items():
            if checkpoint_id in checkpoints:
                return type_name.upper()
        
        # Por defecto, asumir Object (elementos individuales de datos)
        return "Object"

    def _initialize_checkpoint_groups(self) -> Dict:
        """
        Inicializa los grupos de checkpoints con información detallada.
        
        Returns:
            Dict: Grupos de checkpoints con títulos y descripciones
        """
        # Definiciones de grupos
        groups = {
            "01": {
                "title": "Etiquetado de contenido real",
                "description": "Etiquetado adecuado de contenido real frente a artefactos",
                "checkpoints": {}
            },
            "02": {
                "title": "Mapeo de roles",
                "description": "Mapeo apropiado de tipos de etiquetas personalizadas a tipos estándar",
                "checkpoints": {}
            },
            "03": {
                "title": "Parpadeo",
                "description": "Contenido que parpadea y puede causar problemas de accesibilidad",
                "checkpoints": {}
            },
            "04": {
                "title": "Color y contraste",
                "description": "Uso adecuado del color y contraste para transmitir información",
                "checkpoints": {}
            },
            "05": {
                "title": "Sonido",
                "description": "Accesibilidad del contenido de audio",
                "checkpoints": {}
            },
            "06": {
                "title": "Metadatos",
                "description": "Presencia y calidad de metadatos requeridos",
                "checkpoints": {}
            },
            "07": {
                "title": "Diccionario",
                "description": "Configuración correcta del diccionario de preferencias del visor",
                "checkpoints": {}
            },
            "08": {
                "title": "Validación OCR",
                "description": "Calidad del texto generado por OCR",
                "checkpoints": {}
            },
            "09": {
                "title": "Etiquetas apropiadas",
                "description": "Uso adecuado de etiquetas estructurales",
                "checkpoints": {}
            },
            "10": {
                "title": "Mapeo de caracteres",
                "description": "Mapeo de caracteres a Unicode",
                "checkpoints": {}
            },
            "11": {
                "title": "Idioma natural declarado",
                "description": "Declaración adecuada del idioma natural del contenido",
                "checkpoints": {}
            },
            "12": {
                "title": "Caracteres extensibles",
                "description": "Representación de caracteres estirados",
                "checkpoints": {}
            },
            "13": {
                "title": "Gráficos",
                "description": "Etiquetado y descripción de gráficos",
                "checkpoints": {}
            },
            "14": {
                "title": "Encabezados",
                "description": "Estructura y uso de encabezados",
                "checkpoints": {}
            },
            "15": {
                "title": "Tablas",
                "description": "Estructura y accesibilidad de tablas",
                "checkpoints": {}
            },
            "16": {
                "title": "Listas",
                "description": "Estructura y marcado de listas",
                "checkpoints": {}
            },
            "17": {
                "title": "Expresiones matemáticas",
                "description": "Etiquetado y descripción de fórmulas matemáticas",
                "checkpoints": {}
            },
            "18": {
                "title": "Encabezados y pies de página",
                "description": "Marcado de encabezados y pies de página como artefactos",
                "checkpoints": {}
            },
            "19": {
                "title": "Notas y referencias",
                "description": "Etiquetado de notas al pie, notas finales y referencias",
                "checkpoints": {}
            },
            "20": {
                "title": "Contenido opcional",
                "description": "Configuración del contenido opcional",
                "checkpoints": {}
            },
            "21": {
                "title": "Archivos embebidos",
                "description": "Inclusión correcta de archivos embebidos",
                "checkpoints": {}
            },
            "22": {
                "title": "Hilos de artículo",
                "description": "Orden lógico de los hilos de artículo",
                "checkpoints": {}
            },
            "23": {
                "title": "Firmas digitales",
                "description": "Uso correcto de firmas digitales",
                "checkpoints": {}
            },
            "24": {
                "title": "Formularios no interactivos",
                "description": "Etiquetado de formularios no interactivos",
                "checkpoints": {}
            },
            "25": {
                "title": "XFA",
                "description": "Uso de XFA (XML Forms Architecture)",
                "checkpoints": {}
            },
            "26": {
                "title": "Seguridad",
                "description": "Configuración de seguridad que no impide la accesibilidad",
                "checkpoints": {}
            },
            "27": {
                "title": "Navegación",
                "description": "Elementos de navegación accesibles",
                "checkpoints": {}
            },
            "28": {
                "title": "Anotaciones",
                "description": "Accesibilidad de las anotaciones",
                "checkpoints": {}
            },
            "29": {
                "title": "Acciones",
                "description": "Accesibilidad de las acciones",
                "checkpoints": {}
            },
            "30": {
                "title": "XObjects",
                "description": "Uso adecuado de XObjects",
                "checkpoints": {}
            },
            "31": {
                "title": "Fuentes",
                "description": "Incrustación y configuración de fuentes",
                "checkpoints": {}
            }
        }
        
        # Llenar los checkpoints para cada grupo
        for checkpoint_id, definition in self.checkpoint_definitions.items():
            group_id = self._get_checkpoint_group(checkpoint_id)
            
            if group_id in groups:
                groups[group_id]["checkpoints"][checkpoint_id] = {
                    "title": definition.get("title", ""),
                    "description": definition.get("description", ""),
                    "machine_checkable": definition.get("machine_checkable", False)
                }
        
        return groups

    def _get_checkpoint_group(self, checkpoint_id: str) -> str:
        """
        Obtiene el grupo al que pertenece un checkpoint.
        
        Args:
            checkpoint_id: ID del checkpoint
            
        Returns:
            str: ID del grupo
        """
        if "-" in checkpoint_id:
            return checkpoint_id.split("-")[0]
        
        return "00"  # Grupo desconocido

    def _get_failure_conditions_for_checkpoint(self, checkpoint_id: str) -> List[Dict]:
        """
        Obtiene todas las condiciones de fallo para un checkpoint específico.
        
        Args:
            checkpoint_id: ID del checkpoint
            
        Returns:
            List[Dict]: Lista de condiciones de fallo
        """
        if checkpoint_id in self.failure_conditions:
            return [self.failure_conditions[checkpoint_id]]
        
        # Si el checkpoint exacto no se encuentra, buscar condiciones en el mismo grupo
        group = self._get_checkpoint_group(checkpoint_id)
        conditions = []
        
        for cond_id, condition in self.failure_conditions.items():
            if cond_id.startswith(f"{group}-"):
                conditions.append(condition)
        
        return conditions

    def _is_checkpoint_machine_checkable(self, checkpoint_id: str) -> bool:
        """
        Determina si un checkpoint es verificable por máquina.
        
        Args:
            checkpoint_id: ID del checkpoint
            
        Returns:
            bool: True si es verificable por máquina
        """
        if checkpoint_id in self.checkpoint_definitions:
            return self.checkpoint_definitions[checkpoint_id].get("machine_checkable", False)
        
        return False

    def _get_checkpoint_severity(self, checkpoint_id: str) -> str:
        """
        Determina la severidad predeterminada de un checkpoint.
        
        Args:
            checkpoint_id: ID del checkpoint
            
        Returns:
            str: Severidad (error, warning, info)
        """
        # Checkpoints que siempre son errores críticos
        error_checkpoints = [
            "01-005", "06-001", "06-002", "06-003", "07-001", "07-002",
            "13-004", "14-003", "15-003", "28-002", "28-004", "28-011"
        ]
        
        # Checkpoints que son advertencias
        warning_checkpoints = [
            "01-006", "02-002", "04-001", "06-004", "11-007", "13-008",
            "16-001"
        ]
        
        if checkpoint_id in error_checkpoints:
            return "error"
        elif checkpoint_id in warning_checkpoints:
            return "warning"
        
        # Por defecto, info
        return "info"

    def _generate_checkpoint_summary(self, checkpoint_issues: Dict) -> Dict:
        """
        Genera un resumen de los problemas por checkpoint.
        
        Args:
            checkpoint_issues: Diccionario de problemas agrupados por checkpoint
            
        Returns:
            Dict: Resumen de checkpoints con conteos
        """
        summary = {}
        
        for checkpoint, issues in checkpoint_issues.items():
            error_count = len([i for i in issues if i.get("severity") == "error"])
            warning_count = len([i for i in issues if i.get("severity") == "warning"])
            info_count = len([i for i in issues if i.get("severity") == "info"])
            fixable_count = len([i for i in issues if i.get("fixable", False)])
            
            group = self._get_checkpoint_group(checkpoint)
            
            # Inicializar grupo si no existe
            if group not in summary:
                summary[group] = {
                    "title": self.checkpoint_groups.get(group, {}).get("title", f"Grupo {group}"),
                    "checkpoints": {},
                    "error_count": 0,
                    "warning_count": 0,
                    "info_count": 0,
                    "total_count": 0,
                    "fixable_count": 0
                }
            
            # Añadir información del checkpoint
            summary[group]["checkpoints"][checkpoint] = {
                "title": self.checkpoint_definitions.get(checkpoint, {}).get("title", f"Checkpoint {checkpoint}"),
                "error_count": error_count,
                "warning_count": warning_count,
                "info_count": info_count,
                "total_count": len(issues),
                "fixable_count": fixable_count
            }
            
            # Actualizar conteos del grupo
            summary[group]["error_count"] += error_count
            summary[group]["warning_count"] += warning_count
            summary[group]["info_count"] += info_count
            summary[group]["total_count"] += len(issues)
            summary[group]["fixable_count"] += fixable_count
        
        return summary