#!/usr/bin/env python3
"""
Filter Reviewed Mapping for CMJ Template

Reads the customer-reviewed mapping file (_PROCESSED_Reviewed.xlsx):
1. Normalizes Migration Action case (e.g., 'Map' → 'MAP')
2. Enriches missing Target IDs from converted target data
3. Excludes EXACT_MATCH objects (CMJ auto-handles these)
4. Excludes objects NOT in CMJ snapshot (CMJ won't process them)
5. Outputs filtered file for CMJ template generation

Usage:
    python3 filter_for_cmj_template.py
"""

import pandas as pd
import csv
from pathlib import Path
from datetime import datetime


# Base paths (relative to script location: scripts/ -> cmj_template/)
BASE_DIR = Path(__file__).resolve().parent.parent
SOURCE_DATA_DIR = BASE_DIR / 'source_data'
TARGET_DATA_DIR = BASE_DIR / 'target_data'
TARGET_PRE_DIR = TARGET_DATA_DIR / 'pre_import'
CMJ_SNAPSHOT_DIR = SOURCE_DATA_DIR / 'cmj_snapshot_objs'
OUTPUT_DIR = BASE_DIR / 'customer_review'


def parse_cmj_snapshots():
    """Parse CMJ snapshot CSVs to get objects that need remapping."""
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


def find_reviewed_files():
    """Auto-detect all customer-reviewed mapping files.

    Returns a list of (file_path, project_key) tuples for all found files.
    """
    pattern = '*_Customer_Mapping_PROCESSED_Reviewed.xlsx'
    matches = list(OUTPUT_DIR.glob(pattern))

    if not matches:
        print(f"  ⚠ No reviewed files found matching: {pattern}")
        print(f"    Looking in: {OUTPUT_DIR}")
        return []

    result = []
    for match in sorted(matches):
        project_key = match.stem.replace('_Customer_Mapping_PROCESSED_Reviewed', '')
        result.append((match, project_key))

    return result


def load_target_lookups():
    """Load target data from converted xlsx for ID enrichment."""
    target_xlsx = TARGET_PRE_DIR / 'target_data_pre_import_converted.xlsx'

    if not target_xlsx.exists():
        print(f"  ⚠ Target data file not found: {target_xlsx}")
        return {}

    data = {}
    xls = pd.ExcelFile(target_xlsx)

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

        print(f"  ✓ {mapping_sheet}: {len(data[mapping_sheet])} target entries loaded")

    return data


def normalize_and_enrich(df, sheet_name, target_lookup):
    """Normalize Migration Action case and enrich missing Target IDs."""
    if df.empty:
        return df, 0, 0

    normalized_count = 0
    enriched_count = 0

    lookup = target_lookup.get(sheet_name, {})

    for idx, row in df.iterrows():
        # === NORMALIZE MIGRATION ACTION CASE ===
        action = row.get('Migration Action')
        if pd.notna(action):
            action_upper = str(action).strip().upper()
            if str(action).strip() != action_upper:
                df.at[idx, 'Migration Action'] = action_upper
                normalized_count += 1

        # === ENRICH MISSING TARGET IDs ===
        target_name = row.get('Target Name')
        target_id = row.get('Target ID')

        if pd.notna(target_name) and str(target_name).strip() != '':
            target_name_str = str(target_name).strip()

            # Missing Target ID - look up from target data
            if pd.isna(target_id) or str(target_id).strip() == '':
                if target_name_str in lookup:
                    df.at[idx, 'Target ID'] = lookup[target_name_str]['id']
                    enriched_count += 1
                else:
                    # Try case-insensitive match
                    for tgt_name, tgt_data in lookup.items():
                        if tgt_name.lower() == target_name_str.lower():
                            df.at[idx, 'Target ID'] = tgt_data['id']
                            enriched_count += 1
                            break

            # Enrich Target Type for CustomFields - ALWAYS use lookup to ensure internal ID format
            # (Manual entries may have human-readable types like "Text Field (single line)"
            # but CMJ needs internal IDs like "com.atlassian.jira.plugin.system.customfieldtypes:textfield")
            if sheet_name == 'CustomFields':
                if target_name_str in lookup:
                    internal_type = lookup[target_name_str].get('type', '')
                    if internal_type:
                        df.at[idx, 'Target Type'] = internal_type
                else:
                    for tgt_name, tgt_data in lookup.items():
                        if tgt_name.lower() == target_name_str.lower():
                            internal_type = tgt_data.get('type', '')
                            if internal_type:
                                df.at[idx, 'Target Type'] = internal_type
                            break

    return df, normalized_count, enriched_count


def filter_sheet_for_cmj(df, sheet_name, snapshot_objects):
    """Filter sheet to exclude exact matches and objects not in CMJ snapshot.

    Only objects that are:
    1. NOT EXACT_MATCH (those auto-match in CMJ)
    2. IN the CMJ snapshot (objects not in snapshot won't be processed by CMJ)
    """
    if df.empty:
        return df, 0, 0

    excluded_exact = 0
    excluded_not_in_snapshot = 0

    if 'Match Type' not in df.columns:
        return df, 0, 0

    # Get the set of object names in the CMJ snapshot for this sheet
    snapshot_names = snapshot_objects.get(sheet_name, set())
    snapshot_names_lower = {name.lower() for name in snapshot_names}

    # Track which rows to keep
    rows_to_keep = []

    for idx, row in df.iterrows():
        source_name = row.get('Source Name', '')
        match_type = row.get('Match Type', '')

        # Exclude EXACT_MATCH (CMJ auto-handles these)
        if match_type == 'EXACT_MATCH':
            excluded_exact += 1
            continue

        # Exclude objects not in CMJ snapshot (CMJ won't process them anyway)
        # Use case-insensitive comparison
        source_name_lower = str(source_name).strip().lower() if pd.notna(source_name) else ''
        if snapshot_names_lower and source_name_lower not in snapshot_names_lower:
            excluded_not_in_snapshot += 1
            continue

        rows_to_keep.append(idx)

    filtered_df = df.loc[rows_to_keep].copy()

    return filtered_df, excluded_exact, excluded_not_in_snapshot


def get_column_letter(col_num):
    """Convert column number to Excel column letter."""
    result = ""
    while col_num > 0:
        col_num, remainder = divmod(col_num - 1, 26)
        result = chr(65 + remainder) + result
    return result


def process_single_file(input_file, project_key, target_lookup, snapshot_objects):
    """Process a single reviewed file and return filtered sheets and stats.

    Returns:
        tuple: (filtered_sheets_dict, stats_dict, normalized_count, enriched_count)
    """
    print(f"\n{'=' * 80}")
    print(f"PROCESSING FILE: {input_file.name}")
    print(f"Project: {project_key}")
    print("=" * 80)

    try:
        xls = pd.ExcelFile(input_file)
        print(f"  ✓ Found {len(xls.sheet_names)} sheets: {', '.join(xls.sheet_names)}")
    except Exception as e:
        print(f"\n❌ Error reading file: {e}")
        return {}, {}, 0, 0

    filtered_sheets = {}
    stats = {}
    total_normalized = 0
    total_enriched = 0

    for sheet_name in xls.sheet_names:
        if sheet_name.startswith('_'):
            continue

        df = pd.read_excel(input_file, sheet_name=sheet_name)
        original_count = len(df)

        print(f"\n  Sheet: {sheet_name}")
        print(f"  {'-' * 40}")

        # Add Project column to track which project each row came from
        df['Project'] = project_key

        # Step 1: Normalize and enrich
        df, normalized_count, enriched_count = normalize_and_enrich(df, sheet_name, target_lookup)
        total_normalized += normalized_count
        total_enriched += enriched_count

        if normalized_count > 0:
            print(f"    ✓ Normalized {normalized_count} Migration Action values")
        if enriched_count > 0:
            print(f"    ✓ Enriched {enriched_count} missing Target IDs")

        # Validate: check for MAP rows still missing Target ID
        if 'Migration Action' in df.columns and 'Target ID' in df.columns:
            map_no_id = df[
                (df['Migration Action'] == 'MAP') &
                (df['Target ID'].isna() | (df['Target ID'].astype(str).str.strip() == ''))
            ]
            if len(map_no_id) > 0:
                print(f"    ⚠ WARNING: {len(map_no_id)} rows have MAP action but no Target ID:")
                for _, row in map_no_id.head(5).iterrows():
                    print(f"      - {row.get('Source Name', 'N/A')} → {row.get('Target Name', 'N/A')}")
                if len(map_no_id) > 5:
                    print(f"      ... and {len(map_no_id) - 5} more")

        # Step 2: Filter out exact matches and objects not in CMJ snapshot
        filtered_df, excluded_exact, excluded_not_in_snapshot = filter_sheet_for_cmj(
            df, sheet_name, snapshot_objects
        )
        filtered_count = len(filtered_df)

        filtered_sheets[sheet_name] = filtered_df
        stats[sheet_name] = {
            'original': original_count,
            'filtered': filtered_count,
            'excluded_exact': excluded_exact,
            'excluded_not_in_snapshot': excluded_not_in_snapshot
        }

        print(f"    Total objects: {original_count}")
        print(f"    Excluded (EXACT_MATCH): {excluded_exact}")
        if excluded_not_in_snapshot > 0:
            print(f"    Excluded (not in CMJ snapshot): {excluded_not_in_snapshot}")
        print(f"    For CMJ template: {filtered_count}")

    return filtered_sheets, stats, total_normalized, total_enriched


def main():
    """Main function."""
    print("=" * 80)
    print("FILTER REVIEWED MAPPINGS FOR CMJ TEMPLATE")
    print("=" * 80)
    print(f"Timestamp: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")

    # Auto-detect all reviewed files
    print("\n🔍 Auto-detecting reviewed mapping files...")
    reviewed_files = find_reviewed_files()

    if not reviewed_files:
        print("\n❌ Error: No reviewed mapping files found")
        print(f"   Place files named {{PROJECT_KEY}}_Customer_Mapping_PROCESSED_Reviewed.xlsx in:")
        print(f"   {OUTPUT_DIR}")
        return

    print(f"\nFound {len(reviewed_files)} file(s) to process:")
    project_keys = []
    for input_file, project_key in reviewed_files:
        print(f"  - {input_file.name} (Project: {project_key})")
        project_keys.append(project_key)

    # Generate combined output filename
    if len(project_keys) == 1:
        output_file = OUTPUT_DIR / f'{project_keys[0]}_Customer_Mapping_FOR_CMJ.xlsx'
    else:
        # Use COMBINED prefix for multiple projects
        output_file = OUTPUT_DIR / 'COMBINED_Customer_Mapping_FOR_CMJ.xlsx'

    print(f"\n📁 Output: {output_file.name}")

    # Load target data for ID enrichment (shared across all files)
    print("\n📊 Loading Target Data for ID Enrichment...")
    print("-" * 80)
    target_lookup = load_target_lookups()

    if not target_lookup:
        print("  ⚠ Warning: No target data loaded. Target IDs may be incomplete.")

    # Parse CMJ snapshots to know which objects need remapping (shared across all files)
    snapshot_objects = parse_cmj_snapshots()

    if not any(snapshot_objects.values()):
        print("  ⚠ Warning: No objects found in CMJ snapshots. All non-exact matches will be included.")

    # Process each file and combine results
    combined_sheets = {}
    combined_stats = {}
    grand_total_normalized = 0
    grand_total_enriched = 0

    for input_file, project_key in reviewed_files:
        filtered_sheets, stats, normalized, enriched = process_single_file(
            input_file, project_key, target_lookup, snapshot_objects
        )

        grand_total_normalized += normalized
        grand_total_enriched += enriched

        # Combine sheets from this file with previous files
        for sheet_name, df in filtered_sheets.items():
            if sheet_name not in combined_sheets:
                combined_sheets[sheet_name] = df
            else:
                # Append to existing sheet, avoiding duplicates by Source Name
                existing_sources = set(combined_sheets[sheet_name]['Source Name'].dropna().str.strip())
                new_rows = df[~df['Source Name'].str.strip().isin(existing_sources)]
                if len(new_rows) > 0:
                    combined_sheets[sheet_name] = pd.concat(
                        [combined_sheets[sheet_name], new_rows],
                        ignore_index=True
                    )
                    print(f"    Added {len(new_rows)} unique rows to {sheet_name}")

        # Combine stats
        for sheet_name, sheet_stats in stats.items():
            if sheet_name not in combined_stats:
                combined_stats[sheet_name] = {
                    'original': 0,
                    'filtered': 0,
                    'excluded_exact': 0,
                    'excluded_not_in_snapshot': 0
                }
            for key in sheet_stats:
                combined_stats[sheet_name][key] += sheet_stats[key]

    # Write combined filtered file
    print(f"\n{'=' * 80}")
    print("WRITING COMBINED CMJ TEMPLATE FILE")
    print("=" * 80)

    output_file.parent.mkdir(parents=True, exist_ok=True)

    with pd.ExcelWriter(output_file, engine='openpyxl') as writer:
        for sheet_name, df in combined_sheets.items():
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

    print(f"\n✓ Combined CMJ template saved: {output_file}")

    # Summary
    print(f"\n{'=' * 80}")
    print("FILTERING SUMMARY")
    print("=" * 80)

    print(f"\nProjects processed: {', '.join(project_keys)}")

    total_original = sum(s['original'] for s in combined_stats.values())
    total_excluded_exact = sum(s['excluded_exact'] for s in combined_stats.values())
    total_excluded_not_in_snapshot = sum(s['excluded_not_in_snapshot'] for s in combined_stats.values())
    total_for_cmj = sum(s['filtered'] for s in combined_stats.values())

    print(f"\nTotal objects (combined):")
    print(f"  Original: {total_original}")
    print(f"  Excluded (exact matches): {total_excluded_exact}")
    if total_excluded_not_in_snapshot > 0:
        print(f"  Excluded (not in CMJ snapshot): {total_excluded_not_in_snapshot}")
    print(f"  For CMJ template: {total_for_cmj}")
    if grand_total_normalized > 0:
        print(f"  Migration Actions normalized: {grand_total_normalized}")
    if grand_total_enriched > 0:
        print(f"  Target IDs enriched: {grand_total_enriched}")

    # Per-sheet breakdown
    print(f"\nPer-sheet breakdown:")
    for sheet_name, stats in combined_stats.items():
        if stats['filtered'] > 0:
            print(f"  {sheet_name}: {stats['filtered']} objects for CMJ")

    print(f"\n{'=' * 80}")
    print("✅ FILTERING COMPLETE!")
    print("=" * 80)
    print(f"\nOutput: {output_file}")
    print(f"\nNext steps:")
    print(f"  1. Review {output_file.name}")
    print(f"  2. Run: python3 create_cmj_templates.py")
    print("=" * 80)


if __name__ == "__main__":
    main()
