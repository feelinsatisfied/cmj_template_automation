#!/usr/bin/env python3
"""
Convert Source/Target Data to XLSX

Converts RTF/JSON API data exports to a single xlsx file with tabs for each data type.
This provides an audit trail and easier data validation.

Usage:
    python3 convert_data_to_xlsx.py --source      # Convert source API data
    python3 convert_data_to_xlsx.py --target-pre  # Convert target pre-import data
    python3 convert_data_to_xlsx.py --target-post # Convert target post-import data
    python3 convert_data_to_xlsx.py --all         # Convert all data files

Output:
    source_data/source_api_full/source_data_converted.xlsx
    target_data/target_data_pre_import_converted.xlsx
    target_data/post_import/target_data_post_import_converted.xlsx
"""

import pandas as pd
import json
import subprocess
import tempfile
import argparse
import re
from pathlib import Path
from datetime import datetime


# Base paths (relative to script location: scripts/ -> cmj_template/)
BASE_DIR = Path(__file__).resolve().parent.parent
SOURCE_DIR = BASE_DIR / 'source_data' / 'source_api_full'
TARGET_PRE_DIR = BASE_DIR / 'target_data' / 'pre_import'
TARGET_POST_DIR = BASE_DIR / 'target_data' / 'post_import'


def extract_text_from_file(file_path):
    """Extract plain text from RTF or TXT file.

    For RTF files, uses macOS textutil to convert.
    For TXT files, reads directly.
    """
    file_path = Path(file_path)

    if not file_path.exists():
        print(f"  ⚠ File not found: {file_path}")
        return None

    # For .txt files, just read directly
    if file_path.suffix.lower() == '.txt':
        try:
            with open(file_path, 'r', encoding='utf-8') as f:
                return f.read()
        except Exception as e:
            print(f"  ⚠ Error reading TXT: {e}")
            return None

    # For .rtf files, use textutil to convert
    with tempfile.NamedTemporaryFile(mode='w', suffix='.txt', delete=False) as tmp:
        txt_path = tmp.name

    try:
        subprocess.run([
            'textutil', '-convert', 'txt', '-output', txt_path, str(file_path)
        ], check=True, capture_output=True)

        with open(txt_path, 'r', encoding='utf-8') as f:
            content = f.read()

        return content
    except subprocess.CalledProcessError as e:
        print(f"  ⚠ Error converting RTF: {e}")
        return None
    finally:
        if Path(txt_path).exists():
            Path(txt_path).unlink()


def extract_text_from_rtf(rtf_path):
    """Legacy wrapper for extract_text_from_file."""
    return extract_text_from_file(rtf_path)


def find_source_file(directory, keyword):
    """Find a source API file by keyword, supporting multiple naming conventions.

    Supports:
      - *_{keyword}_api.rtf/.txt  (e.g., PROJECT_field_api.rtf)
      - source_{keyword}_pre-import.rtf/.txt  (e.g., source_field_pre-import.rtf)
    """
    directory = Path(directory)

    for ext in ['*.rtf', '*.txt']:
        for f in directory.glob(ext):
            name_lower = f.name.lower()
            if keyword not in name_lower:
                continue
            # Match *_{keyword}_api.* or source_{keyword}_pre-import.*
            if 'api' in name_lower or ('source' in name_lower and 'pre-import' in name_lower):
                return f

    return None


def parse_json_content(content, data_key=None):
    """Parse JSON content from text.

    Args:
        content: Raw text content
        data_key: Optional key to extract data from wrapper object (e.g., 'issueLinkTypes')
    """
    try:
        data = json.loads(content)

        # Handle wrapper objects like {"issueLinkTypes": [...]}
        if data_key and isinstance(data, dict) and data_key in data:
            return data[data_key]

        # Auto-detect wrapper if data is a dict with single array value
        if isinstance(data, dict) and len(data) == 1:
            key = list(data.keys())[0]
            if isinstance(data[key], list):
                return data[key]

        return data
    except json.JSONDecodeError:
        return None


def parse_csv_content(content):
    """Parse CSV-like content from target data exports.

    Handles formats like:
    "ID","Name"
    "10001","Status Name"

    Or single-line format where records are separated by spaces:
    Target ID,Target Name,Field Type "10000","Development","type1" "10001","Name2","type2"
    """
    if not content:
        return []

    data = []

    # First try to detect if there's a header line
    # Check if content starts with column names (not quoted)
    header_match = re.match(r'^([A-Za-z][A-Za-z\s,]+?)(?:\s*")', content)
    if header_match:
        # Skip the header part - we'll infer structure from data
        content = content[header_match.end()-1:]  # Keep the first quote

    # Find all quoted record patterns
    # Pattern: "value1","value2" or "value1","value2","value3"
    # Records are separated by spaces or the closing quote of one and opening quote of next

    # Split by pattern of '" "' which separates records
    # First, normalize the content - replace '" "' with a delimiter
    normalized = re.sub(r'"\s+"', '"|"', content)

    # Split on the delimiter to get individual records
    record_strings = normalized.split('|')

    for record_str in record_strings:
        # Extract quoted values from each record
        matches = re.findall(r'"([^"]*)"', record_str)
        if matches and len(matches) >= 2:  # Need at least ID and Name
            data.append(matches)

    return data


def parse_consolidated_export(file_path):
    """Parse the consolidated target export file (target_all_objects.txt).

    This file contains all 5 object types in a single file with section markers:
    ###SECTION:STATUSES###
    Target ID,Target Name
    "10001","Status Name"
    ###END:STATUSES###

    Also handles single-line format where records are space-separated:
    "10001","Status1" "10002","Status2"

    Properly handles CSV-escaped quotes (e.g., field names containing quotes like
    "Other" become ""Other"" in CSV format).

    Returns a dict mapping sheet_name -> list of records
    """
    import csv
    import io

    file_path = Path(file_path)
    if not file_path.exists():
        return None

    try:
        with open(file_path, 'r', encoding='utf-8') as f:
            content = f.read()
    except Exception as e:
        print(f"  ⚠ Error reading consolidated export: {e}")
        return None

    # Section name to sheet name mapping and expected column counts
    section_map = {
        'STATUSES': ('Statuses', 2),
        'RESOLUTIONS': ('Resolutions', 2),
        'CUSTOMFIELDS': ('CustomFields', 3),
        'ISSUETYPES': ('IssueTypes', 3),
        'ISSUELINKTYPES': ('IssueLinkTypes', 4)
    }

    result = {}

    for section_key, (sheet_name, col_count) in section_map.items():
        # Find section content between markers
        pattern = rf'###SECTION:{section_key}###\s*(.*?)\s*###END:{section_key}###'
        match = re.search(pattern, content, re.DOTALL)

        if not match:
            continue

        section_content = match.group(1).strip()

        # Skip the header line (Target ID,Target Name,...)
        # Header ends at first quote
        header_end = section_content.find('"')
        if header_end > 0:
            section_content = section_content[header_end:]

        # Parse using CSV reader which properly handles escaped quotes
        # First, try to parse if content has newlines (proper CSV)
        records = []

        if '\n' in section_content or '\r' in section_content:
            # Content has newlines - parse line by line
            try:
                reader = csv.reader(io.StringIO(section_content))
                for row in reader:
                    if len(row) >= 2 and row[0].strip():
                        records.append(row[:col_count] if len(row) >= col_count else row)
            except csv.Error:
                pass

        # If no records from line-by-line, try single-line parsing
        if not records:
            # For single-line format, we need a smarter approach
            # Find records by looking for patterns that start with numeric ID
            # Pattern: "ID","Name",... where ID is numeric
            record_pattern = rf'"(\d+)"((?:,"[^"]*(?:""[^"]*)*")*)'
            if col_count == 2:
                record_pattern = r'"(\d+)","([^"]*(?:""[^"]*)*)"'
            elif col_count == 3:
                record_pattern = r'"(\d+)","([^"]*(?:""[^"]*)*?)","([^"]*(?:""[^"]*)*)"'
            elif col_count == 4:
                record_pattern = r'"(\d+)","([^"]*(?:""[^"]*)*?)","([^"]*(?:""[^"]*)*?)","([^"]*(?:""[^"]*)*)"'

            matches = re.findall(record_pattern, section_content)
            for match_tuple in matches:
                # Unescape doubled quotes
                record = [v.replace('""', '"') for v in match_tuple]
                if len(record) >= 2:
                    records.append(record)

        if records:
            result[sheet_name] = records
            print(f"    Parsed {sheet_name}: {len(records)} records")

    return result if result else None


def convert_consolidated_to_df(records, sheet_name):
    """Convert consolidated export records to DataFrame."""
    if not records:
        return None

    rows = []
    for record in records:
        if sheet_name == 'CustomFields' and len(record) >= 3:
            rows.append({
                'Target ID': record[0],
                'Target Name': record[1],
                'Field Type': record[2]
            })
        elif sheet_name == 'IssueTypes' and len(record) >= 3:
            rows.append({
                'Target ID': record[0],
                'Target Name': record[1],
                'Is SubTask': record[2]
            })
        elif sheet_name == 'IssueLinkTypes' and len(record) >= 4:
            rows.append({
                'Target ID': record[0],
                'Target Name': record[1],
                'Inward': record[2],
                'Outward': record[3]
            })
        elif len(record) >= 2:
            # Statuses, Resolutions
            rows.append({
                'Target ID': record[0],
                'Target Name': record[1]
            })

    return pd.DataFrame(rows) if rows else None


def convert_source_data():
    """Convert source API RTF/TXT files to xlsx."""
    print("\n" + "=" * 80)
    print("CONVERTING SOURCE API DATA TO XLSX")
    print("=" * 80)

    output_file = SOURCE_DIR / 'source_data_converted.xlsx'
    sheets = {}

    # Define file mappings: (keyword, sheet_name, field_extractors)
    # Files are auto-detected by keyword pattern (e.g., *_field_api.rtf or *_field_api.txt)
    file_mappings = [
        ('field', 'CustomFields',
         lambda item: {
             'Source ID': item.get('id', '').replace('customfield_', ''),
             'Source Name': item.get('name', ''),
             'Source Type': item.get('schema', {}).get('custom', ''),
             'Description': item.get('description', ''),
             'Searchable': item.get('searchable', ''),
             'Schema Type': item.get('schema', {}).get('type', '')
         }),
        ('status', 'Statuses',
         lambda item: {
             'Source ID': str(item.get('id', '')),
             'Source Name': item.get('name', ''),
             'Description': item.get('description', ''),
             'Category': item.get('statusCategory', {}).get('name', '') if isinstance(item.get('statusCategory'), dict) else ''
         }),
        ('issuetype', 'IssueTypes',
         lambda item: {
             'Source ID': str(item.get('id', '')),
             'Source Name': item.get('name', ''),
             'Description': item.get('description', ''),
             'Subtask': item.get('subtask', False)
         }),
        ('issuelinktype', 'IssueLinkTypes',
         lambda item: {
             'Source ID': str(item.get('id', '')),
             'Source Name': item.get('name', ''),
             'Inward': item.get('inward', ''),
             'Outward': item.get('outward', '')
         }),
        ('resolution', 'Resolutions',
         lambda item: {
             'Source ID': str(item.get('id', '')),
             'Source Name': item.get('name', ''),
             'Description': item.get('description', '')
         })
    ]

    for keyword, sheet_name, extractor in file_mappings:
        # Auto-detect file by keyword
        source_file = find_source_file(SOURCE_DIR, keyword)

        if not source_file:
            print(f"\n⚠ No file found for {keyword} (looking for *_{keyword}_api.rtf or .txt)")
            continue

        print(f"\n📄 Processing {source_file.name}...")

        content = extract_text_from_file(source_file)
        if not content:
            print(f"  ⚠ Could not read {source_file.name}")
            continue

        json_data = parse_json_content(content)
        if not json_data:
            print(f"  ⚠ Could not parse JSON from {source_file.name}")
            continue

        # Extract fields
        rows = [extractor(item) for item in json_data]
        df = pd.DataFrame(rows)

        sheets[sheet_name] = df
        print(f"  ✓ {sheet_name}: {len(df)} records")

    # Write xlsx
    if sheets:
        write_xlsx(sheets, output_file)
        print(f"\n✅ Source data saved to: {output_file}")
    else:
        print("\n⚠ No data to write")

    return output_file


def find_consolidated_export(directory, stage='pre-import'):
    """Find a consolidated export file (TXT or RTF) and ensure it's in TXT format.

    Looks for files like:
    - target_pre-import.txt / target_post-import.txt (preferred - no conversion)
    - target_all_objects_pre-import.txt / target_all_objects_post-import.txt
    - target_pre-import.rtf / target_post-import.rtf (will convert)
    - target_all_objects.txt (legacy name)

    Args:
        directory: Path to search in
        stage: 'pre-import' or 'post-import' for naming converted files

    Returns path to the TXT file if successful, None otherwise.
    """
    directory = Path(directory)

    # First, look for existing TXT files (no conversion needed)
    txt_patterns = [
        f'target_{stage}.txt',
        f'target_all_objects_{stage}.txt',
        'target_all_objects.txt',
        'target*.txt'  # Fallback glob
    ]

    for pattern in txt_patterns:
        if '*' in pattern:
            matches = list(directory.glob(pattern))
            # Filter out individual files (those with field_, status_, etc.)
            matches = [m for m in matches if not any(x in m.name for x in ['field', 'status', 'issuetype', 'issuelinktype', 'resolution', '_converted'])]
            if matches:
                print(f"\n📄 Found consolidated TXT: {matches[0].name}")
                return matches[0]
        else:
            candidate = directory / pattern
            if candidate.exists():
                print(f"\n📄 Found consolidated TXT: {candidate.name}")
                return candidate

    # No TXT found, look for RTF files to convert
    rtf_patterns = [
        f'target_{stage}.rtf',
        f'target_all_objects_{stage}.rtf',
        'target_all_objects.rtf',
        'target*.rtf'  # Fallback glob
    ]

    rtf_file = None
    for pattern in rtf_patterns:
        if '*' in pattern:
            matches = list(directory.glob(pattern))
            # Filter out individual RTF files
            matches = [m for m in matches if not any(x in m.name for x in ['field', 'status', 'issuetype', 'issuelinktype', 'resolution'])]
            if matches:
                rtf_file = matches[0]
                break
        else:
            candidate = directory / pattern
            if candidate.exists():
                rtf_file = candidate
                break

    if not rtf_file:
        return None

    # Convert RTF to TXT with stage-specific name
    txt_file = directory / f'target_all_objects_{stage}.txt'
    print(f"\n📄 Found consolidated RTF: {rtf_file.name}")
    print(f"  Converting to TXT...")

    try:
        result = subprocess.run([
            'textutil', '-convert', 'txt', '-output', str(txt_file), str(rtf_file)
        ], check=True, capture_output=True)
        print(f"  ✓ Converted to: {txt_file.name}")
        return txt_file
    except subprocess.CalledProcessError as e:
        print(f"  ⚠ Error converting RTF: {e}")
        return None
    except FileNotFoundError:
        print(f"  ⚠ textutil not found (macOS only)")
        return None


def convert_target_pre_import():
    """Convert target pre-import RTF files to xlsx.

    Supports two input methods:
    1. Consolidated export: target_all_objects.txt or .rtf (preferred - single file)
    2. Individual RTF files: target_*_pre-import.rtf (legacy - 5 files)
    """
    print("\n" + "=" * 80)
    print("CONVERTING TARGET PRE-IMPORT DATA TO XLSX")
    print("=" * 80)

    output_file = TARGET_PRE_DIR / 'target_data_pre_import_converted.xlsx'
    sheets = {}

    # Find consolidated export (TXT or RTF, auto-converts if needed)
    consolidated_file = find_consolidated_export(TARGET_PRE_DIR, stage='pre-import')

    if consolidated_file and consolidated_file.exists():
        print(f"\n📦 Found consolidated export: {consolidated_file.name}")
        consolidated_data = parse_consolidated_export(consolidated_file)

        if consolidated_data:
            for sheet_name, records in consolidated_data.items():
                df = convert_consolidated_to_df(records, sheet_name)
                if df is not None and not df.empty:
                    sheets[sheet_name] = df
                    print(f"  ✓ {sheet_name}: {len(df)} records")

            if sheets:
                write_xlsx(sheets, output_file)
                print(f"\n✅ Target pre-import data saved to: {output_file}")
                return output_file

        print("  ⚠ Could not parse consolidated export, falling back to RTF files")

    # Fallback to individual RTF files
    print("\n📄 Processing individual RTF files...")

    # Define file mappings for target data
    file_mappings = [
        ('target_field_pre-import.rtf', 'CustomFields'),
        ('target_status_pre-import.rtf', 'Statuses'),
        ('target_issuetype_pre-import.rtf', 'IssueTypes'),
        ('target_issuelinktype_pre-import.rtf', 'IssueLinkTypes'),
        ('target_resolution_pre-import.rtf', 'Resolutions')
    ]

    for rtf_file, sheet_name in file_mappings:
        rtf_path = TARGET_PRE_DIR / rtf_file
        print(f"\n📄 Processing {rtf_file}...")

        df = convert_target_rtf_to_df(rtf_path, sheet_name)
        if df is not None and not df.empty:
            sheets[sheet_name] = df
            print(f"  ✓ {sheet_name}: {len(df)} records")
        else:
            print(f"  ⚠ No data extracted from {rtf_file}")

    # Write xlsx
    if sheets:
        write_xlsx(sheets, output_file)
        print(f"\n✅ Target pre-import data saved to: {output_file}")
    else:
        print("\n⚠ No data to write")

    return output_file


def convert_target_post_import():
    """Convert target post-import RTF files to xlsx.

    Supports two input methods:
    1. Consolidated export: target_all_objects.txt or .rtf (preferred - single file)
    2. Individual RTF files: target_*_post-import.rtf (legacy - 5 files)
    """
    print("\n" + "=" * 80)
    print("CONVERTING TARGET POST-IMPORT DATA TO XLSX")
    print("=" * 80)

    output_file = TARGET_POST_DIR / 'target_data_post_import_converted.xlsx'
    sheets = {}

    # Find consolidated export (TXT or RTF, auto-converts if needed)
    consolidated_file = find_consolidated_export(TARGET_POST_DIR, stage='post-import')

    if consolidated_file and consolidated_file.exists():
        print(f"\n📦 Found consolidated export: {consolidated_file.name}")
        consolidated_data = parse_consolidated_export(consolidated_file)

        if consolidated_data:
            for sheet_name, records in consolidated_data.items():
                df = convert_consolidated_to_df(records, sheet_name)
                if df is not None and not df.empty:
                    sheets[sheet_name] = df
                    print(f"  ✓ {sheet_name}: {len(df)} records")

            if sheets:
                write_xlsx(sheets, output_file)
                print(f"\n✅ Target post-import data saved to: {output_file}")
                return output_file

        print("  ⚠ Could not parse consolidated export, falling back to RTF files")

    # Fallback to individual RTF files
    print("\n📄 Processing individual RTF files...")

    # Define file mappings for post-import data
    file_mappings = [
        ('target_field_post-import.rtf', 'CustomFields'),
        ('target_status_post-import.rtf', 'Statuses'),
        ('target_issuetype_post-import.rtf', 'IssueTypes'),
        ('target_issuelinktype_post-import.rtf', 'IssueLinkTypes'),
        ('target_resolution_post-import.rtf', 'Resolutions')
    ]

    for rtf_file, sheet_name in file_mappings:
        rtf_path = TARGET_POST_DIR / rtf_file
        print(f"\n📄 Processing {rtf_file}...")

        df = convert_target_rtf_to_df(rtf_path, sheet_name)
        if df is not None and not df.empty:
            sheets[sheet_name] = df
            print(f"  ✓ {sheet_name}: {len(df)} records")
        else:
            print(f"  ⚠ No data extracted from {rtf_file}")

    # Write xlsx
    if sheets:
        write_xlsx(sheets, output_file)
        print(f"\n✅ Target post-import data saved to: {output_file}")
    else:
        print("\n⚠ No data to write")

    return output_file


def convert_target_rtf_to_df(rtf_path, sheet_name):
    """Convert a target RTF file to DataFrame.

    Target files can be either JSON or CSV-like format.
    """
    content = extract_text_from_rtf(rtf_path)
    if not content:
        return None

    # Try JSON first
    json_data = parse_json_content(content)
    if json_data:
        return convert_target_json_to_df(json_data, sheet_name)

    # Try CSV-like format
    csv_data = parse_csv_content(content)
    if csv_data:
        return convert_target_csv_to_df(csv_data, sheet_name)

    return None


def convert_target_json_to_df(json_data, sheet_name):
    """Convert target JSON data to DataFrame."""
    rows = []

    for item in json_data:
        if sheet_name == 'CustomFields':
            rows.append({
                'Target ID': item.get('id', '').replace('customfield_', ''),
                'Target Name': item.get('name', ''),
                'Field Type': item.get('schema', {}).get('custom', '') if isinstance(item.get('schema'), dict) else '',
                'Description': item.get('description', '')
            })
        elif sheet_name == 'Statuses':
            rows.append({
                'Target ID': str(item.get('id', '')),
                'Target Name': item.get('name', ''),
                'Category': item.get('statusCategory', {}).get('name', '') if isinstance(item.get('statusCategory'), dict) else ''
            })
        elif sheet_name == 'IssueTypes':
            rows.append({
                'Target ID': str(item.get('id', '')),
                'Target Name': item.get('name', ''),
                'Description': item.get('description', '')
            })
        elif sheet_name == 'IssueLinkTypes':
            rows.append({
                'Target ID': str(item.get('id', '')),
                'Target Name': item.get('name', ''),
                'Inward': item.get('inward', ''),
                'Outward': item.get('outward', '')
            })
        elif sheet_name == 'Resolutions':
            rows.append({
                'Target ID': str(item.get('id', '')),
                'Target Name': item.get('name', ''),
                'Description': item.get('description', '')
            })

    return pd.DataFrame(rows) if rows else None


def convert_target_csv_to_df(csv_data, sheet_name):
    """Convert target CSV-like data to DataFrame.

    Expected formats:
    - 2 columns: ID, Name
    - 3 columns: ID, Name, Type (for CustomFields)
    """
    if not csv_data:
        return None

    rows = []

    for record in csv_data:
        if len(record) >= 2:
            row = {
                'Target ID': record[0].replace('customfield_', '') if 'customfield_' in record[0] else record[0],
                'Target Name': record[1]
            }

            # Add type for CustomFields if 3rd column exists
            if len(record) >= 3 and sheet_name == 'CustomFields':
                row['Field Type'] = record[2]

            rows.append(row)

    return pd.DataFrame(rows) if rows else None


def write_xlsx(sheets, output_file):
    """Write sheets to xlsx with formatting."""
    with pd.ExcelWriter(output_file, engine='openpyxl') as writer:
        for sheet_name, df in sheets.items():
            df.to_excel(writer, sheet_name=sheet_name, index=False)

            # Auto-adjust column widths
            worksheet = writer.sheets[sheet_name]
            for idx, col in enumerate(df.columns):
                max_length = max(
                    df[col].astype(str).apply(len).max() if len(df) > 0 else 0,
                    len(col)
                ) + 2
                # Convert index to column letter (A, B, C, ... AA, AB, etc.)
                col_letter = get_column_letter(idx + 1)
                worksheet.column_dimensions[col_letter].width = min(max_length, 50)

        # Add metadata sheet
        metadata = pd.DataFrame([
            {'Property': 'Converted Date', 'Value': datetime.now().strftime('%Y-%m-%d %H:%M:%S')},
            {'Property': 'Sheets', 'Value': ', '.join(sheets.keys())},
            {'Property': 'Total Records', 'Value': sum(len(df) for df in sheets.values())}
        ])
        metadata.to_excel(writer, sheet_name='_Metadata', index=False)


def get_column_letter(col_num):
    """Convert column number to Excel column letter (1=A, 2=B, ..., 27=AA)."""
    result = ""
    while col_num > 0:
        col_num, remainder = divmod(col_num - 1, 26)
        result = chr(65 + remainder) + result
    return result


def main():
    parser = argparse.ArgumentParser(description='Convert RTF data files to XLSX')
    parser.add_argument('--source', action='store_true', help='Convert source API data')
    parser.add_argument('--target-pre', action='store_true', help='Convert target pre-import data')
    parser.add_argument('--target-post', action='store_true', help='Convert target post-import data')
    parser.add_argument('--all', action='store_true', help='Convert all data files')

    args = parser.parse_args()

    # Default to --all if no args provided
    if not any([args.source, args.target_pre, args.target_post, args.all]):
        args.all = True

    print("=" * 80)
    print("DATA TO XLSX CONVERTER")
    print("=" * 80)
    print(f"Timestamp: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")

    output_files = []

    if args.source or args.all:
        output_files.append(convert_source_data())

    if args.target_pre or args.all:
        output_files.append(convert_target_pre_import())

    if args.target_post or args.all:
        output_files.append(convert_target_post_import())

    print("\n" + "=" * 80)
    print("CONVERSION COMPLETE")
    print("=" * 80)
    print("\nOutput files:")
    for f in output_files:
        if f:
            print(f"  📊 {f}")

    print("\n✅ Done!")


if __name__ == "__main__":
    main()