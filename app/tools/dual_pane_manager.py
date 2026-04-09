import os
import shutil
from dataclasses import dataclass, field
from datetime import datetime
from typing import Optional

from PyQt6.QtCore import QDir, QEvent, QFileInfo, QModelIndex, QSettings, Qt, QTimer
from PyQt6.QtGui import QKeySequence, QShortcut, QStandardItem, QStandardItemModel
from PyQt6.QtWidgets import (
    QAbstractItemView,
    QApplication,
    QCheckBox,
    QComboBox,
    QDialog,
    QDialogButtonBox,
    QFileIconProvider,
    QFormLayout,
    QFrame,
    QGridLayout,
    QHBoxLayout,
    QInputDialog,
    QLabel,
    QLineEdit,
    QMainWindow,
    QMessageBox,
    QProgressDialog,
    QPushButton,
    QScrollArea,
    QSplitter,
    QTabWidget,
    QToolButton,
    QTreeView,
    QVBoxLayout,
    QWidget,
)

try:
    from send2trash import send2trash
except Exception:
    send2trash = None


class NavigableTreeView(QTreeView):
    def __init__(self, parent=None):
        super().__init__(parent)
        self.on_enter_dir = None
        self.on_go_parent = None

    def keyPressEvent(self, event):
        key = event.key()
        if key in (Qt.Key.Key_Return, Qt.Key.Key_Enter):
            index = self.currentIndex()
            if index.isValid() and callable(self.on_enter_dir):
                self.on_enter_dir(index)
            return
        if key == Qt.Key.Key_Backspace:
            if callable(self.on_go_parent):
                self.on_go_parent()
            return
        super().keyPressEvent(event)


class PaneWidgets:
    """파일 관리자 패널 위젯 컨테이너"""
    def __init__(self, container: QFrame, drive_combo: QComboBox, path_edit: QLineEdit,
                 filter_edit: QLineEdit, tab_widget: 'QTabWidget', status_label: QLabel,
                 name: str, current_path: str = '', all_entries: list = None):
        self.container = container
        self.drive_combo = drive_combo
        self.path_edit = path_edit
        self.filter_edit = filter_edit
        self.tab_widget = tab_widget
        self.status_label = status_label
        self.name = name
        self.current_path = current_path
        self.all_entries = all_entries if all_entries is not None else []
        self.tab_models: dict = {}  # 탭 인덱스 -> 모델 매핑


class DualPaneManager(QWidget):
    tool_key = 'dual_pane_manager'
    tool_name = '🗂️ 파일 관리자'
    window_title = '파일 관리자'
    singleton = True
    enabled = True

    ACTIVE_EDIT_STYLE = (
        'QLineEdit {'
        'background-color: #EAF3FF;'
        'border: 1px solid #9FC3FF;'
        'border-radius: 8px;'
        'padding: 6px 8px;'
        '}'
    )
    INACTIVE_EDIT_STYLE = (
        'QLineEdit {'
        'background-color: #FFFFFF;'
        'border: 1px solid #D8DEE6;'
        'border-radius: 8px;'
        'padding: 6px 8px;'
        '}'
    )

    def __init__(self, parent=None):
        super().__init__(parent)
        self.left_pane: Optional[PaneWidgets] = None
        self.right_pane: Optional[PaneWidgets] = None
        self.active_pane: Optional[PaneWidgets] = None
        self.shortcuts = []
        self.icon_provider = QFileIconProvider()
        self.bookmarks: list[str] = []
        self.settings = QSettings('DeskUtil', 'DualPaneManager')
        self._build_ui()
        self._setup_shortcuts()
        self._load_bookmarks()
        self._restore_last_folders()

    def _build_ui(self):
        root = QVBoxLayout(self)
        root.setContentsMargins(10, 10, 10, 10)
        root.setSpacing(8)

        # Bookmark toolbar
        bookmark_layout = QHBoxLayout()
        bookmark_layout.setSpacing(6)

        # 즐겨찾기 헤더 (+ 아이콘 버튼 포함)
        header_layout = QHBoxLayout()
        header_layout.setSpacing(4)
        bookmark_label = QLabel('⭐ 즐겨찾기')
        bookmark_label.setStyleSheet('font-weight: bold; color: #4A5568; font-size: 13px;')
        header_layout.addWidget(bookmark_label)

        # + 아이콘 버튼 (즐겨찾기 추가)
        add_fav_btn = QToolButton()
        add_fav_btn.setText('✚')
        add_fav_btn.setToolTip('현재 폴더를 즐겨찾기에 추가')
        add_fav_btn.setStyleSheet(
            'QToolButton {'
            'background-color: #EAF3FF;'
            'border: 1px solid #9FC3FF;'
            'border-radius: 10px;'
            'padding: 2px 6px;'
            'font-size: 12px;'
            'color: #007AFF;'
            'font-weight: bold;'
            '}'
            'QToolButton:hover { background-color: #D8E9FF; }'
        )
        add_fav_btn.clicked.connect(self._add_bookmark_current)
        header_layout.addWidget(add_fav_btn)
        header_layout.addSpacing(8)
        bookmark_layout.addLayout(header_layout)

        self.bookmark_container = QHBoxLayout()
        self.bookmark_container.setSpacing(6)
        bookmark_layout.addLayout(self.bookmark_container, 1)
        bookmark_layout.addStretch()

        root.addLayout(bookmark_layout)

        self.splitter = QSplitter(Qt.Orientation.Horizontal)
        self.splitter.setChildrenCollapsible(False)
        root.addWidget(self.splitter, 1)

        self.left_pane = self._create_pane('Left')
        self.right_pane = self._create_pane('Right')

        self.splitter.addWidget(self.left_pane.container)
        self.splitter.addWidget(self.right_pane.container)
        self.splitter.setSizes([1, 1])

        self._set_active_pane(self.left_pane)
        QTimer.singleShot(0, self._ensure_equal_split)

        # Bottom toolbar with shortcut buttons
        bottom_bar = QFrame()
        bottom_bar.setStyleSheet('background-color: #F7FAFC; border-top: 1px solid #D8DEE6; border-radius: 0 0 10px 10px;')
        bottom_layout = QHBoxLayout(bottom_bar)
        bottom_layout.setContentsMargins(12, 8, 12, 8)
        bottom_layout.setSpacing(8)

        # Button style helper
        def create_shortcut_btn(text, shortcut, handler):
            btn = QPushButton(text)
            btn.setStyleSheet(
                'QPushButton {'
                'background-color: #FFFFFF;'
                'border: 1px solid #D8DEE6;'
                'border-radius: 6px;'
                'padding: 6px 12px;'
                'font-size: 12px;'
                'color: #4A5568;'
                '}'
                'QPushButton:hover {'
                'background-color: #EAF3FF;'
                'border-color: #9FC3FF;'
                'color: #007AFF;'
                '}'
            )
            btn.setToolTip(shortcut)
            btn.clicked.connect(handler)
            return btn

        # Add shortcut buttons
        bottom_layout.addWidget(create_shortcut_btn('📋 복사 (F5)', 'F5', self._on_f5))
        bottom_layout.addWidget(create_shortcut_btn('📁 이동 (F6)', 'F6', self._on_f6))
        bottom_layout.addWidget(create_shortcut_btn('📂 새 폴더 (F7)', 'F7', self._on_f7))
        bottom_layout.addWidget(create_shortcut_btn('🗑️ 삭제 (F8)', 'F8', self._on_f8))
        bottom_layout.addWidget(create_shortcut_btn('🔄 패널 전환 (Tab)', 'Tab', self._on_tab_switch))
        bottom_layout.addWidget(create_shortcut_btn('🔍 검색 (Ctrl+F)', 'Ctrl+F', self._on_ctrl_f))
        bottom_layout.addWidget(create_shortcut_btn('ℹ️ 속성 (Alt+Enter)', 'Alt+Enter', self._on_alt_enter))
        bottom_layout.addStretch()

        root.addWidget(bottom_bar)

    def _ensure_equal_split(self):
        half = max(1, self.width() // 2)
        self.splitter.setSizes([half, half])

    def resizeEvent(self, event):
        super().resizeEvent(event)
        self._ensure_equal_split()

    def _create_pane(self, pane_name: str) -> PaneWidgets:
        container = QFrame()
        container.setObjectName(f'{pane_name.lower()}Pane')
        container.setStyleSheet(
            'QFrame {'
            'background: #FFFFFF;'
            'border: 1px solid #DCE2EA;'
            'border-radius: 10px;'
            '}'
        )

        layout = QVBoxLayout(container)
        layout.setContentsMargins(10, 10, 10, 10)
        layout.setSpacing(8)

        top_row = QHBoxLayout()
        top_row.setSpacing(8)
        drive_combo = QComboBox()
        drive_combo.setMinimumWidth(120)
        path_edit = QLineEdit()
        path_edit.setPlaceholderText('경로를 입력하고 Enter를 누르세요')
        path_edit.setStyleSheet(self.INACTIVE_EDIT_STYLE)

        top_row.addWidget(drive_combo, 0)
        top_row.addWidget(path_edit, 1)
        layout.addLayout(top_row)

        # Filter row
        filter_row = QHBoxLayout()
        filter_row.setSpacing(8)
        filter_label = QLabel('🔍')
        filter_edit = QLineEdit()
        filter_edit.setPlaceholderText('파일 필터 (Ctrl+F)')
        filter_edit.setStyleSheet(
            'QLineEdit {'
            'background-color: #F8FAFC;'
            'border: 1px solid #D8DEE6;'
            'border-radius: 6px;'
            'padding: 4px 8px;'
            'font-size: 12px;'
            '}'
        )
        filter_row.addWidget(filter_label, 0)
        filter_row.addWidget(filter_edit, 1)
        layout.addLayout(filter_row)

        # 탭 추가 버튼
        tab_btn_row = QHBoxLayout()
        tab_btn_row.setSpacing(8)
        tab_btn_row.addStretch()
        add_tab_btn = QPushButton('+ 새 탭')
        add_tab_btn.setFixedHeight(28)
        add_tab_btn.setMinimumWidth(70)
        add_tab_btn.setStyleSheet(
            'QPushButton {'
            'background: #007AFF;'
            'color: white;'
            'border: none;'
            'border-radius: 4px;'
            'padding: 4px 8px;'
            'font-weight: 600;'
            'font-size: 11px;'
            '}'
            'QPushButton:hover {'
            'background: #0056D3;'
            '}'
        )
        tab_btn_row.addWidget(add_tab_btn)
        layout.addLayout(tab_btn_row)

        # 탭 위젯으로 파일 리스트 관리
        tab_widget = QTabWidget()
        tab_widget.setObjectName(f'{pane_name.lower()}Tabs')
        tab_widget.setTabPosition(QTabWidget.TabPosition.North)
        tab_widget.setDocumentMode(True)
        tab_widget.setMovable(True)
        tab_widget.setTabsClosable(True)
        # 시그널은 PaneWidgets 생성 후에 연결

        layout.addWidget(tab_widget, 1)

        status_label = QLabel('선택: 0개 | 총 용량: 0 B')
        status_label.setStyleSheet('color: #4A5568; padding: 2px 4px;')
        layout.addWidget(status_label)

        pane = PaneWidgets(
            container=container,
            drive_combo=drive_combo,
            path_edit=path_edit,
            filter_edit=filter_edit,
            tab_widget=tab_widget,
            status_label=status_label,
            name=pane_name,
            current_path='',
            all_entries=[],
        )

        self._populate_drives(pane)
        self._connect_pane_signals(pane)
        filter_edit.textChanged.connect(lambda text, p=pane: self._apply_filter(p, text))

        # 탭 변경 시그널 연결 (pane 객체 직접 전달)
        tab_widget.currentChanged.connect(lambda idx, p=pane: self._on_pane_tab_changed(p, idx))

        # 탭 추가 버튼 시그널 연결
        add_tab_btn.clicked.connect(lambda _checked, p=pane: self._add_file_tab(p, QDir.homePath(), '새 탭'))

        # 기본 탭 추가
        self._add_file_tab(pane, QDir.homePath(), '홈')
        return pane

    def _populate_drives(self, pane: PaneWidgets):
        pane.drive_combo.blockSignals(True)
        pane.drive_combo.clear()
        for drive in QDir.drives():
            path = drive.absoluteFilePath()
            pane.drive_combo.addItem(path, path)
        pane.drive_combo.blockSignals(False)

    def _connect_pane_signals(self, pane: PaneWidgets):
        pane.drive_combo.currentIndexChanged.connect(lambda _idx, p=pane: self._on_drive_changed(p))
        pane.path_edit.returnPressed.connect(lambda p=pane: self._on_path_entered(p))

        pane.path_edit.installEventFilter(self)

    def _get_current_tree_view(self, pane: PaneWidgets) -> NavigableTreeView | None:
        """현재 활성 탭의 tree_view 반환"""
        current_widget = pane.tab_widget.currentWidget()
        if isinstance(current_widget, NavigableTreeView):
            return current_widget
        return None

    def _add_file_tab(self, pane: PaneWidgets, path: str, label: str = None) -> int:
        """파일 탭 추가"""
        # 새 트리 뷰 생성
        tree_view = NavigableTreeView()
        tree_view.setAlternatingRowColors(True)
        tree_view.setStyleSheet(
            'QTreeView {'
            'border: 1px solid #DCE2EA;'
            'border-radius: 8px;'
            'alternate-background-color: #F7FAFE;'
            'selection-background-color: #D8E9FF;'
            '}'
        )
        tree_view.setSortingEnabled(True)
        tree_view.setRootIsDecorated(False)
        tree_view.setItemsExpandable(False)
        tree_view.setUniformRowHeights(True)
        tree_view.setSelectionMode(QAbstractItemView.SelectionMode.ExtendedSelection)
        tree_view.setColumnWidth(0, 280)
        tree_view.setColumnWidth(1, 90)
        tree_view.setColumnWidth(2, 130)
        tree_view.setColumnWidth(3, 170)

        # 모델 설정
        model = QStandardItemModel()
        model.setHorizontalHeaderLabels(['이름', '크기', '유형', '수정일'])
        tree_view.setModel(model)

        # 시그널 연결
        tree_view.doubleClicked.connect(lambda index, p=pane: self._on_item_double_clicked(p, index))
        tree_view.on_enter_dir = lambda index, p=pane: self._on_item_double_clicked(p, index)
        tree_view.on_go_parent = lambda p=pane: self._go_parent(p)
        tree_view.installEventFilter(self)
        tree_view.viewport().installEventFilter(self)

        selection_model = tree_view.selectionModel()
        if selection_model:
            selection_model.selectionChanged.connect(lambda _sel, _desel, p=pane: self._update_status(p))

        # 탭 추가
        tab_label = label or os.path.basename(path) or path
        tab_index = pane.tab_widget.addTab(tree_view, tab_label)
        pane.tab_models[tab_index] = model

        # 디렉토리 로드
        self._load_directory_to_model(model, path)

        return tab_index

    def _on_pane_tab_changed(self, pane: PaneWidgets, index: int):
        """패널 탭 변경 시 처리"""
        if not pane:
            return
        if index >= 0 and index in pane.tab_models:
            # 현재 경로 업데이트
            tree_view = pane.tab_widget.widget(index)
            if isinstance(tree_view, NavigableTreeView):
                model = pane.tab_models[index]
                # 첫 번째 아이템에서 경로 추출 (parent_path 저장용)
                pass  # TODO: 경로 추적 로직
        self._update_status(pane)

    def _close_file_tab(self, pane: PaneWidgets, index: int):
        """파일 탭 닫기"""
        if pane.tab_widget.count() <= 1:
            return  # 마지막 탭은 닫지 않음
        pane.tab_widget.removeTab(index)
        # 모델 정리
        if index in pane.tab_models:
            del pane.tab_models[index]

    def _format_file_size(self, size: int) -> str:
        units = ['B', 'KB', 'MB', 'GB', 'TB']
        value = float(size)
        for unit in units:
            if value < 1024 or unit == units[-1]:
                return f'{value:.0f} {unit}' if unit == 'B' else f'{value:.1f} {unit}'
            value /= 1024.0
        return f'{size} B'

    def _get_file_type(self, path: str) -> str:
        if os.path.isdir(path):
            return '폴더'
        ext = os.path.splitext(path)[1].lower()
        type_map = {
            '.exe': '실행 파일', '.dll': 'DLL', '.py': 'Python', '.txt': '텍스트',
            '.pdf': 'PDF', '.doc': '문서', '.docx': '문서', '.xls': '스프레드시트',
            '.xlsx': '스프레드시트', '.ppt': '프레젠테이션', '.pptx': '프레젠테이션',
            '.jpg': '이미지', '.jpeg': '이미지', '.png': '이미지', '.gif': '이미지',
            '.bmp': '이미지', '.mp3': '오디오', '.mp4': '비디오', '.avi': '비디오',
            '.zip': '압축 파일', '.rar': '압축 파일', '.7z': '압축 파일',
        }
        return type_map.get(ext, f'{ext[1:].upper() if ext else "파일"} 파일') if ext else '파일'

    def _restore_last_folders(self):
        """Restore last opened folders from QSettings"""
        left_path = self.settings.value('last_left_folder', QDir.homePath())
        right_path = self.settings.value('last_right_folder', QDir.homePath())

        if os.path.isdir(left_path):
            self._load_directory(self.left_pane, left_path)
        if os.path.isdir(right_path):
            self._load_directory(self.right_pane, right_path)

    def _save_last_folders(self):
        """Save current folder paths to QSettings"""
        if self.left_pane and self.left_pane.current_path:
            self.settings.setValue('last_left_folder', self.left_pane.current_path)
        if self.right_pane and self.right_pane.current_path:
            self.settings.setValue('last_right_folder', self.right_pane.current_path)

    def _load_directory_to_model(self, model: QStandardItemModel, path: str) -> list:
        """특정 모델에 디렉토리 내용 로드"""
        if not path or not os.path.isdir(path):
            return []

        normalized = os.path.abspath(path)
        model.removeRows(0, model.rowCount())
        all_entries = []

        try:
            entries = os.listdir(normalized)
        except PermissionError:
            QMessageBox.warning(self, '접근 거부', f'폴더에 접근할 수 없습니다:\n{normalized}')
            return []
        except Exception as e:
            QMessageBox.warning(self, '오류', f'폴더 읽기 오류:\n{e}')
            return []

        # Add parent directory entry
        parent_item = QStandardItem('..')
        parent_item.setData(normalized, Qt.ItemDataRole.UserRole)
        parent_item.setData('parent', Qt.ItemDataRole.UserRole + 1)
        parent_item.setFlags(parent_item.flags() & ~Qt.ItemFlag.ItemIsEditable)
        parent_item.setIcon(self.icon_provider.icon(QFileIconProvider.IconType.Folder))
        model.appendRow([parent_item, QStandardItem(''), QStandardItem('상위 폴더'), QStandardItem('')])

        # Store all entries for filtering
        sorted_entries = sorted(entries, key=lambda x: (not os.path.isdir(os.path.join(normalized, x)), x.lower()))

        for entry in sorted_entries:
            full_path = os.path.join(normalized, entry)
            try:
                stat = os.stat(full_path)
                is_dir = os.path.isdir(full_path)

                name_item = QStandardItem(entry)
                name_item.setData(full_path, Qt.ItemDataRole.UserRole)
                name_item.setData('dir' if is_dir else 'file', Qt.ItemDataRole.UserRole + 1)
                name_item.setFlags(name_item.flags() & ~Qt.ItemFlag.ItemIsEditable)

                # Set icon based on file type
                if is_dir:
                    name_item.setIcon(self.icon_provider.icon(QFileIconProvider.IconType.Folder))
                else:
                    file_info = QFileInfo(full_path)
                    name_item.setIcon(self.icon_provider.icon(file_info))

                if is_dir:
                    size_item = QStandardItem('')
                    type_item = QStandardItem('폴더')
                else:
                    size_item = QStandardItem(self._format_file_size(stat.st_size))
                    type_item = QStandardItem(self._get_file_type(full_path))

                mtime = datetime.fromtimestamp(stat.st_mtime)
                date_item = QStandardItem(mtime.strftime('%Y-%m-%d %H:%M'))

                all_entries.append({
                    'name': entry,
                    'path': full_path,
                    'is_dir': is_dir,
                    'size': stat.st_size if not is_dir else 0,
                    'mtime': stat.st_mtime,
                })
                model.appendRow([name_item, size_item, type_item, date_item])
            except OSError:
                continue

        return all_entries

    def _load_directory(self, pane: PaneWidgets, path: str):
        """현재 활성 탭에 디렉토리 로드"""
        if not path or not os.path.isdir(path):
            return False

        normalized = os.path.abspath(path)
        pane.current_path = normalized
        pane.path_edit.setText(normalized)

        # Save current folder paths
        self._save_last_folders()

        # Update drive combo
        drive_text = os.path.splitdrive(normalized)[0]
        if drive_text:
            drive_text = drive_text + '\\'
            combo_index = pane.drive_combo.findData(drive_text)
            if combo_index >= 0:
                pane.drive_combo.blockSignals(True)
                pane.drive_combo.setCurrentIndex(combo_index)
                pane.drive_combo.blockSignals(False)

        # 현재 활성 탭의 모델 가져와서 로드
        current_index = pane.tab_widget.currentIndex()
        if current_index >= 0 and current_index in pane.tab_models:
            model = pane.tab_models[current_index]
            pane.all_entries = self._load_directory_to_model(model, path)
            # 탭 이름 업데이트
            pane.tab_widget.setTabText(current_index, os.path.basename(path) or path)
            # 필터 적용 및 상태 업데이트
            self._apply_filter(pane, pane.filter_edit.text())
            self._update_status(pane)
        return True

    def _apply_filter(self, pane: PaneWidgets, filter_text: str):
        """현재 활성 탭의 필터 적용"""
        tree_view = self._get_current_tree_view(pane)
        if not tree_view:
            return

        model = tree_view.model()
        if not isinstance(model, QStandardItemModel):
            return

        if not filter_text.strip():
            # Show all
            for row in range(model.rowCount()):
                tree_view.setRowHidden(row, QModelIndex(), False)
            return

        filter_lower = filter_text.lower()
        for row in range(model.rowCount()):
            item = model.item(row, 0)
            if not item:
                continue
            name = item.text().lower()
            # Always show parent directory
            is_hidden = item.data(Qt.ItemDataRole.UserRole + 1) != 'parent' and filter_lower not in name
            tree_view.setRowHidden(row, QModelIndex(), is_hidden)

    def eventFilter(self, watched, event):
        if event.type() in (QEvent.Type.MouseButtonPress, QEvent.Type.FocusIn):
            left_tree = self._get_current_tree_view(self.left_pane) if self.left_pane else None
            right_tree = self._get_current_tree_view(self.right_pane) if self.right_pane else None

            if self.left_pane and watched in ([left_tree, left_tree.viewport() if left_tree else None, self.left_pane.path_edit]):
                self._set_active_pane(self.left_pane)
            elif self.right_pane and watched in ([right_tree, right_tree.viewport() if right_tree else None, self.right_pane.path_edit]):
                self._set_active_pane(self.right_pane)
        return super().eventFilter(watched, event)

    def _set_active_pane(self, pane: PaneWidgets):
        self.active_pane = pane
        for target in (self.left_pane, self.right_pane):
            if not target:
                continue
            target.path_edit.setStyleSheet(self.ACTIVE_EDIT_STYLE if target is pane else self.INACTIVE_EDIT_STYLE)

    def _on_drive_changed(self, pane: PaneWidgets):
        drive_path = pane.drive_combo.currentData()
        if drive_path:
            self._load_directory(pane, drive_path)

    def _on_path_entered(self, pane: PaneWidgets):
        self._load_directory(pane, pane.path_edit.text().strip())

    def _on_item_double_clicked(self, pane: PaneWidgets, index):
        if not index.isValid():
            return

        tree_view = self._get_current_tree_view(pane)
        if not tree_view:
            return

        model = tree_view.model()
        if not isinstance(model, QStandardItemModel):
            return

        item = model.itemFromIndex(index)
        if not item:
            return

        path = item.data(Qt.ItemDataRole.UserRole)
        item_type = item.data(Qt.ItemDataRole.UserRole + 1)

        if item_type == 'parent' or (path and os.path.isdir(path)):
            if item_type == 'parent':
                self._go_parent(pane)
            else:
                self._load_directory(pane, path)

    def _go_parent(self, pane: PaneWidgets):
        if not pane.current_path:
            return
        parent_path = os.path.dirname(pane.current_path.rstrip('\\/'))
        if parent_path and os.path.isdir(parent_path):
            self._load_directory(pane, parent_path)

    def _get_selected_paths(self, pane: PaneWidgets) -> list:
        paths = []
        tree_view = self._get_current_tree_view(pane)
        if not tree_view:
            return paths

        selection_model = tree_view.selectionModel()
        if not selection_model:
            return paths

        model = tree_view.model()
        if not isinstance(model, QStandardItemModel):
            return paths

        for index in selection_model.selectedRows(0):
            item = model.itemFromIndex(index)
            if not item:
                continue
            path = item.data(Qt.ItemDataRole.UserRole)
            item_type = item.data(Qt.ItemDataRole.UserRole + 1)
            if path and item_type != 'parent':
                paths.append(path)
        return paths

    def _update_status(self, pane: PaneWidgets):
        paths = self._get_selected_paths(pane)
        total_size = 0
        for path in paths:
            if os.path.isfile(path):
                try:
                    total_size += os.path.getsize(path)
                except OSError:
                    pass

        pane.status_label.setText(f'선택: {len(paths)}개 | 총 용량: {self._format_file_size(total_size)}')

    def _get_target_pane(self) -> Optional[PaneWidgets]:
        if self.active_pane is self.left_pane:
            return self.right_pane
        if self.active_pane is self.right_pane:
            return self.left_pane
        return None

    def _unique_destination_path(self, target_dir: str, name: str) -> str:
        candidate = os.path.join(target_dir, name)
        if not os.path.exists(candidate):
            return candidate

        stem, ext = os.path.splitext(name)
        suffix = 1
        while True:
            numbered = f'{stem} ({suffix}){ext}'
            candidate = os.path.join(target_dir, numbered)
            if not os.path.exists(candidate):
                return candidate
            suffix += 1

    def _validate_copy_move_source(self, src: str, target_dir: str) -> Optional[str]:
        src_abs = os.path.abspath(src)
        target_abs = os.path.abspath(target_dir)

        src_parent = os.path.abspath(os.path.dirname(src_abs))
        if src_parent == target_abs:
            return '원본과 동일한 폴더입니다.'

        if os.path.isdir(src_abs):
            try:
                if os.path.commonpath([src_abs, target_abs]) == src_abs:
                    return '폴더를 자기 자신 또는 하위 폴더로 작업할 수 없습니다.'
            except ValueError:
                pass

        return None

    def _create_progress_dialog(self, title: str, maximum: int) -> QProgressDialog:
        dlg = QProgressDialog(title, '취소', 0, maximum, self)
        dlg.setWindowTitle(title)
        dlg.setWindowModality(Qt.WindowModality.WindowModal)
        dlg.setMinimumDuration(0)
        dlg.setAutoClose(True)
        dlg.setAutoReset(True)
        return dlg

    def _copy_paths(self, paths: list, target_dir: str):
        copied = 0
        errors = []
        progress = self._create_progress_dialog('복사 중...', len(paths))
        for i, src in enumerate(paths, start=1):
            progress.setValue(i - 1)
            if progress.wasCanceled():
                errors.append('사용자가 작업을 취소했습니다.')
                break

            guard_error = self._validate_copy_move_source(src, target_dir)
            if guard_error:
                errors.append(f'{src}: {guard_error}')
                continue

            try:
                dest = self._unique_destination_path(target_dir, os.path.basename(src))
                if os.path.isdir(src):
                    shutil.copytree(src, dest)
                else:
                    shutil.copy2(src, dest)
                copied += 1
            except Exception as exc:
                errors.append(f'{src}: {exc}')
        progress.setValue(len(paths))
        return copied, errors

    def _move_paths(self, paths: list, target_dir: str):
        moved = 0
        errors = []
        progress = self._create_progress_dialog('이동 중...', len(paths))
        for i, src in enumerate(paths, start=1):
            progress.setValue(i - 1)
            if progress.wasCanceled():
                errors.append('사용자가 작업을 취소했습니다.')
                break

            guard_error = self._validate_copy_move_source(src, target_dir)
            if guard_error:
                errors.append(f'{src}: {guard_error}')
                continue

            try:
                dest = self._unique_destination_path(target_dir, os.path.basename(src))
                shutil.move(src, dest)
                moved += 1
            except Exception as exc:
                errors.append(f'{src}: {exc}')
        progress.setValue(len(paths))
        return moved, errors

    def _delete_paths(self, paths: list):
        deleted = 0
        errors = []
        progress = self._create_progress_dialog('삭제 중...', len(paths))
        for i, path in enumerate(paths, start=1):
            progress.setValue(i - 1)
            if progress.wasCanceled():
                errors.append('사용자가 작업을 취소했습니다.')
                break

            try:
                if send2trash:
                    send2trash(path)
                else:
                    if os.path.isdir(path):
                        shutil.rmtree(path)
                    else:
                        os.remove(path)
                deleted += 1
            except Exception as exc:
                errors.append(f'{path}: {exc}')
        progress.setValue(len(paths))
        return deleted, errors

    def _show_result(self, title: str, success_count: int, errors: list):
        if errors:
            detail = '\n'.join(errors[:5])
            if len(errors) > 5:
                detail += f'\n... {len(errors) - 5} more'
            QMessageBox.warning(
                self,
                title,
                f'완료: {success_count}개\n실패: {len(errors)}개\n\n{detail}',
            )
            return
        QMessageBox.information(self, title, f'완료: {success_count}개')

    def _setup_shortcuts(self):
        self.shortcuts = [
            (QShortcut(QKeySequence('F5'), self), self._on_f5),
            (QShortcut(QKeySequence('F6'), self), self._on_f6),
            (QShortcut(QKeySequence('F7'), self), self._on_f7),
            (QShortcut(QKeySequence('F8'), self), self._on_f8),
            (QShortcut(QKeySequence('Tab'), self), self._on_tab_switch),
            (QShortcut(QKeySequence('Ctrl+F'), self), self._on_ctrl_f),
            (QShortcut(QKeySequence('Alt+Return'), self), self._on_alt_enter),
            (QShortcut(QKeySequence('Alt+Enter'), self), self._on_alt_enter),
        ]
        for shortcut, _handler in self.shortcuts:
            shortcut.setContext(Qt.ShortcutContext.WidgetWithChildrenShortcut)

        for i in range(len(self.shortcuts)):
            self.shortcuts[i][0].activated.connect(self.shortcuts[i][1])

    def _active_pane_name(self) -> str:
        return self.active_pane.name if self.active_pane else 'Unknown'

    def _refresh_panes(self):
        for pane in (self.left_pane, self.right_pane):
            if pane and pane.current_path:
                self._load_directory(pane, pane.current_path)

    def _on_f5(self):
        print(f'F5 pressed on {self._active_pane_name()} pane')
        if not self.active_pane:
            return
        target_pane = self._get_target_pane()
        if not target_pane:
            return

        paths = self._get_selected_paths(self.active_pane)
        if not paths:
            QMessageBox.information(self, '복사', '복사할 파일/폴더를 선택해주세요.')
            return

        target_dir = target_pane.current_path
        if not target_dir:
            return

        copied, errors = self._copy_paths(paths, target_dir)
        self._refresh_panes()
        self._show_result('복사 결과', copied, errors)

    def _on_f6(self):
        print(f'F6 pressed on {self._active_pane_name()} pane')
        if not self.active_pane:
            return
        target_pane = self._get_target_pane()
        if not target_pane:
            return

        paths = self._get_selected_paths(self.active_pane)
        if not paths:
            QMessageBox.information(self, '이동', '이동할 파일/폴더를 선택해주세요.')
            return

        target_dir = target_pane.current_path
        if not target_dir:
            return

        moved, errors = self._move_paths(paths, target_dir)
        self._refresh_panes()
        self._show_result('이동 결과', moved, errors)

    def _on_f7(self):
        print(f'F7 pressed on {self._active_pane_name()} pane')
        if not self.active_pane:
            return

        target_dir = self.active_pane.current_path
        if not target_dir:
            return

        folder_name, ok = QInputDialog.getText(self, '새 폴더', '폴더 이름을 입력하세요:')
        if not ok:
            return
        folder_name = folder_name.strip()
        if not folder_name:
            QMessageBox.information(self, '새 폴더', '폴더 이름이 비어 있습니다.')
            return

        new_dir = os.path.join(target_dir, folder_name)
        if os.path.exists(new_dir):
            QMessageBox.warning(self, '새 폴더', '이미 같은 이름의 항목이 존재합니다.')
            return

        try:
            os.makedirs(new_dir, exist_ok=False)
        except Exception as exc:
            QMessageBox.critical(self, '새 폴더', f'폴더 생성 실패:\n{exc}')
            return

        self._refresh_panes()
        QMessageBox.information(self, '새 폴더', f'생성 완료: {folder_name}')

    def _on_f8(self):
        print(f'F8 pressed on {self._active_pane_name()} pane')
        if not self.active_pane:
            return

        paths = self._get_selected_paths(self.active_pane)
        if not paths:
            QMessageBox.information(self, '삭제', '삭제할 파일/폴더를 선택해주세요.')
            return

        delete_mode_message = '(휴지통으로 이동)'
        if not send2trash:
            delete_mode_message = '(send2trash 미설치: 영구 삭제)'

        confirm = QMessageBox.question(
            self,
            '삭제 확인',
            (
                f'선택한 {len(paths)}개 항목을 삭제하시겠습니까?\n'
                f'{delete_mode_message}\n'
                '(이 작업은 되돌릴 수 없습니다.)'
            ),
            QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No,
            QMessageBox.StandardButton.No,
        )
        if confirm != QMessageBox.StandardButton.Yes:
            return

        deleted, errors = self._delete_paths(paths)
        self._refresh_panes()
        self._show_result('삭제 결과', deleted, errors)

    def _on_tab_switch(self):
        target = self.right_pane if self.active_pane is self.left_pane else self.left_pane
        self._set_active_pane(target)
        target.tree_view.setFocus()
        print(f'Tab pressed on {self._active_pane_name()} pane')

    def _on_ctrl_f(self):
        if not self.active_pane:
            return
        self.active_pane.filter_edit.setFocus()
        self.active_pane.filter_edit.selectAll()
        print(f'Ctrl+F pressed on {self._active_pane_name()} pane')

    def _on_alt_enter(self):
        print(f'Alt+Enter pressed on {self._active_pane_name()} pane')
        if not self.active_pane:
            return
        paths = self._get_selected_paths(self.active_pane)
        if not paths:
            QMessageBox.information(self, '파일 속성', '파일이나 폴더를 선택해주세요.')
            return
        if len(paths) > 1:
            QMessageBox.information(self, '파일 속성', '하나의 파일이나 폴더만 선택해주세요.')
            return
        self._show_file_properties(paths[0])

    def _show_file_properties(self, path: str):
        dialog = QDialog(self)
        dialog.setWindowTitle('파일 속성')
        dialog.setFixedSize(400, 350)
        dialog.setStyleSheet(
            'QDialog { background-color: #FFFFFF; }'
            'QLabel { color: #4A5568; }'
            'QLineEdit { background-color: #F7FAFC; border: 1px solid #D8DEE6; border-radius: 6px; padding: 6px; }'
        )

        layout = QFormLayout(dialog)
        layout.setContentsMargins(20, 20, 20, 20)
        layout.setSpacing(12)

        # File name
        name_edit = QLineEdit(os.path.basename(path))
        name_edit.setReadOnly(True)
        layout.addRow('이름:', name_edit)

        # Full path
        path_edit = QLineEdit(path)
        path_edit.setReadOnly(True)
        layout.addRow('전체 경로:', path_edit)

        # Type
        is_dir = os.path.isdir(path)
        type_edit = QLineEdit('폴더' if is_dir else self._get_file_type(path))
        type_edit.setReadOnly(True)
        layout.addRow('유형:', type_edit)

        try:
            stat = os.stat(path)
            # Size
            if is_dir:
                size_text = self._format_directory_size(path)
            else:
                size_text = self._format_file_size(stat.st_size)
            size_edit = QLineEdit(size_text)
            size_edit.setReadOnly(True)
            layout.addRow('크기:', size_edit)

            # Dates
            created = datetime.fromtimestamp(stat.st_ctime).strftime('%Y-%m-%d %H:%M:%S')
            modified = datetime.fromtimestamp(stat.st_mtime).strftime('%Y-%m-%d %H:%M:%S')
            accessed = datetime.fromtimestamp(stat.st_atime).strftime('%Y-%m-%d %H:%M:%S')

            layout.addRow('생성일:', QLabel(created))
            layout.addRow('수정일:', QLabel(modified))
            layout.addRow('접근일:', QLabel(accessed))

            # Attributes
            attr_layout = QHBoxLayout()
            read_only = QCheckBox('읽기 전용')
            read_only.setChecked(not os.access(path, os.W_OK))
            read_only.setEnabled(False)
            hidden = QCheckBox('숨김')
            hidden.setChecked(os.path.basename(path).startswith('.') if os.name != 'nt' else bool(stat.st_file_attributes & 2 if hasattr(stat, 'st_file_attributes') else False))
            hidden.setEnabled(False)
            attr_layout.addWidget(read_only)
            attr_layout.addWidget(hidden)
            attr_layout.addStretch()
            layout.addRow('속성:', attr_layout)
        except OSError as e:
            layout.addRow('오류:', QLabel(f'정보를 읽을 수 없습니다: {e}'))

        # OK button
        buttons = QDialogButtonBox(QDialogButtonBox.StandardButton.Ok)
        buttons.accepted.connect(dialog.accept)
        layout.addRow(buttons)

        dialog.exec()

    def _format_directory_size(self, path: str) -> str:
        try:
            total_size = 0
            total_files = 0
            total_dirs = 0
            for dirpath, dirnames, filenames in os.walk(path):
                total_dirs += len(dirnames)
                total_files += len(filenames)
                for f in filenames:
                    fp = os.path.join(dirpath, f)
                    try:
                        total_size += os.path.getsize(fp)
                    except OSError:
                        pass
            return f'{self._format_file_size(total_size)} ({total_files}개 파일, {total_dirs}개 폴더)'
        except Exception:
            return '계산할 수 없음'

    def _load_bookmarks(self):
        # Load bookmarks from QSettings
        self.bookmarks = self.settings.value('bookmarks', [], list)
        self._update_bookmark_ui()

    def _save_bookmarks(self):
        # Save bookmarks to QSettings
        self.settings.setValue('bookmarks', self.bookmarks)

    def _update_bookmark_ui(self):
        # Clear existing widgets
        while self.bookmark_container.count():
            item = self.bookmark_container.takeAt(0)
            widget = item.widget()
            if widget:
                widget.deleteLater()

        # Add bookmark items with delete button
        for bookmark_path in self.bookmarks:
            if not os.path.exists(bookmark_path):
                continue

            # 개별 즐겨찾기 컨테이너
            item_layout = QHBoxLayout()
            item_layout.setSpacing(2)
            item_layout.setContentsMargins(0, 0, 0, 0)

            # 폴더명 버튼 (클릭 시 이동)
            btn = QToolButton()
            btn.setText(os.path.basename(bookmark_path) or bookmark_path)
            btn.setToolTip(bookmark_path)
            btn.setStyleSheet(
                'QToolButton {'
                'background-color: #F7FAFC;'
                'border: 1px solid #D8DEE6;'
                'border-radius: 6px;'
                'padding: 4px 8px;'
                'font-size: 12px;'
                '}'
                'QToolButton:hover { background-color: #EAF3FF; }'
            )
            btn.clicked.connect(lambda checked, p=bookmark_path: self._go_to_bookmark(p))
            item_layout.addWidget(btn)

            # 삭제 버튼 (X)
            del_btn = QToolButton()
            del_btn.setText('✕')
            del_btn.setToolTip('즐겨찾기에서 삭제')
            del_btn.setStyleSheet(
                'QToolButton {'
                'background-color: transparent;'
                'border: none;'
                'padding: 2px 4px;'
                'font-size: 10px;'
                'color: #9CA3AF;'
                '}'
                'QToolButton:hover {'
                'color: #EF4444;'
                'background-color: #FEE2E2;'
                'border-radius: 4px;'
                '}'
            )
            del_btn.clicked.connect(lambda checked, p=bookmark_path: self._remove_bookmark(p))
            item_layout.addWidget(del_btn)

            # 컨테이너를 위젯으로 감싸서 추가
            item_widget = QWidget()
            item_widget.setLayout(item_layout)
            self.bookmark_container.addWidget(item_widget)

        self.bookmark_container.addStretch()

    def _add_bookmark_current(self):
        if not self.active_pane or not self.active_pane.current_path:
            QMessageBox.information(self, '즐겨찾기', '먼저 폴더를 선택해주세요.')
            return

        path = self.active_pane.current_path
        if path in self.bookmarks:
            QMessageBox.information(self, '즐겨찾기', '이미 즐겨찾기에 추가된 폴더입니다.')
            return

        self.bookmarks.append(path)
        self._update_bookmark_ui()
        self._save_bookmarks()
        QMessageBox.information(self, '즐겨찾기', f'추가되었습니다:\n{path}')

    def _remove_bookmark(self, path: str):
        if path in self.bookmarks:
            self.bookmarks.remove(path)
            self._update_bookmark_ui()
            self._save_bookmarks()

    def _go_to_bookmark(self, path: str):
        if not os.path.exists(path):
            QMessageBox.warning(self, '즐겨찾기', f'폴더를 찾을 수 없습니다:\n{path}')
            self._remove_bookmark(path)
            return

        if self.active_pane:
            self._load_directory(self.active_pane, path)


if __name__ == '__main__':
    app = QApplication([])
    window = QMainWindow()
    window.setWindowTitle('Dual Pane Manager Test')
    window.resize(1400, 900)

    widget = DualPaneManager()
    window.setCentralWidget(widget)
    window.show()

    app.exec()
