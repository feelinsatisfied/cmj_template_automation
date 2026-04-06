#!/usr/bin/env python3
"""
Validate Cleanup Results

Validates the Groovy cleanup script output against the cleanup report.

Two modes:
1. --dryrun: Validate dryrun output BEFORE running live cleanup
   - Ensures all items to be deleted are in the cleanup report
   - Flags any unexpected deletions

2. --liverun: Validate liverun output AFTER cleanup execution
   - Ensures liverun matches dryrun (nothing unexpected deleted)
   - Confirms all deletions were authorized

Usage:
    python3 validate_cleanup_results.py --dryrun
    python3 validate_cleanup_results.py --liverun
"""

import re
import subprocess
from pathlib import Path
from datetime import datetime
import pandas as pd

# Base paths
BASE_DIR = Path(__file__).resolve().parent.parent
VALIDATION_DIR = BASE_DIR / 'target_data' / 'cleaning_validation'
OUTPUT_DIR = BASE_DIR / 'customer_review'


def convert_rtf_to_text(rtf_path):
    """Convert RTF file to plain text using textutil."""
    if not rtf_path.exists():
        return None

    try:
        result = subprocess.run(
            ['textutil', '-convert', 'txt', '-stdout', str(rtf_path)],
            capture_output=True,
            text=True,
            check=True
        )
        return result.stdout
    except subprocess.CalledProcessError as e:
        print(f"  Error converting RTF: {e}")
        return None


def parse_cleanup_output(content):
    """Parse the Groovy cleanup script output.

    Returns dict with:
        - deleted: list of (type, name, id) tuples
        - skipped: list of (type, name, id, reason) tuples
        - manual_delete: list of (type, name, id) tuples (resolutions)
    """
    result = {
        'deleted': [],
        'skipped': [],
        'manual_delete': []
    }

    if not content:
        return result

    # Extract deleted section
    deleted_match = re.search(r'\[deleted:\[(.*?)\], skipped:', content, re.DOTALL)
    if deleted_match:
        deleted_content = deleted_match.group(1)

        # Parse DELETED or [DRY RUN] WOULD DELETE entries
        # Pattern: DELETED CustomField: Name (customfield_12345)
        # Or: [DRY RUN] WOULD DELETE CustomField: Name (customfield_12345) - 0 issues
        # Note: Some names contain parentheses, so we match the ID pattern specifically
        # CustomField IDs: customfield_XXXXX
        # Status/Resolution/IssueType/IssueLinkType IDs: numeric only
        cf_pattern = r'(?:\[DRY RUN\] WOULD DELETE |DELETED )(CustomField): (.+?) \((customfield_\d+)\)'
        for match in re.finditer(cf_pattern, deleted_content):
            obj_type, name, obj_id = match.groups()
            result['deleted'].append((obj_type.strip(), name.strip(), obj_id.strip()))

        # For Status, Resolution, IssueType, IssueLinkType - ID is numeric
        other_pattern = r'(?:\[DRY RUN\] WOULD DELETE |DELETED )(Status|Resolution|IssueType|IssueLinkType): (.+?) \((\d+)\)'
        for match in re.finditer(other_pattern, deleted_content):
            obj_type, name, obj_id = match.groups()
            result['deleted'].append((obj_type.strip(), name.strip(), obj_id.strip()))

        # Parse MANUAL DELETE SAFE entries (resolutions)
        manual_pattern = r'MANUAL DELETE SAFE - (Resolution): ([^(]+) \((\d+)\)'
        for match in re.finditer(manual_pattern, deleted_content):
            obj_type, name, obj_id = match.groups()
            result['manual_delete'].append((obj_type.strip(), name.strip(), obj_id.strip()))

    # Extract skipped section
    skipped_match = re.search(r'skipped:\[(.*?)\]\]', content, re.DOTALL)
    if skipped_match:
        skipped_content = skipped_match.group(1)

        # Parse SKIPPED entries
        # Pattern: SKIPPED CustomField: Name (customfield_12345) - reason
        # CustomField IDs: customfield_XXXXX
        cf_skip_pattern = r'SKIPPED (CustomField): (.+?) \((customfield_\d+)\) - (.+?)(?:,|$)'
        for match in re.finditer(cf_skip_pattern, skipped_content):
            obj_type, name, obj_id, reason = match.groups()
            result['skipped'].append((obj_type.strip(), name.strip(), obj_id.strip(), reason.strip()))

        # For Status, Resolution, IssueType, IssueLinkType - ID is numeric
        other_skip_pattern = r'SKIPPED (Status|Resolution|IssueType|IssueLinkType): (.+?) \((\d+)\) - (.+?)(?:,|$)'
        for match in re.finditer(other_skip_pattern, skipped_content):
            obj_type, name, obj_id, reason = match.groups()
            result['skipped'].append((obj_type.strip(), name.strip(), obj_id.strip(), reason.strip()))

    return result


def load_cleanup_report():
    """Load the cleanup report and extract expected deletions."""
    # Find cleanup report
    pattern = '*_Customer_Mapping_CLEANUP_REPORT.xlsx'
    matches = list(OUTPUT_DIR.glob(pattern))

    if not matches:
        return None, None

    report_file = matches[0]
    project_key = report_file.stem.replace('_Customer_Mapping_CLEANUP_REPORT', '')

    expected_deletions = {
        'CustomField': set(),
        'Status': set(),
        'Resolution': set(),
        'IssueType': set(),
        'IssueLinkType': set()
    }

    xlsx = pd.ExcelFile(report_file)

    # Map sheet names to object types
    sheet_mapping = {
        'DELETE_CustomFields': 'CustomField',
        'DELETE_Status': 'Status',
        'DELETE_Resolutions': 'Resolution',
        'DELETE_IssueTypes': 'IssueType',
        'DELETE_IssueLinkTypes': 'IssueLinkType'
    }

    for sheet_name, obj_type in sheet_mapping.items():
        if sheet_name in xlsx.sheet_names:
            df = pd.read_excel(report_file, sheet_name=sheet_name)
            if 'Source Name' in df.columns:
                for name in df['Source Name'].dropna():
                    expected_deletions[obj_type].add(name.strip())

    return expected_deletions, project_key


def validate_dryrun():
    """Validate dryrun output before executing live cleanup."""
    print("=" * 80)
    print("CLEANUP VALIDATION - DRYRUN MODE")
    print("=" * 80)
    print(f"Timestamp: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")

    # Load dryrun file
    dryrun_file = VALIDATION_DIR / 'target_cleaning_dryrun.rtf'
    if not dryrun_file.exists():
        print(f"\n ERROR: Dryrun file not found: {dryrun_file}")
        return False

    print(f"\n Input: {dryrun_file.name}")

    # Convert and parse
    content = convert_rtf_to_text(dryrun_file)
    if not content:
        print(" ERROR: Could not read dryrun file")
        return False

    dryrun_data = parse_cleanup_output(content)

    # Load cleanup report
    expected_deletions, project_key = load_cleanup_report()
    if not expected_deletions:
        print(" ERROR: Cleanup report not found")
        return False

    print(f" Project: {project_key}")
    print("-" * 80)

    # Validate
    issues = []
    warnings = []

    # Check each deleted item is in the expected list
    print("\n VALIDATING DELETIONS...")
    for obj_type, name, obj_id in dryrun_data['deleted']:
        if name not in expected_deletions.get(obj_type, set()):
            issues.append(f"  UNEXPECTED: {obj_type} '{name}' ({obj_id}) not in cleanup report")

    # Check manual deletes (resolutions)
    for obj_type, name, obj_id in dryrun_data['manual_delete']:
        if name not in expected_deletions.get(obj_type, set()):
            issues.append(f"  UNEXPECTED MANUAL: {obj_type} '{name}' ({obj_id}) not in cleanup report")

    # Summary counts
    print("\n DRYRUN SUMMARY:")
    print(f"   CustomFields to delete: {len([d for d in dryrun_data['deleted'] if d[0] == 'CustomField'])}")
    print(f"   Statuses to delete: {len([d for d in dryrun_data['deleted'] if d[0] == 'Status'])}")
    print(f"   Resolutions (manual): {len(dryrun_data['manual_delete'])}")
    print(f"   Items skipped: {len(dryrun_data['skipped'])}")

    # Check skipped items for warnings
    print("\n SKIPPED ITEMS REVIEW:")
    jql_failed = [s for s in dryrun_data['skipped'] if 'JQL check failed' in s[3]]
    has_data = [s for s in dryrun_data['skipped'] if 'issues have data' in s[3]]

    print(f"   Skipped (has data): {len(has_data)}")
    print(f"   Skipped (JQL failed): {len(jql_failed)}")

    if jql_failed:
        warnings.append(f"  {len(jql_failed)} items skipped due to JQL failures (check field names with quotes)")

    # Report results
    print("\n" + "=" * 80)
    if issues:
        print(" VALIDATION FAILED")
        print("=" * 80)
        print("\n Issues found:")
        for issue in issues:
            print(issue)
        return False
    else:
        print(" VALIDATION PASSED")
        print("=" * 80)
        if warnings:
            print("\n Warnings:")
            for warning in warnings:
                print(warning)
        print("\n Safe to proceed with live cleanup!")
        return True


def validate_liverun():
    """Validate liverun output after cleanup execution."""
    print("=" * 80)
    print("CLEANUP VALIDATION - LIVERUN MODE")
    print("=" * 80)
    print(f"Timestamp: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")

    # Load both files
    dryrun_file = VALIDATION_DIR / 'target_cleaning_dryrun.rtf'
    liverun_file = VALIDATION_DIR / 'target_cleaning_liverun.rtf'

    if not dryrun_file.exists():
        print(f"\n ERROR: Dryrun file not found: {dryrun_file}")
        return False

    if not liverun_file.exists():
        print(f"\n ERROR: Liverun file not found: {liverun_file}")
        return False

    print(f"\n Dryrun file: {dryrun_file.name}")
    print(f" Liverun file: {liverun_file.name}")

    # Parse both
    dryrun_content = convert_rtf_to_text(dryrun_file)
    liverun_content = convert_rtf_to_text(liverun_file)

    if not dryrun_content or not liverun_content:
        print(" ERROR: Could not read files")
        return False

    dryrun_data = parse_cleanup_output(dryrun_content)
    liverun_data = parse_cleanup_output(liverun_content)

    # Load cleanup report for additional context
    expected_deletions, project_key = load_cleanup_report()
    print(f" Project: {project_key}")
    print("-" * 80)

    issues = []
    warnings = []

    # Build sets for comparison (name, id tuples for matching)
    dryrun_deleted_set = {(d[0], d[1], d[2]) for d in dryrun_data['deleted']}
    liverun_deleted_set = {(d[0], d[1], d[2]) for d in liverun_data['deleted']}

    dryrun_skipped_set = {(s[0], s[1], s[2]) for s in dryrun_data['skipped']}
    liverun_skipped_set = {(s[0], s[1], s[2]) for s in liverun_data['skipped']}

    # Check 1: Items deleted in liverun should have been in dryrun deleted list
    print("\n VALIDATING LIVERUN DELETIONS...")
    unexpected_deletes = liverun_deleted_set - dryrun_deleted_set
    for obj_type, name, obj_id in unexpected_deletes:
        issues.append(f"  UNEXPECTED DELETE: {obj_type} '{name}' ({obj_id}) was deleted but not in dryrun!")

    # Check 2: Items that were in dryrun but not deleted (moved to skipped or missing)
    not_deleted = dryrun_deleted_set - liverun_deleted_set
    for obj_type, name, obj_id in not_deleted:
        if (obj_type, name, obj_id) in liverun_skipped_set:
            warnings.append(f"  CHANGED TO SKIP: {obj_type} '{name}' ({obj_id}) was skipped in liverun (was in dryrun delete)")
        else:
            warnings.append(f"  NOT FOUND: {obj_type} '{name}' ({obj_id}) from dryrun not in liverun results")

    # Check 3: Skipped items consistency
    print("\n VALIDATING SKIPPED ITEMS...")
    new_skips = liverun_skipped_set - dryrun_skipped_set
    for obj_type, name, obj_id in new_skips:
        if (obj_type, name, obj_id) not in dryrun_deleted_set:
            warnings.append(f"  NEW SKIP: {obj_type} '{name}' ({obj_id}) skipped in liverun (not in dryrun)")

    # Summary
    print("\n COMPARISON SUMMARY:")
    print(f"   Dryrun would delete: {len(dryrun_deleted_set)}")
    print(f"   Liverun deleted: {len(liverun_deleted_set)}")
    print(f"   Dryrun skipped: {len(dryrun_skipped_set)}")
    print(f"   Liverun skipped: {len(liverun_skipped_set)}")
    print(f"   Manual deletes (resolutions): {len(liverun_data['manual_delete'])}")

    # Detailed breakdown
    print("\n LIVERUN DELETION BREAKDOWN:")
    cf_deleted = len([d for d in liverun_data['deleted'] if d[0] == 'CustomField'])
    status_deleted = len([d for d in liverun_data['deleted'] if d[0] == 'Status'])
    print(f"   CustomFields deleted: {cf_deleted}")
    print(f"   Statuses deleted: {status_deleted}")

    # Report results
    print("\n" + "=" * 80)
    if issues:
        print(" VALIDATION FAILED - UNEXPECTED DELETIONS!")
        print("=" * 80)
        print("\n Critical issues:")
        for issue in issues:
            print(issue)
        if warnings:
            print("\n Warnings:")
            for warning in warnings:
                print(warning)
        return False
    else:
        print(" VALIDATION PASSED")
        print("=" * 80)
        if warnings:
            print("\n Warnings (non-critical):")
            for warning in warnings:
                print(warning)
        print("\n Cleanup completed successfully - all deletions were authorized!")
        return True


def main():
    """Main entry point."""
    import sys

    if len(sys.argv) < 2:
        print("Usage: python3 validate_cleanup_results.py [--dryrun | --liverun]")
        print("")
        print("  --dryrun   Validate dryrun output before live cleanup")
        print("  --liverun  Validate liverun output after cleanup execution")
        sys.exit(1)

    mode = sys.argv[1]

    if mode == '--dryrun':
        success = validate_dryrun()
    elif mode == '--liverun':
        success = validate_liverun()
    else:
        print(f"Unknown mode: {mode}")
        print("Use --dryrun or --liverun")
        sys.exit(1)

    sys.exit(0 if success else 1)


if __name__ == "__main__":
    main()
