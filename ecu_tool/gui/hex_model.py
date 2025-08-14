# gui/hex_model.py
from __future__ import annotations
from PySide6.QtCore import QAbstractTableModel, Qt, QModelIndex
from typing import List, Tuple

BYTES_PER_ROW = 16

class HexTableModel(QAbstractTableModel):
    """
    Табличная модель: 16 байт в строке + ASCII колонка.
    Поддержка: редактирование, подсветка изменённых байтов, поиск, Undo/Redo.
    """
    def __init__(self, data: bytes | bytearray = b""):
        super().__init__()
        self._orig = bytearray(data)     # исходный образ
        self._buf  = bytearray(data)     # рабочая копия
        self._dirty = set()              # индексы изменённых байтов
        self._undo: List[Tuple[int, int, int]] = []   # (index, old, new)
        self._redo: List[Tuple[int, int, int]] = []

    # ---------- Публичный API ----------
    def load_bytes(self, data: bytes):
        self.beginResetModel()
        self._orig = bytearray(data)
        self._buf  = bytearray(data)
        self._dirty.clear()
        self._undo.clear(); self._redo.clear()
        self.endResetModel()

    def bytes(self) -> bytes:
        return bytes(self._buf)

    def is_dirty(self) -> bool:
        return bool(self._dirty)

    # поиск: pattern в виде bytes; ascii=True искать по ASCII-представлению
    def find_next(self, pattern: bytes, start: int = 0, ascii_mode: bool = False) -> int:
        if not pattern:
            return -1
        data = bytes(self._buf)
        if ascii_mode:
            # нерPrintable -> '.'
            trans = bytes(ch if 32 <= ch <= 126 else ord('.') for ch in data)
            pat = bytes(ch if 32 <= ch <= 126 else ord('.') for ch in pattern)
            idx = trans.find(pat, start)
        else:
            idx = data.find(pattern, start)
        return idx

    # Undo/Redo
    def can_undo(self) -> bool: return len(self._undo) > 0
    def can_redo(self) -> bool: return len(self._redo) > 0

    def undo(self):
        if not self._undo: return
        i, old, new = self._undo.pop()
        self._redo.append((i, old, new))
        self._apply_set(i, old, push_history=False)

    def redo(self):
        if not self._redo: return
        i, old, new = self._redo.pop()
        self._undo.append((i, old, new))
        self._apply_set(i, new, push_history=False)

    # ---------- Qt model ----------
    def rowCount(self, parent=QModelIndex()) -> int:
        if parent.isValid(): return 0
        return (len(self._buf) + BYTES_PER_ROW - 1) // BYTES_PER_ROW

    def columnCount(self, parent=QModelIndex()) -> int:
        return BYTES_PER_ROW + 1  # + ASCII колонка

    def index_to_offset(self, row: int, col: int) -> int:
        return row * BYTES_PER_ROW + col

    def data(self, index, role=Qt.DisplayRole):
        if not index.isValid(): return None
        r, c = index.row(), index.column()

        # ASCII колонка
        if c == BYTES_PER_ROW:
            if role in (Qt.DisplayRole, Qt.EditRole):
                start = r * BYTES_PER_ROW
                end = min(start + BYTES_PER_ROW, len(self._buf))
                chunk = self._buf[start:end]
                return "".join(chr(b) if 32 <= b <= 126 else "." for b in chunk)
            return None

        # HEX байты
        i = self.index_to_offset(r, c)
        if i >= len(self._buf):
            return None

        if role in (Qt.DisplayRole, Qt.EditRole):
            return f"{self._buf[i]:02X}"

        if role == Qt.TextAlignmentRole:
            return Qt.AlignCenter

        if role == Qt.BackgroundRole and i in self._dirty:
            # мягкая подсветка изменённых байтов
            from PySide6.QtGui import QBrush, QColor
            return QBrush(QColor(255, 248, 200))  # светло-жёлтый

        return None

    def headerData(self, section, orientation, role=Qt.DisplayRole):
        if role != Qt.DisplayRole: return None
        if orientation == Qt.Horizontal:
            if section < BYTES_PER_ROW: return f"+{section:02X}"
            return "ASCII"
        else:
            return f"{section*BYTES_PER_ROW:06X}"

    def flags(self, index):
        if not index.isValid(): return Qt.NoItemFlags
        if index.column() == BYTES_PER_ROW:
            return Qt.ItemIsEnabled | Qt.ItemIsSelectable
        return Qt.ItemIsEnabled | Qt.ItemIsSelectable | Qt.ItemIsEditable

    def setData(self, index, value, role=Qt.EditRole):
        if role != Qt.EditRole or not index.isValid(): return False
        if index.column() == BYTES_PER_ROW: return False

        s = str(value).strip().upper()
        # допускаем "0x1A" или "1a"
        if s.startswith("0X"): s = s[2:]
        if len(s) == 1: s = "0" + s
        if len(s) != 2: return False
        try:
            b = int(s, 16) & 0xFF
        except ValueError:
            return False

        i = self.index_to_offset(index.row(), index.column())
        if i >= len(self._buf): return False

        old = self._buf[i]
        if old == b: return True

        self._apply_set(i, b, push_history=True, changed_index=index)
        # обновим ASCII ячейку строки
        ascii_idx = self.index(index.row(), BYTES_PER_ROW)
        self.dataChanged.emit(ascii_idx, ascii_idx, [Qt.DisplayRole])
        return True

    # ---------- внутреннее ----------
    def _apply_set(self, i: int, value: int, push_history: bool, changed_index=None):
        old = self._buf[i]
        self._buf[i] = value & 0xFF

        # пометим/снимем "грязный" байт
        if self._buf[i] != (self._orig[i] if i < len(self._orig) else 0xFF):
            self._dirty.add(i)
        else:
            self._dirty.discard(i)

        if push_history:
            self._undo.append((i, old, self._buf[i]))
            self._redo.clear()

        # уведомим таблицу
        if changed_index is None:
            row, col = divmod(i, BYTES_PER_ROW)
            changed_index = self.index(row, col)
        self.dataChanged.emit(changed_index, changed_index, [Qt.DisplayRole, Qt.EditRole, Qt.BackgroundRole])
