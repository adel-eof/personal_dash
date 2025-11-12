# features/salary_tracker.py
from decimal import Decimal, ROUND_HALF_UP
from core.validation import get_valid_float_input, get_valid_date_input
from core.database import execute_query
import sqlite3
from datetime import date # Explicit import
from termcolor import colored # ADDED: for color output

hide_base_salay = True

def calculate_allowance(base_salary, total_fiscal_days, overseas_days, overtime_days, rate_percent):
    """
    Calculates the Overseas Allowance and Overtime amount based on salary and days worked.
    Returns: (overseas_allowance, overtime_amount)
    """
    try:
        monthly_base = Decimal(str(base_salary))
        fiscal_days = Decimal(str(total_fiscal_days))
        o_days = Decimal(str(overseas_days))
        ot_days = Decimal(str(overtime_days))
        rate = Decimal(str(rate_percent))

        daily_rate = monthly_base / fiscal_days
        overseas_allowance = daily_rate * o_days * (rate / 100)
        overtime_amount = daily_rate * ot_days

        def round_currency(amount):
            return float(amount.quantize(Decimal('.01'), rounding=ROUND_HALF_UP))

        return round_currency(overseas_allowance), round_currency(overtime_amount)
    except Exception as e:
        # Note: Calculation errors here should be non-critical, usually due to bad input data type
        return 0.0, 0.0

def setup_salary(data):
    """Allows the user to set initial salary parameters and fiscal days."""
    print(colored("\n--- 💵 Salary Setup ---", 'magenta'))

    # CHECK 1: Base Salary
    new_base = get_valid_float_input(f"Enter New Monthly Base Salary (current: ${data['salary']['monthly_base']:.2f}): ", allow_negative=False)
    if new_base is None:
        print(colored("Salary setup cancelled.", 'yellow'))
        return
    data['salary']['monthly_base'] = new_base

    # CHECK 2: Fiscal Days
    new_fiscal_days = get_valid_float_input(f"Enter Monthly Fiscal Days (e.g., 22, current: {data['salary']['total_fiscal_days']:.1f}): ", allow_negative=False)
    if new_fiscal_days is None:
        print(colored("Salary setup cancelled.", 'yellow'))
        return
    data['salary']['total_fiscal_days'] = new_fiscal_days

    # CHECK 3: Allowance Rate
    new_rate = get_valid_float_input(f"Enter Overseas Allowance Rate (percentage, e.g., 20 for 20%, current: {data['salary']['overseas_allowance_rate']:.1f}%): ", allow_negative=False)
    if new_rate is None:
        print(colored("Salary setup cancelled.", 'yellow'))
        return
    data['salary']['overseas_allowance_rate'] = new_rate

    print(colored("Salary, Fiscal Days, and Allowance Rate updated.", 'green'))

def salary_bonus_tracker(data, print_log_table):
    """
    Tracks base salary, overseas allowance, and overtime using SQLite.
    LOOP ADDED to keep the user in the tracker until they exit.
    """
    salary_data = data['salary']
    monthly_base = salary_data['monthly_base'] # Retrieve base salary

    while True: # Persistence Loop
        print(colored("\n--- 💵 Salary and Bonus Tracker ---", 'cyan'))

        if hide_base_salay:
            print(f"**Monthly Base Salary:** {colored('****', 'white')}")
        else:
            print(f"**Monthly Base Salary:** {colored(f'${monthly_base:.2f}', 'white')}")

        print(f"**Monthly Fiscal Days:** {salary_data['total_fiscal_days']:.1f}")
        print(f"**Overseas Allowance Rate:** {salary_data['overseas_allowance_rate']:.1f}%")

        # --- SQL CHANGE: Calculate totals from DB ---
        try:
            # Calculate sum of all logged amounts
            total_summary_result = execute_query("""
                SELECT SUM(allowance_amount), SUM(overtime_amount), SUM(total_earned)
                FROM allowance_logs
            """)

            # Safely unpack the results (handle NULLs)
            totals = total_summary_result[1][0] if total_summary_result[1] else (0.0, 0.0, 0.0)
            total_allowance = totals[0] if totals[0] is not None else 0.0
            total_overtime = totals[1] if totals[1] is not None else 0.0
            grand_total_allowance = totals[2] if totals[2] is not None else 0.0

            # --- NEW CALCULATION: Grand Total Including Base Salary ---
            estimated_monthly_grand_total = monthly_base + grand_total_allowance
            # ---------------------------------------------------------

        except sqlite3.Error as e:
            print(colored(f"Error calculating totals from DB: {e}", 'red'))
            total_allowance, total_overtime, grand_total_allowance = 0.0, 0.0, 0.0
            estimated_monthly_grand_total = monthly_base # Fallback
        # --------------------------------------------

        print("-" * 40)
        print(f"**Total Overseas Allowance Logged:** {colored(f'${total_allowance:.2f}', 'green')}")
        print(f"**Total Overtime Logged:** {colored(f'${total_overtime:.2f}', 'green')}")
        print(f"**GRAND TOTAL ALLOWANCE:** {colored(f'${grand_total_allowance:.2f}', 'green', attrs=['bold'])}")

        # --- NEW DISPLAY LINE ---
        if hide_base_salay:
            print(f"**MONTHLY GRAND TOTAL:** {colored('****', 'yellow', attrs=['bold'])}")
        else:
            print(f"**MONTHLY GRAND TOTAL: {colored(f'${estimated_monthly_grand_total:.2f}', 'yellow', attrs=['bold'])}**")
        # ------------------------

        choice = input(colored("\n[A]dd Allowance Log, [S]etup Base/Rate, [D]isplay Logs, [B]ack to Main Menu\nEnter option: ", 'green')).upper()

        if choice == 'A':
            # Note: core.validation is already imported at the module level.

            date_str = get_valid_date_input("Date of Payment/Period (YYYY-MM-DD, leave blank for today): ", allow_empty=True)
            if date_str is None: # Cancellation check
                print(colored("Logging cancelled.", 'yellow'))
                continue

            if not date_str:
                date_str = date.today().strftime("%Y-%m-%d")

            start_date = get_valid_date_input("Start Date of Overseas Work (YYYY-MM-DD, for reference only): ", allow_empty=True)
            if start_date is None: # Cancellation check
                print(colored("Logging cancelled.", 'yellow'))
                continue

            end_date = get_valid_date_input("End Date of Overseas Work (YYYY-MM-DD, for reference only): ", allow_empty=True)
            if end_date is None: # Cancellation check
                print(colored("Logging cancelled.", 'yellow'))
                continue

            # Check for cancellation within the validation function is already done.
            # We must set defaults to None if empty input was received for start/end dates
            start_date = start_date if start_date else None
            end_date = end_date if end_date else None

            # CHECK 4: Overseas Days
            overseas_days = get_valid_float_input("Total Overseas Days worked: ", allow_negative=False)
            if overseas_days is None:
                print(colored("Logging cancelled.", 'yellow'))
                continue

            # CHECK 5: Overtime Days
            overtime_days = get_valid_float_input("Total Overtime Days worked (Sat/Sun): ", allow_negative=False)
            if overtime_days is None:
                print(colored("Logging cancelled.", 'yellow'))
                continue

            allowance_amount, overtime_amount = calculate_allowance(
                salary_data['monthly_base'],
                salary_data['total_fiscal_days'],
                overseas_days,
                overtime_days,
                salary_data['overseas_allowance_rate']
            )

            total_earned = allowance_amount + overtime_amount

            # --- SQL CHANGE: INSERT new log into allowance_logs table ---
            try:
                execute_query("""
                    INSERT INTO allowance_logs (date, start_date, end_date, overseas_days, overtime_days, allowance_amount, overtime_amount, total_earned)
                    VALUES (?, ?, ?, ?, ?, ?, ?, ?)
                """, (
                    date_str,
                    start_date if start_date else 'N/A',
                    end_date if end_date else 'N/A',
                    overseas_days,
                    overtime_days,
                    allowance_amount,
                    overtime_amount,
                    total_earned
                ))
                print(colored(f"Logged {overseas_days} overseas days and {overtime_days} overtime days. Total: ${total_earned:.2f}", 'green'))
            except sqlite3.Error as e:
                print(colored(f"Error logging allowance: {e}", 'red'))
            # -------------------------------------------------------------

            print(f"Calculated Total Allowance: {colored(f'${total_earned:.2f}', 'white', attrs=['bold'])} (Allowance: ${allowance_amount:.2f}, Overtime: ${overtime_amount:.2f})")

        elif choice == 'S':
            setup_salary(data)

        elif choice == 'D':
            print(colored("\n**💰 Allowance Log History:**", 'cyan'))

            # --- SQL CHANGE: SELECT log history from DB ---
            try:
                columns, results = execute_query("""
                    SELECT date, end_date, overseas_days, overtime_days, allowance_amount, overtime_amount, total_earned
                    FROM allowance_logs
                    ORDER BY date DESC
                """)

                logs_from_db = []
                for row in results:
                    logs_from_db.append({
                        'pay_date': row[0],
                        'period_end': row[1],
                        'overseas_days': row[2],
                        'overtime_days': row[3],
                        'allowance_amount': row[4],
                        'overtime_amount': row[5],
                        'total_earned': row[6]
                    })

            except sqlite3.Error as e:
                print(colored(f"Error retrieving log history: {e}", 'red'))
                logs_from_db = []
            # ---------------------------------------------

            if logs_from_db:
                headers = ["PAY DATE", "PERIOD END", "O.DAYS", "OT DAYS", "ALLOWANCE", "OVERTIME", "TOTAL"]
                column_keys = ["pay_date", "period_end", "overseas_days", "overtime_days", "allowance_amount", "overtime_amount", "total_earned"]
                currency_cols = [4, 5, 6]

                print_log_table(headers, logs_from_db, column_keys, currency_cols)
            else:
                print("No allowance history found.")

        elif choice == 'B':
            return # Exit the loop and return to the main menu

        else:
            print(colored("Invalid option. Please choose A, S, D, or B.", 'red'))
