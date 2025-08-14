from __future__ import annotations
import sys
import ecu_tool.main as _cli_mod
import ecu_tool.gui.main_qt as _gui_mod

def main():
    if len(sys.argv) == 1:
        # GUI
        try:
            _gui_mod.main()
        except AttributeError:
            # запасной путь, если в модуле нет main()
            from PySide6.QtWidgets import QApplication
            app = QApplication(sys.argv)
            win = _gui_mod.MainWindow()
            win.show()
            sys.exit(app.exec_() if hasattr(app, "exec_") else app.exec())
    else:
        # CLI
        _cli_mod.app()

if __name__ == "__main__":
    main()
