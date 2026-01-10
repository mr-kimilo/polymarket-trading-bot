#!/usr/bin/env python3
"""
Convenience script to run orderbook_tui from the project root directory.

Usage:
    python orderbook.py --coin BTC
    python orderbook.py --coin ETH
"""

import sys
from pathlib import Path

# Add the project root to path
sys.path.insert(0, str(Path(__file__).parent))

# Import and run the main function
from apps.orderbook_tui import main

if __name__ == "__main__":
    main()
