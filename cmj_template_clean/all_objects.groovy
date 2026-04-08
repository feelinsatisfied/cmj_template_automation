package migration_scripts

/**
 * Export All Target Data - Consolidated Script
 *
 * Run this ONCE in ScriptRunner Console to export all 5 object types:
 * - Statuses
 * - Resolutions
 * - Custom Fields
 * - Issue Types
 * - Issue Link Types
 *
 * The output is formatted for easy parsing by the migration pipeline.
 * Copy the entire output and save as: target_all_objects.txt
 */

import com.atlassian.jira.component.ComponentAccessor
import com.atlassian.jira.config.StatusManager
import com.atlassian.jira.config.ConstantsManager
import com.atlassian.jira.issue.CustomFieldManager
import com.atlassian.jira.issue.link.IssueLinkTypeManager

def output = new StringBuilder()
def timestamp = new Date().format("yyyy-MM-dd HH:mm:ss")

output.append("=" * 80 + "\n")
output.append("TARGET DATA EXPORT\n")
output.append("Generated: ${timestamp}\n")
output.append("=" * 80 + "\n\n")

// ============================================================================
// STATUSES
// ============================================================================
def statusManager = ComponentAccessor.getComponent(StatusManager)
def allStatuses = statusManager.getStatuses()
def sortedStatuses = allStatuses.collect { it }.sort { it.id }

output.append("###SECTION:STATUSES###\n")
output.append("Target ID,Target Name\n")
sortedStatuses.each { status ->
    output.append("\"${status.id}\",")
    output.append("\"${status.name.replaceAll('"', '""')}\"\n")
}
output.append("###END:STATUSES### (${allStatuses.size()} items)\n\n")

// ============================================================================
// RESOLUTIONS
// ============================================================================
def constantsManager = ComponentAccessor.getConstantsManager()
def resolutions = constantsManager.getResolutions()
def sortedResolutions = resolutions.collect { it }.sort { it.id }

output.append("###SECTION:RESOLUTIONS###\n")
output.append("Target ID,Target Name\n")
sortedResolutions.each { resolution ->
    output.append("\"${resolution.id}\",")
    output.append("\"${resolution.name.replaceAll('"', '""')}\"\n")
}
output.append("###END:RESOLUTIONS### (${resolutions.size()} items)\n\n")

// ============================================================================
// CUSTOM FIELDS
// ============================================================================
def customFieldManager = ComponentAccessor.getCustomFieldManager()
def customFields = customFieldManager.getCustomFieldObjects()
def sortedFields = customFields.collect { it }.sort {
    it.idAsLong ?: it.id.replace("customfield_", "").toLong()
}

output.append("###SECTION:CUSTOMFIELDS###\n")
output.append("Target ID,Target Name,Field Type\n")
sortedFields.each { field ->
    def fieldId = field.idAsLong ?: field.id.replace("customfield_", "")
    def fieldName = field.name.replaceAll('"', '""')
    def fieldType = field.customFieldType?.key ?: ""

    output.append("\"${fieldId}\",")
    output.append("\"${fieldName}\",")
    output.append("\"${fieldType}\"\n")
}
output.append("###END:CUSTOMFIELDS### (${customFields.size()} items)\n\n")

// ============================================================================
// ISSUE TYPES
// ============================================================================
def issueTypes = constantsManager.getAllIssueTypeObjects()
def sortedTypes = issueTypes.collect { it }.sort { it.id }

output.append("###SECTION:ISSUETYPES###\n")
output.append("Target ID,Target Name,Is SubTask\n")
sortedTypes.each { issueType ->
    output.append("\"${issueType.id}\",")
    output.append("\"${issueType.name.replaceAll('"', '""')}\",")
    output.append("\"${issueType.isSubTask()}\"\n")
}
output.append("###END:ISSUETYPES### (${issueTypes.size()} items)\n\n")

// ============================================================================
// ISSUE LINK TYPES
// ============================================================================
def issueLinkTypeManager = ComponentAccessor.getComponent(IssueLinkTypeManager)

def linkTypes = []
try {
    linkTypes = issueLinkTypeManager.getIssueLinkTypes()
} catch (Exception e) {
    try {
        linkTypes = issueLinkTypeManager.getIssueLinkTypesList()
    } catch (Exception e2) {
        linkTypes = issueLinkTypeManager.class.methods.find {
            it.name.contains("IssueLink") && it.parameterCount == 0
        }?.invoke(issueLinkTypeManager) ?: []
    }
}
def sortedLinkTypes = linkTypes.collect { it }.sort { it.id }

output.append("###SECTION:ISSUELINKTYPES###\n")
output.append("Target ID,Target Name,Inward,Outward\n")
sortedLinkTypes.each { linkType ->
    output.append("\"${linkType.id}\",")
    output.append("\"${linkType.name.replaceAll('"', '""')}\",")
    output.append("\"${linkType.inward?.replaceAll('"', '""') ?: ''}\",")
    output.append("\"${linkType.outward?.replaceAll('"', '""') ?: ''}\"\n")
}
output.append("###END:ISSUELINKTYPES### (${linkTypes.size()} items)\n\n")

// ============================================================================
// SUMMARY
// ============================================================================
output.append("=" * 80 + "\n")
output.append("EXPORT SUMMARY\n")
output.append("=" * 80 + "\n")
output.append("Statuses:        ${allStatuses.size()}\n")
output.append("Resolutions:     ${resolutions.size()}\n")
output.append("Custom Fields:   ${customFields.size()}\n")
output.append("Issue Types:     ${issueTypes.size()}\n")
output.append("Issue Link Types: ${linkTypes.size()}\n")
output.append("-" * 40 + "\n")
output.append("TOTAL:           ${allStatuses.size() + resolutions.size() + customFields.size() + issueTypes.size() + linkTypes.size()} objects\n")
output.append("=" * 80 + "\n\n")

output.append("""
INSTRUCTIONS:
1. Copy ALL output above (from "TARGET DATA EXPORT" to the summary)
2. Save as: target_all_objects.txt
3. Place in: target_data/pre_import/ OR target_data/post_import/
4. The pipeline will auto-parse this file

NOTE: This replaces the need for 5 separate RTF export files.
""")

return output.toString()
