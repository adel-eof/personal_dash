# features/ai_tools.py
import datetime
import json
import inspect
import os
import sqlite3
import re
from pydantic import BaseModel, Field, ValidationError
from features.salary_tracker import calculate_allowance
from core.data_manager import load_data
from core.database import execute_query
from llama_cpp import Llama
from termcolor import colored # ADDED: for color output
from dotenv import load_dotenv

# --- ENVIRONMENT LOAD ---
load_dotenv()

# --- LLM CONFIGURATION ---
MODEL_PATH = os.getenv("MODEL_PATH")
N_CTX = 4096
LLM_N_GPU_LAYERS = 60

LLM_MODEL = None

def load_local_llm():
    """
    Initializes and loads the local GGUF model only if it hasn't been loaded yet (Lazy Loading).
    """
    global LLM_MODEL

    if LLM_MODEL is not None:
        return LLM_MODEL # Already loaded, return instance immediately

    if not os.path.exists(MODEL_PATH):
        print(colored(f"\n[CRITICAL ERROR] Local model file not found at {MODEL_PATH}", 'red'))
        print(colored("Please download a GGUF model and update the configured MODEL_PATH.", 'yellow'))
        return None

    try:
        # NOTE: This print statement is now the main indicator for the loading delay
        print(colored(f"\n[LOADING LLM] Initializing model from {MODEL_PATH}... This may take a moment.", 'magenta'))
        LLM_MODEL = Llama(
            model_path=MODEL_PATH,
            n_ctx=N_CTX,
            n_gpu_layers=LLM_N_GPU_LAYERS,
            verbose=False
        )
        print(colored("Local LLM loaded successfully.", 'green'))
    except Exception as e:
        print(colored(f"\n[CRITICAL ERROR] Failed to load LLM: {e}", 'red'))
        LLM_MODEL = None
        return None

    return LLM_MODEL

# --- Pydantic Schemas (Guardrail Definition) ---

class SalaryAllowanceArgs(BaseModel):
    """Schema for arguments to query_salary_allowance."""
    days_overseas: int = Field(..., description="Total days worked overseas (positive integer).")
    days_overtime: int = Field(..., description="Total overtime days worked (weekends, positive integer).")
    base_salary: float | None = Field(None, description="Optional override for monthly base salary.")

class DocumentExpiryArgs(BaseModel):
    """Schema for arguments to query_document_expiry."""
    target_year: int = Field(..., description="The year to check for expiry (e.g., 2026).")
    target_month: int | None = Field(None, ge=1, le=12, description="The month (1-12) to check. If None, the entire year is checked.")

class SQLQueryArgs(BaseModel):
    """Schema for arguments to execute_sql_query."""
    query: str = Field(..., description="The full, safe SQL SELECT query to run against the database.")

class ConversationArgs(BaseModel):
    """Schema for arguments to respond_conversationally."""
    response: str = Field(..., description="A simple greeting or brief, direct answer to the user's non-data query.")

# --- AI Tool Definitions (Adapted for Text-to-SQL) ---

def respond_conversationally(response: str) -> str:
    """Handles simple greetings and queries not requiring data access."""
    return response

def query_salary_allowance(days_overseas: int, days_overtime: int, base_salary: float = None) -> str:
    """Calculates the total overseas allowance and overtime amount."""
    app_data, _ = load_data()
    salary_data = app_data['salary']

    base = float(base_salary) if base_salary is not None else float(salary_data['monthly_base'])
    fiscal_days = float(salary_data['total_fiscal_days'])
    rate = float(salary_data['overseas_allowance_rate'])

    allowance_amount, overtime_amount = calculate_allowance(
        base, fiscal_days, days_overseas, days_overtime, rate
    )

    total_earned = allowance_amount + overtime_amount

    return f"Based on a monthly salary of ${base:.2f}, working {days_overseas} overseas days and {days_overtime} overtime days yields a total allowance of ${total_earned:.2f} (Allowance: ${allowance_amount:.2f}, Overtime: ${overtime_amount:.2f})."


def query_document_expiry(target_year: int, target_month: int | None = None) -> str:
    """Finds documents expiring within a specific month or the entire year."""
    month_filter = f"AND STRFTIME('%m', expiry_date) = '{target_month:02d}'" if target_month is not None else ""

    sql_query = f"""
        SELECT name, expiry_date
        FROM documents
        WHERE STRFTIME('%Y', expiry_date) = '{target_year}' {month_filter}
    """

    try:
        columns, results = execute_query(sql_query)
    except Exception as e:
        return f"ERROR: Could not query database for expiry: {e}"

    if results:
        return f"Documents expiring in the requested period: {', '.join([f'{name} on {date}' for name, date in results])}"
    else:
        period_desc = f"in the year {target_year}" if target_month is None else f" in {target_month}/{target_year}"
        return f"No documents found expiring {period_desc}."

def execute_sql_query(query: str) -> str:
    """
    Executes a safe SQL SELECT query against the database,
    returning machine-readable JSON including error status.
    """

    if not query.strip().upper().startswith('SELECT'):
        return json.dumps({"status": "error", "message": "Only safe SELECT queries are permitted for data analysis."})

    try:
        columns, results = execute_query(query)

        # 1. Handle Empty Results (including [None] for aggregate queries on empty tables)
        is_aggregate_zero = (
            len(results) == 1 and
            len(columns) == 1 and
            (results[0][0] is None or results[0][0] == 0) and
            any(agg in columns[0].upper() for agg in ['SUM', 'COUNT', 'AVG'])
        )

        if not results or is_aggregate_zero:
            # Report a clean zero result for aggregates, or simple 'no_results' otherwise
            clean_data = {columns[0]: 0.0} if is_aggregate_zero else []
            return json.dumps({"status": "no_results", "data": clean_data, "query": query})

        formatted_results = []
        for row in results:
            row_dict = {}
            for col_name, value in zip(columns, row):
                # Ensure values are clean, readable strings/floats for the summarizing AI
                row_dict[col_name] = value if value is not None else "NULL"
            formatted_results.append(row_dict)

        # Return raw JSON for the next pass
        return json.dumps({"status": "success", "data": formatted_results})

    except Exception as e:
        # Structure the database error output clearly for the summary engine
        return json.dumps({"status": "error", "message": f"Database Error: {e}"})


# --- NEW: SECOND LLM PASS for Conversational Summary (Refined Prompt & Error Handling) ---

def natural_language_summary(user_query: str, raw_result_json: str) -> str:
    """Sends the raw SQL result back to the LLM for conversational interpretation."""
    llm = load_local_llm()
    if llm is None:
        return "Error: Cannot generate summary, LLM not loaded."

    # --- REFINED SUMMARY PROMPT FOR ERROR HANDLING ---
    summary_prompt = (
        "You are a helpful and supportive data analyst. "
        "The user's original request was: '{user_query}'. "
        "The database operation returned the following JSON result: '{raw_result_json}'. "

        "Your primary task is to summarize the outcome conversationally for the user."

        "**CRITICAL INSTRUCTIONS:**"
        "1. **Success/No Results:** Summarize data clearly, using $X.YY for money and explicitly stating units (e.g., '5 days')."
        "2. **Error Handling:** If the 'status' is 'error', analyze the 'message' field (e.g., 'Database Error: no such column'). Explain the error simply (e.g., 'It looks like the column name was misspelled, please check table and column names') and ask the user to rephrase their original request, referencing the potential mistake."
        "3. **Tone:** Be concise, supportive, and avoid technical jargon."

        "Output ONLY the final conversational summary."
    ).format(user_query=user_query, raw_result_json=raw_result_json)
    # ----------------------------------------------------


    try:
        output = llm(
            summary_prompt,
            max_tokens=512,
            stop=["User asked:", "JSON data:", "CRITICAL INSTRUCTIONS:"],
            temperature=0.2
        )
        return output["choices"][0]["text"].strip()
    except Exception as e:
        return f"Error generating conversational summary: {e}"


# --- AI Tool Execution Pipeline ---

ALLOWED_TOOLS = {
    "respond_conversationally": {
        "function": respond_conversationally,
        "schema": ConversationArgs,
        "description": "Use this tool ONLY for simple greetings, acknowledgments (like Hi, Thanks, Bye), or questions completely unrelated to financial or tracking data."
    },
    "query_salary_allowance": {
        "function": query_salary_allowance,
        "schema": SalaryAllowanceArgs,
        "description": "Calculates projected salary/allowance based on days worked."
    },
    "query_document_expiry": {
        "function": query_document_expiry,
        "schema": DocumentExpiryArgs,
        "description": "Checks which documents are expiring in a specific month AND year. Use for simple date filtering, not ranking (soonest/latest)."
    },
    "execute_sql_query": {
        "function": execute_sql_query,
        "schema": SQLQueryArgs,
        "description": (
            "Use for complex data analysis, calculating totals (SUM/COUNT), or filtering logs. "
            "CRITICAL RULE: When using SUM, COUNT, or AVG, you MUST assign an alias using the 'AS' keyword (e.g., 'SELECT SUM(amount) AS total_amount')."
            "DATE FILTERING FORMAT: Use SUBSTR(date, 1, 7) = 'YYYY-MM' for month filtering, or SUBSTR(date, 1, 4) = 'YYYY' for year filtering. "
            "IMPORTANT PLACEHOLDERS: For current time, use '{{CURRENT_YEAR}}' or '{{CURRENT_MONTH}}' (format MM). For relative time, use '{{CURRENT_YEAR-N}}' or '{{CURRENT_MONTH+N}}'. "
            "Example Month Query: WHERE SUBSTR(date, 1, 7) = '{{CURRENT_YEAR}}-{{CURRENT_MONTH}}'. "
            "Use this tool for all queries involving **TOTAL DAYS OF LEAVE**, expenses analysis, or counting tasks. "
            "Use this tool for queries involving: **SOONEST**, LATEST, HIGHEST, LOWEST, AVG. "
            "Available Tables & Columns: "
            "1. leave_logs (id, date, days, description) - Use SUM(days) for total leave."
            "2. expenses (id, date, category, description, amount) - Use SUM(amount) for totals."
            "3. tasks (id, task, done)"
            "4. documents (id, name, expiry_date) - Use ORDER BY expiry_date ASC LIMIT 1 for 'soonest'."
            "5. allowance_logs (id, date, total_earned, overseas_days, overtime_days, allowance_amount, overtime_amount)"
            "6. **loans_master** (id, description, total_amount, monthly_payment, start_date, duration_months, due_day, status) - Use this for general loan terms."
            "7. **loan_payments** (id, loan_id, payment_date, amount_paid) - Use with SUM(amount_paid) and JOIN on loans_master for balances."
        )
    },
}

# --- Function to generate the structured prompt for the LLM (Refined) ---
def generate_tool_prompt(user_query: str, history: list) -> str:
    """Generates the structured prompt including tools, current date, and conversation history."""

    tool_descriptions = []

    current_date = datetime.date.today().strftime("%Y-%m-%d")
    current_year = datetime.date.today().strftime("%Y")
    current_month = datetime.date.today().strftime("%m")

    for name, info in ALLOWED_TOOLS.items():
        schema_json = info['schema'].schema_json(indent=2)

        tool_descriptions.append(
f"""
Tool Name: {name}
Description: {info['description']}
JSON Schema: {schema_json.replace('\n', ' ')}
"""
        )

    tools_text = "\n---\n".join(tool_descriptions)

    history_string = ""
    if history:
        history_string = "\n--- CONVERSATION HISTORY ---\n"
        for turn in history:
            role = turn["role"].title()
            content = turn["content"]
            history_string += f"{role}: {content}\n"
        history_string += "--------------------------\n"

    system_prompt = (
        "You are an intelligent, low-latency function-calling engine. "
        "The current date is **{current_date}**. The CURRENT YEAR is **{current_year}**. The CURRENT MONTH is **{current_month}** (MM format). "

        # FIX: Generalize the PRIORITY instruction to force the use of the SQL tool for complex analysis
        "PRIORITY: For any queries involving **analysis** (e.g., 'total', 'sum', 'average', 'highest', 'month', or calculations), you MUST use the **'execute_sql_query' tool**. The correct table must be selected from the tool description."

        "Analyze the user's request, select the single appropriate tool, and generate ONLY the JSON call. "
        "Your response MUST start immediately with '{{\"function\":...}}' (use double quotes for all keys/strings). "
        "If the query is a simple greeting or non-contextual question, use the 'respond_conversationally' tool. "
        "DO NOT include newlines or leading spaces before the JSON output."
    ).format(current_date=current_date, current_year=current_year, current_month=current_month)

    prompt = (
        f"--- SYSTEM INSTRUCTION ---\n{system_prompt}\n\n"
        f"--- AVAILABLE TOOLS ---\n{tools_text}\n\n"
        f"{history_string}"
        f"--- USER REQUEST ---\n{user_query}\n\n"
        f"--- JSON OUTPUT (STARTING WITH {{) ---\n"
    )
    return prompt

# --- Function that replaces the simulation (Fixed) ---
def call_local_llm(user_query: str, history: list) -> str:
    """Calls the local LLM to generate the structured JSON function call."""
    llm = load_local_llm()
    if llm is None:
        return None

    prompt = generate_tool_prompt(user_query, history)

    print("\n[Debug: Sending prompt to LLM... this may take a moment]")

    try:
        output = llm(
            prompt,
            max_tokens=2048,
            stop=["\n---", "None"],
            temperature=0.0
        )
    except Exception as e:
        # print(f"\n[CRITICAL LLM CALL ERROR] {e}")
        return f'{{"error": "LLM Inference Failed during call: {e}"}}'


    raw_output_text = output["choices"][0]["text"]
    print(f"[DEBUG: Raw LLM Text Before Strip] {repr(raw_output_text)}")
    llm_output_text = raw_output_text.strip()

    # --- FIX: Brace Counting Extraction Logic ---
    try:
        start_index = llm_output_text.index('{')
        potential_json = llm_output_text[start_index:]

        brace_count = 0
        end_index = -1
        for i, char in enumerate(potential_json):
            if char == '{':
                brace_count += 1
            elif char == '}':
                brace_count -= 1

            if brace_count == 0 and i > 0:
                end_index = i
                break

        if end_index != -1:
            clean_json = potential_json[:end_index + 1].strip()

            json.loads(clean_json)

            if clean_json:
                return clean_json

    except (ValueError, json.JSONDecodeError) as e:
        print(f"[DEBUG: JSON Extraction Failed. Error: {e}]")
        return f'{{"error": "LLM output was not clean JSON. Raw text: {llm_output_text.replace("\"", "''")}"}}'

    return f'{{"error": "LLM output was not clean JSON. Raw text: {llm_output_text.replace("\"", "''")}"}}'


def parse_and_execute_tool(llm_response_text: str) -> str:
    """
    Safely parses the LLM's structured output using Pydantic validation
    and executes the whitelisted function.

    Handles manual placeholder substitution and conversational summary.
    """
    try:
        response_json = json.loads(llm_response_text.strip())

        if 'error' in response_json:
            return f"Error from LLM generation: {response_json['error']}"

        function_name = response_json.get("function")

        # --- FIX: Robust argument retrieval with check for un-nested 'response' ---
        function_args = {}
        if "args" in response_json:
            function_args = response_json["args"]
        elif "arguments" in response_json:
            function_args = response_json["arguments"]

        # FIX: Check for the custom 'response' key used by the conversational tool (no args wrapper)
        elif function_name == "respond_conversationally" and "response" in response_json:
            function_args = {"response": response_json["response"]}
        # -----------------------------------------------------------------------

        if function_name not in ALLOWED_TOOLS:
            return f"Error: Function '{function_name}' is not a whitelisted tool. Execution is blocked."

        tool_info = ALLOWED_TOOLS[function_name]

        # --- Manual Placeholder Substitution (only for execute_sql_query) ---
        user_query_for_summary = f"Querying {function_name}." # Default summary context

        if function_name == "execute_sql_query":
            raw_query = function_args.get('query', '')
            current_year = datetime.date.today().year
            current_month = datetime.date.today().month

            # Regex patterns
            pattern_year = r'\{\{CURRENT_YEAR([+\-]\d+)?\}\}'
            pattern_month = r'\{\{CURRENT_MONTH([+\-]\d+)?\}\}'

            def replace_year(match):
                arithmetic = match.group(1)

                if not arithmetic:
                    return str(current_year)

                try:
                    return str(eval(str(current_year) + arithmetic))
                except Exception:
                    return str(current_year)

            def replace_month(match):
                arithmetic = match.group(1)

                target_month_int = current_month
                if arithmetic:
                    try:
                        # Calculate the relative month (e.g., 11 - 1 = 10)
                        target_month_int = eval(f"{current_month} {arithmetic}")
                    except Exception:
                        pass # Use current_month on failure

                # Ensure month is zero-padded string (e.g., 01, 11)
                return f"{target_month_int:02d}"

            # Perform the substitutions
            raw_query = re.sub(pattern_year, replace_year, raw_query)
            raw_query = re.sub(pattern_month, replace_month, raw_query)

            function_args['query'] = raw_query

            # Use the final, substituted SQL as the context for the summary pass
            user_query_for_summary = f"SQL Query: {raw_query}"
        # --- END Manual Placeholder Substitution ---


        try:
            validated_args = tool_info["schema"](**function_args)
            validated_args_dict = validated_args.model_dump(exclude_none=True)

        except ValidationError as e:
            return f"Error: AI provided invalid arguments for tool '{function_name}'. Details: {e.errors()}"

        # --- EXECUTE TOOL ---
        target_function = tool_info["function"]
        raw_result = target_function(**validated_args_dict)

        # --- Check if this was the SQL tool or the Conversation tool ---
        if function_name == "execute_sql_query":
            # Pass the raw result to the LLM for the second pass
            summary_result = natural_language_summary(user_query_for_summary, raw_result)

            # Check for error status in the raw result JSON (if available) to colorize the output
            try:
                raw_json_data = json.loads(raw_result)
                if raw_json_data.get("status") == "error":
                    return colored(f"AI Assistant: {summary_result}", 'red')

            except json.JSONDecodeError:
                # Fallback, should ideally not happen if execute_sql_query is fixed to return JSON
                pass

            return colored(f"AI Assistant: {summary_result}", 'green') # Success is green

        elif function_name == "respond_conversationally":
            # Return the direct conversational string from the tool's result
            return colored(f"AI Assistant: {raw_result}", 'white') # Simple conversation is neutral/white


        return f"AI Query Result: {raw_result}"

    except Exception as e:
        return colored(f"An unexpected internal error occurred during tool execution: {e}", 'red')
