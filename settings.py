import json
from pathlib import Path

from PySide6.QtCore import Qt
from PySide6.QtGui import QFontDatabase
from PySide6.QtWidgets import (
    QCheckBox,
    QComboBox,
    QDialog,
    QDoubleSpinBox,
    QFrame,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QMessageBox,
    QPushButton,
    QScrollArea,
    QSpinBox,
    QVBoxLayout,
    QWidget,
)

DATA_DIR = Path.home() / ".mosaic"
SETTINGS_FILE = DATA_DIR / "settings.json"

DEFAULT_SETTINGS = {
    "theme": "dark",
    "font_family": "System Default",
    "font_size": 11,
    "compact_mode": False,
    "show_timestamps": False,
    "show_token_counts": True,
    "send_on_enter": True,
    "auto_title": True,
    "confirm_delete": True,
    "active_mode": "chat",
    "last_model": "llama3.2",
    "ollama_url": "http://localhost:11434",
    "ollama_api_key": "",
    "chat_api_enabled": False,
    "chat_api_service": "none",
    "chat_api_key": "",
    "chat_api_base_url": "",
    "chat_api_confirm": False,
    "auto_start_ollama": True,
    "stream_responses": True,
    "smooth_responses": True,
    "smooth_typing_speed": "natural",
    "keep_alive": "5m",
    "request_timeout": 300,
    "temperature": 0.7,
    "top_p": 0.9,
    "num_ctx": 4096,
    "repeat_penalty": 1.1,
    "num_predict": -1,
    "web_search_always_on": False,
    "web_search_max_results": 5,
    "web_search_show_sources": True,
    "memory_enabled": True,
    "memory_limit": 20,
    "auto_memory": False,
    "cowork_allow_vision": True,
    "cowork_allow_cursor": True,
    "cowork_confirm_actions": True,
}

DARK_PALETTE = {
    "mode": "dark",
    "bg_root": "#0f1117",
    "bg_rail": "#0b0d12",
    "bg_sidebar": "#131620",
    "bg_card": "#181c28",
    "bg_elevated": "#1f2433",
    "bg_input": "#161923",
    "bg_code": "#11141d",
    "bg_code_header": "#191e2c",
    "border": "#262c3d",
    "border_subtle": "#1f2433",
    "text_primary": "#e6e9f2",
    "text_secondary": "#9aa3b8",
    "text_muted": "#687188",
    "accent": "#4f8cff",
    "accent_hover": "#669cff",
    "green": "#22c55e",
    "red": "#ef4444",
    "yellow": "#eab308",
    "orange": "#f97316",
    "purple": "#a855f7",
    "cyan": "#06b6d4",
}

LIGHT_PALETTE = {
    "mode": "light",
    "bg_root": "#f5f7fb",
    "bg_rail": "#eaedf4",
    "bg_sidebar": "#eef1f7",
    "bg_card": "#ffffff",
    "bg_elevated": "#e4e8f2",
    "bg_input": "#ffffff",
    "bg_code": "#f1f4f9",
    "bg_code_header": "#e5e9f2",
    "border": "#d5dce8",
    "border_subtle": "#e2e7f0",
    "text_primary": "#141824",
    "text_secondary": "#4b556b",
    "text_muted": "#7b849b",
    "accent": "#2563eb",
    "accent_hover": "#1d4ed8",
    "green": "#16a34a",
    "red": "#dc2626",
    "yellow": "#ca8a04",
    "orange": "#ea580c",
    "purple": "#9333ea",
    "cyan": "#0891b2",
}


def load_settings():
    DATA_DIR.mkdir(parents=True, exist_ok=True)
    merged = dict(DEFAULT_SETTINGS)
    if SETTINGS_FILE.exists():
        try:
            raw = json.loads(SETTINGS_FILE.read_text(encoding="utf-8"))
            if isinstance(raw, dict):
                merged.update(raw)
        except (OSError, json.JSONDecodeError):
            pass
    return merged


def save_settings(updates):
    DATA_DIR.mkdir(parents=True, exist_ok=True)
    current = load_settings()
    if isinstance(updates, dict):
        current.update(updates)
    SETTINGS_FILE.write_text(
        json.dumps(current, indent=2, ensure_ascii=False), encoding="utf-8"
    )
    return current


def get_palette(cfg=None):
    data = cfg if cfg is not None else load_settings()
    return dict(LIGHT_PALETTE if data.get("theme") == "light" else DARK_PALETTE)


def build_stylesheet(p):
    return f"""
    QWidget#root {{
        background-color: {p["bg_root"]};
        color: {p["text_primary"]};
    }}
    QWidget#modeRail {{
        background-color: {p["bg_rail"]};
        border-right: 1px solid {p["border_subtle"]};
    }}
    QToolButton#modeRailBtn {{
        background-color: transparent;
        color: {p["text_secondary"]};
        border: 1px solid transparent;
        border-radius: 10px;
        font-size: 11px;
        font-weight: 600;
        padding: 4px;
    }}
    QToolButton#modeRailBtn:hover {{
        background-color: {p["bg_elevated"]};
        color: {p["text_primary"]};
    }}
    QToolButton#modeRailBtn:checked {{
        background-color: {p["bg_elevated"]};
        color: {p["accent"]};
        border: 1px solid {p["accent"]};
    }}
    QWidget#sidebar {{
        background-color: {p["bg_sidebar"]};
        border-right: 1px solid {p["border_subtle"]};
    }}
    QLabel#brand {{
        font-size: 18px;
        font-weight: bold;
        color: {p["text_primary"]};
    }}
    QLabel#brandBadge {{
        background-color: {p["bg_elevated"]};
        color: {p["accent"]};
        border: 1px solid {p["border"]};
        border-radius: 6px;
        padding: 2px 7px;
        font-size: 10px;
        font-weight: bold;
    }}
    QLabel#chatTitle {{
        font-size: 15px;
        font-weight: bold;
        color: {p["text_primary"]};
    }}
    QLabel#sectionHeading {{
        font-size: 16px;
        font-weight: bold;
        color: {p["text_primary"]};
    }}
    QLabel#settingTitle {{
        font-size: 13px;
        font-weight: bold;
        color: {p["text_primary"]};
    }}
    QLabel#muted {{
        color: {p["text_muted"]};
        font-size: 12px;
    }}
    QFrame#sidebarDivider {{
        color: {p["border_subtle"]};
    }}
    QPushButton {{
        background-color: {p["bg_card"]};
        color: {p["text_primary"]};
        border: 1px solid {p["border"]};
        border-radius: 8px;
        padding: 6px 12px;
        font-size: 12px;
    }}
    QPushButton:hover {{
        background-color: {p["bg_elevated"]};
        border-color: {p["accent"]};
    }}
    QPushButton:disabled {{
        color: {p["text_muted"]};
        background-color: {p["bg_sidebar"]};
    }}
    QPushButton#newChat {{
        background-color: {p["accent"]};
        color: #ffffff;
        border: none;
        border-radius: 8px;
        padding: 9px 12px;
        font-weight: bold;
        font-size: 13px;
    }}
    QPushButton#newChat:hover {{
        background-color: {p["accent_hover"]};
    }}
    QPushButton#send {{
        background-color: {p["accent"]};
        color: #ffffff;
        border: none;
        border-radius: 10px;
        font-weight: bold;
        font-size: 13px;
    }}
    QPushButton#send:hover {{
        background-color: {p["accent_hover"]};
    }}
    QPushButton#send[stopping="true"] {{
        background-color: {p["red"]};
        color: #ffffff;
    }}
    QPushButton#iconBtn, QPushButton#miniBtn, QPushButton#msgActionBtn {{
        background-color: transparent;
        border: 1px solid transparent;
        border-radius: 7px;
        padding: 2px;
    }}
    QPushButton#iconBtn:hover, QPushButton#miniBtn:hover, QPushButton#msgActionBtn:hover {{
        background-color: {p["bg_elevated"]};
        border-color: {p["border"]};
    }}
    QPushButton#sidebarFooterBtn {{
        background-color: transparent;
        border: none;
        border-radius: 8px;
        text-align: left;
        padding: 8px 10px;
        color: {p["text_secondary"]};
        font-size: 13px;
    }}
    QPushButton#sidebarFooterBtn:hover {{
        background-color: {p["bg_elevated"]};
        color: {p["text_primary"]};
    }}
    QPushButton#webSearchBtn {{
        background-color: {p["bg_card"]};
        color: {p["text_secondary"]};
        border: 1px solid {p["border"]};
        border-radius: 10px;
        font-weight: 600;
    }}
    QPushButton#webSearchBtn:checked {{
        background-color: {p["bg_elevated"]};
        color: {p["accent"]};
        border: 1px solid {p["accent"]};
    }}
    QPushButton#promptCard {{
        background-color: {p["bg_card"]};
        color: {p["text_primary"]};
        border: 1px solid {p["border"]};
        border-radius: 10px;
        text-align: left;
        padding: 10px 12px;
        font-size: 12px;
    }}
    QPushButton#promptCard:hover {{
        background-color: {p["bg_elevated"]};
        border-color: {p["accent"]};
    }}
    QPushButton#chip {{
        background-color: {p["bg_elevated"]};
        color: {p["text_primary"]};
        border: 1px solid {p["border"]};
        border-radius: 12px;
        padding: 4px 10px;
        font-size: 11px;
    }}
    QLineEdit, QPlainTextEdit, QComboBox, QSpinBox, QDoubleSpinBox {{
        background-color: {p["bg_input"]};
        color: {p["text_primary"]};
        border: 1px solid {p["border"]};
        border-radius: 8px;
        padding: 6px 10px;
    }}
    QLineEdit:focus, QPlainTextEdit:focus, QComboBox:focus {{
        border: 1px solid {p["accent"]};
    }}
    QListWidget#chatList, QListWidget#memList {{
        background-color: transparent;
        border: none;
        outline: none;
    }}
    QListWidget#chatList::item {{
        padding: 8px 10px;
        border-radius: 8px;
        color: {p["text_secondary"]};
        margin-bottom: 2px;
    }}
    QListWidget#chatList::item:hover {{
        background-color: {p["bg_elevated"]};
        color: {p["text_primary"]};
    }}
    QListWidget#chatList::item:selected {{
        background-color: {p["bg_elevated"]};
        color: {p["text_primary"]};
        font-weight: bold;
    }}
    QScrollArea#chatScroll, QWidget#chatContainer, QScrollArea#settingsScroll, QWidget#settingsPage {{
        background-color: transparent;
        border: none;
    }}
    QFrame#userBubble {{
        background-color: {p["bg_card"]};
        border: 1px solid {p["border"]};
        border-radius: 12px;
    }}
    QFrame#settingsCard, QFrame#modeContextBar, QFrame#sourcesBox {{
        background-color: {p["bg_card"]};
        border: 1px solid {p["border"]};
        border-radius: 10px;
    }}
    QFrame#memoryNote {{
        background-color: {p["bg_elevated"]};
        border: 1px solid {p["border"]};
        border-radius: 10px;
    }}
    QLabel#memoryNoteText {{
        color: {p["text_secondary"]};
        font-size: 12px;
    }}
    QCheckBox {{
        color: {p["text_primary"]};
        spacing: 8px;
    }}
    """


class SettingsDialog(QDialog):

    def __init__(
        self,
        parent=None,
        available_models=None,
        on_manage_memories=None,
        on_export_all=None,
        on_clear_history=None,
    ):
        super().__init__(parent)
        self.setWindowTitle("Mosaic Settings")
        self.resize(620, 660)
        self.settings = load_settings()
        self.palette = get_palette(self.settings)
        self.setStyleSheet(build_stylesheet(self.palette))

        self._on_manage_memories = on_manage_memories
        self._on_export_all = on_export_all
        self._on_clear_history = on_clear_history

        outer = QVBoxLayout(self)
        outer.setContentsMargins(18, 16, 18, 16)
        outer.setSpacing(12)

        hdr = QLabel("Mosaic Studio Settings")
        hdr.setObjectName("sectionHeading")
        outer.addWidget(hdr)

        scroll = QScrollArea()
        scroll.setObjectName("settingsScroll")
        scroll.setWidgetResizable(True)
        scroll.setFrameShape(QFrame.NoFrame)

        page = QWidget()
        page.setObjectName("settingsPage")
        lay = QVBoxLayout(page)
        lay.setContentsMargins(0, 0, 6, 0)
        lay.setSpacing(12)

        # 1. Appearance
        app_card = QFrame()
        app_card.setObjectName("settingsCard")
        app_lay = QVBoxLayout(app_card)
        app_lay.setContentsMargins(14, 12, 14, 12)
        app_lay.setSpacing(8)
        t1 = QLabel("Appearance")
        t1.setObjectName("settingTitle")
        app_lay.addWidget(t1)

        row_theme = QHBoxLayout()
        row_theme.addWidget(QLabel("Theme:"))
        self.theme_box = QComboBox()
        self.theme_box.addItem("Dark Mode", "dark")
        self.theme_box.addItem("Light Mode", "light")
        idx = self.theme_box.findData(self.settings.get("theme", "dark"))
        if idx >= 0:
            self.theme_box.setCurrentIndex(idx)
        row_theme.addWidget(self.theme_box)

        row_theme.addSpacing(12)
        row_theme.addWidget(QLabel("Font Size:"))
        self.font_size_spin = QSpinBox()
        self.font_size_spin.setRange(9, 20)
        self.font_size_spin.setValue(int(self.settings.get("font_size", 11)))
        row_theme.addWidget(self.font_size_spin)
        row_theme.addStretch()
        app_lay.addLayout(row_theme)

        row_font = QHBoxLayout()
        row_font.addWidget(QLabel("Font Family:"))
        self.font_box = QComboBox()
        self.font_box.addItem("System Default")
        for fam in QFontDatabase.families():
            self.font_box.addItem(fam)
        cur_fam = self.settings.get("font_family", "System Default")
        fidx = self.font_box.findText(cur_fam)
        if fidx >= 0:
            self.font_box.setCurrentIndex(fidx)
        row_font.addWidget(self.font_box, 1)
        app_lay.addLayout(row_font)

        self.compact_cb = QCheckBox("Compact chat spacing")
        self.compact_cb.setChecked(bool(self.settings.get("compact_mode", False)))
        app_lay.addWidget(self.compact_cb)

        self.timestamps_cb = QCheckBox("Show message timestamps")
        self.timestamps_cb.setChecked(bool(self.settings.get("show_timestamps", False)))
        app_lay.addWidget(self.timestamps_cb)

        self.tokens_cb = QCheckBox("Show estimated token counts in sidebar")
        self.tokens_cb.setChecked(bool(self.settings.get("show_token_counts", True)))
        app_lay.addWidget(self.tokens_cb)
        lay.addWidget(app_card)

        # 2. Chat & Typing Experience
        chat_card = QFrame()
        chat_card.setObjectName("settingsCard")
        chat_lay = QVBoxLayout(chat_card)
        chat_lay.setContentsMargins(14, 12, 14, 12)
        chat_lay.setSpacing(8)
        t2 = QLabel("Chat & Response Typing Animation")
        t2.setObjectName("settingTitle")
        chat_lay.addWidget(t2)

        self.smooth_cb = QCheckBox(
            "Smooth responses (animate Llama's reply like someone is typing it instead of pasting chunks)"
        )
        self.smooth_cb.setChecked(bool(self.settings.get("smooth_responses", True)))
        self.smooth_cb.toggled.connect(self._on_smooth_toggled)
        chat_lay.addWidget(self.smooth_cb)

        speed_row = QHBoxLayout()
        speed_row.addSpacing(22)
        self.speed_lbl = QLabel("Typing Speed:")
        speed_row.addWidget(self.speed_lbl)
        self.speed_box = QComboBox()
        self.speed_box.addItem("Relaxed (human typing pace)", "relaxed")
        self.speed_box.addItem("Natural (smooth & balanced)", "natural")
        self.speed_box.addItem("Fast (rapid live typing)", "fast")
        sidx = self.speed_box.findData(self.settings.get("smooth_typing_speed", "natural"))
        if sidx >= 0:
            self.speed_box.setCurrentIndex(sidx)
        speed_row.addWidget(self.speed_box)
        speed_row.addStretch()
        chat_lay.addLayout(speed_row)
        self._on_smooth_toggled(self.smooth_cb.isChecked())

        self.stream_cb = QCheckBox("Stream tokens live from Ollama")
        self.stream_cb.setChecked(bool(self.settings.get("stream_responses", True)))
        chat_lay.addWidget(self.stream_cb)

        self.enter_send_cb = QCheckBox("Press Enter to send (Shift+Enter for new line)")
        self.enter_send_cb.setChecked(bool(self.settings.get("send_on_enter", True)))
        chat_lay.addWidget(self.enter_send_cb)

        self.auto_title_cb = QCheckBox("Automatically generate AI titles for new chats")
        self.auto_title_cb.setChecked(bool(self.settings.get("auto_title", True)))
        chat_lay.addWidget(self.auto_title_cb)

        self.confirm_del_cb = QCheckBox("Confirm before deleting chats")
        self.confirm_del_cb.setChecked(bool(self.settings.get("confirm_delete", True)))
        chat_lay.addWidget(self.confirm_del_cb)
        lay.addWidget(chat_card)

        # 3. Ollama Connection & Model Parameters
        oll_card = QFrame()
        oll_card.setObjectName("settingsCard")
        oll_lay = QVBoxLayout(oll_card)
        oll_lay.setContentsMargins(14, 12, 14, 12)
        oll_lay.setSpacing(8)
        t3 = QLabel("Ollama Engine & Model Parameters")
        t3.setObjectName("settingTitle")
        oll_lay.addWidget(t3)

        url_row = QHBoxLayout()
        url_row.addWidget(QLabel("Ollama URL:"))
        self.url_edit = QLineEdit(self.settings.get("ollama_url", "http://localhost:11434"))
        url_row.addWidget(self.url_edit, 1)
        oll_lay.addLayout(url_row)

        key_row = QHBoxLayout()
        key_row.addWidget(QLabel("Ollama / Web API Key:"))
        self.api_key_edit = QLineEdit(self.settings.get("ollama_api_key", ""))
        self.api_key_edit.setEchoMode(QLineEdit.Password)
        self.api_key_edit.setPlaceholderText("Optional — for Ollama Cloud or Web Search")
        key_row.addWidget(self.api_key_edit, 1)

        self.toggle_key_btn = QPushButton("Show")
        self.toggle_key_btn.setCheckable(True)
        self.toggle_key_btn.toggled.connect(self._toggle_api_key_visibility)
        key_row.addWidget(self.toggle_key_btn)
        oll_lay.addLayout(key_row)

        self.auto_start_cb = QCheckBox("Auto-start local Ollama server if not running")
        self.auto_start_cb.setChecked(bool(self.settings.get("auto_start_ollama", True)))
        oll_lay.addWidget(self.auto_start_cb)

        p_row1 = QHBoxLayout()
        p_row1.addWidget(QLabel("Temperature:"))
        self.temp_spin = QDoubleSpinBox()
        self.temp_spin.setRange(0.0, 2.0)
        self.temp_spin.setSingleStep(0.1)
        self.temp_spin.setValue(float(self.settings.get("temperature", 0.7)))
        p_row1.addWidget(self.temp_spin)

        p_row1.addSpacing(12)
        p_row1.addWidget(QLabel("Top P:"))
        self.top_p_spin = QDoubleSpinBox()
        self.top_p_spin.setRange(0.05, 1.0)
        self.top_p_spin.setSingleStep(0.05)
        self.top_p_spin.setValue(float(self.settings.get("top_p", 0.9)))
        p_row1.addWidget(self.top_p_spin)
        p_row1.addStretch()
        oll_lay.addLayout(p_row1)

        p_row2 = QHBoxLayout()
        p_row2.addWidget(QLabel("Context Window:"))
        self.ctx_spin = QSpinBox()
        self.ctx_spin.setRange(512, 131072)
        self.ctx_spin.setSingleStep(1024)
        self.ctx_spin.setValue(int(self.settings.get("num_ctx", 4096)))
        p_row2.addWidget(self.ctx_spin)

        p_row2.addSpacing(12)
        p_row2.addWidget(QLabel("Repeat Penalty:"))
        self.rep_spin = QDoubleSpinBox()
        self.rep_spin.setRange(0.8, 2.0)
        self.rep_spin.setSingleStep(0.05)
        self.rep_spin.setValue(float(self.settings.get("repeat_penalty", 1.1)))
        p_row2.addWidget(self.rep_spin)
        p_row2.addStretch()
        oll_lay.addLayout(p_row2)
        lay.addWidget(oll_card)

        # 4. Web Search & Memory
        wm_card = QFrame()
        wm_card.setObjectName("settingsCard")
        wm_lay = QVBoxLayout(wm_card)
        wm_lay.setContentsMargins(14, 12, 14, 12)
        wm_lay.setSpacing(8)
        t4 = QLabel("Web Search & Memory")
        t4.setObjectName("settingTitle")
        wm_lay.addWidget(t4)

        self.web_always_cb = QCheckBox("Enable Web Search by default on new chats")
        self.web_always_cb.setChecked(bool(self.settings.get("web_search_always_on", False)))
        wm_lay.addWidget(self.web_always_cb)

        self.show_sources_cb = QCheckBox("Show clickable Sources bar below replies")
        self.show_sources_cb.setChecked(bool(self.settings.get("web_search_show_sources", True)))
        wm_lay.addWidget(self.show_sources_cb)

        self.mem_enabled_cb = QCheckBox("Enable persistent Mosaic Memories across chats")
        self.mem_enabled_cb.setChecked(bool(self.settings.get("memory_enabled", True)))
        wm_lay.addWidget(self.mem_enabled_cb)

        self.auto_mem_cb = QCheckBox("Auto-learn facts from conversations")
        self.auto_mem_cb.setChecked(bool(self.settings.get("auto_memory", False)))
        wm_lay.addWidget(self.auto_mem_cb)

        data_row = QHBoxLayout()
        if self._on_manage_memories:
            mem_btn = QPushButton("Manage Memories...")
            mem_btn.clicked.connect(self._on_manage_memories)
            data_row.addWidget(mem_btn)
        if self._on_export_all:
            exp_btn = QPushButton("Export All Chats...")
            exp_btn.clicked.connect(self._on_export_all)
            data_row.addWidget(exp_btn)
        if self._on_clear_history:
            clr_btn = QPushButton("Clear All Chats")
            clr_btn.setStyleSheet(f"color: {self.palette['red']};")
            clr_btn.clicked.connect(self._confirm_clear_all)
            data_row.addWidget(clr_btn)
        data_row.addStretch()
        wm_lay.addLayout(data_row)
        lay.addWidget(wm_card)

        lay.addStretch()
        scroll.setWidget(page)
        outer.addWidget(scroll, 1)

        footer = QHBoxLayout()
        cancel_btn = QPushButton("Cancel")
        cancel_btn.clicked.connect(self.reject)
        save_btn = QPushButton("Save Settings")
        save_btn.setObjectName("send")
        save_btn.clicked.connect(self._save)
        footer.addStretch()
        footer.addWidget(cancel_btn)
        footer.addWidget(save_btn)
        outer.addLayout(footer)

    def _on_smooth_toggled(self, checked):
        self.speed_lbl.setEnabled(checked)
        self.speed_box.setEnabled(checked)

    def _toggle_api_key_visibility(self, checked):
        self.api_key_edit.setEchoMode(QLineEdit.Normal if checked else QLineEdit.Password)
        self.toggle_key_btn.setText("Hide" if checked else "Show")

    def _confirm_clear_all(self):
        ans = QMessageBox.question(
            self,
            "Clear All Chats",
            "Delete all saved chats permanently? This cannot be undone.",
            QMessageBox.Yes | QMessageBox.No,
            QMessageBox.No,
        )
        if ans == QMessageBox.Yes and self._on_clear_history:
            self._on_clear_history()

    def _save(self):
        updates = {
            "theme": self.theme_box.currentData() or "dark",
            "font_size": int(self.font_size_spin.value()),
            "font_family": self.font_box.currentText() or "System Default",
            "compact_mode": bool(self.compact_cb.isChecked()),
            "show_timestamps": bool(self.timestamps_cb.isChecked()),
            "show_token_counts": bool(self.tokens_cb.isChecked()),
            "smooth_responses": bool(self.smooth_cb.isChecked()),
            "smooth_typing_speed": self.speed_box.currentData() or "natural",
            "stream_responses": bool(self.stream_cb.isChecked()),
            "send_on_enter": bool(self.enter_send_cb.isChecked()),
            "auto_title": bool(self.auto_title_cb.isChecked()),
            "confirm_delete": bool(self.confirm_del_cb.isChecked()),
            "ollama_url": self.url_edit.text().strip() or "http://localhost:11434",
            "ollama_api_key": self.api_key_edit.text().strip(),
            "auto_start_ollama": bool(self.auto_start_cb.isChecked()),
            "temperature": float(self.temp_spin.value()),
            "top_p": float(self.top_p_spin.value()),
            "num_ctx": int(self.ctx_spin.value()),
            "repeat_penalty": float(self.rep_spin.value()),
            "web_search_always_on": bool(self.web_always_cb.isChecked()),
            "web_search_show_sources": bool(self.show_sources_cb.isChecked()),
            "memory_enabled": bool(self.mem_enabled_cb.isChecked()),
            "auto_memory": bool(self.auto_mem_cb.isChecked()),
        }
        self.settings = save_settings(updates)
        self.accept()