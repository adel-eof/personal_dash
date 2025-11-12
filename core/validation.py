# core/validation.py
import datetime
from datetime import timedelta # Import for relative calculations
from termcolor import colored

def get_valid_float_input(prompt, allow_negative=False):
    """
    Prompts the user until a valid float is entered.
    Allows 'B' or 'Back' to exit the input process.
    """

    exit_prompt = " (Type 'B' to cancel): "
    if " " in prompt:
        prompt = prompt.strip() + exit_prompt
    else:
        prompt = prompt + exit_prompt

    while True:
        user_input = input(prompt).strip()

        if user_input.upper() in ['B', 'BACK']:
            return None

        try:
            value = float(user_input)

            if not allow_negative and value < 0:
                print(colored("❌ Error: Value cannot be negative. Please enter a positive number.", 'red'))
                continue

            return value

        except ValueError:
            print(colored("❌ Error: Invalid number format. Please enter a numerical value (e.g., 10.50).", 'red'))


def get_valid_date_input(prompt, allow_empty=False):
    """
    Prompts the user until a date in YYYY-MM-DD format is entered.
    Accepts 'today', 'yesterday', and various short formats (MM-DD, M/D).
    """

    date_format_tip = " (Format YYYY-MM-DD, today, yesterday, or MM-DD"
    if allow_empty:
        date_format_tip += ", or press Enter to skip"
    date_format_tip += "): "

    prompt = prompt.strip() + date_format_tip

    while True:
        date_str = input(prompt).strip().lower()
        today = datetime.date.today()

        if date_str.upper() in ['B', 'BACK']:
            return None

        # 1. Handle allowed empty input
        if not date_str:
            if allow_empty:
                return None
            else:
                print(colored("❌ Error: Date cannot be empty. Please enter a date or type 'B' to cancel.", 'red'))
                continue

        # 2. Handle relative dates
        if date_str == 'today':
            return today.strftime("%Y-%m-%d")

        if date_str == 'yesterday':
            yesterday = today - timedelta(days=1)
            return yesterday.strftime("%Y-%m-%d")

        # 3. Handle flexible short formats (MM-DD, M/D)
        # Attempt to parse as MM-DD or M-D, assuming current year
        try:
            # Normalize common separators to '-'
            date_str_normalized = date_str.replace('/', '-')

            # Check for formats like 11-10 or 1-1
            parts = date_str_normalized.split('-')
            if 2 <= len(parts) <= 3:
                month = int(parts[0])
                day = int(parts[1])

                # Check for 3 parts (M-D-Y or Y-M-D)
                if len(parts) == 3:
                    # If the first part is clearly a four-digit year, try YYYY-MM-DD
                    if len(parts[0]) == 4:
                        datetime.datetime.strptime(date_str, "%Y-%m-%d")
                        return date_str_normalized # Return if standard format works

                    # If the last part is the year, format it
                    year = int(parts[2])
                    if year < 100: year += 2000 # Assume 20xx for two-digit year
                else:
                    # Assume current year for M-D format
                    year = today.year

                # Check if this date is valid
                try:
                    target_date = datetime.date(year, month, day)
                    return target_date.strftime("%Y-%m-%d")
                except ValueError:
                    # Invalid month/day combination (e.g., Feb 30th)
                    pass

        except ValueError:
            # Input wasn't a number/date, fall through to strict check
            pass

        # 4. Handle strict YYYY-MM-DD format (The original check)
        try:
            datetime.datetime.strptime(date_str, "%Y-%m-%d")
            return date_str

        except ValueError:
            print(colored("❌ Error: Invalid date format. Use YYYY-MM-DD, 'today', 'yesterday', or M-D (e.g., 2025-01-15 or 1-15).", 'red'))
