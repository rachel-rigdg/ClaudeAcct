#!/usr/bin/env python3
"""
Run script for OFX Accounting System Web UI
"""

import os
import sys
from flask import Flask

# Add current directory to path
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

try:
    from accounting_web_ui import app
    
    if __name__ == '__main__':
        print("Starting OFX Accounting System Web UI...")
        print("Open your browser to: http://localhost:8080")
        print("Press Ctrl+C to stop the server")
        
        app.run(debug=True, host='0.0.0.0', port=8080)
        
except ImportError as e:
    print(f"Error importing modules: {e}")
    print("Make sure you have:")
    print("1. accounting_system.py - The core accounting system")
    print("2. accounting_web_ui.py - The Flask web interface")
    print("3. templates/ directory with all HTML templates")
    print("4. Required packages installed: pip install -r requirements.txt")
    sys.exit(1)
