"""
LangChain SQL Agent utility for natural language to SQL queries.
Uses XAI API (Grok) with LangChain to answer questions about the database.
Infers schema on the fly and stores it in session.
"""
import os
import json
import re
from pathlib import Path
from typing import Optional, Dict, Any, List
from dotenv import load_dotenv

try:
    import pandas as pd
except ImportError:
    pd = None

try:
    from langchain_community.utilities import SQLDatabase
    from langchain_openai import ChatOpenAI
    from langchain_core.prompts import ChatPromptTemplate
    from langchain_core.messages import SystemMessage, HumanMessage
except ImportError as e:
    raise ImportError(
        f"LangChain dependencies not installed. Please install: "
        f"pip install langchain langchain-community langchain-openai"
    ) from e

# Load environment variables
load_dotenv()


class LangChainSQLAgent:
    """
    A simple SQL agent using LangChain and XAI (Grok) for natural language queries.
    
    Infers schema on the fly and stores it in memory for the session.
    Always returns structured DataFrames and SQL queries.
    """
    
    def __init__(
        self,
        db_url: Optional[str] = None,
        api_key: Optional[str] = None,
        model: str = "grok-3",
        temperature: float = 0.0,
        verbose: bool = False
    ):
        """
        Initialize the LangChain SQL Agent.
        
        Args:
            db_url: Database connection URL. If not provided, reads from EE_DB_URL env var.
            api_key: XAI API key. If not provided, reads from XAI_API_KEY env var.
            model: XAI model name (default: grok-3)
            temperature: LLM temperature (default: 0.0 for deterministic SQL)
            verbose: Whether to print verbose output (default: False)
        """
        # Get database URL
        self.db_url = db_url or os.getenv('EE_DB_URL')
        if not self.db_url:
            raise ValueError("Database URL must be provided or set EE_DB_URL in environment")
        
        # Get API key
        self.api_key = api_key or os.getenv('XAI_API_KEY')
        if not self.api_key:
            raise ValueError("XAI_API_KEY must be provided or set in environment")
        
        self.model = model
        self.temperature = temperature
        self.verbose = verbose
        
        # Initialize components
        self._initialize_database()
        self._initialize_llm()
        self._infer_and_cache_schema()
    
    def _initialize_database(self):
        """Initialize SQLDatabase from connection URL."""
        try:
            self.db = SQLDatabase.from_uri(
                self.db_url,
                include_tables=None,  # Include all tables
                sample_rows_in_table_info=3  # Include sample rows for better context
            )
            # Also create SQLAlchemy engine for direct query execution
            from sqlalchemy import create_engine
            self.engine = create_engine(self.db_url)
        except Exception as e:
            raise RuntimeError(f"Failed to connect to database: {str(e)}") from e
    
    def _initialize_llm(self):
        """Initialize ChatOpenAI LLM with XAI endpoint."""
        self.llm = ChatOpenAI(
            model=self.model,
            temperature=self.temperature,
            openai_api_key=self.api_key,
            openai_api_base="https://api.x.ai/v1"
        )
    
    def _infer_and_cache_schema(self):
        """Infer schema from database and cache it in memory."""
        try:
            # Get table info from SQLDatabase
            schema_text = self.db.get_table_info_no_throw()
            
            # Store in instance variable for reuse
            self._cached_schema = schema_text
            
            if self.verbose:
                print(f"✅ Schema inferred and cached ({len(schema_text)} characters)")
        except Exception as e:
            if self.verbose:
                print(f"⚠️  Failed to infer schema: {str(e)}")
            self._cached_schema = ""
    
    def _build_system_prompt(self) -> str:
        """Build the system prompt for SQL generation."""
        schema_text = self._cached_schema or self.db.get_table_info_no_throw()
        
        # Escape curly braces in schema text to prevent format() from interpreting them
        schema_escaped = schema_text.replace('{', '{{').replace('}', '}') if schema_text else ""
        
        prompt = """You are an expert SQL analyst. Your task is to convert natural language questions into valid PostgreSQL SQL queries.

CRITICAL RULES:
1. Generate ONLY SELECT queries - never modify data (no INSERT, UPDATE, DELETE, DROP, etc.)
2. Use exact table and column names as shown in the schema
3. Use appropriate JOINs when querying related tables
4. Use aggregate functions (COUNT, SUM, AVG, MAX, MIN, etc.) when appropriate
5. Include ORDER BY and LIMIT for large result sets
6. Handle NULL values properly with IS NULL / IS NOT NULL
7. Use proper PostgreSQL date/time functions
8. Return ONLY the SQL query - no explanations, no markdown, no narrative text
9. Format: Return JSON with this exact structure:
   {{
     "sql_query": "SELECT ... FROM ...",
     "results": [...]
   }}
   OR simply return the SQL query as plain text (preferred)

DATABASE SCHEMA:
{schema}

Remember: Your response must be either:
- A valid SQL SELECT query (preferred)
- OR JSON with "sql_query" and "results" fields
No other text or explanations.""".format(schema=schema_escaped)
        
        return prompt
    
    def _generate_sql(self, question: str) -> str:
        """Generate SQL from natural language question."""
        system_prompt = self._build_system_prompt()
        user_prompt = f"Question: {question}\n\nGenerate the SQL query:"
        
        messages = [
            SystemMessage(content=system_prompt),
            HumanMessage(content=user_prompt)
        ]
        
        try:
            response = self.llm.invoke(messages)
            content = response.content if hasattr(response, 'content') else str(response)
            
            if self.verbose:
                print(f"DEBUG: LLM Response (first 500 chars):\n{content[:500]}\n")
            
            # Clean and extract SQL
            sql = self._extract_sql_from_response(content)
            
            if self.verbose:
                print(f"DEBUG: Extracted SQL:\n{sql}\n")
            
            if not sql:
                # If extraction failed, try to use the raw content if it looks like SQL
                content_clean = content.strip()
                if content_clean.upper().startswith('SELECT'):
                    if self.verbose:
                        print("DEBUG: Using raw content as SQL")
                    return content_clean
            
            return sql
        except Exception as e:
            if self.verbose:
                import traceback
                print(f"DEBUG: Error in _generate_sql: {e}")
                print(f"DEBUG: Traceback:\n{traceback.format_exc()}")
            # Don't raise, return empty string instead
            return ""
    
    def _extract_sql_from_response(self, content: str) -> str:
        """Extract SQL query from LLM response."""
        if not content:
            return ""
        
        try:
            content_str = str(content).strip()
        except Exception:
            return ""
        
        # First check: if entire content is SQL (most common case)
        if content_str.upper().startswith('SELECT'):
            # Remove trailing semicolon if present, we'll add it back
            sql = content_str.rstrip(';').strip()
            return sql + ';' if sql else ""
        
        # Try to parse as JSON first
        try:
            # Look for JSON in response - try full JSON first
            json_match = re.search(r'\{[\s\S]*?"sql_query"[\s\S]*?\}', content_str, re.DOTALL)
            if json_match:
                json_str = json_match.group(0)
                json_data = json.loads(json_str)
                sql = json_data.get('sql_query', '')
                if sql:
                    return sql.strip()
        except Exception as e:
            # Silently continue - JSON parsing failed, try other methods
            pass
        
        # Try to extract SQL from markdown code blocks
        sql_patterns = [
            r'```sql\s*(SELECT[\s\S]*?)\s*```',  # Markdown SQL block
            r'```\s*(SELECT[\s\S]*?)\s*```',  # Generic code block
            r'(SELECT[\s\S]*?)(?:;|\n\n|\Z)',  # SELECT statement
        ]
        
        for pattern in sql_patterns:
            try:
                match = re.search(pattern, content_str, re.IGNORECASE | re.MULTILINE | re.DOTALL)
                if match:
                    sql = match.group(1).strip()
                    # Clean up
                    sql = sql.replace('```sql', '').replace('```', '').strip()
                    sql = sql.replace('\\n', '\n').replace('\\"', '"')
                    if sql:
                        return sql
            except Exception:
                continue
        
        # Try to find SQL query after common prefixes
        prefixes = ['SQL:', 'Query:', 'SELECT']
        for prefix in prefixes:
            try:
                idx = content_str.upper().find(prefix)
                if idx >= 0:
                    sql = content_str[idx:].split('\n')[0].strip()
                    if sql.upper().startswith('SELECT'):
                        return sql
            except Exception:
                continue
        
        # Last resort: return empty (will be handled by caller)
        if self.verbose:
            print(f"DEBUG: Could not extract SQL from: {content_str[:200]}")
        return ""
    
    def _is_safe_sql(self, sql: str) -> bool:
        """Check if SQL is safe (SELECT only)."""
        sql_clean = sql.strip().upper()
        # Remove comments
        sql_clean = re.sub(r'--.*$', '', sql_clean, flags=re.MULTILINE)
        sql_clean = re.sub(r'/\*.*?\*/', '', sql_clean, flags=re.DOTALL)
        sql_clean = sql_clean.strip()
        
        # Block data-changing statements
        forbidden = ['DELETE', 'UPDATE', 'INSERT', 'DROP', 'ALTER', 'CREATE', 'REPLACE', 'TRUNCATE']
        first_word = sql_clean.split()[0] if sql_clean.split() else ""
        return first_word not in forbidden
    
    def _execute_sql(self, sql: str) -> pd.DataFrame:
        """Execute SQL and return results as pandas DataFrame."""
        if not pd:
            raise RuntimeError("pandas is required for DataFrame results")
        
        if not self._is_safe_sql(sql):
            raise ValueError("Only SELECT queries are allowed")
        
        try:
            # Use SQLAlchemy engine directly to get structured results
            with self.engine.connect() as conn:
                df = pd.read_sql_query(sql, conn)
                return df
        except Exception as e:
            raise RuntimeError(f"SQL execution failed: {e}") from e
    
    def query(self, question: str) -> Dict[str, Any]:
        """
        Execute a natural language query (backward compatibility).
        Returns dict with answer, sql_query, and result.
        """
        try:
            result = self.query_to_dataframe(question)
            return {
                "answer": result.get("answer"),
                "sql_query": result.get("sql_query"),
                "result": result,
                "error": result.get("error")
            }
        except Exception as e:
            return {
                "answer": None,
                "sql_query": None,
                "result": None,
                "error": str(e)
            }
    
    def query_to_dataframe(self, question: str) -> Dict[str, Any]:
        """
        Execute a natural language query and return results as a pandas DataFrame.
        ALWAYS returns a DataFrame and SQL query.
        
        Args:
            question: Natural language question about the database
            
        Returns:
            Dictionary containing:
                - dataframe: pandas DataFrame with results (always structured)
                - sql_query: The SQL query that was executed (always provided)
                - answer: None (no narrative)
                - error: Error message if any
        """
        try:
            # Generate SQL
            try:
                sql_query = self._generate_sql(question)
            except Exception as e:
                error_msg = str(e)
                if self.verbose:
                    print(f"DEBUG: SQL generation exception: {error_msg}")
                return {
                    "dataframe": pd.DataFrame({'Error': [f'SQL generation failed: {error_msg}']}),
                    "sql_query": "",
                    "answer": None,
                    "error": error_msg
                }
            
            if not sql_query:
                return {
                    "dataframe": pd.DataFrame({'Error': ['Could not generate SQL query - empty response']}),
                    "sql_query": "",
                    "answer": None,
                    "error": "SQL generation returned empty result"
                }
            
            # Execute SQL to get DataFrame
            try:
                dataframe = self._execute_sql(sql_query)
                
                return {
                    "dataframe": dataframe,
                    "sql_query": sql_query,
                    "answer": None,
                    "error": None
                }
            except Exception as e:
                # Return error DataFrame with SQL query still available
                error_msg = str(e)
                if self.verbose:
                    print(f"DEBUG: SQL execution exception: {error_msg}")
                return {
                    "dataframe": pd.DataFrame({'Error': [f'SQL execution failed: {error_msg}']}),
                    "sql_query": sql_query,
                    "answer": None,
                    "error": error_msg
                }
                
        except Exception as e:
            error_msg = str(e)
            if self.verbose:
                print(f"DEBUG: Unexpected exception: {error_msg}")
            return {
                "dataframe": pd.DataFrame({'Error': [f'Unexpected error: {error_msg}']}),
                "sql_query": "",
                "answer": None,
                "error": error_msg
            }
    
    def get_table_info(self, table_name: Optional[str] = None) -> str:
        """
        Get information about database tables.
        
        Args:
            table_name: Specific table name, or None for all tables
            
        Returns:
            Formatted table information string
        """
        if table_name:
            return self.db.get_table_info_no_throw([table_name])
        else:
            return self.db.get_table_info_no_throw()
    
    def run_query(self, sql_query: str) -> List[Dict]:
        """
        Execute a raw SQL query directly.
        
        Args:
            sql_query: SQL query string
            
        Returns:
            List of dictionaries representing query results
        """
        try:
            result = self.db.run(sql_query)
            return result
        except Exception as e:
            raise RuntimeError(f"SQL query failed: {str(e)}") from e


def create_sql_agent(
    db_url: Optional[str] = None,
    api_key: Optional[str] = None,
    **kwargs
) -> LangChainSQLAgent:
    """
    Convenience function to create a LangChainSQLAgent instance.
    
    Args:
        db_url: Database connection URL
        api_key: XAI API key
        **kwargs: Additional arguments passed to LangChainSQLAgent
        
    Returns:
        LangChainSQLAgent instance
    """
    return LangChainSQLAgent(
        db_url=db_url,
        api_key=api_key,
        **kwargs
    )
