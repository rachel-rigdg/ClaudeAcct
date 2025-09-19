#!/usr/bin/env python3
"""
Complete Fixed Web UI for OFX-Compliant Accounting System
Threading-safe version with full interactive editing capabilities
"""

from flask import Flask, render_template, request, jsonify, redirect, url_for, flash, send_file, g
import os
from datetime import datetime, date
from decimal import Decimal
import json
import tempfile
import io

# Import the accounting system
try:
    from accounting_system import AccountingSystem, AccountType
except ImportError:
    print("Please save the fixed accounting system code as 'accounting_system.py' in the same directory")
    exit(1)

app = Flask(__name__)
app.secret_key = 'your-secret-key-change-this-in-production'

def get_accounting_system():
    """Get a thread-safe accounting system instance"""
    if 'accounting' not in g:
        g.accounting = AccountingSystem()
    return g.accounting

@app.teardown_appcontext
def close_accounting_system(error):
    """Close the database connection when the request ends"""
    accounting = g.pop('accounting', None)
    if accounting is not None:
        accounting.close()

@app.route('/')
def dashboard():
    """Main dashboard with overview"""
    try:
        accounting = get_accounting_system()
        
        # Get current balances for key accounts
        cash_balance = accounting.get_account_balance('1110')  # Cash account
        revenue_balance = accounting.get_account_balance('4100')  # Sales Revenue
        expense_balance = accounting.get_account_balance('5200')  # Operating Expenses
        
        # Get recent transactions (last 10)
        cursor = accounting.conn.cursor()
        cursor.execute('''
            SELECT t.id, t.date, t.description, 
                   GROUP_CONCAT(a.name || ': $' || 
                   CASE WHEN te.debit_amount > 0 THEN te.debit_amount 
                        ELSE te.credit_amount END, '; ') as accounts
            FROM transactions t
            JOIN transaction_entries te ON t.id = te.transaction_id
            JOIN accounts a ON te.account_id = a.id
            GROUP BY t.id, t.date, t.description
            ORDER BY t.date DESC, t.id DESC
            LIMIT 10
        ''')
        recent_transactions = cursor.fetchall()
        
        return render_template('dashboard.html', 
                             cash_balance=cash_balance,
                             revenue_balance=revenue_balance,
                             expense_balance=expense_balance,
                             recent_transactions=recent_transactions)
    except Exception as e:
        flash(f'Error loading dashboard: {str(e)}', 'error')
        return render_template('dashboard.html', 
                             cash_balance=0, revenue_balance=0, expense_balance=0,
                             recent_transactions=[])

@app.route('/accounts')
def accounts():
    """List all accounts"""
    try:
        accounting = get_accounting_system()
        cursor = accounting.conn.cursor()
        cursor.execute('''
            SELECT id, name, account_type, parent_id, is_active 
            FROM accounts 
            ORDER BY id
        ''')
        accounts_list = cursor.fetchall()
        
        # Calculate balances for each account
        accounts_with_balances = []
        for account in accounts_list:
            balance = accounting.get_account_balance(account['id'])
            accounts_with_balances.append((
                account['id'], 
                account['name'], 
                account['account_type'], 
                account['parent_id'], 
                account['is_active'], 
                balance
            ))
        
        return render_template('accounts.html', accounts=accounts_with_balances)
    except Exception as e:
        flash(f'Error loading accounts: {str(e)}', 'error')
        return render_template('accounts.html', accounts=[])

@app.route('/accounts/new', methods=['GET', 'POST'])
def new_account():
    """Create new account"""
    if request.method == 'POST':
        try:
            accounting = get_accounting_system()
            account_id = request.form['account_id']
            name = request.form['name']
            account_type = AccountType(request.form['account_type'])
            parent_id = request.form.get('parent_id') or None
            description = request.form.get('description', '')
            
            if accounting.create_account(account_id, name, account_type, parent_id, description):
                flash('Account created successfully!', 'success')
                return redirect(url_for('accounts'))
            else:
                flash('Failed to create account. Account ID may already exist.', 'error')
        except Exception as e:
            flash(f'Error creating account: {str(e)}', 'error')
    
    try:
        # Get parent accounts for dropdown
        accounting = get_accounting_system()
        cursor = accounting.conn.cursor()
        cursor.execute('SELECT id, name FROM accounts WHERE is_active = 1 ORDER BY id')
        parent_accounts = cursor.fetchall()
        
        return render_template('new_account.html', 
                             account_types=[t.value for t in AccountType],
                             parent_accounts=parent_accounts)
    except Exception as e:
        flash(f'Error loading form: {str(e)}', 'error')
        return render_template('new_account.html', 
                             account_types=[t.value for t in AccountType],
                             parent_accounts=[])

@app.route('/accounts/<account_id>/edit', methods=['GET', 'POST'])
def edit_account(account_id):
    """Edit an existing account"""
    try:
        accounting = get_accounting_system()
        cursor = accounting.conn.cursor()
        
        if request.method == 'POST':
            name = request.form['name']
            account_type = AccountType(request.form['account_type'])
            parent_id = request.form.get('parent_id') or None
            description = request.form.get('description', '')
            is_active = bool(request.form.get('is_active'))
            
            # Update account
            cursor.execute('''
                UPDATE accounts 
                SET name = ?, account_type = ?, parent_id = ?, description = ?, is_active = ?
                WHERE id = ?
            ''', (name, account_type.value, parent_id, description, is_active, account_id))
            
            accounting.conn.commit()
            flash('Account updated successfully!', 'success')
            return redirect(url_for('accounts'))
        
        # GET request - show edit form
        cursor.execute('''
            SELECT id, name, account_type, parent_id, description, is_active, created_date
            FROM accounts WHERE id = ?
        ''', (account_id,))
        
        account = cursor.fetchone()
        if not account:
            flash('Account not found', 'error')
            return redirect(url_for('accounts'))
        
        # Get current balance and transaction count
        current_balance = accounting.get_account_balance(account_id)
        
        cursor.execute('''
            SELECT COUNT(*) as count FROM transaction_entries WHERE account_id = ?
        ''', (account_id,))
        transaction_count = cursor.fetchone()['count']
        
        # Get parent accounts for dropdown
        cursor.execute('SELECT id, name FROM accounts WHERE is_active = 1 ORDER BY id')
        parent_accounts = cursor.fetchall()
        
        return render_template('edit_account.html', 
                             account=account,
                             current_balance=current_balance,
                             transaction_count=transaction_count,
                             account_types=[t.value for t in AccountType],
                             parent_accounts=parent_accounts)
        
    except Exception as e:
        flash(f'Error editing account: {str(e)}', 'error')
        return redirect(url_for('accounts'))

@app.route('/accounts/<account_id>/delete')
def delete_account(account_id):
    """Delete an account (only if balance is zero)"""
    try:
        accounting = get_accounting_system()
        balance = accounting.get_account_balance(account_id)
        
        if balance != 0:
            flash('Cannot delete account with non-zero balance', 'error')
            return redirect(url_for('accounts'))
        
        cursor = accounting.conn.cursor()
        cursor.execute('DELETE FROM accounts WHERE id = ?', (account_id,))
        accounting.conn.commit()
        
        flash('Account deleted successfully!', 'success')
        
    except Exception as e:
        flash(f'Error deleting account: {str(e)}', 'error')
    
    return redirect(url_for('accounts'))

@app.route('/accounts/<account_id>/toggle')
def toggle_account(account_id):
    """Toggle account active status"""
    try:
        accounting = get_accounting_system()
        cursor = accounting.conn.cursor()
        
        cursor.execute('UPDATE accounts SET is_active = NOT is_active WHERE id = ?', (account_id,))
        accounting.conn.commit()
        
        flash('Account status updated!', 'success')
        
    except Exception as e:
        flash(f'Error updating account: {str(e)}', 'error')
    
    return redirect(url_for('accounts'))

@app.route('/transactions')
def transactions():
    """List transactions with multi-bank account balances"""
    try:
        accounting = get_accounting_system()
        page = int(request.args.get('page', 1))
        per_page = 20
        offset = (page - 1) * per_page
        
        # Get transactions with bank balance effects
        transactions_data, bank_account_names = accounting.get_transactions_with_bank_balances(per_page, offset)
        
        # Get total transaction count
        cursor = accounting.conn.cursor()
        cursor.execute('SELECT COUNT(*) as count FROM transactions')
        total_transactions = cursor.fetchone()['count']
        
        # Calculate pagination
        total_pages = (total_transactions + per_page - 1) // per_page
        has_prev = page > 1
        has_next = page < total_pages
        
        return render_template('transactions.html',
                             transactions_data=transactions_data,
                             bank_accounts=bank_account_names,
                             page=page,
                             total_pages=total_pages,
                             has_prev=has_prev,
                             has_next=has_next)
                             
    except Exception as e:
        flash(f'Error loading transactions: {str(e)}', 'error')
        return render_template('transactions.html',
                             transactions_data=[],
                             bank_accounts={},
                             page=1,
                             total_pages=1,
                             has_prev=False,
                             has_next=False)

@app.route('/accounts/<account_id>/transactions')
def account_transactions(account_id):
    """View transaction history for a specific account"""
    try:
        accounting = get_accounting_system()
        
        # Get account info
        cursor = accounting.conn.cursor()
        cursor.execute('SELECT id, name, account_type FROM accounts WHERE id = ?', (account_id,))
        account = cursor.fetchone()
        
        if not account:
            flash('Account not found', 'error')
            return redirect(url_for('accounts'))
        
        # Get transaction history with running balance
        transaction_history = accounting.get_account_transaction_history(account_id, 200)
        
        # Reverse to show most recent first
        transaction_history.reverse()
        
        # Get current balance
        current_balance = accounting.get_account_balance(account_id)
        
        return render_template('account_transactions.html',
                             account=account,
                             transactions=transaction_history,
                             current_balance=current_balance)
        
    except Exception as e:
        flash(f'Error loading account transactions: {str(e)}', 'error')
        return redirect(url_for('accounts'))
    
@app.route('/cash-flow')
def cash_flow_summary():
    """Cash flow summary across all bank accounts"""
    try:
        accounting = get_accounting_system()
        
        # Get all bank accounts with current balances
        bank_accounts = accounting.get_bank_accounts()
        account_balances = {}
        total_cash = Decimal('0')
        
        for acc in bank_accounts:
            balance = accounting.get_account_balance(acc['id'])
            account_balances[acc['id']] = {
                'name': acc['name'],
                'balance': balance
            }
            total_cash += balance
        
        # Get recent cash-affecting transactions
        transactions_data, bank_names = accounting.get_transactions_with_bank_balances(30, 0)
        
        return render_template('cash_flow.html',
                             account_balances=account_balances,
                             total_cash=total_cash,
                             recent_transactions=transactions_data,
                             bank_names=bank_names)
                             
    except Exception as e:
        flash(f'Error loading cash flow: {str(e)}', 'error')
        return render_template('cash_flow.html',
                             account_balances={},
                             total_cash=0,
                             recent_transactions=[],
                             bank_names={})


# Replace your new_transaction route with this version:
@app.route('/transactions/new', methods=['GET', 'POST'])
def new_transaction():
    """Create new transaction with auto-generated ID"""
    if request.method == 'POST':
        try:
            accounting = get_accounting_system()
            
            # Get form data
            date_str = request.form['date']
            trn_date = datetime.strptime(date_str, '%Y-%m-%d').date()
            description = request.form['description']
            reference = request.form.get('reference', '')
            
            # Parse entries from form to calculate total amount
            entries = []
            entry_count = int(request.form.get('entry_count', 0))
            total_amount = Decimal('0')
            
            for i in range(entry_count):
                account_id = request.form.get(f'entries[{i}][account_id]')
                debit = Decimal(request.form.get(f'entries[{i}][debit]', '0') or '0')
                credit = Decimal(request.form.get(f'entries[{i}][credit]', '0') or '0')
                entry_desc = request.form.get(f'entries[{i}][description]', '')
                
                if account_id and (debit > 0 or credit > 0):
                    entries.append((account_id, debit, credit, entry_desc))
                    total_amount += max(debit, credit)  # Use larger amount for ID generation
            
            # Auto-generate transaction ID
            transaction_id = accounting.generate_transaction_id(trn_date, total_amount)
            
            if accounting.create_transaction(transaction_id, trn_date, description, entries, reference):
                flash(f'Transaction {transaction_id} created successfully!', 'success')
                return redirect(url_for('transactions'))
            else:
                flash('Failed to create transaction. Check that debits equal credits.', 'error')
                
        except Exception as e:
            flash(f'Error creating transaction: {str(e)}', 'error')
    
    try:
        # Get accounts for dropdown
        accounting = get_accounting_system()
        cursor = accounting.conn.cursor()
        cursor.execute('SELECT id, name FROM accounts WHERE is_active = 1 ORDER BY id')
        accounts_list = cursor.fetchall()
        
        return render_template('new_transaction.html', accounts=accounts_list)
    except Exception as e:
        flash(f'Error loading form: {str(e)}', 'error')
        return render_template('new_transaction.html', accounts=[])

# Add the missing transaction detail route:
@app.route('/transactions/<transaction_id>')
def transaction_detail(transaction_id):
    """View transaction details"""
    try:
        accounting = get_accounting_system()
        cursor = accounting.conn.cursor()
        
        # Get transaction info
        cursor.execute('''
            SELECT id, date, description, reference, created_date
            FROM transactions 
            WHERE id = ?
        ''', (transaction_id,))
        
        transaction = cursor.fetchone()
        if not transaction:
            flash('Transaction not found', 'error')
            return redirect(url_for('transactions'))
        
        # Get transaction entries
        cursor.execute('''
            SELECT te.id, te.account_id, a.name, te.debit_amount, te.credit_amount, te.description
            FROM transaction_entries te
            JOIN accounts a ON te.account_id = a.id
            WHERE te.transaction_id = ?
            ORDER BY te.id
        ''', (transaction_id,))
        
        entries = cursor.fetchall()
        
        return render_template('transaction_detail.html', 
                             transaction=transaction,
                             entries=entries)
    except Exception as e:
        flash(f'Error loading transaction: {str(e)}', 'error')
        return redirect(url_for('transactions'))

@app.route('/transactions/<transaction_id>/edit', methods=['GET', 'POST'])
def edit_transaction(transaction_id):
    """Edit an existing transaction"""
    try:
        accounting = get_accounting_system()
        cursor = accounting.conn.cursor()
        
        if request.method == 'POST':
            date_str = request.form['date']
            trn_date = datetime.strptime(date_str, '%Y-%m-%d').date()
            description = request.form['description']
            reference = request.form.get('reference', '')
            
            # Parse entries from form
            entries = []
            entry_count = int(request.form.get('entry_count', 0))
            
            for i in range(entry_count):
                account_id = request.form.get(f'entries[{i}][account_id]')
                debit = Decimal(request.form.get(f'entries[{i}][debit]', '0') or '0')
                credit = Decimal(request.form.get(f'entries[{i}][credit]', '0') or '0')
                entry_desc = request.form.get(f'entries[{i}][description]', '')
                
                if account_id and (debit > 0 or credit > 0):
                    entries.append((account_id, debit, credit, entry_desc))
            
            # Validate double-entry bookkeeping
            total_debits = sum(entry[1] for entry in entries)
            total_credits = sum(entry[2] for entry in entries)
            
            if total_debits != total_credits:
                flash('Transaction not balanced: Debits must equal Credits', 'error')
                return redirect(request.url)
            
            # Delete old entries and create new ones
            cursor.execute('DELETE FROM transaction_entries WHERE transaction_id = ?', (transaction_id,))
            
            # Update transaction
            cursor.execute('''
                UPDATE transactions 
                SET date = ?, description = ?, reference = ?
                WHERE id = ?
            ''', (trn_date.isoformat(), description, reference, transaction_id))
            
            # Insert new transaction entries
            for i, (account_id, debit, credit, entry_desc) in enumerate(entries):
                entry_id = f"{transaction_id}_{i+1}"
                cursor.execute('''
                    INSERT INTO transaction_entries 
                    (id, transaction_id, account_id, debit_amount, credit_amount, description)
                    VALUES (?, ?, ?, ?, ?, ?)
                ''', (entry_id, transaction_id, account_id, float(debit), float(credit), entry_desc))
            
            accounting.conn.commit()
            flash('Transaction updated successfully!', 'success')
            return redirect(url_for('transactions'))
        
        # GET request - show edit form
        cursor.execute('''
            SELECT id, date, description, reference, created_date
            FROM transactions WHERE id = ?
        ''', (transaction_id,))
        
        transaction = cursor.fetchone()
        if not transaction:
            flash('Transaction not found', 'error')
            return redirect(url_for('transactions'))
        
        # Get transaction entries
        cursor.execute('''
            SELECT te.id, te.account_id, a.name, te.debit_amount, te.credit_amount, te.description
            FROM transaction_entries te
            JOIN accounts a ON te.account_id = a.id
            WHERE te.transaction_id = ?
            ORDER BY te.id
        ''', (transaction_id,))
        
        entries = cursor.fetchall()
        
        # Get accounts for dropdown - Convert Row objects to simple tuples
        cursor.execute('SELECT id, name FROM accounts WHERE is_active = 1 ORDER BY id')
        accounts_rows = cursor.fetchall()
        
        # Convert Row objects to simple list of tuples for JSON serialization
        accounts_list = [(row['id'], row['name']) for row in accounts_rows]
        
        return render_template('edit_transaction.html',
                             transaction=transaction,
                             entries=entries,
                             accounts=accounts_list)
        
    except Exception as e:
        flash(f'Error editing transaction: {str(e)}', 'error')
        return redirect(url_for('transactions'))

@app.route('/transactions/<transaction_id>/delete')
def delete_transaction(transaction_id):
    """Delete a transaction"""
    try:
        accounting = get_accounting_system()
        cursor = accounting.conn.cursor()
        
        # Delete transaction entries first (foreign key constraint)
        cursor.execute('DELETE FROM transaction_entries WHERE transaction_id = ?', (transaction_id,))
        # Delete transaction
        cursor.execute('DELETE FROM transactions WHERE id = ?', (transaction_id,))
        
        accounting.conn.commit()
        flash('Transaction deleted successfully!', 'success')
        
    except Exception as e:
        flash(f'Error deleting transaction: {str(e)}', 'error')
    
    return redirect(url_for('transactions'))

@app.route('/reports')
def reports():
    """Reports menu"""
    return render_template('reports.html')

@app.route('/reports/trial-balance')
def trial_balance():
    """Generate trial balance"""
    try:
        accounting = get_accounting_system()
        as_of_date = request.args.get('as_of_date')
        if as_of_date:
            as_of_date = datetime.strptime(as_of_date, '%Y-%m-%d').date()
        
        trial_balance_data = accounting.generate_trial_balance(as_of_date)
        
        return render_template('trial_balance.html', 
                             trial_balance=trial_balance_data,
                             as_of_date=as_of_date)
    except Exception as e:
        flash(f'Error generating trial balance: {str(e)}', 'error')
        return render_template('trial_balance.html', 
                             trial_balance=[],
                             as_of_date=None)

@app.route('/reports/income-statement')
def income_statement():
    """Generate income statement"""
    start_date_str = request.args.get('start_date')
    end_date_str = request.args.get('end_date')
    
    if start_date_str and end_date_str:
        try:
            accounting = get_accounting_system()
            start_date = datetime.strptime(start_date_str, '%Y-%m-%d').date()
            end_date = datetime.strptime(end_date_str, '%Y-%m-%d').date()
            
            income_data = accounting.generate_income_statement(start_date, end_date)
            return render_template('income_statement.html', 
                                 income_statement=income_data,
                                 start_date=start_date,
                                 end_date=end_date)
        except Exception as e:
            flash(f'Error generating income statement: {str(e)}', 'error')
    
    return render_template('income_statement.html')

@app.route('/reports/balance-sheet')
def balance_sheet():
    """Generate balance sheet"""
    as_of_date_str = request.args.get('as_of_date')
    
    if as_of_date_str:
        try:
            accounting = get_accounting_system()
            as_of_date = datetime.strptime(as_of_date_str, '%Y-%m-%d').date()
            balance_sheet_data = accounting.generate_balance_sheet(as_of_date)
            return render_template('balance_sheet.html',
                                 balance_sheet=balance_sheet_data,
                                 as_of_date=as_of_date)
        except Exception as e:
            flash(f'Error generating balance sheet: {str(e)}', 'error')
    
    return render_template('balance_sheet.html')

@app.route('/import', methods=['GET', 'POST'])
def import_ofx():
    """Import OFX file"""
    if request.method == 'POST':
        if 'ofx_file' not in request.files:
            flash('No file selected', 'error')
            return redirect(request.url)
        
        file = request.files['ofx_file']
        if file.filename == '':
            flash('No file selected', 'error')
            return redirect(request.url)
        
        cash_account = request.form['cash_account']
        
        try:
            accounting = get_accounting_system()
            # Save uploaded file temporarily
            with tempfile.NamedTemporaryFile(mode='w+b', delete=False, suffix='.ofx') as tmp_file:
                file.save(tmp_file.name)
                
                # Import transactions
                count = accounting.import_ofx_transactions(tmp_file.name, cash_account)
                
                # Clean up temp file
                os.unlink(tmp_file.name)
                
                flash(f'Successfully imported {count} transactions!', 'success')
                return redirect(url_for('transactions'))
                
        except Exception as e:
            flash(f'Import failed: {str(e)}', 'error')
    
    try:
        # Get cash accounts for dropdown
        accounting = get_accounting_system()
        cursor = accounting.conn.cursor()
        cursor.execute('''
            SELECT id, name 
            FROM accounts 
            WHERE account_type = 'ASSET' AND is_active = 1 
            ORDER BY id
        ''')
        cash_accounts = cursor.fetchall()
        
        return render_template('import_ofx.html', cash_accounts=cash_accounts)
    except Exception as e:
        flash(f'Error loading form: {str(e)}', 'error')
        return render_template('import_ofx.html', cash_accounts=[])

@app.route('/export')
def export_menu():
    """Export menu"""
    try:
        accounting = get_accounting_system()
        cursor = accounting.conn.cursor()
        cursor.execute('SELECT id, name FROM accounts WHERE is_active = 1 ORDER BY id')
        accounts_list = cursor.fetchall()
        
        return render_template('export.html', accounts=accounts_list)
    except Exception as e:
        flash(f'Error loading accounts: {str(e)}', 'error')
        return render_template('export.html', accounts=[])

@app.route('/export/ofx')
def export_ofx():
    """Export to OFX file"""
    account_id = request.args.get('account_id')
    start_date_str = request.args.get('start_date')
    end_date_str = request.args.get('end_date')
    
    if not all([account_id, start_date_str, end_date_str]):
        flash('Please provide all required fields', 'error')
        return redirect(url_for('export_menu'))
    
    try:
        accounting = get_accounting_system()
        start_date = datetime.strptime(start_date_str, '%Y-%m-%d').date()
        end_date = datetime.strptime(end_date_str, '%Y-%m-%d').date()
        
        ofx_content = accounting.export_to_ofx(account_id, start_date, end_date)
        
        # Create file-like object for download
        ofx_file = io.BytesIO()
        ofx_file.write(ofx_content.encode('utf-8'))
        ofx_file.seek(0)
        
        filename = f"export_{account_id}_{start_date}_{end_date}.ofx"
        
        return send_file(ofx_file, 
                        as_attachment=True, 
                        download_name=filename,
                        mimetype='application/x-ofx')
                        
    except Exception as e:
        flash(f'Export failed: {str(e)}', 'error')
        return redirect(url_for('export_menu'))

@app.route('/api/accounts')
def api_accounts():
    """API endpoint for accounts (for AJAX)"""
    try:
        accounting = get_accounting_system()
        cursor = accounting.conn.cursor()
        cursor.execute('SELECT id, name FROM accounts WHERE is_active = 1 ORDER BY name')
        accounts_list = [{'id': row['id'], 'name': row['name']} for row in cursor.fetchall()]
        return jsonify(accounts_list)
    except Exception as e:
        return jsonify({'error': str(e)}), 500

@app.route('/api/account-balance/<account_id>')
def api_account_balance(account_id):
    """API endpoint for account balance"""
    try:
        accounting = get_accounting_system()
        balance = accounting.get_account_balance(account_id)
        return jsonify({'balance': float(balance)})
    except Exception as e:
        return jsonify({'error': str(e)}), 500

# Template filters
@app.template_filter('currency')
def currency_filter(value):
    """Format currency values"""
    if value is None:
        return "$0.00"
    return f"${float(value):,.2f}"

@app.template_filter('date_format')
def date_format_filter(value):
    """Format dates"""
    if isinstance(value, str):
        return value
    return value.strftime('%Y-%m-%d') if value else ''

if __name__ == '__main__':
    print("Starting OFX Accounting System Web UI...")
    print("Open your browser to: http://localhost:8080")
    print("Press Ctrl+C to stop the server")
    app.run(debug=True, host='0.0.0.0', port=8080)