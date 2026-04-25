"""Heavy opsiyonel bağımlılıkları import etmeden önce stub'la (firebase vb.)."""
import sys
from unittest.mock import MagicMock


def apply():
    if "firebase_admin" not in sys.modules:
        m = MagicMock()
        m._apps = []
        sys.modules["firebase_admin"] = m
    for sub in ("credentials", "messaging"):
        name = f"firebase_admin.{sub}"
        if name not in sys.modules:
            sys.modules[name] = MagicMock()
