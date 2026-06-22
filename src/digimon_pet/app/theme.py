from __future__ import annotations


COLORS = {
    "surface": "#080b12",
    "surface_alt": "#0d1320",
    "panel": "#111a29",
    "panel_alt": "#172236",
    "panel_hot": "#1d2b40",
    "line": "#263955",
    "line_soft": "#1a283d",
    "text": "#f4f8ff",
    "muted": "#9baac2",
    "subtle": "#62718b",
    "accent": "#19d7ff",
    "accent_soft": "#0d6684",
    "accent_pressed": "#0b96bf",
    "focus": "#ffd84d",
    "focus_soft": "#6f5d18",
    "success": "#6ee787",
    "danger": "#ff5f73",
    "danger_soft": "#5b2632",
}


APP_QSS = f"""
QWidget {{
    background: {COLORS["surface"]};
    color: {COLORS["text"]};
    font-family: "Segoe UI", Arial, sans-serif;
    font-size: 12px;
    selection-background-color: {COLORS["accent_soft"]};
    selection-color: {COLORS["text"]};
}}

QLabel {{
    background: transparent;
}}

QLabel#Title {{
    color: {COLORS["text"]};
    font-size: 15px;
    font-weight: 800;
}}

QLabel#Muted {{
    color: {COLORS["muted"]};
}}

QLabel#DebugValue {{
    color: {COLORS["text"]};
    font-weight: 700;
}}

QLabel#SectionTitle,
QLabel#StageHeader,
QLabel#EvolutionGraphStageHeader {{
    color: {COLORS["focus"]};
    background: transparent;
    font-weight: 800;
}}

QFrame#SelectedDigimonHeader,
QFrame#EditorSection,
QFrame#EvolutionEditorSection,
QWidget#StageHeaderPanel,
QWidget#EvolutionNode {{
    background: {COLORS["panel"]};
    border: 1px solid {COLORS["line"]};
    border-radius: 8px;
}}

QFrame#SelectedDigimonHeader {{
    border-top-color: {COLORS["accent"]};
}}

QLabel#SelectedDigimonSprite {{
    background: {COLORS["surface_alt"]};
    border: 1px solid {COLORS["line"]};
    border-radius: 7px;
    color: {COLORS["muted"]};
    font-size: 10px;
}}

QLabel#SelectedDigimonTitle {{
    background: transparent;
    color: {COLORS["text"]};
    font-size: 17px;
    font-weight: 800;
}}

QLabel#SelectedDigimonStatus,
QLabel#ValidationSummary,
QLabel#VisualImportStatus {{
    background: {COLORS["surface_alt"]};
    border: 1px solid {COLORS["line"]};
    border-radius: 7px;
    padding: 5px 8px;
    color: {COLORS["muted"]};
    font-weight: 800;
}}

QLabel#SelectedDigimonStatus[state="ok"],
QLabel#ValidationSummary[state="ok"] {{
    color: {COLORS["success"]};
    border-color: #2f7a48;
}}

QLabel#SelectedDigimonStatus[state="warning"],
QLabel#ValidationSummary[state="warning"],
QLabel#VisualImportStatus[state="pending"] {{
    color: {COLORS["focus"]};
    border-color: {COLORS["focus_soft"]};
}}

QLabel#SelectedDigimonStatus[state="error"],
QLabel#ValidationSummary[state="error"],
QLabel#VisualImportStatus[state="error"] {{
    color: {COLORS["danger"]};
    border-color: {COLORS["danger_soft"]};
}}

QWidget#DebugHeader {{
    background: {COLORS["panel"]};
    border-bottom: 1px solid {COLORS["accent_soft"]};
}}

QWidget#StageCompleteStar {{
    background: transparent;
}}

QWidget#EvolutionNode[selected="true"] {{
    background: {COLORS["panel_hot"]};
    border-color: {COLORS["focus"]};
}}

QLabel#EvolutionNodeName {{
    background: transparent;
    font-size: 11px;
    font-weight: 800;
}}

QPushButton {{
    background: {COLORS["panel_alt"]};
    border: 1px solid {COLORS["line"]};
    border-radius: 7px;
    padding: 7px 11px;
    font-weight: 700;
}}

QPushButton:hover {{
    background: {COLORS["panel_hot"]};
    border-color: {COLORS["accent"]};
}}

QPushButton:pressed {{
    background: {COLORS["accent_soft"]};
    border-color: {COLORS["accent"]};
}}

QPushButton:focus {{
    border-color: {COLORS["focus"]};
}}

QPushButton:disabled {{
    color: {COLORS["subtle"]};
    background: #0b1018;
    border-color: {COLORS["line_soft"]};
}}

QPushButton#PrimaryButton {{
    background: #123e52;
    border-color: {COLORS["accent_soft"]};
    color: {COLORS["text"]};
}}

QPushButton#PrimaryButton:hover {{
    border-color: {COLORS["accent"]};
}}

QPushButton#DangerButton {{
    background: {COLORS["danger_soft"]};
    border-color: #8b3442;
}}

QPushButton#DangerButton:hover {{
    border-color: {COLORS["danger"]};
}}

QGroupBox {{
    background: {COLORS["panel"]};
    border: 1px solid {COLORS["line"]};
    border-radius: 8px;
    margin-top: 10px;
    padding-top: 8px;
    font-weight: 800;
}}

QGroupBox::title {{
    subcontrol-origin: margin;
    subcontrol-position: top left;
    left: 10px;
    padding: 0 5px;
    color: {COLORS["focus"]};
}}

QSpinBox,
QComboBox,
QLineEdit,
QPlainTextEdit {{
    background: {COLORS["surface_alt"]};
    color: {COLORS["text"]};
    border: 1px solid {COLORS["line"]};
    border-radius: 7px;
    padding: 5px 8px;
    min-height: 24px;
}}

QSpinBox:hover,
QComboBox:hover,
QLineEdit:hover,
QPlainTextEdit:hover {{
    border-color: {COLORS["accent"]};
}}

QSpinBox:focus,
QComboBox:focus,
QLineEdit:focus,
QPlainTextEdit:focus {{
    border-color: {COLORS["focus"]};
}}

QProgressBar {{
    background: {COLORS["surface_alt"]};
    border: 1px solid {COLORS["line"]};
    border-radius: 6px;
    height: 13px;
    text-align: center;
}}

QProgressBar::chunk {{
    background: {COLORS["accent"]};
    border-radius: 5px;
}}

QComboBox QAbstractItemView {{
    background: {COLORS["panel"]};
    color: {COLORS["text"]};
    border: 1px solid {COLORS["line"]};
    selection-background-color: {COLORS["accent_soft"]};
    selection-color: {COLORS["text"]};
}}

QListWidget,
QTableWidget {{
    background: {COLORS["surface_alt"]};
    color: {COLORS["text"]};
    border: 1px solid {COLORS["line"]};
    border-radius: 8px;
    padding: 4px;
    outline: 0;
}}

QListWidget::item {{
    border-radius: 5px;
    padding: 7px 8px;
}}

QListWidget::item:hover,
QTableWidget::item:hover {{
    background: {COLORS["panel_hot"]};
}}

QListWidget::item:selected,
QTableWidget::item:selected {{
    background: {COLORS["accent_soft"]};
    color: {COLORS["text"]};
}}

QHeaderView::section {{
    background: {COLORS["panel"]};
    color: {COLORS["muted"]};
    border: none;
    border-bottom: 1px solid {COLORS["line"]};
    padding: 7px 8px;
    font-weight: 800;
}}

QTableWidget {{
    gridline-color: {COLORS["line_soft"]};
}}

QTableWidget::item {{
    padding: 6px 8px;
}}

QDialogButtonBox QPushButton {{
    min-width: 72px;
}}

QToolButton#BabyChoiceCard {{
    background: {COLORS["panel"]};
    border: 1px solid {COLORS["line"]};
    border-radius: 8px;
    padding: 8px 6px;
    font-size: 11px;
    font-weight: 800;
}}

QToolButton#BabyChoiceCard:hover {{
    border-color: {COLORS["accent"]};
}}

QToolButton#BabyChoiceCard:checked {{
    background: {COLORS["panel_hot"]};
    border-color: {COLORS["focus"]};
}}

QToolTip {{
    background: {COLORS["panel"]};
    color: {COLORS["text"]};
    border: 1px solid {COLORS["accent_soft"]};
    padding: 5px 7px;
}}

QCheckBox {{
    spacing: 8px;
    font-weight: 700;
}}

QCheckBox::indicator {{
    width: 16px;
    height: 16px;
    border: 1px solid {COLORS["line"]};
    border-radius: 5px;
    background: {COLORS["surface_alt"]};
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
    background: {COLORS["surface_alt"]};
    width: 10px;
    margin: 0;
}}

QScrollBar::handle:vertical {{
    background: {COLORS["accent_soft"]};
    border-radius: 5px;
    min-height: 40px;
}}

QScrollBar::handle:vertical:hover {{
    background: {COLORS["accent_pressed"]};
}}

QScrollBar:horizontal {{
    background: {COLORS["surface_alt"]};
    height: 10px;
    margin: 0;
}}

QScrollBar::handle:horizontal {{
    background: {COLORS["accent_soft"]};
    border-radius: 5px;
    min-width: 40px;
}}

QScrollBar::handle:horizontal:hover {{
    background: {COLORS["accent_pressed"]};
}}

QScrollBar::add-line,
QScrollBar::sub-line {{
    width: 0;
    height: 0;
}}

QMenu {{
    background: {COLORS["panel"]};
    border: 1px solid {COLORS["line"]};
}}

QMenu::item {{
    padding: 6px 18px;
}}

QMenu::item:selected {{
    background: {COLORS["accent_soft"]};
}}

QPlainTextEdit#SelectedValidationOutput {{
    background: {COLORS["surface_alt"]};
    border-color: {COLORS["line"]};
    color: {COLORS["text"]};
}}

QTabWidget::pane {{
    border: 1px solid {COLORS["line"]};
    border-radius: 8px;
    background: {COLORS["panel"]};
}}

QTabBar::tab {{
    background: {COLORS["surface_alt"]};
    color: {COLORS["muted"]};
    border: 1px solid {COLORS["line"]};
    border-bottom: none;
    padding: 7px 11px;
    margin-right: 3px;
    border-top-left-radius: 7px;
    border-top-right-radius: 7px;
    font-weight: 700;
}}

QTabBar::tab:selected {{
    background: {COLORS["panel_hot"]};
    color: {COLORS["text"]};
    border-color: {COLORS["focus"]};
}}
"""
