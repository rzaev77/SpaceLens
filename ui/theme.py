"""Тёмная плоская тема SpaceLens."""

DARK_QSS = """
* {
    font-family: "Segoe UI", "Inter", "Arial", sans-serif;
    font-size: 10pt;
    outline: none;
}
QMainWindow, QWidget {
    background-color: #0f1420;
    color: #e2e8f0;
}
QLabel {
    background: transparent;
    color: #cbd5e1;
}
QLabel#heading {
    color: #f1f5f9;
    font-size: 12pt;
    font-weight: 600;
}
QLabel#muted {
    color: #64748b;
}
QLabel#badgeOriginal {
    color: #2dd4bf;
    font-weight: 600;
}
QPushButton {
    background-color: #1e293b;
    color: #e2e8f0;
    border: 1px solid #334155;
    border-radius: 6px;
    padding: 6px 14px;
}
QPushButton:hover { background-color: #273449; border-color: #475569; }
QPushButton:pressed { background-color: #172033; }
QPushButton:disabled { color: #475569; background-color: #151c2c; border-color: #232f45; }
QPushButton#accent {
    background-color: #4f46e5;
    border: 1px solid #6366f1;
    color: #ffffff;
    font-weight: 600;
}
QPushButton#accent:hover { background-color: #5b52f0; }
QPushButton#accent:pressed { background-color: #4338ca; }
QPushButton#danger {
    background-color: #3b1d24;
    border: 1px solid #7f1d1d;
    color: #fca5a5;
}
QPushButton#danger:hover { background-color: #4c222b; }
QPushButton#crumb {
    background: transparent;
    border: none;
    border-radius: 6px;
    padding: 4px 8px;
    color: #94a3b8;
}
QPushButton#crumb:hover { background-color: #1e293b; color: #e2e8f0; }
QPushButton#crumbCurrent {
    background: transparent;
    border: none;
    padding: 4px 8px;
    color: #a5b4fc;
    font-weight: 600;
}
QLineEdit {
    background-color: #151c2c;
    border: 1px solid #334155;
    border-radius: 6px;
    padding: 6px 10px;
    color: #e2e8f0;
    selection-background-color: #4f46e5;
}
QLineEdit:focus { border-color: #6366f1; }
QTabWidget::pane {
    border: 1px solid #232f45;
    border-radius: 8px;
    top: -1px;
}
QTabBar::tab {
    background: transparent;
    color: #94a3b8;
    padding: 9px 20px;
    border-bottom: 2px solid transparent;
}
QTabBar::tab:hover { color: #e2e8f0; }
QTabBar::tab:selected {
    color: #a5b4fc;
    border-bottom: 2px solid #6366f1;
}
QProgressBar {
    background-color: #151c2c;
    border: 1px solid #232f45;
    border-radius: 6px;
    height: 14px;
    text-align: center;
    color: #94a3b8;
    font-size: 8pt;
}
QProgressBar::chunk {
    background-color: #4f46e5;
    border-radius: 5px;
}
QScrollArea { border: none; background: transparent; }
QScrollBar:vertical {
    background: #0f1420; width: 10px; margin: 0;
}
QScrollBar::handle:vertical {
    background: #334155; border-radius: 5px; min-height: 24px;
}
QScrollBar::handle:vertical:hover { background: #475569; }
QScrollBar::add-line:vertical, QScrollBar::sub-line:vertical { height: 0; }
QScrollBar:horizontal {
    background: #0f1420; height: 10px; margin: 0;
}
QScrollBar::handle:horizontal {
    background: #334155; border-radius: 5px; min-width: 24px;
}
QScrollBar::add-line:horizontal, QScrollBar::sub-line:horizontal { width: 0; }
QScrollBar::add-page, QScrollBar::sub-page { background: transparent; }
QFrame#card {
    background-color: #151c2c;
    border: 1px solid #232f45;
    border-radius: 8px;
}
QFrame#thumb {
    background-color: #101828;
    border: 1px solid #232f45;
    border-radius: 6px;
}
QCheckBox { color: #94a3b8; spacing: 6px; background: transparent; }
QCheckBox::indicator {
    width: 15px; height: 15px;
    border: 1px solid #475569; border-radius: 4px;
    background: #151c2c;
}
QCheckBox::indicator:checked { background: #4f46e5; border-color: #6366f1; }
QToolTip {
    background-color: #1e293b;
    color: #e2e8f0;
    border: 1px solid #475569;
    border-radius: 6px;
    padding: 6px 8px;
}
QMenu {
    background-color: #1e293b;
    border: 1px solid #334155;
    border-radius: 8px;
    padding: 4px;
}
QMenu::item {
    padding: 7px 22px;
    border-radius: 6px;
    color: #e2e8f0;
}
QMenu::item:selected { background-color: #334155; }
QMenu::separator { height: 1px; background: #334155; margin: 4px 8px; }
QMessageBox { background-color: #151c2c; }
QFileDialog { background-color: #0f1420; }
"""