from __future__ import annotations


COLORS = {
    "surface": "#171719",
    "panel": "#222225",
    "panel_alt": "#2b2b2f",
    "text": "#f3f0e8",
    "muted": "#b8b1a4",
    "accent": "#f08a3c",
    "accent_pressed": "#c86d2e",
    "focus": "#ffd166",
    "danger": "#d95f5f",
}


APP_QSS = f"""
QWidget {{
    background: {COLORS["surface"]};
    color: {COLORS["text"]};
    font-family: "Segoe UI", Arial, sans-serif;
    font-size: 12px;
}}

QLabel#Title {{
    color: {COLORS["text"]};
    font-size: 14px;
    font-weight: 700;
}}

QLabel#Muted {{
    color: {COLORS["muted"]};
}}

QLabel#DebugValue {{
    color: {COLORS["text"]};
    font-weight: 600;
}}

QWidget#DebugHeader {{
    background: {COLORS["panel"]};
    border-bottom: 1px solid #343337;
}}

QLabel#StageHeader {{
    color: {COLORS["focus"]};
    background: {COLORS["panel"]};
    border: 1px solid #3a3938;
    border-radius: 6px;
    padding: 5px 8px;
    font-weight: 700;
}}

QWidget#EvolutionNode {{
    background: {COLORS["panel"]};
    border: 1px solid #3a3938;
    border-radius: 6px;
}}

QWidget#EvolutionNode[selected="true"] {{
    background: {COLORS["panel_alt"]};
    border-color: {COLORS["focus"]};
}}

QLabel#EvolutionNodeName {{
    background: transparent;
    font-size: 11px;
    font-weight: 700;
}}

QLabel#EvolutionGraphStageHeader {{
    background: transparent;
    color: {COLORS["focus"]};
    font-weight: 700;
}}

QPushButton {{
    background: {COLORS["panel_alt"]};
    border: 1px solid #3a3938;
    border-radius: 6px;
    padding: 6px 10px;
}}

QPushButton:hover {{
    border-color: {COLORS["accent"]};
}}

QPushButton:pressed {{
    background: {COLORS["accent_pressed"]};
}}

QPushButton:focus {{
    border-color: {COLORS["focus"]};
}}

QPushButton:disabled {{
    color: #686560;
    background: #1d1d20;
}}

QGroupBox {{
    background: {COLORS["panel"]};
    border: 1px solid #343337;
    border-radius: 6px;
    margin-top: 9px;
    padding-top: 6px;
    font-weight: 700;
}}

QGroupBox::title {{
    subcontrol-origin: margin;
    subcontrol-position: top left;
    left: 10px;
    padding: 0 4px;
    color: {COLORS["focus"]};
}}

QSpinBox {{
    background: #111113;
    border: 1px solid #3a3938;
    border-radius: 5px;
    padding: 4px 8px;
    min-height: 22px;
}}

QSpinBox:hover {{
    border-color: {COLORS["accent"]};
}}

QSpinBox:focus {{
    border-color: {COLORS["focus"]};
}}

QProgressBar {{
    background: #111113;
    border: 1px solid #3a3938;
    border-radius: 5px;
    height: 12px;
    text-align: center;
}}

QProgressBar::chunk {{
    background: {COLORS["accent"]};
    border-radius: 4px;
}}

QComboBox {{
    background: #111113;
    color: {COLORS["text"]};
    border: 1px solid #3a3938;
    border-radius: 5px;
    padding: 4px 8px;
    min-height: 22px;
}}

QComboBox:hover {{
    border-color: {COLORS["accent"]};
}}

QComboBox:focus {{
    border-color: {COLORS["focus"]};
}}

QComboBox QAbstractItemView {{
    background: {COLORS["panel"]};
    color: {COLORS["text"]};
    border: 1px solid #3a3938;
    selection-background-color: {COLORS["accent_pressed"]};
    selection-color: {COLORS["text"]};
}}

QListWidget {{
    background: #111113;
    color: {COLORS["text"]};
    border: 1px solid #3a3938;
    border-radius: 6px;
    padding: 4px;
    outline: 0;
}}

QListWidget::item {{
    border-radius: 4px;
    padding: 6px 8px;
}}

QListWidget::item:hover {{
    background: {COLORS["panel_alt"]};
}}

QListWidget::item:selected {{
    background: {COLORS["accent_pressed"]};
    color: {COLORS["text"]};
}}

QDialogButtonBox QPushButton {{
    min-width: 72px;
}}

QToolButton#BabyChoiceCard {{
    background: {COLORS["panel"]};
    border: 1px solid #3a3938;
    border-radius: 6px;
    padding: 8px 6px;
    font-size: 11px;
    font-weight: 700;
}}

QToolButton#BabyChoiceCard:hover {{
    border-color: {COLORS["accent"]};
}}

QToolButton#BabyChoiceCard:checked {{
    background: {COLORS["panel_alt"]};
    border-color: {COLORS["focus"]};
}}

QToolTip {{
    background: {COLORS["panel"]};
    color: {COLORS["text"]};
    border: 1px solid #3a3938;
    padding: 4px 6px;
}}

QCheckBox {{
    spacing: 8px;
    font-weight: 600;
}}

QCheckBox::indicator {{
    width: 16px;
    height: 16px;
    border: 1px solid #4c4a46;
    border-radius: 4px;
    background: #111113;
}}

QCheckBox::indicator:hover {{
    border-color: {COLORS["accent"]};
}}

QCheckBox::indicator:checked {{
    background: {COLORS["accent"]};
    border-color: {COLORS["accent"]};
}}

QScrollArea {{
    border: none;
}}

QScrollBar:vertical {{
    background: #111113;
    width: 10px;
    margin: 0;
}}

QScrollBar::handle:vertical {{
    background: #4a4742;
    border-radius: 5px;
    min-height: 40px;
}}

QScrollBar::handle:vertical:hover {{
    background: {COLORS["accent_pressed"]};
}}

QScrollBar::add-line:vertical,
QScrollBar::sub-line:vertical {{
    height: 0;
}}

QMenu {{
    background: {COLORS["panel"]};
    border: 1px solid #3a3938;
}}

QMenu::item {{
    padding: 6px 18px;
}}

QMenu::item:selected {{
    background: {COLORS["accent_pressed"]};
}}

QLineEdit,
QPlainTextEdit {{
    background: #111113;
    color: {COLORS["text"]};
    border: 1px solid #3a3938;
    border-radius: 5px;
    padding: 4px 8px;
    selection-background-color: {COLORS["accent_pressed"]};
}}

QLineEdit:hover,
QPlainTextEdit:hover {{
    border-color: {COLORS["accent"]};
}}

QLineEdit:focus,
QPlainTextEdit:focus {{
    border-color: {COLORS["focus"]};
}}

QTableWidget {{
    background: #111113;
    color: {COLORS["text"]};
    border: 1px solid #3a3938;
    border-radius: 6px;
    gridline-color: #2f2e31;
    selection-background-color: {COLORS["accent_pressed"]};
    selection-color: {COLORS["text"]};
    outline: 0;
}}

QHeaderView::section {{
    background: {COLORS["panel"]};
    color: {COLORS["muted"]};
    border: none;
    border-bottom: 1px solid #3a3938;
    padding: 6px 8px;
    font-weight: 700;
}}

QTableWidget::item {{
    padding: 5px 8px;
}}

QTableWidget::item:hover {{
    background: {COLORS["panel_alt"]};
}}

QTabWidget::pane {{
    border: 1px solid #343337;
    border-radius: 6px;
    background: {COLORS["panel"]};
}}

QTabBar::tab {{
    background: #111113;
    color: {COLORS["muted"]};
    border: 1px solid #343337;
    border-bottom: none;
    padding: 6px 10px;
    margin-right: 2px;
    border-top-left-radius: 5px;
    border-top-right-radius: 5px;
}}

QTabBar::tab:selected {{
    background: {COLORS["panel_alt"]};
    color: {COLORS["text"]};
    border-color: {COLORS["focus"]};
}}
"""
