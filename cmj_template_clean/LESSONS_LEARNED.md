# CMJ Migration Lessons Learned & Pre-Engagement Checklist

A comprehensive guide of lessons learned during CMJ migrations and requirements to gather before accepting a migration project.

---

## Table of Contents

1. [Pre-Engagement Requirements](#pre-engagement-requirements)
2. [Source Instance Assessment](#source-instance-assessment)
3. [Add-ons and Integrations](#add-ons-and-integrations)
4. [Instance Consolidation Considerations](#instance-consolidation-considerations)
5. [Pre-Snapshot Preparation](#pre-snapshot-preparation)
6. [CMJ Template Strategy](#cmj-template-strategy)
7. [Version Compatibility](#version-compatibility)
8. [Data Migration Specifics](#data-migration-specifics)
9. [Technical Access Requirements](#technical-access-requirements)
10. [Common Issues and Fixes](#common-issues-and-fixes)
11. [Support and Escalation](#support-and-escalation)

---

## Pre-Engagement Requirements

### What We Need From Source Instance Before Accepting Project

| Requirement | Why It Matters |
|-------------|----------------|
| **Admin Access** | Required for API exports, CMJ operations, configuration review |
| **Permissions Matrix** | Understand existing permission schemes, may affect migration |
| **Add-on Inventory** | Identify unsupported add-ons, data migration complexity |
| **Project List** | Scope the migration, identify project groupings |
| **User Count** | Licensing implications on target |
| **Issue Count** | Estimate migration time, identify large projects |
| **Attachment Size** | Storage requirements, migration bandwidth |
| **Custom Field Inventory** | Complexity indicator, field type compatibility |
| **Workflow Complexity** | Post-functions, validators, conditions that may break |

### Pre-Engagement Questionnaire

```markdown
□ Total number of projects to migrate?
□ Total number of issues across all projects?
□ Total attachment storage size?
□ List of installed add-ons/plugins?
□ Jira version (Server/Data Center/Cloud)?
□ Are there any custom scripts (ScriptRunner, etc.)?
□ Any external integrations (CI/CD, monitoring, etc.)?
□ Timeline requirements?
□ Downtime tolerance?
□ Any compliance/security requirements?
```

---

## Source Instance Assessment

### Admin Access Requirements

**Minimum access needed:**
- Jira System Administrator
- Access to all projects being migrated
- Database read access (preferred) or SQL query capability
- Server/file system access (for large attachment migrations)

### Data Export Checklist

Before migration, export from source:

```
□ /rest/api/2/field              → Custom Fields
□ /rest/api/2/status             → Statuses
□ /rest/api/2/issuetype          → Issue Types
□ /rest/api/2/issueLinkType      → Issue Link Types
□ /rest/api/2/resolution         → Resolutions
□ /rest/api/2/priority           → Priorities
□ /rest/api/2/project            → Projects
□ /rest/api/2/workflow           → Workflows
□ /rest/api/2/screens            → Screens
```

### Configuration Audit

Review and document:
- **Workflow schemes** - Which projects use which workflows
- **Permission schemes** - Project-level permissions
- **Notification schemes** - Email configurations
- **Field configurations** - Required fields, field visibility
- **Screen schemes** - Create/Edit/View screens per issue type

---

## Add-ons and Integrations

### Add-on Compatibility Assessment

**Critical Questions:**
1. Is the add-on available on target (TARGET_INSTANCE/Cloud)?
2. Does the add-on store data in custom tables?
3. Is there a migration path for add-on data?
4. What happens to add-on custom fields?

### Common Add-on Categories

| Category | Examples | Migration Complexity |
|----------|----------|---------------------|
| **Test Management** | Zephyr, Xray, TestRail | HIGH - Separate migration |
| **Time Tracking** | Tempo, Time in Status | MEDIUM - Data export needed |
| **Reporting** | eazyBI, Power BI connectors | LOW - Reconfigure on target |
| **Automation** | ScriptRunner, Automation for Jira | MEDIUM - Scripts need review |
| **Agile** | Portfolio, Advanced Roadmaps | MEDIUM - Board reconfiguration |
| **Custom Fields** | Various | HIGH - Field type mapping |

### Add-ons NOT in Target (TARGET_INSTANCE)

**Action required for each:**
1. Document what the add-on does
2. Identify data stored by add-on
3. Determine if native replacement exists
4. Plan data migration or archival
5. Communicate feature loss to stakeholders

### Effect on Custom Fields

Add-ons often create custom fields that:
- May not have equivalent field types on target
- Store data in proprietary formats
- Require add-on to render/edit properly

**Assessment checklist:**
```
□ List all custom fields created by add-ons
□ Identify field type for each
□ Check if field type exists on target
□ Determine data migration approach
□ Test field behavior post-migration
```

---

## Instance Consolidation Considerations

### When Consolidating Multiple Instances

**Key Questions:**
1. Are there duplicate project keys across instances?
2. Are there conflicting object names (statuses, fields, etc.)?
3. How do we handle duplicate users?
4. What's the target state architecture?

### Object Naming Conflicts

When consolidating, you may encounter:

| Object Type | Conflict Example | Resolution Options |
|-------------|-----------------|-------------------|
| Status | Both have "In Progress" with different meanings | Rename one, MAP both to same target |
| Custom Field | Same name, different field types | Rename or merge carefully |
| Issue Type | Same name, different workflows | Consolidate workflows first |
| Resolution | Same name, different usage | MAP to unified resolution |

### Do We Modify Source Instance?

**Question:** Do we go into their instance and update field names, links, status, resolutions?

**Answer:** It depends.

| Scenario | Recommendation |
|----------|---------------|
| Minor naming cleanup | Yes - easier pre-migration |
| Major restructuring | No - document and handle in mapping |
| Active production instance | No - minimize source changes |
| Decommissioning after migration | Yes - can be more aggressive |

**Best Practice:**
- Prefer handling differences in the mapping file
- Only modify source if it significantly simplifies migration
- Document ALL source changes made
- Get customer approval before modifying source

---

## Pre-Snapshot Preparation

### Steps BEFORE Creating CMJ Snapshot

#### 1. CMJ Integrity Check

```
□ Run CMJ integrity check on source
□ Review all warnings and errors
□ Run quick fixes for resolvable issues
□ Document issues that cannot be auto-fixed
□ Decide on manual remediation steps
```

**Common integrity issues:**
- Orphaned workflow transitions
- Invalid field configurations
- Missing scheme associations
- Broken post-functions

#### 2. Re-index Projects

```
□ Identify projects to migrate
□ Run background re-index on each project
□ Verify re-index completed successfully
□ Check for indexing errors in logs
```

**Why re-index?**
- Ensures search index matches database
- Fixes stale data references
- Required for accurate issue counts
- Prevents migration of inconsistent data

#### 3. Data Cleanup (Optional but Recommended)

```
□ Archive old/completed projects
□ Delete test/junk issues
□ Clean up unused custom fields
□ Remove deprecated workflows
□ Consolidate duplicate objects
```

#### 4. Create Snapshot

```
□ Select projects for migration
□ Include all related configurations
□ Verify snapshot contents
□ Export snapshot for backup
□ Export diff CSV files for pipeline
```

---

## CMJ Template Strategy

### Instance-by-Instance Approach

**Key Learning:** CMJ templates should be created on an instance-by-instance basis.

**Why?**
- Each source instance has unique object IDs
- Target IDs differ between environments (Dev, Stage, Prod)
- Mappings are specific to source→target pair

### Template Reusability

| Scenario | Template Reuse? |
|----------|----------------|
| Same source → Same target | Yes, if no changes |
| Same source → Different target | No - regenerate with new target IDs |
| Different source → Same target | No - different source IDs |
| Multiple project groups, same instances | Partial - shared objects may overlap |

### Multi-Project Group Strategy

When migrating multiple project groups from same source:

**Option A: Unified Template**
- One mapping file for all groups
- Single CMJ template
- Coordinated deployment
- Pro: No conflicts
- Con: All-or-nothing deployment

**Option B: Separate Templates (Recommended)**
- Copy entire folder structure per group
- Independent mapping files
- Staggered deployment
- Pro: Isolation, phased approach
- Con: More files to manage

---

## Version Compatibility

### Jira Version Considerations

**Source to Target Compatibility:**

| Source Version | Target Version | Compatibility |
|---------------|----------------|---------------|
| Server 8.x | Server 8.x | Full |
| Server 8.x | Data Center 8.x | Full |
| Server 7.x | Server 8.x | Good (some deprecated features) |
| Server 8.x | Cloud | Limited (use Jira Cloud Migration Assistant) |
| Data Center | Cloud | Limited (JCMA recommended) |

### Version-Specific Issues

**Upgrading during migration:**
- Review release notes for breaking changes
- Test workflows on target version first
- Check add-on compatibility with target version
- Plan for deprecated feature replacements

**Known issues by version gap:**
- 2+ major versions: Workflow XML schema changes
- 3+ major versions: Custom field type deprecations
- Server to Cloud: Significant feature differences

---

## Data Migration Specifics

### Zephyr Migration (Essentials to Scale)

**Current Status:** ~80% data transfer working, targeting 100%

**What transfers:**
- Test cases
- Test cycles
- Test executions
- Basic attachments

**Known challenges:**
- Execution history depth
- Custom field mappings
- Attachment size limits
- API rate limiting

**Workarounds:**
- Batch processing for large datasets
- Direct database queries for complex data
- Hybrid approach (API + DB export)

### Automation Migration

**Bug fixes identified:**
- Automation rules may reference old object IDs
- Post-functions with hardcoded values
- ScriptRunner scripts with instance-specific code

**Remediation:**
```
□ Export all automation rules
□ Search for hardcoded IDs
□ Update references post-migration
□ Test each automation rule
□ Document rules that need manual fixes
```

### CMJ Template Live Run

**Best practices:**
- Always run with DRY_RUN first
- Review output carefully
- Have rollback plan
- Run during low-usage window
- Monitor Jira logs during execution

---

## Technical Access Requirements

### ScriptRunner Access

**Why needed:**
- Run cleanup Groovy scripts
- Execute bulk updates
- Automation fixes
- Custom data transformations

**Minimum requirements:**
- ScriptRunner installed on target
- Admin access to Script Console
- Understanding of Groovy basics

### SQL/Database Access

**When required:**
- Large data exports (faster than API)
- Complex data transformations
- Troubleshooting migration issues
- Verifying data integrity

**Access levels:**
| Level | Use Case |
|-------|----------|
| Read-only | Data export, verification |
| Read-write | Direct fixes (use with caution) |
| DBA access | Schema changes, performance tuning |

**Common queries needed:**
```sql
-- Issue counts by project
SELECT project.pkey, COUNT(*) FROM jiraissue
JOIN project ON jiraissue.project = project.id
GROUP BY project.pkey;

-- Custom field usage
SELECT customfield.cfname, COUNT(*) FROM customfieldvalue
JOIN customfield ON customfieldvalue.customfield = customfield.id
GROUP BY customfield.cfname;

-- Attachment sizes
SELECT SUM(filesize)/1024/1024 AS size_mb FROM fileattachment;
```

---

## Common Issues and Fixes

### Issues Discovered During Migration

| Issue | Cause | Fix |
|-------|-------|-----|
| Duplicate object names | Source had multiple objects with same name | Rename before migration |
| Missing Target IDs | Object doesn't exist on target | Change MAP to CREATE |
| ID replacement by CMJ | CMJ created new ID for existing name | Use NAME-based protection |
| Objects in use | Can't delete objects referenced by issues | Clean up references first |
| API limitations | Some operations not supported via API | Manual cleanup via UI |

### Resolution Deletion Limitation

**Issue:** Jira Server API does not support programmatic resolution deletion.

**Workaround:**
1. Script identifies resolutions to delete
2. Script outputs list with IDs
3. Admin manually deletes via: `Jira Admin > Issues > Resolutions`
4. When deleting, select replacement resolution (usually "Done")

### Protection Logic Learned

Objects should be protected from deletion if:
1. **Existed in pre-import** (by ID)
2. **Name existed in pre-import** (CMJ ID replacement scenario)
3. **Mapped in customer mapping** (intentional MAP action)
4. **Used in workflows** (would break workflows)
5. **On screens** (custom fields actively used)

---

## Support and Escalation

### When to Escalate

| Situation | Escalation Path |
|-----------|-----------------|
| CMJ integrity errors won't resolve | Atlassian Support |
| Add-on data won't migrate | Add-on vendor |
| Performance issues during migration | Infrastructure team |
| Data loss or corruption | Stop migration, assess, rollback |
| Customer approval needed | Project POC |

### Documentation Requirements

For each migration, document:
```
□ Source instance details (URL, version, size)
□ Target instance details
□ Project scope (list of projects)
□ Object mapping decisions
□ Add-on migration approach
□ Known issues and workarounds
□ Rollback procedure
□ Sign-off from stakeholders
```

### Post-Migration Checklist

```
□ Verify issue counts match
□ Test sample issues (all fields populated)
□ Verify attachments accessible
□ Test workflows (transitions work)
□ Verify permissions (access as expected)
□ Test automations
□ Verify dashboards/filters
□ User acceptance testing
□ Performance baseline
□ Document lessons learned
```

---

## Quick Reference: Migration Readiness Checklist

### Source Instance Ready When:

```
□ Admin access confirmed
□ All projects identified
□ Add-on inventory complete
□ CMJ integrity check passed
□ Projects re-indexed
□ Snapshot created successfully
□ API exports collected
□ Customer mapping reviewed
```

### Target Instance Ready When:

```
□ Admin access confirmed
□ Jira version compatible
□ Required add-ons installed
□ Pre-import data exported
□ CMJ templates imported
□ Test deployment successful
□ Cleanup script tested (DRY_RUN)
```

### Go-Live Ready When:

```
□ All test migrations successful
□ Customer sign-off received
□ Rollback procedure documented
□ Support team notified
□ Maintenance window scheduled
□ Communication sent to users
```

---

## Revision History

| Date | Version | Changes |
|------|---------|---------|
| 2026-02-15 | 1.0 | Initial lessons learned document |

---

## Contributors

- Migration Team
- Lessons learned from PROJECT migration project
