# -*- coding: utf-8 -*-
"""Пути для скриптов в общее/scripts/. ROOT = папка общее/."""
from pathlib import Path

SCRIPTS = Path(__file__).resolve().parent
ROOT = SCRIPTS.parent
REPO = ROOT.parent
SNAPSHOTS = ROOT / "tgads-snapshots"
SECRETS = ROOT / "secrets"
IMPORTS = ROOT / "imports"
ARCHIVE = ROOT / "archive"
