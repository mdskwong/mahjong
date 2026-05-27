#!/usr/bin/env python3
import os
import sys

# Ensure the root directory is in the Python path
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from backend.main import main

if __name__ == "__main__":
    main()
