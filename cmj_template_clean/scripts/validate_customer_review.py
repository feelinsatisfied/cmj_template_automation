#!/usr/bin/env python3
"""
Validate Customer Review File

Validates the customer-reviewed mapping file before CMJ template generation.
Catches common errors like:
- Leading/trailing spaces in names
- Copied suggestion text with percentages (e.g., "Name (85%)")
- Objects that don't exist in source/target data
- Misspellings (fuzzy match detection)
- Invalid Migration Actions
- Empty required fields
- Duplicate source names
- Duplicate target mappings (multiple sources → same target)

Usage:
    python3 validate_customer_review.py
    python3 validate_customer_review.py --auto-fix  # Apply fixes automatically

Exit codes:
    0 - Validation passed (or only warnings)
    1 - Validation failed (blocking errors found)
"""

import re
import sys
from pathlib import Path
from datetime import datetime
from difflib import SequenceMatcher
import pandas as pd

# Base paths
BASE_DIR = Path(__file__).resolve().parent.parent
SOURCE_DATA_DIR = BASE_DIR / 'source_data'
SOURCE_API_DIR = SOURCE_DATA_DIR / 'source_api_full'
TARGET_PRE_DIR = BASE_DIR / 'target_data' / 'pre_import'
OUTPUT_DIR = BASE_DIR / 'customer_review'

# Valid Migration Actions
VALID_ACTIONS = {'MAP', 'CREATE', 'SKIP', 'DELETE'}

# Sheets to validate
SHEETS_TO_VALIDATE = ['Status', 'CustomFields', 'Resolutions', 'IssueLinkTypes', 'IssueTypes']


def load_source_data():
    """Load source data from converted xlsx file."""
    source_xlsx = SOURCE_API_DIR / 'source_data_converted.xlsx'
    if not source_xlsx.exists():
        return {}

    source_data = {}
    xlsx = pd.ExcelFile(source_xlsx)

    sheet_mapping = {
        'CustomFields': 'CustomFields',
        'Statuses': 'Status',
        'IssueTypes': 'IssueTypes',
        'IssueLinkTypes': 'IssueLinkTypes',
        'Resolutions': 'Resolutions'
    }

    for xlsx_sheet, obj_type in sheet_mapping.items():
        if xlsx_sheet in xlsx.sheet_names:
            df = pd.read_excel(source_xlsx, sheet_name=xlsx_sheet)
            # Check for various name column formats
            name_col = None
            for col in ['Name', 'Source Name', 'name']:
                if col in df.columns:
                    name_col = col
                    break
            if name_col:
                source_data[obj_type] = set(df[name_col].dropna().str.strip().tolist())

    return source_data


def load_target_data():
    """Load target data from converted xlsx file."""
    target_xlsx = TARGET_PRE_DIR / 'target_data_pre_import_converted.xlsx'
    if not target_xlsx.exists():
        return {}

    target_data = {}
    xlsx = pd.ExcelFile(target_xlsx)

    sheet_mapping = {
        'CustomFields': 'CustomFields',
        'Statuses': 'Status',
        'IssueTypes': 'IssueTypes',
        'IssueLinkTypes': 'IssueLinkTypes',
        'Resolutions': 'Resolutions'
    }

    for xlsx_sheet, obj_type in sheet_mapping.items():
        if xlsx_sheet in xlsx.sheet_names:
            df = pd.read_excel(target_xlsx, sheet_name=xlsx_sheet)
            # Check for various name column formats
            name_col = None
            for col in ['Name', 'Target Name', 'name']:
                if col in df.columns:
                    name_col = col
                    break
            if name_col:
                target_data[obj_type] = set(df[name_col].dropna().str.strip().tolist())

    return target_data


def find_reviewed_files():
    """Find all customer-reviewed mapping files.

    Returns a list of (file_path, project_key) tuples for all found files.
    Prioritizes _Reviewed files over _PROCESSED files for each project.
    """
    result = []
    found_projects = set()

    # First try _Reviewed files
    pattern = '*_Customer_Mapping_PROCESSED_Reviewed.xlsx'
    matches = list(OUTPUT_DIR.glob(pattern))

    for match in sorted(matches):
        project_key = match.stem.replace('_Customer_Mapping_PROCESSED_Reviewed', '')
        if project_key not in found_projects:
            result.append((match, project_key))
            found_projects.add(project_key)

    # Fall back to _PROCESSED files for projects without _Reviewed
    pattern = '*_Customer_Mapping_PROCESSED.xlsx'
    matches = list(OUTPUT_DIR.glob(pattern))

    for match in sorted(matches):
        project_key = match.stem.replace('_Customer_Mapping_PROCESSED', '')
        if project_key not in found_projects:
            result.append((match, project_key))
            found_projects.add(project_key)

    return result


def has_percentage_pattern(text):
    """Check if text contains a percentage pattern like (85%) or (100%)."""
    if pd.isna(text):
        return False
    return bool(re.search(r'\(\d+%\)', str(text)))


def has_leading_trailing_spaces(text):
    """Check if text has leading or trailing spaces."""
    if pd.isna(text):
        return False
    text_str = str(text)
    return text_str != text_str.strip()


def find_similar_names(name, valid_names, threshold=0.8):
    """Find similar names using fuzzy matching."""
    if pd.isna(name) or not valid_names:
        return []

    name_str = str(name).strip().lower()
    similar = []

    for valid_name in valid_names:
        valid_lower = str(valid_name).lower()
        ratio = SequenceMatcher(None, name_str, valid_lower).ratio()
        if ratio >= threshold and ratio < 1.0:
            similar.append((valid_name, int(ratio * 100)))

    # Sort by similarity (highest first)
    similar.sort(key=lambda x: x[1], reverse=True)
    return similar[:3]  # Return top 3 matches


def validate_sheet(df, sheet_name, source_names, target_names, auto_fix=False):
    """Validate a single sheet and return errors, warnings, and fixes."""
    errors = []
    warnings = []
    fixes = []

    if df.empty:
        return errors, warnings, fixes, df

    # Make a copy for potential fixes
    df_fixed = df.copy()

    for idx, row in df.iterrows():
        row_num = idx + 2  # Excel row number (1-indexed + header)

        # Get values
        source_name = row.get('Source Name')
        target_name = row.get('Target Name')
        migration_action = row.get('Migration Action')

        # Check 1: Empty Source Name
        if pd.isna(source_name) or str(source_name).strip() == '':
            errors.append(f"Row {row_num}: Empty Source Name")
            continue

        source_name_str = str(source_name)

        # Check 2: Leading/trailing spaces in Source Name
        if has_leading_trailing_spaces(source_name_str):
            if auto_fix:
                df_fixed.at[idx, 'Source Name'] = source_name_str.strip()
                fixes.append(f"Row {row_num}: Trimmed spaces from Source Name '{source_name_str}'")
            else:
                warnings.append(f"Row {row_num}: Source Name has leading/trailing spaces: '{source_name_str}'")

        # Check 3: Leading/trailing spaces in Target Name
        if not pd.isna(target_name) and has_leading_trailing_spaces(str(target_name)):
            target_name_str = str(target_name)
            if auto_fix:
                df_fixed.at[idx, 'Target Name'] = target_name_str.strip()
                fixes.append(f"Row {row_num}: Trimmed spaces from Target Name '{target_name_str}'")
            else:
                warnings.append(f"Row {row_num}: Target Name has leading/trailing spaces: '{target_name_str}'")

        # Check 4: Percentage pattern in Source Name (copied from suggestions)
        if has_percentage_pattern(source_name_str):
            errors.append(f"Row {row_num}: Source Name contains percentage (copied from suggestion?): '{source_name_str}'")

        # Check 5: Percentage pattern in Target Name (copied from suggestions)
        if not pd.isna(target_name) and has_percentage_pattern(str(target_name)):
            errors.append(f"Row {row_num}: Target Name contains percentage (copied from suggestion?): '{target_name}'")

        # Check 6: Invalid Migration Action
        if pd.isna(migration_action):
            errors.append(f"Row {row_num}: Missing Migration Action")
        else:
            action_upper = str(migration_action).strip().upper()
            if action_upper not in VALID_ACTIONS:
                errors.append(f"Row {row_num}: Invalid Migration Action '{migration_action}' (must be MAP, CREATE, SKIP, or DELETE)")
            elif str(migration_action).strip() != action_upper:
                # Fix case if needed
                if auto_fix:
                    df_fixed.at[idx, 'Migration Action'] = action_upper
                    fixes.append(f"Row {row_num}: Normalized Migration Action to '{action_upper}'")

        # Check 7: Source Name doesn't exist in source data
        # Skip this check for CMJ_SNAPSHOT items (they come from CMJ snapshots, not source API)
        # Also skip for CREATE actions (customer may be defining new names)
        source_name_clean = source_name_str.strip()
        project = row.get('Project')
        is_cmj_snapshot = str(project).strip() == 'CMJ_SNAPSHOT' if not pd.isna(project) else False
        action = str(migration_action).strip().upper() if not pd.isna(migration_action) else ''

        if source_names and source_name_clean not in source_names:
            if is_cmj_snapshot:
                pass  # Skip validation for CMJ_SNAPSHOT items
            elif action == 'CREATE':
                pass  # Skip validation for CREATE actions (new items)
            else:
                # Check for close matches
                similar = find_similar_names(source_name_clean, source_names)
                if similar:
                    similar_str = ', '.join([f"'{n}' ({p}%)" for n, p in similar])
                    warnings.append(f"Row {row_num}: Source Name '{source_name_clean}' not found in source data. Did you mean: {similar_str}?")
                else:
                    warnings.append(f"Row {row_num}: Source Name '{source_name_clean}' not found in source data")

        # Check 8: Target Name doesn't exist in target data (for MAP actions)
        if not pd.isna(target_name) and str(target_name).strip():
            target_name_clean = str(target_name).strip()

            if action == 'MAP' and target_names and target_name_clean not in target_names:
                similar = find_similar_names(target_name_clean, target_names)
                if similar:
                    similar_str = ', '.join([f"'{n}' ({p}%)" for n, p in similar])
                    errors.append(f"Row {row_num}: Target Name '{target_name_clean}' not found in target data. Did you mean: {similar_str}?")
                else:
                    errors.append(f"Row {row_num}: Target Name '{target_name_clean}' not found in target data (Migration Action is MAP)")

    # Check 9: Duplicate Source Names
    if 'Source Name' in df.columns:
        source_names_in_sheet = df['Source Name'].dropna().str.strip()
        duplicates = source_names_in_sheet[source_names_in_sheet.duplicated(keep=False)]
        if not duplicates.empty:
            dup_counts = duplicates.value_counts()
            for name, count in dup_counts.items():
                warnings.append(f"Duplicate Source Name '{name}' appears {count} times")

    # Check 10: Duplicate Target Names for MAP actions (conflict detection)
    if 'Target Name' in df.columns and 'Migration Action' in df.columns:
        # Filter to MAP actions only
        map_rows = df[df['Migration Action'].str.upper().str.strip() == 'MAP'].copy()
        if not map_rows.empty and 'Target Name' in map_rows.columns:
            # Get non-empty target names
            map_rows = map_rows[map_rows['Target Name'].notna()]
            map_rows['Target Name Clean'] = map_rows['Target Name'].str.strip()

            # Find duplicates
            dup_targets = map_rows[map_rows.duplicated(subset=['Target Name Clean'], keep=False)]
            if not dup_targets.empty:
                # Group by target name to show which sources conflict
                grouped = dup_targets.groupby('Target Name Clean')['Source Name'].apply(list)
                for target, sources in grouped.items():
                    source_list = [str(s).strip() for s in sources]
                    errors.append(f"CONFLICT: Multiple sources mapping to '{target}': {source_list}")

    return errors, warnings, fixes, df_fixed


def validate_single_file(input_file, project_key, source_data, target_data, auto_fix=False):
    """Validate a single reviewed mapping file.

    Returns:
        tuple: (errors, warnings, fixes, output_file_if_fixed)
    """
    print(f"\n{'=' * 80}")
    print(f"VALIDATING: {input_file.name}")
    print(f"Project: {project_key}")
    print("=" * 80)

    xlsx = pd.ExcelFile(input_file)
    all_errors = []
    all_warnings = []
    all_fixes = []
    fixed_sheets = {}

    for sheet_name in SHEETS_TO_VALIDATE:
        if sheet_name not in xlsx.sheet_names:
            print(f"\n  {sheet_name}: Not found (skipping)")
            continue

        df = pd.read_excel(input_file, sheet_name=sheet_name)
        if df.empty:
            print(f"\n  {sheet_name}: Empty (skipping)")
            continue

        # Get reference data for this sheet type
        source_names = source_data.get(sheet_name, set())
        target_names = target_data.get(sheet_name, set())

        errors, warnings, fixes, df_fixed = validate_sheet(
            df, sheet_name, source_names, target_names, auto_fix
        )

        print(f"\n  {sheet_name}:")
        print(f"    Rows: {len(df)}")
        print(f"    Errors: {len(errors)}")
        print(f"    Warnings: {len(warnings)}")
        if auto_fix:
            print(f"    Fixes applied: {len(fixes)}")

        # Add sheet prefix to messages
        all_errors.extend([f"[{sheet_name}] {e}" for e in errors])
        all_warnings.extend([f"[{sheet_name}] {w}" for w in warnings])
        all_fixes.extend([f"[{sheet_name}] {f}" for f in fixes])

        fixed_sheets[sheet_name] = df_fixed

    # Print detailed results for this file
    print("\n" + "-" * 80)
    print(f"RESULTS FOR {project_key}")
    print("-" * 80)

    if all_fixes:
        print(f"\n FIXES APPLIED ({len(all_fixes)}):")
        for fix in all_fixes:
            print(f"  {fix}")

    if all_warnings:
        print(f"\n WARNINGS ({len(all_warnings)}):")
        for warning in all_warnings[:20]:  # Limit output
            print(f"  {warning}")
        if len(all_warnings) > 20:
            print(f"  ... and {len(all_warnings) - 20} more warnings")

    if all_errors:
        print(f"\n ERRORS ({len(all_errors)}):")
        for error in all_errors[:30]:  # Limit output
            print(f"  {error}")
        if len(all_errors) > 30:
            print(f"  ... and {len(all_errors) - 30} more errors")

    # Save fixed file if auto-fix is enabled and there were fixes
    output_file = None
    if auto_fix and all_fixes and not all_errors:
        output_file = OUTPUT_DIR / f'{project_key}_Customer_Mapping_PROCESSED_Reviewed_VALIDATED.xlsx'

        # Copy all sheets (including non-validated ones)
        with pd.ExcelWriter(output_file, engine='openpyxl') as writer:
            for sheet_name in xlsx.sheet_names:
                if sheet_name in fixed_sheets:
                    fixed_sheets[sheet_name].to_excel(writer, sheet_name=sheet_name, index=False)
                else:
                    df = pd.read_excel(input_file, sheet_name=sheet_name)
                    df.to_excel(writer, sheet_name=sheet_name, index=False)

        print(f"\nFixed file saved: {output_file.name}")

    return all_errors, all_warnings, all_fixes, output_file


def main():
    """Main function."""
    print("=" * 80)
    print("CUSTOMER REVIEW VALIDATION")
    print("=" * 80)
    print(f"Timestamp: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")

    # Parse arguments
    auto_fix = '--auto-fix' in sys.argv

    if auto_fix:
        print("\nMode: AUTO-FIX (will apply automatic corrections)")
    else:
        print("\nMode: VALIDATION ONLY (use --auto-fix to apply corrections)")

    # Find all reviewed files
    print("\n" + "-" * 80)
    print("FINDING INPUT FILES")
    print("-" * 80)

    reviewed_files = find_reviewed_files()
    if not reviewed_files:
        print(f"ERROR: No reviewed mapping files found in {OUTPUT_DIR}")
        print("Expected: *_Customer_Mapping_PROCESSED_Reviewed.xlsx")
        print("      or: *_Customer_Mapping_PROCESSED.xlsx")
        return 1

    print(f"Found {len(reviewed_files)} file(s) to validate:")
    for input_file, project_key in reviewed_files:
        print(f"  - {input_file.name} (Project: {project_key})")

    # Load source and target data ONCE (shared across all files)
    print("\n" + "-" * 80)
    print("LOADING REFERENCE DATA")
    print("-" * 80)

    source_data = load_source_data()
    target_data = load_target_data()

    if source_data:
        for obj_type, names in source_data.items():
            print(f"  Source {obj_type}: {len(names)} objects")
    else:
        print("  WARNING: No source data loaded (run convert_data_to_xlsx.py --source first)")

    if target_data:
        for obj_type, names in target_data.items():
            print(f"  Target {obj_type}: {len(names)} objects")
    else:
        print("  WARNING: No target data loaded (run convert_data_to_xlsx.py --target-pre first)")

    # Validate each file
    total_errors = []
    total_warnings = []
    total_fixes = []
    files_passed = []
    files_failed = []

    for input_file, project_key in reviewed_files:
        errors, warnings, fixes, output_file = validate_single_file(
            input_file, project_key, source_data, target_data, auto_fix
        )

        # Track results with project prefix
        total_errors.extend([f"[{project_key}] {e}" for e in errors])
        total_warnings.extend([f"[{project_key}] {w}" for w in warnings])
        total_fixes.extend([f"[{project_key}] {f}" for f in fixes])

        if errors:
            files_failed.append(project_key)
        else:
            files_passed.append(project_key)

    # Overall Summary
    print("\n" + "=" * 80)
    print("OVERALL VALIDATION SUMMARY")
    print("=" * 80)

    print(f"\nFiles Processed: {len(reviewed_files)}")
    print(f"  Passed: {len(files_passed)}")
    print(f"  Failed: {len(files_failed)}")

    if files_passed:
        print(f"\n  Passed: {', '.join(files_passed)}")
    if files_failed:
        print(f"  Failed: {', '.join(files_failed)}")

    print(f"\nTotal Errors: {len(total_errors)}")
    print(f"Total Warnings: {len(total_warnings)}")
    if auto_fix:
        print(f"Total Fixes Applied: {len(total_fixes)}")

    # Final status
    print("\n" + "=" * 80)
    if files_failed:
        print(" VALIDATION FAILED")
        print("=" * 80)
        print(f"\n{len(files_failed)} file(s) have errors that must be fixed before proceeding.")
        print("\nPlease correct the errors in the reviewed files and run validation again.")
        return 1
    else:
        print(" VALIDATION PASSED")
        print("=" * 80)

        if total_warnings:
            print(f"\n{len(total_warnings)} warning(s) found (non-blocking).")

        print("\nAll files validated successfully!")
        print("Ready to proceed with CMJ template generation!")
        return 0


if __name__ == "__main__":
    sys.exit(main())