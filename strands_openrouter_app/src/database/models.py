from sqlalchemy import create_engine, Column, Integer, String, Boolean, Date
from sqlalchemy.orm import sessionmaker, declarative_base # Use declarative_base for older SQLAlchemy, or just Base = declarative_base() for newer.
from sqlalchemy.ext.declarative import declarative_base

# Define the base for declarative models
Base = declarative_base()

class Child(Base):
    __tablename__ = 'children'

    id = Column(Integer, primary_key=True, index=True, autoincrement=True)
    Name = Column(String, nullable=False, unique=True, index=True)
    Monthly_payment = Column(Integer, nullable=False)
    Last_Payment_date = Column(String, nullable=False) # Stored as TEXT (mm-dd-yyyy string)
    batch_date = Column(String, nullable=True)
    is_active = Column(Boolean, default=True, nullable=False)
    Parent_name = Column(String, nullable=False)

    def __repr__(self):
        return f"<Child(Name='{self.Name}', Parent='{self.Parent_name}', Active='{self.is_active}')>"
