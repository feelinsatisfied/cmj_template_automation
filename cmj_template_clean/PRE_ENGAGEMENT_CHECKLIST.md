# Pre-Engagement Checklist

Requirements to gather from source instance **before** agreeing to a CMJ migration project.

---

## Required Access

| Access Type | Required | Notes |
|-------------|----------|-------|
| Jira System Admin | Yes | For API exports, CMJ operations |
| ScriptRunner Console | Yes | For cleanup scripts, bulk operations |
| Database (read) | Preferred | For large exports, troubleshooting |

---

## Source Instance Information

### Basic Details

```
□ Jira Version: _________________ (Server/Data Center, version number)
□ Instance URL: _________________
□ Total Projects: _______________
□ Total Issues: _________________
□ Total Attachments Size: _______ GB
□ Total Users: __________________
```

### Projects to Migrate

```
□ Project keys and names
□ Issue counts per project
□ Project POC/owner for each
□ Any projects being consolidated?
```

---

## Add-on Inventory

### Critical: Add-ons NOT Available on Target

List all installed add-ons and flag those not available on target (TARGET_INSTANCE):

| Add-on Name | Available on Target? | Data Migration Plan |
|-------------|---------------------|---------------------|
| | Yes / No | |
| | Yes / No | |
| | Yes / No | |

### Add-on Custom Fields

```
□ List custom fields created by add-ons
□ Identify field types (may not exist on target)
□ Determine data migration approach for each
```

---

## Configuration Complexity

### Custom Fields

```
□ Total custom field count: _______
□ Field types in use (list unusual types): _______
□ Any calculated/scripted fields? _______
```

### Workflows

```
□ Number of workflows: _______
□ Any complex post-functions? _______
□ Any ScriptRunner workflow extensions? _______
```

### Automations

```
□ Automation rules count: _______
□ Any rules with hardcoded IDs? _______
□ Any external integrations triggered? _______
```

---

## Pre-Snapshot Requirements

**Source instance must complete before we proceed:**

```
□ CMJ integrity check run
□ CMJ quick fixes applied
□ Projects re-indexed
□ Data cleanup completed (optional but recommended)
□ Snapshot created and exported
□ Snapshot diff CSV files provided
```

---

## API Exports Required

**Source instance must provide these exports:**

```
□ /rest/api/2/field              → Custom Fields
□ /rest/api/2/status             → Statuses
□ /rest/api/2/issuetype          → Issue Types
□ /rest/api/2/issueLinkType      → Issue Link Types
□ /rest/api/2/resolution         → Resolutions
```

Save as RTF files with naming convention: `source_{type}_pre-import.rtf`

---

## Customer Mapping File

```
□ Customer mapping spreadsheet provided
□ Format: {PROJECT}_Customer_Mapping.xlsx
□ Sheets: Status, CustomFields, IssueTypes, IssueLinkTypes, Resolutions
□ Migration decisions indicated (MAP, CREATE, SKIP, DELETE)
```

---

## Go/No-Go Criteria

### Blockers (Must Resolve Before Proceeding)

- [ ] No admin access available
- [ ] CMJ integrity check has unresolvable errors
- [ ] Critical add-on with no migration path
- [ ] Jira version incompatibility (3+ major versions difference)
- [ ] No customer mapping decisions provided

### Risks to Document

- [ ] Large attachment volume (>100GB)
- [ ] Complex ScriptRunner customizations
- [ ] Multiple instances consolidating
- [ ] Tight timeline requirements
- [ ] Active production instance with minimal downtime tolerance

---

## Sign-Off

| Role | Name | Date | Signature |
|------|------|------|-----------|
| Source Instance POC | | | |
| Migration Lead | | | |
| Project Manager | | | |

---

**Once all items are checked, the migration project can proceed to Phase 1.**
