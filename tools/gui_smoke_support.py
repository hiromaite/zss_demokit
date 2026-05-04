from __future__ import annotations

import os
import tempfile
from pathlib import Path


def isolate_gui_settings(prefix: str) -> tempfile.TemporaryDirectory[str]:
    settings_dir = tempfile.TemporaryDirectory(prefix=prefix)
    settings_path = Path(settings_dir.name) / "settings.ini"
    os.environ["ZSS_DEMOKIT_SETTINGS_FILE"] = str(settings_path)
    return settings_dir
