# features/document_expiry_tracker.py
import datetime
import sqlite3
from core.validation import get_valid_date_input
from core.database import execute_query # Import the core DB execution function
from termcolor import colored # Import termcolor for colored messages

def document_expiry_tracker(data, print_log_table):
    """
    Tracks document/license expiration dates, allowing add, edit, and delete using SQLite.
    LOOP ADDED to keep the user in this tracker until they exit.
    """
    while True: # Persistence Loop
        print(colored("\n--- 📄 Document Expiry Tracker ---", 'cyan'))

        today = datetime.date.today()

        # 1. Retrieve and Process all documents from the database
        try:
            columns, results = execute_query("SELECT id, name, expiry_date FROM documents ORDER BY expiry_date ASC")
        except sqlite3.Error as e:
            print(colored(f"Database Error: Could not retrieve documents. {e}", 'red'))
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
                    'STATUS': colored("Error: Invalid date format in DB", 'red'),
                    'days_remaining': 999999
                })
                continue

            days_remaining = (expiry_date - today).days

            status = ""
            if days_remaining < 0:
                status = colored(f"EXPIRED ({abs(days_remaining)} days ago)", 'red', attrs=['bold'])
            elif days_remaining <= 90:
                status = colored(f"WARNING: Expires in {days_remaining} days", 'yellow', attrs=['bold'])
            else:
                status = f"Expires in {days_remaining} days"

            processed_docs.append({
                'ID': doc_id,
                'NAME': name,
                'EXPIRY_DATE': expiry_date.isoformat(),
                'STATUS': status,
                'days_remaining': days_remaining
            })

        # The SQL query already sorts them, but we use the days_remaining key for final sorting integrity
        sorted_docs = sorted(processed_docs, key=lambda x: x['days_remaining'])

        print(colored("\n**📋 Current Documents (Sorted by Expiry Date):**", 'white', attrs=['bold']))

        if sorted_docs:
            # Prepare for print_log_table
            headers = ["ID", "DOCUMENT NAME", "EXPIRY DATE", "STATUS"]
            column_keys = ["ID", "NAME", "EXPIRY_DATE", "STATUS"]

            print_log_table(headers, sorted_docs, column_keys)
        else:
            print("No documents logged.")


        # --- Menu and User Input ---
        print("\n[A]dd, [E]dit, [D]elete Document, [B]ack to Main Menu")
        choice = input(colored("Enter option: ", 'green')).upper()

        if choice == 'A':
            print(colored("\n--- Add Document ---", 'yellow'))
            name = ""
            while True:
                name = input("Document Name (e.g., Driver's License, Type 'B' to cancel): ").strip()
                if name.upper() in ['B', 'BACK']:
                    print(colored("Action cancelled.", 'yellow'))
                    break # Exit the inner loop, cancellation handled below
                if name:
                    break
                print(colored("Error: Document name cannot be blank.", 'red'))

            if name.upper() in ['B', 'BACK']:
                print(colored("Action cancelled.", 'yellow'))
                continue

            expiry_str = get_valid_date_input("Expiry Date (YYYY-MM-DD): ", allow_empty=False)

            # --- CANCELLATION CHECK 1 (Date) ---
            if expiry_str is None:
                print(colored("Action cancelled.", 'yellow'))
                continue

            try:
                # INSERT INTO documents
                execute_query("INSERT INTO documents (name, expiry_date) VALUES (?, ?)", (name, expiry_str))
                print(colored(f"Document '{name}' added successfully.", 'green'))
            except sqlite3.Error as e:
                print(colored(f"Error adding document: {e}", 'red'))

        elif choice == 'E':
            print(colored("\n--- Edit Document ---", 'yellow'))
            doc_id_input = input("Enter ID of document to EDIT (Type 'B' to cancel): ")

            if doc_id_input.upper() in ['B', 'BACK']:
                print(colored("Action cancelled.", 'yellow'))
                continue

            try:
                doc_id = int(doc_id_input)

                # 1. Retrieve current data for editing prompt
                _, current_doc_result = execute_query("SELECT name, expiry_date FROM documents WHERE id = ?", (doc_id,))
                if not current_doc_result:
                    print(colored("Error: Invalid Document ID.", 'red'))
                    continue

                current_name, current_expiry = current_doc_result[0]

                new_name = input(f"New Name (current: {current_name}, press ENTER to keep): ")

                # Check for cancellation during subsequent input
                if new_name.upper() in ['B', 'BACK']:
                    print(colored("Edit cancelled.", 'yellow'))
                    continue

                # Prompt for date. We use standard input first, then validate if not empty.
                new_expiry_str_input = input(f"New Expiry Date (current: {current_expiry}, press ENTER to keep, or type 'B' to cancel): ")

                if new_expiry_str_input.upper() in ['B', 'BACK']:
                    print(colored("Edit cancelled.", 'yellow'))
                    continue

                name_to_update = new_name if new_name else current_name
                expiry_to_update = current_expiry

                if new_expiry_str_input:
                    # Validate the entered date string using the core validator
                    validated_date = get_valid_date_input(f"Confirm '{new_expiry_str_input}' or enter new date (YYYY-MM-DD): ", allow_empty=True)

                    if validated_date is not None and validated_date != '':
                        expiry_to_update = validated_date
                    elif validated_date is None: # User canceled validation prompt
                        print(colored("Edit cancelled.", 'yellow'))
                        continue
                    # Else: If validated_date is '', it means user confirmed an empty value which is handled by previous input check

                # 2. UPDATE database record
                if name_to_update != current_name or expiry_to_update != current_expiry:
                    execute_query("UPDATE documents SET name = ?, expiry_date = ? WHERE id = ?",
                                  (name_to_update, expiry_to_update, doc_id))
                    print(colored(f"Document ID {doc_id} updated successfully.", 'green'))
                else:
                    print("No changes made.")

            except ValueError:
                print(colored("Error: Invalid ID format. Must be a number.", 'red'))
            except sqlite3.Error as e:
                print(colored(f"Error updating document: {e}", 'red'))

        elif choice == 'D':
            print(colored("\n--- Delete Document ---", 'red'))
            doc_id_input = input("Enter ID of document to DELETE (Type 'B' to cancel): ")

            if doc_id_input.upper() in ['B', 'BACK']:
                print(colored("Action cancelled.", 'yellow'))
                continue

            try:
                doc_id = int(doc_id_input)

                # DELETE record
                execute_query("DELETE FROM documents WHERE id = ?", (doc_id,))

                # Check if row was actually deleted
                _, check_results = execute_query("SELECT name FROM documents WHERE id = ?", (doc_id,))
                if not check_results:
                    print(colored(f"Document ID {doc_id} deleted successfully.", 'green'))
                else:
                    print(colored("Error: Document not found or deletion failed.", 'red'))

            except ValueError:
                print(colored("Error: Invalid ID format. Must be a number.", 'red'))
            except sqlite3.Error as e:
                print(colored(f"Error deleting document: {e}", 'red'))

        elif choice == 'B':
            # Exit the loop and return to the main menu
            return

        else:
            print(colored("Invalid option. Please choose A, E, D, or B.", 'red'))
