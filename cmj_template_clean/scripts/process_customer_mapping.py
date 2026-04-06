#!/usr/bin/env python3
"""
Process Customer Mapping File

Comprehensive processor for customer-provided mapping file:
1. Auto-detect customer mapping file ({PROJECT_KEY}_Customer_Mapping.xlsx)
2. Enrich with Source IDs from converted source data xlsx
3. Enrich with Target IDs from converted target data xlsx
4. Set Match Types and Migration Actions
5. Parse CMJ snapshots for additional objects
6. Detect conflicts (multiple sources → same target)
7. Smart match and add to mapping

Usage:
    python3 process_customer_mapping.py
    python3 process_customer_mapping.py --mapping-file /path/to/file.xlsx
"""

import pandas as pd
import argparse
import csv
from pathlib import Path
from difflib import SequenceMatcher
from datetime import datetime


# Field type mapping will be loaded from config/field_type_mapping.csv
FIELD_TYPE_MAP = {}


def load_field_type_mapping():
    """Load field type mapping from CSV configuration file."""
    global FIELD_TYPE_MAP
    config_file = Path(__file__).resolve().parent.parent / 'config' / 'field_type_mapping.csv'

    if not config_file.exists():
        print(f"  ⚠ Field type mapping file not found: {config_file}")
        return

    with open(config_file, 'r') as f:
        reader = csv.reader(f)
        for row in reader:
            if len(row) >= 2 and not row[0].startswith('#'):
                gui_type = row[0].strip()
                api_type = row[1].strip()
                if gui_type and api_type and gui_type != 'GUI Type':  # Skip header
                    FIELD_TYPE_MAP[gui_type.lower()] = api_type


def normalize_field_type(field_type):
    """Normalize field type to technical API format for comparison."""
    if not field_type:
        return ''
    field_type_str = str(field_type).strip()
    # If it's already in technical format (contains a colon), return as-is
    if ':' in field_type_str:
        return field_type_str.lower()
    # Otherwise, look up in mapping
    return FIELD_TYPE_MAP.get(field_type_str.lower(), field_type_str.lower())


# Base paths (relative to script location: scripts/ -> cmj_template/)
BASE_DIR = Path(__file__).resolve().parent.parent
SOURCE_DATA_DIR = BASE_DIR / 'source_data'
SOURCE_API_DIR = SOURCE_DATA_DIR / 'source_api_full'
TARGET_DATA_DIR = BASE_DIR / 'target_data'
TARGET_PRE_DIR = TARGET_DATA_DIR / 'pre_import'
CMJ_SNAPSHOT_DIR = SOURCE_DATA_DIR / 'cmj_snapshot_objs'
OUTPUT_DIR = BASE_DIR / 'customer_review'


def find_customer_mapping_files():
    """Auto-detect all customer mapping files in source_data directory."""
    pattern = '*_Customer_Mapping.xlsx'
    matches = list(SOURCE_DATA_DIR.glob(pattern))

    # Filter out SAMPLE template files
    matches = [m for m in matches if not m.name.startswith('SAMPLE_')]

    if not matches:
        print(f"  ⚠ No customer mapping file found matching pattern: {pattern}")
        print(f"    Looking in: {SOURCE_DATA_DIR}")
        return []

    # Build list of (file, project_key) tuples
    result = []
    for mapping_file in sorted(matches):
        # Extract project key from filename (e.g., "ACME" from "ACME_Customer_Mapping.xlsx")
        project_key = mapping_file.stem.replace('_Customer_Mapping', '')
        result.append((mapping_file, project_key))

    return result


def find_customer_mapping_file():
    """Auto-detect customer mapping file in source_data directory (legacy single-file mode)."""
    files = find_customer_mapping_files()
    if not files:
        return None, None
    if len(files) > 1:
        print(f"  ℹ Multiple mapping files found:")
        for f, k in files:
            print(f"    - {f.name}")
        print(f"  Using first match: {files[0][0].name}")
    return files[0]


def load_source_data_from_xlsx():
    """Load source API data from converted xlsx file."""
    print("\n📊 Loading Source API Data...")
    print("-" * 80)

    source_xlsx = SOURCE_API_DIR / 'source_data_converted.xlsx'

    if not source_xlsx.exists():
        print(f"  ⚠ Source data file not found: {source_xlsx}")
        print("    Run: python3 convert_data_to_xlsx.py --source")
        return {}

    data = {}
    xls = pd.ExcelFile(source_xlsx)

    # Sheet name mappings (xlsx sheet → customer mapping sheet)
    sheet_mappings = {
        'CustomFields': 'CustomFields',
        'Statuses': 'Status',
        'IssueTypes': 'IssueTypes',
        'IssueLinkTypes': 'IssueLinkTypes',
        'Resolutions': 'Resolutions'
    }

    for xlsx_sheet, mapping_sheet in sheet_mappings.items():
        if xlsx_sheet not in xls.sheet_names:
            continue

        df = pd.read_excel(source_xlsx, sheet_name=xlsx_sheet)

        if xlsx_sheet == 'CustomFields':
            data[mapping_sheet] = {
                row['Source Name']: {
                    'id': str(row['Source ID']),
                    'type': row.get('Source Type', '')
                }
                for _, row in df.iterrows()
                if pd.notna(row.get('Source Name'))
            }
        else:
            data[mapping_sheet] = {
                row['Source Name']: {'id': str(row['Source ID'])}
                for _, row in df.iterrows()
                if pd.notna(row.get('Source Name'))
            }

        print(f"  ✓ {mapping_sheet}: {len(data[mapping_sheet])} loaded")

    return data


def load_target_data_from_xlsx():
    """Load target data from converted xlsx file (pre-import)."""
    print("\n📊 Loading Target Data...")
    print("-" * 80)

    target_xlsx = TARGET_PRE_DIR / 'target_data_pre_import_converted.xlsx'

    if not target_xlsx.exists():
        print(f"  ⚠ Target data file not found: {target_xlsx}")
        print("    Run: python3 convert_data_to_xlsx.py --target-pre")
        return {}

    data = {}
    xls = pd.ExcelFile(target_xlsx)

    # Sheet name mappings
    sheet_mappings = {
        'CustomFields': 'CustomFields',
        'Statuses': 'Status',
        'IssueTypes': 'IssueTypes',
        'IssueLinkTypes': 'IssueLinkTypes',
        'Resolutions': 'Resolutions'
    }

    for xlsx_sheet, mapping_sheet in sheet_mappings.items():
        if xlsx_sheet not in xls.sheet_names:
            continue

        df = pd.read_excel(target_xlsx, sheet_name=xlsx_sheet)

        if xlsx_sheet == 'CustomFields':
            data[mapping_sheet] = {
                row['Target Name']: {
                    'id': str(row['Target ID']),
                    'type': row.get('Field Type', '')
                }
                for _, row in df.iterrows()
                if pd.notna(row.get('Target Name'))
            }
        else:
            data[mapping_sheet] = {
                row['Target Name']: {'id': str(row['Target ID'])}
                for _, row in df.iterrows()
                if pd.notna(row.get('Target Name'))
            }

        print(f"  ✓ {mapping_sheet}: {len(data[mapping_sheet])} loaded")

    return data


def similarity_ratio(str1, str2):
    """Calculate similarity ratio between two strings."""
    if not str1 or not str2:
        return 0
    return SequenceMatcher(None, str1.lower().strip(), str2.lower().strip()).ratio()


def find_fuzzy_match(source_name, target_dict, threshold=0.85, excluded_targets=None):
    """Find fuzzy match in target dictionary, excluding reserved targets."""
    best_match = None
    best_ratio = 0
    excluded_targets = excluded_targets or set()

    for target_name in target_dict.keys():
        # Skip targets that are reserved (exact matches with other sources)
        if target_name in excluded_targets:
            continue
        ratio = similarity_ratio(source_name, target_name)
        if ratio > best_ratio and ratio >= threshold:
            best_ratio = ratio
            best_match = target_name

    return best_match, best_ratio


def find_top_fuzzy_matches(source_name, target_dict, threshold=0.6, top_n=3, source_type=None, excluded_targets=None):
    """Find top N fuzzy matches for suggestions.

    If source_type is provided, only return matches with compatible types.
    Excludes targets in excluded_targets set (reserved for exact matches).
    """
    matches = []
    source_type_normalized = normalize_field_type(source_type) if source_type else None
    excluded_targets = excluded_targets or set()

    for target_name, target_info in target_dict.items():
        # Skip targets that are reserved (exact matches with other sources)
        if target_name in excluded_targets:
            continue

        # If source_type provided, filter by type compatibility
        if source_type_normalized:
            target_type = target_info.get('type', '')
            target_type_normalized = normalize_field_type(target_type)
            if source_type_normalized != target_type_normalized:
                continue  # Skip incompatible types

        ratio = similarity_ratio(source_name, target_name)
        if ratio >= threshold:
            matches.append((target_name, ratio))

    # Sort by ratio descending
    matches.sort(key=lambda x: x[1], reverse=True)

    return matches[:top_n]


def process_sheet(df, sheet_name, source_data, target_data, snapshot_objects):
    """Process a single sheet - enrich IDs, detect matches, add suggestions.

    Returns:
        tuple: (processed_df, stats, used_targets)
        - used_targets: set of target names that have been matched (exact or fuzzy)
          These should not be available for fuzzy matching by subsequent sources.
    """
    print(f"\n📝 Processing {sheet_name}...")
    print("-" * 80)

    stats = {
        'enriched_source_ids': 0,
        'enriched_target_ids': 0,
        'auto_matched': 0,
        'exact_matches': 0,
        'fuzzy_matches': 0,
        'manual_matches': 0,
        'no_matches': 0,
        'conflicts': 0,
        'skipped_system_fields': 0
    }

    source_lookup = source_data.get(sheet_name, {})
    target_lookup = target_data.get(sheet_name, {})
    snapshot_names = snapshot_objects.get(sheet_name, set())

    # Track target mappings for conflict detection
    target_to_sources = {}

    # Track rows to drop (System fields)
    rows_to_drop = []

    # === BUILD RESERVED TARGETS SET ===
    # These are target objects that have exact name matches with ANY source object
    # This includes:
    # 1. Global source objects from source API (source_lookup)
    # 2. Objects from CMJ snapshot (snapshot_names)
    # For CustomFields, also require exact type match
    # These cannot be used as mapping targets for other source objects
    reserved_targets = set()

    # Check source API objects
    for source_name, source_info in source_lookup.items():
        for target_name, target_info in target_lookup.items():
            if source_name.lower() == target_name.lower():
                if sheet_name == 'CustomFields':
                    # For CustomFields, also check type compatibility
                    source_type = source_info.get('type', '')
                    target_type = target_info.get('type', '')
                    source_type_normalized = normalize_field_type(source_type)
                    target_type_normalized = normalize_field_type(target_type)
                    if source_type_normalized == target_type_normalized:
                        reserved_targets.add(target_name)
                else:
                    reserved_targets.add(target_name)

    # Also check CMJ snapshot objects (they may have exact target matches too)
    # This prevents fuzzy matching to targets that will later get exact matches from snapshot
    for snapshot_name in snapshot_names:
        for target_name in target_lookup.keys():
            if snapshot_name.lower() == target_name.lower():
                if sheet_name != 'CustomFields':
                    # For non-CustomFields, name match is sufficient
                    reserved_targets.add(target_name)
                # For CustomFields, we can't easily check type here, so skip
                # (the snapshot doesn't have type info readily available)

    if reserved_targets:
        print(f"  ℹ Reserved targets (exact source matches): {len(reserved_targets)}")

    # === TRACK USED TARGETS ===
    # Start with reserved targets, then add any target that gets matched
    # This prevents the same target from being fuzzy-matched to multiple sources
    used_targets = set(reserved_targets)

    # Sort dataframe by Source Name for deterministic processing order
    # This ensures consistent fuzzy matching results across machines
    df = df.sort_values('Source Name', key=lambda x: x.str.lower().fillna('')).reset_index(drop=True)

    for idx, row in df.iterrows():
        source_name = row.get('Source Name')
        target_name = row.get('Target Name')

        if pd.isna(source_name) or str(source_name).strip() == '':
            continue

        source_name = str(source_name).strip()

        # === SKIP SYSTEM FIELDS (CustomFields only) ===
        # System fields are built-in Jira fields that exist in every instance
        if sheet_name == 'CustomFields':
            source_type = str(row.get('Source Type', '')).strip()
            if source_type.lower() == 'system field':
                rows_to_drop.append(idx)
                stats['skipped_system_fields'] += 1
                continue

        # === ENRICH SOURCE ID ===
        if pd.isna(row.get('Source ID')) or str(row.get('Source ID')).strip() == '':
            if source_name in source_lookup:
                df.at[idx, 'Source ID'] = source_lookup[source_name]['id']
                stats['enriched_source_ids'] += 1

        # === ENRICH SOURCE TYPE (for CustomFields) ===
        if sheet_name == 'CustomFields':
            if pd.isna(row.get('Source Type')) or str(row.get('Source Type')).strip() == '':
                if source_name in source_lookup:
                    df.at[idx, 'Source Type'] = source_lookup[source_name].get('type', '')

        # === MARK ON SCREEN STATUS ===
        # Only preserve existing 'Yes' values from customer mapping
        # Default to 'No' if not already set (including CMJ snapshot additions)
        if pd.isna(row.get('On Screen')) or str(row.get('On Screen')).strip() == '':
            df.at[idx, 'On Screen'] = 'No'

        # === PROCESS TARGET MATCHING ===
        # First check if Target Name is provided by customer
        has_target = pd.notna(target_name) and str(target_name).strip() != ''

        # If no target provided, try to auto-match from target data
        if not has_target and target_lookup:
            # Try exact name match first (case-insensitive)
            for tgt_name in target_lookup.keys():
                if source_name.lower() == tgt_name.lower():
                    target_name = tgt_name
                    has_target = True
                    stats['auto_matched'] += 1
                    break

            # If no exact match, try fuzzy match (excluding used targets)
            if not has_target:
                fuzzy_match, ratio = find_fuzzy_match(source_name, target_lookup, threshold=0.85, excluded_targets=used_targets)
                if fuzzy_match:
                    target_name = fuzzy_match
                    has_target = True
                    stats['auto_matched'] += 1
                    # Mark this target as used so it can't be fuzzy-matched again
                    used_targets.add(fuzzy_match)

        if has_target:
            target_name = str(target_name).strip()

            # Set Target Name if it was auto-matched
            if pd.isna(row.get('Target Name')) or str(row.get('Target Name')).strip() == '':
                df.at[idx, 'Target Name'] = target_name

            # Enrich Target ID
            if pd.isna(row.get('Target ID')) or str(row.get('Target ID')).strip() == '':
                if target_name in target_lookup:
                    df.at[idx, 'Target ID'] = target_lookup[target_name]['id']
                    stats['enriched_target_ids'] += 1

            # Enrich Target Type (for CustomFields)
            enriched_target_type = ''
            if sheet_name == 'CustomFields':
                if pd.isna(row.get('Target Type')) or str(row.get('Target Type')).strip() == '':
                    if target_name in target_lookup:
                        enriched_target_type = target_lookup[target_name].get('type', '')
                        df.at[idx, 'Target Type'] = enriched_target_type
                else:
                    enriched_target_type = str(row.get('Target Type', '')).strip()

            # Track for conflict detection
            if target_name not in target_to_sources:
                target_to_sources[target_name] = []
            target_to_sources[target_name].append(source_name)

            # Determine match type
            is_exact_match = False

            if sheet_name == 'CustomFields':
                # For fields, check name AND type (normalized for comparison)
                source_type = str(row.get('Source Type', '')).strip()
                # Use the enriched target type (not from row which may be empty)
                target_type = enriched_target_type

                # Normalize both types for comparison (handles GUI vs API format)
                source_type_normalized = normalize_field_type(source_type)
                target_type_normalized = normalize_field_type(target_type)

                if source_name.lower() == target_name.lower() and source_type_normalized == target_type_normalized:
                    is_exact_match = True
            else:
                # For other objects, just check name
                if source_name.lower() == target_name.lower():
                    is_exact_match = True

            if is_exact_match:
                df.at[idx, 'Match Type'] = 'EXACT_MATCH'
                df.at[idx, 'Confidence'] = 'High'
                if pd.isna(row.get('Migration Action')):
                    df.at[idx, 'Migration Action'] = 'MAP'
                stats['exact_matches'] += 1
            else:
                # Check if it's a fuzzy match (high similarity but not exact)
                ratio = similarity_ratio(source_name, target_name)

                # For CustomFields, fuzzy match also requires type compatibility
                types_compatible = True
                if sheet_name == 'CustomFields':
                    source_type = str(row.get('Source Type', '')) if pd.notna(row.get('Source Type')) else ''
                    target_type = str(row.get('Target Type', '')) if pd.notna(row.get('Target Type')) else ''
                    source_type_normalized = normalize_field_type(source_type)
                    target_type_normalized = normalize_field_type(target_type)
                    types_compatible = (source_type_normalized == target_type_normalized)

                if ratio >= 0.85 and types_compatible:
                    df.at[idx, 'Match Type'] = 'FUZZY_MATCH'
                    df.at[idx, 'Confidence'] = 'Medium' if ratio >= 0.9 else 'Low'
                    stats['fuzzy_matches'] += 1
                    if pd.isna(row.get('Migration Action')):
                        df.at[idx, 'Migration Action'] = 'MAP'
                elif ratio >= 0.85 and not types_compatible:
                    # Name matches but types don't - treat as NO_MATCH and clear target columns
                    df.at[idx, 'Match Type'] = 'NO_MATCH'
                    df.at[idx, 'Confidence'] = 'N/A'
                    df.at[idx, 'Target Name'] = None
                    df.at[idx, 'Target ID'] = None
                    df.at[idx, 'Target Type'] = None
                    if pd.isna(row.get('Migration Action')):
                        df.at[idx, 'Migration Action'] = 'CREATE'
                    stats['no_matches'] += 1
                else:
                    df.at[idx, 'Match Type'] = 'MANUAL_MATCH'
                    df.at[idx, 'Confidence'] = 'Medium'
                    stats['manual_matches'] += 1
                    if pd.isna(row.get('Migration Action')):
                        df.at[idx, 'Migration Action'] = 'MAP'

        else:
            # No target found - mark as NO_MATCH and add suggestions
            df.at[idx, 'Match Type'] = 'NO_MATCH'
            df.at[idx, 'Confidence'] = 'N/A'
            if pd.isna(row.get('Migration Action')):
                df.at[idx, 'Migration Action'] = 'CREATE'
            stats['no_matches'] += 1

            # Add fuzzy suggestions (lower threshold for suggestions)
            # For CustomFields, filter suggestions by compatible types
            # Exclude used targets (exact matches and already fuzzy-matched)
            suggestion_source_type = None
            if sheet_name == 'CustomFields':
                suggestion_source_type = str(row.get('Source Type', '')) if pd.notna(row.get('Source Type')) else None
            suggestions = find_top_fuzzy_matches(source_name, target_lookup, threshold=0.6, top_n=3, source_type=suggestion_source_type, excluded_targets=used_targets)
            for i, (suggestion, ratio) in enumerate(suggestions):
                col_name = f'Target Suggestion #{i+1}'
                if col_name in df.columns:
                    df.at[idx, col_name] = f"{suggestion} ({ratio:.0%})"

    # === DROP SYSTEM FIELDS ===
    if rows_to_drop:
        df = df.drop(rows_to_drop)
        print(f"  ⏭ Skipped {stats['skipped_system_fields']} System fields (built-in Jira fields)")

    # === CONFLICT DETECTION ===
    conflicts = []
    for target_name, sources in target_to_sources.items():
        if len(sources) > 1:
            conflicts.append((target_name, sources))
            stats['conflicts'] += 1

    if conflicts:
        print(f"  ⚠ CONFLICTS DETECTED ({len(conflicts)}):")
        for target, sources in conflicts[:5]:  # Show first 5
            print(f"    Target '{target}' ← Sources: {sources}")
        if len(conflicts) > 5:
            print(f"    ... and {len(conflicts) - 5} more")

    # Print stats
    print(f"  ✓ Enriched {stats['enriched_source_ids']} source IDs")
    print(f"  ✓ Enriched {stats['enriched_target_ids']} target IDs")
    if stats['auto_matched'] > 0:
        print(f"  ✓ Auto-matched {stats['auto_matched']} targets from target data")
    print(f"  ✓ Exact matches: {stats['exact_matches']}")
    print(f"  ✓ Fuzzy matches: {stats['fuzzy_matches']}")
    print(f"  ✓ Manual matches: {stats['manual_matches']}")
    print(f"  ✓ No matches: {stats['no_matches']}")

    return df, stats, used_targets


def parse_cmj_snapshots():
    """Parse CMJ snapshot CSVs for objects in the snapshot."""
    print("\n📊 Parsing CMJ Snapshots...")
    print("-" * 80)

    if not CMJ_SNAPSHOT_DIR.exists():
        print(f"  ⚠ CMJ snapshot directory not found: {CMJ_SNAPSHOT_DIR}")
        return {}

    objects_found = {
        'Status': set(),
        'CustomFields': set(),
        'IssueTypes': set(),
        'Resolutions': set(),
        'IssueLinkTypes': set()
    }

    csv_files = list(CMJ_SNAPSHOT_DIR.glob('*.csv'))

    if not csv_files:
        print("  ⚠ No CSV files found in snapshot directory")
        return objects_found

    for csv_file in csv_files:
        print(f"  Reading: {csv_file.name}")

        try:
            with open(csv_file, 'r', encoding='utf-8') as f:
                reader = csv.DictReader(f)
                for row in reader:
                    category = row.get('category', '')
                    obj_type = row.get('type', '')
                    name = row.get('name', '')
                    change_kind = row.get('changeKind', '')

                    # Include objects that were Added or Changed
                    if change_kind not in ['Added', 'Changed']:
                        continue

                    # Map category/type to our sheet names
                    if category == 'Statuses' or obj_type == 'Status':
                        objects_found['Status'].add(name)
                    elif category == 'Custom Fields' or 'Field' in obj_type:
                        objects_found['CustomFields'].add(name)
                    elif obj_type == 'Issue Type':
                        objects_found['IssueTypes'].add(name)
                    elif obj_type == 'Issue Link Type':
                        objects_found['IssueLinkTypes'].add(name)
                    elif category == 'Resolutions' or obj_type == 'Resolution':
                        objects_found['Resolutions'].add(name)
                    elif category == 'Issue Attributes' and obj_type == 'Resolution':
                        objects_found['Resolutions'].add(name)
        except Exception as e:
            print(f"  ⚠ Error reading {csv_file.name}: {e}")

    for obj_type, names in objects_found.items():
        if names:
            print(f"  ✓ {obj_type}: {len(names)} objects found")

    return objects_found


def add_snapshot_objects(df, sheet_name, snapshot_objects, source_data, target_data, used_targets=None):
    """Add objects from CMJ snapshots that aren't already in mapping.

    Args:
        used_targets: set of target names already matched (exact or fuzzy).
                     These will be excluded from fuzzy matching.
                     New matches will be added to this set.

    Returns:
        tuple: (updated_df, updated_used_targets)
    """
    print(f"\n➕ Checking for additional snapshot objects in {sheet_name}...")

    existing_sources = set(df['Source Name'].dropna().str.strip().str.lower())
    source_lookup = source_data.get(sheet_name, {})
    target_lookup = target_data.get(sheet_name, {})

    # Use provided used_targets or build from scratch if not provided
    if used_targets is None:
        used_targets = set()
        # Build reserved targets set (exact matches that cannot be reused)
        for source_name, source_info in source_lookup.items():
            for target_name, target_info in target_lookup.items():
                if source_name.lower() == target_name.lower():
                    if sheet_name == 'CustomFields':
                        source_type = source_info.get('type', '')
                        target_type = target_info.get('type', '')
                        source_type_normalized = normalize_field_type(source_type)
                        target_type_normalized = normalize_field_type(target_type)
                        if source_type_normalized == target_type_normalized:
                            used_targets.add(target_name)
                    else:
                        used_targets.add(target_name)

    new_objects = snapshot_objects.get(sheet_name, set())
    to_add = [obj for obj in new_objects if obj.lower().strip() not in existing_sources]
    # Sort for deterministic processing order (consistent fuzzy matching across machines)
    to_add = sorted(to_add, key=str.lower)

    if not to_add:
        print(f"  ℹ No additional objects to add")
        return df, used_targets

    print(f"  Found {len(to_add)} objects in snapshot not in customer mapping")

    new_rows = []

    for obj_name in to_add:
        # Try exact match in target
        target_match = None
        match_type = 'NO_MATCH'
        confidence = 'N/A'
        migration_action = 'CREATE'
        target_id = ''
        source_type = ''
        target_type = ''

        # Get source info
        source_id = source_lookup.get(obj_name, {}).get('id', '')
        if sheet_name == 'CustomFields' and obj_name in source_lookup:
            source_type = source_lookup[obj_name].get('type', '')

        # Check for exact match
        if obj_name in target_lookup:
            is_exact = False

            if sheet_name == 'CustomFields':
                candidate_target_type = target_lookup[obj_name].get('type', '')
                # Normalize both types for comparison (handles GUI vs API format)
                source_type_normalized = normalize_field_type(source_type)
                target_type_normalized = normalize_field_type(candidate_target_type)
                if source_type_normalized == target_type_normalized:
                    is_exact = True
                    target_type = candidate_target_type
                # If types don't match, leave as NO_MATCH (will CREATE) and don't set target_type
            else:
                is_exact = True

            if is_exact:
                target_match = obj_name
                match_type = 'EXACT_MATCH'
                confidence = 'High'
                migration_action = 'MAP'
                target_id = target_lookup[obj_name]['id']

        # If no exact match, try fuzzy (excluding used targets)
        if match_type == 'NO_MATCH':
            fuzzy_match, ratio = find_fuzzy_match(obj_name, target_lookup, threshold=0.85, excluded_targets=used_targets)
            if fuzzy_match:
                # For CustomFields, fuzzy match also requires type compatibility
                types_compatible = True
                if sheet_name == 'CustomFields':
                    candidate_target_type = target_lookup[fuzzy_match].get('type', '')
                    source_type_normalized = normalize_field_type(source_type)
                    target_type_normalized = normalize_field_type(candidate_target_type)
                    types_compatible = (source_type_normalized == target_type_normalized)

                if types_compatible:
                    target_match = fuzzy_match
                    match_type = 'FUZZY_MATCH'
                    confidence = 'Medium' if ratio >= 0.9 else 'Low'
                    migration_action = 'MAP'
                    target_id = target_lookup[fuzzy_match]['id']
                    # Mark this target as used so it can't be fuzzy-matched again
                    used_targets.add(fuzzy_match)
                    if sheet_name == 'CustomFields':
                        target_type = candidate_target_type

        new_row = {
            'Project': 'CMJ_SNAPSHOT',
            'Source ID': source_id,
            'Source Name': obj_name,
            'Target ID': target_id,
            'Target Name': target_match if target_match else '',
            'Match Type': match_type,
            'Confidence': confidence,
            'Migration Action': migration_action,
            'On Screen': 'No'  # CMJ snapshot objects default to No (not on screens)
        }

        if sheet_name == 'CustomFields':
            new_row['Source Type'] = source_type
            new_row['Target Type'] = target_type
        elif sheet_name == 'Status':
            new_row['Workflow Name'] = ''  # Not applicable for snapshot additions

        new_rows.append(new_row)
        status = f"→ {target_match}" if target_match else "(create)"
        print(f"  + {obj_name} {status} [{match_type}]")

    if new_rows:
        new_df = pd.DataFrame(new_rows)
        df = pd.concat([df, new_df], ignore_index=True)
        print(f"  ✓ Added {len(new_rows)} objects from snapshot")

    return df, used_targets


def remove_duplicates(df, sheet_name):
    """Remove duplicate objects based on Source Name (case-insensitive)."""
    if df.empty or 'Source Name' not in df.columns:
        return df

    original_count = len(df)

    df['_source_name_lower'] = df['Source Name'].astype(str).str.strip().str.lower()
    df_deduped = df.drop_duplicates(subset=['_source_name_lower'], keep='first')
    df_deduped = df_deduped.drop(columns=['_source_name_lower'])

    duplicates_removed = original_count - len(df_deduped)

    if duplicates_removed > 0:
        print(f"  🗑️ Removed {duplicates_removed} duplicates from {sheet_name}")

    return df_deduped


def get_column_letter(col_num):
    """Convert column number to Excel column letter."""
    result = ""
    while col_num > 0:
        col_num, remainder = divmod(col_num - 1, 26)
        result = chr(65 + remainder) + result
    return result


def write_output_file(processed_sheets, output_file, project_key):
    """Write processed sheets to xlsx with formatting."""
    print(f"\n{'=' * 80}")
    print("WRITING PROCESSED FILE")
    print("=" * 80)

    # Ensure output directory exists
    output_file.parent.mkdir(parents=True, exist_ok=True)

    with pd.ExcelWriter(output_file, engine='openpyxl') as writer:
        for sheet_name, df in processed_sheets.items():
            df.to_excel(writer, sheet_name=sheet_name, index=False)

            # Auto-adjust column widths
            worksheet = writer.sheets[sheet_name]
            for idx, col in enumerate(df.columns):
                max_length = max(
                    df[col].astype(str).apply(len).max() if len(df) > 0 else 0,
                    len(col)
                ) + 2
                col_letter = get_column_letter(idx + 1)
                worksheet.column_dimensions[col_letter].width = min(max_length, 50)

        # Add metadata sheet
        metadata = pd.DataFrame([
            {'Property': 'Project Key', 'Value': project_key},
            {'Property': 'Processed Date', 'Value': datetime.now().strftime('%Y-%m-%d %H:%M:%S')},
            {'Property': 'Sheets', 'Value': ', '.join(processed_sheets.keys())},
            {'Property': 'Total Records', 'Value': sum(len(df) for df in processed_sheets.values())}
        ])
        metadata.to_excel(writer, sheet_name='_Metadata', index=False)

    print(f"\n✓ Processed file saved: {output_file}")


def process_single_mapping_file(input_file, project_key, source_data, target_data, snapshot_objects):
    """Process a single customer mapping file and return stats."""
    print(f"\n{'=' * 80}")
    print(f"PROCESSING PROJECT: {project_key}")
    print(f"{'=' * 80}")
    print(f"📁 Input: {input_file.name}")

    output_file = OUTPUT_DIR / f'{project_key}_Customer_Mapping_PROCESSED.xlsx'

    # Read customer mapping
    try:
        xls = pd.ExcelFile(input_file)
        print(f"  ✓ Found {len(xls.sheet_names)} sheets: {', '.join(xls.sheet_names)}")
    except Exception as e:
        print(f"\n❌ Error reading mapping file: {e}")
        return None, None

    # Process each sheet
    processed_sheets = {}
    all_stats = {}

    for sheet_name in xls.sheet_names:
        if sheet_name.startswith('_'):
            continue  # Skip metadata sheets

        df = pd.read_excel(input_file, sheet_name=sheet_name)

        print(f"\n  Processing: {sheet_name}")

        # Process existing mappings
        # Returns used_targets set to prevent same target from being fuzzy-matched multiple times
        df, stats, used_targets = process_sheet(df, sheet_name, source_data, target_data, snapshot_objects)
        all_stats[sheet_name] = stats

        # Add snapshot objects not in mapping
        # Pass used_targets to prevent duplicate fuzzy matches
        df, used_targets = add_snapshot_objects(df, sheet_name, snapshot_objects, source_data, target_data, used_targets)

        # Remove duplicates
        df = remove_duplicates(df, sheet_name)

        processed_sheets[sheet_name] = df

    # Write output
    write_output_file(processed_sheets, output_file, project_key)

    # Calculate totals for this file
    total_records = sum(len(df) for df in processed_sheets.values())
    total_conflicts = sum(s.get('conflicts', 0) for s in all_stats.values())

    print(f"\n  ✓ {project_key}: {total_records} records, {total_conflicts} conflicts")
    print(f"  ✓ Output: {output_file.name}")

    return processed_sheets, all_stats


def main():
    """Main processing function - supports multiple mapping files."""
    parser = argparse.ArgumentParser(description='Process Customer Mapping File(s)')
    parser.add_argument('--mapping-file', type=str, help='Path to specific customer mapping xlsx file')
    args = parser.parse_args()

    print("=" * 80)
    print("CUSTOMER MAPPING PROCESSOR")
    print("=" * 80)
    print(f"Timestamp: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")

    # Load field type mapping from config
    load_field_type_mapping()

    # Determine which files to process
    if args.mapping_file:
        # Single file mode (explicit path)
        input_file = Path(args.mapping_file)
        project_key = input_file.stem.replace('_Customer_Mapping', '')
        if not input_file.exists():
            print(f"\n❌ Error: Mapping file not found: {input_file}")
            return
        mapping_files = [(input_file, project_key)]
    else:
        # Auto-detect all mapping files
        print("\n🔍 Auto-detecting customer mapping files...")
        mapping_files = find_customer_mapping_files()
        if not mapping_files:
            print("\n❌ Error: No customer mapping files found")
            print(f"   Place file(s) named {{PROJECT_KEY}}_Customer_Mapping.xlsx in:")
            print(f"   {SOURCE_DATA_DIR}")
            return

    # Report what we found
    print(f"\n📋 Found {len(mapping_files)} mapping file(s):")
    for f, k in mapping_files:
        print(f"   - {f.name} (Project: {k})")

    # Load shared data sources ONCE
    print("\n" + "-" * 80)
    print("LOADING SHARED DATA SOURCES")
    print("-" * 80)
    source_data = load_source_data_from_xlsx()
    target_data = load_target_data_from_xlsx()
    snapshot_objects = parse_cmj_snapshots()

    # Check if we have necessary data
    if not source_data:
        print("\n⚠ Warning: No source data loaded. Run convert_data_to_xlsx.py --source first.")
    if not target_data:
        print("\n⚠ Warning: No target data loaded. Run convert_data_to_xlsx.py --target-pre first.")

    # Process each mapping file
    all_results = {}
    grand_total_records = 0
    grand_total_conflicts = 0

    for input_file, project_key in mapping_files:
        processed_sheets, all_stats = process_single_mapping_file(
            input_file, project_key, source_data, target_data, snapshot_objects
        )
        if processed_sheets:
            all_results[project_key] = {
                'sheets': processed_sheets,
                'stats': all_stats,
                'output_file': OUTPUT_DIR / f'{project_key}_Customer_Mapping_PROCESSED.xlsx'
            }
            grand_total_records += sum(len(df) for df in processed_sheets.values())
            grand_total_conflicts += sum(s.get('conflicts', 0) for s in all_stats.values())

    # Print grand summary
    print(f"\n{'=' * 80}")
    print("PROCESSING COMPLETE - ALL PROJECTS")
    print("=" * 80)

    print(f"\nProjects processed: {len(all_results)}")
    for project_key, result in all_results.items():
        records = sum(len(df) for df in result['sheets'].values())
        conflicts = sum(s.get('conflicts', 0) for s in result['stats'].values())
        print(f"  - {project_key}: {records} records, {conflicts} conflicts")

    print(f"\nGrand total: {grand_total_records} records, {grand_total_conflicts} conflicts")

    print(f"\nOutput files:")
    for project_key, result in all_results.items():
        print(f"  - {result['output_file'].name}")

    print(f"\nNext steps:")
    print(f"  1. Customer reviews each _PROCESSED.xlsx file")
    print(f"  2. Customer saves as _PROCESSED_Reviewed.xlsx")
    print(f"  3. Run: python3 validate_customer_review.py")
    print("=" * 80)


if __name__ == "__main__":
    main()
