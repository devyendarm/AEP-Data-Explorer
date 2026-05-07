import duckdb
import os
from logger import logger
import pandas as pd
import re
from data_utils import recurse_struct

class DataManager:
    """
    Manages data interaction using DuckDB for efficient querying of local Parquet files.
    Supports pagination and filtering without loading full dataset to RAM.
    """
    def __init__(self, data_dir):
        self.data_dir = data_dir
        self.db_path = data_dir # Expose for persistence
        self.conn = duckdb.connect(database=':memory:')
        self._initialize_view()

    def _initialize_view(self):
        """Creates a flattened DuckDB view over the parquet files."""
        try:
            # 1. Base View
            parquet_pattern = os.path.join(self.data_dir, "*.parquet")
            
            import glob
            if not glob.glob(parquet_pattern):
                raise IOError(f"No parquet files found in cache directory: {self.data_dir}")
                
            self.conn.execute(f"CREATE OR REPLACE VIEW raw_batch AS SELECT * FROM read_parquet('{parquet_pattern}')")
            
            # 2. Flattening Logic
            schema = self.conn.execute("DESCRIBE raw_batch").fetchall()
            select_parts = []
            
            for col_name, col_type, _, _, _, _ in schema:
                if col_type.startswith("STRUCT"):
                    cols = recurse_struct([col_name], col_type)
                    for expr, alias in cols:
                        select_parts.append(f'{expr} AS "{alias}"')
                else:
                    select_parts.append(f'"{col_name}" AS "{col_name}"')
            
            flat_query = f"CREATE OR REPLACE VIEW current_batch AS SELECT {', '.join(select_parts)} FROM raw_batch"
            self.conn.execute(flat_query)
            
            # Get total count
            count_res = self.conn.execute("SELECT COUNT(*) FROM current_batch").fetchone()
            self.total_rows = count_res[0] if count_res else 0
            logger.info(f"DataManager initialized (Flattened). Total rows: {self.total_rows}")
            
        except Exception as e:
            logger.error(f"Failed to initialize DuckDB view: {e}")
            self.total_rows = 0
            raise # Propagate up instead of letting it silently fail with a dead DataManager!

    def get_data(self, page=1, page_size=100, filters=None, sort_by=None, sort_asc=True, search_text=None):
        """
        Retrieves a page of data with optional filtering, sorting, and global search.
        """
        offset = (page - 1) * page_size
        
        query = "SELECT * FROM current_batch"
        where_clauses = []
        params = []
        
        # 1. Advanced Filters (Specific Columns)
        if filters:
            for col, criteria in filters.items():
                op = criteria.get('op')
                val = criteria.get('val')
                
                # Handle quoted columns for valid SQL
                quoted_col = f"\"{col}\""
                
                if op == "Contains":
                    where_clauses.append(f"contains({quoted_col}, ?)")
                    params.append(val)
                elif op == "Equals":
                    where_clauses.append(f"{quoted_col} = ?")
                    params.append(val)
                elif op == "Starts With":
                    where_clauses.append(f"starts_with({quoted_col}, ?)")
                    params.append(val)
                elif op == "Ends With":
                    where_clauses.append(f"ends_with({quoted_col}, ?)")
                    params.append(val)
        
        # 2. Global Search (All Columns)
        if search_text:
            cols = self.get_columns()
            search_clauses = []
            for col in cols:
                search_clauses.append(f"contains(CAST(\"{col}\" AS VARCHAR), ?)")
                params.append(search_text)
            
            if search_clauses:
                where_clauses.append(f"({' OR '.join(search_clauses)})")

        # Apply WHERE
        if where_clauses:
            query += " WHERE " + " AND ".join(where_clauses)
            
        # Get filtered count
        count_query = f"SELECT COUNT(*) FROM ({query})"
        try:
            filtered_count = self.conn.execute(count_query, params).fetchone()[0]
        except Exception as e:
            logger.error(f"Count query failed: {e}")
            filtered_count = 0
        
        # 3. Sorting
        if sort_by:
            direction = "ASC" if sort_asc else "DESC"
            query += f" ORDER BY \"{sort_by}\" {direction}"
        
        # 4. Pagination
        query += f" LIMIT {page_size} OFFSET {offset}"
        
        try:
            df = self.conn.execute(query, params).df()
            return df, filtered_count
        except Exception as e:
            logger.error(f"Query failed: {e}")
            return None, 0

    def get_columns(self):
        """Returns list of column names."""
        try:
            df = self.conn.execute("SELECT * FROM current_batch LIMIT 0").df()
            return df.columns.tolist()
        except:
            return []

    def export_to_file(self, file_path, filters=None, search_text=None):
        """
        Exports the full (optionally filtered) dataset to a file.
        """
        query = "SELECT * FROM current_batch"
        where_clauses = []
        params = []
        
        if filters:
            for col, criteria in filters.items():
                op = criteria.get('op')
                val = criteria.get('val')
                quoted_col = f"\"{col}\""
                if op == "Contains":
                    where_clauses.append(f"contains({quoted_col}, ?)")
                    params.append(val)
                elif op == "Equals":
                    where_clauses.append(f"{quoted_col} = ?")
                    params.append(val)
                elif op == "Starts With":
                    where_clauses.append(f"starts_with({quoted_col}, ?)")
                    params.append(val)
                elif op == "Ends With":
                    where_clauses.append(f"ends_with({quoted_col}, ?)")
                    params.append(val)
        
        if search_text:
            cols = self.get_columns()
            search_clauses = []
            for col in cols:
                search_clauses.append(f"contains(CAST(\"{col}\" AS VARCHAR), ?)")
                params.append(search_text)
            if search_clauses:
                where_clauses.append(f"({' OR '.join(search_clauses)})")
                
        if where_clauses:
            query += " WHERE " + " AND ".join(where_clauses)
            
        try:
            if file_path.lower().endswith('.csv'):
                self.conn.execute(f"CREATE OR REPLACE TEMP VIEW export_view AS {query}", params)
                self.conn.execute(f"COPY export_view TO '{file_path}' (HEADER, DELIMITER ',')")
                self.conn.execute("DROP VIEW export_view")
                
            elif file_path.lower().endswith('.parquet'):
                self.conn.execute(f"CREATE OR REPLACE TEMP VIEW export_view AS {query}", params)
                self.conn.execute(f"COPY export_view TO '{file_path}' (FORMAT PARQUET)")
                self.conn.execute("DROP VIEW export_view")
                
            elif file_path.lower().endswith('.xlsx'):
                df = self.conn.execute(query, params).df()
                for col in df.columns:
                    if pd.api.types.is_datetime64_any_dtype(df[col]):
                        df[col] = df[col].dt.tz_localize(None)
                df.to_excel(file_path, index=False)
                
            return True
        except Exception as e:
            logger.error(f"Export failed: {e}")
            raise
    
    def save_segment_results(self, segment_id, segment_name, data_df):
        """
        Save segment query results to a DuckDB table for local persistence.
        
        Args:
            segment_id: AEP segment ID
            segment_name: Human-readable segment name
            data_df: pandas DataFrame with segment member data
            
        Returns:
            str: Table name where data was saved
        """
        try:
            # Sanitize segment_id for table name (remove special chars)
            safe_id = re.sub(r'[^a-zA-Z0-9_]', '_', segment_id)
            table_name = f"segment_{safe_id}"
            
            # Drop existing table if it exists
            self.conn.execute(f"DROP TABLE IF EXISTS {table_name}")
            
            # Create table from DataFrame
            self.conn.execute(f"CREATE TABLE {table_name} AS SELECT * FROM data_df")
            
            # Store metadata
            metadata_table = "segment_metadata"
            self.conn.execute(f"""
                CREATE TABLE IF NOT EXISTS {metadata_table} (
                    segment_id VARCHAR,
                    segment_name VARCHAR,
                    table_name VARCHAR,
                    row_count INTEGER,
                    last_updated TIMESTAMP,
                    PRIMARY KEY (segment_id)
                )
            """)
            
            row_count = len(data_df)
            self.conn.execute(f"""
                INSERT OR REPLACE INTO {metadata_table} 
                VALUES (?, ?, ?, ?, CURRENT_TIMESTAMP)
            """, (segment_id, segment_name, table_name, row_count))
            
            logger.info(f"Saved {row_count} segment members to table: {table_name}")
            return table_name
            
        except Exception as e:
            logger.error(f"Failed to save segment results: {e}")
            raise
    
    def get_segment_tables(self):
        """
        Get list of all saved segment tables with metadata.
        
        Returns:
            List of dictionaries with segment metadata
        """
        try:
            result = self.conn.execute("""
                SELECT segment_id, segment_name, table_name, row_count, last_updated
                FROM segment_metadata
                ORDER BY last_updated DESC
            """).fetchall()
            
            return [
                {
                    "segment_id": row[0],
                    "segment_name": row[1],
                    "table_name": row[2],
                    "row_count": row[3],
                    "last_updated": row[4]
                }
                for row in result
            ]
        except Exception as e:
            logger.warning(f"No segment metadata found: {e}")
            return []
    
    def close(self):
        self.conn.close()
