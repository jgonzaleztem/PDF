#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Módulo para generar informes de conformidad PDF/UA.
Crea informes detallados en HTML, PDF y texto plano.

Este módulo facilita la generación de diferentes formatos de reporte
para documentar el nivel de conformidad PDF/UA de un documento, basado
en los checkpoints de Matterhorn Protocol y otros estándares.
"""

import os
import json
import datetime
import tempfile
from pathlib import Path
from typing import Dict, List, Optional, Any, Union
import weasyprint
import markdown2
import jinja2
from loguru import logger
import matplotlib.pyplot as plt
import matplotlib
matplotlib.use('Agg')  # Usar backend no interactivo

class PDFUAReporter:
    """
    Generador de informes de conformidad PDF/UA.
    
    Crea informes detallados sobre la conformidad de documentos PDF
    con el estándar PDF/UA (ISO 14289-1) y Matterhorn Protocol.
    Soporta múltiples formatos de salida: HTML, PDF, texto y JSON.
    """
    
    def __init__(self):
        """Inicializa el generador de informes."""
        # Información del documento
        self.document_info = {}
        
        # Problemas detectados
        self.issues = []
        
        # Resumen calculado
        self.summary = {}
        
        # Plantillas
        self.templates_dir = self._get_templates_dir()
        self.template_env = self._initialize_templates()
        
        # Recursos estáticos (CSS, imágenes)
        self.resources_dir = self._get_resources_dir()
        
        logger.info("PDFUAReporter inicializado")
    
    def set_document_info(self, info: Dict[str, Any]):
        """
        Establece la información básica del documento.
        
        Args:
            info: Diccionario con información del documento (título, ruta, páginas, etc.)
        """
        self.document_info = info
        logger.debug(f"Información del documento establecida: {info.get('filename', '')}")
    
    def add_issues(self, issues: List[Dict[str, Any]]):
        """
        Añade problemas detectados al informe.
        
        Args:
            issues: Lista de problemas detectados por los validadores
        """
        self.issues = issues
        logger.info(f"Añadidos {len(issues)} problemas al informe")
    
    def generate_summary(self) -> Dict[str, Any]:
        """
        Genera un resumen de los problemas y el nivel de conformidad.
        
        Returns:
            Dict: Resumen con estadísticas y métricas de conformidad
        """
        # Inicializar resumen
        summary = {
            "total_issues": len(self.issues),
            "error_count": 0,
            "warning_count": 0,
            "info_count": 0,
            "fixable_count": 0,
            "categories": {},
            "checkpoints": {}
        }
        
        # Contar por severidad y capacidad de corrección
        for issue in self.issues:
            severity = issue.get("severity", "info")
            
            if severity == "error":
                summary["error_count"] += 1
            elif severity == "warning":
                summary["warning_count"] += 1
            else:
                summary["info_count"] += 1
                
            if issue.get("fixable", False):
                summary["fixable_count"] += 1
        
        # Agrupar por categoría de checkpoint
        checkpoint_categories = {
            "01": "Estructura real etiquetada",
            "02": "Mapeo de roles",
            "03": "Parpadeo",
            "04": "Color y contraste",
            "05": "Sonido",
            "06": "Metadatos",
            "07": "Diccionario",
            "08": "Validación OCR",
            "09": "Etiquetas apropiadas",
            "10": "Mapeo de caracteres",
            "11": "Idioma natural declarado",
            "12": "Caracteres extensibles",
            "13": "Gráficos",
            "14": "Encabezados",
            "15": "Tablas",
            "16": "Listas",
            "17": "Expresiones matemáticas",
            "18": "Encabezados y pies de página",
            "19": "Notas y referencias",
            "20": "Contenido opcional",
            "21": "Archivos embebidos",
            "22": "Hilos de artículo",
            "23": "Firmas digitales",
            "24": "Formularios no interactivos",
            "25": "XFA",
            "26": "Seguridad",
            "27": "Navegación",
            "28": "Anotaciones",
            "29": "Acciones",
            "30": "XObjects",
            "31": "Fuentes"
        }
        
        # Inicializar categorías
        for category_id, category_name in checkpoint_categories.items():
            summary["categories"][category_id] = {
                "name": category_name,
                "error_count": 0,
                "warning_count": 0,
                "info_count": 0,
                "total_count": 0,
                "checkpoints": {}
            }
        
        # Agrupar problemas por checkpoint
        for issue in self.issues:
            checkpoint = issue.get("checkpoint", "unknown")
            severity = issue.get("severity", "info")
            
            # Extraer categoría (primeros 2 caracteres del checkpoint)
            category = checkpoint.split("-")[0] if "-" in checkpoint else "00"
            
            # Si la categoría no existe, añadirla
            if category not in summary["categories"]:
                summary["categories"][category] = {
                    "name": f"Categoría {category}",
                    "error_count": 0,
                    "warning_count": 0,
                    "info_count": 0,
                    "total_count": 0,
                    "checkpoints": {}
                }
            
            # Actualizar contadores de categoría
            category_data = summary["categories"][category]
            category_data["total_count"] += 1
            
            if severity == "error":
                category_data["error_count"] += 1
            elif severity == "warning":
                category_data["warning_count"] += 1
            else:
                category_data["info_count"] += 1
            
            # Inicializar checkpoint si no existe
            if checkpoint not in category_data["checkpoints"]:
                category_data["checkpoints"][checkpoint] = {
                    "error_count": 0,
                    "warning_count": 0,
                    "info_count": 0,
                    "total_count": 0,
                    "issues": []
                }
            
            # Actualizar contadores de checkpoint
            checkpoint_data = category_data["checkpoints"][checkpoint]
            checkpoint_data["total_count"] += 1
            
            if severity == "error":
                checkpoint_data["error_count"] += 1
            elif severity == "warning":
                checkpoint_data["warning_count"] += 1
            else:
                checkpoint_data["info_count"] += 1
                
            # Añadir el problema a la lista del checkpoint
            checkpoint_data["issues"].append(issue)
            
            # También añadir a la lista global de checkpoints
            if checkpoint not in summary["checkpoints"]:
                summary["checkpoints"][checkpoint] = {
                    "error_count": 0,
                    "warning_count": 0,
                    "info_count": 0,
                    "total_count": 0,
                    "category": category,
                    "category_name": category_data["name"]
                }
            
            summary["checkpoints"][checkpoint]["total_count"] += 1
            
            if severity == "error":
                summary["checkpoints"][checkpoint]["error_count"] += 1
            elif severity == "warning":
                summary["checkpoints"][checkpoint]["warning_count"] += 1
            else:
                summary["checkpoints"][checkpoint]["info_count"] += 1
        
        # Calcular conformidad global
        # PDF/UA requiere que no haya violaciones de criterios obligatorios
        is_conformant = summary["error_count"] == 0
        conformance_level = "Conforme" if is_conformant else "No conforme"
        
        # Encontrar checkpoints bloqueantes (con errores)
        blocking_checkpoints = []
        for checkpoint, data in summary["checkpoints"].items():
            if data["error_count"] > 0:
                blocking_checkpoints.append({
                    "id": checkpoint,
                    "category": data["category"],
                    "category_name": data["category_name"],
                    "error_count": data["error_count"]
                })
        
        # Calcular nivel de madurez (porcentaje de conformidad)
        total_checks = 31  # Total de categorías de Matterhorn
        failing_categories = len([c for c in summary["categories"].values() 
                               if c["error_count"] > 0])
        
        maturity_level = max(0, min(100, int(100 * (1 - failing_categories / total_checks))))
        
        # Añadir métricas de conformidad al resumen
        summary["conformance"] = {
            "is_conformant": is_conformant,
            "level": conformance_level,
            "maturity_level": maturity_level,
            "blocking_checkpoints": blocking_checkpoints,
            "blocking_count": len(blocking_checkpoints),
            "fixable_percentage": int(100 * summary["fixable_count"] / max(summary["total_issues"], 1))
        }
        
        # Actualizar recomendaciones principales
        summary["recommendations"] = self._generate_recommendations(summary)
        
        # Guardar el resumen calculado
        self.summary = summary
        logger.info(f"Resumen generado: {conformance_level}, {maturity_level}% de madurez")
        
        return summary
    
    def generate_html_report(self, output_path: Optional[str] = None) -> str:
        """
        Genera un informe en formato HTML.
        
        Args:
            output_path: Ruta opcional donde guardar el HTML generado
            
        Returns:
            str: Contenido HTML del informe
        """
        # Asegurar que tenemos un resumen
        if not self.summary:
            self.generate_summary()
        
        # Generar gráficos
        charts = self._generate_charts()
        
        # Preparar contexto para la plantilla
        context = {
            "document": self.document_info,
            "summary": self.summary,
            "issues": self.issues,
            "date": datetime.datetime.now().strftime("%Y-%m-%d %H:%M"),
            "charts": charts
        }
        
        # Renderizar plantilla HTML
        template = self.template_env.get_template("report.html")
        html_content = template.render(**context)
        
        # Guardar en archivo si se especificó una ruta
        if output_path:
            try:
                with open(output_path, "w", encoding="utf-8") as f:
                    f.write(html_content)
                logger.info(f"Informe HTML guardado en: {output_path}")
            except Exception as e:
                logger.error(f"Error al guardar informe HTML: {e}")
        
        return html_content
    
    def generate_pdf_report(self, output_path: str) -> bool:
        """
        Genera un informe en formato PDF.
        
        Args:
            output_path: Ruta donde guardar el PDF generado
            
        Returns:
            bool: True si se generó correctamente
        """
        try:
            # Generar HTML primero
            html_content = self.generate_html_report()
            
            # Crear directorio temporal para recursos
            with tempfile.TemporaryDirectory() as temp_dir:
                # Guardar HTML temporal
                temp_html = os.path.join(temp_dir, "report.html")
                with open(temp_html, "w", encoding="utf-8") as f:
                    f.write(html_content)
                
                # Copiar recursos necesarios (CSS, imágenes)
                self._copy_resources_for_pdf(temp_dir)
                
                # Convertir HTML a PDF
                pdf = weasyprint.HTML(filename=temp_html).write_pdf()
                
                # Guardar PDF
                with open(output_path, "wb") as f:
                    f.write(pdf)
                
                logger.info(f"Informe PDF guardado en: {output_path}")
                return True
                
        except Exception as e:
            logger.error(f"Error al generar informe PDF: {e}")
            return False
    
    def generate_text_report(self, output_path: Optional[str] = None) -> str:
        """
        Genera un informe en formato texto plano.
        
        Args:
            output_path: Ruta opcional donde guardar el texto generado
            
        Returns:
            str: Contenido de texto del informe
        """
        # Asegurar que tenemos un resumen
        if not self.summary:
            self.generate_summary()
        
        lines = []
        
        # Encabezado
        lines.append("=" * 80)
        lines.append(f"INFORME DE CONFORMIDAD PDF/UA")
        lines.append("=" * 80)
        lines.append("")
        
        # Información del documento
        lines.append("INFORMACIÓN DEL DOCUMENTO")
        lines.append("-" * 30)
        lines.append(f"Archivo: {self.document_info.get('filename', 'Desconocido')}")
        lines.append(f"Ruta: {self.document_info.get('path', 'Desconocida')}")
        lines.append(f"Páginas: {self.document_info.get('pages', 0)}")
        lines.append(f"Fecha análisis: {datetime.datetime.now().strftime('%Y-%m-%d %H:%M')}")
        lines.append("")
        
        # Resumen de conformidad
        conformance = self.summary.get("conformance", {})
        lines.append("RESULTADO DE CONFORMIDAD")
        lines.append("-" * 30)
        lines.append(f"Nivel: {conformance.get('level', 'Desconocido')}")
        lines.append(f"Nivel de madurez: {conformance.get('maturity_level', 0)}%")
        lines.append(f"Problemas bloqueantes: {conformance.get('blocking_count', 0)}")
        lines.append("")
        
        # Estadísticas
        lines.append("ESTADÍSTICAS")
        lines.append("-" * 30)
        lines.append(f"Total problemas: {self.summary.get('total_issues', 0)}")
        lines.append(f"Errores: {self.summary.get('error_count', 0)}")
        lines.append(f"Advertencias: {self.summary.get('warning_count', 0)}")
        lines.append(f"Informativo: {self.summary.get('info_count', 0)}")
        lines.append(f"Corregibles automáticamente: {self.summary.get('fixable_count', 0)} ({self.summary.get('conformance', {}).get('fixable_percentage', 0)}%)")
        lines.append("")
        
        # Recomendaciones
        lines.append("RECOMENDACIONES PRINCIPALES")
        lines.append("-" * 30)
        for rec in self.summary.get("recommendations", []):
            lines.append(f"- {rec}")
        lines.append("")
        
        # Problemas por categoría
        lines.append("PROBLEMAS POR CATEGORÍA")
        lines.append("-" * 30)
        categories = self.summary.get("categories", {})
        for cat_id, cat_data in sorted(categories.items()):
            if cat_data["total_count"] == 0:
                continue
                
            lines.append(f"{cat_id}: {cat_data['name']} - {cat_data['total_count']} problemas")
            lines.append(f"  Errores: {cat_data['error_count']}, Advertencias: {cat_data['warning_count']}, Info: {cat_data['info_count']}")
            
            # Checkpoints dentro de esta categoría
            for checkpoint, cp_data in cat_data.get("checkpoints", {}).items():
                if cp_data["total_count"] == 0:
                    continue
                    
                lines.append(f"  {checkpoint} - {cp_data['total_count']} problemas")
                
                # Mostrar algunos ejemplos de problemas
                for i, issue in enumerate(cp_data.get("issues", [])[:3]):  # Mostrar máximo 3 ejemplos
                    desc = issue.get("description", "Sin descripción")
                    page = issue.get("page", "?")
                    page_info = f"página {page}" if page != "all" else "todo el documento"
                    lines.append(f"    - {desc} ({page_info})")
                
                if len(cp_data.get("issues", [])) > 3:
                    lines.append(f"    - ... y {len(cp_data.get('issues', [])) - 3} problemas más")
        
        # Unir todo en un texto
        text_report = "\n".join(lines)
        
        # Guardar en archivo si se especificó una ruta
        if output_path:
            try:
                with open(output_path, "w", encoding="utf-8") as f:
                    f.write(text_report)
                logger.info(f"Informe de texto guardado en: {output_path}")
            except Exception as e:
                logger.error(f"Error al guardar informe de texto: {e}")
        
        return text_report
    
    def export_json(self, output_path: str) -> bool:
        """
        Exporta el informe completo en formato JSON.
        
        Args:
            output_path: Ruta donde guardar el JSON
            
        Returns:
            bool: True si se exportó correctamente
        """
        try:
            # Asegurar que tenemos un resumen
            if not self.summary:
                self.generate_summary()
            
            # Crear objeto de exportación
            export_data = {
                "document": self.document_info,
                "summary": self.summary,
                "issues": self.issues,
                "date": datetime.datetime.now().strftime("%Y-%m-%d %H:%M")
            }
            
            # Guardar JSON
            with open(output_path, "w", encoding="utf-8") as f:
                json.dump(export_data, f, indent=2, ensure_ascii=False)
                
            logger.info(f"Datos JSON exportados a: {output_path}")
            return True
            
        except Exception as e:
            logger.error(f"Error al exportar JSON: {e}")
            return False
    
    def _generate_charts(self) -> Dict[str, str]:
        """
        Genera gráficos para el informe.
        
        Returns:
            Dict[str, str]: Rutas a los gráficos generados
        """
        charts = {}
        
        try:
            # Crear directorio temporal para los gráficos
            charts_dir = tempfile.mkdtemp()
            
            # 1. Gráfico de severidad
            severity_counts = [
                self.summary.get("error_count", 0),
                self.summary.get("warning_count", 0),
                self.summary.get("info_count", 0)
            ]
            
            if sum(severity_counts) > 0:
                plt.figure(figsize=(6, 4))
                bars = plt.bar(
                    ["Errores", "Advertencias", "Info"],
                    severity_counts,
                    color=["#ff4d4d", "#ffcc00", "#3399ff"]
                )
                
                # Añadir valores sobre las barras
                for bar in bars:
                    height = bar.get_height()
                    plt.text(
                        bar.get_x() + bar.get_width()/2.,
                        height + 0.1,
                        str(int(height)),
                        ha='center',
                        fontsize=9
                    )
                
                plt.title("Problemas por severidad")
                plt.tight_layout()
                
                severity_chart_path = os.path.join(charts_dir, "severity.png")
                plt.savefig(severity_chart_path, dpi=100, bbox_inches="tight")
                plt.close()
                
                charts["severity"] = severity_chart_path
            
            # 2. Gráfico de categorías principales
            categories = self.summary.get("categories", {})
            cat_labels = []
            cat_errors = []
            cat_warnings = []
            
            # Seleccionar hasta 10 categorías con más problemas
            top_categories = sorted(
                categories.items(),
                key=lambda x: x[1]["total_count"],
                reverse=True
            )[:10]
            
            for cat_id, cat_data in top_categories:
                if cat_data["total_count"] == 0:
                    continue
                    
                cat_labels.append(cat_id)
                cat_errors.append(cat_data["error_count"])
                cat_warnings.append(cat_data["warning_count"])
            
            if cat_labels:
                plt.figure(figsize=(8, 5))
                
                x = range(len(cat_labels))
                width = 0.35
                
                plt.bar([i - width/2 for i in x], cat_errors, width, label='Errores', color='#ff4d4d')
                plt.bar([i + width/2 for i in x], cat_warnings, width, label='Advertencias', color='#ffcc00')
                
                plt.xlabel('Categorías')
                plt.ylabel('Número de problemas')
                plt.title('Problemas por categoría')
                plt.xticks(x, cat_labels)
                plt.legend()
                plt.tight_layout()
                
                categories_chart_path = os.path.join(charts_dir, "categories.png")
                plt.savefig(categories_chart_path, dpi=100, bbox_inches="tight")
                plt.close()
                
                charts["categories"] = categories_chart_path
            
            # 3. Gráfico de nivel de madurez
            maturity_level = self.summary.get("conformance", {}).get("maturity_level", 0)
            
            plt.figure(figsize=(6, 3))
            plt.barh(["Madurez"], [maturity_level], color="#3399ff")
            plt.barh(["Madurez"], [100 - maturity_level], left=[maturity_level], color="#dddddd")
            
            plt.xlim(0, 100)
            plt.title("Nivel de madurez PDF/UA")
            plt.text(maturity_level / 2, 0, f"{maturity_level}%", 
                    ha='center', va='center', color='white', fontweight='bold')
            
            plt.tight_layout()
            
            maturity_chart_path = os.path.join(charts_dir, "maturity.png")
            plt.savefig(maturity_chart_path, dpi=100, bbox_inches="tight")
            plt.close()
            
            charts["maturity"] = maturity_chart_path
            
            return charts
            
        except Exception as e:
            logger.error(f"Error al generar gráficos: {e}")
            return {}
    
    def _copy_resources_for_pdf(self, target_dir: str):
        """
        Copia recursos necesarios para la generación de PDF.
        
        Args:
            target_dir: Directorio destino para los recursos
        """
        try:
            # Crear directorio CSS si no existe
            css_dir = os.path.join(target_dir, "css")
            os.makedirs(css_dir, exist_ok=True)
            
            # Copiar CSS
            css_source = os.path.join(self.resources_dir, "css", "report.css")
            css_dest = os.path.join(css_dir, "report.css")
            
            if os.path.exists(css_source):
                with open(css_source, "r", encoding="utf-8") as f_src:
                    css_content = f_src.read()
                    
                with open(css_dest, "w", encoding="utf-8") as f_dest:
                    f_dest.write(css_content)
            else:
                # Si no existe el CSS, crear uno básico
                with open(css_dest, "w", encoding="utf-8") as f:
                    f.write(self._get_default_css())
                    
            logger.debug(f"Recursos copiados a: {target_dir}")
                
        except Exception as e:
            logger.error(f"Error al copiar recursos para PDF: {e}")
    
    def _get_templates_dir(self) -> str:
        """
        Obtiene el directorio de plantillas.
        
        Returns:
            str: Ruta al directorio de plantillas
        """
        # Buscar en varias ubicaciones posibles
        possible_locations = [
            os.path.join(os.path.dirname(__file__), "templates"),
            os.path.join(os.path.dirname(__file__), "..", "resources", "templates"),
            os.path.join(os.path.dirname(__file__), "..", "..", "resources", "templates")
        ]
        
        for location in possible_locations:
            if os.path.isdir(location):
                return location
        
        # Si no se encuentra, crear un directorio temporal
        temp_dir = tempfile.mkdtemp()
        logger.warning(f"No se encontró directorio de plantillas, usando directorio temporal: {temp_dir}")
        return temp_dir
    
    def _get_resources_dir(self) -> str:
        """
        Obtiene el directorio de recursos estáticos.
        
        Returns:
            str: Ruta al directorio de recursos
        """
        # Buscar en varias ubicaciones posibles
        possible_locations = [
            os.path.join(os.path.dirname(__file__), "resources"),
            os.path.join(os.path.dirname(__file__), "..", "resources"),
            os.path.join(os.path.dirname(__file__), "..", "..", "resources")
        ]
        
        for location in possible_locations:
            if os.path.isdir(location):
                return location
        
        # Si no se encuentra, crear un directorio temporal
        temp_dir = tempfile.mkdtemp()
        logger.warning(f"No se encontró directorio de recursos, usando directorio temporal: {temp_dir}")
        return temp_dir
    
    def _initialize_templates(self) -> jinja2.Environment:
        """
        Inicializa el entorno de plantillas Jinja2.
        
        Returns:
            jinja2.Environment: Entorno de plantillas configurado
        """
        # Crear entorno de plantillas
        try:
            env = jinja2.Environment(
                loader=jinja2.FileSystemLoader(self.templates_dir),
                autoescape=jinja2.select_autoescape(['html', 'xml'])
            )
            
            # Verificar si existe la plantilla principal
            if not os.path.exists(os.path.join(self.templates_dir, "report.html")):
                # Crear plantilla básica
                self._create_default_templates()
            
            return env
            
        except Exception as e:
            logger.error(f"Error al inicializar plantillas: {e}")
            
            # Crear entorno alternativo con plantilla en memoria
            env = jinja2.Environment(
                loader=jinja2.DictLoader({
                    'report.html': self._get_default_html_template()
                }),
                autoescape=jinja2.select_autoescape(['html', 'xml'])
            )
            
            return env
    
    def _create_default_templates(self):
        """Crea plantillas predeterminadas si no existen."""
        try:
            os.makedirs(self.templates_dir, exist_ok=True)
            
            # Crear plantilla HTML principal
            with open(os.path.join(self.templates_dir, "report.html"), "w", encoding="utf-8") as f:
                f.write(self._get_default_html_template())
                
            # Crear directorio CSS si no existe
            css_dir = os.path.join(self.resources_dir, "css")
            os.makedirs(css_dir, exist_ok=True)
            
            # Crear CSS predeterminado
            with open(os.path.join(css_dir, "report.css"), "w", encoding="utf-8") as f:
                f.write(self._get_default_css())
                
            logger.info("Creadas plantillas predeterminadas")
                
        except Exception as e:
            logger.error(f"Error al crear plantillas predeterminadas: {e}")
    
    def _get_default_html_template(self) -> str:
        """
        Obtiene una plantilla HTML predeterminada.
        
        Returns:
            str: Contenido de la plantilla HTML
        """
        return """<!DOCTYPE html>
<html lang="es">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>Informe de Conformidad PDF/UA</title>
    <link rel="stylesheet" href="css/report.css">
    <style>
        /* Estilos inline básicos por si falla la carga del CSS externo */
        body { font-family: Arial, sans-serif; line-height: 1.6; color: #333; max-width: 1200px; margin: 0 auto; padding: 20px; }
        h1, h2, h3 { color: #205493; }
        .error { color: #d83933; }
        .warning { color: #fdb81e; }
        .info { color: #02bfe7; }
        table { border-collapse: collapse; width: 100%; margin-bottom: 20px; }
        th, td { text-align: left; padding: 8px; border-bottom: 1px solid #ddd; }
        th { background-color: #f1f1f1; }
    </style>
</head>
<body>
    <header>
        <h1>Informe de Conformidad PDF/UA</h1>
        <p>Fecha: {{ date }}</p>
    </header>

    <section id="document-info">
        <h2>Información del Documento</h2>
        <table>
            <tr>
                <th>Archivo:</th>
                <td>{{ document.filename }}</td>
            </tr>
            <tr>
                <th>Ruta:</th>
                <td>{{ document.path }}</td>
            </tr>
            <tr>
                <th>Páginas:</th>
                <td>{{ document.pages }}</td>
            </tr>
            <tr>
                <th>Estructura:</th>
                <td>{{ "Presente" if document.has_structure else "Ausente" }}</td>
            </tr>
        </table>
    </section>

    <section id="conformance">
        <h2>Resultado de Conformidad</h2>
        <div class="conformance-box {{ 'conformant' if summary.conformance.is_conformant else 'non-conformant' }}">
            <h3>Nivel: {{ summary.conformance.level }}</h3>
            <p>Nivel de madurez: {{ summary.conformance.maturity_level }}%</p>
            <p>Problemas bloqueantes: {{ summary.conformance.blocking_count }}</p>
        </div>
        
        {% if charts.maturity %}
        <div class="chart">
            <img src="{{ charts.maturity }}" alt="Gráfico de nivel de madurez">
        </div>
        {% endif %}
    </section>

    <section id="statistics">
        <h2>Estadísticas</h2>
        <div class="stats-container">
            <div class="stat-box">
                <h3>Total de Problemas</h3>
                <p class="stat-number">{{ summary.total_issues }}</p>
            </div>
            <div class="stat-box error">
                <h3>Errores</h3>
                <p class="stat-number">{{ summary.error_count }}</p>
            </div>
            <div class="stat-box warning">
                <h3>Advertencias</h3>
                <p class="stat-number">{{ summary.warning_count }}</p>
            </div>
            <div class="stat-box info">
                <h3>Informativos</h3>
                <p class="stat-number">{{ summary.info_count }}</p>
            </div>
        </div>
        
        {% if charts.severity %}
        <div class="chart">
            <img src="{{ charts.severity }}" alt="Gráfico de severidad">
        </div>
        {% endif %}
    </section>

    <section id="recommendations">
        <h2>Recomendaciones Principales</h2>
        <ul>
            {% for rec in summary.recommendations %}
            <li>{{ rec }}</li>
            {% endfor %}
        </ul>
    </section>

    <section id="categories">
        <h2>Problemas por Categoría</h2>
        
        {% if charts.categories %}
        <div class="chart">
            <img src="{{ charts.categories }}" alt="Gráfico de categorías">
        </div>
        {% endif %}
        
        <div class="accordion">
            {% for cat_id, cat in summary.categories.items() %}
            {% if cat.total_count > 0 %}
            <div class="accordion-item">
                <h3 class="accordion-header">{{ cat_id }}: {{ cat.name }} <span class="count">{{ cat.total_count }}</span></h3>
                <div class="accordion-content">
                    <p class="severity-counts">
                        <span class="error">{{ cat.error_count }} errores</span>
                        <span class="warning">{{ cat.warning_count }} advertencias</span>
                        <span class="info">{{ cat.info_count }} info</span>
                    </p>
                    
                    {% for cp_id, cp in cat.checkpoints.items() %}
                    {% if cp.total_count > 0 %}
                    <div class="checkpoint">
                        <h4>{{ cp_id }} <span class="count">{{ cp.total_count }}</span></h4>
                        <ul class="issues-list">
                            {% for issue in cp.issues %}
                            <li class="issue {{ issue.severity }}">
                                <p>{{ issue.description }}</p>
                                <p class="issue-location">
                                    {% if issue.page != "all" %}Página: {{ issue.page }}{% else %}Todo el documento{% endif %}
                                </p>
                                <p class="issue-fix">{{ issue.fix_description }}</p>
                            </li>
                            {% endfor %}
                        </ul>
                    </div>
                    {% endif %}
                    {% endfor %}
                </div>
            </div>
            {% endif %}
            {% endfor %}
        </div>
    </section>

    <footer>
        <p>Informe generado por PDF/UA Editor</p>
    </footer>

    <script>
        // Script básico para acordeón
        document.addEventListener('DOMContentLoaded', function() {
            const headers = document.querySelectorAll('.accordion-header');
            headers.forEach(header => {
                header.addEventListener('click', function() {
                    this.classList.toggle('active');
                    const content = this.nextElementSibling;
                    if (content.style.maxHeight) {
                        content.style.maxHeight = null;
                    } else {
                        content.style.maxHeight = content.scrollHeight + 'px';
                    }
                });
            });
        });
    </script>
</body>
</html>
"""
    
    def _get_default_css(self) -> str:
        """
        Obtiene un CSS predeterminado para los informes.
        
        Returns:
            str: Contenido CSS
        """
        return """/* Estilos para informes PDF/UA */

/* Estilos generales */
body {
    font-family: Arial, sans-serif;
    line-height: 1.6;
    color: #333;
    max-width: 1200px;
    margin: 0 auto;
    padding: 20px;
}

h1, h2, h3, h4 {
    color: #205493;
    margin-top: 1.5em;
    margin-bottom: 0.5em;
}

h1 {
    font-size: 2em;
    text-align: center;
    border-bottom: 2px solid #205493;
    padding-bottom: 10px;
}

h2 {
    font-size: 1.6em;
    border-bottom: 1px solid #ddd;
    padding-bottom: 5px;
}

h3 {
    font-size: 1.3em;
}

h4 {
    font-size: 1.1em;
}

p {
    margin-bottom: 1em;
}

/* Tablas */
table {
    border-collapse: collapse;
    width: 100%;
    margin-bottom: 20px;
}

th, td {
    text-align: left;
    padding: 8px;
    border-bottom: 1px solid #ddd;
}

th {
    background-color: #f1f1f1;
    font-weight: bold;
}

/* Sección de conformidad */
.conformance-box {
    padding: 15px;
    border-radius: 5px;
    margin-bottom: 20px;
}

.conformant {
    background-color: #e7f4e4;
    border-left: 5px solid #2e8540;
}

.non-conformant {
    background-color: #f9e0de;
    border-left: 5px solid #d83933;
}

/* Estadísticas */
.stats-container {
    display: flex;
    justify-content: space-between;
    flex-wrap: wrap;
    margin-bottom: 20px;
}

.stat-box {
    flex: 1;
    min-width: 150px;
    padding: 15px;
    margin: 5px;
    border-radius: 5px;
    background-color: #f1f1f1;
    text-align: center;
}

.stat-number {
    font-size: 2em;
    font-weight: bold;
    margin: 10px 0;
}

/* Colores de severidad */
.error {
    color: #d83933;
}

.error.stat-box {
    background-color: #f9e0de;
    border-left: 3px solid #d83933;
}

.warning {
    color: #fdb81e;
}

.warning.stat-box {
    background-color: #fff1d2;
    border-left: 3px solid #fdb81e;
}

.info {
    color: #02bfe7;
}

.info.stat-box {
    background-color: #e1f3f8;
    border-left: 3px solid #02bfe7;
}

/* Acordeón para categorías */
.accordion-item {
    margin-bottom: 10px;
    border: 1px solid #ddd;
    border-radius: 5px;
}

.accordion-header {
    background-color: #f1f1f1;
    padding: 10px 15px;
    cursor: pointer;
    position: relative;
}

.accordion-header:hover {
    background-color: #e5e5e5;
}

.accordion-header.active {
    background-color: #e1f3f8;
}

.accordion-content {
    padding: 0 15px;
    max-height: 0;
    overflow: hidden;
    transition: max-height 0.3s ease-out;
}

.count {
    background-color: #205493;
    color: white;
    border-radius: 50%;
    padding: 2px 8px;
    font-size: 0.8em;
    margin-left: 10px;
}

/* Lista de issues */
.issues-list {
    list-style-type: none;
    padding: 0;
}

.issue {
    border-left: 3px solid #ddd;
    padding: 10px 15px;
    margin-bottom: 10px;
    background-color: #f9f9f9;
    border-radius: 0 5px 5px 0;
}

.issue.error {
    border-left-color: #d83933;
    background-color: #f9e0de;
}

.issue.warning {
    border-left-color: #fdb81e;
    background-color: #fff1d2;
}

.issue.info {
    border-left-color: #02bfe7;
    background-color: #e1f3f8;
}

.issue-location {
    font-size: 0.9em;
    color: #666;
}

.issue-fix {
    font-style: italic;
    border-top: 1px dotted #ddd;
    padding-top: 5px;
    margin-top: 5px;
}

/* Checkpoints */
.checkpoint {
    margin-bottom: 20px;
    padding-bottom: 10px;
    border-bottom: 1px dashed #ddd;
}

.checkpoint h4 {
    margin-bottom: 10px;
}

.severity-counts {
    display: flex;
    gap: 15px;
    margin-bottom: 15px;
}

.severity-counts span {
    padding: 3px 8px;
    border-radius: 3px;
    font-size: 0.9em;
}

.error.severity-counts span.error,
.warning.severity-counts span.warning,
.info.severity-counts span.info {
    background-color: rgba(0, 0, 0, 0.1);
}

/* Gráficos */
.chart {
    text-align: center;
    margin: 20px 0;
}

.chart img {
    max-width: 100%;
    height: auto;
}

/* Pie de página */
footer {
    margin-top: 50px;
    padding-top: 20px;
    border-top: 1px solid #ddd;
    text-align: center;
    font-size: 0.9em;
    color: #666;
}

/* Responsive */
@media (max-width: 768px) {
    .stats-container {
        flex-direction: column;
    }
    
    .stat-box {
        margin-bottom: 10px;
    }
}

/* Estilos para impresión */
@media print {
    body {
        font-size: 12pt;
    }
    
    .accordion-content {
        max-height: none !important;
        display: block !important;
    }
    
    .issue {
        break-inside: avoid;
    }
    
    a {
        text-decoration: none;
        color: #000;
    }
}
"""
    
    def _generate_recommendations(self, summary: Dict[str, Any]) -> List[str]:
        """
        Genera recomendaciones priorizadas según los problemas encontrados.
        
        Args:
            summary: Resumen de problemas y conformidad
            
        Returns:
            List[str]: Lista de recomendaciones priorizadas
        """
        recommendations = []
        
        # Verificar si hay estructura en el documento
        if not self.document_info.get("has_structure", False):
            recommendations.append(
                "Añadir estructura lógica al documento (obligatorio para PDF/UA) utilizando "
                "etiquetas apropiadas para cada elemento de contenido."
            )
            
        # Recomendaciones basadas en errores bloqueantes
        blocking_checkpoints = summary.get("conformance", {}).get("blocking_checkpoints", [])
        if blocking_checkpoints:
            # Agrupar por categoría para priorizar
            category_errors = {}
            for checkpoint in blocking_checkpoints:
                cat = checkpoint.get("category", "00")
                if cat not in category_errors:
                    category_errors[cat] = []
                category_errors[cat].append(checkpoint)
            
            # Priorizar categorías críticas
            critical_categories = ["06", "07", "11", "13", "15", "09", "01"]
            for cat in critical_categories:
                if cat in category_errors and len(recommendations) < 5:
                    checkpoints = category_errors[cat]
                    cat_name = summary.get("categories", {}).get(cat, {}).get("name", f"Categoría {cat}")
                    
                    if cat == "06":  # Metadatos
                        recommendations.append(
                            f"Corregir los metadatos del documento para cumplir con PDF/UA: "
                            f"añadir título, idioma y flag PDF/UA a los metadatos XMP."
                        )
                    elif cat == "07":  # Diccionario
                        recommendations.append(
                            f"Establecer DisplayDocTitle=true en ViewerPreferences para que "
                            f"los lectores de pantalla anuncien el título del documento."
                        )
                    elif cat == "11":  # Idioma
                        recommendations.append(
                            f"Definir correctamente el idioma principal del documento y para "
                            f"cualquier contenido en idioma diferente."
                        )
                    elif cat == "13":  # Gráficos
                        recommendations.append(
                            f"Añadir texto alternativo (Alt) a todas las imágenes y elementos "
                            f"gráficos que transmitan información relevante."
                        )
                    elif cat == "15":  # Tablas
                        recommendations.append(
                            f"Corregir la estructura de tablas: definir celdas de cabecera (TH) "
                            f"con atributo Scope y mantener estructura adecuada."
                        )
                    elif cat == "09":  # Etiquetas apropiadas
                        recommendations.append(
                            f"Revisar y corregir el orden de lectura y la estructura jerárquica "
                            f"para asegurar que la secuencia lógica es correcta."
                        )
                    elif cat == "01":  # Estructura real etiquetada
                        recommendations.append(
                            f"Verificar que todo el contenido real esté etiquetado y que "
                            f"elementos decorativos estén marcados como artefactos."
                        )
        
        # Recomendaciones generales si no hay suficientes específicas
        if len(recommendations) < 3:
            general_recs = [
                "Utilizar etiquetas semánticamente apropiadas para cada elemento (P para párrafos, "
                "H1-H6 para encabezados, Figure para imágenes, etc.).",
                
                "Verificar que las tablas tengan una estructura adecuada con celdas de cabecera (TH) "
                "correctamente identificadas usando el atributo Scope.",
                
                "Garantizar que todas las imágenes informativas tengan texto alternativo (Alt) "
                "descriptivo y apropiado.",
                
                "Definir el idioma principal del documento y marcar cambios de idioma en contenido "
                "específico usando el atributo Lang.",
                
                "Asegurar que la secuencia de lectura siga el orden lógico y visual del documento.",
                
                "Marcar los encabezados y pies de página como artefactos para que no interfieran "
                "con el flujo de lectura.",
                
                "Verificar que el contraste entre texto y fondo cumple con los requisitos "
                "de accesibilidad WCAG (4.5:1 para texto normal)."
            ]
            
            # Añadir recomendaciones generales hasta tener al menos 3
            for rec in general_recs:
                if rec not in recommendations and len(recommendations) < 5:
                    recommendations.append(rec)
        
        return recommendations
    
    def import_from_json(self, json_path: str) -> bool:
        """
        Importa datos de un archivo JSON previamente exportado.
        
        Args:
            json_path: Ruta al archivo JSON a importar
            
        Returns:
            bool: True si se importó correctamente
        """
        try:
            # Leer archivo JSON
            with open(json_path, "r", encoding="utf-8") as f:
                data = json.load(f)
            
            # Extraer información
            self.document_info = data.get("document", {})
            self.issues = data.get("issues", [])
            self.summary = data.get("summary", {})
            
            logger.info(f"Datos importados correctamente desde: {json_path}")
            return True
            
        except Exception as e:
            logger.error(f"Error al importar datos desde JSON: {e}")
            return False