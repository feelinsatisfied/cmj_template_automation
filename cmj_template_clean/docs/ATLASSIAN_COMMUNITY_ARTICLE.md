# Automating CMJ Migrations: A Python Toolkit for Jira Data Center

**TL;DR:** After managing multiple large-scale Jira migrations using Configuration Manager for Jira (CMJ), I built a Python toolkit that automates the tedious parts—mapping validation, conflict detection, template generation, and post-migration cleanup. This article shares the approach and lessons learned.

---

## The Problem: CMJ Migrations at Scale

If you've ever done a Jira Data Center migration using CMJ, you know the pain:

- **Hundreds of objects to map**: Statuses, custom fields, issue types, resolutions, link types—each needs a decision
- **Customer coordination**: Someone has to review spreadsheets and make mapping decisions
- **Human error**: Typos, copy-paste mistakes, and inconsistent naming break things
- **Post-migration cleanup**: CMJ creates objects that need to be deleted, but which ones are safe to remove?
- **No audit trail**: What got mapped where? What was created vs. deleted?

For a single small project, this is manageable. For enterprise migrations with thousands of objects across multiple projects, it becomes a full-time job.

---

## The Solution: An 11-Step Automated Pipeline

I built a Python toolkit that wraps around CMJ to automate the repetitive work while keeping humans in the loop for decisions that matter.

### The Pipeline at a Glance

| Phase | Steps | What Happens |
|-------|-------|--------------|
| **Pre-Deployment** | 1-6 | Convert data, process mappings, validate, generate CMJ templates |
| **Customer Review** | Between 3-4 | Customer reviews and approves mapping decisions |
| **CMJ Deployment** | Manual | Import templates, deploy snapshot |
| **Post-Deployment** | 7-11 | Generate cleanup scripts, validate before/after deletion |

### Key Automation Features

**1. Intelligent Matching**

The toolkit automatically matches source objects to target objects using:
- Exact name matching
- Fuzzy matching with confidence scores (e.g., "In Progress" → "InProgress" at 92%)
- Type validation for custom fields (Text → Text, not Text → Number)

```
Match Results:
  EXACT_MATCH:  234 objects (auto-mapped)
  FUZZY_MATCH:   45 objects (suggested, needs review)
  NO_MATCH:      28 objects (will be created)
```

**2. Conflict Detection**

Multiple source objects mapping to the same target? The toolkit catches it:

```
CONFLICTS DETECTED:
  Target 'Approved' ← Sources: ['Approved', 'APPROVED', 'approved']
  Target 'In Progress' ← Sources: ['In Progress', 'InProgress']
```

**3. Customer Review Validation**

Before generating CMJ templates, the toolkit validates the customer-reviewed spreadsheet:

| Check | Example Error |
|-------|---------------|
| Leading/trailing spaces | `" Status Name "` → trim it |
| Copied suggestion text | `"Status Name (85%)"` → remove percentage |
| Invalid actions | `"map"` → should be `"MAP"` |
| Typos | `"Aproved"` vs `"Approved"` in target |
| Duplicate targets | Two sources → same target (conflict) |

**4. Safe Cleanup with JQL Validation**

The generated Groovy cleanup script doesn't blindly delete. It checks first:

```groovy
// Before deleting a status, verify no issues use it
def jql = "status = \"Old Status Name\""
def issueCount = countIssues(jql)

if (issueCount > 0) {
    println "SKIPPED: ${statusName} - ${issueCount} issues use this status"
} else {
    // Safe to delete
    statusManager.removeStatus(statusId)
}
```

---

## Real-World Results

On a recent migration project:

| Metric | Manual Approach | With Toolkit |
|--------|-----------------|--------------|
| Objects processed | 500+ | 500+ |
| Time to generate mappings | ~8 hours | ~10 minutes |
| Human errors caught | Found in UAT | Found before CMJ import |
| Cleanup confidence | "Hope nothing breaks" | JQL-validated, audited |

---

## The Workflow in Practice

### Phase 1: Data Collection (Steps 1-2)

Export data from source and target Jira instances, convert to xlsx for audit trail:

```bash
python3 run_migration.py --step 1  # Convert source data
python3 run_migration.py --step 2  # Convert target data
```

**Output:** Excel workbooks with all objects, IDs, and metadata—easy to review and share.

### Phase 2: Process & Validate (Steps 3-5)

```bash
python3 run_migration.py --step 3  # Process customer mapping
# → Customer reviews the PROCESSED.xlsx file
python3 run_migration.py --step 4  # Validate reviewed file
python3 run_migration.py --step 5  # Filter for CMJ template
```

The validation step is critical. It catches mistakes *before* they become CMJ import failures.

### Phase 3: Generate CMJ Templates (Step 6)

```bash
python3 run_migration.py --step 6  # Generate CMJ XML templates
```

**Output:** Two CMJ template files ready for import:
- `global_cmj_template.cmj` - Statuses, Resolutions, Link Types, Issue Types
- `custom_field_cmj_template.cmj` - Custom Fields (imported separately due to size)

### Phase 4: Post-Deployment Cleanup (Steps 7-11)

After CMJ deployment, export the new target state and generate cleanup:

```bash
python3 run_migration.py --step 7   # Convert post-import data
python3 run_migration.py --step 8   # Generate cleanup report
python3 run_migration.py --step 9   # Generate Groovy cleanup script
python3 run_migration.py --step 10  # Validate dryrun output
python3 run_migration.py --step 11  # Validate liverun output
```

The two-phase validation (dryrun then liverun) ensures nothing gets deleted that shouldn't be.

---

## Architecture Decisions

### Why Python?

- **Pandas** handles large Excel files efficiently
- **Fuzzy matching** libraries for intelligent suggestions
- Cross-platform (works on Mac, Linux, Windows with minor adjustments)
- Easy for admins to modify and extend

### Why xlsx for Everything?

- **Audit trail**: Every conversion is saved
- **Customer-friendly**: Non-technical reviewers can open in Excel
- **Diffable**: Compare pre/post states easily
- **Portable**: Share via email, Teams, etc.

### Why Groovy for Cleanup?

- Runs directly in ScriptRunner console
- Full access to Jira APIs
- DRY_RUN mode for safe testing
- JQL validation before deletion

---

## Lessons Learned

### 1. Validate Early, Validate Often

The #1 cause of CMJ failures in our experience: bad input data. A typo in a target name, an extra space, a copied suggestion with "(85%)" still attached. Catching these before CMJ import saves hours of debugging.

### 2. Protect What Existed Before

Objects that existed in the target *before* migration should never be deleted. The toolkit tracks pre-import state and protects those objects during cleanup.

### 3. Trust but Verify (JQL Checks)

Even after careful planning, always verify with JQL before deleting:
- `status = "StatusName"` → Any issues using this status?
- `"FieldName" is not EMPTY` → Any issues with data in this field?
- `issuetype = "TypeName"` → Any issues of this type?

### 4. Keep the Human in the Loop

Automation handles the tedious work. Humans make the decisions:
- Should this source status map to "Done" or "Closed"?
- Is this fuzzy match correct, or should we create a new object?
- Which of these conflicting mappings wins?

---

## Getting Started

### Prerequisites

- Python 3.8+
- CMJ installed in target Jira
- ScriptRunner for target data export and cleanup execution
- Access to source and target Jira REST APIs

### Quick Start

```bash
# Clone the toolkit
git clone <repository-url>
cd cmj_template

# Install dependencies
pip install -r requirements.txt

# Validate your setup
python3 scripts/run_migration.py --validate

# Run interactively
python3 scripts/run_migration.py
```

### Directory Structure

```
cmj_template/
├── scripts/           # Python automation scripts
├── source_data/       # Source Jira exports
├── target_data/       # Target Jira exports (pre/post)
├── customer_review/   # Processed mappings for review
└── cmj_templates/     # Generated CMJ XML files
```

---

## What's Next?

Future enhancements I'm considering:

- **Web UI**: Flask/Django interface for non-technical users
- **Workflow validation**: Check that mapped statuses exist in target workflows
- **Screen validation**: Verify custom fields appear on expected screens
- **Rollback scripts**: Generate "undo" scripts for cleanup operations

---

## Conclusion

CMJ is a powerful tool, but it's only as good as the data you feed it. This toolkit fills the gap between "we have a mapping spreadsheet" and "CMJ templates are ready to import" with:

- Automated matching and validation
- Conflict detection before it's too late
- Safe, audited post-migration cleanup
- Excel audit trails for everything

If you're facing a large CMJ migration, I hope this approach helps. Happy migrating!

---

**Questions or feedback?** Drop a comment below or reach out directly. I'm always interested in hearing how others are tackling Jira migrations.

---

*Tags: CMJ, Configuration Manager for Jira, Migration, Data Center, Python, Automation, ScriptRunner*