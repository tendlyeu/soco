"""
Database schema inference script.
Connects to database using EE_DB_URL from .env and introspects schema.
Writes the schema to sql/schema.json.
"""
import os
import json
import sys
from pathlib import Path
from dotenv import load_dotenv
from datetime import datetime

try:
    from sqlalchemy import create_engine, inspect, MetaData
    from sqlalchemy.exc import SQLAlchemyError
except ImportError:
    print("❌ Error: sqlalchemy is not installed. Please install it:")
    print("   pip install sqlalchemy")
    sys.exit(1)

# Load environment variables
load_dotenv()

# Get database URL from environment
DB_URL = os.getenv('EE_DB_URL')

if not DB_URL:
    print("❌ Error: EE_DB_URL not found in environment variables")
    print("   Please set EE_DB_URL in your .env file")
    sys.exit(1)


def infer_schema(db_url: str) -> dict:
    """
    Infer database schema by introspecting tables, columns, and constraints.
    
    Args:
        db_url: Database connection URL
        
    Returns:
        Dictionary containing schema information
    """
    try:
        # Create engine
        print(f"🔌 Connecting to database...")
        engine = create_engine(db_url)
        
        # Create inspector
        inspector = inspect(engine)
        
        # Get all table names
        print("📊 Introspecting database schema...")
        table_names = inspector.get_table_names()
        
        if not table_names:
            print("⚠️  Warning: No tables found in database")
            return {
                "database_url": db_url.split('@')[1] if '@' in db_url else "hidden",
                "introspected_at": datetime.now().isoformat(),
                "tables": {}
            }
        
        print(f"   Found {len(table_names)} table(s)")
        
        schema = {
            "database_url": db_url.split('@')[1] if '@' in db_url else "hidden",
            "introspected_at": datetime.now().isoformat(),
            "tables": {}
        }
        
        # Introspect each table
        for table_name in table_names:
            print(f"   Processing table: {table_name}")
            
            # Get columns
            columns = inspector.get_columns(table_name)
            
            # Get primary keys (using get_pk_constraint for newer SQLAlchemy)
            try:
                pk_constraint = inspector.get_pk_constraint(table_name)
                primary_keys = pk_constraint.get('constrained_columns', []) if pk_constraint else []
            except (AttributeError, TypeError):
                # Fallback for older SQLAlchemy versions
                try:
                    primary_keys = inspector.get_primary_keys(table_name)
                except AttributeError:
                    primary_keys = []
            
            # Get foreign keys
            foreign_keys = inspector.get_foreign_keys(table_name)
            
            # Get indexes
            indexes = inspector.get_indexes(table_name)
            
            # Get unique constraints
            unique_constraints = inspector.get_unique_constraints(table_name)
            
            # Build column information
            column_info = []
            for col in columns:
                col_data = {
                    "name": col["name"],
                    "type": str(col["type"]),
                    "nullable": col.get("nullable", True),
                    "default": str(col.get("default", "")) if col.get("default") is not None else None,
                    "autoincrement": col.get("autoincrement", False)
                }
                column_info.append(col_data)
            
            # Build foreign key information
            fk_info = []
            for fk in foreign_keys:
                fk_data = {
                    "name": fk.get("name", ""),
                    "constrained_columns": fk["constrained_columns"],
                    "referred_table": fk["referred_table"],
                    "referred_columns": fk["referred_columns"]
                }
                fk_info.append(fk_data)
            
            # Build index information
            index_info = []
            for idx in indexes:
                idx_data = {
                    "name": idx["name"],
                    "column_names": idx["column_names"],
                    "unique": idx.get("unique", False)
                }
                index_info.append(idx_data)
            
            # Build unique constraint information
            unique_info = []
            for uc in unique_constraints:
                uc_data = {
                    "name": uc.get("name", ""),
                    "column_names": uc["column_names"]
                }
                unique_info.append(uc_data)
            
            # Store table information
            schema["tables"][table_name] = {
                "columns": column_info,
                "primary_keys": primary_keys,
                "foreign_keys": fk_info,
                "indexes": index_info,
                "unique_constraints": unique_info
            }
        
        print("✅ Schema introspection completed successfully")
        return schema
        
    except SQLAlchemyError as e:
        print(f"❌ Database error: {str(e)}")
        raise
    except Exception as e:
        print(f"❌ Unexpected error: {str(e)}")
        raise
    finally:
        if 'engine' in locals():
            engine.dispose()


def write_schema(schema: dict, output_path: Path):
    """
    Write schema to JSON file.
    
    Args:
        schema: Schema dictionary
        output_path: Path to output JSON file
    """
    # Ensure output directory exists
    output_path.parent.mkdir(parents=True, exist_ok=True)
    
    # Write schema to JSON file
    print(f"💾 Writing schema to {output_path}...")
    with open(output_path, 'w', encoding='utf-8') as f:
        json.dump(schema, f, indent=2, ensure_ascii=False)
    
    print(f"✅ Schema written successfully to {output_path}")


def main():
    """Main function to infer and write schema."""
    print("=" * 60)
    print("Database Schema Inference")
    print("=" * 60)
    print()
    
    # Get project root (parent of tasks directory)
    project_root = Path(__file__).parent.parent
    output_path = project_root / "sql" / "schema.json"
    
    try:
        # Infer schema
        schema = infer_schema(DB_URL)
        
        # Write schema to file
        write_schema(schema, output_path)
        
        # Print summary
        print()
        print("=" * 60)
        print("Summary")
        print("=" * 60)
        print(f"Tables found: {len(schema['tables'])}")
        print(f"Output file: {output_path}")
        print()
        
        return 0
        
    except Exception as e:
        print()
        print("=" * 60)
        print("❌ Schema inference failed")
        print("=" * 60)
        print(f"Error: {str(e)}")
        return 1


if __name__ == "__main__":
    sys.exit(main())

