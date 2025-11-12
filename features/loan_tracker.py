# features/loan_tracker.py
import datetime
import sqlite3
from core.database import execute_query
from core.validation import get_valid_float_input, get_valid_date_input
from core.styles import get_style
from core.formatting import format_currency, format_number, format_date
from rich import print as rprint # Use Rich print for all styled output

# --- Global map to store displayed index to DB ID mapping ---
DISPLAY_ID_MAP = {}

# --- Helper Function to Calculate Status/Balance ---

def get_loan_summary(loan_id, total_amount, due_day, master_status):
    """
    Calculates the total paid, remaining balance, and status/payment status for a single loan.
    (Uses Centralized Styling and Formatting)
    """
    try:
        # 1. Calculate Total Paid and Remaining Balance
        query = "SELECT SUM(amount_paid) FROM loan_payments WHERE loan_id = ?"
        _, paid_result = execute_query(query, (loan_id,))

        total_paid = paid_result[0][0] if paid_result and paid_result[0][0] is not None else 0.0
        remaining_balance = total_amount - total_paid

        # Helper to get the neutral N/A style
        na_style = get_style('INFO')

        # --- Loan Completion Status Logic ---

        # If manually Finished
        if master_status == 'Finished':
            return total_paid, 0.0, f"[{get_style('STATUS_FINISHED')}]Finished[/]", 'Finished', f"[{na_style}]N/A[/]"

        # If mathematically paid off (Auto Finished)
        if remaining_balance <= 0.0:
            return total_paid, 0.0, f"[{get_style('STATUS_FINISHED')}]Finished (Auto)[/]", 'Finished', f"[{na_style}]N/A[/]"

        # --- Monthly Payment Status ---
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
        monthly_status_display = f"[{na_style}]N/A[/]"
        if due_day is not None and due_day > 0:
            if payments_this_month > 0:
                monthly_status_display = f"[{get_style('STATUS_PAID')}]PAID[/]"
            elif today.day > due_day:
                monthly_status_display = f"[{get_style('STATUS_MISSED')}]MISSED[/]"
            else:
                 monthly_status_display = f"[{get_style('STATUS_DUE')}]DUE[/]"

        # Return: total_paid, remaining, display_status, calculated_status (for DB), monthly_status_display
        return total_paid, remaining_balance, f"[{get_style('STATUS_ONGOING')}]Ongoing[/]", 'Ongoing', monthly_status_display

    except sqlite3.Error as e:
        return 0.0, total_amount, f"[{get_style('ERROR')}]DB Error[/]", 'DB Error', f"[{get_style('ERROR')}]N/A[/]"

# --- NEW FUNCTION: Display Recent Payments ---
def display_recent_payments(print_log_table, loan_id, limit=3):
    """Retrieves and displays the last N payments made for a specific loan."""

    rprint(f"\n[{get_style('INFO')}]--- Last {limit} Payments for Loan ID {loan_id} ---[/]")

    try:
        query = """
            SELECT payment_date, amount_paid
            FROM loan_payments
            WHERE loan_id = ?
            ORDER BY payment_date DESC, id DESC
            LIMIT ?
        """
        columns, results = execute_query(query, (loan_id, limit))

        if not results:
            rprint(f"[{get_style('WARNING')}]No payment history found.[/]")
            return

        payment_logs = []
        for date_str, amount in results:
            payment_logs.append({
                'PAYMENT_DATE': date_str,
                'AMOUNT_PAID': amount
            })

        history_headers = ["PAYMENT DATE", "AMOUNT PAID"]
        history_keys = ["PAYMENT_DATE", "AMOUNT_PAID"]
        currency_cols = [1]

        # Use the global print_log_table function
        print_log_table(history_headers, payment_logs, history_keys, currency_cols)

    except sqlite3.Error as e:
        rprint(f"[{get_style('ERROR')}]Error retrieving recent payments: {e}[/]")

# --- Input Resolver Utility ---
def resolve_display_id(input_str, action_desc="Loan"):
    """
    Converts a user-provided display index (e.g., '1') into the actual DB ID
    using the global DISPLAY_ID_MAP.

    Returns: The database ID (int), None (on cancel), or False (on invalid input).
    """
    global DISPLAY_ID_MAP

    if input_str.upper() in ['B', 'BACK']:
        rprint(f"[{get_style('WARNING')}]{action_desc} cancelled.[/]")
        return None

    if input_str in DISPLAY_ID_MAP:
        return DISPLAY_ID_MAP[input_str]
    else:
        rprint(f"[{get_style('ERROR')}]Error: Invalid index '{input_str}'. Please enter a listed index number.[/]")
        return False


# --- Core Functions ---

def loan_tracker(data, print_log_table):
    """
    Manages tracking loan details, calculating remaining balance, and logging payments.
    """
    global DISPLAY_ID_MAP
    DISPLAY_ID_MAP.clear() # Clear map at start of each loop

    while True: # Persistence Loop
        rprint(f"[{get_style('HEADER')}]\n--- 🏦 Loan Tracker ---[/]")

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

            # Calculate summary
            total_paid, remaining, display_status, calculated_status, monthly_status = get_loan_summary(loan_id, total, due_day, master_status)

            # --- AUTOMATIC STATUS UPDATE (CRITICAL) ---
            if master_status != 'Finished' and calculated_status == 'Finished':
                execute_query("UPDATE loans_master SET status = ? WHERE id = ?", (calculated_status, loan_id))

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
            rprint(f"[{get_style('WARNING')}]No loans currently logged.[/]")
        else:
            rprint(f"[{get_style('INFO')}]\n**Current Loan Summary (Select by Index):**[/]")

            summary_headers = ["IDX", "NAME", "TOTAL LOAN", "MONTHLY PMT", "DUE DAY", "REMAINING BALANCE", "PAYMENT STATUS", "STATUS"]
            summary_keys = ["DISPLAY_INDEX", "NAME", "TOTAL", "MONTHLY", "DUE_DAY", "REMAINING", "PAY_STATUS", "STATUS"]
            currency_cols = [2, 3, 5]

            print_log_table(summary_headers, processed_loans, summary_keys, currency_cols)


        # Separated menu display and input for clean Rich output
        rprint("\n[A]dd New Loan, [P]ay Loan, [V]iew Payment History, [M]ark Finished, [B]ack to Main Menu")
        choice = input(f"[{get_style('PROMPT')}]Enter option: [/]").upper()

        if choice == 'A':
            add_loan()
        elif choice == 'P':
            log_loan_payment(print_log_table)
        elif choice == 'V':
            view_loan_details(print_log_table)
        elif choice == 'M':
            mark_loan_finished()
        elif choice == 'B':
            return # Exit persistence loop
        else:
            rprint(f"[{get_style('ERROR')}]Invalid option. Please choose A, P, V, M, or B.[/]")


def add_loan():
    """Prompts user for new loan details and inserts into loans_master."""
    rprint(f"[{get_style('WARNING')}]\n--- Add New Loan ---[/]")

    # Input validation and cancellation checks
    description = input("Loan Description (e.g., Laptop, Car, Type 'B' to cancel): ").strip()
    if description.upper() in ['B', 'BACK'] or not description:
        rprint(f"[{get_style('WARNING')}]Loan addition cancelled.[/]")
        return

    total_amount = get_valid_float_input("Total Amount of Loan: $", allow_negative=False)
    if total_amount is None:
        rprint(f"[{get_style('WARNING')}]Loan addition cancelled.[/]")
        return

    monthly_payment = get_valid_float_input("Required Monthly Payment: $", allow_negative=False)
    if monthly_payment is None:
        rprint(f"[{get_style('WARNING')}]Loan addition cancelled.[/]")
        return

    start_date = get_valid_date_input("Start Date (YYYY-MM-DD): ", allow_empty=False)
    if start_date is None:
        rprint(f"[{get_style('WARNING')}]Loan addition cancelled.[/]")
        return

    duration_months = get_valid_float_input("Duration in Months: ", allow_negative=False)
    if duration_months is None:
        rprint(f"[{get_style('WARNING')}]Loan addition cancelled.[/]")
        return

    due_day = get_valid_float_input("Payment Due Day of the Month (e.g., 15 for the 15th): ", allow_negative=False)
    if due_day is None or due_day < 1 or due_day > 31:
        rprint(f"[{get_style('WARNING')}]Invalid or cancelled due day. Must be between 1 and 31. Loan addition cancelled.[/]")
        return
    due_day = int(due_day)

    try:
        execute_query("""
            INSERT INTO loans_master (description, total_amount, monthly_payment, start_date, duration_months, due_day)
            VALUES (?, ?, ?, ?, ?, ?)
        """, (description, total_amount, monthly_payment, start_date, int(duration_months), due_day))
        rprint(f"[{get_style('SUCCESS')}]Loan '{description}' for {format_currency(total_amount)} added successfully.[/]")

    except sqlite3.Error as e:
        rprint(f"[{get_style('ERROR')}]Error adding loan to database: {e}[/]")


def log_loan_payment(print_log_table):
    """
    Prompts user to log a payment against an existing loan and displays recent logs.
    """
    rprint(f"[{get_style('WARNING')}]\n--- Log Loan Payment ---[/]")

    if not DISPLAY_ID_MAP:
        rprint(f"[{get_style('WARNING')}]No active loans found to pay.[/]")
        return

    index_input = input("Enter **INDEX** of loan to pay (Type 'B' to cancel): ").strip()

    loan_id = resolve_display_id(index_input, "Payment")

    if loan_id is None or loan_id is False:
        return

    _, loan_check = execute_query("SELECT description, status FROM loans_master WHERE id = ?", (loan_id,))
    desc, status = loan_check[0]
    if status == 'Finished':
        rprint(f"[{get_style('ERROR')}]Loan '{desc}' (ID {loan_id}) is already marked as Finished.[/]")
        return

    payment_date = get_valid_date_input("Payment Date (YYYY-MM-DD, leave blank for today): ", allow_empty=True)
    if payment_date is None:
        rprint(f"[{get_style('WARNING')}]Payment cancelled.[/]")
        return

    if not payment_date:
        payment_date = datetime.date.today().strftime("%Y-%m-%d")

    # Get current monthly payment suggestion for prompt clarity
    _, monthly_payment_result = execute_query("SELECT monthly_payment FROM loans_master WHERE id = ?", (loan_id,))
    monthly_payment = monthly_payment_result[0][0] if monthly_payment_result else 0.0

    # Use format_currency in the prompt
    amount_paid = get_valid_float_input(f"Amount paid for Loan '{desc}' (Suggested: {format_currency(monthly_payment)}): $", allow_negative=False)
    if amount_paid is None:
        rprint(f"[{get_style('WARNING')}]Payment cancelled.[/]")
        return

    try:
        execute_query("""
            INSERT INTO loan_payments (loan_id, payment_date, amount_paid)
            VALUES (?, ?, ?)
        """, (loan_id, payment_date, amount_paid))

        # Use format_currency in success message
        rprint(f"[{get_style('SUCCESS')}]Payment of {format_currency(amount_paid)} logged successfully for Loan '{desc}'.[/]")

        # --- NEW LOGIC: Display recent payments immediately ---
        display_recent_payments(print_log_table, loan_id, limit=3)
        # ---------------------------------------------------

    except sqlite3.Error as e:
        rprint(f"[{get_style('ERROR')}]Error logging payment: {e}[/]")


def mark_loan_finished():
    """Allows user to manually mark a loan as finished (e.g., due to discount or odd final payment)."""
    rprint(f"[{get_style('ERROR')}]\n--- Mark Loan as Finished ---[/]")

    if not DISPLAY_ID_MAP:
        rprint(f"[{get_style('WARNING')}]No active loans found to mark finished.[/]")
        return

    index_input = input("Enter **INDEX** of the loan to mark FINISHED (Type 'B' to cancel): ").strip()

    loan_id = resolve_display_id(index_input, "Mark Finished")

    if loan_id is None or loan_id is False:
        return

    # Check current status and prevent double-marking
    _, current_status_result = execute_query("SELECT description, status FROM loans_master WHERE id = ?", (loan_id,))
    if not current_status_result:
        rprint(f"[{get_style('ERROR')}]Error: Loan ID {loan_id} not found.[/]")
        return

    desc, status = current_status_result[0]

    if status == 'Finished':
        rprint(f"[{get_style('WARNING')}]Loan '{desc}' is already marked as Finished.[/]")
        return

    # Get summary to show remaining balance before marking finished
    _, loan_result = execute_query("SELECT total_amount, due_day FROM loans_master WHERE id = ?", (loan_id,))
    total_amount, due_day = loan_result[0]
    _, remaining, _, _, _ = get_loan_summary(loan_id, total_amount, due_day, status)

    confirmation = input(f"[{get_style('ERROR')}]CONFIRM: Mark '{desc}' (Remaining: {format_currency(remaining)}) as FINISHED? (Y/N): [/]").upper()

    if confirmation == 'Y':
        try:
            execute_query("UPDATE loans_master SET status = 'Finished' WHERE id = ?", (loan_id,))
            rprint(f"[{get_style('SUCCESS')} bold]SUCCESS: Loan '{desc}' has been marked as FINISHED.[/]")
        except sqlite3.Error as e:
            rprint(f"[{get_style('ERROR')}]Error updating loan status: {e}[/]")
    else:
        rprint(f"[{get_style('WARNING')}]Action cancelled.[/]")


def view_loan_details(print_log_table):
    """Displays detailed payment history for a selected loan."""
    rprint(f"[{get_style('WARNING')}]\n--- Loan History Details ---[/]")

    if not DISPLAY_ID_MAP:
        rprint(f"[{get_style('WARNING')}]No active loans found to view history.[/]")
        return

    index_input = input("Enter **INDEX** of loan to view history (Type 'B' to cancel): ").strip()

    loan_id = resolve_display_id(index_input, "View History")

    if loan_id is None or loan_id is False:
        return

    master_query = "SELECT description, total_amount, due_day, status FROM loans_master WHERE id = ?"
    _, master_result = execute_query(master_query, (loan_id,))

    if not master_result:
        rprint(f"[{get_style('ERROR')}]Error: Loan ID {loan_id} not found.[/]")
        return

    desc, total_amount, due_day, master_status = master_result[0]
    total_paid, remaining, display_status, _, monthly_status = get_loan_summary(loan_id, total_amount, due_day, master_status)

    rprint(f"\nLoan: [white bold]{desc}[/] | Total Loan: {format_currency(total_amount)}")
    rprint(f"Total Paid: {format_currency(total_paid)} | Remaining Balance: [{get_style('WARNING')}]{format_currency(remaining)}[/]")
    rprint(f"Status: {display_status} | Due Day: {due_day if due_day else 'N/A'} | Monthly Status: {monthly_status}")
    rprint("-" * 50)

    # 2. Retrieve payment history
    history_query = "SELECT payment_date, amount_paid FROM loan_payments WHERE loan_id = ? ORDER BY payment_date DESC"
    _, history_results = execute_query(history_query, (loan_id,))

    if not history_results:
        rprint(f"[{get_style('INFO')}]No payments logged for this loan.[/]")
        return

    payment_logs = []
    for date_str, amount in history_results:
        payment_logs.append({
            'PAYMENT_DATE': date_str,
            'AMOUNT_PAID': amount
        })

    # 3. Display history table
    history_headers = ["PAYMENT DATE", "AMOUNT PAID"]
    history_keys = ["PAYMENT_DATE", "AMOUNT_PAID"]
    currency_cols = [1]

    print_log_table(history_headers, payment_logs, history_keys, currency_cols)
