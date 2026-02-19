#!/usr/bin/env python3
"""
Convenience script to run 5-minute orderbook TUI from the project root directory.

Usage:
    python orderbook_5m.py --coin BTC
    python orderbook_5m.py --coin BTC --silent
"""

import sys
from pathlib import Path

# Add the project root to path
sys.path.insert(0, str(Path(__file__).parent))

# Import and run the main function
from apps.orderbook_5m_tui import main

if __name__ == "__main__":
    sys.exit(main())
