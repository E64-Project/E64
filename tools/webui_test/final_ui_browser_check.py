#!/usr/bin/env python3
"""Compatibility entry point for the current unified Firefox UI checks."""
from pathlib import Path
import runpy
runpy.run_path(str(Path(__file__).with_name('unified_ui_browser_check.py')),run_name='__main__')
