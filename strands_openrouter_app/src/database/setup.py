import os
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker, Session as SQLAlchemySession # Alias to avoid confusion
from contextlib import contextmanager
import logging

# Import the Base and Child model from models.py
# Ensure that the path is correct for Python to find 'models' module within 'database' package
# This assumes that 'src' is in PYTHONPATH or the script is run from a context where 'database' is a package.
from .models import Base, Child # Relative import if setup.py is part of the database package

# Define the database URL. SQLite will create this file in the project root.
# For more complex projects, this could be in a data directory or configured via env vars.
DATABASE_FILE = "children.db"
DATABASE_URL = f"sqlite:///{os.path.abspath(os.path.join(os.path.dirname(__file__), '..', '..', DATABASE_FILE))}"
# This path places children.db in the root of strands_openrouter_app

logger = logging.getLogger(__name__)

# Create an engine instance
engine = create_engine(DATABASE_URL, echo=False) # Set echo=True for SQL logging, False for less noise

# Create a configured "Session" class
SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)

def init_db():
    """
    Initializes the database and creates tables if they don't exist.
    This function should be called once at application startup (e.g., in Chainlit's on_chat_start).
    """
    try:
        logger.info(f"Initializing database at {DATABASE_URL}...")
        Base.metadata.create_all(bind=engine)
        logger.info("Database tables created successfully (if they didn't exist).")
    except Exception as e:
        logger.error(f"Error creating database tables: {e}", exc_info=True)
        raise # Re-raise the exception to make the caller aware

@contextmanager
def get_db_session() -> SQLAlchemySession: # Use the aliased SQLAlchemySession
    """
    Provides a database session for use in a 'with' statement.
    Ensures the session is closed properly.
    Usage:
        with get_db_session() as db:
            # do stuff with db
            db.commit() # or db.rollback()
    """
    db = SessionLocal()
    try:
        yield db
    except Exception:
        db.rollback()
        raise
    finally:
        db.close()

def add_test_data(db: SQLAlchemySession):
    """Adds some initial test data to the database if it's empty."""
    if db.query(Child).count() == 0:
        logger.info("Adding test data to the database...")
        test_children = [
            Child(Name="Alice Smith", Monthly_payment=100, Last_Payment_date="12-15-2023", batch_date="B1", is_active=True, Parent_name="John Smith"),
            Child(Name="Bob Johnson", Monthly_payment=150, Last_Payment_date="12-20-2023", batch_date="B1", is_active=True, Parent_name="Jane Johnson"),
            Child(Name="Charlie Brown", Monthly_payment=75, Last_Payment_date="11-30-2023", batch_date="B2", is_active=False, Parent_name="Lucy Brown"),
            Child(Name="Diana Prince", Monthly_payment=200, Last_Payment_date="01-05-2024", batch_date="B2", is_active=True, Parent_name="Steve Trevor"),
        ]
        db.add_all(test_children)
        db.commit()
        logger.info("Test data added.")
    else:
        logger.info("Database already contains data. Skipping test data addition.")

if __name__ == '__main__':
    # This allows running setup.py directly to initialize the DB and add test data
    print("Running database setup directly...")
    logging.basicConfig(level=logging.INFO) # Ensure logger is configured for direct script run
    init_db()
    with get_db_session() as session:
        add_test_data(session)
    print(f"Database setup complete. DB file should be at: {DATABASE_URL.replace('sqlite:///', '')}")

    # Example: Query and print data to verify
    with get_db_session() as session:
        print("\nVerifying data:")
        all_children = session.query(Child).all()
        if all_children:
            for child_obj in all_children:
                print(f"  - {child_obj.Name}, Parent: {child_obj.Parent_name}, Active: {child_obj.is_active}, Last Payment: {child_obj.Last_Payment_date}")
        else:
            print("  No children found in the database.")
