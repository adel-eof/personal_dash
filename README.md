# 🧠 Personal AI Dashboard (CLI)

A minimalist, highly interactive Command-Line Interface (CLI) application for personal tracking and analysis, featuring a local Large Language Model (LLM) for complex Text-to-SQL data querying and a polished user experience.

## ✨ Features

* **Integrated AI Assistant:** Uses a local GGUF LLM for natural language queries against the dashboard's SQLite database (Text-to-SQL).
* **Conversational UX:** The AI Assistant retains short-term memory for follow-up questions and provides conversational, color-coded summaries.
* **Persistent & Validated Menus:** All main tracking modules (Leave, Expense, Documents, Tasks) feature persistent sub-menus and robust input validation.
* **Data Tracking:** Modules for Expenses, Leave Balances (accrual model), Document Expiry, and Task management.

## 💻 Setup and Installation

### Prerequisites

1.  **Python:** Python 3.9+ is required.
2.  **GGUF Model:** You must download a compatible GGUF model (e.g., Mistral 7B Instruct) and save it to the path specified in `features/ai_tools.py`.

### Installation Steps

1.  **Install Dependencies:** Run the following command to install all necessary Python packages:

    ```bash
    pip install -r requirements.txt
    ```

2.  **Configure LLM Path:** Open `features/ai_tools.py` and ensure the `MODEL_PATH` variable points to your downloaded GGUF file:

    ```python
    MODEL_PATH = "/home/jigsaw/projects/llm-models/mistral-7b-instruct-v0.2.Q4_K_M.gguf" # <-- UPDATE THIS PATH
    ```

## 🚀 How to Run

1.  Run the main application file from your terminal:

    ```bash
    python dashboard.py
    ```

2.  The application will run a first-time setup for your initial salary and leave data if the database file is not found.

## 💡 Using the AI Assistant (Option 6)

The AI Assistant is designed for complex data retrieval that simple menu reports cannot handle.

| Query Type | Example | Keywords Used |
| :--- | :--- | :--- |
| **Aggregation** | "What is the **total amount** I spent on food last year?" | `total`, `sum`, `average` |
| **Date Filtering** | "How many days of leave did I take **in March**?" | `this month`, `last month`, `in [month]` |
| **Ranking/Comparison**| "What was the **highest expense** logged in 2024?" | `highest`, `lowest`, `soonest` |

The AI uses placeholders like `{{CURRENT_YEAR}}` and `{{CURRENT_MONTH}}` to handle relative date questions accurately.
