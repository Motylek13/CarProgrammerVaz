# gui/main_qt.py
from __future__ import annotations
import json, zlib, sys
from pathlib import Path

from PySide6.QtWidgets import (
    QApplication, QMainWindow, QWidget, QTabWidget, QVBoxLayout, QHBoxLayout,
    QPushButton, QLabel, QFileDialog, QComboBox, QCheckBox, QMessageBox,
    QSpinBox, QLineEdit, QToolBar, QStatusBar, QGroupBox, QSplitter, QFrame,
    QTextEdit, QTableView, QProgressDialog
)
from PySide6.QtCore import Qt, QModelIndex
from PySide6.QtGui import (
    QAction,
    QFontDatabase,
    QPalette,
    QColor,
    QVector3D,
    QLinearGradient,
)
from PySide6.QtDataVisualization import (
    Q3DSurface,
    QSurface3DSeries,
    QSurfaceDataItem,
    QValue3DAxis,
    Q3DTheme,
    main
)

# ---- Пакетные импорты (работают и в .exe, и из исходников)
try:
    from ..config import LOG_FILE
    from ..diag.dtc import parse_obd_dtc
    from ..ai_assistant.engine import Assistant
    from ..ecu_transport.elm327 import ELM327
    from ..firmware.io import SimBackend, RealBackend, dump_firmware, flash_firmware
    from ..firmware.tune import read_params, write_params, TuneParams, blank_params
    from ..kwp_tools import kwp_ping
    from .hex_model import HexTableModel, BYTES_PER_ROW
except ImportError:
    from config import LOG_FILE
    from diag.dtc import parse_obd_dtc
    from ai_assistant.engine import Assistant
    from ecu_transport.elm327 import ELM327
    from firmware.io import SimBackend, RealBackend, dump_firmware, flash_firmware
    from firmware.tune import read_params, write_params, TuneParams, blank_params
    from kwp_tools import kwp_ping
    from gui.hex_model import HexTableModel, BYTES_PER_ROW

# ---------- ресурсы (rules.json) ----------
PKG_ROOT = Path(__file__).resolve().parents[1]  # .../ecu_tool
BASE_RES  = Path(getattr(sys, "_MEIPASS", PKG_ROOT))
RULES_PATH = BASE_RES / "ai_assistant" / "rules.json"

# ---------- тема ----------
def setup_theme(app):
    app.setStyle("Fusion")
    pal = QPalette()
    pal.setColor(QPalette.Window, QColor(30, 32, 36))
    pal.setColor(QPalette.WindowText, QColor(220, 220, 220))
    pal.setColor(QPalette.Base, QColor(30, 30, 30))
    pal.setColor(QPalette.AlternateBase, QColor(45, 45, 45))
    pal.setColor(QPalette.Text, QColor(220, 220, 220))
    pal.setColor(QPalette.Button, QColor(45, 45, 45))
    pal.setColor(QPalette.ButtonText, QColor(220, 220, 220))
    pal.setColor(QPalette.Highlight, QColor(77, 163, 255))
    pal.setColor(QPalette.HighlightedText, QColor(255, 255, 255))
    app.setPalette(pal)

    app.setStyleSheet("""
        QWidget{font-size:13px; color:#dcdcdc;}
        QGroupBox{margin-top:1ex;}
        QGroupBox::title{color:#9aa3ad;}
        QPushButton{background-color:#2d2f33; color:#ffffff; border:1px solid #3c3f43; border-radius:4px; padding:4px;}
        QPushButton:hover{background-color:#3c3f43;}
        QTextEdit,QLineEdit{background:#1e2024; color:#ffffff;}
        QTableView::item:selected { background:#4DA3FF; color:#ffffff; }
        QTableView { selection-background-color:#4DA3FF; selection-color:#ffffff; }
        QTableView QLineEdit { background:#1E2024; color:#ffffff; selection-background-color:#4DA3FF; selection-color:#ffffff; }
    """)


def hline():
    line = QFrame(); line.setFrameShape(QFrame.HLine); line.setFrameShadow(QFrame.Sunken); return line

# ---------- MainWindow ----------
class MainWindow(QMainWindow):
    def __init__(self):
        super().__init__()
        self.setWindowTitle("ECU Tool")
        self.resize(1280, 800)

        # toolbar
        tb = QToolBar("Main"); tb.setMovable(False); self.addToolBar(tb)
        act_gui = QAction("Главная", self)
        act_hex = QAction("Hex-редактор", self)
        act_tune = QAction("Тюнинг", self)
        tb.addAction(act_gui); tb.addAction(act_hex); tb.addAction(act_tune)
        act_gui.triggered.connect(lambda: self.tabs.setCurrentWidget(self.page_dash))
        act_hex.triggered.connect(lambda: self.tabs.setCurrentWidget(self.page_hex))
        act_tune.triggered.connect(lambda: self.tabs.setCurrentWidget(self.page_tune))

        self.setStatusBar(QStatusBar())

        # tabs
        self.tabs = QTabWidget(); self.setCentralWidget(self.tabs)
        self._build_dashboard()
        self._build_hex_editor()
        self._build_tune_tab()

        # state
        self.current_fw_path: Path | None = None

    # ----------- Dashboard (кнопки + лог) -----------
    def _build_dashboard(self):
        w = QWidget(); root = QVBoxLayout(w)

        # верх: соединение
        grp_conn = QGroupBox("Подключение")
        layc = QHBoxLayout(grp_conn)
        self.cb_ports = QComboBox()
        self.btn_refresh = QPushButton("Обновить порты")
        self.chk_demo = QCheckBox("Демо"); self.chk_demo.setChecked(True)
        self.sp_chunk = QSpinBox(); self.sp_chunk.setRange(64, 8192); self.sp_chunk.setValue(512)
        layc.addWidget(QLabel("Порт:")); layc.addWidget(self.cb_ports, 1)
        layc.addWidget(self.btn_refresh); layc.addWidget(self.chk_demo)
        layc.addWidget(QLabel("Блок, байт:")); layc.addWidget(self.sp_chunk)

        # середина: основные действия
        grp_actions = QGroupBox("Действия")
        laya = QHBoxLayout(grp_actions)
        self.btn_ports = QPushButton("Порты")
        self.btn_ping  = QPushButton("KWP-ping")
        self.btn_dtc   = QPushButton("Считать DTC")
        self.btn_info  = QPushButton("Инфо ЭБУ")
        self.btn_read  = QPushButton("Считать прошивку")
        self.btn_write = QPushButton("Записать прошивку (DEMO)")
        self.btn_open_hex = QPushButton("Открыть в Hex…")
        for b in (self.btn_ports, self.btn_ping, self.btn_dtc, self.btn_info, self.btn_read, self.btn_write, self.btn_open_hex):
            laya.addWidget(b)

        # низ: лог
        grp_log = QGroupBox("Лог")
        layl = QVBoxLayout(grp_log)
        self.log = QTextEdit(); self.log.setReadOnly(True); layl.addWidget(self.log)

        root.addWidget(grp_conn)
        root.addWidget(grp_actions)
        root.addWidget(grp_log, 1)

        # connect
        self.btn_refresh.clicked.connect(self._refresh_ports)
        self.btn_ports.clicked.connect(self._show_ports)
        self.btn_ping.clicked.connect(self._do_kwp_ping)
        self.btn_dtc.clicked.connect(self._do_read_dtc)
        self.btn_info.clicked.connect(self._do_ecu_info)
        self.btn_read.clicked.connect(self._do_read_fw)
        self.btn_write.clicked.connect(self._do_write_fw)
        self.btn_open_hex.clicked.connect(self._open_fw_into_hex)

        self._refresh_ports()

        self.page_dash = w
        self.tabs.addTab(w, "Главная")

    # ----------- Hex-редактор -----------
    def _build_hex_editor(self):
        w = QWidget(); root = QVBoxLayout(w)

        controls = QHBoxLayout()
        btn_open = QPushButton("Открыть .bin")
        btn_save = QPushButton("Сохранить как…")
        self.lbl_crc = QLabel("CRC32: —")
        self.ed_find = QLineEdit(); self.ed_find.setPlaceholderText("Поиск HEX ('DE AD BE EF') или ASCII")
        self.chk_ascii = QCheckBox("ASCII")
        btn_find = QPushButton("Найти")
        self.ed_goto = QLineEdit(); self.ed_goto.setPlaceholderText("Перейти к адресу (hex)")
        btn_goto = QPushButton("Перейти")
        for wdg in (btn_open, btn_save, self.lbl_crc, self.ed_find, self.chk_ascii, btn_find, self.ed_goto, btn_goto):
            controls.addWidget(wdg)
        root.addLayout(controls)

        # таблица
        self.table = QTableView()
        self.model = HexTableModel(b"")
        self.table.setModel(self.model)
        fixed = QFontDatabase.systemFont(QFontDatabase.FixedFont); fixed.setPointSize(12)
        self.table.setFont(fixed)
        self.table.verticalHeader().setDefaultSectionSize(22)
        self.table.setAlternatingRowColors(True)
        self.table.setSelectionBehavior(QTableView.SelectionBehavior.SelectItems)
        root.addWidget(self.table, 1)

        # шрифт покрупнее и моноширинный
        fixed = QFontDatabase.systemFont(QFontDatabase.FixedFont)
        fixed.setPointSize(13)  # было 12 — можно 13–14
        self.table.setFont(fixed)
        self.table.verticalHeader().setDefaultSectionSize(24)  # выше строки
        self.table.horizontalHeader().setDefaultAlignment(Qt.AlignCenter)

        # аккуратные границы и полоски
        self.table.setAlternatingRowColors(True)
        self.table.setShowGrid(True)
        self.table.setCornerButtonEnabled(False)

        btn_zoom_in = QPushButton("Зум +")
        btn_zoom_out = QPushButton("Зум –")
        controls.addWidget(btn_zoom_in)
        controls.addWidget(btn_zoom_out)

        def _zoom(delta):
            f = self.table.font()
            f.setPointSize(max(8, min(24, f.pointSize() + delta)))
            self.table.setFont(f)
            self.table.verticalHeader().setDefaultSectionSize(int(1.85 * f.pointSize()))

        btn_zoom_in.clicked.connect(lambda: _zoom(+1))
        btn_zoom_out.clicked.connect(lambda: _zoom(-1))

        self.chk_only_changed = QCheckBox("Только изменённые")
        controls.addWidget(self.chk_only_changed)
        self.chk_only_changed.stateChanged.connect(self._hex_filter_changed)

        btn_open.clicked.connect(self._hex_open)
        btn_save.clicked.connect(self._hex_save_as)
        btn_find.clicked.connect(self._hex_find)
        btn_goto.clicked.connect(self._hex_goto)
        self.model.dataChanged.connect(lambda *_: self._update_crc())

        self.page_hex = w
        self.tabs.addTab(w, "Hex-редактор")

    # ----------- Tuning tab -----------
    def _build_tune_tab(self):
        w = QWidget(); root = QVBoxLayout(w)

        # Параметры
        grp = QGroupBox("Настройки")
        lay = QVBoxLayout(grp)

        self.sp_rpm = QSpinBox(); self.sp_rpm.setRange(1000, 12000); self.sp_rpm.setSuffix(" об/мин")
        self.sp_rpm.setToolTip("Ограничение максимальных оборотов двигателя")

        mix_layout = QHBoxLayout(); self.mix_spins = []
        for i in range(8):
            sp = QSpinBox(); sp.setRange(0, 255)
            sp.setToolTip("Смесь для точки %d" % (i + 1))
            self.mix_spins.append(sp); mix_layout.addWidget(sp)

        self.chk_pops = QCheckBox("Отстрелы")
        self.chk_pops.setToolTip("Демонстрационный флаг активации отстрелов")

        lay.addWidget(QLabel("Ограничение оборотов:"))
        lay.addWidget(self.sp_rpm)
        lay.addWidget(QLabel("Таблица смеси (0..255):"))
        lay.addLayout(mix_layout)
        lay.addWidget(self.chk_pops)

        btn_apply = QPushButton("Применить к Hex")
        btn_apply.setToolTip("Записать параметры в текущую прошивку")
        btn_refresh = QPushButton("Обновить из Hex")
        btn_refresh.setToolTip("Перечитать параметры из образа")
        btns = QHBoxLayout(); btns.addWidget(btn_refresh); btns.addWidget(btn_apply)
        lay.addLayout(btns)

        root.addWidget(grp)

        # График смеси (3D поверхность)
        self.surface = Q3DSurface()
        self.series = QSurface3DSeries()
        self.surface.addSeries(self.series)

        axX = QValue3DAxis(); axX.setTitle("Точка")
        axY = QValue3DAxis(); axY.setTitle("Смесь")
        axZ = QValue3DAxis(); axZ.setTitle("Зона")
        self.surface.setAxisX(axX); self.surface.setAxisY(axY); self.surface.setAxisZ(axZ)

        grad = QLinearGradient()
        grad.setColorAt(0.0, QColor(0, 0, 255))
        grad.setColorAt(1.0, QColor(255, 0, 0))
        self.series.setBaseGradient(grad)
        self.series.setColorStyle(Q3DTheme.ColorStyleRangeGradient)

        self.chart_view = QWidget.createWindowContainer(self.surface)
        main
        root.addWidget(self.chart_view, 1)

        btn_refresh.clicked.connect(self._update_tune_from_model)
        btn_apply.clicked.connect(self._apply_tune_changes)

        self.page_tune = w
        self.tabs.addTab(w, "Тюнинг")
        self.tune_params = blank_params()
        self._refresh_tune_graph()

    def _hex_filter_changed(self, state):
        if not self.model.edited:
            return
        # прыжок к первой изменённой
        r, c = next(iter(self.model.edited))
        idx = self.model.index(r, c)
        self.table.setCurrentIndex(idx)
        self.table.scrollTo(idx, QTableView.ScrollHint.PositionAtCenter)
        self.table.resizeColumnsToContents()
        self.model.dataChanged.connect(lambda *_: self._update_crc())

        # и потом чуть добавить
        for col in range(self.model.columnCount()):
            self.table.setColumnWidth(col, self.table.columnWidth(col) + 10)

    # ---------- utils ----------
    def _log(self, html: str):
        if hasattr(self, "log") and self.log is not None:
            self.log.append(html)
        self.statusBar().showMessage(self._strip(html), 3000)

    @staticmethod
    def _strip(html: str) -> str:
        import re
        return re.sub("<[^<]+?>", "", html)

    def _backend(self):
        if self.chk_demo.isChecked():
            return SimBackend(Path("logs/sim_ecu.bin"))
        port = self._current_port()
        if not port:
            raise RuntimeError("COM-порт не выбран")
        elm = ELM327(port)
        return RealBackend(adapter=elm, developer_mode=False)

    def _current_port(self) -> str | None:
        return self.cb_ports.currentData() if self.cb_ports.count() else None

    # ---------- actions ----------
    def _refresh_ports(self):
        from serial.tools import list_ports
        self.cb_ports.clear()
        for p in list_ports.comports():
            self.cb_ports.addItem(f"{p.device} — {p.description}", p.device)
        self._log("<span style='color:#9aa3ad'>Порты обновлены.</span>")

    def _show_ports(self):
        if self.cb_ports.count() == 0:
            self._log("<b style='color:#d7ba7d'>Портов не найдено.</b>")
        else:
            items = [self.cb_ports.itemText(i) for i in range(self.cb_ports.count())]
            self._log("Доступные порты:<br>• " + "<br>• ".join(items))

    def _do_kwp_ping(self):
        port = self._current_port()
        if not port:
            QMessageBox.warning(self, "Порт", "Выбери COM-порт."); return
        elm = ELM327(port)
        try:
            self._log("<b>Инициализация адаптера…</b>")
            elm.init()
            ok = kwp_ping(elm, header="81 10 F1", verbose=False)
            self._log("<span style='color:#7ed321'>ECU ответил на KWP (ping OK).</span>" if ok
                      else "<span style='color:#d7ba7d'>Ответ на KWP не распознан.</span>")
        except Exception as e:
            QMessageBox.critical(self, "KWP-ping", str(e))
        finally:
            elm.close()

    def _do_read_dtc(self):
        assistant = Assistant(RULES_PATH)
        if self.chk_demo.isChecked():
            raw = "43 01 71 00 00 00\r\n>"
            dtcs, _ = parse_obd_dtc(raw)
        else:
            port = self._current_port()
            if not port:
                QMessageBox.warning(self, "Порт", "Выбери COM-порт."); return
            elm = ELM327(port)
            try:
                elm.init(); raw = elm.send_obd("03"); dtcs, _ = parse_obd_dtc(raw)
            finally:
                elm.close()
        if dtcs:
            adv = assistant.advise_for_dtcs(dtcs)
            html = f"<b>Найдены DTC:</b> {', '.join(dtcs)}<br><br><b>Рекомендации:</b><br>" + \
                   "<br>".join([f"{a['code'] or '-'} — {a['title']}" for a in adv])
            self._log(html)
        else:
            self._log("<span style='color:#7ed321'>Коды неисправностей не обнаружены.</span>")

    def _do_ecu_info(self):
        backend = self._backend()
        try:
            info = backend.info()
            self._log("<b>Инфо ЭБУ:</b><br><pre style='margin-top:6px'>" +
                      json.dumps(info, ensure_ascii=False, indent=2) + "</pre>")
        finally:
            if hasattr(backend, "close"):
                backend.close()

    def _do_read_fw(self):
        out, _ = QFileDialog.getSaveFileName(self, "Куда сохранить дамп", "logs/dump.bin", "BIN (*.bin)")
        if not out: return
        backend = self._backend()
        try:
            prog = QProgressDialog("Чтение прошивки…", "Отмена", 0, 0, self); prog.setWindowModality(Qt.WindowModal); prog.show()
            result = dump_firmware(backend, Path(out), self.sp_chunk.value())
            prog.close()
            self._log(f"<b>Дамп сохранён:</b> {result['out']} ({result['bytes']} байт)")
            self._load_fw_to_hex(Path(out))
        except Exception as e:
            QMessageBox.critical(self, "Чтение прошивки", str(e))
        finally:
            if hasattr(backend, "close"):
                backend.close()

    def _do_write_fw(self):
        if not self.current_fw_path or not self.current_fw_path.exists():
            QMessageBox.warning(self, "Нет файла", "Сначала открой/считай прошивку на вкладке Hex."); return
        if not self.chk_demo.isChecked():
            QMessageBox.critical(self, "Безопасность", "Запись на реальном ЭБУ отключена."); return
        backend = self._backend()
        try:
            prog = QProgressDialog("Запись прошивки…", "Отмена", 0, 0, self); prog.setWindowModality(Qt.WindowModal); prog.show()
            result = flash_firmware(backend, self.current_fw_path, self.sp_chunk.value())
            prog.close()
            self._log(f"<b>Записано:</b> {result['bytes']} байт из {result['source']}")
        except Exception as e:
            QMessageBox.critical(self, "Запись прошивки", str(e))
        finally:
            if hasattr(backend, "close"):
                backend.close()

    def _open_fw_into_hex(self):
        path, _ = QFileDialog.getOpenFileName(self, "Открыть прошивку", "logs", "BIN (*.bin)")
        if not path: return
        self._load_fw_to_hex(Path(path))
        self.tabs.setCurrentWidget(self.page_hex)

    # ---------- hex handlers ----------
    def _hex_open(self):
        p, _ = QFileDialog.getOpenFileName(self, "Открыть прошивку", "logs", "BIN (*.bin)")
        if not p: return
        self._load_fw_to_hex(Path(p))

    def _load_fw_to_hex(self, path: Path):
        data = Path(path).read_bytes()
        self.model.load_bytes(data)
        self.current_fw_path = Path(path)
        self._update_crc()
        self._log(f"Открыт файл в Hex: <b>{path}</b>")
        self._update_tune_from_model()

    def _hex_save_as(self):
        if self.model.rowCount() == 0:
            QMessageBox.warning(self, "Нет данных", "Сначала открой или считай прошивку."); return
        p, _ = QFileDialog.getSaveFileName(self, "Сохранить как…", "logs/patched.bin", "BIN (*.bin)")
        if not p: return
        Path(p).write_bytes(self.model.bytes())
        self.current_fw_path = Path(p)
        self._update_crc(); self._log(f"Сохранено: <b>{p}</b>")

    def _hex_find(self):
        text = self.ed_find.text().strip()
        if not text: return
        if self.chk_ascii.isChecked():
            pat = text.encode("utf-8", "ignore")
        else:
            hexstr = text.replace(" ", "").replace("0x", "").replace("0X", "")
            try: pat = bytes.fromhex(hexstr)
            except ValueError:
                QMessageBox.warning(self, "HEX", "Неверная HEX-строка."); return
        idx = self.model.find_next(pat, start=0, ascii_mode=self.chk_ascii.isChecked())
        if idx < 0: QMessageBox.information(self, "Поиск", "Не найдено."); return
        self._select_offset(idx)

    def _hex_goto(self):
        s = self.ed_goto.text().strip().lower().replace("0x", "")
        if not s: return
        try: off = int(s, 16)
        except ValueError: QMessageBox.warning(self, "Адрес", "Введи адрес в HEX."); return
        self._select_offset(off)

    def _select_offset(self, off: int):
        row, col = divmod(off, BYTES_PER_ROW)
        idx = self.model.index(row, col)
        self.table.setCurrentIndex(idx)
        self.table.scrollTo(idx, QTableView.ScrollHint.PositionAtCenter)

    # ---------- tuning helpers ----------
    def _update_tune_from_model(self):
        if self.model.rowCount() == 0:
            self.tune_params = blank_params()
        else:
            data = self.model.bytes()
            self.tune_params = read_params(data)
        self.sp_rpm.setValue(self.tune_params.rpm_limit)
        for sp, val in zip(self.mix_spins, self.tune_params.mixture):
            sp.setValue(val)
        self.chk_pops.setChecked(bool(self.tune_params.pops))
        self._refresh_tune_graph()

    def _apply_tune_changes(self):
        self.tune_params.rpm_limit = self.sp_rpm.value()
        self.tune_params.mixture = [sp.value() for sp in self.mix_spins]
        self.tune_params.pops = 1 if self.chk_pops.isChecked() else 0
        buf = bytearray(self.model.bytes())
        write_params(buf, self.tune_params)
        self.model.load_bytes(bytes(buf))
        self._update_crc()
        self._refresh_tune_graph()
        self._log("Параметры тюнинга применены к прошивке.")

    def _refresh_tune_graph(self):

        mix = self.tune_params.mixture
        count = len(mix)
        data = []
        for z in range(count):
            row = []
            for x, v in enumerate(mix):
                y = (v + mix[z]) / 2
                row.append(QSurfaceDataItem(QVector3D(float(x), float(y), float(z))))
            data.append(row)
        self.series.dataProxy().resetArray(data)
        self.surface.axisX().setRange(0, max(0, count - 1))
        self.surface.axisZ().setRange(0, max(0, count - 1))
        self.surface.axisY().setRange(0, 255)
        main

    def _update_crc(self):
        buf = self.model.bytes()
        crc = zlib.crc32(buf) & 0xFFFFFFFF
        self.lbl_crc.setText(f"CRC32: 0x{crc:08X} | size: {len(buf)} bytes")

# ---------- entry ----------
def main():
    app = QApplication(sys.argv)
    setup_theme(app)
    win = MainWindow()
    win.show()
    sys.exit(app.exec())

if __name__ == "__main__":
    main()
