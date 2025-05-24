# ui/problems_panel.py

from PySide6.QtWidgets import (QWidget, QVBoxLayout, QHBoxLayout, QTreeWidget, 
                              QTreeWidgetItem, QPushButton, QLineEdit, QLabel,
                              QComboBox, QHeaderView, QMenu, QMessageBox, QFrame,
                              QCheckBox, QGroupBox, QSplitter, QTextEdit)
from PySide6.QtCore import Qt, Signal, QTimer
from PySide6.QtGui import QIcon, QFont, QColor, QAction
from loguru import logger
import qtawesome as qta
from typing import List, Dict, Any, Optional

class ProblemsPanel(QWidget):
    """
    Panel para mostrar y gestionar problemas de accesibilidad detectados.
    Permite filtrar, ordenar y navegar a los problemas encontrados.
    """
    
    problemSelected = Signal(dict)  # Emite el problema seleccionado
    fixRequested = Signal(dict)     # Emite solicitud de reparación
    navigateToPage = Signal(int)    # Emite solicitud de navegación a página
    
    def __init__(self, parent=None):
        super().__init__(parent)
        
        self.issues = []  # Lista de problemas
        self.filtered_issues = []  # Lista filtrada
        self.current_issue = None
        
        # Filtros
        self.severity_filter = "all"
        self.checkpoint_filter = "all"
        self.fixable_filter = "all"
        self.search_text = ""
        
        self._init_ui()
        self._setup_context_menu()
        
        # Timer para búsqueda diferida
        self.search_timer = QTimer()
        self.search_timer.setSingleShot(True)
        self.search_timer.timeout.connect(self._apply_filters)
    
    def _init_ui(self):
        """Inicializa la interfaz de usuario."""
        main_layout = QVBoxLayout(self)
        
        # Barra de herramientas y filtros
        self._create_toolbar(main_layout)
        
        # Splitter para dividir lista y detalles
        splitter = QSplitter(Qt.Horizontal)
        
        # Panel izquierdo - Lista de problemas
        self._create_problems_list(splitter)
        
        # Panel derecho - Detalles del problema
        self._create_details_panel(splitter)
        
        # Configurar proporciones del splitter
        splitter.setSizes([400, 300])
        main_layout.addWidget(splitter)
        
        # Barra de estado
        self._create_status_bar(main_layout)
    
    def _create_toolbar(self, layout):
        """Crea la barra de herramientas con filtros."""
        toolbar_group = QGroupBox("Filtros y Búsqueda")
        toolbar_layout = QVBoxLayout(toolbar_group)
        
        # Primera fila - Filtros principales
        filters_layout = QHBoxLayout()
        
        # Filtro por severidad
        filters_layout.addWidget(QLabel("Severidad:"))
        self.severity_combo = QComboBox()
        self.severity_combo.addItems(["Todos", "Errores", "Advertencias", "Información"])
        self.severity_combo.currentTextChanged.connect(self._on_severity_filter_changed)
        filters_layout.addWidget(self.severity_combo)
        
        # Filtro por checkpoint
        filters_layout.addWidget(QLabel("Checkpoint:"))
        self.checkpoint_combo = QComboBox()
        self.checkpoint_combo.addItem("Todos")
        self.checkpoint_combo.currentTextChanged.connect(self._on_checkpoint_filter_changed)
        filters_layout.addWidget(self.checkpoint_combo)
        
        # Filtro por reparable
        filters_layout.addWidget(QLabel("Reparable:"))
        self.fixable_combo = QComboBox()
        self.fixable_combo.addItems(["Todos", "Sí", "No"])
        self.fixable_combo.currentTextChanged.connect(self._on_fixable_filter_changed)
        filters_layout.addWidget(self.fixable_combo)
        
        filters_layout.addStretch()
        
        toolbar_layout.addLayout(filters_layout)
        
        # Segunda fila - Búsqueda y acciones
        search_layout = QHBoxLayout()
        
        # Campo de búsqueda
        search_layout.addWidget(QLabel("Buscar:"))
        self.search_field = QLineEdit()
        self.search_field.setPlaceholderText("Buscar en descripción...")
        self.search_field.textChanged.connect(self._on_search_changed)
        search_layout.addWidget(self.search_field)
        
        # Botón de limpiar filtros
        self.clear_filters_btn = QPushButton("Limpiar Filtros")
        self.clear_filters_btn.clicked.connect(self._clear_filters)
        search_layout.addWidget(self.clear_filters_btn)
        
        # Botón de exportar
        self.export_btn = QPushButton("Exportar")
        self.export_btn.clicked.connect(self._export_issues)
        search_layout.addWidget(self.export_btn)
        
        toolbar_layout.addLayout(search_layout)
        
        layout.addWidget(toolbar_group)
    
    def _create_problems_list(self, parent):
        """Crea la lista de problemas."""
        list_widget = QWidget()
        list_layout = QVBoxLayout(list_widget)
        
        # Encabezado
        header_layout = QHBoxLayout()
        header_label = QLabel("Problemas Detectados")
        header_label.setFont(QFont("Arial", 10, QFont.Bold))
        header_layout.addWidget(header_label)
        
        self.count_label = QLabel("0 problemas")
        self.count_label.setStyleSheet("color: #666;")
        header_layout.addWidget(self.count_label)
        header_layout.addStretch()
        
        list_layout.addLayout(header_layout)
        
        # Árbol de problemas
        self.problems_tree = QTreeWidget()
        self.problems_tree.setHeaderLabels(["Severidad", "Checkpoint", "Descripción", "Página", "Reparable"])
        
        # Configurar columnas
        header = self.problems_tree.header()
        header.setSectionResizeMode(0, QHeaderView.ResizeToContents)  # Severidad
        header.setSectionResizeMode(1, QHeaderView.ResizeToContents)  # Checkpoint
        header.setSectionResizeMode(2, QHeaderView.Stretch)           # Descripción
        header.setSectionResizeMode(3, QHeaderView.ResizeToContents)  # Página
        header.setSectionResizeMode(4, QHeaderView.ResizeToContents)  # Reparable
        
        # Conectar eventos
        self.problems_tree.itemSelectionChanged.connect(self._on_problem_selected)
        self.problems_tree.itemDoubleClicked.connect(self._on_problem_double_clicked)
        
        # Habilitar menú contextual
        self.problems_tree.setContextMenuPolicy(Qt.CustomContextMenu)
        self.problems_tree.customContextMenuRequested.connect(self._show_context_menu)
        
        list_layout.addWidget(self.problems_tree)
        
        parent.addWidget(list_widget)
    
    def _create_details_panel(self, parent):
        """Crea el panel de detalles del problema."""
        details_widget = QWidget()
        details_layout = QVBoxLayout(details_widget)
        
        # Encabezado
        header_label = QLabel("Detalles del Problema")
        header_label.setFont(QFont("Arial", 10, QFont.Bold))
        details_layout.addWidget(header_label)
        
        # Información básica
        info_group = QGroupBox("Información")
        info_layout = QVBoxLayout(info_group)
        
        self.checkpoint_label = QLabel("Checkpoint: -")
        info_layout.addWidget(self.checkpoint_label)
        
        self.severity_label = QLabel("Severidad: -")
        info_layout.addWidget(self.severity_label)
        
        self.page_label = QLabel("Página: -")
        info_layout.addWidget(self.page_label)
        
        self.fixable_label = QLabel("Reparable: -")
        info_layout.addWidget(self.fixable_label)
        
        details_layout.addWidget(info_group)
        
        # Descripción
        desc_group = QGroupBox("Descripción")
        desc_layout = QVBoxLayout(desc_group)
        
        self.description_text = QTextEdit()
        self.description_text.setMaximumHeight(80)
        self.description_text.setReadOnly(True)
        desc_layout.addWidget(self.description_text)
        
        details_layout.addWidget(desc_group)
        
        # Solución
        fix_group = QGroupBox("Solución Sugerida")
        fix_layout = QVBoxLayout(fix_group)
        
        self.fix_description_text = QTextEdit()
        self.fix_description_text.setMaximumHeight(80)
        self.fix_description_text.setReadOnly(True)
        fix_layout.addWidget(self.fix_description_text)
        
        details_layout.addWidget(fix_group)
        
        # Botones de acción
        actions_layout = QHBoxLayout()
        
        self.navigate_btn = QPushButton("Ir a Página")
        self.navigate_btn.setIcon(qta.icon("fa5s.external-link-alt"))
        self.navigate_btn.clicked.connect(self._on_navigate_clicked)
        self.navigate_btn.setEnabled(False)
        actions_layout.addWidget(self.navigate_btn)
        
        self.fix_btn = QPushButton("Reparar")
        self.fix_btn.setIcon(qta.icon("fa5s.tools"))
        self.fix_btn.clicked.connect(self._on_fix_clicked)
        self.fix_btn.setEnabled(False)
        actions_layout.addWidget(self.fix_btn)
        
        actions_layout.addStretch()
        
        details_layout.addLayout(actions_layout)
        details_layout.addStretch()
        
        parent.addWidget(details_widget)
    
    def _create_status_bar(self, layout):
        """Crea la barra de estado."""
        status_layout = QHBoxLayout()
        
        self.status_label = QLabel("Listo")
        self.status_label.setStyleSheet("color: #666; font-size: 10px;")
        status_layout.addWidget(self.status_label)
        
        status_layout.addStretch()
        
        # Estadísticas
        self.stats_label = QLabel("")
        self.stats_label.setStyleSheet("color: #666; font-size: 10px;")
        status_layout.addWidget(self.stats_label)
        
        layout.addLayout(status_layout)
    
    def _setup_context_menu(self):
        """Configura el menú contextual."""
        self.context_menu = QMenu(self)
        
        # Acción de navegación
        self.action_navigate = QAction(qta.icon("fa5s.external-link-alt"), "Ir a página", self)
        self.action_navigate.triggered.connect(self._on_navigate_clicked)
        self.context_menu.addAction(self.action_navigate)
        
        # Acción de reparación
        self.action_fix = QAction(qta.icon("fa5s.tools"), "Reparar problema", self)
        self.action_fix.triggered.connect(self._on_fix_clicked)
        self.context_menu.addAction(self.action_fix)
        
        self.context_menu.addSeparator()
        
        # Acción de copiar
        self.action_copy = QAction(qta.icon("fa5s.copy"), "Copiar descripción", self)
        self.action_copy.triggered.connect(self._copy_description)
        self.context_menu.addAction(self.action_copy)
        
        # Acción de marcar como revisado
        self.action_mark_reviewed = QAction("Marcar como revisado", self)
        self.action_mark_reviewed.triggered.connect(self._mark_as_reviewed)
        self.context_menu.addAction(self.action_mark_reviewed)
    
    def set_issues(self, issues: List[Dict]):
        """
        Establece la lista de problemas a mostrar.
        
        Args:
            issues: Lista de problemas detectados
        """
        self.issues = issues.copy() if issues else []
        
        # Actualizar lista de checkpoints para el filtro
        self._update_checkpoint_filter()
        
        # Aplicar filtros
        self._apply_filters()
        
        # Actualizar estadísticas
        self._update_statistics()
        
        logger.info(f"Panel de problemas actualizado con {len(self.issues)} problemas")
    
    def get_issues(self) -> List[Dict]:
        """Obtiene la lista actual de problemas."""
        return self.issues.copy()
    
    def _update_checkpoint_filter(self):
        """Actualiza la lista de checkpoints en el filtro."""
        checkpoints = set()
        for issue in self.issues:
            checkpoint = issue.get("checkpoint", "")
            if checkpoint:
                checkpoints.add(checkpoint)
        
        # Limpiar y rellenar combo
        current_text = self.checkpoint_combo.currentText()
        self.checkpoint_combo.clear()
        self.checkpoint_combo.addItem("Todos")
        
        for checkpoint in sorted(checkpoints):
            self.checkpoint_combo.addItem(checkpoint)
        
        # Restaurar selección si es posible
        index = self.checkpoint_combo.findText(current_text)
        if index >= 0:
            self.checkpoint_combo.setCurrentIndex(index)
    
    def _apply_filters(self):
        """Aplica los filtros actuales a la lista de problemas."""
        self.filtered_issues = []
        
        for issue in self.issues:
            # Filtro por severidad
            if self.severity_filter != "all":
                issue_severity = issue.get("severity", "").lower()
                if self.severity_filter == "error" and issue_severity != "error":
                    continue
                elif self.severity_filter == "warning" and issue_severity != "warning":
                    continue
                elif self.severity_filter == "info" and issue_severity != "info":
                    continue
            
            # Filtro por checkpoint
            if self.checkpoint_filter != "all":
                issue_checkpoint = issue.get("checkpoint", "")
                if issue_checkpoint != self.checkpoint_filter:
                    continue
            
            # Filtro por reparable
            if self.fixable_filter != "all":
                is_fixable = issue.get("fixable", False)
                if self.fixable_filter == "yes" and not is_fixable:
                    continue
                elif self.fixable_filter == "no" and is_fixable:
                    continue
            
            # Filtro de búsqueda
            if self.search_text:
                description = issue.get("description", "").lower()
                fix_description = issue.get("fix_description", "").lower()
                if (self.search_text.lower() not in description and 
                    self.search_text.lower() not in fix_description):
                    continue
            
            self.filtered_issues.append(issue)
        
        # Actualizar vista
        self._update_problems_tree()
        self._update_count_label()
    
    def _update_problems_tree(self):
        """Actualiza el árbol de problemas con los problemas filtrados."""
        self.problems_tree.clear()
        
        # Agrupar por checkpoint
        grouped_issues = {}
        for issue in self.filtered_issues:
            checkpoint = issue.get("checkpoint", "Unknown")
            if checkpoint not in grouped_issues:
                grouped_issues[checkpoint] = []
            grouped_issues[checkpoint].append(issue)
        
        # Crear elementos del árbol
        for checkpoint in sorted(grouped_issues.keys()):
            issues_in_checkpoint = grouped_issues[checkpoint]
            
            # Crear elemento padre para el checkpoint
            checkpoint_item = QTreeWidgetItem(self.problems_tree)
            checkpoint_item.setText(0, "")  # Severidad (vacía para grupo)
            checkpoint_item.setText(1, checkpoint)
            checkpoint_item.setText(2, f"{len(issues_in_checkpoint)} problemas")
            checkpoint_item.setText(3, "")  # Página (vacía para grupo)
            checkpoint_item.setText(4, "")  # Reparable (vacía para grupo)
            
            # Estilo para el grupo
            font = QFont()
            font.setBold(True)
            checkpoint_item.setFont(1, font)
            checkpoint_item.setFont(2, font)
            
            # Crear elementos hijos para cada problema
            for issue in issues_in_checkpoint:
                issue_item = QTreeWidgetItem(checkpoint_item)
                
                # Configurar columnas
                severity = issue.get("severity", "").upper()
                issue_item.setText(0, severity)
                issue_item.setText(1, "")  # Checkpoint vacío para hijos
                issue_item.setText(2, issue.get("description", ""))
                
                page = issue.get("page", "")
                if isinstance(page, int):
                    issue_item.setText(3, str(page + 1))  # Convertir a base 1
                elif page == "all":
                    issue_item.setText(3, "Todas")
                else:
                    issue_item.setText(3, str(page))
                
                issue_item.setText(4, "Sí" if issue.get("fixable", False) else "No")
                
                # Configurar colores según severidad
                if severity == "ERROR":
                    color = QColor(255, 0, 0)  # Rojo
                elif severity == "WARNING":
                    color = QColor(255, 165, 0)  # Naranja
                else:
                    color = QColor(0, 0, 255)  # Azul
                
                issue_item.setForeground(0, color)
                
                # Almacenar referencia al problema
                issue_item.setData(0, Qt.UserRole, issue)
            
            # Expandir el grupo si tiene pocos elementos
            if len(issues_in_checkpoint) <= 5:
                checkpoint_item.setExpanded(True)
    
    def _update_count_label(self):
        """Actualiza la etiqueta de conteo."""
        total = len(self.issues)
        filtered = len(self.filtered_issues)
        
        if total == filtered:
            self.count_label.setText(f"{total} problemas")
        else:
            self.count_label.setText(f"{filtered} de {total} problemas")
    
    def _update_statistics(self):
        """Actualiza las estadísticas mostradas."""
        if not self.issues:
            self.stats_label.setText("")
            return
        
        # Contar por severidad
        errors = len([i for i in self.issues if i.get("severity") == "error"])
        warnings = len([i for i in self.issues if i.get("severity") == "warning"])
        infos = len([i for i in self.issues if i.get("severity") == "info"])
        fixable = len([i for i in self.issues if i.get("fixable", False)])
        
        stats_text = f"Errores: {errors} | Advertencias: {warnings} | Info: {infos} | Reparables: {fixable}"
        self.stats_label.setText(stats_text)
    
    def _on_problem_selected(self):
        """Maneja la selección de un problema."""
        current_item = self.problems_tree.currentItem()
        if not current_item:
            self.current_issue = None
            self._update_details_panel(None)
            return
        
        # Obtener el problema almacenado
        issue = current_item.data(0, Qt.UserRole)
        if not issue:
            # Posiblemente es un grupo, no un problema individual
            self.current_issue = None
            self._update_details_panel(None)
            return
        
        self.current_issue = issue
        self._update_details_panel(issue)
        
        # Emitir señal
        self.problemSelected.emit(issue)
    
    def _on_problem_double_clicked(self, item, column):
        """Maneja el doble clic en un problema."""
        issue = item.data(0, Qt.UserRole)
        if issue:
            # Navegar a la página del problema
            self._navigate_to_problem(issue)
    
    def _update_details_panel(self, issue: Optional[Dict]):
        """
        Actualiza el panel de detalles con la información del problema.
        
        Args:
            issue: Problema seleccionado o None
        """
        if not issue:
            self.checkpoint_label.setText("Checkpoint: -")
            self.severity_label.setText("Severidad: -")
            self.page_label.setText("Página: -")
            self.fixable_label.setText("Reparable: -")
            self.description_text.clear()
            self.fix_description_text.clear()
            self.navigate_btn.setEnabled(False)
            self.fix_btn.setEnabled(False)
            return
        
        # Actualizar información básica
        checkpoint = issue.get("checkpoint", "Desconocido")
        self.checkpoint_label.setText(f"Checkpoint: {checkpoint}")
        
        severity = issue.get("severity", "").title()
        self.severity_label.setText(f"Severidad: {severity}")
        
        page = issue.get("page", "")
        if isinstance(page, int):
            page_text = str(page + 1)  # Convertir a base 1
        elif page == "all":
            page_text = "Todo el documento"
        else:
            page_text = str(page)
        self.page_label.setText(f"Página: {page_text}")
        
        fixable = "Sí" if issue.get("fixable", False) else "No"
        self.fixable_label.setText(f"Reparable: {fixable}")
        
        # Actualizar descripciones
        description = issue.get("description", "Sin descripción")
        self.description_text.setText(description)
        
        fix_description = issue.get("fix_description", "Sin información de reparación")
        self.fix_description_text.setText(fix_description)
        
        # Habilitar/deshabilitar botones
        can_navigate = (page != "all" and page is not None)
        self.navigate_btn.setEnabled(can_navigate)
        
        can_fix = issue.get("fixable", False)
        self.fix_btn.setEnabled(can_fix)
    
    def _on_navigate_clicked(self):
        """Maneja el clic en el botón de navegación."""
        if self.current_issue:
            self._navigate_to_problem(self.current_issue)
    
    def _on_fix_clicked(self):
        """Maneja el clic en el botón de reparación."""
        if self.current_issue:
            self.fixRequested.emit(self.current_issue)
    
    def _navigate_to_problem(self, issue: Dict):
        """
        Navega a la página del problema.
        
        Args:
            issue: Problema al que navegar
        """
        page = issue.get("page")
        if page is not None and page != "all":
            try:
                if isinstance(page, int):
                    self.navigateToPage.emit(page)
                else:
                    page_num = int(page)
                    self.navigateToPage.emit(page_num)
            except (ValueError, TypeError):
                logger.error(f"Número de página inválido: {page}")
    
    def _show_context_menu(self, position):
        """Muestra el menú contextual."""
        item = self.problems_tree.itemAt(position)
        if item:
            issue = item.data(0, Qt.UserRole)
            if issue:
                # Actualizar estado de las acciones
                page = issue.get("page")
                can_navigate = (page != "all" and page is not None)
                self.action_navigate.setEnabled(can_navigate)
                
                can_fix = issue.get("fixable", False)
                self.action_fix.setEnabled(can_fix)
                
                # Mostrar menú
                self.context_menu.exec_(self.problems_tree.mapToGlobal(position))
    
    def _copy_description(self):
        """Copia la descripción del problema al portapapeles."""
        if self.current_issue:
            from PySide6.QtGui import QGuiApplication
            
            description = self.current_issue.get("description", "")
            clipboard = QGuiApplication.clipboard()
            clipboard.setText(description)
            
            self.status_label.setText("Descripción copiada al portapapeles")
            QTimer.singleShot(3000, lambda: self.status_label.setText("Listo"))
    
    def _mark_as_reviewed(self):
        """Marca el problema como revisado."""
        if self.current_issue:
            # Agregar marca de revisado al problema
            self.current_issue["reviewed"] = True
            
            # Actualizar visualización
            current_item = self.problems_tree.currentItem()
            if current_item:
                font = current_item.font(2)
                font.setStrikeOut(True)
                current_item.setFont(2, font)
                
                # Cambiar color a gris
                for col in range(self.problems_tree.columnCount()):
                    current_item.setForeground(col, QColor(128, 128, 128))
            
            self.status_label.setText("Problema marcado como revisado")
    
    # Métodos de filtro
    def _on_severity_filter_changed(self, text):
        """Maneja cambios en el filtro de severidad."""
        filter_map = {
            "Todos": "all",
            "Errores": "error",
            "Advertencias": "warning",
            "Información": "info"
        }
        self.severity_filter = filter_map.get(text, "all")
        self._apply_filters()
    
    def _on_checkpoint_filter_changed(self, text):
        """Maneja cambios en el filtro de checkpoint."""
        self.checkpoint_filter = "all" if text == "Todos" else text
        self._apply_filters()
    
    def _on_fixable_filter_changed(self, text):
        """Maneja cambios en el filtro de reparable."""
        filter_map = {
            "Todos": "all",
            "Sí": "yes",
            "No": "no"
        }
        self.fixable_filter = filter_map.get(text, "all")
        self._apply_filters()
    
    def _on_search_changed(self, text):
        """Maneja cambios en el texto de búsqueda."""
        self.search_text = text
        # Usar timer para búsqueda diferida
        self.search_timer.stop()
        self.search_timer.start(300)
    
    def _clear_filters(self):
        """Limpia todos los filtros."""
        self.severity_combo.setCurrentIndex(0)  # "Todos"
        self.checkpoint_combo.setCurrentIndex(0)  # "Todos"
        self.fixable_combo.setCurrentIndex(0)  # "Todos"
        self.search_field.clear()
        
        self.severity_filter = "all"
        self.checkpoint_filter = "all"
        self.fixable_filter = "all"
        self.search_text = ""
        
        self._apply_filters()
        self.status_label.setText("Filtros limpiados")
    
    def _export_issues(self):
        """Exporta los problemas a un archivo."""
        if not self.filtered_issues:
            QMessageBox.information(self, "Sin problemas", "No hay problemas para exportar.")
            return
        
        from PySide6.QtWidgets import QFileDialog
        import json
        import csv
        from datetime import datetime
        
        # Seleccionar archivo
        file_path, selected_filter = QFileDialog.getSaveFileName(
            self,
            "Exportar problemas",
            f"problemas_accesibilidad_{datetime.now().strftime('%Y%m%d_%H%M%S')}",
            "Archivos JSON (*.json);;Archivos CSV (*.csv);;Archivos de texto (*.txt)"
        )
        
        if not file_path:
            return
        
        try:
            if "JSON" in selected_filter:
                with open(file_path, 'w', encoding='utf-8') as f:
                    json.dump(self.filtered_issues, f, indent=2, ensure_ascii=False)
                    
            elif "CSV" in selected_filter:
                with open(file_path, 'w', newline='', encoding='utf-8') as f:
                    writer = csv.writer(f)
                    # Encabezados
                    writer.writerow(["Checkpoint", "Severidad", "Descripción", "Página", "Reparable", "Solución"])
                    
                    # Datos
                    for issue in self.filtered_issues:
                        writer.writerow([
                            issue.get("checkpoint", ""),
                            issue.get("severity", ""),
                            issue.get("description", ""),
                            issue.get("page", ""),
                            "Sí" if issue.get("fixable", False) else "No",
                            issue.get("fix_description", "")
                        ])
                        
            else:  # Texto plano
                with open(file_path, 'w', encoding='utf-8') as f:
                    f.write("INFORME DE PROBLEMAS DE ACCESIBILIDAD\n")
                    f.write("=" * 50 + "\n\n")
                    f.write(f"Fecha: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}\n")
                    f.write(f"Total de problemas: {len(self.filtered_issues)}\n\n")
                    
                    for i, issue in enumerate(self.filtered_issues, 1):
                        f.write(f"{i}. {issue.get('checkpoint', 'N/A')} - {issue.get('severity', '').upper()}\n")
                        f.write(f"   Descripción: {issue.get('description', '')}\n")
                        f.write(f"   Página: {issue.get('page', 'N/A')}\n")
                        f.write(f"   Reparable: {'Sí' if issue.get('fixable', False) else 'No'}\n")
                        if issue.get('fix_description'):
                            f.write(f"   Solución: {issue.get('fix_description', '')}\n")
                        f.write("\n")
            
            self.status_label.setText(f"Problemas exportados a {file_path}")
            QTimer.singleShot(5000, lambda: self.status_label.setText("Listo"))
            
        except Exception as e:
            logger.error(f"Error al exportar problemas: {e}")
            QMessageBox.critical(self, "Error", f"Error al exportar problemas:\n{str(e)}")
    
    def get_current_issue(self) -> Optional[Dict]:
        """Obtiene el problema actualmente seleccionado."""
        return self.current_issue
    
    def select_issue_by_checkpoint(self, checkpoint: str):
        """
        Selecciona el primer problema de un checkpoint específico.
        
        Args:
            checkpoint: ID del checkpoint
        """
        for issue in self.filtered_issues:
            if issue.get("checkpoint") == checkpoint:
                # Buscar el item en el árbol
                root = self.problems_tree.invisibleRootItem()
                for i in range(root.childCount()):
                    group_item = root.child(i)
                    if group_item.text(1) == checkpoint:
                        if group_item.childCount() > 0:
                            first_issue_item = group_item.child(0)
                            self.problems_tree.setCurrentItem(first_issue_item)
                            self.problems_tree.scrollToItem(first_issue_item)
                            return
                break
    
    def highlight_issues_by_type(self, issue_type: str):
        """
        Resalta problemas de un tipo específico.
        
        Args:
            issue_type: Tipo de problema a resaltar
        """
        # Esta funcionalidad podría expandirse para resaltar visualmente
        # ciertos tipos de problemas en la lista
        pass