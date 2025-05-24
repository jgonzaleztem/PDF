import fitz  # PyMuPDF
from pikepdf import Pdf, Name, Dictionary, Array, String
from loguru import logger
import os
from typing import Dict, List, Optional, Any, Set, Tuple, Union

class PDFLoader:
    """Carga y extrae contenido de documentos PDF."""
    
    def __init__(self):
        self.doc = None  # PyMuPDF document
        self.pikepdf_doc = None  # pikepdf document
        self.file_path = None
        self.page_count = 0
        self.structure_tree = None  # Estructura jerárquica del documento
        self.structure_elements_by_id = {}  # Índice de elementos por ID para búsqueda rápida
        self.mcid_to_text = {}  # Mapeo de MCID a texto para mejor extracción
        
    def load_document(self, file_path):
        """Carga un documento PDF."""
        try:
            # Cerrar documentos previos si existen
            self.close()
                
            # Cargar con PyMuPDF para visualización y extracción básica
            self.doc = fitz.open(file_path)
            self.file_path = file_path
            self.page_count = self.doc.page_count
            
            # Cargar con pikepdf para acceso a la estructura
            self.pikepdf_doc = Pdf.open(file_path)
            
            # Pre-procesar MCID mapping para mejor extracción de texto
            self._build_mcid_mapping()
            
            # Extraer la estructura etiquetada
            self.extract_structure_tree()
            
            logger.info(f"Documento cargado: {file_path}")
            return True
        except Exception as e:
            logger.error(f"Error loading PDF: {e}")
            # Asegurarse de que los recursos se limpian en caso de error
            self.close()
            return False
    
    def _build_mcid_mapping(self):
        """Construye un mapeo de MCID a texto para facilitar la extracción."""
        self.mcid_to_text = {}
        
        try:
            for page_num in range(self.page_count):
                page = self.doc[page_num]
                self.mcid_to_text[page_num] = {}
                
                # Extraer bloques de texto con información de MCID
                blocks = page.get_text("dict", flags=0)["blocks"]
                for block in blocks:
                    if block["type"] == 0:  # Bloque de texto
                        for line in block["lines"]:
                            for span in line["spans"]:
                                mcid = span.get("mcid", -1)
                                if mcid >= 0:
                                    if mcid not in self.mcid_to_text[page_num]:
                                        self.mcid_to_text[page_num][mcid] = []
                                    self.mcid_to_text[page_num][mcid].append(span["text"])
                
                # Consolidar texto por MCID
                for mcid in self.mcid_to_text[page_num]:
                    self.mcid_to_text[page_num][mcid] = " ".join(self.mcid_to_text[page_num][mcid])
                    
        except Exception as e:
            logger.error(f"Error construyendo mapeo MCID: {e}")
    
    def extract_structure_tree(self):
        """Extrae la estructura jerárquica del documento."""
        self.structure_tree = None
        self.structure_elements_by_id = {}
        
        try:
            if "/StructTreeRoot" not in self.pikepdf_doc.Root:
                logger.warning("Document is not tagged (no StructTreeRoot)")
                return None
                
            struct_root = self.pikepdf_doc.Root["/StructTreeRoot"]
            
            # Crear estructura jerárquica
            self.structure_tree = {
                "type": "StructTreeRoot",
                "element": struct_root,
                "children": [],
                "text": ""  # Root no tiene texto propio
            }
            
            # Extraer mapa de roles si está disponible
            role_map = {}
            if "/RoleMap" in struct_root:
                for key, value in struct_root.RoleMap.items():
                    role_key = str(key)
                    if role_key.startswith("/"):
                        role_key = role_key[1:]
                    role_value = str(value)
                    if role_value.startswith("/"):
                        role_value = role_value[1:]
                    role_map[role_key] = role_value
            
            self.structure_tree["role_map"] = role_map
            
            # Procesar elementos hijo recursivamente
            if "/K" in struct_root:
                if isinstance(struct_root.K, Array):
                    for item in struct_root.K:
                        child = self._process_structure_element(item)
                        if child:
                            self.structure_tree["children"].append(child)
                else:
                    child = self._process_structure_element(struct_root.K)
                    if child:
                        self.structure_tree["children"].append(child)
                        
            # Registrar elementos por ID para búsqueda rápida
            self._build_element_index(self.structure_tree)
            
            logger.info(f"Estructura jerárquica extraída con éxito")
            return self.structure_tree
        except Exception as e:
            logger.error(f"Error extracting structure tree: {e}")
            return None
    
    def _process_structure_element(self, element, page_num=0):
        """Procesa un elemento de estructura recursivamente con extracción de texto mejorada."""
        if not element:
            return None
            
        # Manejar Arrays
        if isinstance(element, Array):
            children = []
            for item in element:
                child = self._process_structure_element(item, page_num)
                if child:
                    if isinstance(child, list):
                        children.extend(child)
                    else:
                        children.append(child)
            return children
            
        # Manejar Dictionaries (elementos estructurales)
        if isinstance(element, Dictionary):
            # Determinar tipo y página
            element_type = str(element.get(Name.S, "Unknown"))[1:] if Name.S in element else "Unknown"
            
            if Name.Pg in element:
                try:
                    page_num = self.pikepdf_doc.pages.index(element.Pg)
                except ValueError:
                    pass
                    
            # Crear nodo
            node = {
                "type": element_type,
                "element": element,
                "page": page_num,
                "children": [],
                "text": "",  # Inicializar texto vacío
                "attributes": {}  # Inicializar atributos
            }
            
            # Extraer atributos del elemento
            self._extract_element_attributes(element, node)
            
            # Extraer texto del elemento con múltiples estrategias
            extracted_text = self._extract_element_text_enhanced(element, page_num)
            node["text"] = extracted_text
            
            # Procesar hijos recursivamente
            children_text = []
            if Name.K in element:
                k_value = element.K
                
                if isinstance(k_value, Array):
                    for item in k_value:
                        child = self._process_structure_element(item, page_num)
                        if child:
                            if isinstance(child, list):
                                node["children"].extend(child)
                                # Recopilar texto de los hijos
                                for c in child:
                                    if isinstance(c, dict) and c.get("text"):
                                        children_text.append(c["text"])
                            else:
                                node["children"].append(child)
                                if isinstance(child, dict) and child.get("text"):
                                    children_text.append(child["text"])
                                    
                elif isinstance(k_value, Dictionary):
                    child = self._process_structure_element(k_value, page_num)
                    if child:
                        if isinstance(child, list):
                            node["children"].extend(child)
                            for c in child:
                                if isinstance(c, dict) and c.get("text"):
                                    children_text.append(c["text"])
                        else:
                            node["children"].append(child)
                            if isinstance(child, dict) and child.get("text"):
                                children_text.append(child["text"])
                                
                elif isinstance(k_value, String):
                    # El texto está directamente en K
                    direct_text = str(k_value)
                    if direct_text.strip():
                        node["text"] = direct_text
                    
                elif isinstance(k_value, int):
                    # Es un MCID - extraer texto usando el mapeo
                    mcid_text = self._get_text_by_mcid(page_num, k_value)
                    if mcid_text:
                        node["text"] = mcid_text
            
            # Si no hay texto directo pero hay texto de hijos, consolidar
            if not node["text"].strip() and children_text:
                node["text"] = " ".join(children_text).strip()
            
            # Si el elemento tiene texto pero no hijos, y es un elemento contenedor,
            # crear un nodo de texto hijo para una mejor visualización
            if (node["text"].strip() and 
                not node["children"] and 
                element_type in ["P", "Span", "H1", "H2", "H3", "H4", "H5", "H6", "TH", "TD", "LI"]):
                
                text_node = {
                    "type": "TextContent",
                    "text": node["text"],
                    "page": page_num,
                    "element": element,  # Compartir referencia
                    "children": [],
                    "attributes": {}
                }
                node["children"].append(text_node)
                    
            return node
            
        # Manejar otros tipos (números para MCID, etc.)
        elif isinstance(element, int):
            # Es un MCID directo
            mcid_text = self._get_text_by_mcid(page_num, element)
            if mcid_text:
                return {
                    "type": "MCID",
                    "text": mcid_text,
                    "page": page_num,
                    "mcid": element,
                    "element": None,
                    "children": [],
                    "attributes": {}
                }
            
        return None
    
    def _extract_element_attributes(self, element, node):
        """Extrae atributos del elemento pikepdf."""
        try:
            # Lista de atributos comunes a extraer
            common_attributes = [
                "Alt", "ActualText", "E", "Lang", "Scope", "Headers", "ID",
                "ColSpan", "RowSpan", "ListNumbering", "Placement", "WritingMode"
            ]
            
            for attr_name in common_attributes:
                attr_key = Name(f"/{attr_name}")
                
                if attr_key in element:
                    attr_value = element[attr_key]
                    # Convertir a string si es necesario
                    if isinstance(attr_value, String):
                        node["attributes"][attr_name.lower()] = str(attr_value)
                    elif isinstance(attr_value, Name):
                        node["attributes"][attr_name.lower()] = str(attr_value)[1:]  # Quitar /
                    else:
                        node["attributes"][attr_name.lower()] = attr_value
                        
        except Exception as e:
            logger.debug(f"Error extrayendo atributos: {e}")
    
    def _extract_element_text_enhanced(self, element, page_num):
        """Extrae el texto asociado a un elemento de estructura con múltiples estrategias."""
        text_parts = []
        
        try:
            # Estrategia 1: ActualText (tiene prioridad más alta)
            if Name.ActualText in element:
                actual_text = str(element.ActualText)
                if actual_text.strip():
                    return actual_text
            
            # Estrategia 2: Alt text para figuras
            if (element.get(Name.S) == Name.Figure and Name.Alt in element):
                alt_text = str(element.Alt)
                if alt_text.strip():
                    return alt_text
            
            # Estrategia 3: Contenido E (expansion text)
            if Name.E in element:
                e_text = str(element.E)
                if e_text.strip():
                    return e_text
            
            # Estrategia 4: Procesar contenido K
            if Name.K in element:
                k_value = element.K
                text_parts.extend(self._extract_text_from_k(k_value, page_num))
            
            # Estrategia 5: Si es una referencia a contenido marcado, extraer de la página
            if hasattr(element, 'objgen'):
                page_text = self._extract_text_from_page_reference(element, page_num)
                if page_text:
                    text_parts.append(page_text)
        
        except Exception as e:
            logger.debug(f"Error en extracción de texto: {e}")
        
        # Consolidar y limpiar texto
        final_text = " ".join(text_parts).strip()
        final_text = self._clean_text(final_text)
        
        return final_text
    
    def _extract_text_from_k(self, k_value, page_num):
        """Extrae texto del valor K de un elemento."""
        text_parts = []
        
        try:
            if isinstance(k_value, String):
                text_parts.append(str(k_value))
                
            elif isinstance(k_value, int):
                # Es un MCID
                mcid_text = self._get_text_by_mcid(page_num, k_value)
                if mcid_text:
                    text_parts.append(mcid_text)
                    
            elif isinstance(k_value, Array):
                for item in k_value:
                    if isinstance(item, String):
                        text_parts.append(str(item))
                    elif isinstance(item, int):
                        mcid_text = self._get_text_by_mcid(page_num, item)
                        if mcid_text:
                            text_parts.append(mcid_text)
                    elif isinstance(item, Dictionary):
                        # Procesar diccionario (puede ser MCR)
                        if Name.S in item and item.S == Name.MCR:
                            if Name.MCID in item:
                                mcid = item.MCID
                                mcid_text = self._get_text_by_mcid(page_num, mcid)
                                if mcid_text:
                                    text_parts.append(mcid_text)
                        else:
                            # Recursivamente extraer de otros elementos
                            sub_text = self._extract_element_text_enhanced(item, page_num)
                            if sub_text:
                                text_parts.append(sub_text)
                                
            elif isinstance(k_value, Dictionary):
                # Procesar como MCR o elemento anidado
                if Name.S in k_value and k_value.S == Name.MCR:
                    if Name.MCID in k_value:
                        mcid = k_value.MCID
                        mcid_text = self._get_text_by_mcid(page_num, mcid)
                        if mcid_text:
                            text_parts.append(mcid_text)
                else:
                    # Recursivamente extraer de elemento anidado
                    sub_text = self._extract_element_text_enhanced(k_value, page_num)
                    if sub_text:
                        text_parts.append(sub_text)
                        
        except Exception as e:
            logger.debug(f"Error extrayendo texto de K: {e}")
        
        return text_parts
    
    def _get_text_by_mcid(self, page_num, mcid):
        """Obtiene texto por MCID usando el mapeo pre-construido."""
        try:
            if (page_num in self.mcid_to_text and 
                mcid in self.mcid_to_text[page_num]):
                return self.mcid_to_text[page_num][mcid]
                
            # Fallback: extraer directamente de la página
            if page_num < self.page_count:
                page = self.doc[page_num]
                blocks = page.get_text("dict", flags=0)["blocks"]
                for block in blocks:
                    if block["type"] == 0:  # Bloque de texto
                        for line in block["lines"]:
                            for span in line["spans"]:
                                if span.get("mcid") == mcid:
                                    return span["text"]
        except Exception as e:
            logger.debug(f"Error obteniendo texto por MCID {mcid}: {e}")
        
        return ""
    
    def _extract_text_from_page_reference(self, element, page_num):
        """Extrae texto de una referencia de página si es posible."""
        try:
            # Esta es una implementación básica que podría expandirse
            # basándose en referencias específicas del elemento
            if page_num < self.page_count:
                page = self.doc[page_num]
                # Intentar encontrar texto asociado mediante análisis geométrico
                # (implementación simplificada)
                text = page.get_text("text")
                if text and len(text.strip()) < 1000:  # Evitar texto muy largo
                    return text.strip()
        except Exception as e:
            logger.debug(f"Error extrayendo texto de referencia de página: {e}")
        
        return ""
    
    def _clean_text(self, text):
        """Limpia y normaliza el texto extraído."""
        if not text:
            return ""
        
        # Eliminar caracteres de control (excepto espacios, tabs, saltos de línea)
        cleaned = ''.join(char for char in text if ord(char) >= 32 or char in '\t\n\r')
        
        # Normalizar espacios en blanco
        cleaned = ' '.join(cleaned.split())
        
        return cleaned
    
    def _build_element_index(self, node):
        """Construye un índice de elementos por ID para búsqueda rápida."""
        if not node:
            return
            
        # Si es un diccionario con elemento, registrarlo
        if isinstance(node, dict) and "element" in node:
            element_id = id(node["element"]) if node["element"] else id(node)
            self.structure_elements_by_id[element_id] = node
            
            # Procesar hijos recursivamente
            if "children" in node:
                for child in node["children"]:
                    self._build_element_index(child)
                    
        # Si es una lista, procesar cada elemento
        elif isinstance(node, list):
            for item in node:
                self._build_element_index(item)
    
    def find_structure_element_by_id(self, element_id):
        """Busca un elemento de la estructura por su ID."""
        # Usar índice para búsqueda rápida
        if element_id in self.structure_elements_by_id:
            return self.structure_elements_by_id[element_id]
        
        # Si no está en el índice, buscar recursivamente (fallback)
        def search_element(node, target_id):
            if isinstance(node, dict) and "element" in node:
                node_id = id(node["element"]) if node["element"] else id(node)
                if node_id == target_id:
                    return node
                
            if isinstance(node, dict) and "children" in node:
                for child in node["children"]:
                    result = search_element(child, target_id)
                    if result:
                        return result
                        
            return None
            
        return search_element(self.structure_tree, element_id)
    
    def get_element_display_text(self, element):
        """Obtiene texto para mostrar en la interfaz de un elemento."""
        if not isinstance(element, dict):
            return ""
        
        element_type = element.get("type", "Unknown")
        element_text = element.get("text", "").strip()
        
        # Para diferentes tipos de elementos, generar texto descriptivo
        if element_type == "StructTreeRoot":
            child_count = len(element.get("children", []))
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
            alt_text = element.get("attributes", {}).get("alt", "")
            if alt_text:
                return f"Figure: {alt_text}"
            elif element_text:
                return f"Figure: {element_text[:40]}..."
            else:
                return "Figure (no alt text)"
        
        elif element_type == "Table":
            child_count = len(element.get("children", []))
            return f"Table ({child_count} rows)"
        
        elif element_type in ["TH", "TD"]:
            if element_text:
                preview = element_text[:30] + "..." if len(element_text) > 30 else element_text
                return f"{element_type}: {preview}"
            else:
                return f"{element_type} (empty)"
        
        elif element_type == "L":
            child_count = len(element.get("children", []))
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
            mcid = element.get("mcid", "?")
            if element_text:
                preview = element_text[:40] + "..." if len(element_text) > 40 else element_text
                return f"MCID {mcid}: {preview}"
            else:
                return f"MCID {mcid} (no text)"
        
        else:
            # Para otros tipos, mostrar tipo y texto si existe
            if element_text:
                preview = element_text[:40] + "..." if len(element_text) > 40 else element_text
                return f"{element_type}: {preview}"
            else:
                child_count = len(element.get("children", []))
                if child_count > 0:
                    return f"{element_type} ({child_count} children)"
                else:
                    return f"{element_type} (empty)"
    
    # ... resto de métodos existentes (get_visual_content, get_metadata, close, save_structure_tree)
    
    def get_visual_content(self, page_num):
        """Obtiene elementos visuales de una página (texto, imágenes)."""
        if not self.doc or page_num >= self.page_count:
            return []
            
        page = self.doc[page_num]
        elements = []
        
        # Extraer texto
        blocks = page.get_text("dict")["blocks"]
        for block in blocks:
            if block["type"] == 0:  # Bloque de texto
                for line in block["lines"]:
                    for span in line["spans"]:
                        elements.append({
                            "type": "text",
                            "rect": [span["bbox"][0], span["bbox"][1], span["bbox"][2], span["bbox"][3]],
                            "text": span["text"],
                            "font": span["font"],
                            "size": span["size"],
                            "color": span["color"],
                            "mcid": span.get("mcid", -1)
                        })
        
        # Extraer imágenes
        for img_index, img in enumerate(page.get_images(full=True)):
            xref = img[0]
            bbox = page.get_image_bbox(img)
            if bbox:
                elements.append({
                    "type": "image",
                    "rect": [bbox.x0, bbox.y0, bbox.x1, bbox.y1],
                    "xref": xref,
                    "width": img[2],
                    "height": img[3]
                })
                
        return elements
    
    def get_metadata(self):
        """Obtiene los metadatos del documento."""
        metadata = {
            "filename": os.path.basename(self.file_path) if self.file_path else "",
            "has_xmp": False,
            "pdf_ua_flag": False,
            "pdf_ua_version": "",
            "has_lang": False,
            "language": "",
            "title": "",
            "author": "",
            "subject": "",
            "keywords": "",
            "creator": "",
            "producer": "",
            "has_viewer_preferences": False,
            "display_doc_title": False
        }
        
        try:
            if not self.doc or not self.pikepdf_doc:
                return metadata
                
            # Metadatos básicos del diccionario Info
            if self.doc.metadata:
                info_dict = self.doc.metadata
                metadata["info_title"] = info_dict.get("title", "")
                metadata["title"] = info_dict.get("title", "")
                metadata["author"] = info_dict.get("author", "")
                metadata["subject"] = info_dict.get("subject", "")
                metadata["keywords"] = info_dict.get("keywords", "")
                metadata["creator"] = info_dict.get("creator", "")
                metadata["producer"] = info_dict.get("producer", "")
            
            # Verificar XMP
            if hasattr(self.pikepdf_doc, "Root") and self.pikepdf_doc.Root.get("/Metadata"):
                metadata["has_xmp"] = True
                
                # Acceder a metadatos XMP
                with self.pikepdf_doc.open_metadata() as xmp_metadata:
                    # Verificar flag PDF/UA
                    if "pdfuaid:part" in xmp_metadata:
                        metadata["pdf_ua_flag"] = True
                        metadata["pdf_ua_version"] = str(xmp_metadata["pdfuaid:part"])
                    
                    # Extraer título de XMP
                    if "dc:title" in xmp_metadata:
                        if isinstance(xmp_metadata["dc:title"], str):
                            metadata["xmp_title"] = xmp_metadata["dc:title"]
                            metadata["title"] = xmp_metadata["dc:title"]
                        else:
                            # A veces es un array o lista
                            try:
                                if hasattr(xmp_metadata["dc:title"], "item"):
                                    # Es un array o diccionario
                                    if "x-default" in xmp_metadata["dc:title"]:
                                        metadata["xmp_title"] = str(xmp_metadata["dc:title"]["x-default"])
                                        metadata["title"] = str(xmp_metadata["dc:title"]["x-default"])
                            except Exception as e:
                                logger.debug(f"Error procesando dc:title: {e}")
            
            # Verificar Lang a nivel de documento
            if hasattr(self.pikepdf_doc, "Root") and "/Lang" in self.pikepdf_doc.Root:
                metadata["has_lang"] = True
                metadata["language"] = str(self.pikepdf_doc.Root["/Lang"])
            
            # Verificar ViewerPreferences y DisplayDocTitle
            if hasattr(self.pikepdf_doc, "Root") and "/ViewerPreferences" in self.pikepdf_doc.Root:
                metadata["has_viewer_preferences"] = True
                viewer_prefs = self.pikepdf_doc.Root["/ViewerPreferences"]
                if "/DisplayDocTitle" in viewer_prefs:
                    display_doc_title = viewer_prefs["/DisplayDocTitle"]
                    # Puede ser un objeto booleano o un objeto con valor booleano
                    if hasattr(display_doc_title, "value"):
                        metadata["display_doc_title"] = bool(display_doc_title.value)
                    else:
                        metadata["display_doc_title"] = bool(display_doc_title)
                        
            return metadata
            
        except Exception as e:
            logger.error(f"Error getting metadata: {e}")
            return metadata
    
    def close(self):
        """Cierra los documentos abiertos y limpia las referencias."""
        try:
            if self.doc:
                logger.debug("Cerrando documento PyMuPDF")
                self.doc.close()
                self.doc = None
            
            if self.pikepdf_doc:
                logger.debug("Limpiando referencia a documento pikepdf")
                self.pikepdf_doc = None
            
            # Limpiar otras referencias
            self.structure_tree = None
            self.structure_elements_by_id = {}
            self.mcid_to_text = {}
            self.page_count = 0
                
        except Exception as e:
            logger.error(f"Error closing document: {e}")
    
    def save_structure_tree(self, output_path=None):
        """Guarda la estructura del documento en formato JSON."""
        import json
        
        if not self.structure_tree:
            logger.warning("No structure tree to save")
            return None
            
        # Crear una versión serializable (sin referencias a objetos pikepdf)
        def clean_node(node):
            if isinstance(node, dict):
                result = {}
                for key, value in node.items():
                    if key == "element":  # Saltar objetos pikepdf
                        continue
                    elif key == "children":
                        result[key] = clean_node(value)
                    else:
                        result[key] = value
                return result
            elif isinstance(node, list):
                return [clean_node(item) for item in node]
            else:
                return node
                
        clean_tree = clean_node(self.structure_tree)
        
        if output_path:
            with open(output_path, 'w', encoding='utf-8') as f:
                json.dump(clean_tree, f, indent=2, ensure_ascii=False)
            return output_path
        else:
            return json.dumps(clean_tree, indent=2, ensure_ascii=False)