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
    font-family: Segoe UI;
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

QLabel#StageHeader {{
    color: {COLORS["focus"]};
    background: {COLORS["panel"]};
    border: 1px solid #3a3938;
    border-radius: 6px;
    padding: 5px 8px;
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
"""

