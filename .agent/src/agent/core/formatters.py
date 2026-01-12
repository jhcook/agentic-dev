"""
Output formatters for agent CLI commands.

This module provides utilities to format data in various output formats
including JSON, CSV, YAML, Markdown, plain text, and TSV.
"""

import json
import csv
import yaml
from io import StringIO
from typing import Any, List, Dict


def format_data(format_name: str, data: List[Dict[str, Any]]) -> str:
    """
    Route data to the appropriate formatter based on format name.
    
    Args:
        format_name: The output format (json, csv, yaml, markdown, plain, tsv, pretty)
        data: List of dictionaries to format
        
    Returns:
        Formatted string output
        
    Raises:
        ValueError: If format_name is not supported
    """
    formatters = {
        "json": format_json,
        "csv": format_csv,
        "yaml": format_yaml,
        "markdown": format_markdown,
        "plain": format_plain,
        "tsv": format_tsv,
        "pretty": format_pretty,
    }
    
    formatter = formatters.get(format_name.lower())
    if not formatter:
        valid_formats = ", ".join(formatters.keys())
        raise ValueError(
            f"Unsupported format: {format_name}. "
            f"Valid formats are: {valid_formats}"
        )
    
    return formatter(data)


def format_json(data: List[Dict[str, Any]]) -> str:
    """Format data as JSON."""
    return json.dumps(data, indent=2, ensure_ascii=False)


def format_csv(data: List[Dict[str, Any]]) -> str:
    """
    Format data as CSV with proper escaping to prevent CSV injection.
    
    Fields starting with special characters (=, +, -, @) are prefixed
    with a single quote to prevent formula injection in spreadsheet software.
    """
    if not data:
        return ""
    
    output = StringIO()
    fieldnames = list(data[0].keys()) if data else []
    writer = csv.DictWriter(output, fieldnames=fieldnames)
    
    writer.writeheader()
    
    # Sanitize data to prevent CSV injection
    sanitized_data = []
    for row in data:
        sanitized_row = {}
        for key, value in row.items():
            str_value = str(value)
            # Prevent CSV injection by escaping formula characters
            if str_value and str_value[0] in ('=', '+', '-', '@'):
                str_value = "'" + str_value
            sanitized_row[key] = str_value
        sanitized_data.append(sanitized_row)
    
    writer.writerows(sanitized_data)
    return output.getvalue()


def format_yaml(data: List[Dict[str, Any]]) -> str:
    """Format data as YAML."""
    return yaml.dump(data, default_flow_style=False, allow_unicode=True, sort_keys=False)


def format_markdown(data: List[Dict[str, Any]]) -> str:
    """Format data as a Markdown table."""
    if not data:
        return ""
    
    fieldnames = list(data[0].keys())
    
    # Header
    lines = []
    lines.append("| " + " | ".join(fieldnames) + " |")
    lines.append("| " + " | ".join(["---"] * len(fieldnames)) + " |")
    
    # Rows
    for row in data:
        values = [str(row.get(field, "")) for field in fieldnames]
        # Escape pipe characters in values
        values = [v.replace("|", "\\|") for v in values]
        lines.append("| " + " | ".join(values) + " |")
    
    return "\n".join(lines)


def format_plain(data: List[Dict[str, Any]]) -> str:
    """Format data as plain text with tab-separated columns."""
    if not data:
        return ""
    
    fieldnames = list(data[0].keys())
    
    lines = []
    # Header
    lines.append("\t".join(fieldnames))
    
    # Rows
    for row in data:
        values = [str(row.get(field, "")) for field in fieldnames]
        lines.append("\t".join(values))
    
    return "\n".join(lines)


def format_tsv(data: List[Dict[str, Any]]) -> str:
    """
    Format data as TSV (Tab-Separated Values) with proper escaping.
    
    Similar to CSV but uses tabs as delimiters. Also prevents injection.
    """
    if not data:
        return ""
    
    output = StringIO()
    fieldnames = list(data[0].keys()) if data else []
    writer = csv.DictWriter(output, fieldnames=fieldnames, delimiter='\t')
    
    writer.writeheader()
    
    # Sanitize data to prevent TSV injection
    sanitized_data = []
    for row in data:
        sanitized_row = {}
        for key, value in row.items():
            str_value = str(value)
            # Prevent injection by escaping formula characters
            if str_value and str_value[0] in ('=', '+', '-', '@'):
                str_value = "'" + str_value
            sanitized_row[key] = str_value
        sanitized_data.append(sanitized_row)
    
    writer.writerows(sanitized_data)
    return output.getvalue()


def format_pretty(data: List[Dict[str, Any]]) -> str:
    """
    Format data as a Rich table (pretty print).
    
    Note: This returns the table markup as a string. For live rendering,
    use console.print(table) directly in the command.
    """
    if not data:
        return "(No data)"
    
    # For pretty format, we'll return JSON as a fallback
    # The actual Rich table rendering should be done in the command
    return json.dumps(data, indent=2, ensure_ascii=False)
