"""Colours, metrics and the stylesheet built from them.

The palette is the one the previous version already shipped; the additions
(switch, segmented control, colour labels) extend it rather than replacing it,
so the redesign still looks like the same program.
"""
from __future__ import annotations

# -- surfaces ---------------------------------------------------------
GROUND = "#0B0E14"
PANEL = "#111620"
BAR = "#10151E"
SUNKEN = "#080B10"
CARD = "#151B26"
CARD_HOVER = "#192130"
CONTROL = "#171D29"
CONTROL_HOVER = "#202838"
INPUT = "#0C1017"

# -- borders ----------------------------------------------------------
LINE = "#222A38"
LINE_CONTROL = "#293244"
LINE_COMBO = "#2B3547"
LINE_CARD = "#242D3D"
LINE_CARD_SET = "#343B58"
LINE_TABLE = "#263044"

# -- accent -----------------------------------------------------------
ACCENT = "#7357F5"
ACCENT_HOVER = "#8369FA"
ACCENT_BORDER = "#846CFA"
ACCENT_DIM = "#5E4CBD"
SELECTED_FILL = "#2A2348"
SELECTED_LINE = "#4B3E86"
KEYCAP_FILL = "#252040"
KEYCAP_LINE = "#51438C"
KEYCAP_TEXT = "#C9BBFF"

# -- text -------------------------------------------------------------
TEXT_TITLE = "#F5F7FF"
TEXT = "#E8ECF6"
TEXT_BUTTON = "#C7CEDC"
TEXT_SECOND = "#AEB7C9"
TEXT_CAPTION = "#778298"
TEXT_FAINT = "#68738A"
TEXT_HINT = "#596479"

# -- status -----------------------------------------------------------
OK = "#66D9A8"
WARN = "#E4B86A"
ERROR = "#F27D88"
REVIEW = "#83D8C5"
REVIEW_FILL = "#13242A"
REVIEW_LINE = "#28505A"
UNDO = "#CDBFFF"
UNDO_FILL = "#1D1930"
UNDO_LINE = "#42366B"

#: Colour labels, in the order the keyboard shortcuts Alt+1..5 assign them.
LABEL_COLOURS = {
    "red": "#F27D88",
    "yellow": "#E4B86A",
    "green": "#66D9A8",
    "blue": "#63A6F0",
    "purple": "#A78BFA",
}

FONT_STACK = '"Microsoft YaHei UI", "Segoe UI", "PingFang SC", "Noto Sans CJK SC", sans-serif'
MONO_STACK = '"Cascadia Mono", "Consolas", "DejaVu Sans Mono", monospace'

#: Height, compact padding and base font per density. English strings run about
#: 60% longer than Chinese, which is what "roomy" buys room for.
DENSITY = {
    "compact": {"button": 30, "compact": 26, "icon": 32, "font": 12, "gap": 7, "pad": 12},
    "standard": {"button": 36, "compact": 29, "icon": 36, "font": 13, "gap": 9, "pad": 15},
    "roomy": {"button": 40, "compact": 32, "icon": 40, "font": 14, "gap": 11, "pad": 18},
}


def metrics(density: str = "standard") -> dict:
    return DENSITY.get(density, DENSITY["standard"])


def stylesheet(density: str = "standard") -> str:
    m = metrics(density)
    return f"""
* {{ font-family: {FONT_STACK}; font-size: {m['font']}px; color: {TEXT}; }}
QWidget#root, QDialog {{ background: {GROUND}; }}
QToolTip {{ background: #222938; color: {TEXT}; border: 1px solid #3B465A; padding: 5px; }}

QFrame#panel, QFrame#sidebar {{ background: {PANEL}; border: 1px solid {LINE}; border-radius: 14px; }}
QFrame#panel {{ border-radius: 16px; }}
QFrame#toolsBar, QFrame#statusStrip {{ background: {BAR}; border: 1px solid #202837; border-radius: 10px; }}
QFrame#card {{ background: {CARD}; border: 1px solid {LINE_CARD}; border-radius: 11px; }}
QStackedWidget#previewStack, QWidget#previewStack {{ background: {SUNKEN}; border: none; border-radius: 15px; }}
QFrame#filmstripBar {{ background: {INPUT}; border: none; border-top: 1px solid #1E2634; }}
QFrame#metadataBar {{ background: {PANEL}; border: none; border-top: 1px solid {LINE};
    border-bottom-left-radius: 15px; border-bottom-right-radius: 15px; }}
QFrame#separator {{ background: {LINE}; max-width: 1px; border: none; }}

QLabel#brand {{ font-size: {m['font'] + 7}px; font-weight: 800; color: {TEXT_TITLE}; }}
/* Qt stylesheets have no letter-spacing; the window sets it on the font. */
QLabel#brandSubtitle {{ font-size: 8px; color: {TEXT_FAINT}; }}
QLabel#sideTitle {{ font-size: {m['font'] + 3}px; font-weight: 700; color: #F0F2F9; }}
QLabel#sideSubtitle {{ font-size: {m['font'] - 2}px; color: #747F94; }}
QLabel#dialogTitle {{ font-size: {m['font'] + 7}px; font-weight: 700; color: #F1F3F9; }}
QLabel#dialogSubtitle {{ color: #7F8A9F; font-size: {m['font'] - 1}px; }}
QLabel#sectionTitle {{ font-size: {m['font'] + 1}px; font-weight: 700; color: #F0F2F9; }}
QLabel#filename {{ font-size: {m['font'] + 1}px; font-weight: 700; color: #ECF0F9; }}
QLabel#fileDetail {{ font-size: {m['font'] - 2}px; color: {TEXT_CAPTION}; }}
QLabel#caption {{ font-size: {m['font'] - 2}px; color: {TEXT_CAPTION}; }}
QLabel#mono {{ font-family: {MONO_STACK}; color: {TEXT_SECOND}; }}
QLabel#keyboardHint {{ font-size: {m['font'] - 3}px; color: {TEXT_HINT}; padding-top: 2px; }}
QLabel#emptyIcon {{ font-size: 52px; color: #6651D4; }}
QLabel#emptyTitle {{ font-size: {m['font'] + 9}px; font-weight: 700; color: #E9ECF4; }}
QLabel#emptyText {{ color: #788399; }}
QLabel#counterPill {{ background: #1C2230; border: 1px solid #2C3547; border-radius: 11px;
    padding: 4px 10px; color: #AEB7CB; font-weight: 700; }}
QLabel#badge {{ background: #1E2A38; border: 1px solid #2F4256; border-radius: 5px;
    padding: 1px 6px; color: #8FA3B8; font-size: {m['font'] - 4}px; font-weight: 700; }}
QLabel#badgeAccent {{ background: {SELECTED_FILL}; border: 1px solid {SELECTED_LINE};
    border-radius: 6px; padding: 2px 7px; color: {KEYCAP_TEXT}; font-size: {m['font'] - 3}px;
    font-weight: 800; }}
QLabel#keyCap {{ background: {KEYCAP_FILL}; border: 1px solid {KEYCAP_LINE}; border-radius: 9px;
    color: {KEYCAP_TEXT}; font-size: {m['font'] + 1}px; font-weight: 800;
    min-width: 30px; min-height: 30px; }}
QLabel#bindingName {{ font-size: {m['font'] - 1}px; font-weight: 700; color: #DCE1EC; }}
QLabel#bindingPath {{ font-size: {m['font'] - 3}px; color: #69758B; }}

QLineEdit, QLineEdit#sourceDisplay {{ background: {INPUT}; border: 1px solid {LINE_COMBO};
    border-radius: 8px; padding: 6px 11px; color: {TEXT_SECOND}; }}
QLineEdit:focus {{ border-color: {ACCENT}; }}
QLineEdit#sourceDisplay {{ background: {PANEL}; border-color: {LINE}; border-radius: 10px; }}

QPushButton {{ min-height: {m['button']}px; padding: 0 {m['pad']}px; border-radius: 9px;
    font-weight: 600; background: {CONTROL}; border: 1px solid {LINE_CONTROL};
    color: {TEXT_BUTTON}; }}
QPushButton:hover {{ background: {CONTROL_HOVER}; border-color: {ACCENT_DIM}; }}
QPushButton:disabled {{ background: #141923; border-color: #202736; color: #545E70; }}
QPushButton#primaryButton {{ background: {ACCENT}; border: 1px solid {ACCENT_BORDER};
    color: #FFFFFF; padding: 0 18px; }}
QPushButton#primaryButton:hover {{ background: {ACCENT_HOVER}; }}
QPushButton#compactButton {{ min-height: {m['compact']}px; padding: 0 11px;
    font-size: {m['font'] - 2}px; }}
QPushButton#ghostButton {{ background: {CONTROL}; }}
QPushButton#dangerButton {{ background: #2E1E22; border-color: #57323A; color: #D9909A; }}
QPushButton#undoButton {{ background: {UNDO_FILL}; border: 1px solid {UNDO_LINE};
    color: {UNDO}; min-height: {m['button']}px; }}
QPushButton#undoButton:hover {{ background: #29213F; border-color: #7058B7; }}
QPushButton#undoButton:disabled {{ background: #151923; border-color: #242A37; color: #545E70; }}
QPushButton#reviewButton {{ background: {REVIEW_FILL}; border: 1px solid {REVIEW_LINE};
    color: {REVIEW}; min-height: {m['button']}px; }}
QPushButton#reviewButton:hover, QPushButton#reviewButton[active="true"] {{
    background: #19343A; border-color: #3C8E83; }}

QPushButton#segment {{ min-height: 28px; padding: 0 12px; border-radius: 6px;
    border: 1px solid transparent; background: transparent; color: #8B95A9;
    font-size: {m['font'] - 2}px; font-weight: 600; }}
QPushButton#segment:hover {{ color: {TEXT_BUTTON}; }}
QPushButton#segment:checked {{ background: {SELECTED_FILL}; border-color: {SELECTED_LINE};
    color: {KEYCAP_TEXT}; font-weight: 700; }}
QFrame#segmentBar {{ background: {INPUT}; border: 1px solid #232C3C; border-radius: 8px; }}
QPushButton#segmentPrimary:checked {{ background: {ACCENT}; border-color: {ACCENT_BORDER};
    color: #FFFFFF; }}

QToolButton#headerIconButton {{ background: {CARD}; border: 1px solid #283144; border-radius: 10px;
    min-width: {m['icon']}px; min-height: {m['icon']}px; font-size: 16px; color: #BDC6D8; }}
QToolButton#headerIconButton:hover {{ background: {CONTROL_HOVER}; border-color: #7057E9;
    color: #FFFFFF; }}
QToolButton#navButton {{ background: #1A202D; border: 1px solid #2A3345; border-radius: 9px;
    min-width: 34px; min-height: 34px; font-size: 18px; color: #DCE2EF; }}
QToolButton#navButton:hover {{ background: #262E40; border-color: #6B55DE; }}
QToolButton#navButton:disabled {{ color: #444D5F; background: #141923; border-color: #202736; }}
QToolButton#roundButton {{ background: #1F2634; border: 1px solid #303A4D; border-radius: 16px;
    min-width: 32px; min-height: 32px; color: {TEXT}; font-size: {m['font'] - 3}px; }}
QToolButton#roundButton:hover {{ background: #2B3446; border-color: #6752D8; }}
QToolButton#iconButton {{ background: transparent; border: none; border-radius: 7px;
    min-width: 28px; min-height: 28px; color: #8792A8; font-size: 16px; font-weight: 700; }}
QToolButton#iconButton:hover {{ background: {SELECTED_FILL}; color: {KEYCAP_TEXT}; }}
QToolButton#browseButton {{ background: #202737; border: 1px solid #303A4D; border-radius: 7px;
    min-width: 52px; min-height: {m['compact']}px; color: #BEC6D6; }}

QComboBox {{ background: {CONTROL}; border: 1px solid {LINE_COMBO}; border-radius: 7px;
    padding: 4px 9px; color: #D2D8E5; min-height: {m['compact'] - 8}px; }}
QComboBox:hover {{ border-color: #5F4CC1; }}
QComboBox::drop-down {{ border: none; width: 18px; }}
QComboBox QAbstractItemView {{ background: {CONTROL}; border: 1px solid #354057;
    selection-background-color: #624CC8; }}
QSpinBox, QDoubleSpinBox {{ background: {INPUT}; border: 1px solid {LINE_COMBO};
    border-radius: 7px; padding: 4px 8px; color: #D6DCE9; min-height: {m['compact'] - 8}px; }}

QCheckBox {{ color: {TEXT_SECOND}; spacing: 7px; }}
QCheckBox::indicator {{ width: 15px; height: 15px; border: 1px solid #3A455A; border-radius: 4px;
    background: {PANEL}; }}
QCheckBox::indicator:checked {{ background: {ACCENT}; border-color: #8C76F7; }}
QRadioButton {{ color: {TEXT_SECOND}; spacing: 8px; }}
QRadioButton::indicator {{ width: 15px; height: 15px; border: 1px solid #3A455A;
    border-radius: 8px; background: {PANEL}; }}
QRadioButton::indicator:checked {{ background: {ACCENT}; border-color: #8C76F7; }}

QFrame#bindingCard {{ background: {CARD}; border: 1px solid {LINE_CARD}; border-radius: 11px; }}
QFrame#bindingCard[configured="true"] {{ border-color: {LINE_CARD_SET}; }}
QFrame#bindingCard[current="true"] {{ background: {CARD_HOVER}; border-color: #4F467A; }}
QFrame#bindingCard:hover {{ background: {CARD_HOVER}; border-color: #4F467A; }}
QFrame#settingsRow {{ background: #121823; border: 1px solid #242C3B; border-radius: 10px; }}
QFrame#settingsCard {{ background: {PANEL}; border: 1px solid {LINE}; border-radius: 13px; }}
QLabel#rowNumber {{ color: #606C82; font-size: {m['font'] - 2}px; font-weight: 700; }}

QLabel#statusBar {{ color: #7A8599; font-size: {m['font'] - 2}px; padding: 0 4px; }}
QLabel#statusBar[tone="success"] {{ color: {OK}; }}
QLabel#statusBar[tone="warning"] {{ color: {WARN}; }}
QLabel#statusBar[tone="error"] {{ color: {ERROR}; }}
QProgressBar {{ background: #1C2230; border: none; border-radius: 3px; max-height: 6px;
    text-align: center; color: transparent; }}
QProgressBar::chunk {{ background: {ACCENT}; border-radius: 3px; }}
QProgressBar#quotaBar::chunk {{ background: {OK}; }}
QProgressBar#quotaBar[full="true"]::chunk {{ background: {WARN}; }}

QFrame#videoControls {{ background: {BAR}; border: none; border-top: 1px solid #242B39; }}
QLabel#timeLabel {{ color: #8B96AA; font-size: {m['font'] - 3}px; min-width: 86px; }}
QSlider::groove:horizontal {{ height: 4px; background: #2B3342; border-radius: 2px; }}
QSlider::sub-page:horizontal {{ background: #765AF4; border-radius: 2px; }}
QSlider::handle:horizontal {{ background: #E9E4FF; width: 12px; margin: -4px 0; border-radius: 6px; }}

QTableWidget, QTextEdit, QPlainTextEdit {{ background: {BAR}; alternate-background-color: {CARD};
    border: 1px solid {LINE_TABLE}; gridline-color: {LINE_TABLE};
    selection-background-color: #5340A8; }}
QHeaderView::section {{ background: #1A2130; color: #AEB8CA; padding: 6px; border: none;
    border-right: 1px solid {LINE_COMBO}; }}
QListWidget {{ background: {SUNKEN}; border: none; }}
QListWidget#grid {{ background: {SUNKEN}; border: none; padding: 6px; }}
QListWidget#grid::item {{ border: 1px solid transparent; border-radius: 8px; margin: 3px;
    color: #8B95A9; }}
QListWidget#grid::item:selected {{ border: 2px solid {ACCENT}; background: {SELECTED_FILL};
    color: {KEYCAP_TEXT}; }}
QListWidget#filmstrip {{ background: transparent; border: none; }}
QListWidget#filmstrip::item {{ border: 2px solid transparent; border-radius: 7px; margin: 2px; }}
QListWidget#filmstrip::item:selected {{ border-color: {ACCENT}; background: {SELECTED_FILL}; }}
QListWidget#navList::item {{ padding: 8px 10px; border-radius: 9px; color: #9BA5B9; }}
QListWidget#navList::item:selected {{ background: {SELECTED_FILL}; color: {KEYCAP_TEXT}; }}

QScrollArea {{ background: transparent; border: none; }}
QScrollArea > QWidget > QWidget {{ background: transparent; }}
QScrollBar:vertical {{ background: transparent; width: 9px; margin: 2px; }}
QScrollBar::handle:vertical {{ background: #343D50; border-radius: 4px; min-height: 32px; }}
QScrollBar::add-line:vertical, QScrollBar::sub-line:vertical {{ height: 0; }}
QScrollBar:horizontal {{ background: transparent; height: 9px; margin: 2px; }}
QScrollBar::handle:horizontal {{ background: #343D50; border-radius: 4px; min-width: 32px; }}
QScrollBar::add-line:horizontal, QScrollBar::sub-line:horizontal {{ width: 0; }}

QTabWidget::pane {{ border: 1px solid {LINE}; border-radius: 10px; }}
QTabBar::tab {{ background: transparent; color: #8B95A9; padding: 7px 14px; border-radius: 7px;
    margin-right: 3px; }}
QTabBar::tab:selected {{ background: {SELECTED_FILL}; color: {KEYCAP_TEXT}; }}
QMenu {{ background: {CONTROL}; border: 1px solid #354057; padding: 4px; }}
QMenu::item {{ padding: 6px 18px; border-radius: 6px; }}
QMenu::item:selected {{ background: #624CC8; }}
"""
