#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Corrección automática de formularios según PDF/UA.
Añade estructura y accesibilidad a formularios.
"""

from typing import Dict, List, Optional, Any
from loguru import logger

class FormsFixer:
    """
    Clase para corregir formularios según PDF/UA.
    Añade Alt, TU y Contents a widgets y marca formularios planos.
    """
    
    def __init__(self, pdf_writer=None):
        """
        Inicializa el corrector de formularios.
        
        Args:
            pdf_writer: Instancia opcional de PDFWriter
        """
        self.pdf_writer = pdf_writer
        logger.info("FormsFixer inicializado")
    
    def set_pdf_writer(self, pdf_writer):
        """Establece el escritor de PDF a utilizar"""
        self.pdf_writer = pdf_writer
    
    def fix_all_forms(self, structure_tree: Dict, pdf_loader) -> bool:
        """
        Corrige todos los formularios en el documento.
        
        Args:
            structure_tree: Diccionario representando la estructura lógica
            pdf_loader: Instancia de PDFLoader con el documento cargado
            
        Returns:
            bool: True si se realizaron correcciones
            
        Referencias:
            - Matterhorn: 24-001, 28-005, 28-010
            - Tagged PDF: 4.3.3, 5.3
        """
        try:
            if self.pdf_writer is None:
                logger.error("No hay PDFWriter configurado para aplicar correcciones")
                return False
            
            changes_made = False
            
            # Buscar anotaciones de Widget sin estructura Form
            untagged_widgets = self._find_untagged_widgets(pdf_loader)
            
            if untagged_widgets:
                logger.info(f"Encontrados {len(untagged_widgets)} widgets sin etiquetar")
                
                # Etiquetar widgets
                for widget in untagged_widgets:
                    widget_fixed = self._fix_untagged_widget(widget, structure_tree)
                    if widget_fixed:
                        changes_made = True
            
            # Buscar nodos Form sin atributos correctos
            incomplete_forms = self._find_incomplete_forms(structure_tree.get("children", []))
            
            if incomplete_forms:
                logger.info(f"Encontrados {len(incomplete_forms)} nodos Form incompletos")
                
                # Completar nodos Form
                for form in incomplete_forms:
                    form_fixed = self._fix_incomplete_form(form)
                    if form_fixed:
                        changes_made = True
            
            # Detectar formularios planos (no interactivos)
            non_interactive_forms = self._find_non_interactive_forms(pdf_loader)
            
            if non_interactive_forms:
                logger.info(f"Encontrados {len(non_interactive_forms)} formularios no interactivos")
                
                # Marcar formularios no interactivos
                for form in non_interactive_forms:
                    form_fixed = self._fix_non_interactive_form(form, structure_tree)
                    if form_fixed:
                        changes_made = True
            
            return changes_made
            
        except Exception as e:
            logger.exception(f"Error al corregir formularios: {e}")
            return False
    
    def add_form_node(self, parent_id: str, widget_id: str, field_name: str) -> bool:
        """
        Añade un nodo Form para un widget.
        
        Args:
            parent_id: Identificador del elemento padre
            widget_id: Identificador del widget
            field_name: Nombre del campo de formulario
            
        Returns:
            bool: True si se añadió el nodo
            
        Referencias:
            - Matterhorn: 28-010
            - Tagged PDF: 4.3.3
        """
        try:
            if self.pdf_writer is None:
                logger.error("No hay PDFWriter configurado para aplicar correcciones")
                return False
            
            # Preparar información del nodo Form
            tag_info = {
                "type": "Form",
                "parent_id": parent_id,
                "attributes": {
                    "objr": widget_id,
                    "field_name": field_name
                }
            }
            
            logger.info(f"Añadiendo nodo Form para widget {widget_id} bajo {parent_id}")
            
            # En implementación real, se añadiría el nodo
            # self.pdf_writer.add_tag(tag_info)
            
            return True
            
        except Exception as e:
            logger.exception(f"Error al añadir nodo Form: {e}")
            return False
    
    def update_form_attributes(self, form_id: str, alt_text: str = None, tu_text: str = None) -> bool:
        """
        Actualiza atributos de un nodo Form.
        
        Args:
            form_id: Identificador del nodo Form
            alt_text: Texto alternativo (opcional)
            tu_text: Texto para TU (opcional)
            
        Returns:
            bool: True si se actualizaron los atributos
            
        Referencias:
            - Matterhorn: 28-005
            - Tagged PDF: 4.3.3
        """
        try:
            if self.pdf_writer is None:
                logger.error("No hay PDFWriter configurado para aplicar correcciones")
                return False
            
            changes_made = False
            
            # Actualizar Alt
            if alt_text:
                logger.info(f"Añadiendo Alt='{alt_text}' a Form {form_id}")
                self.pdf_writer.update_tag_attribute(form_id, "alt", alt_text)
                changes_made = True
            
            # Actualizar TU (en implementación real, se actualizaría el campo del formulario)
            if tu_text:
                logger.info(f"Añadiendo TU='{tu_text}' al campo de formulario asociado a {form_id}")
                changes_made = True
            
            return changes_made
            
        except Exception as e:
            logger.exception(f"Error al actualizar atributos de Form: {e}")
            return False
    
    def mark_print_field(self, element_id: str, role: str, description: str) -> bool:
        """
        Marca un campo de formulario no interactivo con PrintField.
        
        Args:
            element_id: Identificador del elemento
            role: Rol del campo (CheckBox, TextField, etc.)
            description: Descripción del campo
            
        Returns:
            bool: True si se marcó el campo
            
        Referencias:
            - Matterhorn: 24-001
            - Tagged PDF: 5.3
        """
        try:
            if self.pdf_writer is None:
                logger.error("No hay PDFWriter configurado para aplicar correcciones")
                return False
            
            # Preparar atributos PrintField
            printfield_attributes = {
                "role": role,
                "desc": description
            }
            
            logger.info(f"Marcando elemento {element_id} como PrintField de tipo {role}")
            
            # En implementación real, se añadirían los atributos
            # self.pdf_writer.update_tag_attribute(element_id, "printfield", printfield_attributes)
            
            return True
            
        except Exception as e:
            logger.exception(f"Error al marcar PrintField: {e}")
            return False
    
    def _find_untagged_widgets(self, pdf_loader) -> List[Dict]:
        """
        Encuentra anotaciones de Widget sin estructura Form.
        
        Args:
            pdf_loader: Instancia de PDFLoader con el documento cargado
            
        Returns:
            List[Dict]: Lista de widgets sin etiquetar
        """
        # Simulación - en implementación real se analizaría el documento
        untagged_widgets = []
        
        # Recorrer páginas para encontrar anotaciones
        if pdf_loader and pdf_loader.doc:
            for page_num in range(pdf_loader.doc.page_count):
                # Obtener anotaciones de la página
                page = pdf_loader.doc[page_num]
                
                # Simulación: crear widgets artificiales
                for i in range(2):  # Simulación: 2 widgets por página
                    # Verificar si el widget está etiquetado (simulado)
                    is_tagged = (i % 2 == 0)  # Simulación: uno de cada dos widgets no está etiquetado
                    
                    if not is_tagged:
                        # Extraer información del widget
                        widget_info = {
                            "id": f"widget-{page_num}-{i}",
                            "page": page_num,
                            "bbox": [100, 100, 200, 130],
                            "field_name": f"field_{page_num}_{i}",
                            "field_type": "text" if i % 2 == 0 else "checkbox"
                        }
                        
                        untagged_widgets.append(widget_info)
        
        return untagged_widgets
    
    def _fix_untagged_widget(self, widget: Dict, structure_tree: Dict) -> bool:
        """
        Etiqueta un widget sin estructura Form.
        
        Args:
            widget: Información del widget
            structure_tree: Diccionario representando la estructura lógica
            
        Returns:
            bool: True si se etiquetó el widget
        """
        # Determinar el elemento padre apropiado
        parent_id = self._find_appropriate_parent(widget, structure_tree)
        
        if not parent_id:
            logger.warning(f"No se pudo encontrar un padre apropiado para el widget en página {widget.get('page', 0)}")
            return False
        
        # Añadir nodo Form
        form_added = self.add_form_node(parent_id, widget.get("id", ""), widget.get("field_name", ""))
        
        if not form_added:
            return False
        
        # Añadir atributos Alt y TU
        field_name = widget.get("field_name", "")
        field_type = widget.get("field_type", "")
        
        # Generar texto descriptivo
        desc_text = f"Campo de {field_type}: {field_name}"
        
        # Simulación - en implementación real se actualizarían los atributos
        logger.info(f"Configurando atributos para widget: Alt='{desc_text}', TU='{desc_text}'")
        
        return True
    
    def _find_incomplete_forms(self, elements: List[Dict], path: str = "") -> List[Dict]:
        """
        Encuentra nodos Form sin atributos correctos.
        
        Args:
            elements: Lista de elementos de estructura
            path: Ruta de anidamiento actual
            
        Returns:
            List[Dict]: Lista de nodos Form incompletos
        """
        incomplete_forms = []
        
        for i, element in enumerate(elements):
            element_type = element.get("type", "")
            current_path = f"{path}/{i}:{element_type}"
            
            if element_type == "Form":
                # Verificar atributos
                has_alt = "alt" in element.get("attributes", {})
                has_tu = "tu" in element.get("attributes", {})
                
                if not has_alt or not has_tu:
                    # Añadir información de contexto
                    element["_path"] = current_path
                    incomplete_forms.append(element)
            
            # Buscar en los hijos
            if element.get("children"):
                child_forms = self._find_incomplete_forms(element["children"], current_path)
                incomplete_forms.extend(child_forms)
        
        return incomplete_forms
    
    def _fix_incomplete_form(self, form: Dict) -> bool:
        """
        Completa atributos de un nodo Form.
        
        Args:
            form: Información del nodo Form
            
        Returns:
            bool: True si se completaron los atributos
        """
        form_id = form.get("id", "unknown")
        field_name = form.get("attributes", {}).get("field_name", "campo")
        
        # Generar texto descriptivo
        desc_text = f"Campo de formulario: {field_name}"
        
        # Actualizar atributos
        return self.update_form_attributes(form_id, desc_text, desc_text)
    
    def _find_non_interactive_forms(self, pdf_loader) -> List[Dict]:
        """
        Encuentra campos de formulario no interactivos.
        
        Args:
            pdf_loader: Instancia de PDFLoader con el documento cargado
            
        Returns:
            List[Dict]: Lista de campos no interactivos
        """
        # Simulación - en implementación real se analizaría el documento
        non_interactive_forms = []
        
        # Recorrer páginas para encontrar campos visibles pero no interactivos
        if pdf_loader and pdf_loader.doc:
            for page_num in range(pdf_loader.doc.page_count):
                # Simulación: crear campos artificiales
                if page_num % 2 == 0:  # Simulación: solo en páginas pares
                    # Extraer información del campo
                    field_info = {
                        "id": f"print_field-{page_num}",
                        "page": page_num,
                        "bbox": [150, 150, 250, 180],
                        "field_type": "TextField",
                        "description": f"Campo de texto en página {page_num}"
                    }
                    
                    non_interactive_forms.append(field_info)
        
        return non_interactive_forms
    
    def _fix_non_interactive_form(self, form: Dict, structure_tree: Dict) -> bool:
        """
        Marca un campo de formulario no interactivo.
        
        Args:
            form: Información del campo
            structure_tree: Diccionario representando la estructura lógica
            
        Returns:
            bool: True si se marcó el campo
        """
        # Determinar el elemento en la estructura que corresponde al campo
        element_id = self._find_element_by_bbox(form.get("bbox", [0, 0, 0, 0]), form.get("page", 0), structure_tree)
        
        if not element_id:
            logger.warning(f"No se pudo encontrar un elemento para el campo no interactivo en página {form.get('page', 0)}")
            return False
        
        # Marcar como PrintField
        return self.mark_print_field(element_id, form.get("field_type", ""), form.get("description", ""))
    
    def _find_appropriate_parent(self, widget: Dict, structure_tree: Dict) -> str:
        """
        Encuentra el elemento padre apropiado para un widget.
        
        Args:
            widget: Información del widget
            structure_tree: Diccionario representando la estructura lógica
            
        Returns:
            str: Identificador del elemento padre apropiado
        """
        # Simulación - en implementación real se buscaría por posición en la página
        
        # Para la simulación, devolver un ID genérico
        return "p-generic"
    
    def _find_element_by_bbox(self, bbox: List[float], page_num: int, structure_tree: Dict) -> str:
        """
        Encuentra un elemento por su bounding box.
        
        Args:
            bbox: Bounding box [x0, y0, x1, y1]
            page_num: Número de página
            structure_tree: Diccionario representando la estructura lógica
            
        Returns:
            str: Identificador del elemento encontrado
        """
        # Simulación - en implementación real se buscaría por intersección de bounding boxes
        
        # Para la simulación, devolver un ID genérico
        return "p-generic"