# features/expense_tracker.py
import datetime
from core.validation import get_valid_float_input, get_valid_date_input
from core.database import execute_query
import sqlite3
from termcolor import colored

# --- NEW: Category Retrieval Function ---
def get_recent_categories(limit=5):
    """Retrieves the top N most frequent expense categories from the database."""
    try:
        # Query to count and group categories, ordering by count (frequency)
        query = """
            SELECT category, COUNT(category) as count
            FROM expenses
            GROUP BY category
            ORDER BY count DESC
            LIMIT ?
        """
        _, results = execute_query(query, (limit,))

        # Format results: returns a list of category names
        return [row[0].title() for row in results if row[0]]

    except sqlite3.Error as e:
        print(colored(f"[DB Error] Could not retrieve categories: {e}", 'red'))
        return []
# ----------------------------------------


def expense_reporting(data, print_log_table):
    """Calculates and displays expense summaries using SQL aggregations."""
    print(colored("\n--- 📊 Expense Reports ---", 'cyan'))

    try:
        # Get total overall spent
        total_spent_result = execute_query("SELECT SUM(amount) FROM expenses")
        total_spent = total_spent_result[1][0][0] if total_spent_result[1] and total_spent_result[1][0][0] is not None else 0.0

        if total_spent == 0.0:
            print("No expenses logged yet to generate a report.")
            return

        # Get Total Spending for Current Month
        today = datetime.date.today()
        current_month_key = today.strftime("%Y-%m")
        current_month_query = f"""
            SELECT SUM(amount) FROM expenses
            WHERE date LIKE '{current_month_key}-%'
        """
        month_spent_result = execute_query(current_month_query)
        current_month_total = month_spent_result[1][0][0] if month_spent_result[1] and month_spent_result[1][0][0] is not None else 0.0

        # Get Category Breakdown (Group By)
        category_query = """
            SELECT category, SUM(amount) as total_spent
            FROM expenses
            GROUP BY category
            ORDER BY total_spent DESC
        """
        columns, results = execute_query(category_query)

        # Prepare logs for table function
        report_logs = []
        for row in results:
            report_logs.append({
                'category': row[0].title(),
                'total_spent': row[1]
            })

        print(f"\n**Total Spending for {today.strftime('%B %Y')}: {colored(f'${current_month_total:.2f}', 'green')}**")
        print("\n**Category Breakdown (All Time):**")

        headers = ["CATEGORY", "TOTAL SPENT"]
        column_keys = ["category", "total_spent"]
        currency_cols = [1]

        print_log_table(headers, report_logs, column_keys, currency_cols)

    except sqlite3.Error as e:
        print(colored(f"Database Error during reporting: {e}", 'red'))

def filter_expenses(data, print_log_table):
    """Prompts user for filters and displays matching expense logs using SQL."""
    print(colored("\n--- 🔎 Filter Expenses ---", 'cyan'))

    print("Filter options (Type 'B' or leave blank to skip a filter):")

    category_filter = input("Filter by Category keyword: ").strip()
    if category_filter.upper() in ['B', 'BACK']:
        print(colored("Filtering cancelled.", 'yellow'))
        return

    start_date_str = get_valid_date_input("Filter Start Date (YYYY-MM-DD): ", allow_empty=True)
    if start_date_str is None and start_date_str != '':
        print(colored("Filtering cancelled.", 'yellow'))
        return

    end_date_str = get_valid_date_input("Filter End Date (YYYY-MM-DD): ", allow_empty=True)
    if end_date_str is None and end_date_str != '':
        print(colored("Filtering cancelled.", 'yellow'))
        return

    # Base query
    query = "SELECT date, category, description, amount FROM expenses WHERE 1=1"
    params = []

    if category_filter and category_filter.upper() not in ['B', 'BACK']:
        query += " AND lower(category) LIKE ?"
        params.append(f"%{category_filter.lower()}%")

    if start_date_str:
        query += " AND date >= ?"
        params.append(start_date_str)

    if end_date_str:
        query += " AND date <= ?"
        params.append(end_date_str)

    query += " ORDER BY date DESC"

    try:
        columns, results = execute_query(query, tuple(params))
    except sqlite3.Error as e:
        print(colored(f"Database Error during filtering: {e}", 'red'))
        return

    filtered_logs = []
    total_filtered_spent = 0.0

    for row in results:
        log = {
            'date': row[0],
            'category': row[1].title(),
            'description': row[2],
            'amount': row[3]
        }
        filtered_logs.append(log)
        total_filtered_spent += row[3]

    print(f"\n**Total Filtered Expenses ({len(filtered_logs)} items): {colored(f'${total_filtered_spent:.2f}', 'green')}**")

    if filtered_logs:
        headers = ["DATE", "CATEGORY", "DESCRIPTION", "AMOUNT"]
        column_keys = ["date", "category", "description", "amount"]
        currency_cols = [3]

        print_log_table(headers, filtered_logs, column_keys, currency_cols)
    else:
        print("No expenses matched the filter criteria.")


def expense_tracker(data, print_log_table):
    """
    Adds expenses, displays totals, and offers reports/filters using SQL.
    Includes Category Auto-Suggestion for logging expenses.
    """
    while True: # Persistence Loop
        print(colored("\n--- 💰 Expense Tracker ---", 'cyan'))

        # 1. Get total spent from DB
        try:
            total_result = execute_query("SELECT SUM(amount) FROM expenses")
            total_spent = total_result[1][0][0] if total_result[1] and total_result[1][0][0] is not None else 0.0
        except sqlite3.Error:
            total_spent = 0.0

        print(f"**Total logged expenses: {colored(f'${total_spent:.2f}', 'green')}**")

        print("\n[A]dd Expense, [R]eport, [D]isplay Recent, [F]ilter/Search, [B]ack to Main Menu")
        choice = input("Enter option: ").upper()

        if choice == 'A':
            # 1. Date Input and Cancellation Check
            date_str = get_valid_date_input("Date (YYYY-MM-DD, leave blank for today): ", allow_empty=True)
            if date_str is None:
                print(colored("Expense logging cancelled.", 'yellow'))
                continue

            if not date_str:
                date_str = datetime.date.today().strftime("%Y-%m-%d")

            # --- CATEGORY AUTO-SUGGESTION LOGIC ---
            suggested_categories = get_recent_categories()
            category_selection = None

            if suggested_categories:
                print(colored("\nSuggested Categories:", 'white'))
                # Display categories with index starting at 1
                for i, cat in enumerate(suggested_categories, 1):
                    print(f"[{i}] {cat}")

                # Get user input for selection or new category
                category_input = input(colored("Enter **index number** or **type a new category** (Type 'B' to cancel): ", 'yellow')).strip()

                if category_input.upper() in ['B', 'BACK']:
                    print(colored("Expense logging cancelled.", 'yellow'))
                    continue

                # Check if input is a valid index
                try:
                    index = int(category_input)
                    if 1 <= index <= len(suggested_categories):
                        category_selection = suggested_categories[index - 1]
                except ValueError:
                    # Input was text, treat it as a new category
                    category_selection = category_input.title() # Use .title() for consistent capitalization

            # Fallback if no suggestions or user typed a new one
            if category_selection is None:
                category_selection = input("Category (e.g., Food, Transport, Bills): ").strip().title()
                if not category_selection or category_selection.upper() in ['B', 'BACK']:
                    print(colored("Expense logging cancelled.", 'yellow'))
                    continue

            category = category_selection.lower() # Store in lowercase for consistency in DB queries
            print(f"Category set to: {category.title()}")

            desc = input("Description: ")

            # 2. Amount Input and Cancellation Check
            amount = get_valid_float_input("Amount spent: $", allow_negative=False)
            if amount is None:
                print(colored("Expense logging cancelled.", 'yellow'))
                continue

            # INSERT INTO DATABASE
            try:
                execute_query("""
                    INSERT INTO expenses (date, category, description, amount)
                    VALUES (?, ?, ?, ?)
                """, (date_str, category, desc, amount))
                print(colored(f"Expense of ${amount:.2f} logged successfully to database.", 'green'))
            except sqlite3.Error as e:
                print(colored(f"Error logging expense to database: {e}", 'red'))


        elif choice == 'R':
            expense_reporting(data, print_log_table)

        elif choice == 'D':
            print(colored("\n**Recent Expenses (from DB):**", 'cyan'))
            try:
                # SELECT recent 5 expenses
                columns, results = execute_query("SELECT date, category, description, amount FROM expenses ORDER BY date DESC LIMIT 5")

                if results:
                    table_logs = []
                    for row in results:
                        table_logs.append({
                            'date': row[0],
                            'category': row[1],
                            'description': row[2],
                            'amount': row[3]
                        })

                    headers = ["DATE", "CATEGORY", "DESCRIPTION", "AMOUNT"]
                    column_keys = ["date", "category", "description", "amount"]
                    currency_cols = [3]
                    print_log_table(headers, table_logs, column_keys, currency_cols)
                else:
                    print("No recent expenses found.")
            except sqlite3.Error as e:
                print(colored(f"Error retrieving recent expenses: {e}", 'red'))


        elif choice == 'F':
            filter_expenses(data, print_log_table)

        elif choice == 'B':
            # Exit the loop and return to the main menu
            return

        else:
            print(colored("Invalid option. Please choose A, R, D, F, or B.", 'red'))
