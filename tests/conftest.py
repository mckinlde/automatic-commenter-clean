"""Pytest configuration for the tests/ directory.

Adds the project root to sys.path so test files can import project modules.
"""

import sys
from pathlib import Path

# Add project root to path so imports work from tests/ subdirectory
project_root = str(Path(__file__).parent.parent)
if project_root not in sys.path:
    sys.path.insert(0, project_root)
