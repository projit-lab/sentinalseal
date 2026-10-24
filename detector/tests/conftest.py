"""Shared fixtures for detector tests."""

from __future__ import annotations

import sys
from pathlib import Path

import pytest


# Ensure the repo root is on sys.path so `import detector` works
REPO_ROOT = Path(__file__).resolve().parents[2]
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))
