#!/usr/bin/env python3
"""
Create CMJ Templates from FOR_CMJ File

Generates CMJ XML templates from the {PROJECT}_Customer_Mapping_FOR_CMJ.xlsx file:
1. global_cmj_template.cmj - Statuses, Resolutions, IssueLinkTypes, IssueTypes
2. custom_field_cmj_template.cmj - CustomFields only

Only MAP actions with both Source ID and Target ID are included.
EXACT_MATCH rows should already be filtered out by step 4.

Usage:
    python3 create_cmj_templates.py
"""

import pandas as pd
import csv
from xml.etree.ElementTree import Element, SubElement, tostring
from xml.dom import minidom
from pathlib import Path
from datetime import datetime


# Field type mapping: GUI names → API types (loaded from config)
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
                if gui_type and api_type and gui_type != 'GUI Type':
                    FIELD_TYPE_MAP[gui_type.lower()] = api_type


def normalize_field_type(field_type):
    """Convert GUI field type to API format."""
    if not field_type:
        return ''
    field_type_str = str(field_type).strip()
    # If already in API format (contains colon), return as-is
    if ':' in field_type_str:
        return field_type_str
    # Otherwise look up in mapping
    return FIELD_TYPE_MAP.get(field_type_str.lower(), field_type_str)


# Base paths (relative to script location: scripts/ -> cmj_template/)
BASE_DIR = Path(__file__).resolve().parent.parent
OUTPUT_DIR = BASE_DIR / 'customer_review'
CMJ_OUTPUT_DIR = BASE_DIR / 'cmj_templates'


def find_for_cmj_file():
    """Auto-detect the FOR_CMJ mapping file."""
    pattern = '*_Customer_Mapping_FOR_CMJ.xlsx'
    matches = list(OUTPUT_DIR.glob(pattern))

    if not matches:
        print(f"  ⚠ No FOR_CMJ file found matching: {pattern}")
        print(f"    Looking in: {OUTPUT_DIR}")
        return None, None

    if len(matches) > 1:
        print(f"  ⚠ Multiple FOR_CMJ files found:")
        for m in matches:
            print(f"    - {m.name}")
        print(f"  Using first match: {matches[0].name}")

    cmj_file = matches[0]
    project_key = cmj_file.stem.replace('_Customer_Mapping_FOR_CMJ', '')

    return cmj_file, project_key


# Sheet name → CMJ object type mapping
SHEET_CONFIGS = {
    'Status': {'type': 'Status', 'has_properties': False},
    'Statuses': {'type': 'Status', 'has_properties': False},
    'CustomFields': {'type': 'Custom field', 'has_properties': True},
    'Resolutions': {'type': 'Resolution', 'has_properties': False},
    'IssueLinkTypes': {'type': 'Issue Link Type', 'has_properties': True},
    'IssueTypes': {'type': 'Issue type', 'has_properties': True}
}


def create_rematch_operation(parent, row, object_type, has_properties=False):
    """Create a RematchOperation XML element for a single mapping row."""
    change = SubElement(parent, 'changes')
    change.set('xsi:type', 'operations:RematchOperation')

    is_custom_field = object_type == 'Custom field'
    source_id = int(float(row['Source ID']))
    target_id = int(float(row['Target ID']))

    # Custom fields need 'customfield_' prefix, others use numeric ID
    if is_custom_field:
        source_native_id = f'customfield_{source_id}'
        target_native_id = f'customfield_{target_id}'
    else:
        source_native_id = str(source_id)
        target_native_id = str(target_id)

    # Source object
    source_obj = SubElement(change, 'sourceObject')
    source_obj.set('type', object_type)
    source_obj.set('nativeId', source_native_id)
    source_obj.set('name', str(row['Source Name']))

    if has_properties:
        add_properties(source_obj, row, 'Source', object_type)

    # Target object
    target_obj = SubElement(change, 'targetObject')
    target_obj.set('type', object_type)
    target_obj.set('nativeId', target_native_id)
    target_obj.set('name', str(row['Target Name']))

    if has_properties:
        add_properties(target_obj, row, 'Target', object_type)


def add_properties(parent_element, row, prefix, object_type):
    """Add property elements based on object type."""
    # Issue Types - subtask property
    if 'Is SubTask' in row.index and pd.notna(row.get('Is SubTask')):
        prop = SubElement(parent_element, 'properties')
        prop.set('key', 'isSubTask')
        is_subtask = str(row['Is SubTask']).lower() in ['true', 'yes', '1', 'y']
        prop.set('booleanValue', str(is_subtask).lower())

    # Issue Link Types - style property
    if 'Style' in row.index and pd.notna(row.get('Style')):
        prop = SubElement(parent_element, 'properties')
        prop.set('key', 'style')
        prop.set('stringValue', str(row['Style']))
    elif 'Style' in row.index:
        prop = SubElement(parent_element, 'properties')
        prop.set('key', 'style')
        prop.set('stringValue', '')

    # Custom Fields - typeId property (always use API format)
    if object_type == 'Custom field':
        field_type_value = None
        if prefix == 'Source' and 'Source Type' in row.index and pd.notna(row.get('Source Type')):
            # Convert GUI format to API format
            field_type_value = normalize_field_type(row['Source Type'])
        elif prefix == 'Target' and 'Target Type' in row.index and pd.notna(row.get('Target Type')):
            # Target is already in API format
            field_type_value = str(row['Target Type'])
        elif 'Field Type' in row.index and pd.notna(row.get('Field Type')):
            field_type_value = str(row['Field Type'])

        if field_type_value:
            prop = SubElement(parent_element, 'properties')
            prop.set('key', 'typeId')
            prop.set('stringValue', field_type_value)


def generate_cmj_xml(excel_file, include_sheets=None, exclude_sheets=None):
    """
    Generate CMJ XML from the FOR_CMJ Excel file.

    Returns (xml_bytes, operation_count, stats_dict)
    """
    include_sheets = include_sheets or []
    exclude_sheets = exclude_sheets or []

    xls = pd.ExcelFile(excel_file)

    # Create root element
    root = Element('selectivemerge:DiffChangeDescriptor')
    root.set('xmi:version', '2.0')
    root.set('xmlns:xmi', 'http://www.omg.org/XMI')
    root.set('xmlns:xsi', 'http://www.w3.org/2001/XMLSchema-instance')
    root.set('xmlns:operations', 'http://www.botronsoft.com/rollout/selectivemerge/operations/2.0')
    root.set('xmlns:selectivemerge', 'http://www.botronsoft.com/rollout/selectivemerge/2.0')

    total_operations = 0
    stats = {}

    for sheet_name in xls.sheet_names:
        if sheet_name.startswith('_'):
            continue

        config = SHEET_CONFIGS.get(sheet_name)
        if not config:
            continue

        # Apply include/exclude filters
        if include_sheets and sheet_name not in include_sheets:
            continue
        if sheet_name in exclude_sheets:
            continue

        df = pd.read_excel(excel_file, sheet_name=sheet_name)

        if df.empty:
            stats[sheet_name] = {'total': 0, 'mapped': 0, 'skipped_no_ids': 0, 'skipped_not_map': 0}
            continue

        sheet_mapped = 0
        skipped_no_ids = 0
        skipped_not_map = 0

        for _, row in df.iterrows():
            # Only include MAP actions
            action = str(row.get('Migration Action', '')).strip().upper()
            if action != 'MAP':
                skipped_not_map += 1
                continue

            # Must have both Source ID and Target ID
            if pd.isna(row.get('Source ID')) or pd.isna(row.get('Target ID')):
                skipped_no_ids += 1
                continue

            create_rematch_operation(root, row, config['type'], config['has_properties'])
            sheet_mapped += 1

            # Add periodic AnalyzeOperation
            if total_operations > 0 and total_operations % 10 == 0:
                analyze = SubElement(root, 'changes')
                analyze.set('xsi:type', 'operations:AnalyzeOperation')

            total_operations += 1

        stats[sheet_name] = {
            'total': len(df),
            'mapped': sheet_mapped,
            'skipped_no_ids': skipped_no_ids,
            'skipped_not_map': skipped_not_map
        }

    # Add final AnalyzeOperation
    analyze = SubElement(root, 'changes')
    analyze.set('xsi:type', 'operations:AnalyzeOperation')

    # Pretty print XML
    xml_str = minidom.parseString(tostring(root, encoding='utf-8')).toprettyxml(
        indent='  ',
        encoding='UTF-8'
    )

    # CMJ uses XML 1.1
    xml_str = xml_str.replace(b'version="1.0"', b'version="1.1"')

    return xml_str, total_operations, stats


def main():
    """Main function."""
    print("=" * 80)
    print("CREATE CMJ TEMPLATES")
    print("=" * 80)
    print(f"Timestamp: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")

    # Load field type mapping for GUI→API conversion
    load_field_type_mapping()

    # Auto-detect FOR_CMJ file
    print("\n🔍 Auto-detecting FOR_CMJ mapping file...")
    input_file, project_key = find_for_cmj_file()

    if not input_file:
        print("\n❌ Error: No FOR_CMJ mapping file found")
        print(f"   Run step 4 first: python3 filter_for_cmj_template.py")
        return

    print(f"\n📁 Input:   {input_file.name}")
    print(f"📋 Project: {project_key}")

    # Create output directory
    CMJ_OUTPUT_DIR.mkdir(parents=True, exist_ok=True)

    global_output = CMJ_OUTPUT_DIR / f'{project_key}_global_cmj_template.cmj'
    cf_output = CMJ_OUTPUT_DIR / f'{project_key}_custom_field_cmj_template.cmj'

    # === Generate Global CMJ Template (exclude CustomFields) ===
    print(f"\n{'=' * 80}")
    print("1. GENERATING GLOBAL CMJ TEMPLATE")
    print("=" * 80)
    print("  Includes: Status, Resolutions, IssueLinkTypes, IssueTypes")
    print("  Excludes: CustomFields")

    xml_bytes, op_count, stats = generate_cmj_xml(
        input_file,
        exclude_sheets=['CustomFields']
    )

    with open(global_output, 'wb') as f:
        f.write(xml_bytes)

    print(f"\n  Results:")
    for sheet_name, s in stats.items():
        print(f"    {sheet_name}: {s['mapped']} rematch operations "
              f"(skipped: {s['skipped_not_map']} non-MAP, {s['skipped_no_ids']} missing IDs)")
    print(f"  Total operations: {op_count}")
    print(f"  ✓ Saved: {global_output.name}")

    # === Generate Custom Fields CMJ Template ===
    print(f"\n{'=' * 80}")
    print("2. GENERATING CUSTOM FIELDS CMJ TEMPLATE")
    print("=" * 80)
    print("  Includes: CustomFields only")

    xml_bytes_cf, op_count_cf, stats_cf = generate_cmj_xml(
        input_file,
        include_sheets=['CustomFields']
    )

    with open(cf_output, 'wb') as f:
        f.write(xml_bytes_cf)

    print(f"\n  Results:")
    for sheet_name, s in stats_cf.items():
        print(f"    {sheet_name}: {s['mapped']} rematch operations "
              f"(skipped: {s['skipped_not_map']} non-MAP, {s['skipped_no_ids']} missing IDs)")
    print(f"  Total operations: {op_count_cf}")
    print(f"  ✓ Saved: {cf_output.name}")

    # Summary
    print(f"\n{'=' * 80}")
    print("✅ CMJ TEMPLATES CREATED SUCCESSFULLY!")
    print("=" * 80)
    print(f"\nLocation: {CMJ_OUTPUT_DIR}/")
    print(f"\nFiles created:")
    print(f"  1. {global_output.name} ({op_count} operations)")
    print(f"  2. {cf_output.name} ({op_count_cf} operations)")
    print(f"\nNext steps:")
    print(f"  1. Review the CMJ template files")
    print(f"  2. Import {global_output.name} FIRST in CMJ")
    print(f"  3. Then import {cf_output.name}")
    print(f"  4. Deploy the CMJ snapshot")
    print("=" * 80)


if __name__ == "__main__":
    main()
