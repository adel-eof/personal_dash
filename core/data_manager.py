# core/data_manager.py
import json
import datetime
import shutil
import os
import sqlite3

# Import database functions and constants
from core.database import get_db_connection, setup_database, DB_FILE

# Global constants are now defined in core/database.py (DB_FILE)
# JSON/Pickle code is removed as per instruction

def initialize_data():
    """Creates the initial, empty configuration data structure."""
    today_str = datetime.date.today().strftime("%Y-%m-%d")
    return {
        'tasks': [], # These are now managed directly by DB functions in feature files
        'expenses': [], # These are now managed directly by DB functions in feature files
        'documents': [], # These are now managed directly by DB functions in feature files
        'leave': {
            'annual_leave_days': 12.0,
            'start_date': today_str,
            'taken_days': 0.0,
            'carried_over_days': 0.0,
            'leave_logs': []
        },
        'salary': {
            'monthly_base': 5000.0,
            'total_fiscal_days': 22.0,
            'overseas_allowance_rate': 20.0,
            'allowance_logs': []
        }
    }

def load_data():
    """Loads configuration data (salary/leave setup) from the DB settings table."""

    # 1. Ensure the database structure exists
    # If the DB file is new, setup_database will create tables and initialize.
    db_exists = os.path.exists('personal_dashboard.db')
    setup_database() # This call initializes tables if they don't exist

    conn = get_db_connection()
    cursor = conn.cursor()

    app_data = initialize_data()
    data_exists = False

    try:
        # 2. Retrieve settings from the 'settings' table
        cursor.execute("SELECT key, value FROM settings")
        settings = dict(cursor.fetchall())
        conn.close()

        if settings:
            data_exists = True
            # Load Salary and Leave setups from settings (stored as JSON strings)

            # NOTE: We use .get(..., '{}') to prevent KeyError if the key is missing but the table exists.
            salary_config = json.loads(settings.get('salary', '{}'))
            leave_config = json.loads(settings.get('leave', '{}'))

            app_data['salary'].update(salary_config)
            app_data['leave'].update(leave_config)

        if db_exists:
            print("Configuration data loaded from database.")

    except sqlite3.OperationalError:
        # Should not happen if setup_database() runs first, but kept as a safeguard
        conn.close()
        pass

    return app_data, data_exists


def save_data(data):
    """Saves configuration data (salary/leave setup) to the DB settings table."""
    conn = get_db_connection()
    cursor = conn.cursor()

    # Only store the configuration sections (salary and leave setup) in the settings table.
    settings_to_save = {
        'salary': json.dumps(data.get('salary', {})),
        'leave': json.dumps(data.get('leave', {})),
    }

    for key, value in settings_to_save.items():
        # INSERT OR REPLACE ensures we update existing keys or create new ones
        cursor.execute("""
            INSERT OR REPLACE INTO settings (key, value)
            VALUES (?, ?)
        """, (key, value))

    conn.commit()
    conn.close()

def create_database_backup():
    """
    Creates a time-stamped backup of the SQLite database file.
    """
    try:
        if not os.path.exists(DB_FILE):
            return "Error: Database file not found. Cannot create backup.", 'red'

        backup_dir = os.path.join(os.getcwd(), 'backup')
        if not os.path.exists(backup_dir):
            os.makedirs(backup_dir)

        # Create a timestamped backup file name
        timestamp = datetime.datetime.now().strftime("%Y%m%d_%H%M%S")
        backup_filename = f"personal_dashboard_backup_{timestamp}.bak"

        backup_path = os.path.join(backup_dir, backup_filename)

        # Use shutil to copy the file safely
        shutil.copy2(DB_FILE, backup_path)

        return f"Database successfully backed up to: {backup_path}", 'green'

    except Exception as e:
        return f"Critical error during backup: {e}", 'red'
