#!/usr/bin/env python3
"""
Generate Groovy Cleanup Script

Reads the cleanup report DELETE and CMJ_DELETE sheets and post-import target data
to generate a Groovy script that deletes unused objects created by CMJ.

Usage:
    python3 generate_groovy_cleanup.py
"""

import pandas as pd
from pathlib import Path
import subprocess

# Base paths (relative to script location: scripts/ -> cmj_template/)
BASE_DIR = Path(__file__).resolve().parent.parent
OUTPUT_DIR = BASE_DIR / 'customer_review'
TARGET_POST_DIR = BASE_DIR / 'target_data' / 'post_import'


def find_cleanup_report():
    """Auto-detect the cleanup report file."""
    pattern = '*_Customer_Mapping_CLEANUP_REPORT.xlsx'
    matches = list(OUTPUT_DIR.glob(pattern))

    if not matches:
        return None, None

    report_file = matches[0]
    # Extract project key from filename
    project_key = report_file.stem.replace('_Customer_Mapping_CLEANUP_REPORT', '')
    return report_file, project_key


def parse_rtf_to_dict(rtf_file):
    """Convert RTF file to dictionary mapping name -> ID."""
    if not rtf_file.exists():
        return {}

    # Convert RTF to text using macOS textutil
    result = subprocess.run(
        ['textutil', '-convert', 'txt', '-stdout', str(rtf_file)],
        capture_output=True,
        text=True
    )

    if result.returncode != 0:
        print(f"  ✗ Error converting {rtf_file.name}")
        return {}

    # The RTF conversion puts everything on one line
    # Format: Target ID,Target Name "10000","Name1" "10001","Name2" ...
    text = result.stdout.strip()

    # Remove the header (Target ID,Target Name or similar)
    if text.startswith('Target ID,'):
        text = text.split('"', 1)[-1]  # Remove everything before first quote
        text = '"' + text  # Add quote back

    # Split by '" "' to get individual entries
    name_to_id = {}
    entries = text.split('" "')

    for entry in entries:
        # Each entry is like: "10000","Name" or 10000","Name
        entry = entry.strip().strip('"')  # Remove outer quotes

        # Split by ","
        parts = entry.split('","')
        if len(parts) >= 2:
            obj_id = parts[0].strip('"').strip()
            obj_name = parts[1].strip('"').strip()

            if obj_id and obj_name:
                name_to_id[obj_name] = obj_id

    return name_to_id


def load_target_data_from_xlsx(xlsx_file):
    """Load target data from converted xlsx file."""
    if not xlsx_file.exists():
        return {}

    target_data = {
        'CustomFields': {},
        'Status': {},
        'IssueTypes': {},
        'IssueLinkTypes': {},
        'Resolutions': {}
    }

    # Map xlsx sheet names to our object types
    sheet_mapping = {
        'CustomFields': 'CustomFields',
        'Statuses': 'Status',
        'IssueTypes': 'IssueTypes',
        'IssueLinkTypes': 'IssueLinkTypes',
        'Resolutions': 'Resolutions'
    }

    try:
        xls = pd.ExcelFile(xlsx_file)
        for sheet_name, obj_type in sheet_mapping.items():
            if sheet_name in xls.sheet_names:
                df = pd.read_excel(xlsx_file, sheet_name=sheet_name)
                # Build name -> ID mapping
                if 'Target ID' in df.columns and 'Target Name' in df.columns:
                    for _, row in df.iterrows():
                        obj_id = str(row['Target ID']).strip()
                        obj_name = str(row['Target Name']).strip()
                        if obj_id and obj_name and obj_id != 'nan' and obj_name != 'nan':
                            target_data[obj_type][obj_name] = obj_id
    except Exception as e:
        print(f"  ✗ Error reading xlsx: {e}")

    return target_data


def generate_groovy_script(cleanup_report, target_data_dir, output_file):
    """Generate Groovy cleanup script."""

    print("=" * 80)
    print("GROOVY CLEANUP SCRIPT GENERATOR")
    print("=" * 80)
    print(f"\nInput Report: {cleanup_report.name}")
    print(f"Target Data:  {target_data_dir.name}/")
    print(f"Output:       {output_file.name}")
    print("-" * 80)

    # Load target data - prefer xlsx file, fall back to individual RTF files
    print("\n📂 Loading Post-Import Target Data...")
    print("-" * 80)

    # First try to load from converted xlsx file
    xlsx_file = target_data_dir / 'target_data_post_import_converted.xlsx'
    if xlsx_file.exists():
        print(f"  📊 Loading from: {xlsx_file.name}")
        target_data = load_target_data_from_xlsx(xlsx_file)
    else:
        # Fall back to individual RTF files
        print("  📄 Loading from individual RTF files...")
        target_data = {
            'CustomFields': parse_rtf_to_dict(target_data_dir / 'target_field_post-import.rtf'),
            'Status': parse_rtf_to_dict(target_data_dir / 'target_status_post-import.rtf'),
            'IssueTypes': parse_rtf_to_dict(target_data_dir / 'target_issuetype_post-import.rtf'),
            'IssueLinkTypes': parse_rtf_to_dict(target_data_dir / 'target_issuelinktype_post-import.rtf'),
            'Resolutions': parse_rtf_to_dict(target_data_dir / 'target_resolution_post-import.rtf')
        }

    for obj_type, data in target_data.items():
        print(f"  ✓ {obj_type}: {len(data)} objects loaded")

    # Read cleanup report
    print("\n📊 Reading Cleanup Report...")
    print("-" * 80)

    xls = pd.ExcelFile(cleanup_report)

    # Collect objects to delete
    deletion_plan = {
        'CustomFields': [],
        'Status': [],
        'IssueTypes': [],
        'IssueLinkTypes': [],
        'Resolutions': []
    }

    # Process both DELETE_* and CMJ_DELETE_* sheets
    for sheet_name in xls.sheet_names:
        # Check if this is a deletion sheet (either DELETE_ or CMJ_DELETE_)
        if sheet_name.startswith('DELETE_'):
            obj_type = sheet_name.replace('DELETE_', '')
            sheet_type = 'mapping'
        elif sheet_name.startswith('CMJ_DELETE_'):
            obj_type = sheet_name.replace('CMJ_DELETE_', '')
            sheet_type = 'cmj_delta'
        else:
            continue

        if obj_type not in deletion_plan:
            continue

        # Skip IssueLinkTypes - deletion logic still being refined
        if obj_type == 'IssueLinkTypes':
            print(f"\n  Skipping {sheet_name} (IssueLinkType deletion logic still being refined)")
            continue

        # Skip IssueTypes - mark for manual deletion like Resolutions
        if obj_type == 'IssueTypes':
            print(f"\n  Processing {sheet_name} (marked for MANUAL deletion)...")

        df = pd.read_excel(cleanup_report, sheet_name=sheet_name)

        if df.empty:
            continue

        print(f"\n  Processing {sheet_name}...")

        for _, row in df.iterrows():
            # CMJ_DELETE sheets have Target ID directly
            if sheet_type == 'cmj_delta' and 'Target ID' in df.columns:
                target_id = str(row['Target ID'])
                obj_name = str(row.get('Target Name', 'Unknown'))
                reason = row.get('Deletion Reason', 'Created by CMJ')

                # Avoid duplicates
                existing_ids = [item['id'] for item in deletion_plan[obj_type]]
                if target_id not in existing_ids:
                    deletion_plan[obj_type].append({
                        'name': obj_name,
                        'id': target_id,
                        'reason': reason
                    })
                    print(f"    ✓ {obj_name} -> ID {target_id}")
            else:
                # DELETE sheets need to lookup ID by name
                obj_name = None
                if 'Target Name' in df.columns and pd.notna(row['Target Name']):
                    obj_name = str(row['Target Name'])
                elif 'Source Name' in df.columns:
                    obj_name = str(row['Source Name'])

                if not obj_name or obj_name == 'nan':
                    continue

                # Find target ID from post-import data
                if obj_name in target_data[obj_type]:
                    target_id = target_data[obj_type][obj_name]
                    # Avoid duplicates
                    existing_ids = [item['id'] for item in deletion_plan[obj_type]]
                    if target_id not in existing_ids:
                        deletion_plan[obj_type].append({
                            'name': obj_name,
                            'id': target_id,
                            'reason': row.get('Deletion Reason', 'Unknown')
                        })
                        print(f"    ✓ {obj_name} -> ID {target_id}")
                else:
                    print(f"    ⚠ {obj_name} -> NOT FOUND in post-import data")

    # Generate Groovy script using data-driven approach (avoids "Method too large" error)
    print("\n" + "=" * 80)
    print("GENERATING GROOVY SCRIPT")
    print("=" * 80)

    groovy_code = []
    groovy_code.append("// Jira Post-CMJ Cleanup Script")
    groovy_code.append("// Generated from cleanup report")
    groovy_code.append("//")
    groovy_code.append("// This script deletes unused objects created by CMJ deployment")
    groovy_code.append("// Run this script in Jira Script Console after CMJ deployment")
    groovy_code.append("//")
    groovy_code.append("// ============================================================================")
    groovy_code.append("// DRY RUN MODE - Set to false to actually delete objects")
    groovy_code.append("// ============================================================================")
    groovy_code.append("def DRY_RUN = true  // Set to false to perform actual deletions")
    groovy_code.append("")
    groovy_code.append('if (DRY_RUN) {')
    groovy_code.append('    println "=" * 80')
    groovy_code.append('    println "DRY RUN MODE - No objects will be deleted"')
    groovy_code.append('    println "Set DRY_RUN = false to perform actual deletions"')
    groovy_code.append('    println "=" * 80')
    groovy_code.append('    println ""')
    groovy_code.append('}')
    groovy_code.append("")
    groovy_code.append("import com.atlassian.jira.component.ComponentAccessor")
    groovy_code.append("import com.atlassian.jira.issue.fields.CustomField")
    groovy_code.append("import com.atlassian.jira.config.StatusManager")
    groovy_code.append("import com.atlassian.jira.config.ConstantsManager")
    groovy_code.append("import com.atlassian.jira.issue.link.IssueLinkTypeManager")
    groovy_code.append("import com.atlassian.jira.issue.search.SearchProvider")
    groovy_code.append("import com.atlassian.jira.jql.parser.JqlQueryParser")
    groovy_code.append("import com.atlassian.jira.web.bean.PagerFilter")
    groovy_code.append("import com.atlassian.jira.issue.search.SearchQuery")
    groovy_code.append("import com.atlassian.jira.workflow.WorkflowManager")
    groovy_code.append("")
    groovy_code.append("def customFieldManager = ComponentAccessor.getCustomFieldManager()")
    groovy_code.append("def workflowManager = ComponentAccessor.getWorkflowManager()")
    groovy_code.append("def statusManager = ComponentAccessor.getComponent(StatusManager)")
    groovy_code.append("def constantsManager = ComponentAccessor.getConstantsManager()")
    groovy_code.append("def issueLinkTypeManager = ComponentAccessor.getComponent(IssueLinkTypeManager)")
    groovy_code.append("def searchProvider = ComponentAccessor.getComponent(SearchProvider)")
    groovy_code.append("def jqlQueryParser = ComponentAccessor.getComponent(JqlQueryParser)")
    groovy_code.append("def user = ComponentAccessor.jiraAuthenticationContext.loggedInUser")
    groovy_code.append("")
    groovy_code.append("def deletionLog = []")
    groovy_code.append("def skippedLog = []")
    groovy_code.append("")
    groovy_code.append("// Helper function to check if issues exist matching a JQL query")
    groovy_code.append("def countIssues = { String jql ->")
    groovy_code.append("    try {")
    groovy_code.append("        def query = jqlQueryParser.parseQuery(jql)")
    groovy_code.append("        def searchQuery = SearchQuery.create(query, user)")
    groovy_code.append("        def searchResults = searchProvider.search(searchQuery, PagerFilter.getUnlimitedFilter())")
    groovy_code.append("        return searchResults.total")
    groovy_code.append("    } catch (Exception e) {")
    groovy_code.append("        println \"  ⚠ JQL check failed: ${e.message}\"")
    groovy_code.append("        return -1  // Return -1 to indicate check failed (will skip deletion)")
    groovy_code.append("    }")
    groovy_code.append("}")
    groovy_code.append("")
    groovy_code.append("// Helper function to check if a status is associated with any workflow")
    groovy_code.append("def getWorkflowsUsingStatus = { String statusId ->")
    groovy_code.append("    def workflowsUsingStatus = []")
    groovy_code.append("    try {")
    groovy_code.append("        def allWorkflows = workflowManager.getWorkflows()")
    groovy_code.append("        allWorkflows.each { workflow ->")
    groovy_code.append("            def linkedStatuses = workflow.getLinkedStatusObjects()")
    groovy_code.append("            if (linkedStatuses.any { it.id == statusId }) {")
    groovy_code.append("                workflowsUsingStatus << workflow.name")
    groovy_code.append("            }")
    groovy_code.append("        }")
    groovy_code.append("    } catch (Exception e) {")
    groovy_code.append("        println \"  ⚠ Workflow check failed: ${e.message}\"")
    groovy_code.append("    }")
    groovy_code.append("    return workflowsUsingStatus")
    groovy_code.append("}")
    groovy_code.append("")

    # Custom Fields - data-driven approach with JQL validation
    if deletion_plan['CustomFields']:
        groovy_code.append("// ============================================================================")
        groovy_code.append("// DELETE CUSTOM FIELDS (with JQL validation)")
        groovy_code.append("// ============================================================================")
        groovy_code.append("// JQL check: \"FieldName\" is not EMPTY to verify no issues have data in this field")
        groovy_code.append("")

        # Build the data array
        cf_data = ", ".join([f'["customfield_{item["id"]}", "{item["name"].replace(chr(34), chr(92)+chr(34))}"]'
                            for item in deletion_plan['CustomFields']])
        groovy_code.append(f"def customFieldsToDelete = [{cf_data}]")
        groovy_code.append("")
        groovy_code.append('println "Checking ${customFieldsToDelete.size()} custom fields..."')
        groovy_code.append('println ""')
        groovy_code.append("")
        groovy_code.append("customFieldsToDelete.each { cfData ->")
        groovy_code.append("    def cfId = cfData[0]")
        groovy_code.append("    def cfName = cfData[1]")
        groovy_code.append("    try {")
        groovy_code.append("        CustomField cf = customFieldManager.getCustomFieldObject(cfId)")
        groovy_code.append("        if (cf != null) {")
        groovy_code.append("            // JQL check: verify no issues have data in this field")
        groovy_code.append('            def escapedName = cfName.replace("\'", "\'\'")')
        groovy_code.append('            def jql = "\\"${escapedName}\\" is not EMPTY"')
        groovy_code.append("            def issueCount = countIssues(jql)")
        groovy_code.append("            ")
        groovy_code.append("            if (issueCount > 0) {")
        groovy_code.append('                skippedLog << "SKIPPED CustomField: ${cfName} (${cfId}) - ${issueCount} issues have data"')
        groovy_code.append('                println "  ⏭ SKIPPED: ${cfName} - ${issueCount} issues have data in this field"')
        groovy_code.append("            } else if (issueCount < 0) {")
        groovy_code.append('                skippedLog << "SKIPPED CustomField: ${cfName} (${cfId}) - JQL check failed"')
        groovy_code.append('                println "  ⏭ SKIPPED: ${cfName} - JQL check failed (check manually)"')
        groovy_code.append("            } else {")
        groovy_code.append("                if (DRY_RUN) {")
        groovy_code.append('                    deletionLog << "[DRY RUN] WOULD DELETE CustomField: ${cfName} (${cfId}) - 0 issues"')
        groovy_code.append('                    println "  [DRY RUN] Would delete: ${cfName} (${cfId}) - 0 issues"')
        groovy_code.append("                } else {")
        groovy_code.append("                    customFieldManager.removeCustomField(cf)")
        groovy_code.append('                    deletionLog << "DELETED CustomField: ${cfName} (${cfId})"')
        groovy_code.append('                    println "  ✓ Deleted: ${cfName}"')
        groovy_code.append("                }")
        groovy_code.append("            }")
        groovy_code.append("        } else {")
        groovy_code.append('            deletionLog << "NOT FOUND CustomField: ${cfName} (${cfId})"')
        groovy_code.append('            println "  ⚠ Not found: ${cfName}"')
        groovy_code.append("        }")
        groovy_code.append("    } catch (Exception e) {")
        groovy_code.append('        deletionLog << "ERROR CustomField: ${cfName} (${cfId}) - ${e.message}"')
        groovy_code.append('        println "  ✗ Error: ${cfName}: ${e.message}"')
        groovy_code.append("    }")
        groovy_code.append("}")
        groovy_code.append("")

    # Statuses - data-driven approach with JQL validation
    if deletion_plan['Status']:
        groovy_code.append("// ============================================================================")
        groovy_code.append("// DELETE STATUSES (with workflow and JQL validation)")
        groovy_code.append("// ============================================================================")
        groovy_code.append("// 1. Workflow check: verify status is not associated with any workflow")
        groovy_code.append("// 2. JQL check: status = \"StatusName\" to verify no issues use this status")
        groovy_code.append("")

        status_data = ", ".join([f'["{item["id"]}", "{item["name"].replace(chr(34), chr(92)+chr(34))}"]'
                                 for item in deletion_plan['Status']])
        groovy_code.append(f"def statusesToDelete = [{status_data}]")
        groovy_code.append("")
        groovy_code.append('println "Checking ${statusesToDelete.size()} statuses..."')
        groovy_code.append('println ""')
        groovy_code.append("")
        groovy_code.append("statusesToDelete.each { statusData ->")
        groovy_code.append("    def statusId = statusData[0]")
        groovy_code.append("    def statusName = statusData[1]")
        groovy_code.append("    try {")
        groovy_code.append("        def status = constantsManager.getStatusObject(statusId)")
        groovy_code.append("        if (status != null) {")
        groovy_code.append("            // First check: verify status is not associated with any workflow")
        groovy_code.append("            def workflowsUsingStatus = getWorkflowsUsingStatus(statusId)")
        groovy_code.append("            if (workflowsUsingStatus.size() > 0) {")
        groovy_code.append('                def workflowList = workflowsUsingStatus.take(3).join(", ")')
        groovy_code.append('                if (workflowsUsingStatus.size() > 3) { workflowList += ", ..." }')
        groovy_code.append('                skippedLog << "SKIPPED Status: ${statusName} (${statusId}) - associated with ${workflowsUsingStatus.size()} workflow(s): ${workflowList}"')
        groovy_code.append('                println "  ⏭ SKIPPED: ${statusName} - associated with workflow(s): ${workflowList}"')
        groovy_code.append("                return  // Skip to next status")
        groovy_code.append("            }")
        groovy_code.append("            ")
        groovy_code.append("            // Second check: verify no issues use this status via JQL")
        groovy_code.append('            def escapedName = statusName.replace("\'", "\'\'")')
        groovy_code.append('            def jql = "status = \\"${escapedName}\\""')
        groovy_code.append("            def issueCount = countIssues(jql)")
        groovy_code.append("            ")
        groovy_code.append("            if (issueCount > 0) {")
        groovy_code.append('                skippedLog << "SKIPPED Status: ${statusName} (${statusId}) - ${issueCount} issues use this status"')
        groovy_code.append('                println "  ⏭ SKIPPED: ${statusName} - ${issueCount} issues use this status"')
        groovy_code.append("            } else if (issueCount < 0) {")
        groovy_code.append('                skippedLog << "SKIPPED Status: ${statusName} (${statusId}) - JQL check failed"')
        groovy_code.append('                println "  ⏭ SKIPPED: ${statusName} - JQL check failed (check manually)"')
        groovy_code.append("            } else {")
        groovy_code.append("                if (DRY_RUN) {")
        groovy_code.append('                    deletionLog << "[DRY RUN] WOULD DELETE Status: ${statusName} (${statusId}) - 0 issues, 0 workflows"')
        groovy_code.append('                    println "  [DRY RUN] Would delete: ${statusName} (${statusId}) - 0 issues, 0 workflows"')
        groovy_code.append("                } else {")
        groovy_code.append("                    statusManager.removeStatus(statusId)")
        groovy_code.append('                    deletionLog << "DELETED Status: ${statusName} (${statusId})"')
        groovy_code.append('                    println "  ✓ Deleted: ${statusName}"')
        groovy_code.append("                }")
        groovy_code.append("            }")
        groovy_code.append("        } else {")
        groovy_code.append('            deletionLog << "NOT FOUND Status: ${statusName} (${statusId})"')
        groovy_code.append('            println "  ⚠ Not found: ${statusName}"')
        groovy_code.append("        }")
        groovy_code.append("    } catch (Exception e) {")
        groovy_code.append('        deletionLog << "ERROR Status: ${statusName} (${statusId}) - ${e.message}"')
        groovy_code.append('        println "  ✗ Error: ${statusName}: ${e.message}"')
        groovy_code.append("    }")
        groovy_code.append("}")
        groovy_code.append("")

    # Issue Types - Manual deletion required with JQL validation (like Resolutions)
    if deletion_plan['IssueTypes']:
        groovy_code.append("// ============================================================================")
        groovy_code.append("// ISSUE TYPES - MANUAL DELETION REQUIRED (with JQL validation)")
        groovy_code.append("// ============================================================================")
        groovy_code.append("// JQL check: issuetype = \"IssueTypeName\" to verify no issues use this type")
        groovy_code.append("// NOTE: Issue type deletion can cause issues with workflows/schemes.")
        groovy_code.append("// Delete manually via: Jira Admin > Issues > Issue Types")
        groovy_code.append("// Verify the issue type is not used in any workflow schemes before deleting.")
        groovy_code.append("")

        it_data = ", ".join([f'["{item["id"]}", "{item["name"].replace(chr(34), chr(92)+chr(34))}"]'
                             for item in deletion_plan['IssueTypes']])
        groovy_code.append(f"def issueTypesToDelete = [{it_data}]")
        groovy_code.append("")
        groovy_code.append('println "Checking ${issueTypesToDelete.size()} issue types..."')
        groovy_code.append('println ""')
        groovy_code.append("")
        groovy_code.append("def issueTypesNeedingDeletion = []")
        groovy_code.append("def issueTypesInUse = []")
        groovy_code.append("issueTypesToDelete.each { itData ->")
        groovy_code.append("    def itId = itData[0]")
        groovy_code.append("    def itName = itData[1]")
        groovy_code.append("    try {")
        groovy_code.append("        def issueType = constantsManager.getAllIssueTypeObjects().find { it.id == itId }")
        groovy_code.append("        if (issueType != null) {")
        groovy_code.append("            // JQL check: verify no issues use this issue type")
        groovy_code.append('            def escapedName = itName.replace("\'", "\'\'")')
        groovy_code.append('            def jql = "issuetype = \\"${escapedName}\\""')
        groovy_code.append("            def issueCount = countIssues(jql)")
        groovy_code.append("            ")
        groovy_code.append("            if (issueCount > 0) {")
        groovy_code.append("                issueTypesInUse << [itId, itName, issueCount]")
        groovy_code.append('                skippedLog << "SKIPPED IssueType: ${itName} (${itId}) - ${issueCount} issues use this type"')
        groovy_code.append('                println "  ⏭ SKIPPED: ${itName} - ${issueCount} issues use this type"')
        groovy_code.append("            } else if (issueCount < 0) {")
        groovy_code.append('                skippedLog << "SKIPPED IssueType: ${itName} (${itId}) - JQL check failed"')
        groovy_code.append('                println "  ⏭ SKIPPED: ${itName} - JQL check failed (check manually)"')
        groovy_code.append("            } else {")
        groovy_code.append("                issueTypesNeedingDeletion << [itId, itName]")
        groovy_code.append('                deletionLog << "MANUAL DELETE SAFE - IssueType: ${itName} (${itId}) - 0 issues"')
        groovy_code.append('                println "  ⚠ MANUAL DELETE (safe): ${itName} (ID: ${itId}) - 0 issues"')
        groovy_code.append("            }")
        groovy_code.append("        } else {")
        groovy_code.append('            deletionLog << "NOT FOUND IssueType: ${itName} (${itId})"')
        groovy_code.append('            println "  ✓ Already deleted: ${itName}"')
        groovy_code.append("        }")
        groovy_code.append("    } catch (Exception e) {")
        groovy_code.append('        deletionLog << "ERROR IssueType: ${itName} (${itId}) - ${e.message}"')
        groovy_code.append('        println "  ✗ Error: ${itName}: ${e.message}"')
        groovy_code.append("    }")
        groovy_code.append("}")
        groovy_code.append("")
        groovy_code.append("if (issueTypesNeedingDeletion.size() > 0) {")
        groovy_code.append('    println ""')
        groovy_code.append('    println "=" * 60')
        groovy_code.append('    println "ACTION REQUIRED: Delete ${issueTypesNeedingDeletion.size()} issue types manually"')
        groovy_code.append('    println "Go to: Jira Admin > Issues > Issue Types"')
        groovy_code.append('    println "Verify not used in workflow schemes before deleting"')
        groovy_code.append('    println "=" * 60')
        groovy_code.append("}")
        groovy_code.append("")

    # Issue Link Types - data-driven approach with JQL validation
    if deletion_plan['IssueLinkTypes']:
        groovy_code.append("// ============================================================================")
        groovy_code.append("// DELETE ISSUE LINK TYPES (with JQL validation)")
        groovy_code.append("// ============================================================================")
        groovy_code.append("// JQL check: issueFunction in hasLinkType('LinkTypeName') to verify no links exist")
        groovy_code.append("// NOTE: Requires ScriptRunner for hasLinkType() function")
        groovy_code.append("")

        ilt_data = ", ".join([f'["{item["id"]}", "{item["name"].replace(chr(34), chr(92)+chr(34))}"]'
                              for item in deletion_plan['IssueLinkTypes']])
        groovy_code.append(f"def issueLinkTypesToDelete = [{ilt_data}]")
        groovy_code.append("")
        groovy_code.append('println "Checking ${issueLinkTypesToDelete.size()} issue link types..."')
        groovy_code.append('println ""')
        groovy_code.append("")
        groovy_code.append("issueLinkTypesToDelete.each { iltData ->")
        groovy_code.append("    def iltId = iltData[0]")
        groovy_code.append("    def iltName = iltData[1]")
        groovy_code.append("    try {")
        groovy_code.append("        def linkTypes = issueLinkTypeManager.getIssueLinkTypesByName(iltName)")
        groovy_code.append("        if (linkTypes && !linkTypes.isEmpty()) {")
        groovy_code.append("            def linkType = linkTypes.first()")
        groovy_code.append("            // JQL check: verify no issues have this link type (requires ScriptRunner)")
        groovy_code.append('            def escapedName = iltName.replace("\'", "\'\'")')
        groovy_code.append('            def jql = "issueFunction in hasLinkType(\'${escapedName}\')"')
        groovy_code.append("            def issueCount = countIssues(jql)")
        groovy_code.append("            ")
        groovy_code.append("            if (issueCount > 0) {")
        groovy_code.append('                skippedLog << "SKIPPED IssueLinkType: ${iltName} (${iltId}) - ${issueCount} issues have this link"')
        groovy_code.append('                println "  ⏭ SKIPPED: ${iltName} - ${issueCount} issues have this link type"')
        groovy_code.append("            } else if (issueCount < 0) {")
        groovy_code.append('                skippedLog << "SKIPPED IssueLinkType: ${iltName} (${iltId}) - JQL check failed (ScriptRunner required)"')
        groovy_code.append('                println "  ⏭ SKIPPED: ${iltName} - JQL check failed (requires ScriptRunner hasLinkType)"')
        groovy_code.append("            } else {")
        groovy_code.append("                if (DRY_RUN) {")
        groovy_code.append('                    deletionLog << "[DRY RUN] WOULD DELETE IssueLinkType: ${iltName} (${iltId}) - 0 issues"')
        groovy_code.append('                    println "  [DRY RUN] Would delete: ${iltName} (${iltId}) - 0 issues"')
        groovy_code.append("                } else {")
        groovy_code.append("                    issueLinkTypeManager.removeIssueLinkType(linkType.id)")
        groovy_code.append('                    deletionLog << "DELETED IssueLinkType: ${iltName} (${iltId})"')
        groovy_code.append('                    println "  ✓ Deleted: ${iltName}"')
        groovy_code.append("                }")
        groovy_code.append("            }")
        groovy_code.append("        } else {")
        groovy_code.append('            deletionLog << "NOT FOUND IssueLinkType: ${iltName} (${iltId})"')
        groovy_code.append('            println "  ⚠ Not found: ${iltName}"')
        groovy_code.append("        }")
        groovy_code.append("    } catch (Exception e) {")
        groovy_code.append('        deletionLog << "ERROR IssueLinkType: ${iltName} (${iltId}) - ${e.message}"')
        groovy_code.append('        println "  ✗ Error: ${iltName}: ${e.message}"')
        groovy_code.append("    }")
        groovy_code.append("}")
        groovy_code.append("")

    # Resolutions - Manual deletion required with JQL validation
    if deletion_plan['Resolutions']:
        groovy_code.append("// ============================================================================")
        groovy_code.append("// RESOLUTIONS - MANUAL DELETION REQUIRED (with JQL validation)")
        groovy_code.append("// ============================================================================")
        groovy_code.append("// JQL check: resolution = \"ResolutionName\" to verify no issues use this resolution")
        groovy_code.append("// NOTE: Jira Server does not support programmatic resolution deletion.")
        groovy_code.append("// Delete manually via: Jira Admin > Issues > Resolutions")
        groovy_code.append("// When deleting, select 'Done' as the replacement resolution.")
        groovy_code.append("")

        res_data = ", ".join([f'["{item["id"]}", "{item["name"].replace(chr(34), chr(92)+chr(34))}"]'
                              for item in deletion_plan['Resolutions']])
        groovy_code.append(f"def resolutionsToDelete = [{res_data}]")
        groovy_code.append("")
        groovy_code.append('println "Checking ${resolutionsToDelete.size()} resolutions..."')
        groovy_code.append('println ""')
        groovy_code.append("")
        groovy_code.append("def resolutionsNeedingDeletion = []")
        groovy_code.append("def resolutionsInUse = []")
        groovy_code.append("resolutionsToDelete.each { resData ->")
        groovy_code.append("    def resId = resData[0]")
        groovy_code.append("    def resName = resData[1]")
        groovy_code.append("    def resolution = constantsManager.getResolutions().find { it.id == resId }")
        groovy_code.append("    if (resolution != null) {")
        groovy_code.append("        // JQL check: verify no issues use this resolution")
        groovy_code.append('        def escapedName = resName.replace("\'", "\'\'")')
        groovy_code.append('        def jql = "resolution = \\"${escapedName}\\""')
        groovy_code.append("        def issueCount = countIssues(jql)")
        groovy_code.append("        ")
        groovy_code.append("        if (issueCount > 0) {")
        groovy_code.append("            resolutionsInUse << [resId, resName, issueCount]")
        groovy_code.append('            skippedLog << "SKIPPED Resolution: ${resName} (${resId}) - ${issueCount} issues use this resolution"')
        groovy_code.append('            println "  ⏭ SKIPPED: ${resName} - ${issueCount} issues use this resolution"')
        groovy_code.append("        } else if (issueCount < 0) {")
        groovy_code.append('            skippedLog << "SKIPPED Resolution: ${resName} (${resId}) - JQL check failed"')
        groovy_code.append('            println "  ⏭ SKIPPED: ${resName} - JQL check failed (check manually)"')
        groovy_code.append("        } else {")
        groovy_code.append("            resolutionsNeedingDeletion << [resId, resName]")
        groovy_code.append('            deletionLog << "MANUAL DELETE SAFE - Resolution: ${resName} (${resId}) - 0 issues"')
        groovy_code.append('            println "  ⚠ MANUAL DELETE (safe): ${resName} (ID: ${resId}) - 0 issues"')
        groovy_code.append("        }")
        groovy_code.append("    } else {")
        groovy_code.append('        deletionLog << "NOT FOUND Resolution: ${resName} (${resId})"')
        groovy_code.append('        println "  ✓ Already deleted: ${resName}"')
        groovy_code.append("    }")
        groovy_code.append("}")
        groovy_code.append("")
        groovy_code.append("if (resolutionsNeedingDeletion.size() > 0) {")
        groovy_code.append('    println ""')
        groovy_code.append('    println "=" * 60')
        groovy_code.append('    println "ACTION REQUIRED: Delete ${resolutionsNeedingDeletion.size()} resolutions manually"')
        groovy_code.append('    println "Go to: Jira Admin > Issues > Resolutions"')
        groovy_code.append('    println "Select \'Done\' as replacement when deleting"')
        groovy_code.append('    println "=" * 60')
        groovy_code.append("}")
        groovy_code.append("if (resolutionsInUse.size() > 0) {")
        groovy_code.append('    println ""')
        groovy_code.append('    println "NOTE: ${resolutionsInUse.size()} resolutions are IN USE and cannot be deleted"')
        groovy_code.append("}")
        groovy_code.append("")

    # Summary
    groovy_code.append("// ============================================================================")
    groovy_code.append("// DELETION SUMMARY")
    groovy_code.append("// ============================================================================")
    groovy_code.append("")
    groovy_code.append('println ""')
    groovy_code.append('println "=" * 80')
    groovy_code.append('if (DRY_RUN) {')
    groovy_code.append('    println "DRY RUN COMPLETE - No objects were deleted"')
    groovy_code.append('    println "Set DRY_RUN = false and run again to perform actual deletions"')
    groovy_code.append('} else {')
    groovy_code.append('    println "CLEANUP COMPLETE"')
    groovy_code.append('}')
    groovy_code.append('println "=" * 80')
    groovy_code.append('println ""')
    groovy_code.append('println "Deletion Log (${deletionLog.size()} items):"')
    groovy_code.append('deletionLog.each { println "  - ${it}" }')
    groovy_code.append('println ""')
    groovy_code.append('if (skippedLog.size() > 0) {')
    groovy_code.append('    println "Skipped (IN USE - ${skippedLog.size()} items):"')
    groovy_code.append('    skippedLog.each { println "  - ${it}" }')
    groovy_code.append('}')
    groovy_code.append("")
    groovy_code.append("return [deleted: deletionLog, skipped: skippedLog]")

    # Write to file
    with open(output_file, 'w') as f:
        f.write('\n'.join(groovy_code))

    print(f"\n✓ Groovy script generated: {output_file}")

    # Print summary
    print("\n" + "=" * 80)
    print("DELETION SUMMARY")
    print("=" * 80)

    total_deletions = 0
    for obj_type, items in deletion_plan.items():
        if items:
            print(f"\n{obj_type}:")
            print(f"  Objects to delete: {len(items)}")
            total_deletions += len(items)

    print(f"\nTotal objects to delete: {total_deletions}")
    print("\n" + "=" * 80)
    print("GROOVY CLEANUP SCRIPT READY!")
    print("=" * 80)
    print(f"\nScript: {output_file}")
    print("\nNext steps:")
    print("  1. Review the generated Groovy script")
    print("  2. Run in Jira Script Console (DRY_RUN = true by default)")
    print("  3. Review the dry run output to see what WOULD be deleted")
    print("  4. Set DRY_RUN = false and run again to perform actual deletions")
    print("  5. Objects in use may fail to delete - review manually")
    print("=" * 80)


def main():
    """Main function."""
    # Auto-detect cleanup report
    cleanup_report, project_key = find_cleanup_report()

    if not cleanup_report:
        print(f"❌ No cleanup report found in: {OUTPUT_DIR}")
        print("Run: python3 generate_cleanup_report_v2.py")
        return

    target_data_dir = TARGET_POST_DIR
    output_file = OUTPUT_DIR / f'{project_key}_post_cmj_cleanup.groovy'

    if not target_data_dir.exists():
        print(f"❌ Target data directory not found: {target_data_dir}")
        return

    generate_groovy_script(cleanup_report, target_data_dir, output_file)


if __name__ == "__main__":
    main()
