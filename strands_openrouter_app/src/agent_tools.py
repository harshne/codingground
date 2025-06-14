import logging
from sqlalchemy.orm import Session as SQLAlchemySession
from sqlalchemy.exc import SQLAlchemyError, IntegrityError

from strands import tool

# Assuming 'src' is in PYTHONPATH or script is run from root where 'src' is a top-level dir.
# For robust imports if running tools directly or from different contexts, ensure Python path is set up.
# When Chainlit runs app.py, and app.py adds 'src' to path, these should work.
try:
    from database.setup import get_db_session
    from database.models import Child
except ImportError:
    # Fallback for potential path issues if this module is imported differently (e.g. by a test directly)
    # This is a common issue in modular Python projects without full packaging.
    # Adding this path adjustment here is a pragmatic way to help, but proper packaging is the ideal solution.
    import sys
    import os
    # Construct the absolute path to the 'src' directory
    # __file__ is the path to agent_tools.py (e.g., /app/src/agent_tools.py)
    # os.path.dirname(__file__) is /app/src
    # os.path.join(os.path.dirname(__file__), '..') is /app
    src_dir_path = os.path.abspath(os.path.join(os.path.dirname(__file__), '..'))
    if src_dir_path not in sys.path:
        sys.path.insert(0, src_dir_path)
    from database.setup import get_db_session
    from database.models import Child


logger = logging.getLogger(__name__)

@tool
def add_child(name: str, monthly_payment: int, last_payment_date: str, batch_date: str, is_active: bool, parent_name: str) -> str:
    """
    Adds a new child record to the database.
    Args:
        name (str): The full name of the child.
        monthly_payment (int): The monthly payment amount for the child.
        last_payment_date (str): The last payment date in 'mm-dd-yyyy' format.
        batch_date (str): The batch date associated with the child.
        is_active (bool): The active status of the child (True for active, False for inactive).
        parent_name (str): The full name of the parent.
    Returns:
        str: A message indicating success or failure.
    """
    logger.info(f"Tool 'add_child' called with: name='{name}', parent='{parent_name}'")
    db: SQLAlchemySession # For type hinting
    try:
        with get_db_session() as db:
            existing_child = db.query(Child).filter(Child.Name == name).first()
            if existing_child:
                return f"Error: Child with name '{name}' already exists."

            new_child = Child(
                Name=name,
                Monthly_payment=monthly_payment,
                Last_Payment_date=last_payment_date, # Assuming validation happens before or is not critical here
                batch_date=batch_date,
                is_active=is_active,
                Parent_name=parent_name
            )
            db.add(new_child)
            db.commit()
            return f"Successfully added child: {name}, Parent: {parent_name}."
    except IntegrityError as ie:
        # This block might be specific if db variable is not in scope after exception from context manager
        # However, the rollback is typically handled by the context manager's __exit__
        logger.warning(f"Integrity error in add_child for {name}: {ie}")
        # db.rollback() # Context manager should handle rollback on exception
        return f"Error: A child with the name '{name}' might already exist or other integrity issue."
    except SQLAlchemyError as e:
        logger.error(f"Database error in add_child for {name}: {e}", exc_info=True)
        # db.rollback() # Context manager should handle rollback
        return f"Error adding child '{name}': A database error occurred. Details: {str(e)}"
    except Exception as e:
        logger.error(f"Unexpected error in add_child for {name}: {e}", exc_info=True)
        return f"An unexpected error occurred while trying to add child '{name}'. Details: {str(e)}"

@tool
def get_child_details(name: str) -> str:
    """
    Retrieves and returns details for a specific child by their full name.
    Args:
        name (str): The full name of the child to retrieve.
    Returns:
        str: A string containing the child's details, or a message if not found or an error occurs.
    """
    logger.info(f"Tool 'get_child_details' called for: name='{name}'")
    try:
        with get_db_session() as db:
            child = db.query(Child).filter(Child.Name == name).first()
            if child:
                details = (
                    f"Child Details for {child.Name}:\n"
                    f"  ID: {child.id}\n"
                    f"  Monthly Payment: ${child.Monthly_payment}\n"
                    f"  Last Payment Date: {child.Last_Payment_date}\n"
                    f"  Batch Date: {child.batch_date}\n"
                    f"  Active Status: {'Active' if child.is_active else 'Inactive'}\n"
                    f"  Parent Name: {child.Parent_name}"
                )
                return details
            else:
                return f"Child with name '{name}' not found."
    except SQLAlchemyError as e:
        logger.error(f"Database error in get_child_details for {name}: {e}", exc_info=True)
        return f"Error retrieving details for child '{name}': A database error occurred. Details: {str(e)}"
    except Exception as e:
        logger.error(f"Unexpected error in get_child_details for {name}: {e}", exc_info=True)
        return f"An unexpected error occurred while trying to retrieve details for child '{name}'. Details: {str(e)}"

@tool
def update_child_payment(name: str, new_payment_amount: int, new_last_payment_date: str) -> str:
    """
    Updates a child's monthly payment amount and last payment date.
    Args:
        name (str): The full name of the child to update.
        new_payment_amount (int): The new monthly payment amount.
        new_last_payment_date (str): The new last payment date in 'mm-dd-yyyy' format.
    Returns:
        str: A message indicating success or failure.
    """
    logger.info(f"Tool 'update_child_payment' called for: name='{name}'")
    try:
        with get_db_session() as db:
            child = db.query(Child).filter(Child.Name == name).first()
            if child:
                child.Monthly_payment = new_payment_amount
                child.Last_Payment_date = new_last_payment_date
                db.commit()
                return f"Successfully updated payment details for child: {name}."
            else:
                return f"Child with name '{name}' not found. No update performed."
    except SQLAlchemyError as e:
        logger.error(f"Database error in update_child_payment for {name}: {e}", exc_info=True)
        return f"Error updating payment for child '{name}': A database error occurred. Details: {str(e)}"
    except Exception as e:
        logger.error(f"Unexpected error in update_child_payment for {name}: {e}", exc_info=True)
        return f"An unexpected error occurred while trying to update payment for child '{name}'. Details: {str(e)}"

@tool
def set_child_active_status(name: str, is_active: bool) -> str:
    """
    Sets a child's active status.
    Args:
        name (str): The full name of the child to update.
        is_active (bool): The new active status (True for active, False for inactive).
    Returns:
        str: A message indicating success or failure.
    """
    logger.info(f"Tool 'set_child_active_status' called for: name='{name}', status='{is_active}'")
    try:
        with get_db_session() as db:
            child = db.query(Child).filter(Child.Name == name).first()
            if child:
                child.is_active = is_active
                db.commit()
                status_str = "active" if is_active else "inactive"
                return f"Successfully set status for child '{name}' to {status_str}."
            else:
                return f"Child with name '{name}' not found. No status change."
    except SQLAlchemyError as e:
        logger.error(f"Database error in set_child_active_status for {name}: {e}", exc_info=True)
        return f"Error setting status for child '{name}': A database error occurred. Details: {str(e)}"
    except Exception as e:
        logger.error(f"Unexpected error in set_child_active_status for {name}: {e}", exc_info=True)
        return f"An unexpected error occurred while trying to set status for child '{name}'. Details: {str(e)}"

@tool
def list_children_by_parent(parent_name: str) -> str:
    """
    Lists all children associated with a given parent's name.
    Args:
        parent_name (str): The full name of the parent.
    Returns:
        str: A string containing a list of children, or a message if none found or an error occurs.
    """
    logger.info(f"Tool 'list_children_by_parent' called for: parent_name='{parent_name}'")
    try:
        with get_db_session() as db:
            children = db.query(Child).filter(Child.Parent_name == parent_name).all()
            if children:
                response_lines = [f"Children of {parent_name}:"]
                for child in children:
                    status_str = "Active" if child.is_active else "Inactive"
                    response_lines.append(f"  - {child.Name} (Payment: ${child.Monthly_payment}, Last Paid: {child.Last_Payment_date}, Status: {status_str}, Batch: {child.batch_date})")
                return "\n".join(response_lines)
            else:
                return f"No children found for parent: {parent_name}."
    except SQLAlchemyError as e:
        logger.error(f"Database error in list_children_by_parent for {parent_name}: {e}", exc_info=True)
        return f"Error listing children for parent '{parent_name}': A database error occurred. Details: {str(e)}"
    except Exception as e:
        logger.error(f"Unexpected error in list_children_by_parent for {parent_name}: {e}", exc_info=True)
        return f"An unexpected error occurred while listing children for parent '{parent_name}'. Details: {str(e)}"

@tool
def list_active_children() -> str:
    """
    Lists all children who are currently marked as active.
    Returns:
        str: A string containing a list of active children, or a message if none found or an error occurs.
    """
    logger.info(f"Tool 'list_active_children' called.")
    try:
        with get_db_session() as db:
            children = db.query(Child).filter(Child.is_active == True).all() # Use == True for SQLAlchemy boolean comparison
            if children:
                response_lines = ["Active Children:"]
                for child in children:
                    response_lines.append(f"  - {child.Name} (Parent: {child.Parent_name}, Payment: ${child.Monthly_payment}, Last Paid: {child.Last_Payment_date}, Batch: {child.batch_date})")
                return "\n".join(response_lines)
            else:
                return "No active children found."
    except SQLAlchemyError as e:
        logger.error(f"Database error in list_active_children: {e}", exc_info=True)
        return f"Error listing active children: A database error occurred. Details: {str(e)}"
    except Exception as e:
        logger.error(f"Unexpected error in list_active_children: {e}", exc_info=True)
        return f"An unexpected error occurred while listing active children. Details: {str(e)}"

def get_tools():
    """Returns a list of all defined database tools for the agent."""
    return [
        add_child,
        get_child_details,
        update_child_payment,
        set_child_active_status,
        list_children_by_parent,
        list_active_children
    ]

if __name__ == '__main__':
    # Example usage and testing of the tools
    # This requires the database to be initialized first (run src/database/setup.py)
    print("Testing agent tools...")
    logging.basicConfig(level=logging.INFO) # Ensure logger is configured for direct script run

    # Ensure DB is initialized for testing
    # In a real scenario, you might have a separate test DB or ensure setup.py has run.
    try:
        # Adjust import path for direct execution if needed
        current_dir = os.path.dirname(os.path.abspath(__file__))
        project_root = os.path.abspath(os.path.join(current_dir, '..'))
        if project_root not in sys.path:
            sys.path.insert(0, project_root)

        from database.setup import init_db, add_test_data, get_db_session as main_get_db_session
        print("Initializing test database...")
        init_db() # Make sure tables are created
        with main_get_db_session() as s:
             add_test_data(s) # Add test data if needed
        print("Test database initialized and test data added (if DB was empty).")
    except ImportError as imp_err:
        print(f"ImportError during test DB setup: {imp_err}. Ensure PYTHONPATH is correct or run from project root.")
        print(f"Current sys.path: {sys.path}")
        exit(1)
    except Exception as e:
        print(f"Error during test DB setup: {e}")
        exit(1)

    print("\n--- Testing add_child ---")
    print(add_child(name="Test Child E", monthly_payment=50, last_payment_date="01-01-2024", batch_date="B3", is_active=True, parent_name="Test Parent E"))
    print(add_child(name="Alice Smith", monthly_payment=100, last_payment_date="01-01-2024", batch_date="B3", is_active=True, parent_name="Test Parent E")) # Test existing

    print("\n--- Testing get_child_details ---")
    print(get_child_details(name="Alice Smith"))
    print(get_child_details(name="NonExistent Child"))

    print("\n--- Testing update_child_payment ---")
    print(update_child_payment(name="Alice Smith", new_payment_amount=120, new_last_payment_date="01-10-2024"))
    print(get_child_details(name="Alice Smith")) # Verify update

    print("\n--- Testing set_child_active_status ---")
    print(set_child_active_status(name="Alice Smith", is_active=False))
    print(get_child_details(name="Alice Smith")) # Verify status change
    print(set_child_active_status(name="Alice Smith", is_active=True)) # Set back to active
    print(get_child_details(name="Alice Smith"))

    print("\n--- Testing list_children_by_parent ---")
    print(list_children_by_parent(parent_name="John Smith")) # This parent is from test data
    print(list_children_by_parent(parent_name="NonExistent Parent"))

    print("\n--- Testing list_active_children ---")
    print(list_active_children())

    # Example of setting a child inactive to test list_active_children again
    print(set_child_active_status(name="Bob Johnson", is_active=False)) # Bob from test data
    print("\n--- Testing list_active_children (after making Bob inactive) ---")
    print(list_active_children())
    print(set_child_active_status(name="Bob Johnson", is_active=True)) # Reset for other tests

    print("\nTool testing finished.")
