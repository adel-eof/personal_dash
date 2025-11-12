# dashboard.py
import datetime
import os
import inspect
import math
import json
from decimal import Decimal, ROUND_HALF_UP
from dateutil.relativedelta import relativedelta
import re
from rich.console import Console
from rich.table import Table
from rich import print as rprint

# Core Imports
from core.data_manager import load_data, save_data, create_database_backup
from core.validation import get_valid_date_input, get_valid_float_input
from core.database import setup_database, DB_FILE
# --- NEW IMPORTS ---
from core.formatting import format_currency, format_date, format_number
# -------------------

# Feature Imports
from features.salary_tracker import setup_salary, salary_bonus_tracker
from features.leave_tracker import leave_balance_tracker
from features.expense_tracker import expense_tracker
from features.document_expiry_tracker import document_expiry_tracker
from features.task_manager import task_manager
from features.ai_tools import parse_and_execute_tool, load_local_llm, call_local_llm
from features.loan_tracker import loan_tracker


# --- GLOBAL CONTEXT ---
CONVERSATION_HISTORY = []
MAX_HISTORY_TURNS = 2
# --------------------------

# --- NEW: Initialize Rich Console ---
CONSOLE = Console()
# ------------------------------------

# --- Utility Function (Kept for external calls, though Rich now handles width) ---
def strip_ansi_and_calculate_width(text):
    """Strips ANSI escape codes (color) to calculate the true visible length of a string."""
    ansi_escape = re.compile(r'\x1B(?:[@-Z\\-_]|\[[0-?]*[ -/]*[@-~])')
    return len(ansi_escape.sub('', text))
# ----------------------------

# --- Reusable Table Printing Function (REFACRORED for Formatting Utility) ---
def print_log_table(headers, logs, column_keys, currency_cols=None):
    """
    Prints data in a clean, aligned table format using the Rich library
    and centralized formatting utilities.
    """
    if not logs:
        CONSOLE.print("No logs found.")
        return

    # 1. Initialize Rich Table
    table = Table(title=None, show_header=True, header_style="bold cyan", min_width=80)

    # Set up columns
    for header in headers:
        if headers.index(header) in (currency_cols or []):
            table.add_column(header, style="green", justify="right")
        elif 'DATE' in header.upper() or 'PERIOD' in header.upper():
            table.add_column(header, style="yellow", justify="center")
        else:
            table.add_column(header, style="white")

    # 2. Populate Rows
    for log in logs:
        row = []
        for i, key in enumerate(column_keys):
            value = log.get(key)
            formatted_value = str(value)

            # --- Centralized Formatting Logic ---
            if value is None:
                formatted_value = ""
            elif key in ['days', 'overseas_days', 'overtime_days', 'duration_months']:
                # Format to 1 decimal place using the centralized utility
                formatted_value = format_number(value, decimals=1)
            elif key in ['allowance_amount', 'overtime_amount', 'total_earned', 'total_spent', 'amount', 'total', 'monthly', 'remaining', 'total_loan', 'amount_paid']:
                # Format as currency using the centralized utility
                formatted_value = format_currency(value)
            elif 'date' in key.lower() or 'period' in key.lower() or 'expiry' in key.lower():
                # Format date string using the centralized utility (handles N/A internally)
                formatted_value = format_date(str(value))
            elif key == 'description':
                formatted_value = str(value)[:30]
            else:
                # Value is already a string (potentially colored Rich markup) or a simple text field
                formatted_value = str(value)
            # --- End Centralized Formatting Logic ---

            row.append(formatted_value)

        table.add_row(*row)

    # 3. Print the table using the Console
    CONSOLE.print(table)


# --- Feature Modules (Placeholder logic, actual logic imported) ---

def task_manager(data):
    """Manages tasks: display, add, complete. (Assumed to return to main menu after action)"""
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
            rprint("[bold red]\n[ERROR] AI Assistant failed to load. Returning to Main Menu.[/bold red]")
            return

    while True: # LOOP ADDED HERE for persistence
        rprint("\n[bold cyan]--- 🧠 AI Assistant Query ---[/bold cyan]") # Rich print

        # --- USAGE TIP ADDITION ---
        if not CONVERSATION_HISTORY:
            rprint("[yellow]Tip: Try asking for totals ('What is my total expense?') or use relative dates ('What about last month?').[/yellow]")
        # --------------------------

        rprint("[grey50]Type 'B' or 'Back' to return to the Main Menu. Conversation history will be reset.[/grey50]")

        user_input = input("\nAsk the AI a question:\n> ").strip()

        if user_input.upper() in ['B', 'BACK']:
            rprint("[green]Returning to Main Menu.[/green]")
            # Reset history to keep main menu context clean
            CONVERSATION_HISTORY.clear()
            return # EXIT THE LOOP and return to main()

        user_query = user_input.lower()

        # 1. Call the local LLM to get the structured JSON output, passing history
        llm_response_text = call_local_llm(user_query, CONVERSATION_HISTORY)

        if llm_response_text is None:
            rprint("[bold red]\n[ERROR] AI Assistant: Cannot proceed. Local LLM is not loaded.[/bold red]")
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
        rprint("[blue]" + "-" * 50 + "[/blue]")
        rprint(result) # Rich print handles ANSI from tool output
        rprint("[blue]" + "-" * 50 + "[/blue]")


# --- Main Application Loop ---
def main():
    """The main application entry point."""
    rprint("[green]🚀 Loading Personal Dashboard...[/green]") # COLORIZED STARTUP

    setup_database() # Ensure tables exist before loading data
    app_data, data_file_existed = load_data()

    if not data_file_existed:
        rprint("\n[bold magenta]" + "="*40)
        rprint("    FIRST RUN SETUP: Enter Initial Information")
        rprint("="*40 + "[/bold magenta]")

        setup_leave(app_data)
        setup_salary(app_data)
        save_data(app_data)

        rprint("\n[green]Initial setup complete. Starting application.[/green]")

    while True:
        save_data(app_data)

        # FIX: Consolidate the header and footer into a single, properly formatted rich string.
        rprint(
            "[bold cyan]" + "="*40 + "\n"
            "        PERSONAL DASHBOARD MENU" + "\n"
            "========================================" + "[/bold cyan]" # 40 characters of =
        )

        # Now print the menu items cleanly.
        rprint("1. 📝 Task Manager")
        rprint("2. 💰 Expense Tracker")
        rprint("3. 📄 Document Expiry Tracker")
        rprint("4. ⛱️ Leave Balance Tracker")
        rprint("5. 💵 Salary and Bonus Tracker")
        rprint("6. 🏦 Loan Tracker")
        rprint("7. 🧠 Ask AI Assistant")
        rprint("8. 💾 Data Backup")
        rprint("[bold red]Q. Quit and Save[/bold red]")
        rprint("-" * 40)

        choice = input("Enter your choice: ").upper()

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
            ai_query_interface(app_data)
        elif choice == '8':
            message, color = create_database_backup()
            rprint(f"\n[{color}]{message}[/{color}]")
        elif choice == 'Q':
            rprint("[bold red]\nGoodbye! All data has been saved.[/bold red]")
            break
        else:
            rprint("[bold red]Invalid choice. Please select from the menu.[/bold red]")

if __name__ == "__main__":
    main()
