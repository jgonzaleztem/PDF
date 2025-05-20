# pdfua_editor/ui/problems_panel.py

from PySide6.QtWidgets import (QWidget, QVBoxLayout, QHBoxLayout, QPushButton, 
                             QTreeWidget, QTreeWidgetItem, QLabel, QComboBox,
                             QCheckBox, QGroupBox, QMenu, QHeaderView, QSplitter,
                             QTextEdit, QToolButton, QApplication, QProgressBar)
from PySide6.QtCore import Qt, Signal, QSize, QTimer, QSortFilterProxyModel
from PySide6.QtGui import QIcon, QColor, QAction, QFont, QBrush
import qtawesome as qta
from collections import defaultdict
import re

from loguru import logger

class ProblemsPanel(QWidget):
    """
    Panel que muestra problemas de accesibilidad detectados en el PDF.
    
    Responsabilidades:
    - Listar problemas agrupados por categoría
    - Permitir navegación a elementos con problemas
    - Facilitar corrección de problemas específicos
    - Filtrar y organizar problemas por diversos criterios
    
    Relacionado con Matterhorn Protocol:
    - Muestra los 31 checkpoints organizados por categoría (estructura, 
      imágenes, tablas, etc.)
    """
    # Señales
    problemSelected = Signal(dict)  # Información del problema seleccionado
    fixRequested = Signal(dict)     # Solicitud de corrección para un problema específico
    fixAllRequested = Signal(list)  # Solicitud de corrección para múltiples problemas
    filterChanged = Signal(dict)    # Cambio en los filtros aplicados
    
    def __init__(self, parent=None):
        """Inicializa el panel de problemas."""
        super().__init__(parent)
        
        # Inicializar variables
        self.issues = []
        self.filtered_issues = []
        self.categories = {}
        self.checkpoint_groups = self._initialize_checkpoint_groups()
        self.current_filters = {
            'severity': 'Todos',
            'category': 'Todos',
            'page': 'Todas',
            'show_fixed': False
        }
        
        # Inicializar UI
        self._init_ui()
        
    def _init_ui(self):
        """Inicializa la interfaz de usuario del panel."""
        main_layout = QVBoxLayout(self)
        main_layout.setContentsMargins(5, 5, 5, 5)
        main_layout.setSpacing(5)
        
        # Título del panel
        header = QHBoxLayout()
        title = QLabel("<b>Problemas de accesibilidad</b>")
        title.setFont(QFont("Arial", 11))
        header.addWidget(title)
        
        refresh_btn = QToolButton()
        refresh_btn.setIcon(qta.icon("fa5s.sync"))
        refresh_btn.setToolTip("Actualizar")
        refresh_btn.clicked.connect(self._apply_filters)
        header.addWidget(refresh_btn)
        
        header.addStretch()
        
        # Botón ayuda
        help_btn = QToolButton()
        help_btn.setIcon(qta.icon("fa5s.question-circle"))
        help_btn.setToolTip("Ayuda")
        help_btn.clicked.connect(self._show_help)
        header.addWidget(help_btn)
        
        main_layout.addLayout(header)
        
        # Sección de filtros
        filters_box = QGroupBox("Filtros")
        filters_layout = QHBoxLayout(filters_box)
        
        # Filtro por severidad
        filters_layout.addWidget(QLabel("Severidad:"))
        self.severity_combo = QComboBox()
        self.severity_combo.addItems(["Todos", "Error", "Advertencia", "Info"])
        self.severity_combo.currentIndexChanged.connect(self._on_filter_changed)
        filters_layout.addWidget(self.severity_combo)
        
        # Filtro por categoría
        filters_layout.addWidget(QLabel("Categoría:"))
        self.category_combo = QComboBox()
        self.category_combo.addItem("Todos")
        # Las categorías se añadirán dinámicamente
        self.category_combo.currentIndexChanged.connect(self._on_filter_changed)
        filters_layout.addWidget(self.category_combo)
        
        # Filtro por página
        filters_layout.addWidget(QLabel("Página:"))
        self.page_combo = QComboBox()
        self.page_combo.addItem("Todas")
        self.page_combo.currentIndexChanged.connect(self._on_filter_changed)
        filters_layout.addWidget(self.page_combo)
        
        # Mostrar resueltos
        self.show_fixed_cb = QCheckBox("Mostrar resueltos")
        self.show_fixed_cb.stateChanged.connect(self._on_filter_changed)
        filters_layout.addWidget(self.show_fixed_cb)
        
        main_layout.addWidget(filters_box)
        
        # Splitter para árbol y detalles
        splitter = QSplitter(Qt.Vertical)
        
        # Árbol de problemas
        self.issues_tree = QTreeWidget()
        self.issues_tree.setHeaderLabels(["Problema", "Página", "Elemento", "Estado"])
        self.issues_tree.setContextMenuPolicy(Qt.CustomContextMenu)
        self.issues_tree.customContextMenuRequested.connect(self._show_context_menu)
        self.issues_tree.itemClicked.connect(self._on_item_clicked)
        self.issues_tree.setAlternatingRowColors(True)
        
        # Configurar columnas
        header = self.issues_tree.header()
        header.setSectionResizeMode(0, QHeaderView.Stretch)
        header.setSectionResizeMode(1, QHeaderView.ResizeToContents)
        header.setSectionResizeMode(2, QHeaderView.ResizeToContents)
        header.setSectionResizeMode(3, QHeaderView.ResizeToContents)
        
        splitter.addWidget(self.issues_tree)
        
        # Panel de detalles
        self.detail_area = QTextEdit()
        self.detail_area.setReadOnly(True)
        self.detail_area.setMaximumHeight(100)
        splitter.addWidget(self.detail_area)
        
        # Establecer tamaños iniciales
        splitter.setSizes([300, 100])
        
        main_layout.addWidget(splitter, 1)
        
        # Etiqueta de estadísticas
        self.stats_box = QHBoxLayout()
        self.stats_label = QLabel("0 problemas encontrados")
        self.stats_box.addWidget(self.stats_label)
        
        # Barra de progreso para tareas largas
        self.progress_bar = QProgressBar()
        self.progress_bar.setMinimum(0)
        self.progress_bar.setMaximum(100)
        self.progress_bar.setValue(0)
        self.progress_bar.setVisible(False)
        self.stats_box.addWidget(self.progress_bar)
        
        main_layout.addLayout(self.stats_box)
        
        # Botones de acción
        actions_layout = QHBoxLayout()
        
        self.fix_selected_btn = QPushButton("Corregir seleccionado")
        self.fix_selected_btn.setIcon(qta.icon("fa5s.magic"))
        self.fix_selected_btn.clicked.connect(self._on_fix_selected_clicked)
        self.fix_selected_btn.setEnabled(False)
        actions_layout.addWidget(self.fix_selected_btn)
        
        self.fix_all_btn = QPushButton("Corregir todos visibles")
        self.fix_all_btn.setIcon(qta.icon("fa5s.magic"))
        self.fix_all_btn.clicked.connect(self._on_fix_all_clicked)
        actions_layout.addWidget(self.fix_all_btn)
        
        self.mark_reviewed_btn = QPushButton("Marcar como revisado")
        self.mark_reviewed_btn.setIcon(qta.icon("fa5s.check"))
        self.mark_reviewed_btn.clicked.connect(self._on_mark_reviewed_clicked)
        self.mark_reviewed_btn.setEnabled(False)
        actions_layout.addWidget(self.mark_reviewed_btn)
        
        main_layout.addLayout(actions_layout)
        
    def set_issues(self, issues):
        """
        Establece la lista de problemas detectados.
        
        Args:
            issues: Lista de diccionarios con la siguiente estructura:
                {
                    'id': str,              # Identificador único del problema
                    'checkpoint': str,      # Código del checkpoint Matterhorn (ej. '13-004')
                    'category': str,        # Categoría (ej. 'Figure', 'Table', 'Structure')
                    'severity': str,        # Tipo: 'error', 'warning', 'info'
                    'page': int,            # Número de página (opcional)
                    'element_id': str,      # ID del elemento afectado (opcional)
                    'element_type': str,    # Tipo de elemento (ej. 'Figure', 'H1')
                    'description': str,     # Descripción del problema
                    'fix_description': str, # Recomendación de solución
                    'fixed': bool,          # Si ha sido corregido
                    'details': dict         # Información adicional específica del problema
                }
        """
        # Almacenar problemas
        self.issues = issues
        
        # Actualizar filtro de páginas
        self._update_page_filter()
        
        # Actualizar filtro de categorías
        self._update_category_filter()
            
        # Determinar categorías únicas
        self.categories = self._categorize_issues(issues)
            
        # Actualizar estadísticas
        self._update_stats()
        
        # Aplicar filtros y mostrar problemas
        self._apply_filters()
        
        logger.info(f"Problemas cargados: {len(issues)}")
        
    def get_issues(self):
        """
        Retorna la lista completa de problemas.
        
        Returns:
            List[Dict]: Lista completa de problemas
        """
        return self.issues
    
    def get_filtered_issues(self):
        """
        Retorna la lista de problemas filtrados actualmente.
        
        Returns:
            List[Dict]: Lista de problemas filtrados
        """
        return self.filtered_issues
    
    def mark_issue_fixed(self, issue_id, fixed=True):
        """
        Marca un problema como corregido.
        
        Args:
            issue_id: ID del problema a marcar
            fixed: True para marcar como corregido, False para pendiente
            
        Returns:
            bool: True si el cambio fue exitoso
        """
        for issue in self.issues:
            if issue.get('id') == issue_id:
                issue['fixed'] = fixed
                self._apply_filters()  # Actualizar vista
                self._update_stats()   # Actualizar estadísticas
                return True
        return False
    
    def mark_checkpoint_fixed(self, checkpoint, fixed=True):
        """
        Marca todos los problemas de un checkpoint como corregidos.
        
        Args:
            checkpoint: Código del checkpoint (ej. '13-004')
            fixed: True para marcar como corregido, False para pendiente
            
        Returns:
            int: Número de problemas actualizados
        """
        count = 0
        for issue in self.issues:
            if issue.get('checkpoint') == checkpoint:
                issue['fixed'] = fixed
                count += 1
        
        if count > 0:
            self._apply_filters()  # Actualizar vista
            self._update_stats()   # Actualizar estadísticas
            
        return count
    
    def _update_page_filter(self):
        """Actualiza el filtro de páginas basado en los problemas actuales."""
        current_value = self.page_combo.currentText()
        self.page_combo.clear()
        self.page_combo.addItem("Todas")
        
        # Determinar números de página únicos
        pages = set()
        for issue in self.issues:
            page = issue.get('page')
            if page is not None and page != 'all' and isinstance(page, int):
                pages.add(page)
                
        # Añadir páginas ordenadas
        for page in sorted(pages):
            self.page_combo.addItem(f"Página {page}")
        
        # Intentar restaurar selección previa
        index = self.page_combo.findText(current_value)
        if index >= 0:
            self.page_combo.setCurrentIndex(index)
    
    def _update_category_filter(self):
        """Actualiza el filtro de categorías basado en los problemas actuales."""
        current_value = self.category_combo.currentText()
        self.category_combo.clear()
        self.category_combo.addItem("Todos")
        
        # Extraer categorías de checkpoints y agruparlas
        checkpoint_categories = {}
        
        for issue in self.issues:
            checkpoint = issue.get('checkpoint', '')
            if '-' in checkpoint:
                category_id = checkpoint.split('-')[0]
                if category_id in self.checkpoint_groups:
                    category_name = self.checkpoint_groups[category_id]
                    checkpoint_categories[category_id] = category_name
        
        # Añadir categorías ordenadas
        for cat_id, cat_name in sorted(checkpoint_categories.items()):
            self.category_combo.addItem(f"{cat_id}: {cat_name}")
        
        # Intentar restaurar selección previa
        index = self.category_combo.findText(current_value)
        if index >= 0:
            self.category_combo.setCurrentIndex(index)
    
    def _categorize_issues(self, issues):
        """
        Categoriza los problemas por checkpoint.
        
        Args:
            issues: Lista de problemas a categorizar
            
        Returns:
            Dict: Problemas categorizados por checkpoint
        """
        categories = {}
        
        for issue in issues:
            checkpoint = issue.get('checkpoint', 'unknown')
            
            # Obtener o crear categoría
            if checkpoint not in categories:
                category_id = checkpoint.split('-')[0] if '-' in checkpoint else ''
                category_name = self.checkpoint_groups.get(category_id, 'Otros')
                
                categories[checkpoint] = {
                    'name': checkpoint,
                    'category_id': category_id,
                    'category_name': category_name,
                    'issues': []
                }
            
            # Añadir problema a la categoría
            categories[checkpoint]['issues'].append(issue)
        
        return categories
    
    def _apply_filters(self):
        """Aplica los filtros seleccionados y actualiza la vista de árbol."""
        # Mostrar indicador de progreso para operaciones grandes
        if len(self.issues) > 100:
            self.progress_bar.setVisible(True)
            self.progress_bar.setValue(10)
            QApplication.processEvents()
        
        # Limpiar árbol
        self.issues_tree.clear()
        self.filtered_issues = []
        
        # Obtener filtros
        severity_filter = self.severity_combo.currentText()
        category_text = self.category_combo.currentText()
        page_text = self.page_combo.currentText()
        show_fixed = self.show_fixed_cb.isChecked()
        
        # Almacenar filtros actuales
        self.current_filters['severity'] = severity_filter
        self.current_filters['category'] = category_text
        self.current_filters['page'] = page_text
        self.current_filters['show_fixed'] = show_fixed
        
        # Extraer ID de categoría si está seleccionada
        category_filter = None
        if category_text != "Todos":
            # Extraer ID de categoría (ej. "01: Etiquetado de contenido real" -> "01")
            match = re.match(r'(\d+):', category_text)
            if match:
                category_filter = match.group(1)
        
        # Extraer número de página si está seleccionada
        page_filter = None
        if page_text != "Todas":
            # Extraer número de página (ej. "Página 5" -> 5)
            match = re.match(r'Página\s+(\d+)', page_text)
            if match:
                page_filter = int(match.group(1))
        
        # Actualizar progreso
        if self.progress_bar.isVisible():
            self.progress_bar.setValue(20)
            QApplication.processEvents()
        
        # Agrupar problemas por checkpoint
        checkpoint_items = {}
        
        # Añadir problemas filtrados
        total_visible = 0
        items_to_expand = []
        
        # Procesar primero los errores, luego advertencias, luego info
        severity_order = {
            'error': 1, 
            'warning': 2, 
            'info': 3
        }
        
        # Ordenar problemas por severidad, checkpoint y página
        sorted_issues = sorted(
            self.issues,
            key=lambda i: (
                severity_order.get(i.get('severity', ''), 999),
                i.get('checkpoint', ''),
                i.get('page', 999) if isinstance(i.get('page', 'all'), int) else 999
            )
        )
        
        # Configurar progreso para procesamiento de problemas
        total_issues = len(sorted_issues)
        progress_step = 60 / max(total_issues, 1)
        progress_value = 20
        
        for issue in sorted_issues:
            # Actualizar progreso
            if self.progress_bar.isVisible():
                progress_value += progress_step
                self.progress_bar.setValue(int(progress_value))
                if int(progress_value) % 10 == 0:
                    QApplication.processEvents()
            
            # Aplicar filtros
            # Filtrar por severidad
            if severity_filter != "Todos" and issue.get('severity', '').lower() != severity_filter.lower():
                continue
                
            # Filtrar por categoría
            if category_filter:
                checkpoint = issue.get('checkpoint', '')
                checkpoint_category = checkpoint.split('-')[0] if '-' in checkpoint else ''
                if checkpoint_category != category_filter:
                    continue
                    
            # Filtrar por página
            if page_filter is not None:
                page = issue.get('page')
                if page != page_filter and page != 'all':
                    continue
                    
            # Filtrar por estado
            if not show_fixed and issue.get('fixed', False):
                continue
                
            # Incrementar contador y añadir a lista filtrada
            total_visible += 1
            self.filtered_issues.append(issue)
            
            # Obtener o crear ítem de checkpoint para este problema
            checkpoint = issue.get('checkpoint', 'unknown')
            if checkpoint not in checkpoint_items:
                # Obtener categoría del checkpoint
                category_id = checkpoint.split('-')[0] if '-' in checkpoint else ''
                category_name = self.checkpoint_groups.get(category_id, 'Otros')
                
                # Crear ítem para el checkpoint
                checkpoint_item = QTreeWidgetItem(self.issues_tree)
                checkpoint_item.setText(0, f"{checkpoint}: {category_name}")
                checkpoint_item.setFirstColumnSpanned(True)
                
                # Configurar fuente en negrita
                font = checkpoint_item.font(0)
                font.setBold(True)
                checkpoint_item.setFont(0, font)
                
                # Guardar ítem para expandir más tarde
                items_to_expand.append(checkpoint_item)
                
                checkpoint_items[checkpoint] = checkpoint_item
            else:
                checkpoint_item = checkpoint_items[checkpoint]
                
            # Crear ítem para el problema
            issue_item = QTreeWidgetItem(checkpoint_item)
            
            # Establecer textos
            issue_item.setText(0, issue.get('description', ''))
            
            page_text = str(issue.get('page', '-')) if issue.get('page') != 'all' else "Todo"
            issue_item.setText(1, page_text)
            
            element_text = issue.get('element_type', '-')
            issue_item.setText(2, element_text)
            
            status_text = "✓ Corregido" if issue.get('fixed', False) else "❌ Pendiente"
            issue_item.setText(3, status_text)
            
            # Guardar referencia al issue en el item
            issue_item.setData(0, Qt.UserRole, issue)
            
            # Establecer colores según tipo
            if issue.get('severity', '') == 'error':
                issue_item.setForeground(0, QColor(255, 0, 0))
            elif issue.get('severity', '') == 'warning':
                issue_item.setForeground(0, QColor(255, 165, 0))
                
            # Marcar visualmente los corregidos
            if issue.get('fixed', False):
                for col in range(4):
                    issue_item.setForeground(col, QColor(100, 100, 100))
                    
        # Expandir ítems de checkpoint
        for item in items_to_expand:
            item.setExpanded(True)
        
        # Actualizar etiqueta de estadísticas para reflejar los filtros
        self.stats_label.setText(f"{total_visible} problemas mostrados de {len(self.issues)} total")
        
        # Habilitar/deshabilitar botones según número de problemas
        self.fix_all_btn.setEnabled(total_visible > 0)
        
        # Ocultar barra de progreso
        if self.progress_bar.isVisible():
            self.progress_bar.setValue(100)
            QApplication.processEvents()
            self.progress_bar.setVisible(False)
        
        # Emitir señal de cambio de filtro
        self.filterChanged.emit(self.current_filters)
        
    def _update_stats(self):
        """Actualiza estadísticas de problemas."""
        total = len(self.issues)
        errors = sum(1 for issue in self.issues if issue.get('severity', '') == 'error')
        warnings = sum(1 for issue in self.issues if issue.get('severity', '') == 'warning')
        fixed = sum(1 for issue in self.issues if issue.get('fixed', False))
        
        self.stats_label.setText(
            f"Total: {total} | Errores: {errors} | Advertencias: {warnings} | Corregidos: {fixed}"
        )
        
    def _on_item_clicked(self, item, column):
        """Maneja el clic en un ítem del árbol."""
        # Habilitar botones si es un elemento válido
        has_valid_item = item is not None and item.parent() is not None
        self.fix_selected_btn.setEnabled(has_valid_item)
        self.mark_reviewed_btn.setEnabled(has_valid_item)
        
        # Ignorar clics en categorías
        if not has_valid_item:
            self.detail_area.clear()
            return
            
        # Obtener información del problema
        issue = item.data(0, Qt.UserRole)
        if issue:
            # Emitir señal para navegar al problema
            self.problemSelected.emit(issue)
            
            # Mostrar detalles del problema
            self._show_issue_details(issue)
            
    def _show_issue_details(self, issue):
        """
        Muestra detalles del problema en el área de detalles.
        
        Args:
            issue: Información del problema
        """
        if not issue:
            self.detail_area.clear()
            return
            
        # Formatear HTML para detalles
        html = "<html><body style='font-family: Arial; font-size: 10pt;'>"
        
        # Información básica
        severity_color = {
            'error': '#d83933',
            'warning': '#fdb81e',
            'info': '#02bfe7'
        }.get(issue.get('severity', ''), 'black')
        
        html += f"<p><b>Checkpoint:</b> {issue.get('checkpoint', '-')}</p>"
        html += f"<p><b>Severidad:</b> <span style='color:{severity_color};'>{issue.get('severity', '-').title()}</span></p>"
        
        # Descripción
        html += f"<p><b>Descripción:</b> {issue.get('description', '')}</p>"
        
        # Recomendación
        if issue.get('fix_description'):
            html += f"<p><b>Recomendación:</b> {issue.get('fix_description', '')}</p>"
        
        # Detalles adicionales
        details = issue.get('details', {})
        if details:
            html += "<p><b>Detalles adicionales:</b></p><ul>"
            for key, value in details.items():
                html += f"<li><b>{key}:</b> {value}</li>"
            html += "</ul>"
        
        html += "</body></html>"
        self.detail_area.setHtml(html)
            
    def _show_context_menu(self, position):
        """Muestra menú contextual para un ítem."""
        item = self.issues_tree.itemAt(position)
        
        # Menú para ítems de checkpoint
        if item and item.parent() is None:
            self._show_checkpoint_menu(item, self.issues_tree.viewport().mapToGlobal(position))
            return
            
        # Menú para ítems de problema
        if item and item.parent() is not None:
            self._show_issue_menu(item, self.issues_tree.viewport().mapToGlobal(position))
            return
    
    def _show_checkpoint_menu(self, item, global_pos):
        """
        Muestra menú contextual para un checkpoint.
        
        Args:
            item: Ítem del checkpoint en el árbol
            global_pos: Posición global del ratón
        """
        checkpoint_text = item.text(0).split(':')[0]
        
        menu = QMenu(self)
        
        # Acciones
        fix_all_action = QAction("Corregir todos los problemas de este checkpoint", self)
        fix_all_action.triggered.connect(lambda: self._on_fix_checkpoint(checkpoint_text))
        menu.addAction(fix_all_action)
        
        mark_all_action = QAction("Marcar todos como revisados", self)
        mark_all_action.triggered.connect(lambda: self._on_mark_checkpoint_reviewed(checkpoint_text))
        menu.addAction(mark_all_action)
        
        unmark_all_action = QAction("Marcar todos como pendientes", self)
        unmark_all_action.triggered.connect(lambda: self._on_mark_checkpoint_pending(checkpoint_text))
        menu.addAction(unmark_all_action)
        
        menu.addSeparator()
        
        help_action = QAction("Ayuda sobre este checkpoint", self)
        help_action.triggered.connect(lambda: self._on_checkpoint_help(checkpoint_text))
        menu.addAction(help_action)
        
        # Mostrar menú
        menu.exec_(global_pos)
    
    def _show_issue_menu(self, item, global_pos):
        """
        Muestra menú contextual para un problema.
        
        Args:
            item: Ítem del problema en el árbol
            global_pos: Posición global del ratón
        """
        issue = item.data(0, Qt.UserRole)
        if not issue:
            return
            
        menu = QMenu(self)
        
        # Acciones
        fix_action = QAction("Corregir este problema", self)
        fix_action.triggered.connect(lambda: self._on_fix_issue(issue))
        menu.addAction(fix_action)
        
        if not issue.get('fixed', False):
            mark_action = QAction("Marcar como revisado", self)
            mark_action.triggered.connect(lambda: self._on_mark_issue_reviewed(issue))
            menu.addAction(mark_action)
        else:
            unmark_action = QAction("Marcar como pendiente", self)
            unmark_action.triggered.connect(lambda: self._on_mark_issue_pending(issue))
            menu.addAction(unmark_action)
            
        goto_action = QAction("Ir a elemento", self)
        goto_action.triggered.connect(lambda: self._on_goto_element(issue))
        menu.addAction(goto_action)
        
        menu.addSeparator()
        
        checkpoint = issue.get('checkpoint', '')
        help_action = QAction(f"Ayuda sobre checkpoint {checkpoint}", self)
        help_action.triggered.connect(lambda: self._on_checkpoint_help(checkpoint))
        menu.addAction(help_action)
        
        # Mostrar menú
        menu.exec_(global_pos)
        
    def _on_fix_selected_clicked(self):
        """Maneja el clic en el botón de corregir seleccionado."""
        selected_items = self.issues_tree.selectedItems()
        
        if not selected_items:
            return
            
        # Obtener información del problema
        item = selected_items[0]
        if item.parent() is None:
            # Es un checkpoint, no un problema individual
            checkpoint = item.text(0).split(':')[0]
            self._on_fix_checkpoint(checkpoint)
        else:
            # Es un problema individual
            issue = item.data(0, Qt.UserRole)
            if issue:
                self._on_fix_issue(issue)
            
    def _on_fix_all_clicked(self):
        """Maneja el clic en el botón de corregir todos los problemas visibles."""
        if not self.filtered_issues:
            return
        
        # Obtener problemas no corregidos
        unfixed_issues = [issue for issue in self.filtered_issues if not issue.get('fixed', False)]
        
        # Si hay problemas para corregir, emitir señal para corregirlos
        if unfixed_issues:
            # Emitir señal con todos los problemas a corregir
            self.fixAllRequested.emit(unfixed_issues)
            
            # Marcar como corregidos
            for issue in unfixed_issues:
                issue['fixed'] = True
                
            # Actualizar vista
            self._apply_filters()
            self._update_stats()
            
    def _on_mark_reviewed_clicked(self):
        """Maneja el clic en el botón de marcar como revisado."""
        selected_items = self.issues_tree.selectedItems()
        
        if not selected_items:
            return
            
        # Obtener información del problema/checkpoint
        item = selected_items[0]
        if item.parent() is None:
            # Es un checkpoint, no un problema individual
            checkpoint = item.text(0).split(':')[0]
            self._on_mark_checkpoint_reviewed(checkpoint)
        else:
            # Es un problema individual
            issue = item.data(0, Qt.UserRole)
            if issue:
                self._on_mark_issue_reviewed(issue)
            
    def _on_fix_issue(self, issue):
        """Maneja la solicitud de corrección de un problema específico."""
        # Emitir señal para corregir problema
        self.fixRequested.emit(issue)
        
        # Marcar como corregido
        issue['fixed'] = True
        
        # Actualizar vista
        self._apply_filters()
        self._update_stats()
        
    def _on_fix_checkpoint(self, checkpoint):
        """
        Maneja la solicitud de corrección de todos los problemas de un checkpoint.
        
        Args:
            checkpoint: Código del checkpoint (ej. '13-004')
        """
        # Recopilar todos los problemas no corregidos de este checkpoint
        checkpoint_issues = [
            issue for issue in self.issues 
            if issue.get('checkpoint', '') == checkpoint and not issue.get('fixed', False)
        ]
        
        if not checkpoint_issues:
            return
            
        # Emitir señal para corregir problemas
        self.fixAllRequested.emit(checkpoint_issues)
        
        # Marcar como corregidos
        for issue in checkpoint_issues:
            issue['fixed'] = True
            
        # Actualizar vista
        self._apply_filters()
        self._update_stats()
        
    def _on_mark_issue_reviewed(self, issue):
        """Marca un problema como revisado."""
        issue['fixed'] = True
        
        # Actualizar vista
        self._apply_filters()
        self._update_stats()
        
    def _on_mark_issue_pending(self, issue):
        """Marca un problema como pendiente."""
        issue['fixed'] = False
        
        # Actualizar vista
        self._apply_filters()
        self._update_stats()
        
    def _on_mark_checkpoint_reviewed(self, checkpoint):
        """
        Marca todos los problemas de un checkpoint como revisados.
        
        Args:
            checkpoint: Código del checkpoint (ej. '13-004')
        """
        for issue in self.issues:
            if issue.get('checkpoint', '') == checkpoint:
                issue['fixed'] = True
                
        # Actualizar vista
        self._apply_filters()
        self._update_stats()
        
    def _on_mark_checkpoint_pending(self, checkpoint):
        """
        Marca todos los problemas de un checkpoint como pendientes.
        
        Args:
            checkpoint: Código del checkpoint (ej. '13-004')
        """
        for issue in self.issues:
            if issue.get('checkpoint', '') == checkpoint:
                issue['fixed'] = False
                
        # Actualizar vista
        self._apply_filters()
        self._update_stats()
        
    def _on_goto_element(self, issue):
        """Navega al elemento con problema."""
        self.problemSelected.emit(issue)
        
    def _on_checkpoint_help(self, checkpoint):
        """
        Muestra ayuda sobre un checkpoint específico.
        
        Args:
            checkpoint: Código del checkpoint (ej. '13-004')
        """
        # Esta función debería mostrar información específica del checkpoint
        # según el Matterhorn Protocol
        
        # En una implementación completa, esta función mostraría un diálogo con
        # información detallada sobre el checkpoint, incluyendo referencias al
        # protocolo Matterhorn y las mejores prácticas PDF/UA
        
        # Emitir un evento personalizado para que la ventana principal muestre la ayuda
        # (la ventana principal tiene acceso al componente MatterhornChecker)
        self.parent().show_matterhorn_help(checkpoint)
    
    def _on_filter_changed(self):
        """Maneja cambios en los filtros y actualiza la vista."""
        self._apply_filters()
    
    def _show_help(self):
        """Muestra diálogo de ayuda para el panel de problemas."""
        # Esta función mostraría un diálogo con ayuda sobre el panel de problemas
        # En una implementación completa, esta función explicaría cómo usar los
        # filtros, el árbol de problemas y las acciones disponibles
        
        self.parent().show_help_dialog(
            "Ayuda del Panel de Problemas",
            """
            <h3>Panel de Problemas de Accesibilidad PDF/UA</h3>
            <p>Este panel muestra los problemas de accesibilidad detectados en el documento según los criterios de Matterhorn Protocol y PDF/UA.</p>
            
            <h4>Filtros</h4>
            <ul>
                <li><b>Severidad:</b> Filtra por nivel de gravedad (Error, Advertencia, Info)</li>
                <li><b>Categoría:</b> Filtra por tipo de problema (estructura, imágenes, tablas, etc.)</li>
                <li><b>Página:</b> Muestra problemas de una página específica</li>
                <li><b>Mostrar resueltos:</b> Incluye problemas ya marcados como corregidos</li>
            </ul>
            
            <h4>Árbol de Problemas</h4>
            <p>Los problemas se organizan por checkpoint de Matterhorn. Para cada problema puede:</p>
            <ul>
                <li>Hacer clic para ver detalles y navegar al elemento afectado</li>
                <li>Clic derecho para acceder a opciones adicionales</li>
                <li>Usar los botones de acción para corregir problemas</li>
            </ul>
            
            <h4>Acciones</h4>
            <ul>
                <li><b>Corregir seleccionado:</b> Aplica corrección automática al problema seleccionado</li>
                <li><b>Corregir todos visibles:</b> Aplica correcciones a todos los problemas visibles</li>
                <li><b>Marcar como revisado:</b> Marca el problema como revisado manualmente</li>
            </ul>
            """
        )
        
    def _initialize_checkpoint_groups(self):
        """
        Inicializa los grupos de checkpoints según Matterhorn Protocol.
        
        Returns:
            Dict: Mapeo de ID de grupo a nombre
        """
        return {
            "01": "Etiquetado de contenido real",
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