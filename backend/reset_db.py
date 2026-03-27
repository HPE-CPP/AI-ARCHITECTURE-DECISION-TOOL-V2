import sys
from pathlib import Path

# Ensure backend root is on path
sys.path.insert(0, str(Path(__file__).resolve().parent))

try:
    from app.db.session import engine
    from app.db.base import Base
    import app.db.models
    
    print("Dropping all tables...")
    Base.metadata.drop_all(bind=engine)
    
    print("Creating all tables (with updated schema)...")
    Base.metadata.create_all(bind=engine)
    
    print("Database reset successfully.")
except Exception as e:
    print(f"Error resetting database: {e}")
