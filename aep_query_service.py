"""
AEP Query Service Module

Provides PostgreSQL-based connectivity to Adobe Experience Platform Query Service
for scalable querying of datasets, including segment membership data.
"""

import psycopg2
import psycopg2.extras
import logging
from typing import List, Dict, Any, Optional, Tuple

logger = logging.getLogger(__name__)


class AEPQueryService:
    """
    Adobe Experience Platform Query Service client using PostgreSQL protocol.
    
    Enables direct SQL queries to AEP datasets via PostgreSQL connection,
    supporting segment member exports, dataset inspection, and CTAS operations.
    """
    
    def __init__(self, host: str, port: int, database: str, username: str, password: str):
        """
        Initialize Query Service connection parameters.
        
        Args:
            host: Query Service host (e.g., {ORG_ID}.platform-query.adobe.io)
            port: Connection port (typically 80)
            database: Database name (typically prod:all)
            username: Technical account username
            password: Query Service password
        """
        self.host = host
        self.port = port
        self.database = database
        self.username = username
        self.password = password
        self.connection = None
        
    def connect(self) -> bool:
        """
        Establish PostgreSQL connection to Query Service.
        
        Returns:
            bool: True if connection successful, False otherwise
        """
        try:
            self.connection = psycopg2.connect(
                host=self.host,
                port=self.port,
                database=self.database,
                user=self.username,
                password=self.password,
                sslmode='require',
                connect_timeout=30
            )
            logger.info(f"Connected to Query Service: {self.host}")
            return True
        except Exception as e:
            logger.error(f"Failed to connect to Query Service: {e}")
            return False
    
    def disconnect(self):
        """Close the PostgreSQL connection."""
        if self.connection:
            self.connection.close()
            self.connection = None
            logger.info("Disconnected from Query Service")
    
    def execute_query(self, sql: str, params: Optional[Tuple] = None) -> List[Dict[str, Any]]:
        """
        Execute SQL query and return results as list of dictionaries.
        
        Args:
            sql: SQL query string
            params: Optional query parameters for parameterized queries
            
        Returns:
            List of dictionaries representing query results
            
        Raises:
            Exception: If query execution fails
        """
        if not self.connection:
            raise Exception("Not connected to Query Service. Call connect() first.")
        
        try:
            cursor = self.connection.cursor(cursor_factory=psycopg2.extras.RealDictCursor)
            logger.info("Sending query to AEP (this may take time)...")
            cursor.execute(sql, params)
            logger.info("Query execution finished, fetching results...")
            
            # Check if query returns results
            if cursor.description:
                results = cursor.fetchall()
                # Convert RealDictRow to regular dict
                return [dict(row) for row in results]
            else:
                # DDL/DML query (no results)
                self.connection.commit()
                return []
                
        except Exception as e:
            logger.error(f"Query execution failed: {e}")
            logger.error(f"SQL: {sql}")
            raise
        finally:
            cursor.close()
    
    def list_datasets(self) -> List[Dict[str, str]]:
        """
        List available datasets in Query Service.
        
        Returns:
            List of dictionaries with dataset information (name, schema, type)
        """
        sql = """
            SELECT 
                table_schema,
                table_name,
                table_type
            FROM information_schema.tables
            WHERE table_schema NOT IN ('information_schema', 'pg_catalog')
            ORDER BY table_schema, table_name
        """
        return self.execute_query(sql)
    
    def get_dataset_schema(self, dataset_name: str) -> List[Dict[str, str]]:
        """
        Get schema information for a specific dataset.
        
        Args:
            dataset_name: Name of the dataset
            
        Returns:
            List of dictionaries with column information (name, type, nullable)
        """
        sql = """
            SELECT 
                column_name,
                data_type,
                is_nullable
            FROM information_schema.columns
            WHERE table_name = %s
            ORDER BY ordinal_position
        """
        return self.execute_query(sql, (dataset_name,))
    
    def get_segment_members(
        self,
        dataset_name: str,
        segment_id: str,
        limit: int = 1000,
        offset: int = 0,
        fields: Optional[List[str]] = None
    ) -> List[Dict[str, Any]]:
        """
        Query profiles that are members of a specific segment.
        
        Args:
            dataset_name: Name of the profile dataset to query
            segment_id: AEP segment ID
            limit: Maximum number of results to return
            offset: Number of results to skip (for pagination)
            fields: Optional list of fields to select (defaults to all)
            
        Returns:
            List of profile dictionaries
        """
        # Build field list
        if fields:
            field_list = ", ".join(fields)
        else:
            field_list = "*"
        
        sql = f"""
            SELECT {field_list}
            FROM {dataset_name}
            WHERE segmentMembership.ups['{segment_id}'].status = 'realized'
            LIMIT %s OFFSET %s
        """
        
        return self.execute_query(sql, (limit, offset))
    
    def get_segment_member_count(self, dataset_name: str, segment_id: str) -> int:
        """
        Get the total count of profiles in a segment.
        
        Args:
            dataset_name: Name of the profile dataset to query
            segment_id: AEP segment ID
            
        Returns:
            Total count of segment members
        """
        sql = f"""
            SELECT COUNT(*) as count
            FROM {dataset_name}
            WHERE segmentMembership.ups['{segment_id}'].status = 'realized'
        """
        
        result = self.execute_query(sql)
        return result[0]['count'] if result else 0
    
    def create_segment_export(
        self,
        source_dataset: str,
        segment_id: str,
        output_dataset: str
    ) -> str:
        """
        Create a new dataset with segment members using CTAS (Create Table As Select).
        
        This is useful for large segment exports that would be slow to query repeatedly.
        
        Args:
            source_dataset: Source profile dataset name
            segment_id: AEP segment ID
            output_dataset: Name for the output dataset
            
        Returns:
            Success message
            
        Raises:
            Exception: If CTAS fails
        """
        sql = f"""
            CREATE TABLE {output_dataset} AS
            SELECT *
            FROM {source_dataset}
            WHERE segmentMembership.ups['{segment_id}'].status = 'realized'
        """
        
        self.execute_query(sql)
        logger.info(f"Created segment export dataset: {output_dataset}")
        return f"Successfully created dataset: {output_dataset}"
    
    def test_connection(self) -> Tuple[bool, str]:
        """
        Test the Query Service connection.
        
        Returns:
            Tuple of (success: bool, message: str)
        """
        try:
            if not self.connection:
                if not self.connect():
                    return False, "Failed to establish connection"
            
            # Simple test query
            result = self.execute_query("SELECT 1 as test")
            if result and result[0]['test'] == 1:
                return True, "Connection successful"
            else:
                return False, "Unexpected query result"
                
        except Exception as e:
            return False, f"Connection test failed: {str(e)}"
    
    def __enter__(self):
        """Context manager entry - establish connection."""
        self.connect()
        return self
    
    def __exit__(self, exc_type, exc_val, exc_tb):
        """Context manager exit - close connection."""
        self.disconnect()
