"""
Data transformation tools.

Provides tools for converting between different data formats (JSON, CSV, etc.).
"""
import json
import csv
from typing import Dict, Any, List, Union
import io


def execute_json_to_csv(arguments: Dict[str, Any]) -> Dict[str, Any]:
    """
    Convert JSON data to CSV format.

    Args:
        arguments: Dictionary containing:
            - data: JSON data (string, dict, or list of dicts)
            - delimiter: CSV delimiter (optional, default ',')
            - include_headers: Whether to include headers (optional, default True)

    Returns:
        Dictionary with:
            - csv_data: CSV formatted string
            - rows_processed: Number of rows processed
            - columns: List of column names

    Raises:
        ValueError: If JSON data cannot be parsed or converted
    """
    data = arguments.get("data")
    delimiter = arguments.get("delimiter", ",")
    include_headers = arguments.get("include_headers", True)

    if not data:
        raise ValueError("No data provided for conversion")

    try:
        # Parse JSON data if it's a string
        if isinstance(data, str):
            parsed_data = json.loads(data)
        else:
            parsed_data = data

        # Handle different data structures
        if isinstance(parsed_data, dict):
            # Single object - convert to list with one item
            records = [parsed_data]
        elif isinstance(parsed_data, list):
            # List of objects or values
            records = parsed_data
        else:
            # Single value - convert to list
            records = [{"value": parsed_data}]

        if not records:
            raise ValueError("No records found in data")

        # Determine columns from first record
        if isinstance(records[0], dict):
            # List of objects - use keys as columns
            columns = list(records[0].keys())
            # Ensure all records have the same columns
            for record in records:
                if not isinstance(record, dict):
                    raise ValueError("All records must be objects for CSV conversion")
                # Add missing columns with empty values
                for col in columns:
                    if col not in record:
                        record[col] = ""
            rows = records
        else:
            # List of values - use generic column names
            columns = ["value"]
            rows = [{"value": record} for record in records]

        # Convert to CSV
        output = io.StringIO()
        writer = csv.writer(output, delimiter=delimiter)

        # Write headers if requested
        if include_headers:
            writer.writerow(columns)

        # Write data rows
        for row in rows:
            writer.writerow([row.get(col, "") for col in columns])

        csv_data = output.getvalue()
        output.close()

        return {
            "csv_data": csv_data,
            "rows_processed": len(rows),
            "columns": columns,
            "delimiter": delimiter
        }

    except json.JSONDecodeError as e:
        raise ValueError(f"Invalid JSON data: {str(e)}")
    except Exception as e:
        raise ValueError(f"Error converting to CSV: {str(e)}")


def execute_csv_to_json(arguments: Dict[str, Any]) -> Dict[str, Any]:
    """
    Convert CSV data to JSON format.

    Args:
        arguments: Dictionary containing:
            - csv_data: CSV formatted string
            - delimiter: CSV delimiter (optional, auto-detected if not provided)
            - has_headers: Whether CSV has headers (optional, default True)
            - output_format: Output format - 'records' or 'values' (optional, default 'records')

    Returns:
        Dictionary with:
            - json_data: JSON formatted string
            - records: List of parsed records
            - columns: List of column names (if has_headers=True)

    Raises:
        ValueError: If CSV data cannot be parsed
    """
    csv_data = arguments.get("csv_data", "")
    delimiter = arguments.get("delimiter")
    has_headers = arguments.get("has_headers", True)
    output_format = arguments.get("output_format", "records")

    if not csv_data:
        raise ValueError("No CSV data provided for conversion")

    try:
        # Auto-detect delimiter if not provided
        if not delimiter:
            delimiter = _detect_csv_delimiter(csv_data)

        # Parse CSV
        input_io = io.StringIO(csv_data)
        reader = csv.reader(input_io, delimiter=delimiter)

        rows = list(reader)
        input_io.close()

        if not rows:
            raise ValueError("No data found in CSV")

        columns = None
        data_rows = rows

        if has_headers and len(rows) > 1:
            columns = rows[0]
            data_rows = rows[1:]
        elif has_headers and len(rows) == 1:
            # Only headers, no data
            return {
                "json_data": "[]",
                "records": [],
                "columns": rows[0] if rows else [],
                "delimiter": delimiter
            }

        # Convert to requested format
        if output_format == "records":
            # List of objects
            records = []
            for row in data_rows:
                if columns:
                    record = dict(zip(columns, row))
                else:
                    record = row
                records.append(record)
        elif output_format == "values":
            # List of values
            records = data_rows
        else:
            raise ValueError(f"Invalid output_format: {output_format}")

        # Convert to JSON string
        json_data = json.dumps(records, indent=2)

        return {
            "json_data": json_data,
            "records": records,
            "columns": columns or [],
            "delimiter": delimiter,
            "rows_processed": len(data_rows)
        }

    except Exception as e:
        raise ValueError(f"Error converting CSV to JSON: {str(e)}")


def execute_flatten_json(arguments: Dict[str, Any]) -> Dict[str, Any]:
    """
    Flatten nested JSON structure.

    Args:
        arguments: Dictionary containing:
            - data: JSON data (string, dict, or list)
            - separator: Key separator (optional, default '.')
            - max_depth: Maximum depth to flatten (optional, unlimited if not specified)

    Returns:
        Dictionary with:
            - flattened_data: Flattened JSON structure
            - original_depth: Maximum depth of original structure
            - keys_processed: Number of keys processed

    Raises:
        ValueError: If JSON data cannot be parsed
    """
    data = arguments.get("data")
    separator = arguments.get("separator", ".")
    max_depth = arguments.get("max_depth", None)

    if data is None:
        raise ValueError("No data provided")

    try:
        # Parse JSON if it's a string
        if isinstance(data, str):
            parsed_data = json.loads(data)
        else:
            parsed_data = data

        # Flatten the structure
        flattened = _flatten_dict(parsed_data, separator=separator, max_depth=max_depth)

        # Calculate metrics
        original_depth = _calculate_depth(parsed_data)
        keys_processed = len(flattened)

        return {
            "flattened_data": flattened,
            "original_depth": original_depth,
            "keys_processed": keys_processed,
            "separator": separator
        }

    except json.JSONDecodeError as e:
        raise ValueError(f"Invalid JSON data: {str(e)}")
    except Exception as e:
        raise ValueError(f"Error flattening JSON: {str(e)}")


def execute_nest_json(arguments: Dict[str, Any]) -> Dict[str, Any]:
    """
    Nest flattened JSON structure.

    Args:
        arguments: Dictionary containing:
            - data: Flattened JSON data (dict with dot-separated keys)
            - separator: Key separator used in flattened keys (optional, default '.')

    Returns:
        Dictionary with:
            - nested_data: Nested JSON structure
            - keys_processed: Number of keys processed

    Raises:
        ValueError: If data cannot be nested
    """
    data = arguments.get("data")
    separator = arguments.get("separator", ".")

    if not isinstance(data, dict):
        raise ValueError("Data must be a dictionary for nesting")

    try:
        # Parse JSON if it's a string
        if isinstance(data, str):
            parsed_data = json.loads(data)
        else:
            parsed_data = data

        # Nest the structure
        nested = _nest_dict(parsed_data, separator=separator)

        return {
            "nested_data": nested,
            "keys_processed": len(parsed_data),
            "separator": separator
        }

    except json.JSONDecodeError as e:
        raise ValueError(f"Invalid JSON data: {str(e)}")
    except Exception as e:
        raise ValueError(f"Error nesting JSON: {str(e)}")


# Helper functions
def _detect_csv_delimiter(csv_data: str) -> str:
    """Auto-detect CSV delimiter."""
    delimiters = [",", ";", "\t", "|"]
    counts = {}

    for delim in delimiters:
        # Count occurrences in first few lines
        sample = "\n".join(csv_data.split("\n")[:5])
        counts[delim] = sample.count(delim)

    # Return delimiter with highest count
    return max(counts, key=counts.get) or ","


def _flatten_dict(data: Any, parent_key: str = "", separator: str = ".", max_depth: int = None, current_depth: int = 0) -> Dict[str, Any]:
    """Recursively flatten a dictionary."""
    items = []

    if max_depth is not None and current_depth >= max_depth:
        return {parent_key: data} if parent_key else data

    if isinstance(data, dict):
        for key, value in data.items():
            new_key = f"{parent_key}{separator}{key}" if parent_key else key
            if isinstance(value, (dict, list)):
                items.extend(_flatten_dict(value, new_key, separator, max_depth, current_depth + 1).items())
            else:
                items.append((new_key, value))
    elif isinstance(data, list):
        for i, value in enumerate(data):
            new_key = f"{parent_key}{separator}{i}" if parent_key else str(i)
            if isinstance(value, (dict, list)):
                items.extend(_flatten_dict(value, new_key, separator, max_depth, current_depth + 1).items())
            else:
                items.append((new_key, value))
    else:
        items.append((parent_key, data))

    return dict(items)


def _calculate_depth(data: Any, current_depth: int = 0) -> int:
    """Calculate maximum depth of nested structure."""
    if isinstance(data, dict):
        if not data:
            return current_depth
        return max(_calculate_depth(value, current_depth + 1) for value in data.values())
    elif isinstance(data, list):
        if not data:
            return current_depth
        return max(_calculate_depth(value, current_depth + 1) for value in data)
    else:
        return current_depth


def _nest_dict(flat_dict: Dict[str, Any], separator: str = ".") -> Dict[str, Any]:
    """Convert flat dictionary with separator keys to nested dictionary."""
    result = {}

    for flat_key, value in flat_dict.items():
        keys = flat_key.split(separator)
        current = result

        # Navigate to the correct nested location
        for key in keys[:-1]:
            if key not in current:
                current[key] = {}
            current = current[key]

        # Set the final value
        current[keys[-1]] = value

    return result


# Tool metadata for each data transformation operation
DATA_TRANSFORM_TOOLS = [
    {
        "name": "json_to_csv",
        "description": "Convert JSON data to CSV format",
        "category": "data_transform",
        "tags": ["json", "csv", "convert", "data", "export"],
        "input_schema": {
            "type": "object",
            "properties": {
                "data": {
                    "type": ["string", "object", "array"],
                    "description": "JSON data to convert to CSV (string, object, or array of objects)"
                },
                "delimiter": {
                    "type": "string",
                    "description": "CSV delimiter character",
                    "default": ","
                },
                "include_headers": {
                    "type": "boolean",
                    "description": "Whether to include column headers in CSV",
                    "default": True
                }
            },
            "required": ["data"]
        },
        "output_schema": {
            "type": "object",
            "properties": {
                "csv_data": {
                    "type": "string",
                    "description": "CSV formatted data"
                },
                "rows_processed": {
                    "type": "integer",
                    "description": "Number of rows converted"
                },
                "columns": {
                    "type": "array",
                    "items": {"type": "string"},
                    "description": "List of column names"
                },
                "delimiter": {
                    "type": "string",
                    "description": "Delimiter used in CSV"
                }
            }
        },
        "implementation_type": "python_function",
        "implementation_code": "app.tools.implementations.data_transform.execute_json_to_csv",
        "version": "1.0.0",
    },
    {
        "name": "csv_to_json",
        "description": "Convert CSV data to JSON format",
        "category": "data_transform",
        "tags": ["csv", "json", "convert", "data", "import"],
        "input_schema": {
            "type": "object",
            "properties": {
                "csv_data": {
                    "type": "string",
                    "description": "CSV data to convert to JSON"
                },
                "delimiter": {
                    "type": "string",
                    "description": "CSV delimiter character (auto-detected if not provided)"
                },
                "has_headers": {
                    "type": "boolean",
                    "description": "Whether CSV has a header row",
                    "default": True
                },
                "output_format": {
                    "type": "string",
                    "enum": ["records", "values"],
                    "description": "Output format: 'records' for objects, 'values' for arrays",
                    "default": "records"
                }
            },
            "required": ["csv_data"]
        },
        "output_schema": {
            "type": "object",
            "properties": {
                "json_data": {
                    "type": "string",
                    "description": "JSON formatted data"
                },
                "records": {
                    "type": "array",
                    "description": "Parsed records as Python objects"
                },
                "columns": {
                    "type": "array",
                    "items": {"type": "string"},
                    "description": "List of column names (if headers present)"
                },
                "delimiter": {
                    "type": "string",
                    "description": "Delimiter detected/used in CSV"
                },
                "rows_processed": {
                    "type": "integer",
                    "description": "Number of data rows processed"
                }
            }
        },
        "implementation_type": "python_function",
        "implementation_code": "app.tools.implementations.data_transform.execute_csv_to_json",
        "version": "1.0.0",
    },
    {
        "name": "flatten_json",
        "description": "Flatten nested JSON structure to flat key-value pairs",
        "category": "data_transform",
        "tags": ["json", "flatten", "data", "structure"],
        "input_schema": {
            "type": "object",
            "properties": {
                "data": {
                    "type": ["string", "object", "array"],
                    "description": "JSON data to flatten"
                },
                "separator": {
                    "type": "string",
                    "description": "Separator for nested keys",
                    "default": "."
                },
                "max_depth": {
                    "type": "integer",
                    "description": "Maximum depth to flatten (unlimited if not specified)"
                }
            },
            "required": ["data"]
        },
        "output_schema": {
            "type": "object",
            "properties": {
                "flattened_data": {
                    "type": "object",
                    "description": "Flattened key-value pairs"
                },
                "original_depth": {
                    "type": "integer",
                    "description": "Maximum depth of original structure"
                },
                "keys_processed": {
                    "type": "integer",
                    "description": "Number of keys in flattened result"
                },
                "separator": {
                    "type": "string",
                    "description": "Separator used for flattening"
                }
            }
        },
        "implementation_type": "python_function",
        "implementation_code": "app.tools.implementations.data_transform.execute_flatten_json",
        "version": "1.0.0",
    },
    {
        "name": "nest_json",
        "description": "Convert flattened JSON structure back to nested format",
        "category": "data_transform",
        "tags": ["json", "nest", "data", "structure"],
        "input_schema": {
            "type": "object",
            "properties": {
                "data": {
                    "type": ["object", "string"],
                    "description": "Flattened JSON data with separator-separated keys"
                },
                "separator": {
                    "type": "string",
                    "description": "Separator used in flattened keys",
                    "default": "."
                }
            },
            "required": ["data"]
        },
        "output_schema": {
            "type": "object",
            "properties": {
                "nested_data": {
                    "type": "object",
                    "description": "Nested JSON structure"
                },
                "keys_processed": {
                    "type": "integer",
                    "description": "Number of keys processed"
                },
                "separator": {
                    "type": "string",
                    "description": "Separator used for nesting"
                }
            }
        },
        "implementation_type": "python_function",
        "implementation_code": "app.tools.implementations.data_transform.execute_nest_json",
        "version": "1.0.0",
    },
]