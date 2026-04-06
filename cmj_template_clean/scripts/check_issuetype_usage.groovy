/**
 * IssueType Usage Checker
 *
 * Run this script BEFORE cleanup to identify which IssueTypes are in use.
 *
 * Usage: Run in Jira Script Console (ScriptRunner)
 * Output: Report showing issue type usage counts
 */

import com.atlassian.jira.component.ComponentAccessor

def issueTypeManager = ComponentAccessor.getComponent(com.atlassian.jira.config.IssueTypeManager)
def searchService = ComponentAccessor.getComponent(com.atlassian.jira.bc.issue.search.SearchService)
def jqlQueryParser = ComponentAccessor.getComponent(com.atlassian.jira.jql.parser.JqlQueryParser)
def user = ComponentAccessor.jiraAuthenticationContext.loggedInUser

println "=" * 80
println "ISSUE TYPE USAGE REPORT"
println "=" * 80
println ""
println "Generated: ${new Date()}"
println ""

// Get all issue types
def allIssueTypes = issueTypeManager.getIssueTypes()

println "Total IssueTypes in system: ${allIssueTypes.size()}"
println ""
println "-" * 80
println String.format("%-6s | %-40s | %-10s | %-10s | %s", "ID", "Issue Type Name", "Count", "Subtask?", "Status")
println "-" * 80

def inUse = []
def notInUse = []

allIssueTypes.sort { it.name }.each { issueType ->
    def issueCount = 0

    try {
        // Use JQL to count issues of this type
        def jql = "issuetype = \"${issueType.name.replace('"', '\\"')}\""
        def query = jqlQueryParser.parseQuery(jql)
        def searchResults = searchService.searchCount(user, query)
        issueCount = searchResults
    } catch (Exception e) {
        // Fallback: try by ID
        try {
            def delegator = ComponentAccessor.getComponent(org.ofbiz.core.entity.DelegatorInterface)
            def issues = delegator.findByAnd("Issue", [issuetype: issueType.id])
            issueCount = issues?.size() ?: 0
        } catch (Exception e2) {
            issueCount = -1
        }
    }

    def isSubtask = issueType.isSubTask() ? "Yes" : "No"
    def status = ""

    if (issueCount == -1) {
        status = "UNKNOWN"
    } else if (issueCount == 0) {
        status = "NOT USED"
        notInUse << [id: issueType.id, name: issueType.name, count: issueCount, subtask: isSubtask]
    } else {
        status = "IN USE"
        inUse << [id: issueType.id, name: issueType.name, count: issueCount, subtask: isSubtask]
    }

    def countStr = issueCount == -1 ? "?" : issueCount.toString()
    println String.format("%-6s | %-40s | %-10s | %-10s | %s", issueType.id, issueType.name.take(40), countStr, isSubtask, status)
}

println "-" * 80
println ""

// Summary
println "=" * 80
println "SUMMARY"
println "=" * 80
println ""
println "Issue Types IN USE:     ${inUse.size()}"
println "Issue Types NOT IN USE: ${notInUse.size()}"
println ""

if (notInUse.size() > 0) {
    println "CANDIDATES FOR DELETION (not in use):"
    println "-" * 50
    notInUse.each { it ->
        def subtaskNote = it.subtask == "Yes" ? " [Subtask]" : ""
        println "  - ${it.name}${subtaskNote} (ID: ${it.id})"
    }
    println ""
}

if (inUse.size() > 0) {
    println "DO NOT DELETE (in use):"
    println "-" * 50
    inUse.sort { -it.count }.each { it ->
        def subtaskNote = it.subtask == "Yes" ? " [Subtask]" : ""
        println "  - ${it.name}${subtaskNote} (ID: ${it.id}) - ${it.count} issues"
    }
    println ""
}

// Check for issue types in schemes
println "=" * 80
println "ISSUE TYPE SCHEME USAGE"
println "=" * 80
println ""

def issueTypeSchemeManager = ComponentAccessor.issueTypeSchemeManager
def schemeUsage = [:]

allIssueTypes.each { issueType ->
    def schemesUsingType = []
    issueTypeSchemeManager.getAllSchemes().each { scheme ->
        def typesInScheme = issueTypeSchemeManager.getIssueTypesForScheme(scheme)
        if (typesInScheme*.id.contains(issueType.id)) {
            schemesUsingType << scheme.name
        }
    }
    if (schemesUsingType.size() > 0) {
        schemeUsage[issueType.name] = schemesUsingType
    }
}

if (schemeUsage.size() > 0) {
    println "Issue Types assigned to schemes:"
    println "-" * 50
    schemeUsage.sort { it.key }.each { typeName, schemes ->
        println "  ${typeName}:"
        schemes.each { schemeName ->
            println "    - ${schemeName}"
        }
    }
    println ""
}

println "=" * 80
println "NEXT STEPS"
println "=" * 80
println """
1. Review the 'NOT IN USE' issue types above
2. Check scheme assignments - types in schemes may be needed even with 0 issues
3. Verify with stakeholders before deletion
4. To delete unused issue types:
   - Go to: Jira Admin > Issues > Issue Types
   - Delete each unused issue type manually

WARNING: Before deleting an issue type:
  - Remove it from all Issue Type Schemes first
  - Check for references in:
    - Workflow conditions/validators
    - Automation rules
    - ScriptRunner scripts
    - Permission schemes (issue type-specific permissions)
    - Notification schemes
    - Field configurations

Deleting an issue type that is referenced will cause errors.
"""

println "=" * 80
println "END OF REPORT"
println "=" * 80

return "Report complete - see output above"
