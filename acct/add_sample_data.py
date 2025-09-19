#!/usr/bin/env python3
"""
Add sample data to the accounting system for testing
"""

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
    
    print(f"\nAdded {count} sample transactions")
    print("You can now test the web interface with sample data!")
    
    accounting.close()

if __name__ == '__main__':
    add_sample_data()
