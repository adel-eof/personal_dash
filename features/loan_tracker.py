# features/loan_tracker.py
import datetime
import sqlite3
from core.database import execute_query
from core.validation import get_valid_float_input, get_valid_date_input
from termcolor import colored

# --- Global map to store displayed index to DB ID mapping ---
DISPLAY_ID_MAP = {}

# --- Helper Function to Calculate Status/Balance ---

def get_loan_summary(loan_id, total_amount, due_day, master_status):
    """
    Calculates the total paid, remaining balance, and status/payment status for a single loan.
    """
    try:
        # 1. Calculate Total Paid and Remaining Balance
        query = "SELECT SUM(amount_paid) FROM loan_payments WHERE loan_id = ?"
        _, paid_result = execute_query(query, (loan_id,))

        total_paid = paid_result[0][0] if paid_result and paid_result[0][0] is not None else 0.0
        remaining_balance = total_amount - total_paid

        # --- Loan Completion Status Logic ---
        # If master_status is already "Finished" (manually or automatically marked), stick to that.
        if master_status == 'Finished':
            return total_paid, 0.0, colored('Finished', 'green'), 'Finished', colored('N/A', 'light_grey')

        # If mathematically paid off, set the status to Finished
        if remaining_balance <= 0.0:
            return total_paid, 0.0, colored('Finished (Auto)', 'green'), 'Finished', colored('N/A', 'light_grey')

        # --- Monthly Payment Status (Only runs if loan is Ongoing) ---
        today = datetime.date.today()
        current_month_key = today.strftime("%Y-%m")

        # Check if *any* payment was logged this month
        payment_check_query = f"""
            SELECT COUNT(id) FROM loan_payments
            WHERE loan_id = ? AND payment_date LIKE '{current_month_key}-%'
        """
        _, count_result = execute_query(payment_check_query, (loan_id,))
        payments_this_month = count_result[0][0]

        # Determine monthly status based on payments and due date
        monthly_status_display = colored('N/A', 'light_grey')
        if due_day is not None and due_day > 0:
            if payments_this_month > 0:
                monthly_status_display = colored('PAID', 'green')
            elif today.day > due_day:
                monthly_status_display = colored('MISSED', 'red', attrs=['bold'])
            else:
                 monthly_status_display = colored('DUE', 'yellow')

        # Return: total_paid, remaining, display_status, calculated_status (for DB), monthly_status_display
        return total_paid, remaining_balance, colored('Ongoing', 'yellow'), 'Ongoing', monthly_status_display

    except sqlite3.Error as e:
        return 0.0, total_amount, colored("DB Error", 'red'), 'DB Error', colored('N/A', 'red')

# --- Core Functions ---

def loan_tracker(data, print_log_table):
    """
    Manages tracking loan details, calculating remaining balance, and logging payments.
    """
    global DISPLAY_ID_MAP
    DISPLAY_ID_MAP.clear() # Clear map at start of each loop

    while True: # Persistence Loop
        print(colored("\n--- 🏦 Loan Tracker ---", 'cyan'))

        # 1. Retrieve all master loans
        try:
            master_query = "SELECT id, description, total_amount, monthly_payment, start_date, duration_months, due_day, status FROM loans_master ORDER BY status, start_date ASC"
            _, loans_master_rows = execute_query(master_query)
        except sqlite3.Error:
            loans_master_rows = []

        processed_loans = []
        display_index = 1

        for row in loans_master_rows:
            loan_id, desc, total, monthly, start, duration, due_day, master_status = row

            # Calculate summary using the new due_day and master_status
            total_paid, remaining, display_status, calculated_status, monthly_status = get_loan_summary(loan_id, total, due_day, master_status)

            # --- AUTOMATIC STATUS UPDATE (CRITICAL) ---
            # Update the status only if it's NOT manually finished, but mathematically finished
            if master_status != 'Finished' and calculated_status == 'Finished':
                execute_query("UPDATE loans_master SET status = ? WHERE id = ?", (calculated_status, loan_id))
            # ------------------------------------------

            processed_loans.append({
                'ID': loan_id,
                'DISPLAY_INDEX': display_index,
                'NAME': desc,
                'TOTAL': total,
                'MONTHLY': monthly,
                'DUE_DAY': due_day if due_day else 'N/A',
                'REMAINING': remaining,
                'PAY_STATUS': monthly_status,
                'STATUS': display_status
            })

            DISPLAY_ID_MAP[str(display_index)] = loan_id
            display_index += 1


        if not processed_loans:
            print(colored("No loans currently logged.", 'yellow'))
        else:
            print(colored("\n**Current Loan Summary (Select by Index):**", 'white', attrs=['bold']))

            summary_headers = ["IDX", "NAME", "TOTAL LOAN", "MONTHLY PMT", "DUE DAY", "REMAINING BALANCE", "PAYMENT STATUS", "STATUS"]
            summary_keys = ["DISPLAY_INDEX", "NAME", "TOTAL", "MONTHLY", "DUE_DAY", "REMAINING", "PAY_STATUS", "STATUS"]
            currency_cols = [2, 3, 5]

            print_log_table(summary_headers, processed_loans, summary_keys, currency_cols)


        print("\n[A]dd New Loan, [P]ay Loan, [V]iew Payment History, [M]ark Finished, [B]ack to Main Menu") # ADDED [M]
        choice = input(colored("Enter option: ", 'green')).upper()

        if choice == 'A':
            add_loan()
        elif choice == 'P':
            log_loan_payment()
        elif choice == 'V':
            view_loan_details(print_log_table)
        elif choice == 'M': # NEW OPTION
            mark_loan_finished()
        elif choice == 'B':
            return # Exit persistence loop
        else:
            print(colored("Invalid option. Please choose A, P, V, M, or B.", 'red'))


# --- Input Resolver Utility ---
def resolve_display_id(input_str, action_desc="Loan"):
    """Converts a user-provided display index (e.g., '1') into the actual DB ID."""
    global DISPLAY_ID_MAP

    if input_str.upper() in ['B', 'BACK']:
        print(colored(f"{action_desc} cancelled.", 'yellow'))
        return None

    if input_str in DISPLAY_ID_MAP:
        return DISPLAY_ID_MAP[input_str]
    else:
        print(colored(f"Error: Invalid index '{input_str}'. Please enter a listed index number.", 'red'))
        return False # Use False to signal invalid input but not cancellation

# --- NEW FUNCTION: Mark Loan Finished Manually ---
def mark_loan_finished():
    """Allows user to manually mark a loan as finished (e.g., due to discount or odd final payment)."""
    print(colored("\n--- Mark Loan as Finished ---", 'red'))

    if not DISPLAY_ID_MAP:
        print(colored("No active loans found to mark finished.", 'yellow'))
        return

    index_input = input("Enter **INDEX** of the loan to mark FINISHED (Type 'B' to cancel): ").strip()

    loan_id = resolve_display_id(index_input, "Mark Finished")

    if loan_id is None or loan_id is False:
        return

    # Check current status and prevent double-marking
    _, current_status_result = execute_query("SELECT description, status FROM loans_master WHERE id = ?", (loan_id,))
    if not current_status_result:
        print(colored(f"Error: Loan ID {loan_id} not found.", 'red'))
        return

    desc, status = current_status_result[0]

    if status == 'Finished':
        print(colored(f"Loan '{desc}' is already marked as Finished.", 'yellow'))
        return

    # Get summary to show remaining balance before marking finished
    _, loan_result = execute_query("SELECT total_amount, due_day FROM loans_master WHERE id = ?", (loan_id,))
    total_amount, due_day = loan_result[0]
    _, remaining, _, _, _ = get_loan_summary(loan_id, total_amount, due_day, status)

    confirmation = input(colored(f"CONFIRM: Mark '{desc}' (Remaining: ${remaining:.2f}) as FINISHED? (Y/N): ", 'red')).upper()

    if confirmation == 'Y':
        try:
            execute_query("UPDATE loans_master SET status = 'Finished' WHERE id = ?", (loan_id,))
            print(colored(f"SUCCESS: Loan '{desc}' has been marked as FINISHED.", 'green', attrs=['bold']))
        except sqlite3.Error as e:
            print(colored(f"Error updating loan status: {e}", 'red'))
    else:
        print(colored("Action cancelled.", 'yellow'))


# --- ADD LOAN (No changes needed here) ---
def add_loan():
    # ... (function body remains the same) ...
    print(colored("\n--- Add New Loan ---", 'yellow'))

    description = input("Loan Description (e.g., Laptop, Car, Type 'B' to cancel): ").strip()
    if description.upper() in ['B', 'BACK'] or not description:
        print(colored("Loan addition cancelled.", 'yellow'))
        return

    total_amount = get_valid_float_input("Total Amount of Loan: $", allow_negative=False)
    if total_amount is None:
        print(colored("Loan addition cancelled.", 'yellow'))
        return

    monthly_payment = get_valid_float_input("Required Monthly Payment: $", allow_negative=False)
    if monthly_payment is None:
        print(colored("Loan addition cancelled.", 'yellow'))
        return

    start_date = get_valid_date_input("Start Date (YYYY-MM-DD): ", allow_empty=False)
    if start_date is None:
        print(colored("Loan addition cancelled.", 'yellow'))
        return

    duration_months = get_valid_float_input("Duration in Months: ", allow_negative=False)
    if duration_months is None:
        print(colored("Loan addition cancelled.", 'yellow'))
        return

    due_day = get_valid_float_input("Payment Due Day of the Month (e.g., 15 for the 15th): ", allow_negative=False)
    if due_day is None or due_day < 1 or due_day > 31:
        print(colored("Invalid or cancelled due day. Must be between 1 and 31. Loan addition cancelled.", 'yellow'))
        return
    due_day = int(due_day)

    try:
        execute_query("""
            INSERT INTO loans_master (description, total_amount, monthly_payment, start_date, duration_months, due_day)
            VALUES (?, ?, ?, ?, ?, ?)
        """, (description, total_amount, monthly_payment, start_date, int(duration_months), due_day))
        print(colored(f"Loan '{description}' for ${total_amount:.2f} added successfully.", 'green'))

    except sqlite3.Error as e:
        print(colored(f"Error adding loan to database: {e}", 'red'))


# --- LOG PAYMENT (No changes needed here) ---
def log_loan_payment():
    # ... (function body remains the same) ...
    print(colored("\n--- Log Loan Payment ---", 'yellow'))

    if not DISPLAY_ID_MAP:
        print(colored("No active loans found to pay.", 'yellow'))
        return

    index_input = input("Enter **INDEX** of loan to pay (Type 'B' to cancel): ").strip()

    loan_id = resolve_display_id(index_input, "Payment")

    if loan_id is None or loan_id is False:
        return

    _, loan_check = execute_query("SELECT description, status FROM loans_master WHERE id = ?", (loan_id,))
    desc, status = loan_check[0]
    if status == 'Finished':
        print(colored(f"Loan '{desc}' (ID {loan_id}) is already marked as Finished.", 'red'))
        return

    payment_date = get_valid_date_input("Payment Date (YYYY-MM-DD, leave blank for today): ", allow_empty=True)
    if payment_date is None:
        print(colored("Payment cancelled.", 'yellow'))
        return

    if not payment_date:
        payment_date = datetime.date.today().strftime("%Y-%m-%d")

    amount_paid = get_valid_float_input(f"Amount paid for Loan '{desc}': $", allow_negative=False)
    if amount_paid is None:
        print(colored("Payment cancelled.", 'yellow'))
        return

    try:
        execute_query("""
            INSERT INTO loan_payments (loan_id, payment_date, amount_paid)
            VALUES (?, ?, ?)
        """, (loan_id, payment_date, amount_paid))
        print(colored(f"Payment of ${amount_paid:.2f} logged successfully for Loan '{desc}'.", 'green'))
    except sqlite3.Error as e:
        print(colored(f"Error logging payment: {e}", 'red'))


# --- VIEW DETAILS (No changes needed here) ---
def view_loan_details(print_log_table):
    """Displays detailed payment history for a selected loan."""
    print(colored("\n--- Loan History Details ---", 'yellow'))

    if not DISPLAY_ID_MAP:
        print(colored("No active loans found to view history.", 'yellow'))
        return

    index_input = input("Enter **INDEX** of loan to view history (Type 'B' to cancel): ").strip()

    loan_id = resolve_display_id(index_input, "View History")

    if loan_id is None or loan_id is False:
        return

    master_query = "SELECT description, total_amount, due_day, status FROM loans_master WHERE id = ?"
    _, master_result = execute_query(master_query, (loan_id,))

    if not master_result:
        print(colored(f"Error: Loan ID {loan_id} not found.", 'red'))
        return

    desc, total_amount, due_day, master_status = master_result[0] # Retrieve master_status
    total_paid, remaining, display_status, _, monthly_status = get_loan_summary(loan_id, total_amount, due_day, master_status)

    print(f"\nLoan: {colored(desc, 'white', attrs=['bold'])} | Total Loan: ${total_amount:.2f}")
    print(f"Total Paid: ${total_paid:.2f} | Remaining Balance: {colored(f'${remaining:.2f}', 'yellow')}")
    print(f"Status: {display_status} | Due Day: {due_day if due_day else 'N/A'} | Monthly Status: {monthly_status}")
    print("-" * 50)

    history_query = "SELECT payment_date, amount_paid FROM loan_payments WHERE loan_id = ? ORDER BY payment_date DESC"
    _, history_results = execute_query(history_query, (loan_id,))

    if not history_results:
        print("No payments logged for this loan.")
        return

    payment_logs = []
    for date_str, amount in history_results:
        payment_logs.append({
            'PAYMENT_DATE': date_str,
            'AMOUNT_PAID': amount
        })

    history_headers = ["PAYMENT DATE", "AMOUNT PAID"]
    history_keys = ["PAYMENT_DATE", "AMOUNT_PAID"]
    currency_cols = [1]

    print_log_table(history_headers, payment_logs, history_keys, currency_cols)
