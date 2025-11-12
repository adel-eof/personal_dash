# core/formatting.py
import datetime

# --- Global Configuration Constants ---
# You can change these values to instantly update the format application-wide!
CURRENCY_SYMBOL = '$'
# Standard date format for internal storage/display
DISPLAY_DATE_FORMAT = "%Y-%m-%d"
# User-friendly date format for reports (e.g., 12/Nov/2025)
REPORT_DATE_FORMAT = "%d/%b/%Y"
# --------------------------------------

def format_currency(amount, symbol=CURRENCY_SYMBOL):
    """Formats a float amount into a currency string (e.g., $1,234.56)."""
    try:
        # Uses comma for thousands separator
        return f"{symbol}{float(amount):,.2f}"
    except (TypeError, ValueError):
        return f"{symbol}0.00"

def format_date(date_str, format_style=REPORT_DATE_FORMAT):
    """
    Converts internal YYYY-MM-DD string to a user-friendly display format.
    Handles 'N/A' and other non-date strings gracefully.
    """
    if not date_str or date_str.upper() in ['N/A', 'ERROR']:
        return str(date_str)

    try:
        # Assumes input date_str is in YYYY-MM-DD format
        date_obj = datetime.datetime.strptime(date_str, "%Y-%m-%d").date()
        return date_obj.strftime(format_style)
    except (ValueError, TypeError):
        return str(date_str)

def format_number(number, decimals=1):
    """Formats a general number (like days or duration) to a specific decimal place."""
    try:
        return f"{float(number):.{decimals}f}"
    except (TypeError, ValueError):
        return "0.0"

def get_report_date_format():
    """Returns the standard report date format string."""
    return REPORT_DATE_FORMAT
