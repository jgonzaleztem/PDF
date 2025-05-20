# pdfua_editor/core/pdf_loader.py

import fitz  # PyMuPDF
from pikepdf import Pdf, Name, Dictionary, Array, String
from loguru import logger

class PDFLoader:
    """Carga y extrae contenido de documentos PDF."""
    
    def __init__(self):
        self.doc = None  # PyMuPDF document
        self.pikepdf_doc = None  # pikepdf document
        self.file_path = None
        self.page_count = 0
        self.structure_tree = None  # Estructura jerárquica del documento
        
    def load_document(self, file_path):
        """Carga un documento PDF."""
        try:
            # Cerrar documentos previos si existen
            if self.doc:
                self.doc.close()
            if self.pikepdf_doc:
                self.pikepdf_doc.close()
                
            # Cargar con PyMuPDF para visualización y extracción básica
            self.doc = fitz.open(file_path)
            self.file_path = file_path
            self.page_count = self.doc.page_count
            
            # Cargar con pikepdf para acceso a la estructura
            self.pikepdf_doc = Pdf.open(file_path)
            
            # Extraer la estructura etiquetada
            self.extract_structure_tree()
            
            return True
        except Exception as e:
            logger.error(f"Error loading PDF: {e}")
            return False
    
    def extract_structure_tree(self):
        """Extrae la estructura jerárquica del documento."""
        self.structure_tree = None
        
        try:
            if "/StructTreeRoot" not in self.pikepdf_doc.Root:
                logger.warning("Document is not tagged (no StructTreeRoot)")
                return None
                
            struct_root = self.pikepdf_doc.Root["/StructTreeRoot"]
            
            # Crear estructura jerárquica
            self.structure_tree = {
                "type": "StructTreeRoot",
                "element": struct_root,
                "children": []
            }
            
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
                        
            return self.structure_tree
        except Exception as e:
            logger.error(f"Error extracting structure tree: {e}")
            return None
    
    def _process_structure_element(self, element, page_num=0):
        """Procesa un elemento de estructura recursivamente."""
        if not element:
            return None
            
        # Manejar Arrays
        if isinstance(element, Array):
            children = []
            for item in element:
                child = self._process_structure_element(item, page_num)
                if child:
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
                "text": self._extract_element_text(element, page_num),
                "children": []
            }
            
            # Procesar hijos recursivamente
            if Name.K in element:
                if isinstance(element.K, Array):
                    for item in element.K:
                        child = self._process_structure_element(item, page_num)
                        if child:
                            if isinstance(child, list):
                                node["children"].extend(child)
                            else:
                                node["children"].append(child)
                elif isinstance(element.K, Dictionary) or isinstance(element.K, Name):
                    child = self._process_structure_element(element.K, page_num)
                    if child:
                        if isinstance(child, list):
                            node["children"].extend(child)
                        else:
                            node["children"].append(child)
                elif isinstance(element.K, String):
                    # El texto está directamente en K
                    node["text"] = str(element.K)
                    
            return node
            
        return None
    
    def _extract_element_text(self, element, page_num):
        """Extrae el texto asociado a un elemento de estructura."""
        # Punto clave: manejar diferentes fuentes de texto
        text = ""
        
        # 1. Si es una figura con texto alternativo
        if element.get(Name.S) == Name.Figure and Name.Alt in element:
            return str(element.Alt)
            
        # 2. Si tiene ActualText definido
        if Name.ActualText in element:
            return str(element.ActualText)
            
        # 3. Extraer de K si es String
        if Name.K in element and isinstance(element.K, String):
            return str(element.K)
            
        # 4. Si contiene referencias a contenido marcado (MCR)
        if Name.K in element:
            if isinstance(element.K, Array):
                for item in element.K:
                    if isinstance(item, String):
                        text += str(item) + " "
                    elif isinstance(item, Dictionary) and Name.S in item and item.S == Name.MCR:
                        # Este es el caso clave: buscar contenido a través de MCID
                        if Name.MCID in item and page_num < self.page_count:
                            mcid = item.MCID
                            # Usar PyMuPDF para obtener texto de la página
                            page = self.doc[page_num]
                            blocks = page.get_text("dict")["blocks"]
                            for block in blocks:
                                for line in block.get("lines", []):
                                    for span in line.get("spans", []):
                                        if "mcid" in span and span["mcid"] == mcid:
                                            text += span["text"] + " "
        
        return text.strip()
    
    def find_structure_element_by_id(self, element_id):
        """Busca un elemento de la estructura por su ID."""
        # En una implementación real, usaríamos un índice precompilado
        def search_element(node, target_id):
            if isinstance(node, dict) and id(node["element"]) == target_id:
                return node
                
            if isinstance(node, dict) and "children" in node:
                for child in node["children"]:
                    result = search_element(child, target_id)
                    if result:
                        return result
                        
            return None
            
        return search_element(self.structure_tree, element_id)
    
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
                json.dump(clean_tree, f, indent=2)
            return output_path
        else:
            return json.dumps(clean_tree, indent=2)