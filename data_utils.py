import re

def parse_struct_content(content):
    """
    Parses the inner content of a DuckDB STRUCT type string.
    Example: 'id VARCHAR, address STRUCT(city VARCHAR, zip INT)'
    Returns list of (name, type) tuples.
    """
    fields = []
    current_part = []
    balance = 0
    
    for char in content:
        if char == '(': balance += 1
        elif char == ')': balance -= 1
        
        if char == ',' and balance == 0:
            fields.append("".join(current_part).strip())
            current_part = []
        else:
            current_part.append(char)
    if current_part: fields.append("".join(current_part).strip())
        
    parsed = []
    for part in fields:
        match = re.match(r'^(".*?"|\S+)\s+(.+)$', part)
        if match:
            n = match.group(1).strip('"')
            t = match.group(2)
            parsed.append((n, t))
    return parsed

def recurse_struct(current_path, type_str):
    """
    Recursively generates SQL selection expressions for flattened columns.
    
    Args:
        current_path (list): List of path parts (e.g. ['address', 'city'])
        type_str (str): The DuckDB type string (e.g. 'STRUCT(num INT)')
        
    Returns:
        list: List of tuples (sql_expression, alias_name)
    """
    if type_str.startswith("STRUCT") and type_str.endswith(")"):
        inner = type_str[7:-1]
        fields = parse_struct_content(inner)
        results = []
        for name, t in fields:
            results.extend(recurse_struct(current_path + [name], t))
        return results
    else:
        # It's a leaf node (primitive type)
        # Construct path: "col"."subcol"
        expr_parts = [f'"{p}"' for p in current_path]
        expr = ".".join(expr_parts)
        
        # Construct alias: col.subcol
        alias = ".".join(current_path)
        
        return [(expr, alias)]

def generate_flattened_query(conn, source_view, target_view):
    """
    Generates and executes a query to create a flattened view from a source view.
    
    Args:
        conn: DuckDB connection
        source_view (str): Name of the source view/table (e.g. 'raw_data')
        target_view (str): Name of the target flattened view to create
        
    Returns:
        int: Total row count of the new view
    """
    try:
        schema = conn.execute(f"DESCRIBE {source_view}").fetchall()
        select_parts = []
        
        for col_name, col_type, _, _, _, _ in schema:
            if col_type.startswith("STRUCT"):
                cols = recurse_struct([col_name], col_type)
                for expr, alias in cols:
                    select_parts.append(f'{expr} AS "{alias}"')
            else:
                select_parts.append(f'"{col_name}" AS "{col_name}"')
        
        flat_query = f"CREATE OR REPLACE VIEW {target_view} AS SELECT {', '.join(select_parts)} FROM {source_view}"
        conn.execute(flat_query)
        
        # Get count
        count_res = conn.execute(f"SELECT COUNT(*) FROM {target_view}").fetchone()
        return count_res[0] if count_res else 0
        
    except Exception as e:
        # Fallback if flattening fails (e.g. strict SQL mode or weird types)
        # Just alias the original
        print(f"Flattening failed: {e}") 
        conn.execute(f"CREATE OR REPLACE VIEW {target_view} AS SELECT * FROM {source_view}")
        return 0
