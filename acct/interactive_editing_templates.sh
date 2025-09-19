#!/bin/bash
# Add interactive editing capabilities

# 1. Enhanced ACCOUNTS.HTML with edit/delete buttons
cat > templates/accounts.html << 'EOF'
{% extends "base.html" %}

{% block content %}
<div class="d-flex justify-content-between flex-wrap flex-md-nowrap align-items-center pt-3 pb-2 mb-3 border-bottom">
    <h1 class="h2">Chart of Accounts</h1>
    <div class="btn-toolbar mb-2 mb-md-0">
        <a href="/accounts/new" class="btn btn-sm btn-outline-secondary">
            <i class="fas fa-plus"></i> New Account
        </a>
    </div>
</div>

<div class="table-responsive">
    <table class="table table-striped">
        <thead>
            <tr>
                <th>Account ID</th>
                <th>Name</th>
                <th>Type</th>
                <th>Parent</th>
                <th>Balance</th>
                <th>Status</th>
                <th>Actions</th>
            </tr>
        </thead>
        <tbody>
            {% for account in accounts %}
            <tr>
                <td>{{ account[0] }}</td>
                <td>{{ account[1] }}</td>
                <td><span class="badge bg-secondary">{{ account[2] }}</span></td>
                <td>{{ account[3] or '-' }}</td>
                <td class="text-end">{{ account[5] | currency }}</td>
                <td>
                    {% if account[4] %}
                        <span class="badge bg-success">Active</span>
                    {% else %}
                        <span class="badge bg-danger">Inactive</span>
                    {% endif %}
                </td>
                <td>
                    <div class="btn-group btn-group-sm">
                        <a href="/accounts/{{ account[0] }}/edit" class="btn btn-outline-primary" title="Edit">
                            <i class="fas fa-edit"></i>
                        </a>
                        {% if account[5] == 0 %}
                            <button class="btn btn-outline-danger" onclick="deleteAccount('{{ account[0] }}')" title="Delete">
                                <i class="fas fa-trash"></i>
                            </button>
                        {% else %}
                            <button class="btn btn-outline-warning" onclick="toggleAccount('{{ account[0] }}')" title="Deactivate">
                                <i class="fas fa-ban"></i>
                            </button>
                        {% endif %}
                    </div>
                </td>
            </tr>
            {% endfor %}
        </tbody>
    </table>
</div>

<!-- Delete Confirmation Modal -->
<div class="modal fade" id="deleteModal" tabindex="-1">
    <div class="modal-dialog">
        <div class="modal-content">
            <div class="modal-header">
                <h5 class="modal-title">Delete Account</h5>
                <button type="button" class="btn-close" data-bs-dismiss="modal"></button>
            </div>
            <div class="modal-body">
                <p>Are you sure you want to delete this account? This action cannot be undone.</p>
                <p><strong>Note:</strong> Only accounts with zero balance can be deleted.</p>
            </div>
            <div class="modal-footer">
                <button type="button" class="btn btn-secondary" data-bs-dismiss="modal">Cancel</button>
                <button type="button" class="btn btn-danger" id="confirmDelete">Delete</button>
            </div>
        </div>
    </div>
</div>
{% endblock %}

{% block scripts %}
<script>
let accountToDelete = null;

function deleteAccount(accountId) {
    accountToDelete = accountId;
    new bootstrap.Modal(document.getElementById('deleteModal')).show();
}

function toggleAccount(accountId) {
    if (confirm('Toggle account status?')) {
        window.location.href = `/accounts/${accountId}/toggle`;
    }
}

document.getElementById('confirmDelete').addEventListener('click', function() {
    if (accountToDelete) {
        window.location.href = `/accounts/${accountToDelete}/delete`;
    }
});
</script>
{% endblock %}
EOF

# 2. EDIT ACCOUNT template
cat > templates/edit_account.html << 'EOF'
{% extends "base.html" %}

{% block content %}
<div class="d-flex justify-content-between flex-wrap flex-md-nowrap align-items-center pt-3 pb-2 mb-3 border-bottom">
    <h1 class="h2">Edit Account</h1>
</div>

<div class="row">
    <div class="col-md-6">
        <form method="POST">
            <div class="mb-3">
                <label for="account_id" class="form-label">Account ID</label>
                <input type="text" class="form-control" id="account_id" name="account_id" value="{{ account.id }}" readonly>
                <div class="form-text">Account ID cannot be changed</div>
            </div>
            
            <div class="mb-3">
                <label for="name" class="form-label">Account Name</label>
                <input type="text" class="form-control" id="name" name="name" value="{{ account.name }}" required>
            </div>
            
            <div class="mb-3">
                <label for="account_type" class="form-label">Account Type</label>
                <select class="form-select" id="account_type" name="account_type" required>
                    {% for type in account_types %}
                        <option value="{{ type }}" {% if account.account_type == type %}selected{% endif %}>{{ type }}</option>
                    {% endfor %}
                </select>
            </div>
            
            <div class="mb-3">
                <label for="parent_id" class="form-label">Parent Account (Optional)</label>
                <select class="form-select" id="parent_id" name="parent_id">
                    <option value="">None</option>
                    {% for parent in parent_accounts %}
                        {% if parent[0] != account.id %}
                            <option value="{{ parent[0] }}" {% if account.parent_id == parent[0] %}selected{% endif %}>
                                {{ parent[0] }} - {{ parent[1] }}
                            </option>
                        {% endif %}
                    {% endfor %}
                </select>
            </div>
            
            <div class="mb-3">
                <label for="description" class="form-label">Description</label>
                <textarea class="form-control" id="description" name="description" rows="3">{{ account.description or '' }}</textarea>
            </div>
            
            <div class="mb-3 form-check">
                <input type="checkbox" class="form-check-input" id="is_active" name="is_active" {% if account.is_active %}checked{% endif %}>
                <label class="form-check-label" for="is_active">Active</label>
            </div>
            
            <button type="submit" class="btn btn-primary">Update Account</button>
            <a href="/accounts" class="btn btn-secondary">Cancel</a>
        </form>
    </div>
    
    <div class="col-md-6">
        <div class="card">
            <div class="card-header">
                <h6>Account Information</h6>
            </div>
            <div class="card-body">
                <dl class="row">
                    <dt class="col-sm-4">Current Balance:</dt>
                    <dd class="col-sm-8">{{ current_balance | currency }}</dd>
                    
                    <dt class="col-sm-4">Created:</dt>
                    <dd class="col-sm-8">{{ account.created_date }}</dd>
                    
                    <dt class="col-sm-4">Transactions:</dt>
                    <dd class="col-sm-8">{{ transaction_count }}</dd>
                </dl>
                
                {% if transaction_count > 0 %}
                    <div class="alert alert-warning">
                        <i class="fas fa-exclamation-triangle"></i>
                        This account has {{ transaction_count }} transactions. 
                        Changing the account type may affect your reports.
                    </div>
                {% endif %}
            </div>
        </div>
    </div>
</div>
{% endblock %}
EOF

# 3. Enhanced TRANSACTIONS.HTML with edit buttons
cat > templates/transactions.html << 'EOF'
{% extends "base.html" %}

{% block content %}
<div class="d-flex justify-content-between flex-wrap flex-md-nowrap align-items-center pt-3 pb-2 mb-3 border-bottom">
    <h1 class="h2">Transactions</h1>
    <div class="btn-toolbar mb-2 mb-md-0">
        <a href="/transactions/new" class="btn btn-sm btn-outline-secondary">
            <i class="fas fa-plus"></i> New Transaction
        </a>
    </div>
</div>

<div class="table-responsive">
    <table class="table table-striped">
        <thead>
            <tr>
                <th>ID</th>
                <th>Date</th>
                <th>Description</th>
                <th>Reference</th>
                <th>Entries</th>
                <th>Amount</th>
                <th>Actions</th>
            </tr>
        </thead>
        <tbody>
            {% for transaction in transactions %}
            <tr>
                <td><a href="/transactions/{{ transaction[0] }}">{{ transaction[0] }}</a></td>
                <td>{{ transaction[1] }}</td>
                <td>{{ transaction[2] }}</td>
                <td>{{ transaction[3] or '-' }}</td>
                <td>{{ transaction[4] }}</td>
                <td class="text-end">{{ transaction[5] | currency }}</td>
                <td>
                    <div class="btn-group btn-group-sm">
                        <a href="/transactions/{{ transaction[0] }}/edit" class="btn btn-outline-primary" title="Edit">
                            <i class="fas fa-edit"></i>
                        </a>
                        <button class="btn btn-outline-danger" onclick="deleteTransaction('{{ transaction[0] }}')" title="Delete">
                            <i class="fas fa-trash"></i>
                        </button>
                    </div>
                </td>
            </tr>
            {% endfor %}
        </tbody>
    </table>
</div>

<!-- Pagination -->
{% if total_pages > 1 %}
<nav aria-label="Transaction pagination">
    <ul class="pagination justify-content-center">
        {% if has_prev %}
            <li class="page-item">
                <a class="page-link" href="?page={{ page - 1 }}">Previous</a>
            </li>
        {% endif %}
        
        {% for p in range(1, total_pages + 1) %}
            <li class="page-item {% if p == page %}active{% endif %}">
                <a class="page-link" href="?page={{ p }}">{{ p }}</a>
            </li>
        {% endfor %}
        
        {% if has_next %}
            <li class="page-item">
                <a class="page-link" href="?page={{ page + 1 }}">Next</a>
            </li>
        {% endif %}
    </ul>
</nav>
{% endif %}

<!-- Delete Confirmation Modal -->
<div class="modal fade" id="deleteModal" tabindex="-1">
    <div class="modal-dialog">
        <div class="modal-content">
            <div class="modal-header">
                <h5 class="modal-title">Delete Transaction</h5>
                <button type="button" class="btn-close" data-bs-dismiss="modal"></button>
            </div>
            <div class="modal-body">
                <p>Are you sure you want to delete this transaction? This action cannot be undone and will affect your account balances.</p>
            </div>
            <div class="modal-footer">
                <button type="button" class="btn btn-secondary" data-bs-dismiss="modal">Cancel</button>
                <button type="button" class="btn btn-danger" id="confirmDelete">Delete</button>
            </div>
        </div>
    </div>
</div>
{% endblock %}

{% block scripts %}
<script>
let transactionToDelete = null;

function deleteTransaction(transactionId) {
    transactionToDelete = transactionId;
    new bootstrap.Modal(document.getElementById('deleteModal')).show();
}

document.getElementById('confirmDelete').addEventListener('click', function() {
    if (transactionToDelete) {
        window.location.href = `/transactions/${transactionToDelete}/delete`;
    }
});
</script>
{% endblock %}
EOF

# 4. EDIT TRANSACTION template
cat > templates/edit_transaction.html << 'EOF'
{% extends "base.html" %}

{% block content %}
<div class="d-flex justify-content-between flex-wrap flex-md-nowrap align-items-center pt-3 pb-2 mb-3 border-bottom">
    <h1 class="h2">Edit Transaction</h1>
</div>

<div class="row">
    <div class="col-md-10">
        <form method="POST" id="transactionForm">
            <div class="row">
                <div class="col-md-4">
                    <div class="mb-3">
                        <label for="transaction_id" class="form-label">Transaction ID</label>
                        <input type="text" class="form-control" id="transaction_id" name="transaction_id" 
                               value="{{ transaction.id }}" readonly>
                        <div class="form-text">Transaction ID cannot be changed</div>
                    </div>
                </div>
                <div class="col-md-4">
                    <div class="mb-3">
                        <label for="date" class="form-label">Date</label>
                        <input type="date" class="form-control" id="date" name="date" 
                               value="{{ transaction.date }}" required>
                    </div>
                </div>
                <div class="col-md-4">
                    <div class="mb-3">
                        <label for="reference" class="form-label">Reference</label>
                        <input type="text" class="form-control" id="reference" name="reference" 
                               value="{{ transaction.reference or '' }}">
                    </div>
                </div>
            </div>
            
            <div class="mb-3">
                <label for="description" class="form-label">Description</label>
                <input type="text" class="form-control" id="description" name="description" 
                       value="{{ transaction.description }}" required>
            </div>
            
            <h5>Transaction Entries</h5>
            <div class="alert alert-info">
                <strong>Balance Check:</strong>
                <span id="balanceStatus">Checking balance...</span>
            </div>
            
            <div id="entries">
                {% for entry in entries %}
                <div class="row mb-3 transaction-entry">
                    <div class="col-md-4">
                        <label class="form-label">Account</label>
                        <select class="form-select" name="entries[{{ loop.index0 }}][account_id]" required>
                            {% for account in accounts %}
                                <option value="{{ account[0] }}" {% if entry[1] == account[0] %}selected{% endif %}>
                                    {{ account[0] }} - {{ account[1] }}
                                </option>
                            {% endfor %}
                        </select>
                    </div>
                    <div class="col-md-2">
                        <label class="form-label">Debit</label>
                        <input type="number" class="form-control debit-input" 
                               name="entries[{{ loop.index0 }}][debit]" 
                               value="{{ entry[3] if entry[3] > 0 else '' }}"
                               placeholder="0.00" step="0.01" min="0" onchange="updateBalance()">
                    </div>
                    <div class="col-md-2">
                        <label class="form-label">Credit</label>
                        <input type="number" class="form-control credit-input" 
                               name="entries[{{ loop.index0 }}][credit]" 
                               value="{{ entry[4] if entry[4] > 0 else '' }}"
                               placeholder="0.00" step="0.01" min="0" onchange="updateBalance()">
                    </div>
                    <div class="col-md-3">
                        <label class="form-label">Description</label>
                        <input type="text" class="form-control" 
                               name="entries[{{ loop.index0 }}][description]" 
                               value="{{ entry[5] or '' }}"
                               placeholder="Entry description">
                    </div>
                    <div class="col-md-1">
                        <label class="form-label">&nbsp;</label>
                        <button type="button" class="btn btn-danger btn-sm d-block" onclick="removeEntry(this)">
                            <i class="fas fa-trash"></i>
                        </button>
                    </div>
                </div>
                {% endfor %}
            </div>
            
            <div class="mb-3">
                <button type="button" class="btn btn-secondary" onclick="addEntry()">
                    <i class="fas fa-plus"></i> Add Entry
                </button>
            </div>
            
            <input type="hidden" id="entry_count" name="entry_count" value="{{ entries|length }}">
            
            <button type="submit" class="btn btn-primary" id="submitBtn">Update Transaction</button>
            <a href="/transactions" class="btn btn-secondary">Cancel</a>
        </form>
    </div>
</div>
{% endblock %}

{% block scripts %}
<script>
let entryCount = {{ entries|length }};
const accounts = {{ accounts | tojson }};

function addEntry() {
    const entriesDiv = document.getElementById('entries');
    
    const entryDiv = document.createElement('div');
    entryDiv.className = 'row mb-3 transaction-entry';
    entryDiv.innerHTML = `
        <div class="col-md-4">
            <label class="form-label">Account</label>
            <select class="form-select" name="entries[${entryCount}][account_id]" required>
                <option value="">Select Account...</option>
                ${accounts.map(acc => `<option value="${acc[0]}">${acc[0]} - ${acc[1]}</option>`).join('')}
            </select>
        </div>
        <div class="col-md-2">
            <label class="form-label">Debit</label>
            <input type="number" class="form-control debit-input" name="entries[${entryCount}][debit]" 
                   placeholder="0.00" step="0.01" min="0" onchange="updateBalance()">
        </div>
        <div class="col-md-2">
            <label class="form-label">Credit</label>
            <input type="number" class="form-control credit-input" name="entries[${entryCount}][credit]" 
                   placeholder="0.00" step="0.01" min="0" onchange="updateBalance()">
        </div>
        <div class="col-md-3">
            <label class="form-label">Description</label>
            <input type="text" class="form-control" name="entries[${entryCount}][description]" 
                   placeholder="Entry description">
        </div>
        <div class="col-md-1">
            <label class="form-label">&nbsp;</label>
            <button type="button" class="btn btn-danger btn-sm d-block" onclick="removeEntry(this)">
                <i class="fas fa-trash"></i>
            </button>
        </div>
    `;
    
    entriesDiv.appendChild(entryDiv);
    entryCount++;
    document.getElementById('entry_count').value = entryCount;
    updateBalance();
}

function removeEntry(button) {
    if (document.querySelectorAll('.transaction-entry').length > 2) {
        button.closest('.transaction-entry').remove();
        updateBalance();
    } else {
        alert('Transaction must have at least 2 entries');
    }
}

function updateBalance() {
    let totalDebits = 0;
    let totalCredits = 0;
    
    document.querySelectorAll('.debit-input').forEach(input => {
        totalDebits += parseFloat(input.value) || 0;
    });
    
    document.querySelectorAll('.credit-input').forEach(input => {
        totalCredits += parseFloat(input.value) || 0;
    });
    
    const statusSpan = document.getElementById('balanceStatus');
    const submitBtn = document.getElementById('submitBtn');
    
    statusSpan.textContent = `Total Debits: $${totalDebits.toFixed(2)}, Total Credits: $${totalCredits.toFixed(2)}`;
    
    if (Math.abs(totalDebits - totalCredits) < 0.01 && totalDebits > 0) {
        statusSpan.className = 'text-success';
        submitBtn.disabled = false;
    } else {
        statusSpan.className = 'text-danger';
        submitBtn.disabled = true;
    }
}

// Initial balance check
updateBalance();
</script>
{% endblock %}
EOF

echo "✅ Interactive editing templates created!"
echo "✅ Accounts: Edit name, type, parent, description, active status"
echo "✅ Transactions: Edit date, description, account assignments, amounts"
echo "✅ Delete confirmation modals for safety"
echo "✅ Real-time balance validation for transactions"
