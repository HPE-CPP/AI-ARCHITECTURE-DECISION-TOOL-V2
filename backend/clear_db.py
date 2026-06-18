import sys
from pathlib import Path
from sqlalchemy import text

# Ensure backend root is on path
sys.path.insert(0, str(Path(__file__).resolve().parent))

try:
    from app.db.session import engine
    from app.db.base import Base
    
    table_names = [table.name for table in reversed(Base.metadata.sorted_tables)]
    
    print(f"Truncating tables: {', '.join(table_names)}")
    
    with engine.connect() as conn:
        # Use TRUNCATE with CASCADE to handle foreign key constraints
        # PostgreSQL specific syntax
        conn.execute(text(f"TRUNCATE TABLE {', '.join(table_names)} CASCADE;"))
        conn.commit()
    
    print("Database cleared successfully (tables kept).")
except Exception as e:
    print(f"Error clearing database: {e}")
