# dashboard.py
import datetime
import os
import inspect
import math
import json
from decimal import Decimal, ROUND_HALF_UP
from dateutil.relativedelta import relativedelta
from termcolor import colored # ADDED: for color output
import re

# Core Imports
from core.data_manager import load_data, save_data, create_database_backup
from core.validation import get_valid_date_input, get_valid_float_input
from core.database import setup_database, DB_FILE

# Feature Imports
from features.salary_tracker import setup_salary, salary_bonus_tracker
from features.leave_tracker import setup_leave, leave_balance_tracker
from features.expense_tracker import expense_tracker
from features.document_expiry_tracker import document_expiry_tracker
from features.task_manager import task_manager
from features.ai_tools import parse_and_execute_tool, load_local_llm, call_local_llm
from features.loan_tracker import loan_tracker


# --- GLOBAL CONTEXT ---
CONVERSATION_HISTORY = []
MAX_HISTORY_TURNS = 2 # Store user query + LLM response/result (4 list items total)
# --------------------------

# --- NEW UTILITY FUNCTION ---
def strip_ansi_and_calculate_width(text):
    """Strips ANSI escape codes (color) to calculate the true visible length of a string."""
    # Pattern to match ANSI escape codes
    ansi_escape = re.compile(r'\x1B(?:[@-Z\\-_]|\[[0-?]*[ -/]*[@-~])')
    return len(ansi_escape.sub('', text))
# ----------------------------

# --- Reusable Table Printing Function (Centralized utility) ---
def print_log_table(headers, logs, column_keys, currency_cols=None):
    """
    Dynamically calculates column widths and prints data in a clean, aligned table format.
    """
    if not logs:
        print("No logs found.")
        return

    widths = [len(h) for h in headers]
    data_rows = []

    for log in logs:
        row = []
        for i, key in enumerate(column_keys):
            value = log.get(key)

            if key in ['days', 'overseas_days', 'overtime_days']:
                formatted_value = f"{value:.1f}"
            elif key in ['allowance_amount', 'overtime_amount', 'total_earned', 'total_spent', 'amount']:
                formatted_value = f"${value:.2f}"
            elif key == 'description':
                formatted_value = str(value)[:30]
            else:
                formatted_value = str(value)

            row.append(formatted_value)

            # --- FIX: Calculate width using the stripper ---
            data_width = strip_ansi_and_calculate_width(formatted_value)
            widths[i] = max(widths[i], data_width)
            # ---------------------------------------------)
        data_rows.append(row)

    if currency_cols:
        for i in currency_cols:
            widths[i] += 1

    format_spec = " | ".join([f"%-{w}s" for w in widths])
    separator = "+-" + "-+-".join(["-" * w for w in widths]) + "-+"

    print(separator)
    print("| " + format_spec % tuple(headers) + " |")
    print(separator)

    # Print data rows, but use the stripped width for padding calculation
    for row in data_rows:
        # We need to manually calculate padding to correctly account for color codes
        formatted_row = []
        for i, cell in enumerate(row):
            visible_width = strip_ansi_and_calculate_width(cell)
            padding_needed = widths[i] - visible_width

            # Pad the string manually using the calculated padding
            formatted_cell = cell + ' ' * padding_needed
            formatted_row.append(formatted_cell)

        print("| " + " | ".join(formatted_row) + " |")

    print(separator)

# --- Feature Modules (Placeholder logic, actual logic imported) ---

def task_manager(data):
    """Manages tasks: display, add, complete. (Assumed to return to main menu after action)"""
    # NOTE: Assuming task_manager has internal logic (not shown here)
    from features.task_manager import task_manager as _task_manager_func
    _task_manager_func(data)


def ai_query_interface(app_data):
    """
    Handles the user interaction for the AI assistant, calling the local LLM.
    STAYS IN A LOOP until the user explicitly quits the submenu.
    """

    global CONVERSATION_HISTORY # Access the global list

    from features.ai_tools import LLM_MODEL # Access the global state directly
    if LLM_MODEL is None:
        # Load the model only now. The function handles the print/error messages.
        if load_local_llm() is None:
            print(colored("\n[ERROR] AI Assistant failed to load. Returning to Main Menu.", 'red'))
            return

    while True: # LOOP ADDED HERE for persistence
        print(colored("\n--- 🧠 AI Assistant Query ---", 'cyan')) # COLORIZED HEADER

        # --- USAGE TIP ADDITION ---
        if not CONVERSATION_HISTORY:
            print(colored("Tip: Try asking for totals ('What is my total expense?') or use relative dates ('What about last month?').", 'yellow'))
        # --------------------------

        print(colored("Type 'B' or 'Back' to return to the Main Menu. Conversation history will be reset.", 'light_grey'))

        user_input = input("\nAsk the AI a question:\n> ").strip()

        if user_input.upper() in ['B', 'BACK']:
            print(colored("Returning to Main Menu.", 'green'))
            # Reset history to keep main menu context clean
            CONVERSATION_HISTORY.clear()
            return # EXIT THE LOOP and return to main()

        user_query = user_input.lower()

        # 1. Call the local LLM to get the structured JSON output, passing history
        llm_response_text = call_local_llm(user_query, CONVERSATION_HISTORY)

        if llm_response_text is None:
            print(colored("\n[ERROR] AI Assistant: Cannot proceed. Local LLM is not loaded.", 'red'))
            continue # Stay in the loop

        # 2. Pipeline Execution
        result = parse_and_execute_tool(llm_response_text)

        # 3. Update History (Store User Query and Final Result)
        CONVERSATION_HISTORY.append({"role": "user", "content": user_query})
        CONVERSATION_HISTORY.append({"role": "assistant", "content": result})

        # Trim history to the last MAX_HISTORY_TURNS
        if len(CONVERSATION_HISTORY) > MAX_HISTORY_TURNS * 2:
            CONVERSATION_HISTORY = CONVERSATION_HISTORY[-(MAX_HISTORY_TURNS * 2):]

        # Display result with cleaner, colorized separators
        print(colored("-" * 50, 'blue'))
        print(result)
        print(colored("-" * 50, 'blue'))


# --- Main Application Loop ---
def main():
    """The main application entry point."""
    print(colored("🚀 Loading Personal Dashboard...", 'green')) # COLORIZED STARTUP

    app_data, data_file_existed = load_data()

    # load_local_llm()

    if not data_file_existed:
        print(colored("\n" + "="*40, 'magenta'))
        print(colored("    FIRST RUN SETUP: Enter Initial Information", 'magenta'))
        print(colored("="*40, 'magenta'))

        setup_leave(app_data)
        setup_salary(app_data)
        save_data(app_data)

        print(colored("\nInitial setup complete. Starting application.", 'green'))

    while True:
        save_data(app_data)

        print(colored("\n" + "="*40, 'cyan'))
        print(colored("        PERSONAL DASHBOARD MENU", 'cyan'))
        print(colored("="*40, 'cyan'))
        print("1. 📝 Task Manager")
        print("2. 💰 Expense Tracker")
        print("3. 📄 Document Expiry Tracker")
        print("4. ⛱️ Leave Balance Tracker")
        print("5. 💵 Salary and Bonus Tracker")
        print("6. 🏦 **Loan Tracker**")
        print("7. 🧠 Ask AI Assistant")
        print("8. 💾 **Data Backup**")
        print(colored("Q. Quit and Save", 'red')) # COLORIZED QUIT
        print("-" * 40)

        choice = input(colored("Enter your choice: ", 'green')).upper() # COLORIZED INPUT PROMPT

        # NOTE: The feature functions (1-5) are still assumed to return to the main menu loop.
        if choice == '1':
            task_manager(app_data)
        elif choice == '2':
            expense_tracker(app_data, print_log_table)
        elif choice == '3':
            document_expiry_tracker(app_data, print_log_table)
        elif choice == '4':
            leave_balance_tracker(app_data, print_log_table)
        elif choice == '5':
            salary_bonus_tracker(app_data, print_log_table)
        elif choice == '6':
            loan_tracker(app_data, print_log_table)
        elif choice == '7':
            ai_query_interface(app_data) # This function now manages its own loop
        elif choice == '8': # NEW BACKUP LOGIC
            message, color = create_database_backup()
            print(colored(f"\n{message}", color))
        elif choice == 'Q':
            print(colored("\nGoodbye! All data has been saved.", 'red'))
            break
        else:
            print(colored("Invalid choice. Please select from the menu.", 'red'))

if __name__ == "__main__":
    main()
