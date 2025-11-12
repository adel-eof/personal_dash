# features/document_expiry_tracker.py
import datetime
import sqlite3
from core.validation import get_valid_date_input
from core.database import execute_query
from core.styles import get_style # Assuming this is the correct import for the centralized styling
from core.formatting import format_date # NEW IMPORT
from rich import print as rprint

def document_expiry_tracker(data, print_log_table):
    """
    Tracks document/license expiration dates, allowing add, edit, and delete using SQLite.
    LOOP ADDED to keep the user in this tracker until they exit.
    """
    while True: # Persistence Loop
        rprint(f"[{get_style('HEADER')}]\n--- 📄 Document Expiry Tracker ---[/]")

        today = datetime.date.today()

        # 1. Retrieve and Process all documents from the database
        try:
            columns, results = execute_query("SELECT id, name, expiry_date FROM documents ORDER BY expiry_date ASC")
        except sqlite3.Error as e:
            rprint(f"[{get_style('ERROR')}]Database Error: Could not retrieve documents. {e}[/]")
            return # Exit if the initial load fails

        processed_docs = []

        # 2. Process results to calculate days remaining and status
        for doc_id, name, expiry_date_str in results:
            try:
                expiry_date = datetime.datetime.strptime(expiry_date_str, "%Y-%m-%d").date()
            except ValueError:
                processed_docs.append({
                    'ID': doc_id,
                    'NAME': name,
                    'EXPIRY_DATE': expiry_date_str,
                    'STATUS': f"[{get_style('ERROR')}]Error: Invalid date format in DB[/]",
                    'days_remaining': 999999
                })
                continue

            days_remaining = (expiry_date - today).days

            status = ""
            if days_remaining < 0:
                status = f"[{get_style('ERROR')} bold]EXPIRED ({abs(days_remaining)} days ago)[/]"
            elif days_remaining <= 90:
                status = f"[{get_style('WARNING')} bold]WARNING: Expires in {days_remaining} days[/]"
            else:
                status = f"[{get_style('INFO')}]Expires in {days_remaining} days[/]"

            processed_docs.append({
                'ID': doc_id,
                'NAME': name,
                'EXPIRY_DATE': format_date(expiry_date.isoformat()), # Use format_date
                'STATUS': status,
                'days_remaining': days_remaining
            })

        # The SQL query already sorts them, but we use the days_remaining key for final sorting integrity
        sorted_docs = sorted(processed_docs, key=lambda x: x['days_remaining'])

        rprint(f"[{get_style('INFO')} bold]\n**📋 Current Documents (Sorted by Expiry Date):**[/]")

        if sorted_docs:
            # Prepare for print_log_table
            headers = ["ID", "DOCUMENT NAME", "EXPIRY DATE", "STATUS"]
            column_keys = ["ID", "NAME", "EXPIRY_DATE", "STATUS"]

            print_log_table(headers, sorted_docs, column_keys)
        else:
            rprint(f"[{get_style('WARNING')}]No documents logged.[/]")


        # --- Menu and User Input ---
        rprint("\n[A]dd, [E]dit, [D]elete Document, [B]ack to Main Menu")
        choice = input(f"[{get_style('PROMPT')}]Enter option: [/]").upper()

        if choice == 'A':
            rprint(f"[{get_style('WARNING')}]\n--- Add Document ---[/]")

            name = ""
            while True:
                name = input("Document Name (e.g., Driver's License, Type 'B' to cancel): ").strip()
                if name.upper() in ['B', 'BACK']:
                    rprint(f"[{get_style('WARNING')}]Action cancelled.[/]")
                    break
                if name:
                    break
                rprint(f"[{get_style('ERROR')}]Error: Document name cannot be blank.[/]")

            if name.upper() in ['B', 'BACK']:
                continue

            expiry_str = get_valid_date_input("Expiry Date (YYYY-MM-DD): ", allow_empty=False)

            if expiry_str is None:
                rprint(f"[{get_style('WARNING')}]Action cancelled.[/]")
                continue

            try:
                execute_query("INSERT INTO documents (name, expiry_date) VALUES (?, ?)", (name, expiry_str))
                rprint(f"[{get_style('SUCCESS')}]Document '{name}' added successfully.[/]")
            except sqlite3.Error as e:
                rprint(f"[{get_style('ERROR')}]Error adding document: {e}[/]")

        elif choice == 'E':
            rprint(f"[{get_style('WARNING')}]\n--- Edit Document ---[/]")
            doc_id_input = input("Enter ID of document to EDIT (Type 'B' to cancel): ")

            if doc_id_input.upper() in ['B', 'BACK']:
                rprint(f"[{get_style('WARNING')}]Action cancelled.[/]")
                continue

            try:
                doc_id = int(doc_id_input)

                _, current_doc_result = execute_query("SELECT name, expiry_date FROM documents WHERE id = ?", (doc_id,))
                if not current_doc_result:
                    rprint(f"[{get_style('ERROR')}]Error: Invalid Document ID.[/]")
                    continue

                current_name, current_expiry = current_doc_result[0]

                # --- Input loop for new name ---
                name_to_update = current_name
                while True:
                    new_name = input(f"New Name (current: {current_name}, press ENTER to keep, type 'B' to cancel): ").strip()
                    if new_name.upper() in ['B', 'BACK']:
                        rprint(f"[{get_style('WARNING')}]Edit cancelled.[/]")
                        return # Use return to break out of E choice entirely
                    if new_name:
                        name_to_update = new_name
                        break
                    elif not new_name:
                        break
                    rprint(f"[{get_style('ERROR')}]Error: Document name cannot be blank.[/]")

                expiry_to_update = current_expiry

                new_expiry_str_input = input(f"New Expiry Date (current: {format_date(current_expiry)}, press ENTER to keep): ").strip() # Use format_date in prompt

                if new_expiry_str_input.upper() in ['B', 'BACK']:
                    rprint(f"[{get_style('WARNING')}]Edit cancelled.[/]")
                    continue

                if new_expiry_str_input:
                    validated_date = get_valid_date_input(f"Confirm '{new_expiry_str_input}' or enter new date (YYYY-MM-DD): ", allow_empty=True)

                    if validated_date is None:
                        rprint(f"[{get_style('WARNING')}]Edit cancelled.[/]")
                        continue

                    if validated_date != '':
                        expiry_to_update = validated_date

                if name_to_update != current_name or expiry_to_update != current_expiry:
                    execute_query("UPDATE documents SET name = ?, expiry_date = ? WHERE id = ?",
                                  (name_to_update, expiry_to_update, doc_id))
                    rprint(f"[{get_style('SUCCESS')}]Document ID {doc_id} updated successfully.[/]")
                else:
                    rprint(f"[{get_style('INFO')}]No changes made.[/]")

            except ValueError:
                rprint(f"[{get_style('ERROR')}]Error: Invalid ID format. Must be a number.[/]")
            except sqlite3.Error as e:
                rprint(f"[{get_style('ERROR')}]Error updating document: {e}[/]")
            # Removed redundant SystemExit exception handling

        elif choice == 'D':
            rprint(f"[{get_style('ERROR')}]\n--- Delete Document ---[/]")
            doc_id_input = input("Enter ID of document to DELETE (Type 'B' to cancel): ")

            if doc_id_input.upper() in ['B', 'BACK']:
                rprint(f"[{get_style('WARNING')}]Action cancelled.[/]")
                continue

            try:
                doc_id = int(doc_id_input)

                execute_query("DELETE FROM documents WHERE id = ?", (doc_id,))

                _, check_results = execute_query("SELECT name FROM documents WHERE id = ?", (doc_id,))
                if not check_results:
                    rprint(f"[{get_style('SUCCESS')}]Document ID {doc_id} deleted successfully.[/]")
                else:
                    rprint(f"[{get_style('ERROR')}]Error: Document not found or deletion failed.[/]")

            except ValueError:
                rprint(f"[{get_style('ERROR')}]Error: Invalid ID format. Must be a number.[/]")
            except sqlite3.Error as e:
                rprint(f"[{get_style('ERROR')}]Error deleting document: {e}[/]")

        elif choice == 'B':
            return

        else:
            rprint(f"[{get_style('ERROR')}]Invalid option. Please choose A, E, D, or B.[/]")
