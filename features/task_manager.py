# features/task_manager.py
import sqlite3
from core.database import execute_query
from termcolor import colored

def task_manager(data):
    """
    Manages tasks (display, add, complete) using SQLite.
    NOW USES POSITIONAL INDEXING for task completion (C).
    """
    while True: # Persistence Loop
        print(colored("\n--- 📝 Task Manager ---", 'cyan'))

        # 1. READ: Retrieve all active tasks from DB
        try:
            columns, active_tasks_rows = execute_query("SELECT id, task FROM tasks WHERE done = 0 ORDER BY id ASC")

            # Store both the displayed list and the hidden IDs
            active_tasks = []
            display_to_db_id = {} # Dictionary to map display index (1, 2, 3...) to DB ID

            if active_tasks_rows:
                # Assign a sequential display index (starting at 1)
                for index, (task_id, task_desc) in enumerate(active_tasks_rows, 1):
                    active_tasks.append({'id': task_id, 'task': task_desc, 'display_index': index})
                    display_to_db_id[str(index)] = task_id # Map '1' -> 15, '2' -> 32, etc.

        except sqlite3.Error as e:
            print(colored(f"Database Error: Could not retrieve tasks. {e}", 'red'))
            active_tasks = []
            display_to_db_id = {}


        if not active_tasks:
            print(colored("🎉 All tasks complete! Add a new one.", 'green'))
        else:
            print(colored("\n**Active Tasks (Select by Index):**", 'white', attrs=['bold']))
            for t in active_tasks:
                # Display the sequential index instead of the DB ID
                print(colored(f"[{t['display_index']:02d}] {t['task']}", 'yellow'))

        print("\n[A]dd Task, [C]omplete Task, [B]ack to Main Menu")
        choice = input(colored("Enter option: ", 'green')).upper()

        if choice == 'A':
            task_desc = ""
            # Input loop to ensure task is not blank
            while True:
                task_desc = input("Enter new task description (Type 'B' to cancel): ").strip()
                if task_desc.upper() in ['B', 'BACK']:
                    print(colored("Task addition cancelled.", 'yellow'))
                    break
                if task_desc:
                    break
                print(colored("Error: Task description cannot be blank.", 'red'))

            if task_desc.upper() in ['B', 'BACK']:
                continue # Return to start of the loop

            # 2. CREATE: Insert new task into DB (id is auto-incremented, done=0)
            try:
                execute_query("INSERT INTO tasks (task, done) VALUES (?, 0)", (task_desc,))
                print(colored(f"Task '{task_desc}' added successfully.", 'green'))
            except sqlite3.Error as e:
                print(colored(f"Error adding task: {e}", 'red'))

        elif choice == 'C':
            if not active_tasks:
                print(colored("No active tasks to complete.", 'yellow'))
                continue

            # --- CONTEXTUAL ID SELECTION LOGIC ---
            task_index_input = input("Enter **INDEX** of task to complete (e.g., 1, Type 'B' to cancel): ").strip()

            if task_index_input.upper() in ['B', 'BACK']:
                print(colored("Completion cancelled.", 'yellow'))
                continue

            # 1. Attempt lookup using the input as the display index
            if task_index_input in display_to_db_id:
                task_id_to_complete = display_to_db_id[task_index_input]
            else:
                # 2. Handle invalid input
                print(colored("Error: Invalid task index. Please enter a number shown in the list (e.g., 01, 02).", 'red'))
                continue
            # -------------------------------------

            try:
                # 3. UPDATE: Use the looked-up DB ID to complete the task
                execute_query("UPDATE tasks SET done = 1 WHERE id = ? AND done = 0", (task_id_to_complete,))

                print(colored(f"Task index {task_index_input} marked as complete.", 'green'))

            except sqlite3.Error as e:
                print(colored(f"Error completing task: {e}", 'red'))

        elif choice == 'B':
            # Exit the persistence loop
            return

        else:
            print(colored("Invalid option. Please choose A, C, or B.", 'red'))
