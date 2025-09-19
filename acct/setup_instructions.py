#!/usr/bin/env python3
"""
Setup script and requirements for OFX Accounting System Web UI
"""

# requirements.txt content
requirements_txt = """
Flask==2.3.3
Werkzeug==2.3.7
"""

# Directory structure setup
import os
import sys

def create_directory_structure():
    """Create the necessary directory structure"""
    directories = [
        'templates',
        'static/css',
        'static/js',
        'backups',
        'uploads'
    ]
    
    for directory in directories:
        os.makedirs(directory, exist_ok=True)
        print(f"Created directory: {directory}")

def create_requirements_file():
    """Create requirements.txt file"""
    with open('requirements.txt', 'w') as f:
        f.write(requirements_txt.strip())
    print("Created requirements.txt")

def create_run_script():
    """Create a simple run script"""
    run_script = """#!/usr/bin/env python3
\"\"\"
Run script for OFX Accounting System Web UI
\"\"\"

import os
import sys
from flask import Flask

# Add current directory to path
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

try:
    from accounting_web_ui import app
    
    if __name__ == '__main__':
        print("Starting OFX Accounting System Web UI...")
        print("Open your browser to: http://localhost:5000")
        print("Press Ctrl+C to stop the server")
        
        app.run(debug=True, host='0.0.0.0', port=5000)
        
except ImportError as e:
    print(f"Error importing modules: {e}")
    print("Make sure you have:")
    print("1. accounting_system.py - The core accounting system")
    print("2. accounting_web_ui.py - The Flask web interface")
    print("3. templates/ directory with all HTML templates")
    print("4. Required packages installed: pip install -r requirements.txt")
    sys.exit(1)
"""
    
    with open('run_server.py', 'w') as f:
        f.write(run_script)
    
    # Make executable on Unix systems
    if os.name != 'nt':
        os.chmod('run_server.py', 0o755)
    
    print("Created run_server.py")

def create_sample_data_script():
    """Create script to add sample data"""
    sample_script = """#!/usr/bin/env python3
\"\"\"
Add sample data to the accounting system for testing
\"\"\"

from datetime import date, datetime
from decimal import Decimal
from accounting_system import AccountingSystem, AccountType

def add_sample_data():
    accounting = AccountingSystem()
    
    print("Adding sample transactions...")
    
    # Sample transactions
    transactions = [
        {
            'id': 'SAMPLE001',
            'date': date(2024, 1, 15),
            'description': 'Initial capital investment',
            'entries': [
                ('1110', Decimal('10000'), Decimal('0'), 'Cash deposit'),
                ('3100', Decimal('0'), Decimal('10000'), 'Owner investment')
            ]
        },
        {
            'id': 'SAMPLE002', 
            'date': date(2024, 1, 20),
            'description': 'Office supplies purchase',
            'entries': [
                ('5240', Decimal('150'), Decimal('0'), 'Office supplies'),
                ('1110', Decimal('0'), Decimal('150'), 'Cash payment')
            ]
        },
        {
            'id': 'SAMPLE003',
            'date': date(2024, 1, 25), 
            'description': 'Service revenue',
            'entries': [
                ('1120', Decimal('2500'), Decimal('0'), 'Accounts receivable'),
                ('4200', Decimal('0'), Decimal('2500'), 'Service revenue')
            ]
        },
        {
            'id': 'SAMPLE004',
            'date': date(2024, 1, 30),
            'description': 'Rent payment',
            'entries': [
                ('5220', Decimal('800'), Decimal('0'), 'Rent expense'),
                ('1110', Decimal('0'), Decimal('800'), 'Cash payment')
            ]
        }
    ]
    
    count = 0
    for txn in transactions:
        if accounting.create_transaction(txn['id'], txn['date'], txn['description'], txn['entries']):
            count += 1
            print(f"Added transaction: {txn['id']}")
        else:
            print(f"Failed to add transaction: {txn['id']}")
    
    print(f"\\nAdded {count} sample transactions")
    print("You can now test the web interface with sample data!")
    
    accounting.close()

if __name__ == '__main__':
    add_sample_data()
"""
    
    with open('add_sample_data.py', 'w') as f:
        f.write(sample_script)
    
    if os.name != 'nt':
        os.chmod('add_sample_data.py', 0o755)
    
    print("Created add_sample_data.py")

def main():
    print("Setting up OFX Accounting System Web UI...")
    print("=" * 50)
    
    create_directory_structure()
    create_requirements_file()
    create_run_script() 
    create_sample_data_script()
    
    print("\\nSetup complete!")
    print("\\nNext steps:")
    print("1. Save the accounting system code as 'accounting_system.py'")
    print("2. Save the web UI code as 'accounting_web_ui.py'") 
    print("3. Save all HTML templates in the 'templates/' directory:")
    print("   - base.html")
    print("   - dashboard.html")
    print("   - accounts.html")
    print("   - new_account.html")
    print("   - transactions.html")
    print("   - new_transaction.html")
    print("   - transaction_detail.html")
    print("   - reports.html")
    print("   - trial_balance.html")
    print("   - income_statement.html")
    print("   - balance_sheet.html")
    print("   - import_ofx.html")
    print("   - export.html")
    print("4. Install requirements: pip install -r requirements.txt")
    print("5. Add sample data: python add_sample_data.py")
    print("6. Run the server: python run_server.py")
    print("7. Open browser to http://localhost:5000")

if __name__ == '__main__':
    main()
