#!/usr/bin/env python3
"""
Fixed OFX-Compliant Accounting System
Complete version with multi-bank account support
"""

import sqlite3
import xml.etree.ElementTree as ET
from datetime import datetime, date
from decimal import Decimal, ROUND_HALF_UP
from dataclasses import dataclass, field
from typing import List, Dict, Optional, Tuple
from enum import Enum
import csv
import json
import hashlib
import re

# Custom adapter for date objects
def adapt_date(val):
    return val.isoformat()

def convert_date(val):
    return datetime.fromisoformat(val.decode()).date()

# Register the adapter and converter
sqlite3.register_adapter(date, adapt_date)
sqlite3.register_converter("DATE", convert_date)

class AccountType(Enum):
    ASSET = "ASSET"
    LIABILITY = "LIABILITY"
    EQUITY = "EQUITY"
    REVENUE = "REVENUE"
    EXPENSE = "EXPENSE"

class TransactionType(Enum):
    DEBIT = "DEBIT"
    CREDIT = "CREDIT"

@dataclass
class Account:
    id: str
    name: str
    account_type: AccountType
    parent_id: Optional[str] = None
    description: str = ""
    is_active: bool = True
    created_date: datetime = field(default_factory=datetime.now)

@dataclass
class Transaction:
    id: str
    date: date
    description: str
    reference: str = ""
    created_date: datetime = field(default_factory=datetime.now)
    entries: List['TransactionEntry'] = field(default_factory=list)

@dataclass
class TransactionEntry:
    id: str
    transaction_id: str
    account_id: str
    debit_amount: Decimal = Decimal('0')
    credit_amount: Decimal = Decimal('0')
    description: str = ""

class AccountingSystem:
    def __init__(self, db_path: str = "accounting.db"):
        self.db_path = db_path
        # Use detect_types to enable date/datetime conversion
        self.conn = sqlite3.connect(db_path, detect_types=sqlite3.PARSE_DECLTYPES|sqlite3.PARSE_COLNAMES)
        self.conn.row_factory = sqlite3.Row  # Enable column access by name
        self.setup_database()
        self.setup_chart_of_accounts()

    def setup_database(self):
        """Initialize database tables"""
        cursor = self.conn.cursor()
        
        # Accounts table
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS accounts (
                id TEXT PRIMARY KEY,
                name TEXT NOT NULL,
                account_type TEXT NOT NULL,
                parent_id TEXT,
                description TEXT,
                is_active BOOLEAN DEFAULT 1,
                created_date TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                FOREIGN KEY (parent_id) REFERENCES accounts (id)
            )
        ''')
        
        # Transactions table - use TEXT for date to avoid binding issues
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS transactions (
                id TEXT PRIMARY KEY,
                date TEXT NOT NULL,
                description TEXT NOT NULL,
                reference TEXT,
                created_date TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            )
        ''')
        
        # Transaction entries table
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS transaction_entries (
                id TEXT PRIMARY KEY,
                transaction_id TEXT NOT NULL,
                account_id TEXT NOT NULL,
                debit_amount REAL DEFAULT 0,
                credit_amount REAL DEFAULT 0,
                description TEXT,
                FOREIGN KEY (transaction_id) REFERENCES transactions (id),
                FOREIGN KEY (account_id) REFERENCES accounts (id)
            )
        ''')
        
        # OFX import tracking
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS ofx_imports (
                id TEXT PRIMARY KEY,
                bank_id TEXT,
                account_id TEXT,
                import_date TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                file_hash TEXT,
                transactions_imported INTEGER
            )
        ''')
        
        self.conn.commit()

    def setup_chart_of_accounts(self):
        """Set up standard chart of accounts"""
        standard_accounts = [
            # Assets
            ("1000", "ASSETS", AccountType.ASSET, None),
            ("1100", "Current Assets", AccountType.ASSET, "1000"),
            ("1110", "Cash and Bank Accounts", AccountType.ASSET, "1100"),
            ("1120", "Accounts Receivable", AccountType.ASSET, "1100"),
            ("1130", "Inventory", AccountType.ASSET, "1100"),
            ("1140", "Prepaid Expenses", AccountType.ASSET, "1100"),
            ("1200", "Fixed Assets", AccountType.ASSET, "1000"),
            ("1210", "Equipment", AccountType.ASSET, "1200"),
            ("1220", "Accumulated Depreciation - Equipment", AccountType.ASSET, "1200"),
            
            # Liabilities
            ("2000", "LIABILITIES", AccountType.LIABILITY, None),
            ("2100", "Current Liabilities", AccountType.LIABILITY, "2000"),
            ("2110", "Accounts Payable", AccountType.LIABILITY, "2100"),
            ("2120", "Accrued Expenses", AccountType.LIABILITY, "2100"),
            ("2130", "Short-term Debt", AccountType.LIABILITY, "2100"),
            ("2200", "Long-term Liabilities", AccountType.LIABILITY, "2000"),
            ("2210", "Long-term Debt", AccountType.LIABILITY, "2200"),
            
            # Equity
            ("3000", "EQUITY", AccountType.EQUITY, None),
            ("3100", "Owner's Equity", AccountType.EQUITY, "3000"),
            ("3200", "Retained Earnings", AccountType.EQUITY, "3000"),
            
            # Revenue
            ("4000", "REVENUE", AccountType.REVENUE, None),
            ("4100", "Sales Revenue", AccountType.REVENUE, "4000"),
            ("4200", "Service Revenue", AccountType.REVENUE, "4000"),
            ("4300", "Other Income", AccountType.REVENUE, "4000"),
            
            # Expenses
            ("5000", "EXPENSES", AccountType.EXPENSE, None),
            ("5100", "Cost of Goods Sold", AccountType.EXPENSE, "5000"),
            ("5200", "Operating Expenses", AccountType.EXPENSE, "5000"),
            ("5210", "Salaries and Wages", AccountType.EXPENSE, "5200"),
            ("5220", "Rent Expense", AccountType.EXPENSE, "5200"),
            ("5230", "Utilities Expense", AccountType.EXPENSE, "5200"),
            ("5240", "Office Supplies", AccountType.EXPENSE, "5200"),
            ("5250", "Depreciation Expense", AccountType.EXPENSE, "5200"),
        ]
        
        for account_id, name, acc_type, parent_id in standard_accounts:
            self.create_account(account_id, name, acc_type, parent_id)

    def create_account(self, account_id: str, name: str, account_type: AccountType, 
                      parent_id: Optional[str] = None, description: str = "") -> bool:
        """Create a new account"""
        try:
            cursor = self.conn.cursor()
            cursor.execute('''
                INSERT OR IGNORE INTO accounts (id, name, account_type, parent_id, description)
                VALUES (?, ?, ?, ?, ?)
            ''', (account_id, name, account_type.value, parent_id, description))
            self.conn.commit()
            return cursor.rowcount > 0
        except sqlite3.Error as e:
            print(f"Error creating account: {e}")
            return False

    def generate_transaction_id(self, transaction_date: date, amount: Decimal) -> str:
        """Generate a unique transaction ID based on date and amount"""
        cursor = self.conn.cursor()
        
        # Get the next sequence number for this date
        date_str = transaction_date.strftime('%Y%m%d')
        cursor.execute('''
            SELECT COUNT(*) as count 
            FROM transactions 
            WHERE date = ?
        ''', (transaction_date.isoformat(),))
        
        count = cursor.fetchone()['count'] + 1
        
        # Format: TXN-YYYYMMDD-NNN
        transaction_id = f"TXN-{date_str}-{count:03d}"
        
        # Ensure uniqueness (in case of concurrent transactions)
        while True:
            cursor.execute('SELECT id FROM transactions WHERE id = ?', (transaction_id,))
            if not cursor.fetchone():
                break
            count += 1
            transaction_id = f"TXN-{date_str}-{count:03d}"
        
        return transaction_id

    def get_bank_accounts(self) -> List[Tuple]:
        """Get all bank/cash accounts"""
        cursor = self.conn.cursor()
        cursor.execute('''
            SELECT id, name, description
            FROM accounts 
            WHERE account_type = 'ASSET' 
            AND (name LIKE '%bank%' OR name LIKE '%cash%' OR name LIKE '%checking%' OR name LIKE '%savings%')
            AND is_active = 1
            ORDER BY id
        ''')
        return cursor.fetchall()

    def get_transactions_with_bank_balances(self, limit: int = 50, offset: int = 0) -> Tuple[List, Dict]:
        """Get transactions with running balances for all bank accounts"""
        cursor = self.conn.cursor()
        
        # Get all bank accounts
        bank_accounts = self.get_bank_accounts()
        bank_account_ids = [acc['id'] for acc in bank_accounts]
        
        if not bank_account_ids:
            # No bank accounts found, return empty
            return [], {}
        
        # Get transactions that affect any bank account
        placeholders = ','.join(['?' for _ in bank_account_ids])
        cursor.execute(f'''
            SELECT DISTINCT t.id, t.date, t.description, t.reference,
                   COUNT(te.id) as entry_count
            FROM transactions t
            JOIN transaction_entries te ON t.id = te.transaction_id
            WHERE te.account_id IN ({placeholders})
            GROUP BY t.id, t.date, t.description, t.reference
            ORDER BY t.date DESC, t.id DESC
            LIMIT ? OFFSET ?
        ''', (*bank_account_ids, limit, offset))
        
        transactions = cursor.fetchall()
        
        # For each transaction, get the bank account effects
        transactions_with_balances = []
        current_balances = {}
        
        # Get current balances for all bank accounts
        for acc in bank_accounts:
            current_balances[acc['id']] = self.get_account_balance(acc['id'])
        
        for txn in transactions:
            txn_id = txn['id']
            bank_effects = {}
            
            # Get effects on each bank account for this transaction
            for acc_id in bank_account_ids:
                cursor.execute('''
                    SELECT COALESCE(debit_amount, 0) - COALESCE(credit_amount, 0) as effect
                    FROM transaction_entries
                    WHERE transaction_id = ? AND account_id = ?
                ''', (txn_id, acc_id))
                
                result = cursor.fetchone()
                effect = Decimal(str(result['effect'])) if result else Decimal('0')
                bank_effects[acc_id] = effect
            
            transactions_with_balances.append({
                'transaction': txn,
                'bank_effects': bank_effects,
                'balances_after': current_balances.copy()  # Balance after this transaction
            })
            
            # Update running balances (working backwards)
            for acc_id in bank_account_ids:
                current_balances[acc_id] -= bank_effects[acc_id]
        
        return transactions_with_balances, {acc['id']: acc['name'] for acc in bank_accounts}

    def get_account_transaction_history(self, account_id: str, limit: int = 100) -> List:
        """Get transaction history for a specific account with running balance"""
        cursor = self.conn.cursor()
        
        # Get account info
        cursor.execute('SELECT account_type FROM accounts WHERE id = ?', (account_id,))
        account_info = cursor.fetchone()
        if not account_info:
            return []
        
        account_type = account_info['account_type']
        
        # Get transactions affecting this account
        cursor.execute('''
            SELECT t.id, t.date, t.description, t.reference,
                   te.debit_amount, te.credit_amount, te.description as entry_description
            FROM transactions t
            JOIN transaction_entries te ON t.id = te.transaction_id
            WHERE te.account_id = ?
            ORDER BY t.date ASC, t.id ASC
            LIMIT ?
        ''', (account_id, limit))
        
        transactions = cursor.fetchall()
        
        # Calculate running balance
        running_balance = Decimal('0')
        result = []
        
        for txn in transactions:
            debit = Decimal(str(txn['debit_amount']))
            credit = Decimal(str(txn['credit_amount']))
            
            # Calculate effect based on account type
            if account_type in ['ASSET', 'EXPENSE']:
                effect = debit - credit  # Normal debit balance
            else:
                effect = credit - debit  # Normal credit balance
            
            running_balance += effect
            
            result.append({
                'id': txn['id'],
                'date': txn['date'],
                'description': txn['description'],
                'reference': txn['reference'],
                'debit': debit,
                'credit': credit,
                'effect': effect,
                'running_balance': running_balance,
                'entry_description': txn['entry_description']
            })
        
        return result

    def create_transaction(self, transaction_id: str, transaction_date: date, description: str,
                          entries: List[Tuple[str, Decimal, Decimal, str]], 
                          reference: str = "") -> bool:
        """Create a new transaction with entries"""
        try:
            # Validate double-entry bookkeeping
            total_debits = sum(entry[1] for entry in entries)
            total_credits = sum(entry[2] for entry in entries)
            
            if total_debits != total_credits:
                raise ValueError(f"Transaction not balanced: Debits {total_debits} != Credits {total_credits}")
            
            cursor = self.conn.cursor()
            
            # Convert date to string for database storage
            date_str = transaction_date.isoformat()
            
            # Insert transaction
            cursor.execute('''
                INSERT INTO transactions (id, date, description, reference)
                VALUES (?, ?, ?, ?)
            ''', (transaction_id, date_str, description, reference))
            
            # Insert transaction entries
            for i, (account_id, debit, credit, entry_desc) in enumerate(entries):
                entry_id = f"{transaction_id}_{i+1}"
                cursor.execute('''
                    INSERT INTO transaction_entries 
                    (id, transaction_id, account_id, debit_amount, credit_amount, description)
                    VALUES (?, ?, ?, ?, ?, ?)
                ''', (entry_id, transaction_id, account_id, float(debit), float(credit), entry_desc))
            
            self.conn.commit()
            return True
            
        except (sqlite3.Error, ValueError) as e:
            print(f"Error creating transaction: {e}")
            self.conn.rollback()
            return False

    def get_account_balance(self, account_id: str, as_of_date: Optional[date] = None) -> Decimal:
        """Get account balance as of a specific date"""
        cursor = self.conn.cursor()
        
        date_clause = ""
        params = [account_id]
        if as_of_date:
            date_clause = "AND date(t.date) <= date(?)"
            params.append(as_of_date.isoformat())
        
        cursor.execute(f'''
            SELECT 
                COALESCE(SUM(te.debit_amount), 0) as total_debits,
                COALESCE(SUM(te.credit_amount), 0) as total_credits,
                a.account_type
            FROM accounts a
            LEFT JOIN transaction_entries te ON a.id = te.account_id
            LEFT JOIN transactions t ON te.transaction_id = t.id
            WHERE a.id = ? {date_clause}
            GROUP BY a.id, a.account_type
        ''', params)
        
        result = cursor.fetchone()
        if not result:
            return Decimal('0')
        
        total_debits = Decimal(str(result['total_debits']))
        total_credits = Decimal(str(result['total_credits']))
        account_type = result['account_type']
        
        # Normal balances: Assets/Expenses = Debit, Liabilities/Equity/Revenue = Credit
        if account_type in ['ASSET', 'EXPENSE']:
            return total_debits - total_credits
        else:
            return total_credits - total_debits

    def generate_trial_balance(self, as_of_date: Optional[date] = None) -> List[Tuple[str, str, Decimal, Decimal]]:
        """Generate trial balance"""
        cursor = self.conn.cursor()
        cursor.execute("SELECT id, name, account_type FROM accounts WHERE is_active = 1 ORDER BY id")
        accounts = cursor.fetchall()
        
        trial_balance = []
        total_debits = Decimal('0')
        total_credits = Decimal('0')
        
        for account in accounts:
            account_id = account['id']
            name = account['name']
            account_type = account['account_type']
            
            balance = self.get_account_balance(account_id, as_of_date)
            
            if balance != 0:
                if account_type in ['ASSET', 'EXPENSE'] and balance > 0:
                    trial_balance.append((account_id, name, balance, Decimal('0')))
                    total_debits += balance
                elif account_type in ['LIABILITY', 'EQUITY', 'REVENUE'] and balance > 0:
                    trial_balance.append((account_id, name, Decimal('0'), balance))
                    total_credits += balance
                elif balance < 0:
                    # Reverse the normal balance
                    if account_type in ['ASSET', 'EXPENSE']:
                        trial_balance.append((account_id, name, Decimal('0'), abs(balance)))
                        total_credits += abs(balance)
                    else:
                        trial_balance.append((account_id, name, abs(balance), Decimal('0')))
                        total_debits += abs(balance)
        
        trial_balance.append(("TOTAL", "TOTAL", total_debits, total_credits))
        return trial_balance

    def generate_income_statement(self, start_date: date, end_date: date) -> Dict:
        """Generate income statement"""
        cursor = self.conn.cursor()
        
        # Get revenue accounts
        cursor.execute('''
            SELECT a.id, a.name, 
                   COALESCE(SUM(te.credit_amount), 0) - COALESCE(SUM(te.debit_amount), 0) as balance
            FROM accounts a
            LEFT JOIN transaction_entries te ON a.id = te.account_id
            LEFT JOIN transactions t ON te.transaction_id = t.id
            WHERE a.account_type = 'REVENUE' AND date(t.date) BETWEEN date(?) AND date(?)
            GROUP BY a.id, a.name
            HAVING balance != 0
            ORDER BY a.id
        ''', (start_date.isoformat(), end_date.isoformat()))
        
        revenues = [(row['id'], row['name'], Decimal(str(row['balance']))) for row in cursor.fetchall()]
        total_revenue = sum(rev[2] for rev in revenues)
        
        # Get expense accounts
        cursor.execute('''
            SELECT a.id, a.name, 
                   COALESCE(SUM(te.debit_amount), 0) - COALESCE(SUM(te.credit_amount), 0) as balance
            FROM accounts a
            LEFT JOIN transaction_entries te ON a.id = te.account_id
            LEFT JOIN transactions t ON te.transaction_id = t.id
            WHERE a.account_type = 'EXPENSE' AND date(t.date) BETWEEN date(?) AND date(?)
            GROUP BY a.id, a.name
            HAVING balance != 0
            ORDER BY a.id
        ''', (start_date.isoformat(), end_date.isoformat()))
        
        expenses = [(row['id'], row['name'], Decimal(str(row['balance']))) for row in cursor.fetchall()]
        total_expenses = sum(exp[2] for exp in expenses)
        
        net_income = total_revenue - total_expenses
        
        return {
            'period': f"{start_date} to {end_date}",
            'revenues': revenues,
            'total_revenue': total_revenue,
            'expenses': expenses,
            'total_expenses': total_expenses,
            'net_income': net_income
        }

    def generate_balance_sheet(self, as_of_date: date) -> Dict:
        """Generate balance sheet"""
        cursor = self.conn.cursor()
        
        balance_sheet = {}
        
        for account_type in ['ASSET', 'LIABILITY', 'EQUITY']:
            cursor.execute('''
                SELECT a.id, a.name
                FROM accounts a
                WHERE a.account_type = ? AND a.is_active = 1
                ORDER BY a.id
            ''', (account_type,))
            
            accounts = []
            total = Decimal('0')
            
            for row in cursor.fetchall():
                account_id = row['id']
                name = row['name']
                balance = self.get_account_balance(account_id, as_of_date)
                if balance != 0:
                    accounts.append((account_id, name, balance))
                    total += balance
            
            balance_sheet[account_type.lower()] = {
                'accounts': accounts,
                'total': total
            }
        
        return balance_sheet

    def parse_ofx_file(self, file_path: str) -> Dict:
        """Parse OFX file and extract transaction data"""
        try:
            with open(file_path, 'r', encoding='utf-8') as file:
                content = file.read()
            
            # Remove OFX headers and clean up
            ofx_start = content.find('<OFX>')
            if ofx_start != -1:
                content = content[ofx_start:]
            
            # Parse XML
            root = ET.fromstring(content)
            
            # Extract bank account info
            bank_acct = root.find('.//BANKACCTFROM')
            if bank_acct is None:
                raise ValueError("No bank account information found in OFX file")
            
            bank_id = bank_acct.find('BANKID').text if bank_acct.find('BANKID') is not None else ""
            account_id = bank_acct.find('ACCTID').text if bank_acct.find('ACCTID') is not None else ""
            
            # Extract transactions
            transactions = []
            stmttrns = root.findall('.//STMTTRN')
            
            for trn in stmttrns:
                tran_data = {}
                tran_data['fitid'] = trn.find('FITID').text if trn.find('FITID') is not None else ""
                tran_data['type'] = trn.find('TRNTYPE').text if trn.find('TRNTYPE') is not None else ""
                tran_data['date'] = trn.find('DTPOSTED').text if trn.find('DTPOSTED') is not None else ""
                tran_data['amount'] = trn.find('TRNAMT').text if trn.find('TRNAMT') is not None else "0"
                tran_data['name'] = trn.find('NAME').text if trn.find('NAME') is not None else ""
                tran_data['memo'] = trn.find('MEMO').text if trn.find('MEMO') is not None else ""
                
                transactions.append(tran_data)
            
            return {
                'bank_id': bank_id,
                'account_id': account_id,
                'transactions': transactions
            }
            
        except Exception as e:
            print(f"Error parsing OFX file: {e}")
            return None

    def import_ofx_transactions(self, file_path: str, cash_account_id: str) -> int:
        """Import transactions from OFX file"""
        ofx_data = self.parse_ofx_file(file_path)
        if not ofx_data:
            return 0
        
        imported_count = 0
        
        for trn_data in ofx_data['transactions']:
            try:
                # Parse date
                date_str = trn_data['date'][:8]  # YYYYMMDD
                trn_date = datetime.strptime(date_str, '%Y%m%d').date()
                
                amount = Decimal(trn_data['amount'])
                description = f"{trn_data['name']} {trn_data['memo']}".strip()
                
                # Create transaction ID from FITID
                transaction_id = f"OFX_{trn_data['fitid']}"
                
                # Check if already imported
                cursor = self.conn.cursor()
                cursor.execute('SELECT id FROM transactions WHERE id = ?', (transaction_id,))
                if cursor.fetchone():
                    continue  # Skip if already exists
                
                # Determine accounts based on transaction type and amount
                if amount > 0:
                    # Credit to cash account (debit cash, credit revenue or other)
                    entries = [
                        (cash_account_id, amount, Decimal('0'), description),
                        ('4300', Decimal('0'), amount, description)  # Other Income
                    ]
                else:
                    # Debit to cash account (credit cash, debit expense or other)
                    entries = [
                        ('5240', abs(amount), Decimal('0'), description),  # Office Supplies
                        (cash_account_id, Decimal('0'), abs(amount), description)
                    ]
                
                if self.create_transaction(transaction_id, trn_date, description, entries, trn_data['fitid']):
                    imported_count += 1
                    
            except Exception as e:
                print(f"Error importing transaction {trn_data['fitid']}: {e}")
                continue
        
        # Record import
        file_hash = hashlib.md5(open(file_path, 'rb').read()).hexdigest()
        cursor = self.conn.cursor()
        cursor.execute('''
            INSERT INTO ofx_imports (id, bank_id, account_id, file_hash, transactions_imported)
            VALUES (?, ?, ?, ?, ?)
        ''', (f"IMPORT_{datetime.now().isoformat()}", ofx_data['bank_id'], 
              ofx_data['account_id'], file_hash, imported_count))
        self.conn.commit()
        
        return imported_count

    def export_to_ofx(self, account_id: str, start_date: date, end_date: date) -> str:
        """Export transactions to OFX format"""
        cursor = self.conn.cursor()
        
        # Get account info
        cursor.execute('SELECT name FROM accounts WHERE id = ?', (account_id,))
        account_result = cursor.fetchone()
        if not account_result:
            raise ValueError(f"Account {account_id} not found")
        
        account_name = account_result['name']
        
        # Get transactions
        cursor.execute('''
            SELECT t.id, t.date, t.description, te.debit_amount, te.credit_amount
            FROM transactions t
            JOIN transaction_entries te ON t.id = te.transaction_id
            WHERE te.account_id = ? AND date(t.date) BETWEEN date(?) AND date(?)
            ORDER BY t.date, t.id
        ''', (account_id, start_date.isoformat(), end_date.isoformat()))
        
        transactions = cursor.fetchall()
        
        # Generate OFX
        ofx_header = '''OFXHEADER:100
DATA:OFXSGML
VERSION:102
SECURITY:NONE
ENCODING:USASCII
CHARSET:1252
COMPRESSION:NONE
OLDFILEUID:NONE
NEWFILEUID:NONE

'''
        
        ofx_body = f'''<OFX>
<SIGNONMSGSRSV1>
<SONRS>
<STATUS>
<CODE>0</CODE>
<SEVERITY>INFO</SEVERITY>
</STATUS>
<DTSERVER>{datetime.now().strftime('%Y%m%d%H%M%S')}</DTSERVER>
<LANGUAGE>ENG</LANGUAGE>
</SONRS>
</SIGNONMSGSRSV1>
<BANKMSGSRSV1>
<STMTTRNRS>
<TRNUID>1</TRNUID>
<STATUS>
<CODE>0</CODE>
<SEVERITY>INFO</SEVERITY>
</STATUS>
<STMTRS>
<CURDEF>USD</CURDEF>
<BANKACCTFROM>
<BANKID>123456789</BANKID>
<ACCTID>{account_id}</ACCTID>
<ACCTTYPE>CHECKING</ACCTTYPE>
</BANKACCTFROM>
<BANKTRANLIST>
<DTSTART>{start_date.strftime('%Y%m%d')}</DTSTART>
<DTEND>{end_date.strftime('%Y%m%d')}</DTEND>
'''
        
        for row in transactions:
            trn_id = row['id']
            trn_date = row['date'].replace('-', '') if isinstance(row['date'], str) else row['date'].strftime('%Y%m%d')
            description = row['description']
            debit = Decimal(str(row['debit_amount']))
            credit = Decimal(str(row['credit_amount']))
            
            amount = credit - debit if credit > debit else -(debit - credit)
            trn_type = "CREDIT" if amount > 0 else "DEBIT"
            
            ofx_body += f'''<STMTTRN>
<TRNTYPE>{trn_type}</TRNTYPE>
<DTPOSTED>{trn_date}</DTPOSTED>
<TRNAMT>{amount}</TRNAMT>
<FITID>{trn_id}</FITID>
<NAME>{description[:32]}</NAME>
<MEMO>{description}</MEMO>
</STMTTRN>
'''
        
        ofx_body += '''</BANKTRANLIST>
<LEDGERBAL>
<BALAMT>0.00</BALAMT>
<DTASOF>{}</DTASOF>
</LEDGERBAL>
</STMTRS>
</STMTTRNRS>
</BANKMSGSRSV1>
</OFX>
'''.format(end_date.strftime('%Y%m%d'))
        
        return ofx_header + ofx_body

    def backup_database(self, backup_path: str):
        """Create database backup"""
        backup_conn = sqlite3.connect(backup_path)
        self.conn.backup(backup_conn)
        backup_conn.close()

    def close(self):
        """Close database connection"""
        self.conn.close()

# Command Line Interface
def main():
    accounting = AccountingSystem()
    
    print("OFX-Compliant Accounting System")
    print("==============================")
    
    while True:
        print("\nMenu:")
        print("1. Create Account")
        print("2. Create Transaction") 
        print("3. View Account Balance")
        print("4. Generate Trial Balance")
        print("5. Generate Income Statement")
        print("6. Generate Balance Sheet")
        print("7. Import OFX File")
        print("8. Export to OFX")
        print("9. Backup Database")
        print("0. Exit")
        
        choice = input("\nSelect option: ")
        
        if choice == "1":
            account_id = input("Account ID: ")
            name = input("Account Name: ")
            print("Account Types: ASSET, LIABILITY, EQUITY, REVENUE, EXPENSE")
            acc_type = AccountType(input("Account Type: ").upper())
            parent_id = input("Parent Account ID (optional): ") or None
            
            if accounting.create_account(account_id, name, acc_type, parent_id):
                print("Account created successfully!")
            else:
                print("Failed to create account.")
        
        elif choice == "2":
            transaction_id = input("Transaction ID: ")
            date_str = input("Date (YYYY-MM-DD): ")
            trn_date = datetime.strptime(date_str, "%Y-%m-%d").date()
            description = input("Description: ")
            
            entries = []
            print("Enter transaction entries (empty account ID to finish):")
            while True:
                account_id = input("Account ID: ")
                if not account_id:
                    break
                debit = Decimal(input("Debit amount (0 if none): ") or "0")
                credit = Decimal(input("Credit amount (0 if none): ") or "0")
                entry_desc = input("Entry description: ")
                entries.append((account_id, debit, credit, entry_desc))
            
            if accounting.create_transaction(transaction_id, trn_date, description, entries):
                print("Transaction created successfully!")
            else:
                print("Failed to create transaction.")
        
        elif choice == "3":
            account_id = input("Account ID: ")
            balance = accounting.get_account_balance(account_id)
            print(f"Account {account_id} balance: ${balance}")
        
        elif choice == "4":
            trial_balance = accounting.generate_trial_balance()
            print(f"\n{'Account':<10} {'Name':<30} {'Debit':<15} {'Credit':<15}")
            print("-" * 70)
            for account_id, name, debit, credit in trial_balance:
                print(f"{account_id:<10} {name:<30} ${debit:<14.2f} ${credit:<14.2f}")
        
        elif choice == "5":
            start_date = datetime.strptime(input("Start Date (YYYY-MM-DD): "), "%Y-%m-%d").date()
            end_date = datetime.strptime(input("End Date (YYYY-MM-DD): "), "%Y-%m-%d").date()
            
            income_statement = accounting.generate_income_statement(start_date, end_date)
            print(f"\nIncome Statement - {income_statement['period']}")
            print("=" * 50)
            
            print("\nREVENUES:")
            for account_id, name, amount in income_statement['revenues']:
                print(f"  {name}: ${amount:.2f}")
            print(f"Total Revenue: ${income_statement['total_revenue']:.2f}")
            
            print("\nEXPENSES:")
            for account_id, name, amount in income_statement['expenses']:
                print(f"  {name}: ${amount:.2f}")
            print(f"Total Expenses: ${income_statement['total_expenses']:.2f}")
            
            print(f"\nNET INCOME: ${income_statement['net_income']:.2f}")
        
        elif choice == "6":
            as_of_date = datetime.strptime(input("As of Date (YYYY-MM-DD): "), "%Y-%m-%d").date()
            
            balance_sheet = accounting.generate_balance_sheet(as_of_date)
            print(f"\nBalance Sheet as of {as_of_date}")
            print("=" * 40)
            
            for section in ['asset', 'liability', 'equity']:
                print(f"\n{section.upper()}S:")
                for account_id, name, balance in balance_sheet[section]['accounts']:
                    print(f"  {name}: ${balance:.2f}")
                print(f"Total {section}s: ${balance_sheet[section]['total']:.2f}")
        
        elif choice == "7":
            file_path = input("OFX File Path: ")
            cash_account = input("Cash Account ID (e.g., 1110): ")
            
            count = accounting.import_ofx_transactions(file_path, cash_account)
            print(f"Imported {count} transactions.")
        
        elif choice == "8":
            account_id = input("Account ID to export: ")
            start_date = datetime.strptime(input("Start Date (YYYY-MM-DD): "), "%Y-%m-%d").date()
            end_date = datetime.strptime(input("End Date (YYYY-MM-DD): "), "%Y-%m-%d").date()
            output_file = input("Output file path: ")
            
            try:
                ofx_content = accounting.export_to_ofx(account_id, start_date, end_date)
                with open(output_file, 'w') as f:
                    f.write(ofx_content)
                print(f"Exported to {output_file}")
            except Exception as e:
                print(f"Export failed: {e}")
        
        elif choice == "9":
            backup_path = input("Backup file path: ")
            accounting.backup_database(backup_path)
            print(f"Database backed up to {backup_path}")
        
        elif choice == "0":
            break
        
        else:
            print("Invalid option.")
    
    accounting.close()

if __name__ == "__main__":
    main()