# core/database.py
import sqlite3
import os
import json
import datetime

DB_FILE = 'personal_dashboard.db'
JSON_FILE = 'personal_dashboard_data.json'

def get_db_connection():
    """Returns a connection object to the SQLite database."""
    return sqlite3.connect(DB_FILE)

def setup_database(data=None):
    """Creates tables if they don't exist and attempts to migrate data from JSON."""
    conn = get_db_connection()
    cursor = conn.cursor()

    # --- 1. Create Tables ---
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS expenses (
            id INTEGER PRIMARY KEY,
            date TEXT NOT NULL,
            category TEXT NOT NULL,
            description TEXT,
            amount REAL NOT NULL
        )
    """)

    cursor.execute("""
        CREATE TABLE IF NOT EXISTS documents (
            id INTEGER PRIMARY KEY,
            name TEXT NOT NULL,
            expiry_date TEXT NOT NULL
        )
    """)

    cursor.execute("""
        CREATE TABLE IF NOT EXISTS tasks (
            id INTEGER PRIMARY KEY,
            task TEXT NOT NULL,
            done INTEGER NOT NULL
        )
    """)

    # Store dynamic config/metadata in a key-value store (e.g., salary, leave setup)
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS settings (
            key TEXT PRIMARY KEY,
            value TEXT NOT NULL
        )
    """)

    cursor.execute("""
        CREATE TABLE IF NOT EXISTS leave_logs (
            id INTEGER PRIMARY KEY,
            date TEXT NOT NULL,
            days REAL NOT NULL,
            description TEXT
        )
    """)

    cursor.execute("""
        CREATE TABLE IF NOT EXISTS allowance_logs (
            id INTEGER PRIMARY KEY,
            date TEXT NOT NULL,
            start_date TEXT,
            end_date TEXT,
            overseas_days REAL NOT NULL,
            overtime_days REAL NOT NULL,
            allowance_amount REAL NOT NULL,
            overtime_amount REAL NOT NULL,
            total_earned REAL NOT NULL
        )
    """)

    # 6. LOANS MASTER Table (NEW)
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS loans_master (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            description TEXT NOT NULL,
            total_amount REAL NOT NULL,
            monthly_payment REAL NOT NULL,
            start_date TEXT NOT NULL,
            duration_months INTEGER NOT NULL,
            due_day INTEGER, -- NEW COLUMN
            status TEXT NOT NULL DEFAULT 'Ongoing'
        )
    """)

    # 7. LOAN PAYMENTS Table (NEW)
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS loan_payments (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            loan_id INTEGER NOT NULL,
            payment_date TEXT NOT NULL,
            amount_paid REAL NOT NULL,
            FOREIGN KEY (loan_id) REFERENCES loans_master(id)
        )
    """)

    # --- 2. Data Migration from JSON ---
    if os.path.exists(JSON_FILE) and data:
        print("Attempting migration from JSON file...")

        # Migrate Expenses
        expense_data = data.get('expenses', [])
        for expense in expense_data:
            cursor.execute("""
                INSERT INTO expenses (date, category, description, amount)
                VALUES (?, ?, ?, ?)
            """, (expense['date'], expense['category'], expense['description'], expense['amount']))

        # Migrate Documents
        doc_data = data.get('documents', [])
        for i, doc in enumerate(doc_data):
            # Ensure date is string format for DB
            date_str = doc['expiry_date'].isoformat() if isinstance(doc['expiry_date'], datetime.date) else doc['expiry_date']
            cursor.execute("""
                INSERT INTO documents (name, expiry_date)
                VALUES (?, ?)
            """, (doc['name'], date_str))

        # Migrate Tasks
        task_data = data.get('tasks', [])
        for task in task_data:
            cursor.execute("""
                INSERT INTO tasks (id, task, done)
                VALUES (?, ?, ?)
            """, (task['id'], task['task'], 1 if task['done'] else 0))

        # Migrate Setup Data (Salary, Leave) - Storing as JSON string in settings
        settings_to_save = {
            'salary': json.dumps(data.get('salary', {})),
            'leave': json.dumps(data.get('leave', {})),
        }
        for key, value in settings_to_save.items():
            cursor.execute("""
                INSERT OR REPLACE INTO settings (key, value)
                VALUES (?, ?)
            """, (key, value))

        conn.commit()
        # Rename the old file so migration only runs once
        os.rename(JSON_FILE, JSON_FILE + '.migrated')
        print("Migration complete. Old JSON file renamed.")

    conn.close()

def execute_query(query, params=()):
    """Execute a read/write query and return the results."""
    conn = get_db_connection()
    cursor = conn.cursor()

    try:
        cursor.execute(query, params)
        if query.strip().upper().startswith('SELECT'):
            results = cursor.fetchall()
            # Get column names
            columns = [desc[0] for desc in cursor.description]
            conn.close()
            return columns, results
        else:
            conn.commit()
            conn.close()
            return None, None

    except sqlite3.Error as e:
        conn.close()
        raise sqlite3.Error(f"Database error executing query: {e}")
