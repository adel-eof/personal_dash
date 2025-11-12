# core/styles.py (NEW FILE)

# --- Define the application's color palette using Rich Markup tags ---
STYLE_PALETTE = {
    "HEADER": "bold cyan",
    "SUCCESS": "bold green",
    "ERROR": "bold white on red",
    "WARNING": "bold yellow",
    "INFO": "white",

    # Feature specific styles
    "STATUS_ONGOING": "yellow",
    "STATUS_FINISHED": "green",
    "STATUS_MISSED": "bold red",
    "STATUS_DUE": "yellow",
    "MONEY": "green",
    "PROMPT": "green",
    "TIP": "yellow"
}

# --- Define a centralized print function for consistency ---
from rich import print as rprint_rich
from rich.console import Console
CONSOLE = Console()

def print_styled(key, text):
    """Prints text using a style defined in the STYLE_PALETTE."""
    style = STYLE_PALETTE.get(key, "white")
    rprint_rich(f"[{style}]{text}[/{style}]")

def get_style(key):
    """Returns the raw style string for embedding in larger text blocks or tables."""
    return STYLE_PALETTE.get(key, "white")
