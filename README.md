# 🧠 Personal AI Dashboard (CLI)

A minimalist, highly interactive Command-Line Interface (CLI) application for personal tracking and analysis, featuring a local Large Language Model (LLM) for complex Text-to-SQL data querying and a polished user experience powered by the **Rich** library.

## ✨ Key Features & Improvements

* **Integrated AI Assistant:** Uses a local GGUF LLM for natural language queries against the dashboard's SQLite database (Text-to-SQL).
* **Loan Tracker:** Track loan payments, automatically calculates remaining balance, and monitors current monthly payment status (PAID/DUE/MISSED).
* **Enhanced UX:** Utilizes the **Rich** library for beautiful, stable tables and centralized styling management.
* **Fast Data Entry:** Supports **Relative Date Input** (e.g., "today", "yesterday") and **Category Auto-Suggestion** in the Expense Tracker.
* **Robust Data:** Includes modules for Expenses, Leave Balances, Document Expiry, Task Management, and a **Data Backup** utility.

## 💻 Setup and Installation

### Prerequisites

1.  **Python:** Python 3.9+ is required.
2.  **GGUF Model:** You must download a compatible GGUF model (e.g., Mistral 7B Instruct) and save it to the path specified in `features/ai_tools.py`.

### Installation Steps

1.  **Install Dependencies:** Run the following command to install all necessary Python packages (excluding the legacy `termcolor` library):

    ```bash
    pip install -r requirements.txt
    ```

2.  **Configure LLM Path:** Update your `.env` file and ensure the `MODEL_PATH` variable points to your downloaded GGUF file:

    ```python
    MODEL_PATH = "/path/to/llm-models/mistral-7b-instruct-v0.2.Q4_K_M.gguf" # <-- UPDATE THIS PATH
    ```

## 🚀 How to Run

1.  Run the main application file from your terminal:

    ```bash
    python dashboard.py
    ```

2.  The application will run a first-time setup for your initial salary and leave data if the database file is not found.

## 🧠 Using the AI Assistant (Option 7)

The AI Assistant is the application's most powerful feature, enabling you to ask complex questions that require SQL aggregation and filtering.

| Goal | Example Prompt | Key Tables Used |
| :--- | :--- | :--- |
| **Loan Status** | What is the **remaining balance** on my *Laptop* loan? | `loans_master`, `loan_payments` |
| **Total Expenses** | What is the **total** I spent on *Food* last month? | `expenses` |
| **Leave Accrual** | How many days of leave did I **take** in 2024? | `leave_logs` |
| **Ranking/Extremes** | What was the **highest expense** logged in 2025? | `expenses` |
| **Future Planning** | Which document is expiring **soonest**? | `documents` |
| **Earnings Check** | What is the **total amount** of overseas allowance logged? | `allowance_logs` |

The AI uses placeholders like `{{CURRENT_YEAR}}` and relative date logic to handle complex filtering automatically.
