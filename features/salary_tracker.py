# features/salary_tracker.py
from decimal import Decimal, ROUND_HALF_UP
from core.validation import get_valid_float_input, get_valid_date_input
from core.database import execute_query
import sqlite3
from datetime import date
from core.styles import get_style
from core.formatting import format_currency, format_number, format_date # NEW IMPORTS
from rich import print as rprint

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
        return 0.0, 0.0

def setup_salary(data):
    """Allows the user to set initial salary parameters and fiscal days."""
    rprint(f"[{get_style('INFO')}]\n--- 💵 Salary Setup ---[/]")

    # Use format_currency for display in prompt
    new_base = get_valid_float_input(f"Enter New Monthly Base Salary (current: {format_currency(data['salary']['monthly_base'])}): ", allow_negative=False)
    if new_base is None:
        rprint(f"[{get_style('WARNING')}]Salary setup cancelled.[/]")
        return
    data['salary']['monthly_base'] = new_base

    # Use format_number for display in prompt
    new_fiscal_days = get_valid_float_input(f"Enter Monthly Fiscal Days (e.g., 22, current: {format_number(data['salary']['total_fiscal_days'])}): ", allow_negative=False)
    if new_fiscal_days is None:
        rprint(f"[{get_style('WARNING')}]Salary setup cancelled.[/]")
        return
    data['salary']['total_fiscal_days'] = new_fiscal_days

    # Use format_number for display in prompt
    new_rate = get_valid_float_input(f"Enter Overseas Allowance Rate (percentage, e.g., 20 for 20%, current: {format_number(data['salary']['overseas_allowance_rate'])}%): ", allow_negative=False)
    if new_rate is None:
        rprint(f"[{get_style('WARNING')}]Salary setup cancelled.[/]")
        return
    data['salary']['overseas_allowance_rate'] = new_rate

    rprint(f"[{get_style('SUCCESS')}]Salary, Fiscal Days, and Allowance Rate updated.[/]")

def salary_bonus_tracker(data, print_log_table):
    """
    Tracks base salary, overseas allowance, and overtime using SQLite.
    LOOP ADDED to keep the user in the tracker until they exit.
    """
    salary_data = data['salary']
    monthly_base = salary_data['monthly_base']

    while True:
        rprint(f"[{get_style('HEADER')}]\n--- 💵 Salary and Bonus Tracker ---[/]")

        if hide_base_salay:
            rprint(f"**Monthly Base Salary:** [white]****[/white]")
        else:
            rprint(f"**Monthly Base Salary:** [white]{format_currency(monthly_base)}[/white]") # Use format_currency

        rprint(f"**Monthly Fiscal Days:** {format_number(salary_data['total_fiscal_days'])}") # Use format_number
        rprint(f"**Overseas Allowance Rate:** {format_number(salary_data['overseas_allowance_rate'])}%") # Use format_number

        try:
            total_summary_result = execute_query("""
                SELECT SUM(allowance_amount), SUM(overtime_amount), SUM(total_earned)
                FROM allowance_logs
            """)

            totals = total_summary_result[1][0] if total_summary_result[1] else (0.0, 0.0, 0.0)
            total_allowance = totals[0] if totals[0] is not None else 0.0
            total_overtime = totals[1] if totals[1] is not None else 0.0
            grand_total_allowance = totals[2] if totals[2] is not None else 0.0

            estimated_monthly_grand_total = monthly_base + grand_total_allowance

        except sqlite3.Error as e:
            rprint(f"[{get_style('ERROR')}]Error calculating totals from DB: {e}[/]")
            total_allowance, total_overtime, grand_total_allowance = 0.0, 0.0, 0.0
            estimated_monthly_grand_total = monthly_base

        rprint("-" * 40)
        # Use format_currency for all money displays
        rprint(f"**Total Overseas Allowance Logged:** [{get_style('MONEY')}]{format_currency(total_allowance)}[/]")
        rprint(f"**Total Overtime Logged:** [{get_style('MONEY')}]{format_currency(total_overtime)}[/]")
        rprint(f"**GRAND TOTAL ALLOWANCE:** [{get_style('MONEY')} bold]{format_currency(grand_total_allowance)}[/]")

        # --- NEW DISPLAY LINE ---
        if hide_base_salay:
            rprint(f"**MONTHLY GRAND TOTAL:** [{get_style('WARNING')} bold]****[/]")
        else:
            rprint(f"**MONTHLY GRAND TOTAL:** [{get_style('WARNING')} bold]{format_currency(estimated_monthly_grand_total)}[/]")
        # ------------------------

        choice = input(f"[{get_style('PROMPT')}]\n[A]dd Allowance Log, [S]etup Base/Rate, [D]isplay Logs, [B]ack to Main Menu\nEnter option: [/]").upper()

        if choice == 'A':
            # Note: No changes needed to date inputs, as format_date is used in prompts via get_valid_date_input

            start_date = get_valid_date_input("Start Date of Overseas Work (YYYY-MM-DD, for reference only): ", allow_empty=True)
            if start_date is None:
                rprint(f"[{get_style('WARNING')}]Logging cancelled.[/]")
                return

            end_date = get_valid_date_input("End Date of Overseas Work (YYYY-MM-DD, for reference only): ", allow_empty=True)
            if end_date is None:
                rprint(f"[{get_style('WARNING')}]Logging cancelled.[/]")
                return

            start_date = start_date if start_date else None
            end_date = end_date if end_date else None

            overseas_days = get_valid_float_input("Total Overseas Days worked: ", allow_negative=False)
            if overseas_days is None:
                rprint(f"[{get_style('WARNING')}]Logging cancelled.[/]")
                return

            overtime_days = get_valid_float_input("Total Overtime Days worked (Sat/Sun): ", allow_negative=False)
            if overtime_days is None:
                rprint(f"[{get_style('WARNING')}]Logging cancelled.[/]")
                return

            allowance_amount, overtime_amount = calculate_allowance(
                salary_data['monthly_base'],
                salary_data['total_fiscal_days'],
                overseas_days,
                overtime_days,
                salary_data['overseas_allowance_rate']
            )

            total_earned = allowance_amount + overtime_amount

            try:
                # ... (SQL query remains the same) ...
                # Use format_number and format_currency in success message
                rprint(f"[{get_style('SUCCESS')}]Logged {format_number(overseas_days)} overseas days and {format_number(overtime_days)} overtime days. Total: {format_currency(total_earned)}[/]")
            except sqlite3.Error as e:
                rprint(f"[{get_style('ERROR')}]Error logging allowance: {e}[/]")

            # Use format_currency for final result display
            rprint(f"Calculated Total Allowance: [white bold]{format_currency(total_earned)}[/] (Allowance: {format_currency(allowance_amount)}, Overtime: {format_currency(overtime_amount)})")

        elif choice == 'S':
            setup_salary(data)

        elif choice == 'D':
            rprint(f"[{get_style('INFO')}]\n**💰 Allowance Log History:**[/]")

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
                rprint(f"[{get_style('ERROR')}]Error retrieving log history: {e}[/]")
                logs_from_db = []

            if logs_from_db:
                headers = ["PAY DATE", "PERIOD END", "O.DAYS", "OT DAYS", "ALLOWANCE", "OVERTIME", "TOTAL"]
                column_keys = ["pay_date", "period_end", "overseas_days", "overtime_days", "allowance_amount", "overtime_amount", "total_earned"]
                currency_cols = [4, 5, 6]

                print_log_table(headers, logs_from_db, column_keys, currency_cols)
            else:
                rprint(f"[{get_style('WARNING')}]No allowance history found.[/]")

        elif choice == 'B':
            return

        else:
            rprint(f"[{get_style('ERROR')}]Invalid option. Please choose A, S, D, or B.[/]")
