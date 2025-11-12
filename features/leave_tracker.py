# features/leave_tracker.py
import datetime
import math
import sqlite3
from dateutil.relativedelta import relativedelta
from core.validation import get_valid_float_input, get_valid_date_input
from core.database import execute_query # Import the core DB execution function
from termcolor import colored # Import termcolor for colored messages

def calculate_leave_balance(leave_data):
    """Calculates the current accrued leave balance and total taken days from the DB."""
    today = datetime.date.today()

    try:
        start_date = leave_data['start_date']
        if isinstance(start_date, str):
            start_date = datetime.datetime.strptime(start_date, "%Y-%m-%d").date()
    except Exception:
        return 0.0, 0.0, 0, "Error: Invalid Start Date.", 0.0

    # --- SQL CHANGE: Calculate total taken from the database ---
    try:
        total_taken_result = execute_query("SELECT SUM(days) FROM leave_logs")
        # Extract the sum, default to 0.0 if NULL or empty
        total_taken = total_taken_result[1][0][0] if total_taken_result[1] and total_taken_result[1][0][0] is not None else 0.0
    except sqlite3.Error:
        total_taken = 0.0
    # -----------------------------------------------------------

    delta = relativedelta(today, start_date)
    duration_str = f"{delta.years} years, {delta.months} months, {delta.days} days"

    days_worked = (today - start_date).days
    annual_days = leave_data['annual_leave_days']
    daily_accrual = annual_days / 365.0

    total_accrued = days_worked * daily_accrual
    total_accrued += leave_data['carried_over_days']

    floor_accrued = math.floor(total_accrued)
    available_balance = floor_accrued - total_taken

    return total_accrued, available_balance, floor_accrued, duration_str, total_taken

def setup_leave(data):
    """Allows the user to set initial leave parameters and clear logs via DB."""
    print(colored("\n--- 📝 Leave Setup ---", 'magenta'))

    start_date_str = get_valid_date_input(f"Enter Work Start Date (YYYY-MM-DD, current: {data['leave']['start_date']}): ", allow_empty=False)
    # --- CHECK 1: Handle cancellation from date input ---
    if start_date_str is None:
        print(colored("Setup cancelled.", 'red'))
        return
    # ---------------------------------------------------
    data['leave']['start_date'] = start_date_str
    print(f"Start date set to {start_date_str}.")

    annual = get_valid_float_input(f"Enter Annual Leave Days (current: {data['leave']['annual_leave_days']}): ")
    # --- CHECK 2: Handle cancellation from float input ---
    if annual is None:
        print(colored("Setup cancelled.", 'red'))
        return
    # ---------------------------------------------------
    data['leave']['annual_leave_days'] = annual
    print(f"Annual leave set to {annual} days.")

    carried = get_valid_float_input(f"Enter Initial Carry-Over/Brought-Forward Leave Days (current: {data['leave']['carried_over_days']}): ", allow_negative=True)
    # --- CHECK 3: Handle cancellation from float input ---
    if carried is None:
        print(colored("Setup cancelled.", 'red'))
        return
    # ---------------------------------------------------
    data['leave']['carried_over_days'] = carried
    print(f"Carried-over balance set to {carried} days.")

    taken_reset = input(colored("NOTICE: Past Leave must now be logged with dates. Press ENTER to clear all historical logs, or type 'C' to cancel setup: ", 'yellow')).upper()

    if taken_reset != 'C':
        # --- SQL CHANGE: Clear all logs from the database ---
        try:
            execute_query("DELETE FROM leave_logs")
            print(colored("Historical leave logs cleared from database.", 'green'))
        except sqlite3.Error as e:
            print(colored(f"Error clearing logs: {e}", 'red'))
        # ----------------------------------------------------


def leave_balance_tracker(data, print_log_table):
    """
    Tracks annual leave allowance and balance using an accrual model.
    LOOP ADDED to keep the user in the leave tracker until they exit.
    """
    while True: # Persistence Loop
        print(colored("\n--- ⛱️ Leave Balance Tracker ---", 'cyan'))

        # Recalculate balance on every loop iteration
        total_accrued_precise, balance, floor_accrued, duration_str, total_taken = calculate_leave_balance(data['leave'])

        # Ensure start_date_display is a string for printing consistency
        start_date_display = data['leave']['start_date'].isoformat() if isinstance(data['leave']['start_date'], datetime.date) else data['leave']['start_date']

        print(f"**Work Start Date:** {start_date_display}")
        print(f"**Time Worked:** {duration_str}")
        print(f"**Annual Allowance:** {data['leave']['annual_leave_days']} days")
        print("-" * 30)
        print(f"**Total Accrued (Precise):** {total_accrued_precise:.3f} days")
        print(f"**Accrued (Rounded Down):** {floor_accrued:.0f} days")
        print(f"**Leave Taken:** {total_taken:.1f} days")
        print(f"**Current Available Balance:** {colored(f'{balance:.1f} days', 'green' if balance >= 0 else 'red')}")

        choice = input(colored("\n[T]ake Leave, [L]og History, [S]etup Initial Data, [B]ack to Main Menu\nEnter option: ", 'green')).upper()

        if choice == 'T':
            date_str = get_valid_date_input("Date of leave (YYYY-MM-DD): ", allow_empty=False)
            if date_str is None:
                print(colored("Leave logging cancelled.", 'yellow'))
                continue # Return to start of the loop

            days = get_valid_float_input("How many days of leave did you take/log? (e.g., 1 or 0.5): ", allow_negative=False)
            if days is None:
                print(colored("Leave logging cancelled.", 'yellow'))
                continue # Return to start of the loop

            desc = input("Description (e.g., Vacation, Sick Day): ")

            if balance - days < 0:
                print(colored("Warning: Taking this leave will result in a negative balance.", 'yellow'))

            # --- SQL CHANGE: Log leave to the database ---
            try:
                formatted_date_str = date_str

                execute_query("""
                    INSERT INTO leave_logs (date, days, description)
                    VALUES (?, ?, ?)
                """, (formatted_date_str, days, desc))
                print(colored(f"{days:.1f} day(s) logged successfully to database for {formatted_date_str}.", 'green'))
            except sqlite3.Error as e:
                print(colored(f"Error logging leave: {e}", 'red'))
            # ---------------------------------------------

        elif choice == 'L':
            print(colored("\n**⛱️ Leave Log History:**", 'cyan'))

            # --- SQL CHANGE: Retrieve log history from the database ---
            try:
                columns, results = execute_query("SELECT date, days, description FROM leave_logs ORDER BY date DESC")

                logs_from_db = []
                for date_str, days_val, desc in results:
                    logs_from_db.append({
                        'date': date_str,
                        'days': days_val,
                        'description': desc
                    })
            except sqlite3.Error as e:
                print(colored(f"Error retrieving log history: {e}", 'red'))
                logs_from_db = []
            # ----------------------------------------------------------

            if logs_from_db:
                headers = ["DATE TAKEN", "DAYS", "DESCRIPTION"]
                column_keys = ["date", "days", "description"]

                print_log_table(headers, logs_from_db, column_keys)
            else:
                print("No leave history found.")

        elif choice == 'S':
            setup_leave(data)

        elif choice == 'B':
            # Exit the loop and return to the main menu
            return

        else:
            print(colored("Invalid option. Please choose T, L, S, or B.", 'red'))
