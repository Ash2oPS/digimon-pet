from __future__ import annotations


COLORS = {
    "surface": "#050b13",
    "surface_alt": "#091827",
    "panel": "#0d1a29",
    "panel_alt": "#12263b",
    "panel_hot": "#173653",
    "line": "#2e5876",
    "line_soft": "#18324a",
    "text": "#f6fbff",
    "muted": "#9ec5d8",
    "subtle": "#5f7f95",
    "accent": "#00d8ff",
    "accent_soft": "#0b6680",
    "accent_pressed": "#0b9ec0",
    "accent_alt": "#ff5a2f",
    "focus": "#ffdf4a",
    "focus_soft": "#725f20",
    "success": "#7dff8a",
    "danger": "#ff5f73",
    "danger_soft": "#5b2632",
}


APP_QSS = f"""
QWidget {{
    background: {COLORS["surface"]};
    color: {COLORS["text"]};
    font-family: "Cascadia Mono", "Consolas", "Courier New", "Segoe UI", Arial, sans-serif;
    font-size: 13px;
    selection-background-color: {COLORS["accent_soft"]};
    selection-color: {COLORS["text"]};
}}

QLabel {{
    background: transparent;
}}

QLabel#Title {{
    color: {COLORS["text"]};
    font-size: 16px;
    font-weight: 900;
}}

QLabel#Muted {{
    color: {COLORS["muted"]};
}}

QLabel#DebugValue {{
    color: {COLORS["text"]};
    font-weight: 800;
}}

QLabel#SectionTitle,
QLabel#StageHeader,
QLabel#EvolutionGraphStageHeader {{
    color: {COLORS["focus"]};
    background: transparent;
    font-weight: 900;
}}

QFrame#SelectedDigimonHeader,
QFrame#EditorSection,
QFrame#EvolutionEditorSection,
QWidget#StageHeaderPanel,
QWidget#EvolutionNode {{
    background: {COLORS["panel"]};
    border: 2px solid {COLORS["line"]};
    border-radius: 2px;
}}

QFrame#SelectedDigimonHeader {{
    border-top-color: {COLORS["accent"]};
}}

QLabel#SelectedDigimonSprite {{
    background: {COLORS["surface_alt"]};
    border: 2px solid {COLORS["line"]};
    border-radius: 2px;
    color: {COLORS["muted"]};
    font-size: 10px;
}}

QLabel#SelectedDigimonTitle {{
    background: transparent;
    color: {COLORS["text"]};
    font-size: 17px;
    font-weight: 900;
}}

QLabel#SelectedDigimonStatus,
QLabel#ValidationSummary,
QLabel#VisualImportStatus {{
    background: {COLORS["surface_alt"]};
    border: 2px solid {COLORS["line"]};
    border-radius: 2px;
    padding: 5px 8px;
    color: {COLORS["muted"]};
    font-weight: 900;
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
    border-bottom: 2px solid {COLORS["accent"]};
}}

QFrame#StatsHeader,
QFrame#StatsPanel,
QFrame#StatsMetricCard,
QFrame#EvolutionRequirementCard {{
    background: {COLORS["panel"]};
    border: 2px solid {COLORS["line"]};
    border-radius: 2px;
}}

QFrame#EvolutionIntelPanel {{
    background: {COLORS["surface"]};
    border: 2px solid {COLORS["line"]};
    border-radius: 2px;
}}

QToolButton#EvolutionIntelCard {{
    background: {COLORS["panel"]};
    border: 2px solid {COLORS["line"]};
    border-radius: 2px;
    padding: 5px 6px;
    text-align: center;
    font-weight: 900;
}}

QToolButton#EvolutionIntelCard:hover {{
    background: {COLORS["panel_hot"]};
    border-color: {COLORS["accent"]};
}}

QToolButton#EvolutionIntelCard:checked {{
    background: {COLORS["panel_hot"]};
    border-color: {COLORS["focus"]};
}}

QFrame#StatsHeader {{
    border-top-color: {COLORS["accent"]};
}}

QLabel#StatsPortrait {{
    background: {COLORS["surface_alt"]};
    border: 2px solid {COLORS["line"]};
    border-radius: 2px;
    color: {COLORS["muted"]};
}}

QScrollArea#FriendLineageScroll,
QScrollArea#FriendLineageScroll QWidget {{
    background: {COLORS["surface_alt"]};
}}

QLabel#FriendLineageSprite {{
    background: {COLORS["panel"]};
    border: 1px solid {COLORS["line_soft"]};
    border-radius: 2px;
}}

QLabel#FriendLineageName {{
    color: {COLORS["text"]};
    font-size: 9px;
    font-weight: 800;
}}

QLabel#FriendLineageArrow {{
    color: {COLORS["focus"]};
    font-size: 10px;
    font-weight: 900;
}}

QLabel#StatsStage {{
    color: {COLORS["focus"]};
    font-weight: 900;
}}

QLabel#StatsMetricValue,
QLabel#StatsBarValue {{
    color: {COLORS["text"]};
    font-weight: 900;
}}

QFrame#EvolutionStatRequirement {{
    background: {COLORS["surface_alt"]};
    border: 2px solid {COLORS["line_soft"]};
    border-radius: 2px;
}}

QLabel#EvolutionIntelSummary {{
    background: {COLORS["panel_hot"]};
    border: 2px solid {COLORS["accent_soft"]};
    border-radius: 2px;
    color: {COLORS["focus"]};
    font-weight: 900;
    padding: 5px 8px;
}}

QLabel#EvolutionUnknownChip {{
    background: {COLORS["surface_alt"]};
    border: 2px solid {COLORS["line_soft"]};
    border-radius: 2px;
    color: {COLORS["muted"]};
    font-weight: 900;
    padding: 5px 5px;
}}

QLabel#EvolutionRequirementStatus {{
    background: {COLORS["surface_alt"]};
    border: 2px solid {COLORS["line"]};
    border-radius: 2px;
    padding: 2px 6px;
    font-weight: 900;
}}

QLabel#EvolutionRequirementStatus[state="ok"] {{
    color: {COLORS["success"]};
    border-color: #2f7a48;
}}

QLabel#EvolutionRequirementStatus[state="missing"] {{
    color: {COLORS["focus"]};
    border-color: {COLORS["focus_soft"]};
}}

QLabel#EvolutionRequirementStatus[state="unknown"] {{
    color: {COLORS["muted"]};
    border-color: {COLORS["line"]};
}}

QTabWidget#StatsTabs::pane {{
    background: {COLORS["surface"]};
}}

QProgressBar#StatsBar_hunger::chunk {{
    background: {COLORS["accent"]};
}}

QProgressBar#StatsBar_hunger,
QProgressBar#StatsBar_happiness,
QProgressBar#StatsBar_discipline,
QProgressBar#StatsBar_fatigue {{
    height: 4px;
    max-height: 4px;
}}

QProgressBar#StatsBar_happiness::chunk {{
    background: {COLORS["success"]};
}}

QProgressBar#StatsBar_discipline::chunk {{
    background: {COLORS["focus"]};
}}

QProgressBar#StatsBar_fatigue::chunk {{
    background: {COLORS["danger"]};
}}

QProgressBar#StatsCombatBar_hp,
QProgressBar#StatsCombatBar_mp,
QProgressBar#StatsCombatBar_offense,
QProgressBar#StatsCombatBar_defense,
QProgressBar#StatsCombatBar_speed,
QProgressBar#StatsCombatBar_brains {{
    height: 4px;
    max-height: 4px;
}}

QProgressBar#StatsCombatBar_hp::chunk,
QProgressBar#StatsCombatBar_mp::chunk {{
    background: {COLORS["accent"]};
}}

QProgressBar#StatsCombatBar_offense::chunk,
QProgressBar#StatsCombatBar_defense::chunk,
QProgressBar#StatsCombatBar_speed::chunk,
QProgressBar#StatsCombatBar_brains::chunk {{
    background: {COLORS["focus"]};
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
    font-weight: 900;
}}

QPushButton {{
    background: {COLORS["panel"]};
    border: 2px solid {COLORS["line"]};
    border-radius: 2px;
    padding: 7px 11px;
    color: {COLORS["focus"]};
    font-weight: 800;
}}

QPushButton:hover {{
    background: {COLORS["panel_alt"]};
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
    background: {COLORS["surface_alt"]};
    border-color: {COLORS["line_soft"]};
}}

QPushButton#PrimaryButton {{
    background: {COLORS["panel_alt"]};
    border-color: {COLORS["accent"]};
    color: {COLORS["text"]};
}}

QPushButton#PrimaryButton:hover {{
    border-color: {COLORS["accent"]};
}}

QPushButton#DangerButton {{
    background: {COLORS["danger_soft"]};
    border-color: {COLORS["danger"]};
}}

QPushButton#DangerButton:hover {{
    border-color: {COLORS["danger"]};
}}

QGroupBox {{
    background: {COLORS["panel"]};
    border: 2px solid {COLORS["line"]};
    border-radius: 2px;
    margin-top: 10px;
    padding-top: 8px;
    font-weight: 900;
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
    border: 2px solid {COLORS["line"]};
    border-radius: 2px;
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
    border: 2px solid {COLORS["line"]};
    border-radius: 1px;
    height: 4px;
    text-align: center;
}}

QProgressBar::chunk {{
    background: {COLORS["accent"]};
    border-radius: 0px;
}}

QComboBox QAbstractItemView {{
    background: {COLORS["panel"]};
    color: {COLORS["text"]};
    border: 2px solid {COLORS["line"]};
    selection-background-color: {COLORS["accent_soft"]};
    selection-color: {COLORS["text"]};
}}

QListWidget,
QTableWidget {{
    background: {COLORS["surface_alt"]};
    color: {COLORS["text"]};
    border: 2px solid {COLORS["line"]};
    border-radius: 2px;
    padding: 4px;
    outline: 0;
}}

QListWidget::item {{
    border-radius: 2px;
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
    border-bottom: 2px solid {COLORS["line"]};
    padding: 7px 8px;
    font-weight: 900;
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
    border: 2px solid {COLORS["line"]};
    border-radius: 2px;
    padding: 8px 6px;
    font-size: 11px;
    font-weight: 900;
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
    border: 2px solid {COLORS["accent_soft"]};
    padding: 5px 7px;
}}

QCheckBox {{
    spacing: 8px;
    font-weight: 800;
}}

QCheckBox::indicator {{
    width: 16px;
    height: 16px;
    border: 2px solid {COLORS["line"]};
    border-radius: 2px;
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
    border-radius: 2px;
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
    border-radius: 2px;
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
    border: 2px solid {COLORS["line"]};
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
    border: 2px solid {COLORS["line"]};
    border-radius: 2px;
    background: {COLORS["panel"]};
}}

QTabBar::tab {{
    background: {COLORS["surface_alt"]};
    color: {COLORS["muted"]};
    border: 2px solid {COLORS["line"]};
    border-bottom: none;
    padding: 6px 10px;
    margin-right: 2px;
    border-top-left-radius: 2px;
    border-top-right-radius: 2px;
    font-weight: 800;
}}

QTabBar::tab:selected {{
    background: {COLORS["panel_alt"]};
    color: {COLORS["focus"]};
    border-color: {COLORS["accent"]};
}}
"""
