# Pre-Engagement Checklist (Detailed)

Requirements to gather from source instance **before** agreeing to a CMJ migration project.

This document explains **why** each requirement is necessary.

---

## Required Access

### Jira System Administrator Access (Source Instance)

System Administrator access to the **source** Jira instance is essential because CMJ migration requires exporting configuration data, running integrity checks, and creating snapshots—all of which require admin-level permissions.

| We Need To | Why | What Happens Without It |
|------------|-----|------------------------|
| Export API data (fields, statuses, etc.) | Build accurate mapping between source and target objects | Cannot create CMJ templates; migration fails |
| Run CMJ integrity check | Identify configuration issues before migration | Hidden problems cause migration failures |
| Create CMJ snapshot | Capture all configurations for migration | No migration possible |
| Access all system configurations | Understand workflows, screens, permissions | Incomplete migration; broken workflows |
| View all custom fields | Map field types and data correctly | Data loss; field type mismatches |
| Access workflow schemes | Ensure workflows migrate with correct transitions | Broken issue lifecycle on target |
| Review permission schemes | Replicate access controls on target | Security gaps or access issues |
| API Access | Connect to plugin data sources (e.g., Zephyr) | Add-on data does not transfer in CMJ Snapshots |

**Bottom line:** Without admin access, we cannot see the full picture of what needs to migrate, and we cannot execute the migration.

---

### Support Model Based on Access Level

#### With System Administrator Access Provided

| Support Model | Description |
|---------------|-------------|
| Self-Service | Migration team can perform most tasks independently with minimal POC involvement |

#### Without System Administrator Access (Extra POC Support Required)

When we do not have System Administrator access to the source instance, the customer POC must perform the following tasks on our behalf:

| Task | Why It's Needed |
|------|-----------------|
| System Clean Up | CMJ Integrity Checks require varying levels of clean-up |
| CMJ Snapshot Creation | We need multiple snapshots for each migration |
| Project Re-Indexing | Projects should be re-indexed prior to snapshot creation |
| Field Type Review | Some types don't migrate cleanly and need assessment |
| Calculated/Scripted Fields Review | May break depending on how scripts are written (field ID vs name) |
| Asset Objects Configuration | If using Asset Objects, extra configuration requirements apply |

**This significantly increases the POC's workload and extends the migration timeline.**

---

### Dedicated POC Requirement

A dedicated Point of Contact (POC) from the source instance team is required to:
- Coordinate access and approvals
- Review and approve mapping decisions
- Execute tasks requiring admin access (if not granted to migration team)
- Validate migration results

---

### ScriptRunner / Script Console Access

| We Need To | Why | What Happens Without It |
|------------|-----|------------------------|
| Query configuration data | Export complex data not available via REST API | Incomplete data export |

**Bottom line:** Script console access enables efficient data export and validation.

---

### Database Access (Optional - Nice to Have)

| We Need To | Why | What Happens Without It |
|------------|-----|------------------------|
| Export large datasets efficiently | API has rate limits; DB is faster for bulk data | Slow exports; potential timeouts |
| Troubleshoot migration issues | Verify data integrity at source | Guessing at root causes |
| Validate issue counts | Confirm all data migrated | Undetected data loss |
| Query add-on data | Some add-ons store data outside Jira APIs | Missing add-on data |

**Bottom line:** DB access isn't required but can speed up large migrations and troubleshooting.

---

## Source Instance Information

### Basic Details

| Information | Why We Need It |
|-------------|---------------|
| **Jira Version** | Determines compatibility with target; identifies deprecated features |
| **Instance URL** | Required for API exports and CMJ connection |
| **Total Projects** | Scoping; determines if phased approach needed |
| **Total Issues** | Estimates migration time; identifies performance risks |
| **Attachment Size** | Storage planning; bandwidth requirements |
| **Total Users** | Licensing implications on target |

```
□ Jira Version: _________________ (Server/Data Center, version number)
□ Instance URL: _________________
□ Total Projects: _______________
□ Total Issues: _________________
□ Total Attachments Size: _______ GB
□ Total Users: __________________
```

---

## Add-on Inventory

### Why This Matters

Add-ons can:
- Create custom field types that don't exist on target
- Store data in proprietary database tables
- Have no migration path available
- Require separate licensing on target

### Add-ons NOT Available on Target

| Add-on Name | Available on Target? | Data Migration Plan | Risk Level |
|-------------|---------------------|---------------------|------------|
| | Yes / No | | High/Med/Low |
| | Yes / No | | High/Med/Low |

### Add-on Custom Fields

| Why We Need This | Impact If Missed |
|------------------|------------------|
| Add-on fields may have incompatible types | Data loss or corruption |
| Field rendering depends on add-on | Fields display incorrectly |
| Data format may be proprietary | Cannot migrate field values |

```
□ List custom fields created by add-ons
□ Identify field types (may not exist on target)
□ Determine data migration approach for each
```

---

## Configuration Complexity

### Custom Fields

| What We Check | Why |
|---------------|-----|
| Total count | High counts = longer migration, more mapping work |
| Field types | Some types don't migrate cleanly |
| Calculated/scripted fields | May break without ScriptRunner on target |

```
□ Total custom field count: _______
□ Field types in use (list unusual types): _______
□ Any calculated/scripted fields? _______
```

### Workflows

| What We Check | Why |
|---------------|-----|
| Number of workflows | Complexity indicator |
| Post-functions | May reference source-specific IDs |
| ScriptRunner extensions | Require code review and updates |

```
□ Number of workflows: _______
□ Any complex post-functions? _______
□ Any ScriptRunner workflow extensions? _______
```

### Automations

| What We Check | Why |
|---------------|-----|
| Rule count | Effort estimation |
| Hardcoded IDs | Must be updated post-migration |
| External integrations | May need reconfiguration |

```
□ Automation rules count: _______
□ Any rules with hardcoded IDs? _______
□ Any external integrations triggered? _______
```

---

## Pre-Snapshot Requirements

**These must be completed on source BEFORE we can proceed:**

| Step | Why Required | Who Does It |
|------|--------------|-------------|
| **CMJ integrity check** | Identifies configuration issues that would cause migration failure | Source Admin |
| **CMJ quick fixes** | Resolves auto-fixable issues | Source Admin |
| **Re-index** | Ensures search index matches database; prevents stale data | Source Admin |
| **Data cleanup** | Reduces migration size; removes junk data | Source Admin (optional) |
| **Snapshot creation** | Captures configuration for migration | Source Admin |
| **Export diff CSVs** | Required input for our pipeline | Source Admin |

```
□ CMJ integrity check run
□ CMJ quick fixes applied
□ Re-indexing completed
□ Data cleanup completed (optional but recommended)
□ Snapshot created and exported
□ Snapshot diff CSV files provided
```

---

## API Exports Required

**We need these exports because:**

| Export | Why We Need It |
|--------|---------------|
| Custom Fields | Map source fields to target fields; identify type mismatches |
| Statuses | Map workflow statuses; prevent duplicate creation |
| Issue Types | Map issue types; ensure workflow compatibility |
| Issue Link Types | Map relationships; prevent broken links |
| Resolutions | Map resolutions; ensure issue closure works |

```
□ /rest/api/2/field              → Custom Fields
□ /rest/api/2/status             → Statuses
□ /rest/api/2/issuetype          → Issue Types
□ /rest/api/2/issueLinkType      → Issue Link Types
□ /rest/api/2/resolution         → Resolutions
```

**Format:** Save as RTF files with naming: `source_{type}_pre-import.rtf`

---

## Customer Mapping File

| Why Required | Impact If Missing |
|--------------|-------------------|
| Documents customer decisions on how to handle each object | We guess; customer unhappy with results |
| Specifies MAP vs CREATE vs SKIP vs DELETE | Wrong objects created/deleted |
| Provides audit trail of decisions | No accountability; disputes arise |

```
□ Customer mapping spreadsheet provided
□ Format: {PROJECT}_Customer_Mapping.xlsx
□ Sheets: Status, CustomFields, IssueTypes, IssueLinkTypes, Resolutions
□ Migration decisions indicated (MAP, CREATE, SKIP, DELETE)
```

---

## Go/No-Go Criteria

### Blockers (Must Resolve Before Proceeding)

| Blocker | Why It's a Blocker |
|---------|-------------------|
| No admin access (and no dedicated POC to perform admin tasks) | Cannot export data or run CMJ |
| CMJ integrity errors unresolved | Migration will fail |
| Critical add-on with no migration path | Unacceptable data/feature loss |
| Jira version gap >3 major versions | High risk of incompatibilities |
| No customer mapping provided | No decisions = no migration |

### Risks to Document (Not Blockers, But Need Plan)

| Risk | Mitigation Needed |
|------|-------------------|
| Attachment volume >100GB | Plan for extended transfer time |
| Complex ScriptRunner customizations | Code review and update plan |
| Multiple instances consolidating | Conflict resolution strategy |
| Tight timeline | Parallel workstreams; additional resources |
| Minimal downtime tolerance | Detailed cutover plan; rehearsal |

---

## Summary: Why System Admin Access is Critical

| Without System Admin Access We Cannot: |
|----------------------------------------|
| Export the configuration data needed for mapping |
| Run CMJ integrity checks to identify issues |
| Create or export CMJ snapshots |
| See all custom fields, workflows, and schemes |
| Access plugin/add-on data (e.g., Zephyr) |
| Troubleshoot issues that arise |
| Verify migration success |

**If admin access cannot be granted, a dedicated POC must be available to perform all admin tasks on our behalf. This adds significant time and coordination overhead to the engagement.**

---

## Sign-Off

| Role | Name | Date | Signature |
|------|------|------|-----------|
| Source Instance POC | | | |
| Migration Lead | | | |
| Project Manager | | | |

---

**Once all items are checked and access is confirmed, the migration project can proceed.**