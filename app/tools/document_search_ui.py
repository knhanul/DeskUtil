import sys
import os
from datetime import datetime
from pathlib import Path
import ctypes
from ctypes import wintypes

def resolve_windows_junction(path: str) -> str:
    """Windows 재분석점(junction)을 실제 경로로 변환"""
    try:
        # Try to read the junction target using Windows API
        kernel32 = ctypes.windll.kernel32
        
        # Open the directory with FILE_FLAG_OPEN_REPARSE_POINT
        handle = kernel32.CreateFileW(
            path,
            0,  # GENERIC_READ
            0,  # FILE_SHARE_READ | FILE_SHARE_WRITE | FILE_SHARE_DELETE
            None,
            3,  # OPEN_EXISTING
            0x00200000 | 0x02000000,  # FILE_FLAG_OPEN_REPARSE_POINT | FILE_FLAG_BACKUP_SEMANTICS
            None
        )
        
        print(f"[DocumentSearch] CreateFileW handle={handle} for path={path}")
        
        if handle == -1 or handle == 0xFFFFFFFF:
            err = kernel32.GetLastError()
            print(f"[DocumentSearch] CreateFileW failed, error={err}")
            return path
        
        try:
            # Use GetFinalPathNameByHandleW to get the actual path
            buf = ctypes.create_unicode_buffer(32767)
            result = kernel32.GetFinalPathNameByHandleW(handle, buf, 32767, 0)
            
            print(f"[DocumentSearch] GetFinalPathNameByHandleW result={result}")
            
            if result > 0 and result < 32767:
                actual_path = buf.value
                print(f"[DocumentSearch] resolved path={actual_path!r}")
                # Remove \\?\ prefix if present
                if actual_path.startswith('\\\\?\\'):
                    actual_path = actual_path[4:]
                return actual_path
            else:
                print(f"[DocumentSearch] GetFinalPathNameByHandleW returned invalid result")
        finally:
            kernel32.CloseHandle(handle)
    except Exception as e:
        print(f"[DocumentSearch] resolve_windows_junction exception: {e}")
    
    # Fallback: try using readlink which works in Python 3.10+
    try:
        target = os.readlink(path)
        print(f"[DocumentSearch] os.readlink returned: {target!r}")
        # If relative path, make it absolute
        if not os.path.isabs(target):
            target = os.path.join(os.path.dirname(path), target)
        return target
    except (OSError, ValueError, NotImplementedError) as e:
        print(f"[DocumentSearch] os.readlink failed: {e}")
    
    return path


def list_files_win32(directory: str) -> list[str]:
    """Windows FindFirstFile API를 사용해 파일 목록 가져오기 (OneDrive 가상화 파일 포함)"""
    files = []
    kernel32 = ctypes.windll.kernel32
    
    # WIN32_FIND_DATA structure
    class WIN32_FIND_DATA(ctypes.Structure):
        _fields_ = [
            ("dwFileAttributes", wintypes.DWORD),
            ("ftCreationTime", wintypes.FILETIME),
            ("ftLastAccessTime", wintypes.FILETIME),
            ("ftLastWriteTime", wintypes.FILETIME),
            ("nFileSizeHigh", wintypes.DWORD),
            ("nFileSizeLow", wintypes.DWORD),
            ("dwReserved0", wintypes.DWORD),
            ("dwReserved1", wintypes.DWORD),
            ("cFileName", wintypes.WCHAR * 260),
            ("cAlternateFileName", wintypes.WCHAR * 14),
        ]
    
    search_path = os.path.join(directory, "*")
    find_data = WIN32_FIND_DATA()
    
    handle = kernel32.FindFirstFileW(search_path, ctypes.byref(find_data))
    if handle == -1:
        return files
    
    try:
        while True:
            filename = find_data.cFileName
            if filename not in ('.', '..'):
                files.append(filename)
            if not kernel32.FindNextFileW(handle, ctypes.byref(find_data)):
                break
    finally:
        kernel32.FindClose(handle)
    
    return files


try:
    from PySide6.QtCore import QDir, QItemSelectionModel, QModelIndex, QSize, Qt, QThread, Signal
    from PySide6.QtGui import QAction, QColor, QFileSystemModel, QFont, QPixmap
    from PySide6.QtWidgets import (
        QAbstractItemView,
        QApplication,
        QCheckBox,
        QFrame,
        QGridLayout,
        QHBoxLayout,
        QHeaderView,
        QLayout,
        QLabel,
        QLineEdit,
        QListWidget,
        QListWidgetItem,
        QMainWindow,
        QMessageBox,
        QPushButton,
        QScrollArea,
        QSizePolicy,
        QSplitter,
        QTextEdit,
        QTreeView,
        QTreeWidget,
        QTreeWidgetItem,
        QVBoxLayout,
        QWidget,
    )
except ImportError:
    from PyQt6.QtCore import QDir, QModelIndex, QSize, Qt, QThread, pyqtSignal
    from PyQt6.QtGui import QAction, QColor, QFileSystemModel, QFont, QPixmap
    from PyQt6.QtWidgets import (
        QAbstractItemView,
        QApplication,
        QCheckBox,
        QFrame,
        QGridLayout,
        QHBoxLayout,
        QHeaderView,
        QLayout,
        QLabel,
        QLineEdit,
        QListWidget,
        QListWidgetItem,
        QMainWindow,
        QMessageBox,
        QPushButton,
        QScrollArea,
        QSizePolicy,
        QSplitter,
        QTextEdit,
        QTreeView,
        QTreeWidget,
        QTreeWidgetItem,
        QVBoxLayout,
        QWidget,
    )

    Signal = pyqtSignal

try:
    SelectionFlagSelect = QItemSelectionModel.SelectionFlag.Select
except NameError:
    SelectionFlagSelect = None


class CheckableFileSystemModel(QFileSystemModel):
    def __init__(self, parent=None) -> None:
        super().__init__(parent)
        self._checked_paths: dict[str, Qt.CheckState] = {}

    def flags(self, index: QModelIndex):
        base_flags = super().flags(index)
        if not index.isValid():
            return base_flags
        if self.isDir(index):
            return base_flags | Qt.ItemFlag.ItemIsUserCheckable
        return base_flags

    def data(self, index: QModelIndex, role: int = Qt.ItemDataRole.DisplayRole):
        if index.isValid() and index.column() == 0 and self.isDir(index) and role == Qt.ItemDataRole.CheckStateRole:
            return self._checked_paths.get(os.path.normpath(self.filePath(index)), Qt.CheckState.Unchecked)
        return super().data(index, role)

    def setData(self, index: QModelIndex, value, role: int = Qt.ItemDataRole.EditRole):
        if index.isValid() and index.column() == 0 and self.isDir(index) and role == Qt.ItemDataRole.CheckStateRole:
            check_state = Qt.CheckState(value)
            target_path = self.filePath(index)
            self._set_check_state_recursive(target_path, check_state)
            self._refresh_parent_states(Path(target_path).parent)
            self.dataChanged.emit(index, index, [Qt.ItemDataRole.CheckStateRole])
            return True
        return super().setData(index, value, role)

    def _set_check_state_recursive(self, folder_path: str, check_state: Qt.CheckState) -> None:
        normalized = os.path.normpath(folder_path)
        if check_state == Qt.CheckState.Unchecked:
            self._checked_paths = {
                path: state for path, state in self._checked_paths.items() if path != normalized and not path.startswith(normalized + os.sep)
            }
        else:
            self._checked_paths[normalized] = check_state
            root_index = self.index(normalized)
            if root_index.isValid():
                self._apply_children_state(root_index, check_state)

    def _apply_children_state(self, parent_index: QModelIndex, check_state: Qt.CheckState) -> None:
        row_count = self.rowCount(parent_index)
        for row in range(row_count):
            child_index = self.index(row, 0, parent_index)
            if not child_index.isValid() or not self.isDir(child_index):
                continue
            child_path = os.path.normpath(self.filePath(child_index))
            self._checked_paths[child_path] = check_state
            self._apply_children_state(child_index, check_state)
            self.dataChanged.emit(child_index, child_index, [Qt.ItemDataRole.CheckStateRole])

    def _refresh_parent_states(self, parent_path: Path) -> None:
        while parent_path and str(parent_path) and parent_path != parent_path.parent:
            parent_index = self.index(str(parent_path))
            if not parent_index.isValid() or not self.isDir(parent_index):
                parent_path = parent_path.parent
                continue

            child_states: list[Qt.CheckState] = []
            for row in range(self.rowCount(parent_index)):
                child_index = self.index(row, 0, parent_index)
                if child_index.isValid() and self.isDir(child_index):
                    child_states.append(self._checked_paths.get(os.path.normpath(self.filePath(child_index)), Qt.CheckState.Unchecked))

            normalized = os.path.normpath(str(parent_path))
            if child_states and all(state == Qt.CheckState.Checked for state in child_states):
                self._checked_paths[normalized] = Qt.CheckState.Checked
            elif any(state != Qt.CheckState.Unchecked for state in child_states):
                self._checked_paths[normalized] = Qt.CheckState.PartiallyChecked
            else:
                self._checked_paths.pop(normalized, None)

            self.dataChanged.emit(parent_index, parent_index, [Qt.ItemDataRole.CheckStateRole])
            parent_path = parent_path.parent

    def checked_folder_paths(self) -> list[str]:
        checked = [path for path, state in self._checked_paths.items() if state == Qt.CheckState.Checked]
        checked.sort(key=lambda item: (len(Path(item).parts), item))
        collapsed: list[str] = []
        for path in checked:
            normalized = os.path.normpath(path)
            if any(normalized == base or normalized.startswith(base + os.sep) for base in collapsed):
                continue
            collapsed.append(normalized)
        return collapsed


current_dir = Path(__file__).parent
project_root = current_dir.parent.parent
if str(project_root) not in sys.path:
    sys.path.insert(0, str(project_root))

from doc_search.extractors import get_extractor


def format_datetime(timestamp: float) -> str:
    try:
        return datetime.fromtimestamp(timestamp).strftime('%Y-%m-%d %H:%M')
    except (OverflowError, OSError, ValueError):
        return '-'


def format_file_size(size_bytes: int) -> str:
    size = float(size_bytes)
    units = ['B', 'KB', 'MB', 'GB', 'TB']
    for unit in units:
        if size < 1024 or unit == units[-1]:
            if unit == 'B':
                return f'{int(size)} {unit}'
            return f'{size:.1f} {unit}'
        size /= 1024
    return f'{int(size_bytes)} B'


class CustomResultWidget(QWidget):
    def __init__(
        self,
        file_data: dict[str, str],
        snippet_text: str,
        include_snippet: bool = True,
        parent=None,
    ) -> None:
        super().__init__(parent)
        self.file_name = file_data.get('file_name', '')
        self.file_path = file_data.get('file_path', '')
        self.preview_text = file_data.get('preview', '')
        self.include_snippet = include_snippet

        root = QVBoxLayout(self)
        root.setContentsMargins(0, 0, 0, 0)
        root.setSpacing(0)

        card = QFrame()
        card.setObjectName("resultItemCard")
        card.setProperty("selected", False)
        self.card = card
        if include_snippet:
            card_layout = QGridLayout(card)
            card_layout.setContentsMargins(10, 8, 10, 8)
            card_layout.setHorizontalSpacing(12)
            card_layout.setVerticalSpacing(8)

            meta_labels = [
                f"경로: {self.file_path}",
                f"종류: {file_data.get('file_kind', '-')}",
                f"크기: {file_data.get('file_size', '-')}",
                f"생성: {file_data.get('created_at', '-')}",
                f"수정: {file_data.get('modified_at', '-')}",
            ]
            for col, text in enumerate(meta_labels):
                label = QLabel(text)
                label.setObjectName("resultMetaLabel")
                label.setToolTip(self.file_path)
                card_layout.addWidget(label, 0, col)

            snippet_label = QLabel(snippet_text or self.preview_text)
            snippet_label.setObjectName("resultSnippetLabel")
            snippet_label.setWordWrap(True)
            snippet_label.setTextInteractionFlags(Qt.TextInteractionFlag.TextSelectableByMouse)
            card_layout.addWidget(snippet_label, 1, 0, 1, len(meta_labels))
        else:
            card_layout = QHBoxLayout(card)
            card_layout.setContentsMargins(10, 10, 10, 10)
            card_layout.setSpacing(12)
            labels = [
                f"경로: {self.file_path}",
                f"종류: {file_data.get('file_kind', '-')}",
                f"크기: {file_data.get('file_size', '-')}",
                f"생성: {file_data.get('created_at', '-')}",
                f"수정: {file_data.get('modified_at', '-')}",
            ]
            for index, text in enumerate(labels):
                label = QLabel(text)
                label.setObjectName("resultMetaLabel")
                label.setToolTip(self.file_path)
                label.setTextInteractionFlags(Qt.TextInteractionFlag.TextSelectableByMouse)
                if index == 0:
                    label.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Preferred)
                card_layout.addWidget(label)

        root.addWidget(card)

    def set_selected(self, selected: bool) -> None:
        self.card.setProperty("selected", selected)
        self.card.style().unpolish(self.card)
        self.card.style().polish(self.card)
        self.card.update()



class SearchWorker(QThread):
    result_found = Signal(str, str, str, str, str, str, str, str)
    progress_changed = Signal(int, int, str)
    search_finished = Signal(int, int, bool)
    search_failed = Signal(str)

    def __init__(self, folder_paths: list[str], query: str, allowed_extensions: set[str], parent=None) -> None:
        super().__init__(parent)
        self.folder_paths = [os.path.normpath(path) for path in folder_paths]
        self.query = query.strip().lower()
        self._is_cancelled = False
        self.supported_extensions = allowed_extensions

    def cancel(self) -> None:
        self._is_cancelled = True

    def run(self) -> None:
        try:
            print(f"[DocumentSearch] worker started folders={self.folder_paths} extensions={sorted(self.supported_extensions)} query={self.query!r}")
            files = self._collect_files()
            total = len(files)
            found = 0
            print(f"[DocumentSearch] collected_files={total}")

            for index, file_path in enumerate(files, start=1):
                if self._is_cancelled:
                    print(f"[DocumentSearch] cancelled scanned={index - 1} found={found}")
                    self.search_finished.emit(found, index - 1, True)
                    return

                self.progress_changed.emit(index, total, file_path)
                if index <= 5 or index % 50 == 0:
                    print(f"[DocumentSearch] scanning {index}/{total}: {file_path}")
                text = self._extract_text(file_path)
                if not text:
                    continue

                if self.query in text.lower():
                    found += 1
                    snippet = self._build_snippet(text)
                    stats = os.stat(file_path)
                    extension = Path(file_path).suffix.lower().lstrip('.') or 'file'
                    self.result_found.emit(
                        os.path.basename(file_path),
                        file_path,
                        snippet,
                        text[:5000],
                        format_datetime(stats.st_ctime),
                        format_datetime(stats.st_mtime),
                        format_file_size(stats.st_size),
                        extension.upper(),
                    )

            print(f"[DocumentSearch] finished scanned={total} found={found}")
            self.search_finished.emit(found, total, False)
        except Exception as exc:
            print(f"[DocumentSearch] failed: {exc}")
            self.search_failed.emit(str(exc))

    def _collect_files(self) -> list[str]:
        file_paths: list[str] = []
        visited: set[str] = set()
        for folder_path in self.folder_paths:
            normalized_root = os.path.normpath(folder_path)
            print(f"[DocumentSearch] walking folder: {normalized_root}")
            
            # Try the original path first
            paths_to_try = [normalized_root]
            
            # If folder appears empty, try OneDrive equivalents
            folder_name = Path(normalized_root).name
            folder_name_lower = folder_name.lower()
            
            # Map of known folder names to possible OneDrive subfolder names
            onedrive_name_map = {
                'documents': ['Documents', '문서'],
                '문서': ['Documents', '문서'],
                'desktop': ['Desktop', '바탕 화면'],
                '바탕 화면': ['Desktop', '바탕 화면'],
                'pictures': ['Pictures', '사진'],
                '사진': ['Pictures', '사진'],
            }
            
            if folder_name_lower in onedrive_name_map or folder_name in onedrive_name_map:
                subfolder_names = onedrive_name_map.get(folder_name_lower, onedrive_name_map.get(folder_name, []))
                home = str(Path.home())
                # Find all OneDrive* directories in user home
                try:
                    onedrive_roots = [
                        os.path.join(home, entry.name)
                        for entry in os.scandir(home)
                        if entry.is_dir() and entry.name.lower().startswith('onedrive')
                    ]
                except OSError:
                    onedrive_roots = []
                
                for od_root in onedrive_roots:
                    for subfolder in subfolder_names:
                        candidate = os.path.join(od_root, subfolder)
                        if candidate not in paths_to_try:
                            paths_to_try.append(candidate)
                    # Also try the OneDrive root itself (some configs put files directly there)
                    if od_root not in paths_to_try:
                        paths_to_try.append(od_root)
            
            for try_path in paths_to_try:
                if try_path in visited:
                    continue
                    
                print(f"[DocumentSearch] trying path: {try_path}")
                
                if not os.path.exists(try_path):
                    print(f"[DocumentSearch] path does not exist: {try_path}")
                    continue
                if not os.path.isdir(try_path):
                    print(f"[DocumentSearch] path is not a directory: {try_path}")
                    continue
                
                # Check if this path has content via scandir
                try:
                    entries = list(os.scandir(try_path))
                    print(f"[DocumentSearch] scandir count={len(entries)}")
                    if len(entries) == 0:
                        print(f"[DocumentSearch] path is empty, trying next")
                        continue
                    for entry in entries[:5]:
                        print(f"[DocumentSearch] entry: {entry.name}")
                except Exception as e:
                    print(f"[DocumentSearch] scandir error: {e}")
                    continue
                
                # Found a path with content, use it
                visited.add(try_path)
                
                # Recursive collection using scandir
                try:
                    file_paths = self._collect_files_scandir(try_path, file_paths)
                    print(f"[DocumentSearch] after walk total={len(file_paths)}")
                    break  # Stop trying other paths for this folder
                except Exception as e:
                    print(f"[DocumentSearch] recursive collection error: {e}")
                    continue
            else:
                print(f"[DocumentSearch] all paths exhausted for {normalized_root}")
                
        return file_paths
    
    def _collect_files_scandir(self, root: str, file_paths: list[str]) -> list[str]:
        """os.scandir를 사용해 재귀적으로 파일 수집 (OneDrive 가상화 지원)"""
        try:
            for entry in os.scandir(root):
                if self._is_cancelled:
                    break
                try:
                    if entry.is_dir(follow_symlinks=False):
                        # Recurse into subdirectory
                        file_paths = self._collect_files_scandir(entry.path, file_paths)
                    elif entry.is_file(follow_symlinks=False):
                        # Check file extension
                        ext = Path(entry.name).suffix.lower()
                        if ext in self.supported_extensions:
                            file_paths.append(entry.path)
                            if len(file_paths) <= 5:
                                print(f"[DocumentSearch] MATCH {ext!r} {entry.name!r}")
                except (OSError, PermissionError):
                    # Skip files/dirs we can't access
                    continue
        except (OSError, PermissionError) as e:
            print(f"[DocumentSearch] scandir error in {root}: {e}")
        
        return file_paths

    def _extract_text(self, file_path: str) -> str:
        extractor = get_extractor(file_path)
        if extractor is None:
            return ''
        try:
            return extractor.extract_text(file_path) or ''
        except Exception:
            return ''

    def _build_snippet(self, text: str) -> str:
        lower_text = text.lower()
        pos = lower_text.find(self.query)
        clean_text = text.replace('\n', ' ')
        if pos < 0:
            return clean_text[:180]
        start = max(0, pos - 60)
        end = min(len(clean_text), pos + len(self.query) + 100)
        snippet = clean_text[start:end].strip()
        if start > 0:
            snippet = '...' + snippet
        if end < len(clean_text):
            snippet = snippet + '...'
        return snippet


class DocumentSearchMainWindow(QMainWindow):
    def __init__(self) -> None:
        super().__init__()
        self.search_worker = None
        self.current_folder = ''
        self.current_preview_path = ''
        self._result_payloads: list[dict[str, str]] = []
        self._syncing_folder_checks = False
        self.supported_file_types = {
            '.txt': 'TXT',
            '.pdf': 'PDF',
            '.docx': 'DOCX',
            '.xlsx': 'XLSX',
            '.hwp': 'HWP',
            '.cell': 'CELL',
            '.hwpx': 'HWPX',
        }
        self.setWindowTitle("문서 통합 검색")
        self.resize(1440, 860)
        self.setMinimumSize(QSize(1180, 720))
        self._build_ui()
        self._apply_styles()
        self._connect_signals()

    def _build_ui(self) -> None:
        central = QWidget()
        self.setCentralWidget(central)

        root = QVBoxLayout(central)
        root.setContentsMargins(18, 18, 18, 18)
        root.setSpacing(14)

        self.vertical_splitter = QSplitter(Qt.Orientation.Vertical)
        self.vertical_splitter.setChildrenCollapsible(False)
        self.vertical_splitter.setHandleWidth(6)

        self.top_splitter = QSplitter(Qt.Orientation.Horizontal)
        self.top_splitter.setChildrenCollapsible(False)
        self.top_splitter.setHandleWidth(6)

        self.bottom_splitter = QSplitter(Qt.Orientation.Horizontal)
        self.bottom_splitter.setChildrenCollapsible(False)
        self.bottom_splitter.setHandleWidth(6)

        self.folder_panel = self._build_folder_panel()
        self.conditions_panel = self._build_conditions_panel()
        self.result_panel = self._build_result_panel()
        self.preview_panel = self._build_preview_panel()

        self.top_splitter.addWidget(self.folder_panel)
        self.top_splitter.addWidget(self.conditions_panel)
        self.bottom_splitter.addWidget(self.result_panel)
        self.bottom_splitter.addWidget(self.preview_panel)

        self.top_splitter.setStretchFactor(0, 48)
        self.top_splitter.setStretchFactor(1, 52)
        self.bottom_splitter.setStretchFactor(0, 58)
        self.bottom_splitter.setStretchFactor(1, 42)

        self.vertical_splitter.addWidget(self.top_splitter)
        self.vertical_splitter.addWidget(self.bottom_splitter)
        root.addWidget(self.vertical_splitter, 1)

        self._build_menu()

    def _build_folder_panel(self) -> QWidget:
        panel = QFrame()
        panel.setObjectName("panelCard")
        layout = QVBoxLayout(panel)
        layout.setContentsMargins(14, 14, 14, 14)
        layout.setSpacing(10)

        header = QLabel("폴더 탐색기")
        header.setObjectName("sectionTitle")
        layout.addWidget(header)

        self.folder_path_edit = QLineEdit()
        self.folder_path_edit.setReadOnly(True)
        self.folder_path_edit.setPlaceholderText("선택한 탐색 경로")
        self.folder_path_edit.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Fixed)
        layout.addWidget(self.folder_path_edit)

        self.folder_tree = QTreeWidget()
        self.folder_tree.setHeaderHidden(True)
        self.folder_tree.setRootIsDecorated(True)
        self.folder_tree.setIndentation(16)
        self.folder_tree.setUniformRowHeights(True)
        self.folder_tree.setAnimated(True)
        self.folder_tree.setEditTriggers(QAbstractItemView.EditTrigger.NoEditTriggers)
        self.folder_tree.setSelectionMode(QAbstractItemView.SelectionMode.SingleSelection)
        self.folder_tree.setHorizontalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAsNeeded)
        layout.addWidget(self.folder_tree, 1)

        self.checked_paths_label = QLabel("선택된 폴더 없음")
        self.checked_paths_label.setObjectName("metaLabel")
        layout.addWidget(self.checked_paths_label)
        self.checked_folder_paths_set: set[str] = set()
        self._populate_folder_tree()
        return panel

    def _build_conditions_panel(self) -> QWidget:
        panel = QFrame()
        panel.setObjectName("panelCard")
        layout = QVBoxLayout(panel)
        layout.setContentsMargins(14, 14, 14, 14)
        layout.setSpacing(12)

        header = QLabel("검색 조건")
        header.setObjectName("sectionTitle")
        layout.addWidget(header)

        query_label = QLabel("검색어")
        query_label.setObjectName("fieldLabel")
        layout.addWidget(query_label)
        self.search_input = QLineEdit()
        self.search_input.setPlaceholderText("검색어를 입력하세요")
        self.search_input.setClearButtonEnabled(True)
        layout.addWidget(self.search_input)

        type_label = QLabel("문서 파일 선택")
        type_label.setObjectName("fieldLabel")
        layout.addWidget(type_label)

        type_frame = QFrame()
        type_frame.setObjectName("innerCard")
        type_layout = QGridLayout(type_frame)
        type_layout.setContentsMargins(12, 12, 12, 12)
        type_layout.setHorizontalSpacing(10)
        type_layout.setVerticalSpacing(8)

        self.file_type_checkboxes = {}
        for index, (extension, label) in enumerate(self.supported_file_types.items()):
            checkbox = QCheckBox(label)
            checkbox.setChecked(True)
            self.file_type_checkboxes[extension] = checkbox
            type_layout.addWidget(checkbox, index // 3, index % 3)
        layout.addWidget(type_frame)

        self.include_snippet_checkbox = QCheckBox("검색 결과에 스니펫 포함")
        self.include_snippet_checkbox.setChecked(True)
        layout.addWidget(self.include_snippet_checkbox)

        controls = QHBoxLayout()
        controls.setSpacing(10)
        self.search_button = QPushButton("검색 시작")
        self.search_button.setFixedHeight(38)
        self.search_button.setMinimumWidth(96)

        self.cancel_button = QPushButton("취소")
        self.cancel_button.setFixedHeight(38)
        self.cancel_button.setMinimumWidth(84)
        self.cancel_button.setVisible(False)

        controls.addWidget(self.search_button)
        controls.addWidget(self.cancel_button)
        controls.addStretch()
        layout.addLayout(controls)

        self.conditions_summary_label = QLabel("모든 문서 형식이 검색 대상입니다.")
        self.conditions_summary_label.setObjectName("metaLabel")
        layout.addWidget(self.conditions_summary_label)

        layout.addStretch()
        self._update_conditions_summary()
        return panel

    def _build_result_panel(self) -> QWidget:
        panel = QFrame()
        panel.setObjectName("panelCard")
        layout = QVBoxLayout(panel)
        layout.setContentsMargins(14, 14, 14, 14)
        layout.setSpacing(12)

        header = QLabel("검색 결과")
        header.setObjectName("sectionTitle")
        layout.addWidget(header)

        header_card = QFrame()
        header_card.setObjectName("resultHeaderCard")
        header_grid = QGridLayout(header_card)
        header_grid.setContentsMargins(10, 8, 10, 8)
        header_grid.setHorizontalSpacing(12)
        header_grid.setVerticalSpacing(0)
        for col, text in enumerate(["경로", "종류", "크기", "생성일", "수정일"]):
            label = QLabel(text)
            label.setObjectName("resultHeaderLabel")
            header_grid.addWidget(label, 0, col)
        header_grid.setColumnStretch(0, 4)
        layout.addWidget(header_card)

        self.result_list = QListWidget()
        self.result_list.setObjectName("resultList")
        self.result_list.setSelectionMode(QAbstractItemView.SelectionMode.SingleSelection)
        self.result_list.setUniformItemSizes(False)
        self.result_list.setSpacing(8)
        self.result_list.currentItemChanged.connect(self._handle_selection_changed)
        layout.addWidget(self.result_list, 1)

        self.result_meta_label = QLabel("0개 문서")
        self.result_meta_label.setObjectName("metaLabel")
        layout.addWidget(self.result_meta_label)

        self.status_label = QLabel("폴더를 선택하고 검색어를 입력하세요.")
        self.status_label.setObjectName("metaLabel")
        layout.addWidget(self.status_label)
        return panel

    def _build_preview_panel(self) -> QWidget:
        panel = QFrame()
        panel.setObjectName("panelCard")
        layout = QVBoxLayout(panel)
        layout.setContentsMargins(14, 14, 14, 14)
        layout.setSpacing(10)

        self.preview_title = QLabel("미리보기")
        self.preview_title.setObjectName("sectionTitle")
        layout.addWidget(self.preview_title)

        self.preview_scroll = QScrollArea()
        self.preview_scroll.setWidgetResizable(True)
        self.preview_scroll.setFrameShape(QFrame.Shape.NoFrame)

        preview_container = QWidget()
        preview_layout = QVBoxLayout(preview_container)
        preview_layout.setContentsMargins(0, 0, 0, 0)
        preview_layout.setSpacing(10)

        self.preview_image = QLabel()
        self.preview_image.setObjectName("previewImage")
        self.preview_image.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.preview_image.setVisible(False)
        preview_layout.addWidget(self.preview_image)

        self.preview_text = QTextEdit()
        self.preview_text.setReadOnly(True)
        self.preview_text.setPlaceholderText("문서를 선택하면 미리보기가 표시됩니다.")
        self.preview_text.setPlainText("문서를 선택하면 미리보기가 표시됩니다.")
        preview_layout.addWidget(self.preview_text)

        self.preview_scroll.setWidget(preview_container)
        layout.addWidget(self.preview_scroll, 1)
        return panel

    def _load_dummy_results_for_test(self) -> None:
        self.result_list.clear()
        self._result_payloads.clear()
        dummy_rows = [
            {
                "file_name": "아파트 공동체 활성화 실행계획서.pdf",
                "file_path": r"C:\\Temp\\docs\\아파트 공동체 활성화 실행계획서.pdf",
                "snippet": "...이문 지역 공동체 프로그램 운영 계획...",
                "preview": "이문 지역 공동체 활성화를 위한 연간 실행 계획입니다. 주민 참여형 행사 및 예산 편성 기준이 포함되어 있습니다.",
                "created_at": "2026-04-01 10:20",
                "modified_at": "2026-04-03 14:05",
                "file_size": "2.1 MB",
                "file_kind": "PDF",
            },
            {
                "file_name": "주간업무보고_5월3주차.docx",
                "file_path": r"C:\\Temp\\docs\\주간업무보고_5월3주차.docx",
                "snippet": "...이문역 주변 상권 분석 결과 정리...",
                "preview": "주간업무보고에는 이문역 주변 상권 분석, 다음 주 실행 항목, 리스크 관리 체크리스트가 포함됩니다.",
                "created_at": "2026-03-28 09:11",
                "modified_at": "2026-04-04 08:42",
                "file_size": "384 KB",
                "file_kind": "DOCX",
            },
            {
                "file_name": "회의록_주민협의체.hwpx",
                "file_path": r"C:\\Temp\\docs\\회의록_주민협의체.hwpx",
                "snippet": "...이문 주민협의체 2차 회의 의결사항...",
                "preview": "2차 회의에서 논의된 의결사항은 주차 공간 개선안, 커뮤니티센터 야간 개방, 분기별 만족도 조사 시행입니다.",
                "created_at": "2026-04-02 13:00",
                "modified_at": "2026-04-02 17:33",
                "file_size": "1.0 MB",
                "file_kind": "HWPX",
            },
            {
                "file_name": "예산배정표.xlsx",
                "file_path": r"C:\\Temp\\docs\\예산배정표.xlsx",
                "snippet": "...이문 커뮤니티 프로그램 예산 항목...",
                "preview": "예산배정표에는 문화행사, 시설개선, 홍보비, 운영인력 항목별 분기 예산이 포함되어 있습니다.",
                "created_at": "2026-03-25 16:22",
                "modified_at": "2026-04-05 09:12",
                "file_size": "212 KB",
                "file_kind": "XLSX",
            },
        ]

        for row in dummy_rows:
            self._append_result(
                file_name=row["file_name"],
                file_path=row["file_path"],
                snippet=row["snippet"],
                preview=row["preview"],
                created_at=row["created_at"],
                modified_at=row["modified_at"],
                file_size=row["file_size"],
                file_kind=row["file_kind"],
            )

    def _connect_signals(self) -> None:
        self.search_button.clicked.connect(self._start_search)
        self.search_input.returnPressed.connect(self._start_search)
        self.cancel_button.clicked.connect(self._cancel_search)
        self.include_snippet_checkbox.toggled.connect(self._rerender_result_items)
        self.folder_tree.itemClicked.connect(lambda item, *_: self._handle_folder_tree_item_clicked(item))
        self.folder_tree.itemChanged.connect(self._handle_folder_item_changed)
        self.folder_tree.itemExpanded.connect(self._populate_folder_children)
        self.folder_tree.itemSelectionChanged.connect(self._sync_selected_folder)
        for checkbox in self.file_type_checkboxes.values():
            checkbox.toggled.connect(self._update_conditions_summary)

    def _build_menu(self) -> None:
        refresh_action = QAction("새로고침", self)
        refresh_action.setShortcut("F5")
        refresh_action.triggered.connect(self._start_search)

        clear_action = QAction("선택 해제", self)
        clear_action.setShortcut("Esc")
        clear_action.triggered.connect(self._clear_preview)

        toolbar = self.addToolBar("Quick Actions")
        toolbar.setMovable(False)
        toolbar.addAction(refresh_action)
        toolbar.addAction(clear_action)

    def _handle_folder_tree_item_clicked(self, item: QTreeWidgetItem) -> None:
        path = item.data(0, Qt.ItemDataRole.UserRole)
        node_type = item.data(0, Qt.ItemDataRole.UserRole + 1)
        if node_type == 'folder' and path:
            self._navigate_to_path(path)

    def _handle_folder_item_changed(self, item: QTreeWidgetItem, column: int) -> None:
        if column != 0 or self._syncing_folder_checks:
            return
        if item.data(0, Qt.ItemDataRole.UserRole + 1) != 'folder':
            return
        self._set_folder_check_state(item, item.checkState(0))
        self._update_checked_paths_label()

    def _sync_selected_folder(self) -> None:
        item = self.folder_tree.currentItem()
        if item is None:
            return
        path = item.data(0, Qt.ItemDataRole.UserRole)
        if not path:
            return
        self.current_folder = path
        self.folder_path_edit.setText(self.current_folder)
        self.folder_path_edit.setCursorPosition(0)

    def _populate_folder_tree(self) -> None:
        self.folder_tree.clear()

        favorites_item = QTreeWidgetItem(["즐겨찾기"])
        favorites_item.setData(0, Qt.ItemDataRole.UserRole + 1, 'group')

        this_pc_item = QTreeWidgetItem(["내 PC"])
        this_pc_item.setData(0, Qt.ItemDataRole.UserRole + 1, 'group')

        favorite_candidates = [
            Path.home() / 'Desktop',
            Path.home() / 'Documents',
            Path.home() / 'Downloads',
            Path.home() / 'Pictures',
        ]
        labels = {
            'Desktop': '바탕 화면',
            'Documents': '문서',
            'Downloads': '다운로드',
            'Pictures': '사진',
        }
        for folder in favorite_candidates:
            if folder.exists():
                item = self._create_folder_item(str(folder), labels.get(folder.name, folder.name))
                favorites_item.addChild(item)

        for drive in QDir.drives():
            drive_path = drive.absoluteFilePath()
            label = drive_path.rstrip('\\/') or drive_path
            item = self._create_folder_item(drive_path, label)
            this_pc_item.addChild(item)

        self.folder_tree.addTopLevelItem(favorites_item)
        self.folder_tree.addTopLevelItem(this_pc_item)
        favorites_item.setExpanded(True)
        this_pc_item.setExpanded(True)

    def _create_folder_item(self, folder_path: str, label: str | None = None) -> QTreeWidgetItem:
        item = QTreeWidgetItem([label or Path(folder_path).name or folder_path])
        normalized_path = os.path.normpath(folder_path)
        item.setData(0, Qt.ItemDataRole.UserRole, normalized_path)
        item.setData(0, Qt.ItemDataRole.UserRole + 1, 'folder')
        item.setFlags(item.flags() | Qt.ItemFlag.ItemIsUserCheckable)
        item.setCheckState(0, self._effective_check_state(normalized_path))
        if self._has_child_directories(folder_path):
            item.addChild(QTreeWidgetItem(["..."]))
        return item

    def _effective_check_state(self, folder_path: str) -> Qt.CheckState:
        normalized_path = os.path.normpath(folder_path)
        if normalized_path in self.checked_folder_paths_set:
            return Qt.CheckState.Checked
        if any(normalized_path.startswith(base + os.sep) for base in self.checked_folder_paths_set):
            return Qt.CheckState.Checked
        return Qt.CheckState.Unchecked

    def _has_child_directories(self, folder_path: str) -> bool:
        try:
            with os.scandir(folder_path) as entries:
                return any(entry.is_dir() for entry in entries)
        except OSError:
            return False

    def _populate_folder_children(self, item: QTreeWidgetItem) -> None:
        if item.data(0, Qt.ItemDataRole.UserRole + 1) != 'folder':
            return
        if item.childCount() == 1 and item.child(0).data(0, Qt.ItemDataRole.UserRole) is None:
            item.takeChildren()
            folder_path = item.data(0, Qt.ItemDataRole.UserRole)
            try:
                child_paths = sorted(
                    [entry.path for entry in os.scandir(folder_path) if entry.is_dir()],
                    key=lambda path: Path(path).name.lower(),
                )
            except OSError:
                child_paths = []
            for child_path in child_paths:
                child_item = self._create_folder_item(child_path)
                item.addChild(child_item)

    def _set_folder_check_state(self, item: QTreeWidgetItem, state: Qt.CheckState) -> None:
        self._syncing_folder_checks = True
        try:
            path = item.data(0, Qt.ItemDataRole.UserRole)
            normalized_path = os.path.normpath(path) if path else ''
            if normalized_path:
                if state == Qt.CheckState.Checked:
                    self.checked_folder_paths_set = {
                        checked_path for checked_path in self.checked_folder_paths_set if not normalized_path.startswith(checked_path + os.sep)
                    }
                    self.checked_folder_paths_set = {
                        checked_path for checked_path in self.checked_folder_paths_set if not checked_path.startswith(normalized_path + os.sep)
                    }
                    self.checked_folder_paths_set.add(normalized_path)
                else:
                    self.checked_folder_paths_set = {
                        checked_path for checked_path in self.checked_folder_paths_set if checked_path != normalized_path and not checked_path.startswith(normalized_path + os.sep)
                    }
            item.setCheckState(0, state)
            self._refresh_loaded_descendant_check_states(item)
        finally:
            self._syncing_folder_checks = False

    def _refresh_loaded_descendant_check_states(self, parent_item: QTreeWidgetItem) -> None:
        for index in range(parent_item.childCount()):
            child = parent_item.child(index)
            if child.data(0, Qt.ItemDataRole.UserRole + 1) != 'folder':
                continue
            child_path = child.data(0, Qt.ItemDataRole.UserRole)
            child.setCheckState(0, self._effective_check_state(child_path))
            self._refresh_loaded_descendant_check_states(child)

    def _navigate_to_path(self, target_path: str) -> None:
        self.current_folder = target_path
        self.folder_path_edit.setText(target_path)
        self.folder_path_edit.setCursorPosition(0)

    def _selected_extensions(self) -> set[str]:
        return {extension for extension, checkbox in self.file_type_checkboxes.items() if checkbox.isChecked()}

    def _update_conditions_summary(self) -> None:
        selected_labels = [label for extension, label in self.supported_file_types.items() if self.file_type_checkboxes[extension].isChecked()]
        if not selected_labels:
            self.conditions_summary_label.setText('선택된 문서 형식이 없습니다.')
            return
        snippet_mode = '포함' if self.include_snippet_checkbox.isChecked() else '미포함'
        self.conditions_summary_label.setText('검색 대상 형식: ' + ', '.join(selected_labels) + f' | 스니펫: {snippet_mode}')

    def _start_search(self) -> None:
        self.result_list.clear()
        self._result_payloads.clear()
        self.result_meta_label.setText("0개 문서")
        self._clear_preview()

        checked_folders = sorted(self.checked_folder_paths_set)
        if not checked_folders:
            QMessageBox.information(self, "폴더 선택", "왼쪽 트리에서 검색할 폴더를 체크하세요.")
            return

        query = self.search_input.text().strip()
        if not query:
            QMessageBox.information(self, "검색어 입력", "검색어를 입력하세요.")
            return

        selected_extensions = self._selected_extensions()
        if not selected_extensions:
            QMessageBox.information(self, "파일 형식 선택", "하나 이상의 문서 파일 형식을 선택하세요.")
            return

        print(
            f"[DocumentSearch] start requested folders={checked_folders} "
            f"extensions={sorted(selected_extensions)} query={query!r}"
        )

        if self.search_worker and self.search_worker.isRunning():
            self.search_worker.cancel()
            self.search_worker.wait()

        self.search_button.setEnabled(False)
        self.folder_tree.setEnabled(False)
        self.cancel_button.setVisible(True)
        self.status_label.setText(f"검색을 시작합니다... ({len(checked_folders)}개 폴더)")

        self.search_worker = SearchWorker(checked_folders, query, selected_extensions, self)
        self.search_worker.result_found.connect(self._append_result)
        self.search_worker.progress_changed.connect(self._update_progress)
        self.search_worker.search_finished.connect(self._finish_search)
        self.search_worker.search_failed.connect(self._fail_search)
        self.search_worker.start()

    def _append_result(self, file_name: str, file_path: str, snippet: str, preview: str, created_at: str, modified_at: str, file_size: str, file_kind: str) -> None:
        payload = {
            'file_name': file_name,
            'file_path': file_path,
            'snippet': snippet,
            'preview': preview,
            'created_at': created_at,
            'modified_at': modified_at,
            'file_size': file_size,
            'file_kind': file_kind,
        }
        self._result_payloads.append(payload)
        self._append_result_item(payload)

    def _append_result_item(self, payload: dict[str, str]) -> None:
        include_snippet = self.include_snippet_checkbox.isChecked()
        widget = CustomResultWidget(
            file_data=payload,
            snippet_text=payload.get('snippet', ''),
            include_snippet=include_snippet,
        )
        list_item = QListWidgetItem()
        list_item.setData(Qt.ItemDataRole.UserRole, payload.get('preview', ''))
        list_item.setData(Qt.ItemDataRole.UserRole + 1, payload.get('file_path', ''))
        list_item.setData(Qt.ItemDataRole.UserRole + 2, payload.get('file_name', ''))
        list_item.setSizeHint(widget.sizeHint())
        self.result_list.addItem(list_item)
        self.result_list.setItemWidget(list_item, widget)

        self.result_meta_label.setText(f"{self.result_list.count()}개 문서")
        if self.result_list.currentItem() is None:
            self.result_list.setCurrentItem(list_item)
        self._refresh_result_item_selection(self.result_list.currentItem())

    def _rerender_result_items(self, checked: bool | None = None) -> None:
        if not hasattr(self, 'result_list'):
            return
        selected_path = self.current_preview_path
        self.result_list.clear()
        for payload in self._result_payloads:
            self._append_result_item(payload)
        if selected_path:
            for index in range(self.result_list.count()):
                item = self.result_list.item(index)
                if item.data(Qt.ItemDataRole.UserRole + 1) == selected_path:
                    self.result_list.setCurrentItem(item)
                    break
        self._refresh_result_item_selection(self.result_list.currentItem())
        self._update_conditions_summary()

    def _refresh_result_item_selection(self, current_item) -> None:
        for index in range(self.result_list.count()):
            item = self.result_list.item(index)
            widget = self.result_list.itemWidget(item)
            if isinstance(widget, CustomResultWidget):
                widget.set_selected(item is current_item)

    def _update_progress(self, current: int, total: int, current_file: str) -> None:
        file_name = os.path.basename(current_file)
        self.status_label.setText(f"{current} / {total} 파일 스캔 중 - {file_name}")

    def _finish_search(self, found_count: int, scanned_count: int, cancelled: bool) -> None:
        self.search_button.setEnabled(True)
        self.folder_tree.setEnabled(True)
        self.cancel_button.setVisible(False)
        print(f"[DocumentSearch] finish signal scanned={scanned_count} found={found_count} cancelled={cancelled}")
        if cancelled:
            self.status_label.setText(f"검색이 취소되었습니다. {scanned_count}개 파일 확인, {found_count}개 결과")
        else:
            self.status_label.setText(f"검색 완료: {scanned_count}개 파일 확인, {found_count}개 결과")

    def _fail_search(self, message: str) -> None:
        self.search_button.setEnabled(True)
        self.folder_tree.setEnabled(True)
        self.cancel_button.setVisible(False)
        self.status_label.setText("검색 중 오류가 발생했습니다.")
        print(f"[DocumentSearch] fail signal message={message}")
        QMessageBox.critical(self, "검색 오류", message)

    def _cancel_search(self) -> None:
        if self.search_worker and self.search_worker.isRunning():
            self.search_worker.cancel()

    def _handle_selection_changed(self, current=None, previous=None) -> None:
        item = current if current is not None else self.result_list.currentItem()
        self._refresh_result_item_selection(item)
        if item is None:
            self._clear_preview()
            return

        widget = self.result_list.itemWidget(item)
        if widget is not None:
            self.preview_title.setText(widget.file_name)
        else:
            self.preview_title.setText("미리보기")
        self.current_preview_path = item.data(Qt.ItemDataRole.UserRole + 1) or ''
        preview_text = item.data(Qt.ItemDataRole.UserRole) or "문서를 선택하면 미리보기가 표시됩니다."
        self._update_preview_surface(self.current_preview_path, preview_text)

    def _update_checked_paths_label(self) -> None:
        checked_folders = sorted(self.checked_folder_paths_set)
        if not checked_folders:
            self.checked_paths_label.setText("선택된 폴더 없음")
            self.status_label.setText("왼쪽에서 검색할 폴더를 체크하고 검색어를 입력하세요.")
            return
        if len(checked_folders) == 1:
            self.checked_paths_label.setText(checked_folders[0])
        else:
            self.checked_paths_label.setText(f"{len(checked_folders)}개 폴더 선택됨")

    def _update_preview_surface(self, file_path: str, preview_text: str) -> None:
        suffix = Path(file_path).suffix.lower()
        image_suffixes = {'.png', '.jpg', '.jpeg', '.bmp', '.gif', '.webp'}
        if suffix in image_suffixes and Path(file_path).exists():
            pixmap = QPixmap(file_path)
            if not pixmap.isNull():
                scaled = pixmap.scaled(640, 860, Qt.AspectRatioMode.KeepAspectRatio, Qt.TransformationMode.SmoothTransformation)
                self.preview_image.setPixmap(scaled)
                self.preview_image.setVisible(True)
                self.preview_text.setVisible(False)
                return
        self.preview_image.clear()
        self.preview_image.setVisible(False)
        self.preview_text.setPlainText(preview_text)
        self.preview_text.setVisible(True)

    def _clear_preview(self) -> None:
        self.result_list.clearSelection()
        self._refresh_result_item_selection(None)
        self.preview_title.setText("미리보기")
        self.current_preview_path = ''
        self.preview_image.clear()
        self.preview_image.setVisible(False)
        self.preview_text.setVisible(True)
        self.preview_text.setPlainText("문서를 선택하면 미리보기가 표시됩니다.")

    def _apply_styles(self) -> None:
        self.setStyleSheet(
            """
            QMainWindow {
                background: #F5F6FA;
            }
            QToolBar {
                background: transparent;
                border: none;
                spacing: 6px;
                padding: 0 0 8px 0;
            }
            QToolButton {
                background: #ffffff;
                border: 1px solid #d8e0ea;
                border-radius: 10px;
                padding: 6px 10px;
                color: #243447;
            }
            QToolButton:hover {
                background: #f1f5f9;
            }
            #panelCard {
                background: #FFFFFF;
                border: 1px solid #E5E7EB;
                border-radius: 16px;
            }
            QLabel {
                color: #243447;
            }
            #sectionTitle {
                font-size: 16px;
                font-weight: 700;
                color: #1f2937;
                padding: 2px 2px 6px 2px;
            }
            #fieldLabel {
                font-size: 13px;
                font-weight: 600;
                color: #374151;
                padding-top: 2px;
            }
            #metaLabel {
                color: #6b7280;
                font-size: 12px;
            }
            #innerCard {
                background: #f8fafc;
                border: 1px solid #e5e7eb;
                border-radius: 12px;
            }
            QLineEdit, QTextEdit, QTreeWidget, QTreeView {
                background: #FFFFFF;
                border: 1px solid #E5E7EB;
                border-radius: 12px;
                padding: 8px 10px;
                color: #1f2937;
                selection-background-color: #e0ecff;
            }
            QLineEdit[readOnly="true"] {
                color: #4b5563;
                background: #f9fafb;
            }
            QPushButton {
                background: #ffffff;
                border: 1px solid #d1d5db;
                border-radius: 10px;
                padding: 0 16px;
                color: #1f2937;
                font-weight: 600;
            }
            QPushButton:hover {
                background: #f5f9ff;
                border-color: #b9d1ff;
            }
            QPushButton:pressed {
                background: #e5efff;
            }
            QCheckBox {
                color: #1f2937;
                spacing: 8px;
            }
            QCheckBox::indicator {
                width: 16px;
                height: 16px;
                border: 1px solid #cbd5e1;
                border-radius: 4px;
                background: #ffffff;
            }
            QCheckBox::indicator:checked {
                background: #3b82f6;
                border: 1px solid #3b82f6;
            }
            QTreeWidget, QTreeView {
                outline: none;
                padding: 6px;
            }
            QTreeWidget::item, QTreeView::item {
                padding: 10px 8px;
                border-radius: 8px;
            }
            QTreeWidget::item:hover, QTreeView::item:hover {
                background: #EEF3FF;
            }
            QTreeWidget::item:selected, QTreeView::item:selected {
                background: #E2E8F5;
                color: #111827;
            }
            QTreeWidget::branch, QTreeView::branch {
                border-image: none;
                image: none;
                background: transparent;
            }
            QListWidget#resultList {
                outline: none;
                border: 1px solid #e5e7eb;
                border-radius: 12px;
                background: #FFFFFF;
                padding: 6px;
            }
            QListWidget#resultList::item {
                border: none;
                margin: 0px 0px 8px 0px;
                padding: 0px;
            }
            QListWidget#resultList::item:selected {
                background: transparent;
            }
            #resultHeaderCard {
                background: #F8FAFC;
                border: 1px solid #E5E7EB;
                border-radius: 10px;
            }
            #resultHeaderLabel {
                color: #6B7280;
                font-size: 11px;
                font-weight: 700;
            }
            #resultItemCard {
                background: #ffffff;
                border: 1px solid #e5e7eb;
                border-radius: 12px;
            }
            #resultItemCard[selected="true"] {
                background: #EFF6FF;
                border: 1px solid #93C5FD;
            }
            #resultMetaLabel {
                color: #4B5563;
                font-size: 11px;
            }
            #resultSnippetLabel {
                color: #1f2937;
                font-size: 12px;
                line-height: 1.35;
                background: #f8fafc;
                border: 1px solid #edf2f7;
                border-radius: 8px;
                padding: 6px 8px;
            }
            #resultItemCard[selected="true"] #resultSnippetLabel {
                background: #DBEAFE;
                border: 1px solid #93C5FD;
                color: #1E3A8A;
            }
            QHeaderView::section {
                background: #f9fafb;
                color: #475569;
                border: none;
                border-bottom: 1px solid #e5e7eb;
                padding: 8px;
                font-weight: 600;
            }
            QScrollArea {
                background: transparent;
                border: none;
            }
            QTextEdit {
                padding: 12px;
            }
            #previewImage {
                background: #f9fafb;
                border: 1px solid #e5e7eb;
                border-radius: 12px;
                min-height: 160px;
            }
            QSplitter::handle {
                background: transparent;
            }
            QSplitter::handle:hover {
                background: rgba(148, 163, 184, 0.18);
                border-radius: 3px;
            }
            QScrollBar:vertical, QScrollBar:horizontal {
                background: transparent;
                border: none;
                margin: 2px;
            }
            QScrollBar:vertical {
                width: 8px;
            }
            QScrollBar:horizontal {
                height: 8px;
            }
            QScrollBar::handle:vertical, QScrollBar::handle:horizontal {
                background: #B7C3D6;
                border-radius: 4px;
                min-height: 24px;
                min-width: 24px;
            }
            QScrollBar::handle:vertical:hover, QScrollBar::handle:horizontal:hover {
                background: #8EA1BC;
            }
            QScrollBar::add-line:vertical, QScrollBar::sub-line:vertical,
            QScrollBar::add-line:horizontal, QScrollBar::sub-line:horizontal,
            QScrollBar::add-page:vertical, QScrollBar::sub-page:vertical,
            QScrollBar::add-page:horizontal, QScrollBar::sub-page:horizontal {
                background: transparent;
                border: none;
            }
            """
        )

    def showEvent(self, event) -> None:
        super().showEvent(event)
        total_width = self.top_splitter.size().width()
        total_height = self.vertical_splitter.size().height()
        if total_width > 0:
            self.top_splitter.setSizes([int(total_width * 0.50), int(total_width * 0.50)])
            self.bottom_splitter.setSizes([int(total_width * 0.62), int(total_width * 0.38)])
        if total_height > 0:
            self.vertical_splitter.setSizes([int(total_height * 0.42), int(total_height * 0.58)])

    def closeEvent(self, event) -> None:
        if self.search_worker and self.search_worker.isRunning():
            self.search_worker.cancel()
            self.search_worker.wait(2000)
        super().closeEvent(event)


class DocumentSearchWidget(QWidget):
    tool_key = 'document_search'
    tool_name = '🔍 문서 찾기'
    window_title = '문서 통합 검색'
    singleton = True
    enabled = True

    def __init__(self, parent=None) -> None:
        super().__init__(parent)
        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(0)

        self.window_adapter = DocumentSearchMainWindow()
        self.window_adapter.setMenuWidget(None)
        central = self.window_adapter.takeCentralWidget()
        if central is not None:
            central.setParent(self)
            layout.addWidget(central)


if __name__ == "__main__":
    app = QApplication(sys.argv)
    window = DocumentSearchMainWindow()
    if '--demo-results' in sys.argv:
        window._load_dummy_results_for_test()
    window.show()
    sys.exit(app.exec())
