/**
 * IssueLinkType Usage Checker
 *
 * Run this script BEFORE cleanup to identify which IssueLinkTypes are in use.
 *
 * Usage: Run in Jira Script Console (ScriptRunner)
 * Output: Report showing link type usage counts
 */

import com.atlassian.jira.component.ComponentAccessor

def issueLinkTypeManager = ComponentAccessor.getComponent(com.atlassian.jira.issue.link.IssueLinkTypeManager)
def issueLinkManager = ComponentAccessor.issueLinkManager

println "=" * 80
println "ISSUE LINK TYPE USAGE REPORT"
println "=" * 80
println ""
println "Generated: ${new Date()}"
println ""

// Get all link types
def allLinkTypes = issueLinkTypeManager.getIssueLinkTypes()

println "Total IssueLinkTypes in system: ${allLinkTypes.size()}"
println ""
println "-" * 80
println String.format("%-5s | %-40s | %-10s | %s", "ID", "Link Type Name", "Count", "Status")
println "-" * 80

def inUse = []
def notInUse = []

allLinkTypes.sort { it.name }.each { linkType ->
    // Count links of this type
    // Note: getIssueLinks returns all links, we need to count them
    def linkCount = 0

    try {
        // Use SQL approach via Active Objects or direct count
        // Since direct link count isn't easily available, we'll use a workaround
        def sql = """
            SELECT COUNT(*) as cnt FROM issuelink WHERE linktype = ${linkType.id}
        """

        // Alternative: iterate through a sample of projects
        // For performance, we'll check if ANY links exist rather than counting all
        def delegator = ComponentAccessor.getComponent(org.ofbiz.core.entity.DelegatorInterface)
        def links = delegator.findByAnd("IssueLink", [linktype: linkType.id])
        linkCount = links?.size() ?: 0

    } catch (Exception e) {
        // Fallback: mark as unknown
        linkCount = -1
    }

    def status = ""
    if (linkCount == -1) {
        status = "UNKNOWN"
    } else if (linkCount == 0) {
        status = "NOT USED"
        notInUse << [id: linkType.id, name: linkType.name, count: linkCount]
    } else {
        status = "IN USE"
        inUse << [id: linkType.id, name: linkType.name, count: linkCount]
    }

    def countStr = linkCount == -1 ? "?" : linkCount.toString()
    println String.format("%-5s | %-40s | %-10s | %s", linkType.id, linkType.name.take(40), countStr, status)
}

println "-" * 80
println ""

// Summary
println "=" * 80
println "SUMMARY"
println "=" * 80
println ""
println "Link Types IN USE:     ${inUse.size()}"
println "Link Types NOT IN USE: ${notInUse.size()}"
println ""

if (notInUse.size() > 0) {
    println "CANDIDATES FOR DELETION (not in use):"
    println "-" * 50
    notInUse.each { lt ->
        println "  - ${lt.name} (ID: ${lt.id})"
    }
    println ""
}

if (inUse.size() > 0) {
    println "DO NOT DELETE (in use):"
    println "-" * 50
    inUse.sort { -it.count }.each { lt ->
        println "  - ${lt.name} (ID: ${lt.id}) - ${lt.count} links"
    }
    println ""
}

println "=" * 80
println "NEXT STEPS"
println "=" * 80
println """
1. Review the 'NOT IN USE' link types above
2. Verify they are truly not needed (check with stakeholders)
3. To delete unused link types:
   - Go to: Jira Admin > Issues > Issue Linking > Link Types
   - Delete each unused link type manually

NOTE: Link types that show 0 usage may still be referenced in:
  - Automation rules
  - ScriptRunner scripts
  - External integrations
  - Workflow post-functions

Always verify before deleting.
"""

println "=" * 80
println "END OF REPORT"
println "=" * 80

return "Report complete - see output above"
