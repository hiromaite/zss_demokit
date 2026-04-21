from __future__ import annotations


COLORS = {
    "canvas": "#0B1220",
    "surface": "#111827",
    "surface_alt": "#182133",
    "topbar": "#0F172A",
    "border": "#243041",
    "text": "#E5E7EB",
    "muted": "#94A3B8",
    "accent": "#16263A",
    "accent_strong": "#3B82F6",
    "metric": "#10261E",
    "metric_border": "#1F7A5A",
    "warning": "#2A1E12",
    "warning_border": "#C68D26",
    "recording": "#24151B",
    "recording_border": "#7F1D1D",
    "recording_active": "#7F1D1D",
    "recording_active_border": "#EF4444",
    "recording_badge": "#3B1D24",
    "recording_badge_active": "#7F1D1D",
    "danger": "#F87171",
}


def app_stylesheet() -> str:
    c = COLORS
    return f"""
    QWidget {{
        background: {c["canvas"]};
        color: {c["text"]};
        selection-background-color: {c["accent_strong"]};
        selection-color: white;
    }}
    QMainWindow#AppShell, QWidget#LauncherShell {{
        background: {c["canvas"]};
    }}
    QFrame#SurfaceCard, QFrame#PanelCard {{
        background: {c["surface"]};
        border: 1px solid {c["border"]};
        border-radius: 18px;
    }}
    QFrame#TopBarCard {{
        background: {c["topbar"]};
        border: 1px solid {c["border"]};
        border-radius: 16px;
    }}
    QFrame#MetricCard {{
        background: {c["metric"]};
        border: 1px solid {c["metric_border"]};
        border-radius: 18px;
    }}
    QFrame#AccentCard {{
        background: {c["accent"]};
        border: 1px solid {c["accent_strong"]};
        border-radius: 18px;
    }}
    QFrame#WarningCard {{
        background: {c["warning"]};
        border: 1px solid {c["warning_border"]};
        border-radius: 18px;
    }}
    QFrame#RecordingPanel {{
        background: {c["recording"]};
        border: 1px solid {c["recording_border"]};
        border-radius: 18px;
    }}
    QFrame#RecordingPanel[recordingActive="true"] {{
        background: {c["recording_active"]};
        border: 2px solid {c["recording_active_border"]};
        border-radius: 18px;
    }}
    QLabel#AppTitle {{
        font-size: 28px;
        font-weight: 700;
        color: {c["text"]};
        background: transparent;
    }}
    QLabel#AppSubtitle {{
        font-size: 13px;
        color: {c["muted"]};
        background: transparent;
    }}
    QLabel#SectionTitle {{
        font-size: 14px;
        font-weight: 700;
        background: transparent;
    }}
    QLabel#SectionHint {{
        font-size: 11px;
        color: {c["muted"]};
        background: transparent;
    }}
    QLabel#MetricName {{
        font-size: 11px;
        color: {c["muted"]};
        background: transparent;
    }}
    QLabel#MetricValue {{
        font-size: 20px;
        font-weight: 700;
        background: transparent;
    }}
    QLabel#MetricDetail {{
        font-size: 10px;
        color: {c["muted"]};
        background: transparent;
    }}
    QLabel#ModeStatusLabel {{
        font-size: 12px;
        font-weight: 600;
        color: {c["text"]};
        background: transparent;
    }}
    QLabel#TopCardTitle {{
        font-size: 10px;
        letter-spacing: 0.6px;
        color: {c["muted"]};
        font-weight: 700;
        background: transparent;
    }}
    QLabel#TopCardValue {{
        font-size: 15px;
        font-weight: 700;
        color: {c["text"]};
        background: transparent;
    }}
    QLabel#BadgeLabel {{
        background: {c["accent"]};
        border: 1px solid {c["accent_strong"]};
        border-radius: 12px;
        padding: 6px 12px;
        font-weight: 600;
    }}
    QLabel#RecordingBadge {{
        background: {c["metric"]};
        border: 1px solid {c["metric_border"]};
        border-radius: 12px;
        padding: 6px 12px;
        font-weight: 600;
    }}
    QLabel#WarningBadge {{
        background: {c["warning"]};
        border: 1px solid {c["warning_border"]};
        border-radius: 12px;
        padding: 6px 12px;
        font-weight: 600;
    }}
    QLabel#RecordingStateBadge {{
        background: {c["recording_badge"]};
        border: 1px solid {c["recording_border"]};
        border-radius: 12px;
        padding: 4px 10px;
        font-weight: 700;
    }}
    QLabel#RecordingStateBadge[recordingActive="true"] {{
        background: {c["recording_badge_active"]};
        border: 1px solid {c["recording_active_border"]};
        color: white;
    }}
    QPushButton {{
        min-height: 34px;
        padding: 6px 14px;
        border-radius: 12px;
        border: 1px solid {c["border"]};
        background: {c["surface_alt"]};
        color: {c["text"]};
    }}
    QPushButton:hover {{
        border-color: {c["accent_strong"]};
    }}
    QPushButton#PrimaryButton {{
        background: {c["accent_strong"]};
        color: white;
        border-color: {c["accent_strong"]};
        font-weight: 700;
    }}
    QPushButton#PrimaryButton:hover {{
        background: #2563EB;
    }}
    QPushButton#SecondaryButton {{
        background: {c["accent"]};
        border-color: {c["accent_strong"]};
        font-weight: 600;
    }}
    QPushButton#ToggleButton {{
        min-height: 34px;
        min-width: 132px;
        background: {c["surface_alt"]};
        border-color: {c["border"]};
        font-weight: 700;
    }}
    QPushButton#ToggleButton:checked {{
        background: {c["accent_strong"]};
        border-color: {c["accent_strong"]};
        color: white;
    }}
    QPushButton#RecordToggleButton {{
        min-height: 34px;
        min-width: 132px;
        background: {c["recording"]};
        border-color: {c["recording_border"]};
        font-weight: 700;
    }}
    QPushButton#RecordToggleButton:hover {{
        border-color: {c["recording_active_border"]};
    }}
    QPushButton#RecordToggleButton:checked {{
        background: {c["recording_active"]};
        border-color: {c["recording_active_border"]};
        color: white;
    }}
    QToolButton#SectionToggle {{
        border: none;
        background: transparent;
        color: {c["text"]};
        font-size: 14px;
        font-weight: 700;
        padding: 0px;
    }}
    QPushButton#ModeCardButton {{
        min-height: 40px;
        font-weight: 700;
    }}
    QPushButton#TopBarButton {{
        min-height: 36px;
        font-weight: 700;
        background: {c["surface_alt"]};
    }}
    QComboBox, QLineEdit, QListWidget, QPlainTextEdit {{
        background: {c["surface_alt"]};
        border: 1px solid {c["border"]};
        border-radius: 12px;
        padding: 6px 10px;
    }}
    QPlainTextEdit#LogPane {{
        background: #0F172A;
        font-family: "SF Mono";
        font-size: 11px;
    }}
    QListWidget#SettingsNav {{
        min-width: 170px;
        background: {c["surface"]};
    }}
    QListWidget#SettingsNav::item {{
        padding: 10px 12px;
        border-radius: 10px;
        margin: 4px;
    }}
    QListWidget#SettingsNav::item:selected {{
        background: {c["accent"]};
        border: 1px solid {c["accent_strong"]};
        color: {c["text"]};
    }}
    QGroupBox {{
        border: none;
        margin-top: 0px;
    }}
    QScrollBar:vertical {{
        background: transparent;
        width: 12px;
        margin: 2px;
    }}
    QScrollBar::handle:vertical {{
        background: {c["border"]};
        min-height: 30px;
        border-radius: 6px;
    }}
    """
