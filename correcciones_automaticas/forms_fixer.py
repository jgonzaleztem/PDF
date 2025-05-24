#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Módulo para la corrección de problemas de accesibilidad en formularios PDF.

Este módulo implementa correcciones automáticas para formularios interactivos
y no interactivos según los requisitos de PDF/UA y Matterhorn Protocol.

Funciones principales:
- Añadir descripciones accesibles (TU) a campos de formulario
- Estructurar campos en el árbol de estructura lógica con <Form>
- Corregir formularios no interactivos con atributos PrintField
- Garantizar accesibilidad de grupos de botones de radio y casillas
- Asociar etiquetas de campo con sus campos de formulario

Referencias:
- Matterhorn Protocol Checkpoints: 24-001 a 24-005, 28-001 a 28-011
- PDF/UA-1 (ISO 14289-1): 7.18 (Annotations and Forms), 8.5 (Form Fields)
- Tagged PDF Best Practice Guide: 4.3.3 <Form>
"""

from typing import Dict, List, Optional, Any, Set, Tuple, Union
import os
import re
import pikepdf
from pikepdf import Pdf, Dictionary, Name, String, Array
from loguru import logger

class FormsFixer:
    """
    Clase para la corrección automática de problemas de accesibilidad
    en formularios PDF según PDF/UA y Matterhorn Protocol.
    """
    
    def __init__(self, pdf_writer=None):
        """
        Inicializa el corrector de formularios.
        
        Args:
            pdf_writer: Instancia de PDFWriter con el documento cargado
        """
        self.pdf_writer = pdf_writer
        self.structure_modified = False
        self.fields_fixed = 0
        
        # Mapeo de tipos de campo a etiqueta TU predeterminada
        self.default_field_labels = {
            'Tx': "Campo de texto",
            'Btn': {
                'checkbox': "Casilla de verificación",
                'radio': "Botón de opción",
                'pushbutton': "Botón"
            },
            'Ch': "Lista de selección",
            'Sig': "Campo de firma"
        }
        
        # Definiciones para PrintField (formularios no interactivos)
        self.print_field_roles = {
            'Tx': "Tx",
            'Btn': "Btn",
            'Ch': "Ch",
            'Sig': "Sig"
        }
        
        logger.info("FormsFixer inicializado")
    
    def set_pdf_writer(self, pdf_writer):
        """
        Establece la referencia al escritor de PDF.
        
        Args:
            pdf_writer: Instancia de PDFWriter con el documento cargado
        """
        self.pdf_writer = pdf_writer
        logger.debug("PDFWriter establecido en FormsFixer")
    
    def fix_all_forms(self, structure_tree: Dict, pdf_loader) -> bool:
        """
        Aplica todas las correcciones de accesibilidad a formularios.
        
        Args:
            structure_tree: Diccionario representando la estructura lógica
            pdf_loader: Instancia de PDFLoader con el documento cargado
            
        Returns:
            bool: True si se realizaron correcciones
        """
        if not self.pdf_writer:
            self.pdf_writer = getattr(pdf_loader, 'pdf_writer', None)
            if not self.pdf_writer:
                logger.error("No hay PDFWriter disponible para aplicar correcciones")
                return False
        
        # Reiniciar contadores
        self.structure_modified = False
        self.fields_fixed = 0
        
        try:
            # 1. Corregir campos interactivos existentes
            self._fix_interactive_form_fields(pdf_loader)
            
            # 2. Verificar estructura lógica para campos de formulario
            if structure_tree:
                self._fix_form_structure(structure_tree, pdf_loader)
            
            # 3. Corregir formularios no interactivos (si existen)
            self._fix_non_interactive_forms(pdf_loader)
            
            # 4. Corregir orden de tabulación y navegación
            self._fix_tab_order(pdf_loader)
            
            logger.info(f"Corrección de formularios completada: {self.fields_fixed} campos corregidos")
            return self.structure_modified or self.fields_fixed > 0
            
        except Exception as e:
            logger.exception(f"Error en fix_all_forms: {str(e)}")
            return False
    
    def _fix_interactive_form_fields(self, pdf_loader) -> None:
        """
        Corrige problemas en campos de formulario interactivos.
        
        Args:
            pdf_loader: Instancia de PDFLoader con el documento cargado
        """
        logger.info("Corrigiendo campos de formulario interactivos")
        
        if not hasattr(pdf_loader, 'pikepdf_doc') or pdf_loader.pikepdf_doc is None:
            logger.warning("No hay documento PDF cargado")
            return
        
        # Verificar si hay un diccionario AcroForm
        if '/AcroForm' not in pdf_loader.pikepdf_doc.Root:
            logger.info("Documento sin formulario interactivo (AcroForm)")
            return
        
        acroform = pdf_loader.pikepdf_doc.Root.AcroForm
        
        # Verificar si hay campos de formulario definidos
        if '/Fields' not in acroform or not acroform.Fields:
            logger.info("No hay campos de formulario definidos")
            return
        
        # Recorrer todos los campos de formulario
        for field in acroform.Fields:
            try:
                field_dict = field.get_object()
                
                # Corregir nombres y descripciones accesibles
                self._fix_field_properties(field_dict, pdf_loader)
                
                # Si hay campos anidados (como en grupo de botones radio), procesar también
                if '/Kids' in field_dict:
                    for kid in field_dict.Kids:
                        kid_dict = kid.get_object()
                        self._fix_field_properties(kid_dict, pdf_loader)
                        
                        # Si es un widget, asegurar que esté estructurado
                        if '/Subtype' in kid_dict and kid_dict.Subtype == '/Widget':
                            self._ensure_widget_in_structure(kid_dict, pdf_loader)
            
            except Exception as e:
                logger.error(f"Error al corregir campo de formulario: {str(e)}")
    
    def _fix_field_properties(self, field_dict: Dict, pdf_loader) -> None:
        """
        Corrige propiedades de accesibilidad en un campo de formulario.
        
        Args:
            field_dict: Diccionario del campo de formulario
            pdf_loader: Instancia de PDFLoader con el documento cargado
        """
        # Verificar si el campo tiene un tipo válido
        if '/FT' not in field_dict:
            return
        
        field_type = str(field_dict.FT)
        field_name = str(field_dict.get('/T', ''))
        
        # Eliminar prefijo '/' si está presente
        if field_type.startswith('/'):
            field_type = field_type[1:]
        
        # Corregir TU (descripción accesible)
        self._fix_field_tu(field_dict, field_type, field_name)
        
        # Corregir propiedades específicas según tipo de campo
        if field_type == 'Btn':
            self._fix_button_field(field_dict)
        elif field_type == 'Tx':
            self._fix_text_field(field_dict)
        elif field_type == 'Ch':
            self._fix_choice_field(field_dict)
        elif field_type == 'Sig':
            self._fix_signature_field(field_dict)
        
        self.fields_fixed += 1
    
    def _fix_field_tu(self, field_dict: Dict, field_type: str, field_name: str) -> None:
        """
        Añade o corrige la descripción accesible (TU) de un campo.
        
        Args:
            field_dict: Diccionario del campo de formulario
            field_type: Tipo de campo (Tx, Btn, Ch, Sig)
            field_name: Nombre del campo
        """
        # Si ya tiene TU, verificar que sea válido
        has_valid_tu = False
        
        if '/TU' in field_dict:
            tu_value = str(field_dict.TU)
            # Verificar si el TU no está vacío
            if tu_value and tu_value != field_name:
                has_valid_tu = True
        
        # Si no tiene TU válido, crear uno apropiado
        if not has_valid_tu:
            # Determinar tipo específico para botones
            if field_type == 'Btn' and '/Ff' in field_dict:
                flags = int(field_dict.Ff)
                if flags & 65536:  # Pushbutton
                    btn_type = 'pushbutton'
                elif flags & 32768:  # Radio
                    btn_type = 'radio'
                else:  # Checkbox
                    btn_type = 'checkbox'
                
                default_tu = self.default_field_labels[field_type][btn_type]
            else:
                default_tu = self.default_field_labels.get(field_type, "Campo de formulario")
            
            # Crear descripción más significativa si es posible
            if field_name:
                # Convertir nombre técnico a formato legible
                readable_name = self._convert_to_readable_name(field_name)
                tu_value = readable_name
            else:
                tu_value = default_tu
            
            # Aplicar cambio
            field_dict.TU = pikepdf.String(tu_value)
            logger.debug(f"Añadida descripción accesible (TU) a campo: {tu_value}")
    
    def _convert_to_readable_name(self, technical_name: str) -> str:
        """
        Convierte un nombre técnico de campo a un formato legible.
        
        Args:
            technical_name: Nombre técnico del campo (ej: 'txtFirstName')
            
        Returns:
            str: Nombre legible (ej: 'First Name')
        """
        # Eliminar prefijos comunes
        prefixes = ['txt', 'chk', 'rad', 'cmb', 'btn']
        name = technical_name
        
        for prefix in prefixes:
            if name.lower().startswith(prefix) and len(name) > len(prefix):
                if name[len(prefix)].isupper():
                    name = name[len(prefix):]
                    break
        
        # Separar por mayúsculas (camelCase)
        readable = re.sub(r'([a-z])([A-Z])', r'\1 \2', name)
        
        # Separar por guiones bajos
        readable = readable.replace('_', ' ')
        
        # Capitalizar primera letra de cada palabra
        readable = ' '.join(word.capitalize() for word in readable.split())
        
        return readable
    
    def _fix_button_field(self, field_dict: Dict) -> None:
        """
        Corrige propiedades específicas de campos de botón.
        
        Args:
            field_dict: Diccionario del campo de formulario
        """
        # Verificar flags para determinar tipo específico
        if '/Ff' not in field_dict:
            return
            
        flags = int(field_dict.Ff)
        
        # Botones de radio
        if flags & 32768:  # Radio button
            self._fix_radio_button(field_dict)
        # Casillas de verificación
        elif not (flags & 65536):  # Not a pushbutton (so checkbox)
            self._fix_checkbox(field_dict)
        # Botones de pulsación
        else:  # Pushbutton
            self._fix_pushbutton(field_dict)
    
    def _fix_radio_button(self, field_dict: Dict) -> None:
        """
        Corrige propiedades específicas de botones de radio.
        
        Args:
            field_dict: Diccionario del campo de formulario
        """
        # Verificar si tiene opciones definidas (Opt)
        if '/Kids' in field_dict and '/Opt' not in field_dict:
            # Crear array Opt basado en estados de apariencia de los widgets
            opt_values = []
            
            for kid in field_dict.Kids:
                kid_dict = kid.get_object()
                if '/AP' in kid_dict and '/N' in kid_dict.AP:
                    # Obtener el estado seleccionado (distinto de Off)
                    for state in kid_dict.AP.N:
                        if state != '/Off':
                            # Usar el estado como valor legible
                            state_str = str(state)
                            if state_str.startswith('/'):
                                state_str = state_str[1:]
                            opt_values.append(pikepdf.String(state_str))
                            break
            
            if opt_values:
                field_dict.Opt = pikepdf.Array(opt_values)
                logger.debug(f"Añadidas opciones (Opt) a grupo de botones radio: {opt_values}")
    
    def _fix_checkbox(self, field_dict: Dict) -> None:
        """
        Corrige propiedades específicas de casillas de verificación.
        
        Args:
            field_dict: Diccionario del campo de formulario
        """
        # Verificar estado de verificación para establecer significado claro
        if '/AP' in field_dict and '/N' in field_dict.AP:
            # Asegurar que los estados de apariencia sean claros
            if '/Yes' not in field_dict.AP.N and '/On' not in field_dict.AP.N:
                # Si no tiene estados estándar, buscar estados personalizados
                custom_state = None
                for state in field_dict.AP.N:
                    if state != '/Off':
                        custom_state = state
                        break
                
                if custom_state:
                    # Añadir MK con una descripción del estado activado si no existe
                    if '/MK' not in field_dict:
                        field_dict.MK = pikepdf.Dictionary({})
                    
                    if '/CA' not in field_dict.MK:
                        # Usar valor simbólico como "✓" para el estado marcado
                        field_dict.MK.CA = pikepdf.String("✓")
                        logger.debug("Añadido símbolo de verificación a casilla")
    
    def _fix_pushbutton(self, field_dict: Dict) -> None:
        """
        Corrige propiedades específicas de botones de pulsación.
        
        Args:
            field_dict: Diccionario del campo de formulario
        """
        # Verificar si tiene una descripción del contenido
        if '/MK' not in field_dict:
            field_dict.MK = pikepdf.Dictionary({})
        
        # Si no tiene CA (texto del botón), añadir uno basado en el nombre
        if '/CA' not in field_dict.MK:
            # Usar TU si está disponible, de lo contrario usar el nombre
            button_text = str(field_dict.get('/TU', ''))
            if not button_text and '/T' in field_dict:
                button_text = self._convert_to_readable_name(str(field_dict.T))
            
            if button_text:
                field_dict.MK.CA = pikepdf.String(button_text)
                logger.debug(f"Añadido texto (CA) a botón: {button_text}")
    
    def _fix_text_field(self, field_dict: Dict) -> None:
        """
        Corrige propiedades específicas de campos de texto.
        
        Args:
            field_dict: Diccionario del campo de formulario
        """
        # Verificar si es un campo multilínea y establecer banderas apropiadas
        if '/Ff' in field_dict:
            flags = int(field_dict.Ff)
            
            # Si parece ser un campo de texto largo pero no está configurado como multilínea
            if '/Rect' in field_dict:
                rect = field_dict.Rect
                if len(rect) == 4:
                    # Calcular altura del campo
                    height = float(rect[3]) - float(rect[1])
                    
                    # Si la altura sugiere un campo multilínea (más de 20 puntos)
                    if height > 20 and not (flags & 4096):  # Multiline flag
                        # Establecer como multilínea
                        field_dict.Ff = pikepdf.Integer(flags | 4096)
                        logger.debug("Campo de texto configurado como multilínea")
    
    def _fix_choice_field(self, field_dict: Dict) -> None:
        """
        Corrige propiedades específicas de campos de selección.
        
        Args:
            field_dict: Diccionario del campo de formulario
        """
        # Verificar si tiene opciones definidas
        if '/Opt' not in field_dict or not field_dict.Opt:
            logger.warning("Campo de selección sin opciones (Opt)")
            return
        
        # Verificar si las opciones son comprensibles
        opt_values = field_dict.Opt
        if len(opt_values) > 0:
            # Si las opciones son tuplas [valor, etiqueta], asegurar que las etiquetas sean adecuadas
            first_opt = opt_values[0]
            if isinstance(first_opt, pikepdf.Array) and len(first_opt) >= 2:
                for i, opt in enumerate(opt_values):
                    if len(opt) >= 2 and not opt[1]:
                        # Si la etiqueta está vacía, usar el valor como etiqueta
                        value = str(opt[0])
                        new_opt = pikepdf.Array([opt[0], pikepdf.String(value)])
                        opt_values[i] = new_opt
                        logger.debug(f"Corregida opción de selección: {value}")
    
    def _fix_signature_field(self, field_dict: Dict) -> None:
        """
        Corrige propiedades específicas de campos de firma.
        
        Args:
            field_dict: Diccionario del campo de formulario
        """
        # Asegurar que tenga un TU adecuado
        if '/TU' not in field_dict or not field_dict.TU:
            field_name = str(field_dict.get('/T', ''))
            if field_name:
                readable_name = self._convert_to_readable_name(field_name)
                field_dict.TU = pikepdf.String(f"Campo de firma: {readable_name}")
            else:
                field_dict.TU = pikepdf.String("Campo para firma digital")
            
            logger.debug("Añadida descripción accesible a campo de firma")
    
    def _ensure_widget_in_structure(self, widget_dict: Dict, pdf_loader) -> None:
        """
        Asegura que el widget esté incluido en la estructura lógica con <Form>.
        
        Args:
            widget_dict: Diccionario del widget
            pdf_loader: Instancia de PDFLoader con el documento cargado
        """
        # Este método requeriría acceso al árbol de estructura ya construido
        # y podría implementarse como parte de _fix_form_structure
        # Para una implementación completa, necesitaríamos interactuar con structure_manager
        pass
    
    def _fix_form_structure(self, structure_tree: Dict, pdf_loader) -> None:
        """
        Verifica y corrige la estructura lógica para campos de formulario.
        
        Args:
            structure_tree: Diccionario representando la estructura lógica
            pdf_loader: Instancia de PDFLoader con el documento cargado
        """
        logger.info("Verificando estructura lógica para campos de formulario")
        
        # Recopilar todos los widgets de formulario en el documento
        widgets = self._collect_form_widgets(pdf_loader)
        if not widgets:
            logger.info("No se encontraron widgets de formulario")
            return
        
        # Verificar si cada widget está en la estructura
        widgets_in_structure = self._find_form_elements_in_structure(structure_tree)
        
        # Buscar widgets que no están en la estructura
        missing_widgets = []
        for widget in widgets:
            widget_ref = widget.get('reference')
            if widget_ref not in widgets_in_structure:
                missing_widgets.append(widget)
        
        # Si hay widgets faltantes, añadirlos a la estructura
        if missing_widgets:
            logger.info(f"Encontrados {len(missing_widgets)} widgets sin estructurar")
            self._add_missing_widgets_to_structure(missing_widgets, structure_tree, pdf_loader)
            self.structure_modified = True
    
    def _collect_form_widgets(self, pdf_loader) -> List[Dict]:
        """
        Recopila todos los widgets de formulario en el documento.
        
        Args:
            pdf_loader: Instancia de PDFLoader con el documento cargado
            
        Returns:
            List[Dict]: Lista de widgets encontrados con información contextual
        """
        widgets = []
        
        if not hasattr(pdf_loader, 'pikepdf_doc') or pdf_loader.pikepdf_doc is None:
            return widgets
        
        # Verificar si hay un diccionario AcroForm
        if '/AcroForm' not in pdf_loader.pikepdf_doc.Root:
            return widgets
        
        acroform = pdf_loader.pikepdf_doc.Root.AcroForm
        
        # Verificar si hay campos de formulario definidos
        if '/Fields' not in acroform or not acroform.Fields:
            return widgets
        
        # Recorrer todas las páginas y buscar anotaciones de widget
        for page_idx, page in enumerate(pdf_loader.pikepdf_doc.pages):
            if '/Annots' in page and page.Annots:
                for annot in page.Annots:
                    annot_dict = annot.get_object()
                    
                    # Verificar si es un widget
                    if '/Subtype' in annot_dict and annot_dict.Subtype == '/Widget':
                        # Guardar información relevante
                        widget_info = {
                            'reference': annot,
                            'page': page_idx,
                            'rect': annot_dict.get('/Rect', []),
                            'field_type': self._get_field_type_for_widget(annot_dict, acroform),
                            'field_name': self._get_field_name_for_widget(annot_dict, acroform)
                        }
                        widgets.append(widget_info)
        
        return widgets
    
    def _get_field_type_for_widget(self, widget_dict: Dict, acroform: Dict) -> str:
        """
        Determina el tipo de campo para un widget.
        
        Args:
            widget_dict: Diccionario del widget
            acroform: Diccionario AcroForm
            
        Returns:
            str: Tipo de campo (Tx, Btn, Ch, Sig)
        """
        # Si el widget tiene el tipo directamente
        if '/FT' in widget_dict:
            field_type = str(widget_dict.FT)
            if field_type.startswith('/'):
                field_type = field_type[1:]
            return field_type
        
        # Buscar en campo principal si existe
        if '/Parent' in widget_dict:
            parent = widget_dict.Parent.get_object()
            if '/FT' in parent:
                field_type = str(parent.FT)
                if field_type.startswith('/'):
                    field_type = field_type[1:]
                return field_type
        
        # Si no se encuentra, intentar determinarlo por otras características
        if '/AP' in widget_dict:
            # Probable botón o casilla
            return "Btn"
        
        # Por defecto, asumir campo de texto
        return "Tx"
    
    def _get_field_name_for_widget(self, widget_dict: Dict, acroform: Dict) -> str:
        """
        Obtiene el nombre del campo para un widget.
        
        Args:
            widget_dict: Diccionario del widget
            acroform: Diccionario AcroForm
            
        Returns:
            str: Nombre del campo
        """
        # Si el widget tiene el nombre directamente
        if '/T' in widget_dict:
            return str(widget_dict.T)
        
        # Buscar en campo principal si existe
        if '/Parent' in widget_dict:
            parent = widget_dict.Parent.get_object()
            if '/T' in parent:
                return str(parent.T)
        
        # No se encontró nombre
        return ""
    
    def _find_form_elements_in_structure(self, structure_tree: Dict) -> Set:
        """
        Encuentra elementos <Form> en la estructura.
        
        Args:
            structure_tree: Diccionario representando la estructura lógica
            
        Returns:
            Set: Conjunto de referencias a widgets en la estructura
        """
        form_elements = set()
        
        def traverse(node):
            if not node:
                return
                
            # Verificar si es un elemento <Form>
            if isinstance(node, dict) and node.get('type') == 'Form':
                # Buscar referencia al widget (OBJR)
                for child in node.get('children', []):
                    if isinstance(child, dict) and child.get('type') == 'Link-OBJR':
                        if 'objr' in child:
                            form_elements.add(child['objr'])
            
            # Recorrer hijos
            for child in node.get('children', []):
                traverse(child)
        
        traverse(structure_tree)
        return form_elements
    
    def _add_missing_widgets_to_structure(self, widgets: List[Dict], structure_tree: Dict, pdf_loader) -> None:
        """
        Añade widgets faltantes a la estructura lógica.
        
        Args:
            widgets: Lista de widgets a añadir
            structure_tree: Diccionario representando la estructura lógica
            pdf_loader: Instancia de PDFLoader con el documento cargado
        """
        # Agrupar widgets por página para facilitar su incorporación
        widgets_by_page = {}
        for widget in widgets:
            page = widget['page']
            if page not in widgets_by_page:
                widgets_by_page[page] = []
            widgets_by_page[page].append(widget)
        
        # Para cada página con widgets, buscar el mejor lugar para insertarlos
        for page, page_widgets in widgets_by_page.items():
            # Encontrar contenedores adecuados para estos widgets
            containers = self._find_containers_for_page(structure_tree, page)
            
            if not containers:
                logger.warning(f"No se encontró contenedor para widgets en página {page}")
                continue
            
            # Usar el último contenedor (generalmente más apropiado para formularios)
            container = containers[-1]
            
            # Añadir cada widget al contenedor
            for widget in page_widgets:
                # Crear elemento <Form>
                form_element = {
                    'type': 'Form',
                    'element': None,  # Se creará al aplicar cambios
                    'page': page,
                    'children': [
                        {
                            'type': 'Link-OBJR',
                            'objr': widget['reference'],
                            'element': None  # Se creará al aplicar cambios
                        }
                    ]
                }
                
                # Añadir etiqueta basada en el nombre del campo
                if widget['field_name']:
                    readable_name = self._convert_to_readable_name(widget['field_name'])
                    form_element['text'] = readable_name
                
                # Añadir a la estructura
                container['children'].append(form_element)
                logger.debug(f"Añadido elemento <Form> para widget en página {page}")
    
    def _find_containers_for_page(self, structure_tree: Dict, page: int) -> List[Dict]:
        """
        Encuentra contenedores adecuados para widgets en una página.
        
        Args:
            structure_tree: Diccionario representando la estructura lógica
            page: Número de página
            
        Returns:
            List[Dict]: Lista de contenedores adecuados
        """
        containers = []
        
        def traverse(node, current_page=None):
            if not node or not isinstance(node, dict):
                return
            
            # Actualizar página actual si está definida
            if 'page' in node:
                current_page = node['page']
            
            # Si coincide con la página buscada
            if current_page == page:
                # Verificar si es un contenedor adecuado (P, Div, etc.)
                if node.get('type') in ['P', 'Div', 'TD', 'Sect', 'Art', 'NonStruct']:
                    containers.append(node)
            
            # Recorrer hijos
            for child in node.get('children', []):
                traverse(child, current_page)
        
        traverse(structure_tree)
        return containers
    
    def _fix_non_interactive_forms(self, pdf_loader) -> None:
        """
        Corrige formularios no interactivos usando atributos PrintField.
        
        Args:
            pdf_loader: Instancia de PDFLoader con el documento cargado
        """
        logger.info("Verificando formularios no interactivos")
        
        # Detectar campos de formulario visualmente pero sin interactividad
        # Este paso es complejo y requeriría análisis OCR o visual
        non_interactive_fields = self._detect_non_interactive_fields(pdf_loader)
        
        if not non_interactive_fields:
            logger.info("No se detectaron formularios no interactivos")
            return
        
        # Añadir atributos PrintField a estos elementos
        for field in non_interactive_fields:
            self._add_print_field_attributes(field)
    
    def _detect_non_interactive_fields(self, pdf_loader) -> List[Dict]:
        """
        Detecta campos visualmente como formulario pero sin interactividad.
        
        Args:
            pdf_loader: Instancia de PDFLoader con el documento cargado
            
        Returns:
            List[Dict]: Lista de campos no interactivos detectados
        """
        # Esta implementación es un placeholder
        # Una implementación real requeriría análisis de patrones visuales, OCR, etc.
        return []
    
    def _add_print_field_attributes(self, field: Dict) -> None:
        """
        Añade atributos PrintField a un campo no interactivo.
        
        Args:
            field: Información del campo detectado
        """
        # Obtener estructura lógica del elemento
        element = field.get('element')
        if not element:
            return
        
        # Añadir atributos PrintField
        element_type = field.get('detected_type', 'Tx')
        element_role = self.print_field_roles.get(element_type, 'Tx')
        
        # Establecer atributos según PDF/UA
        printfield_attributes = {
            'Role': element_role
        }
        
        # Para casillas de verificación, añadir estado
        if element_type == 'Btn':
            printfield_attributes['checked'] = field.get('checked', 'off')
        
        # Añadir descripción si está disponible
        if 'description' in field:
            printfield_attributes['Desc'] = field['description']
        
        # Registrar modificación
        element['printfield'] = printfield_attributes
        logger.debug(f"Añadidos atributos PrintField a campo no interactivo: {printfield_attributes}")
    
    def _fix_tab_order(self, pdf_loader) -> None:
        """
        Corrige el orden de tabulación para navegación por teclado.
        
        Args:
            pdf_loader: Instancia de PDFLoader con el documento cargado
        """
        logger.info("Corrigiendo orden de tabulación")
        
        if not hasattr(pdf_loader, 'pikepdf_doc') or pdf_loader.pikepdf_doc is None:
            return
        
        # Verificar si hay un diccionario AcroForm
        if '/AcroForm' not in pdf_loader.pikepdf_doc.Root:
            return
        
        acroform = pdf_loader.pikepdf_doc.Root.AcroForm
        
        # Establecer orden de tabulación por orden de estructura
        if '/Fields' in acroform and acroform.Fields:
            # Asegurar que exista la entrada CO si queremos un orden personalizado
            if len(acroform.Fields) > 1:
                # Si no existe CO, crearlo basado en Fields
                if '/CO' not in acroform:
                    acroform.CO = pikepdf.Array(acroform.Fields)
                    logger.debug("Añadido orden de calculación/tabulación (CO)")
    
    def add_missing_form_elements(self, structure_manager) -> bool:
        """
        Añade elementos <Form> faltantes a la estructura lógica.
        Esta función es para uso explícito desde la interfaz de usuario.
        
        Args:
            structure_manager: Gestor de estructura lógica
            
        Returns:
            bool: True si se realizaron cambios
        """
        if not structure_manager or not structure_manager.pdf_loader:
            logger.error("No hay structure_manager o pdf_loader disponible")
            return False
        
        try:
            pdf_loader = structure_manager.pdf_loader
            structure_tree = structure_manager.get_structure_tree()
            
            # Recopilar widgets
            widgets = self._collect_form_widgets(pdf_loader)
            if not widgets:
                logger.info("No se encontraron widgets de formulario")
                return False
            
            # Verificar widgets estructurados
            widgets_in_structure = self._find_form_elements_in_structure(structure_tree)
            
            # Identificar widgets faltantes
            missing_widgets = [w for w in widgets if w['reference'] not in widgets_in_structure]
            
            if not missing_widgets:
                logger.info("Todos los widgets ya están estructurados")
                return False
            
            # Añadir widgets faltantes a la estructura
            self._add_missing_widgets_to_structure(missing_widgets, structure_tree, pdf_loader)
            
            # Actualizar estructura
            structure_manager.modified = True
            
            logger.info(f"Añadidos {len(missing_widgets)} elementos <Form> a la estructura")
            return True
            
        except Exception as e:
            logger.exception(f"Error al añadir elementos <Form>: {str(e)}")
            return False
    
    def fix_form_field_descriptions(self, pdf_loader) -> bool:
        """
        Corrige descripciones accesibles (TU) en campos de formulario.
        Esta función es para uso explícito desde la interfaz de usuario.
        
        Args:
            pdf_loader: Instancia de PDFLoader con el documento cargado
            
        Returns:
            bool: True si se realizaron cambios
        """
        if not pdf_loader or not hasattr(pdf_loader, 'pikepdf_doc') or pdf_loader.pikepdf_doc is None:
            logger.error("No hay pdf_loader válido disponible")
            return False
        
        try:
            # Reiniciar contador
            self.fields_fixed = 0
            
            # Corregir campos interactivos
            self._fix_interactive_form_fields(pdf_loader)
            
            logger.info(f"Corregidas descripciones de {self.fields_fixed} campos")
            return self.fields_fixed > 0
            
        except Exception as e:
            logger.exception(f"Error al corregir descripciones de campos: {str(e)}")
            return False