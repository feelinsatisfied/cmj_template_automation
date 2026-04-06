#!/usr/bin/env python3
"""
Generate Cleanup Report v2.0 - With Post Import Action Support

Analyzes the processed mapping file to determine what will be deleted
after CMJ deployment.

NEW Deletion Logic:
CustomFields:
  - Delete if "Post Import Action" = "DELETE"
  - Delete if created by CMJ (in target post-import delta) - REVIEW REQUIRED

Status/Resolution/IssueType/IssueLinkType:
  - Delete if "Migration Action" = "DELETE" (explicitly marked)
  - Delete if part of import and not in use (requires manual review)

Usage:
    python3 generate_cleanup_report_v2.py
"""

import pandas as pd
import re
from pathlib import Path
from datetime import datetime


# Base paths (relative to script location: scripts/ -> cmj_template/)
BASE_DIR = Path(__file__).resolve().parent.parent
SOURCE_DATA_DIR = BASE_DIR / 'source_data'
CMJ_SNAPSHOT_DIR = SOURCE_DATA_DIR / 'cmj_snapshot_objs'
OUTPUT_DIR = BASE_DIR / 'customer_review'
TARGET_PRE_DIR = BASE_DIR / 'target_data' / 'pre_import'
TARGET_POST_DIR = BASE_DIR / 'target_data' / 'post_import'

# Custom Fields NOT on any target screens (identified from target screen analysis)
# These 43 fields were created by CMJ but are not used on any screens - safe to delete
CUSTOM_FIELDS_NOT_ON_SCREEN = {
    '13416', '13417', '13418', '13419', '13420', '13421', '13422', '13423',
    '13424', '13425', '13426', '13427', '13428', '13429', '13430', '13431',
    '13432', '13433', '13434', '13435', '13436', '13437', '13438', '13439',
    '13440', '13441', '13442', '13443', '13444', '13445', '13446', '13447',
    '13448', '13449', '13450', '13451', '13452', '13453', '13454', '13455',
    '13456', '13457', '13458'
}


def parse_issue_types_in_workflows():
    """Parse CMJ snapshot CSVs to find issue types assigned to workflows.

    Parses Workflow Scheme entries from CMJ snapshot CSV files to extract
    issue types that are assigned to workflows. These issue types should be
    protected from deletion since deleting them would break the workflows.

    Returns:
        set: Issue type names that are assigned to workflows
    """
    issue_types_in_workflows = set()

    if not CMJ_SNAPSHOT_DIR.exists():
        print(f"  ⚠ CMJ snapshot directory not found: {CMJ_SNAPSHOT_DIR}")
        return issue_types_in_workflows

    import csv

    for csv_file in CMJ_SNAPSHOT_DIR.glob('*.csv'):
        try:
            with open(csv_file, 'r', encoding='utf-8') as f:
                reader = csv.DictReader(f)
                for row in reader:
                    obj_type = row.get('type', '')
                    change_descriptors = row.get('changeDescriptors', '')

                    # Look for Workflow Scheme entries
                    if obj_type == 'Workflow Scheme' and change_descriptors:
                        # Parse patterns like: 'IssueTypeName' assigned to 'WorkflowName'.
                        # Example: 'Defect' assigned to 'MNHREPM: Defect Workflow'.
                        pattern = r"'([^']+)' assigned to '[^']+'"
                        matches = re.findall(pattern, change_descriptors)
                        for issue_type_name in matches:
                            # Skip "Default Workflow" entries
                            if issue_type_name != 'Default Workflow':
                                issue_types_in_workflows.add(issue_type_name)
        except Exception as e:
            print(f"  ⚠ Error reading {csv_file.name}: {e}")

    return issue_types_in_workflows


def parse_target_rtf_ids(rtf_path):
    """Parse Target IDs from an RTF file exported from Jira API."""
    if not rtf_path.exists():
        return set()

    with open(rtf_path, 'r', errors='ignore') as f:
        content = f.read()

    # Extract quoted IDs from RTF content - pattern: "ID","Name"...
    # IDs are numeric strings at the start of each record
    ids = set()
    # Match patterns like "10000","FieldName" or "10000","Name","Type"
    pattern = r'"(\d+)",'
    matches = re.findall(pattern, content)
    for m in matches:
        if m.isdigit():
            ids.add(m)
    return ids


def get_target_delta():
    """Get the delta between pre-import and post-import target data.

    Returns dict with:
        - created: IDs that exist in post but not pre (CMJ created these)
        - deleted: IDs that exist in pre but not post (CMJ removed these)
        - pre_ids: All IDs that existed before CMJ (for protection checks)
        - pre_names: All names that existed before CMJ (for protection checks)
    """
    delta = {
        'CustomFields': {'created': set(), 'deleted': set(), 'pre_ids': set(), 'pre_names': set()},
        'Status': {'created': set(), 'deleted': set(), 'pre_ids': set(), 'pre_names': set()},
        'IssueTypes': {'created': set(), 'deleted': set(), 'pre_ids': set(), 'pre_names': set()},
        'IssueLinkTypes': {'created': set(), 'deleted': set(), 'pre_ids': set(), 'pre_names': set()},
        'Resolutions': {'created': set(), 'deleted': set(), 'pre_ids': set(), 'pre_names': set()},
    }

    file_mappings = {
        'CustomFields': ('target_field_pre-import.rtf', 'target_field_post-import.rtf'),
        'Status': ('target_status_pre-import.rtf', 'target_status_post-import.rtf'),
        'IssueTypes': ('target_issuetype_pre-import.rtf', 'target_issuetype_post-import.rtf'),
        'IssueLinkTypes': ('target_issuelinktype_pre-import.rtf', 'target_issuelinktype_post-import.rtf'),
        'Resolutions': ('target_resolution_pre-import.rtf', 'target_resolution_post-import.rtf'),
    }

    for obj_type, (pre_file, post_file) in file_mappings.items():
        pre_path = TARGET_PRE_DIR / pre_file
        post_path = TARGET_POST_DIR / post_file

        pre_ids = parse_target_rtf_ids(pre_path)
        post_ids = parse_target_rtf_ids(post_path)

        delta[obj_type]['created'] = post_ids - pre_ids
        delta[obj_type]['deleted'] = pre_ids - post_ids
        delta[obj_type]['pre_ids'] = pre_ids  # Store pre-import IDs for protection

        # Parse pre-import names for additional protection
        # (protects against CMJ ID replacement where name stays the same)
        pre_details = parse_target_rtf_details(pre_path, obj_type)
        pre_names = {info.get('name') for info in pre_details.values() if info.get('name')}
        delta[obj_type]['pre_names'] = pre_names

    return delta


def find_processed_files():
    """Auto-detect all processed mapping files (prefer _Reviewed if exists).

    Returns:
        list of tuples: [(file_path, project_key), ...]
    """
    files_found = []

    # First try _Reviewed files
    pattern = '*_Customer_Mapping_PROCESSED_Reviewed.xlsx'
    matches = list(OUTPUT_DIR.glob(pattern))

    for reviewed_file in matches:
        project_key = reviewed_file.stem.replace('_Customer_Mapping_PROCESSED_Reviewed', '')
        files_found.append((reviewed_file, project_key))

    if files_found:
        return files_found

    # Fall back to _PROCESSED files
    pattern = '*_Customer_Mapping_PROCESSED.xlsx'
    matches = list(OUTPUT_DIR.glob(pattern))

    for processed_file in matches:
        project_key = processed_file.stem.replace('_Customer_Mapping_PROCESSED', '')
        files_found.append((processed_file, project_key))

    return files_found


def find_processed_file():
    """Auto-detect the processed mapping file (prefer _Reviewed if exists).

    Legacy function for backward compatibility - returns first file found.
    """
    files = find_processed_files()
    if files:
        return files[0]
    return None, None


def analyze_cleanup_v2(df, sheet_name, target_delta=None, issue_types_in_workflows=None):
    """Analyze what will be deleted vs kept in cleanup (v2 logic).

    Args:
        df: DataFrame from the processed mapping file
        sheet_name: Name of the sheet (CustomFields, Status, etc.)
        target_delta: Dict with 'created' and 'deleted' sets of Target IDs
        issue_types_in_workflows: Set of issue type names that are in workflows (protected)
    """
    issue_types_in_workflows = issue_types_in_workflows or set()
    if df.empty:
        return {
            'will_delete': pd.DataFrame(),
            'will_keep': pd.DataFrame(),
            'stats': {
                'total': 0,
                'delete_explicit': 0,
                'delete_created_unused': 0,
                'delete_post_action': 0,
                'keep_on_screen': 0,
                'keep_mapped': 0,
                'keep_in_use': 0
            }
        }

    has_on_screen = 'On Screen' in df.columns
    has_post_import_action = 'Post Import Action' in df.columns
    has_target_id = 'Target ID' in df.columns

    # Normalize Migration Action column (handle "Delete" vs "DELETE" case variations)
    if 'Migration Action' in df.columns:
        df['Migration Action'] = df['Migration Action'].str.upper()

    # Normalize Target ID to string for comparison with delta
    # Handle float IDs (e.g., 10106.0 -> '10106')
    if has_target_id:
        def normalize_id(val):
            if pd.isna(val) or val == '':
                return ''
            try:
                return str(int(float(val)))
            except (ValueError, TypeError):
                return str(val).strip()
        df['_target_id_str'] = df['Target ID'].apply(normalize_id)

    # Check if each row's Target ID was created by CMJ (in the delta)
    created_ids = target_delta.get('created', set()) if target_delta else set()
    if has_target_id and created_ids:
        df['_is_cmj_created'] = df['_target_id_str'].isin(created_ids)
    else:
        df['_is_cmj_created'] = False

    # Objects that WILL be deleted
    will_delete_list = []

    # Explicit DELETE in Migration Action
    explicit_delete = df[df['Migration Action'] == 'DELETE'].copy()
    if len(explicit_delete) > 0:
        explicit_delete['Deletion Reason'] = 'Marked DELETE in Migration Action'
        will_delete_list.append(explicit_delete)

    # DELETE in Post Import Action (CustomFields only)
    post_delete = pd.DataFrame()  # Initialize for later reference
    if has_post_import_action:
        post_delete = df[
            (df['Post Import Action'].fillna('').str.upper() == 'DELETE') &
            (df['Migration Action'] != 'DELETE')  # Don't double count
        ].copy()
        if len(post_delete) > 0:
            post_delete['Deletion Reason'] = 'Marked DELETE in Post Import Action'
            will_delete_list.append(post_delete)

    # CustomFields: Delete CMJ_SNAPSHOT items, protect project-specific items
    # IMPORTANT: Exclude Field Configuration and Field Configuration Scheme objects
    # These are Jira admin configuration objects, NOT custom fields
    if sheet_name == 'CustomFields' and 'Source Name' in df.columns:
        field_config_mask = df['Source Name'].str.contains('Field Configuration', case=False, na=False)
        if field_config_mask.any():
            excluded_count = field_config_mask.sum()
            print(f"  ⚠ Excluding {excluded_count} Field Configuration objects (not custom fields)")
            df = df[~field_config_mask].copy()

    created_off_screen = pd.DataFrame()  # Initialize for stats calculation
    cmj_snapshot_fields = pd.DataFrame()  # Initialize for CMJ_SNAPSHOT fields
    if sheet_name == 'CustomFields':
        # Get indices already marked for deletion to avoid double counting
        already_delete_idx = set()
        if len(explicit_delete) > 0:
            already_delete_idx.update(explicit_delete.index)
        if len(post_delete) > 0:
            already_delete_idx.update(post_delete.index)

        # Delete CMJ_SNAPSHOT custom fields with CREATE/SKIP action
        has_project_col = 'Project' in df.columns
        if has_project_col:
            cmj_snapshot_fields = df[
                (df['Migration Action'].isin(['CREATE', 'SKIP'])) &
                (df['Project'] == 'CMJ_SNAPSHOT') &  # Only CMJ_SNAPSHOT items
                (~df.index.isin(already_delete_idx))
            ].copy()
            if len(cmj_snapshot_fields) > 0:
                cmj_snapshot_fields['Deletion Reason'] = 'Created by CMJ (CMJ_SNAPSHOT - not project-specific)'
                will_delete_list.append(cmj_snapshot_fields)
                already_delete_idx.update(cmj_snapshot_fields.index)

        # Use target delta to identify additional fields created by CMJ (not already covered)
        created_off_screen = df[
            (df['_is_cmj_created']) &  # Created in target (based on pre/post delta)
            (~df.index.isin(already_delete_idx))
        ].copy()
        if len(created_off_screen) > 0:
            created_off_screen['Deletion Reason'] = 'Created by CMJ (review if on screens)'
            will_delete_list.append(created_off_screen)

    # For Status/Resolutions/IssueTypes: Only delete CMJ_SNAPSHOT items, protect project-specific items
    # Project-specific items (with real project keys) are in use and should be protected
    # NOTE: IssueLinkTypes are excluded from auto-deletion for safety
    created_unused = pd.DataFrame()  # Initialize for stats calculation
    issue_types_not_in_workflow = pd.DataFrame()  # Initialize for IssueTypes
    if sheet_name in ['Status', 'Resolutions', 'IssueTypes']:
        # Only delete items from CMJ_SNAPSHOT, not project-specific items
        has_project_col = 'Project' in df.columns
        if has_project_col:
            created_unused = df[
                (df['Migration Action'].isin(['CREATE', 'SKIP'])) &
                (df['Project'] == 'CMJ_SNAPSHOT') &  # Only CMJ_SNAPSHOT items
                (~df.index.isin(explicit_delete.index if len(explicit_delete) > 0 else []))
            ].copy()
        else:
            created_unused = df[
                (df['Migration Action'].isin(['CREATE', 'SKIP'])) &
                (~df.index.isin(explicit_delete.index if len(explicit_delete) > 0 else []))
            ].copy()

        # For IssueTypes, also protect those in workflows
        if sheet_name == 'IssueTypes' and issue_types_in_workflows and len(created_unused) > 0:
            in_workflow_mask = created_unused['Source Name'].isin(issue_types_in_workflows)
            # Keep track of protected ones for stats
            issue_types_not_in_workflow = created_unused[~in_workflow_mask].copy()
            created_unused = created_unused[~in_workflow_mask]  # Only delete those NOT in workflows

        if len(created_unused) > 0:
            created_unused['Deletion Reason'] = 'Created by CMJ (CMJ_SNAPSHOT - not project-specific)'
            will_delete_list.append(created_unused)

    # Combine all deletions
    if will_delete_list:
        will_delete = pd.concat(will_delete_list, ignore_index=True)
    else:
        will_delete = pd.DataFrame()

    # Objects that WILL be kept
    will_keep_list = []

    # For CustomFields: Keep project-specific items (not CMJ_SNAPSHOT)
    created_on_screen = pd.DataFrame()  # Initialize for stats calculation (kept for backward compat)
    if sheet_name == 'CustomFields':
        has_project_col = 'Project' in df.columns

        # Keep project-specific custom fields (not CMJ_SNAPSHOT)
        if has_project_col:
            project_specific_fields = df[
                (df['Migration Action'].isin(['CREATE', 'SKIP'])) &
                (df['Project'] != 'CMJ_SNAPSHOT') &  # Project-specific items
                (~df['Migration Action'].isin(['DELETE']))
            ].copy()
            if has_post_import_action and len(project_specific_fields) > 0:
                project_specific_fields = project_specific_fields[~project_specific_fields['Post Import Action'].fillna('').str.upper().isin(['DELETE'])]

            if len(project_specific_fields) > 0:
                project_specific_fields['Keep Reason'] = 'Project-specific (in use on project)'
                will_keep_list.append(project_specific_fields)
                created_on_screen = project_specific_fields  # For stats compatibility

    # For Status/Resolutions/IssueTypes: Keep project-specific items (not CMJ_SNAPSHOT)
    project_specific_keep = pd.DataFrame()  # Initialize for stats
    if sheet_name in ['Status', 'Resolutions', 'IssueTypes']:
        has_project_col = 'Project' in df.columns
        if has_project_col:
            project_specific_keep = df[
                (df['Migration Action'].isin(['CREATE', 'SKIP'])) &
                (df['Project'] != 'CMJ_SNAPSHOT') &  # Project-specific items
                (~df.index.isin(explicit_delete.index if len(explicit_delete) > 0 else []))
            ].copy()
            if len(project_specific_keep) > 0:
                project_specific_keep['Keep Reason'] = 'Project-specific (in use on project)'
                will_keep_list.append(project_specific_keep)

    # For IssueTypes: Keep those that ARE in workflows
    issue_types_in_workflow_keep = pd.DataFrame()  # Initialize for stats
    if sheet_name == 'IssueTypes' and issue_types_in_workflows:
        already_delete_idx = set()
        if len(explicit_delete) > 0:
            already_delete_idx.update(explicit_delete.index)

        create_skip_mask = df['Migration Action'].isin(['CREATE', 'SKIP'])
        not_already_deleted = ~df.index.isin(already_delete_idx)
        in_workflow_mask = df['Source Name'].isin(issue_types_in_workflows)

        issue_types_in_workflow_keep = df[
            create_skip_mask & not_already_deleted & in_workflow_mask
        ].copy()
        if len(issue_types_in_workflow_keep) > 0:
            issue_types_in_workflow_keep['Keep Reason'] = 'In workflow (protected)'
            will_keep_list.append(issue_types_in_workflow_keep)

    # Mapped objects (not created by CMJ)
    mapped = df[df['Migration Action'] == 'MAP'].copy()
    if len(mapped) > 0:
        # Check if also marked for post-import deletion
        if has_post_import_action:
            mapped_no_delete = mapped[mapped['Post Import Action'].fillna('').str.upper() != 'DELETE']
            mapped_with_delete = mapped[mapped['Post Import Action'].fillna('').str.upper() == 'DELETE']
            if len(mapped_no_delete) > 0:
                mapped_no_delete = mapped_no_delete.copy()
                mapped_no_delete['Keep Reason'] = 'Mapped to existing object'
                will_keep_list.append(mapped_no_delete)
            # Note: mapped_with_delete will be in delete list
        else:
            mapped['Keep Reason'] = 'Mapped to existing object'
            will_keep_list.append(mapped)

    # Combine all keeps
    if will_keep_list:
        will_keep = pd.concat(will_keep_list, ignore_index=True)
    else:
        will_keep = pd.DataFrame()

    # Remove temporary columns from output
    temp_cols = ['_on_screen_normalized', '_is_on_screen', '_target_id_str', '_is_cmj_created']
    for col in temp_cols:
        if col in will_delete.columns:
            will_delete = will_delete.drop(columns=[col])
        if col in will_keep.columns:
            will_keep = will_keep.drop(columns=[col])

    # Calculate stats (all DataFrames are now properly initialized)
    stats = {
        'total': len(df),
        'delete_explicit': len(explicit_delete),
        'delete_created_unused': len(created_off_screen) + len(created_unused) + len(issue_types_not_in_workflow) + len(cmj_snapshot_fields),
        'delete_post_action': len(post_delete),
        'keep_on_screen': len(created_on_screen),
        'keep_mapped': len(mapped),
        'keep_in_use': len(issue_types_in_workflow_keep),  # Issue types in workflows
        'keep_project_specific': len(project_specific_keep)  # Project-specific items
    }

    return {
        'will_delete': will_delete,
        'will_keep': will_keep,
        'stats': stats
    }


def parse_target_rtf_details(rtf_path, obj_type):
    """Parse detailed info from target RTF file."""
    if not rtf_path.exists():
        return {}

    with open(rtf_path, 'r', errors='ignore') as f:
        content = f.read()

    details = {}
    if obj_type == 'CustomFields':
        # Pattern: "ID","Name","Type"
        pattern = r'"(\d+)","([^"]*?)","([^"]*?)"'
        matches = re.findall(pattern, content)
        for m in matches:
            details[m[0]] = {'name': m[1], 'type': m[2]}
    elif obj_type in ['Status', 'IssueTypes', 'Resolutions']:
        # Pattern: "ID","Name"
        pattern = r'"(\d+)","([^"]*?)"'
        matches = re.findall(pattern, content)
        for m in matches:
            details[m[0]] = {'name': m[1]}
    elif obj_type == 'IssueLinkTypes':
        # Pattern: "ID","Name","Inward","Outward"
        pattern = r'"(\d+)","([^"]*?)","([^"]*?)","([^"]*?)"'
        matches = re.findall(pattern, content)
        for m in matches:
            details[m[0]] = {'name': m[1], 'inward': m[2], 'outward': m[3]}

    return details


def main():
    """Main function."""
    print("=" * 80)
    print("CLEANUP REPORT GENERATOR v2.0")
    print("=" * 80)
    print(f"Timestamp: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")

    # Auto-detect processed files (multi-project support)
    print("\n🔍 Auto-detecting processed mapping file(s)...")
    input_files = find_processed_files()

    if not input_files:
        print(f"❌ No processed mapping file found in: {OUTPUT_DIR}")
        return

    # Determine output filename
    if len(input_files) == 1:
        project_key = input_files[0][1]
        output_file = OUTPUT_DIR / f'{project_key}_Customer_Mapping_CLEANUP_REPORT.xlsx'
    else:
        project_key = 'COMBINED'
        output_file = OUTPUT_DIR / 'COMBINED_Customer_Mapping_CLEANUP_REPORT.xlsx'

    print(f"\n📁 Found {len(input_files)} file(s) to process:")
    for f, pk in input_files:
        print(f"  - {f.name} (Project: {pk})")
    print(f"📁 Output:  {output_file.name}")
    print(f"📋 Mode: {'MULTI-PROJECT' if len(input_files) > 1 else 'SINGLE-PROJECT'}")
    print("-" * 80)

    # Load target pre/post delta to identify objects created by CMJ
    print("\n📊 Loading target pre/post import delta...")
    target_delta = get_target_delta()
    for obj_type, delta in target_delta.items():
        created_count = len(delta['created'])
        if created_count > 0:
            print(f"  {obj_type}: {created_count} objects created by CMJ")

    # Parse issue types in workflows (for protection from deletion)
    print("\n📊 Parsing issue types in workflows...")
    issue_types_in_workflows = parse_issue_types_in_workflows()
    if issue_types_in_workflows:
        print(f"  ✓ {len(issue_types_in_workflows)} issue types found in workflows (protected)")
    else:
        print("  ⚠ No workflow data found - issue types will be marked for review")

    # Read and combine processed mappings from all files
    # For multi-project mode, we combine all files and deduplicate by Source Name
    # (Source objects are what we're deciding to CREATE/MAP/DELETE)
    combined_sheets = {}  # {sheet_name: combined_df}

    for input_file, proj_key in input_files:
        xls = pd.ExcelFile(input_file)
        for sheet_name in xls.sheet_names:
            df = pd.read_excel(input_file, sheet_name=sheet_name)
            if df.empty or 'Migration Action' not in df.columns:
                continue

            if sheet_name not in combined_sheets:
                combined_sheets[sheet_name] = df
            else:
                # Combine all rows first
                combined = pd.concat([combined_sheets[sheet_name], df], ignore_index=True)
                combined_sheets[sheet_name] = combined

    # Now deduplicate each sheet by Source Name with priority logic
    # Priority: MAP > DELETE > CREATE (if any project says MAP, keep it; otherwise use first)
    for sheet_name in combined_sheets:
        df = combined_sheets[sheet_name]
        if 'Source Name' not in df.columns:
            continue

        # Sort by Migration Action priority (MAP first, then DELETE, then CREATE)
        action_priority = {'MAP': 0, 'DELETE': 1, 'CREATE': 2, 'SKIP': 3}
        df['_action_priority'] = df['Migration Action'].map(action_priority).fillna(99)
        df = df.sort_values('_action_priority')

        # Deduplicate by Source Name, keeping the highest priority action
        df = df.drop_duplicates(subset=['Source Name'], keep='first')
        df = df.drop(columns=['_action_priority'])

        combined_sheets[sheet_name] = df

    all_stats = {}
    deletion_sheets = {}
    protected_sheets = {}

    for sheet_name, df in combined_sheets.items():
        print(f"\n📊 Analyzing {sheet_name}...")
        print("-" * 80)

        # Get the target delta for this object type
        obj_delta = target_delta.get(sheet_name, {'created': set(), 'deleted': set()})

        result = analyze_cleanup_v2(
            df, sheet_name,
            target_delta=obj_delta,
            issue_types_in_workflows=issue_types_in_workflows
        )
        all_stats[sheet_name] = result['stats']

        # Store sheets for output
        deletion_sheets[sheet_name] = result['will_delete']
        protected_sheets[sheet_name] = result['will_keep']

        # Print stats
        stats = result['stats']
        print(f"  Total objects: {stats['total']}")
        print(f"\n  WILL BE DELETED ({len(result['will_delete'])} objects):")
        if stats['delete_explicit'] > 0:
            print(f"    - Marked DELETE: {stats['delete_explicit']}")
        if stats['delete_post_action'] > 0:
            print(f"    - Post Import DELETE: {stats['delete_post_action']}")
        if stats['delete_created_unused'] > 0:
            print(f"    - Created (unused/not on screens): {stats['delete_created_unused']}")

        print(f"\n  WILL BE KEPT ({len(result['will_keep'])} objects):")
        if stats['keep_on_screen'] > 0:
            print(f"    - Created but on screens: {stats['keep_on_screen']}")
        if stats['keep_in_use'] > 0:
            print(f"    - In workflow (protected): {stats['keep_in_use']}")
        if stats.get('keep_project_specific', 0) > 0:
            print(f"    - Project-specific (protected): {stats['keep_project_specific']}")
        if stats['keep_mapped'] > 0:
            print(f"    - Mapped (not created): {stats['keep_mapped']}")

    # Build target delta DataFrames (objects created by CMJ but not in mapping)
    print("\n📊 Analyzing target delta (objects created by CMJ)...")
    delta_delete_sheets = {}
    delta_keep_sheets = {}
    file_mappings = {
        'CustomFields': 'target_field_post-import.rtf',
        'Status': 'target_status_post-import.rtf',
        'IssueTypes': 'target_issuetype_post-import.rtf',
        'IssueLinkTypes': 'target_issuelinktype_post-import.rtf',
        'Resolutions': 'target_resolution_post-import.rtf',
    }

    # Get mapped target names from customer mapping (these should be protected)
    # Even if CMJ created new IDs, if the NAME is mapped, it should be kept
    mapped_target_names = {}
    for sheet_name, df in combined_sheets.items():
        try:
            if 'Migration Action' in df.columns and 'Target Name' in df.columns:
                mapped_names = df[df['Migration Action'] == 'MAP']['Target Name'].dropna().unique()
                mapped_target_names[sheet_name] = set(mapped_names)
        except Exception:
            pass

    for obj_type, delta in target_delta.items():
        created_ids = delta.get('created', set())
        pre_ids = delta.get('pre_ids', set())  # Pre-import IDs for protection
        pre_names = delta.get('pre_names', set())  # Pre-import names for protection
        if not created_ids:
            continue

        # Get detailed info for created objects
        post_file = file_mappings.get(obj_type)
        if post_file:
            details = parse_target_rtf_details(TARGET_POST_DIR / post_file, obj_type)

            # Build DataFrames - separate DELETE vs KEEP for CustomFields
            delete_rows = []
            keep_rows = []

            for obj_id in sorted(created_ids, key=int):
                info = details.get(obj_id, {})
                obj_name = info.get('name', 'Unknown')
                row = {'Target ID': obj_id, 'Target Name': obj_name}
                if obj_type == 'CustomFields':
                    row['Field Type'] = info.get('type', '')
                elif obj_type == 'IssueLinkTypes':
                    row['Inward'] = info.get('inward', '')
                    row['Outward'] = info.get('outward', '')

                # FIRST CHECK: If ID existed in pre-import, protect it (safety check)
                # This should never happen since created_ids = post_ids - pre_ids,
                # but we check explicitly as a safety measure
                if obj_id in pre_ids:
                    row['Keep Reason'] = 'Existed in pre-import by ID (protected)'
                    keep_rows.append(row)
                    continue

                # SECOND CHECK: If NAME existed in pre-import, protect it
                # This catches cases where CMJ replaces IDs but keeps the same name
                # (e.g., BPM/FPDT issue where CMJ replaced original IDs with new ones)
                if obj_name and obj_name in pre_names:
                    row['Keep Reason'] = 'NAME existed in pre-import (protected - CMJ replaced ID)'
                    keep_rows.append(row)
                    continue

                # For CustomFields, check if on screen or not
                if obj_type == 'CustomFields':
                    if obj_id in CUSTOM_FIELDS_NOT_ON_SCREEN:
                        row['Deletion Reason'] = 'Created by CMJ, NOT on any screen'
                        delete_rows.append(row)
                    else:
                        row['Keep Reason'] = 'Created by CMJ, ON screen (protected)'
                        keep_rows.append(row)
                # For IssueTypes: Delete if not in workflow, keep if in workflow
                # Protected issue types (pre-import) are already handled above
                elif obj_type == 'IssueTypes':
                    issue_type_name = obj_name
                    if issue_type_name and issue_type_name in issue_types_in_workflows:
                        row['Keep Reason'] = 'Created by CMJ, IN workflow (protected)'
                        keep_rows.append(row)
                    else:
                        row['Deletion Reason'] = 'Created by CMJ, NOT in workflow'
                        delete_rows.append(row)
                # For IssueLinkTypes: Keep ALL for now (no auto-deletion)
                elif obj_type == 'IssueLinkTypes':
                    row['Keep Reason'] = 'Created by CMJ (IssueLinkTypes excluded from auto-deletion)'
                    keep_rows.append(row)
                else:
                    # For other types (Status, Resolutions)
                    # Check if name is mapped - if so, protect it
                    mapped_names_for_type = mapped_target_names.get(obj_type, set())

                    if obj_name and obj_name in mapped_names_for_type:
                        row['Keep Reason'] = 'Created by CMJ, but NAME is mapped (protected)'
                        keep_rows.append(row)
                    else:
                        row['Deletion Reason'] = 'Created by CMJ import (not mapped)'
                        delete_rows.append(row)

            if delete_rows:
                delta_delete_sheets[obj_type] = pd.DataFrame(delete_rows)
            if keep_rows:
                delta_keep_sheets[obj_type] = pd.DataFrame(keep_rows)

            # Print summary
            if obj_type == 'CustomFields':
                print(f"  {obj_type}: {len(delete_rows)} to DELETE (not on screens), {len(keep_rows)} to KEEP (on screens)")
            elif obj_type == 'IssueTypes':
                print(f"  {obj_type}: {len(delete_rows)} to DELETE (not in workflows/mapped), {len(keep_rows)} to KEEP (in workflows/mapped)")
            else:
                print(f"  {obj_type}: {len(delete_rows)} to DELETE (not mapped), {len(keep_rows)} to KEEP (mapped)")

    # Write cleanup report
    print("\n" + "=" * 80)
    print("WRITING CLEANUP REPORT")
    print("=" * 80)

    with pd.ExcelWriter(output_file, engine='openpyxl') as writer:
        # Summary sheet
        summary_data = []
        for sheet_name, stats in all_stats.items():
            summary_data.append({
                'Object Type': sheet_name,
                'Total Objects': stats['total'],
                'Will Delete': stats['delete_explicit'] + stats['delete_created_unused'] + stats['delete_post_action'],
                '  - Migration Action DELETE': stats['delete_explicit'],
                '  - Post Import DELETE': stats['delete_post_action'],
                '  - Created (unused)': stats['delete_created_unused'],
                'Will Keep': stats['keep_on_screen'] + stats['keep_mapped'] + stats['keep_in_use'],
                '  - On Screens': stats['keep_on_screen'],
                '  - Mapped': stats['keep_mapped']
            })

        summary_df = pd.DataFrame(summary_data)
        summary_df.to_excel(writer, sheet_name='SUMMARY', index=False)

        worksheet = writer.sheets['SUMMARY']
        for idx, col in enumerate(summary_df.columns):
            max_length = max(
                summary_df[col].astype(str).apply(len).max() if len(summary_df) > 0 else 0,
                len(col)
            ) + 2
            worksheet.column_dimensions[chr(65 + idx)].width = min(max_length, 30)

        # Deletion sheets
        for sheet_name, df in deletion_sheets.items():
            if not df.empty:
                sheet_key = f"DELETE_{sheet_name}"
                df.to_excel(writer, sheet_name=sheet_key[:31], index=False)

                worksheet = writer.sheets[sheet_key[:31]]
                for idx, col in enumerate(df.columns):
                    max_length = max(
                        df[col].astype(str).apply(len).max() if len(df) > 0 else 0,
                        len(col)
                    ) + 2
                    worksheet.column_dimensions[chr(65 + idx)].width = min(max_length, 50)

        # Protection sheets
        for sheet_name, df in protected_sheets.items():
            if not df.empty:
                sheet_key = f"KEEP_{sheet_name}"
                df.to_excel(writer, sheet_name=sheet_key[:31], index=False)

                worksheet = writer.sheets[sheet_key[:31]]
                for idx, col in enumerate(df.columns):
                    max_length = max(
                        df[col].astype(str).apply(len).max() if len(df) > 0 else 0,
                        len(col)
                    ) + 2
                    worksheet.column_dimensions[chr(65 + idx)].width = min(max_length, 50)

        # CMJ Delta DELETE sheets (objects created by CMJ that should be deleted)
        for sheet_name, df in delta_delete_sheets.items():
            if not df.empty:
                sheet_key = f"CMJ_DELETE_{sheet_name}"
                df.to_excel(writer, sheet_name=sheet_key[:31], index=False)

                worksheet = writer.sheets[sheet_key[:31]]
                for idx, col in enumerate(df.columns):
                    max_length = max(
                        df[col].astype(str).apply(len).max() if len(df) > 0 else 0,
                        len(col)
                    ) + 2
                    worksheet.column_dimensions[chr(65 + idx)].width = min(max_length, 50)

        # CMJ Delta KEEP sheets (objects created by CMJ that should be kept)
        for sheet_name, df in delta_keep_sheets.items():
            if not df.empty:
                sheet_key = f"CMJ_KEEP_{sheet_name}"
                df.to_excel(writer, sheet_name=sheet_key[:31], index=False)

                worksheet = writer.sheets[sheet_key[:31]]
                for idx, col in enumerate(df.columns):
                    max_length = max(
                        df[col].astype(str).apply(len).max() if len(df) > 0 else 0,
                        len(col)
                    ) + 2
                    worksheet.column_dimensions[chr(65 + idx)].width = min(max_length, 50)

    print(f"\n✓ Cleanup report saved: {output_file}")

    # Final Summary
    print("\n" + "=" * 80)
    print("CLEANUP SUMMARY")
    print("=" * 80)

    total_delete = sum(s['delete_explicit'] + s['delete_created_unused'] + s['delete_post_action'] for s in all_stats.values())
    total_keep = sum(s['keep_on_screen'] + s['keep_mapped'] + s.get('keep_project_specific', 0) for s in all_stats.values())
    total_cmj_delete = sum(len(df) for df in delta_delete_sheets.values())
    total_cmj_keep = sum(len(df) for df in delta_keep_sheets.values())

    print(f"\nPost-CMJ Deployment Cleanup:")
    print(f"  From Mapping File Analysis:")
    print(f"    - Objects to DELETE: {total_delete}")
    print(f"    - Objects to KEEP: {total_keep}")
    print(f"  From Target Pre/Post Delta (CMJ-Created):")
    print(f"    - Objects to DELETE: {total_cmj_delete}")
    for obj_type, df in delta_delete_sheets.items():
        print(f"      - {obj_type}: {len(df)}")
    print(f"    - Objects to KEEP (on screens): {total_cmj_keep}")
    for obj_type, df in delta_keep_sheets.items():
        print(f"      - {obj_type}: {len(df)}")

    print(f"\n  TOTAL TO DELETE: {total_delete + total_cmj_delete}")
    print(f"  TOTAL TO KEEP: {total_keep + total_cmj_keep}")

    print("\n" + "=" * 80)
    print("✅ CLEANUP REPORT COMPLETE!")
    print("=" * 80)
    print(f"\nReview: {output_file.name}")
    print("\nSheets:")
    print("  - SUMMARY: Overview of deletion vs protection")
    print("  - DELETE_* : Objects marked for deletion in mapping")
    print("  - KEEP_*   : Objects to be protected from deletion")
    print("  - CMJ_DELETE_* : CMJ-created objects to DELETE (not on screens)")
    print("  - CMJ_KEEP_*   : CMJ-created objects to KEEP (on screens)")
    print("\nNext: Use DELETE_* and CMJ_DELETE_* sheets to generate Groovy cleanup script")
    print("=" * 80)


if __name__ == "__main__":
    main()
