from sqlalchemy import Column, Integer, String, DateTime, ForeignKey, Float, Text, JSON, Boolean
from sqlalchemy.orm import relationship
from sqlalchemy.sql import func

from app.db.database import Base

class PlaidItem(Base):
    __tablename__ = "plaid_items"
    
    id = Column(Integer, primary_key=True, index=True)
    user_id = Column(Integer, ForeignKey("users.id"))
    plaid_item_id = Column(String, unique=True, index=True)
    plaid_access_token = Column(String)
    institution_id = Column(String)
    institution_name = Column(String)
    latest_cursor = Column(String)
    created_at = Column(DateTime(timezone=True), server_default=func.now())
    updated_at = Column(DateTime(timezone=True), onupdate=func.now())
    
    # Relationships
    user = relationship("User", back_populates="plaid_items")
    accounts = relationship("Account", back_populates="plaid_item")
    transactions = relationship("Transaction", back_populates="plaid_item")

class Account(Base):
    __tablename__ = "accounts"
    
    id = Column(Integer, primary_key=True, index=True)
    user_id = Column(Integer, ForeignKey("users.id"))
    plaid_item_id = Column(Integer, ForeignKey("plaid_items.id"))
    plaid_account_id = Column(String, unique=True, index=True)
    name = Column(String)
    official_name = Column(String)
    account_type = Column(String)
    account_subtype = Column(String)
    mask = Column(String)
    available_balance = Column(Float)
    current_balance = Column(Float)
    currency_code = Column(String, default="USD")
    is_active = Column(Boolean, default=True)
    created_at = Column(DateTime(timezone=True), server_default=func.now())
    updated_at = Column(DateTime(timezone=True), onupdate=func.now())
    
    # Relationships
    user = relationship("User", back_populates="accounts")
    plaid_item = relationship("PlaidItem", back_populates="accounts")
    transactions = relationship("Transaction", back_populates="account")

class Transaction(Base):
    __tablename__ = "transactions"
    
    id = Column(Integer, primary_key=True, index=True)
    plaid_item_id = Column(Integer, ForeignKey("plaid_items.id"))
    account_id = Column(Integer, ForeignKey("accounts.id"))
    plaid_transaction_id = Column(String, unique=True, index=True)
    category_id = Column(Integer, ForeignKey("categories.id"), nullable=True)
    
    # Transaction details
    date = Column(DateTime)
    name = Column(String)
    merchant_name = Column(String)
    amount = Column(Float)
    currency_code = Column(String, default="USD")
    pending = Column(Boolean, default=False)
    
    # Location data
    location_address = Column(String, nullable=True)
    location_city = Column(String, nullable=True)
    location_region = Column(String, nullable=True)
    location_postal_code = Column(String, nullable=True)
    location_country = Column(String, nullable=True)
    location_lat = Column(Float, nullable=True)
    location_lon = Column(Float, nullable=True)
    
    # Payment metadata
    payment_channel = Column(String, nullable=True)
    payment_method = Column(String, nullable=True)
    
    # Plaid categorization
    plaid_category = Column(String, nullable=True)
    plaid_category_id = Column(String, nullable=True)
    personal_finance_category = Column(String, nullable=True)
    personal_finance_category_id = Column(String, nullable=True)
    
    # Additional data
    original_description = Column(String, nullable=True)
    iso_currency_code = Column(String, nullable=True)
    unofficial_currency_code = Column(String, nullable=True)
    transaction_code = Column(String, nullable=True)
    
    # Raw data for reference
    raw_data = Column(JSON, nullable=True)
    
    created_at = Column(DateTime(timezone=True), server_default=func.now())
    updated_at = Column(DateTime(timezone=True), onupdate=func.now())
    
    # Relationships
    plaid_item = relationship("PlaidItem", back_populates="transactions")
    account = relationship("Account", back_populates="transactions")
    category = relationship("Category", back_populates="transactions")
    
class Category(Base):
    __tablename__ = "categories"
    
    id = Column(Integer, primary_key=True, index=True)
    user_id = Column(Integer, ForeignKey("users.id"))
    name = Column(String)
    description = Column(Text, nullable=True)
    color = Column(String, nullable=True)  # Hex color code for UI
    is_income = Column(Boolean, default=False)
    parent_id = Column(Integer, ForeignKey("categories.id"), nullable=True)
    created_at = Column(DateTime(timezone=True), server_default=func.now())
    updated_at = Column(DateTime(timezone=True), onupdate=func.now())
    
    # Relationships
    user = relationship("User", back_populates="categories")
    transactions = relationship("Transaction", back_populates="category")
    parent = relationship("Category", remote_side=[id], backref="subcategories")
    budgets = relationship("Budget", back_populates="category")