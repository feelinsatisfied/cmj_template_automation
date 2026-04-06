# CMJ Migration Pipeline Guide

A step-by-step guide for running the Configuration Migration for Jira (CMJ) migration pipeline.

---

## Table of Contents

1. [Overview](#overview)
2. [Prerequisites](#prerequisites)
3. [Folder Structure](#folder-structure)
4. [Phase 1: Pre-Migration Setup](#phase-1-pre-migration-setup)
5. [Phase 2: Migration Pipeline (Steps 1-6)](#phase-2-migration-pipeline-steps-1-6)
6. [Phase 3: CMJ Deployment](#phase-3-cmj-deployment)
7. [Phase 4: Post-Migration Cleanup (Steps 7-11)](#phase-4-post-migration-cleanup-steps-7-11)
8. [Multiple Project Groups](#multiple-project-groups)
9. [Troubleshooting](#troubleshooting)

---

## Overview

This pipeline automates the preparation and cleanup of Jira configuration migrations using CMJ (Configuration Migration for Jira). It handles:

- **Status** mapping and cleanup
- **Custom Fields** mapping and cleanup
- **Issue Types** mapping and cleanup
- **Issue Link Types** mapping and cleanup
- **Resolutions** mapping and cleanup

### Pipeline Flow

```
┌─────────────────────────────────────────────────────────────────────┐
│                     PHASE 1: PRE-MIGRATION                          │
│  Collect source data, target data, CMJ snapshots, customer mapping  │
└─────────────────────────────────────────────────────────────────────┘
                                    │
                                    ▼
┌─────────────────────────────────────────────────────────────────────┐
│                  PHASE 2: MIGRATION PIPELINE                        │
│  Steps 1-6: Process mappings, validate, generate CMJ templates      │
└─────────────────────────────────────────────────────────────────────┘
                                    │
                                    ▼
┌─────────────────────────────────────────────────────────────────────┐
│                    PHASE 3: CMJ DEPLOYMENT                          │
│  Import templates into CMJ, deploy snapshot to target               │
└─────────────────────────────────────────────────────────────────────┘
                                    │
                                    ▼
┌─────────────────────────────────────────────────────────────────────┐
│                 PHASE 4: POST-MIGRATION CLEANUP                     │
│  Steps 7-11: Generate cleanup scripts, validate, execute            │
└─────────────────────────────────────────────────────────────────────┘
```

---

## Prerequisites

### Software Requirements

- **Python 3.8+**
- **Required Python packages:**
  ```bash
  pip install pandas openpyxl
  ```
- **macOS** (for `textutil` RTF conversion) or modify scripts for other platforms

### Required Input Files

| File | Location | Description |
|------|----------|-------------|
| Customer Mapping | `source_data/{PROJECT}_Customer_Mapping.xlsx` | Customer-provided mapping decisions |
| Source API Data | `source_data/source_api_full/*.rtf` | Exported from source Jira instance |
| Target Pre-Import Data | `target_data/pre_import/*.rtf` | Exported from target BEFORE CMJ deployment |
| CMJ Snapshots | `source_data/cmj_snapshot_objs/*.csv` | Exported from CMJ after creating snapshot |

---

## Folder Structure

```
cmj_template/                          # Rename to your project key
├── scripts/                           # Pipeline scripts (DO NOT MODIFY)
│   ├── run_migration.py               # Main orchestrator
│   ├── convert_data_to_xlsx.py        # RTF/TXT to Excel converter
│   ├── process_customer_mapping.py    # Mapping processor
│   ├── validate_customer_review.py    # Customer review validator (Step 4)
│   ├── filter_for_cmj_template.py     # CMJ template filter
│   ├── create_cmj_templates.py        # CMJ XML generator
│   ├── generate_cleanup_report_v2.py  # Cleanup report generator
│   ├── generate_groovy_cleanup.py     # Groovy script generator
│   ├── validate_cleanup_results.py    # Cleanup validation (Steps 10-11)
│   ├── archive_project.py             # Project archiver
│   ├── export_all_target_data.groovy  # Target export: run in ScriptRunner
│   ├── check_issuetype_usage.groovy   # Pre-cleanup: check IssueType usage
│   └── check_issuelinktype_usage.groovy # Pre-cleanup: check IssueLinkType usage
│
├── source_data/
│   ├── {PROJECT}_Customer_Mapping.xlsx
│   ├── source_api_full/
│   │   ├── source_field_pre-import.rtf
│   │   ├── source_status_pre-import.rtf
│   │   ├── source_issuetype_pre-import.rtf
│   │   ├── source_issuelinktype_pre-import.rtf
│   │   └── source_resolution_pre-import.rtf
│   └── cmj_snapshot_objs/
│       └── {PROJECT}_diff_*.csv
│
├── target_data/
│   ├── pre_import/                    # BEFORE CMJ deployment
│   │   ├── target_all_objects.txt     # Option A: Consolidated (recommended)
│   │   └── (or 5 RTF files)           # Option B: Individual files (legacy)
│   ├── post_import/                   # AFTER CMJ deployment
│   │   ├── target_all_objects.txt     # Option A: Consolidated (recommended)
│   │   └── (or 5 RTF files)           # Option B: Individual files (legacy)
│   └── cleaning_validation/           # Groovy cleanup script outputs
│       ├── target_cleaning_dryrun.rtf     # Dryrun output (before cleanup)
│       └── target_cleaning_liverun.rtf    # Liverun output (after cleanup)
│
├── customer_review/                   # Generated files for review
│   ├── {PROJECT}_Customer_Mapping_PROCESSED.xlsx
│   ├── {PROJECT}_Customer_Mapping_PROCESSED_Reviewed.xlsx
│   ├── {PROJECT}_Customer_Mapping_PROCESSED_Reviewed_VALIDATED.xlsx
│   ├── {PROJECT}_Customer_Mapping_FOR_CMJ.xlsx
│   ├── {PROJECT}_Customer_Mapping_CLEANUP_REPORT.xlsx
│   └── {PROJECT}_post_cmj_cleanup.groovy
│
├── cmj_templates/                     # Generated CMJ templates
│   ├── {PROJECT}_global_cmj_template.cmj
│   └── {PROJECT}_custom_field_cmj_template.cmj
│
└── archive/                           # Archived project data
```

---

## Phase 1: Pre-Migration Setup

### Step 1.1: Collect Source Data

1. **Export Source API Data** from source Jira instance:
   - Custom Fields: `/rest/api/2/field`
   - Statuses: `/rest/api/2/status`
   - Issue Types: `/rest/api/2/issuetype`
   - Issue Link Types: `/rest/api/2/issueLinkType`
   - Resolutions: `/rest/api/2/resolution`

2. **Save as RTF files** in `source_data/source_api_full/`:
   - `source_field_pre-import.rtf`
   - `source_status_pre-import.rtf`
   - `source_issuetype_pre-import.rtf`
   - `source_issuelinktype_pre-import.rtf`
   - `source_resolution_pre-import.rtf`

### Step 1.2: Collect Target Pre-Import Data

Export target Jira data BEFORE CMJ deployment. Choose ONE method:

#### Option A: Consolidated Export (Recommended)

1. Run `scripts/export_all_target_data.groovy` in ScriptRunner Console
2. Copy the entire output and save as `target_all_objects.txt`
3. Place in `target_data/pre_import/`

This single file replaces all 5 RTF files below.

#### Option B: Individual RTF Files (Legacy)

1. **Export Target API Data** from target Jira instance:
   - Same endpoints as source

2. **Save as RTF files** in `target_data/pre_import/`:
   - `target_field_pre-import.rtf`
   - `target_status_pre-import.rtf`
   - `target_issuetype_pre-import.rtf`
   - `target_issuelinktype_pre-import.rtf`
   - `target_resolution_pre-import.rtf`

### Step 1.3: Export CMJ Snapshots

1. In CMJ, create your migration snapshot
2. Export the snapshot diff CSV files
3. Place in `source_data/cmj_snapshot_objs/`

### Step 1.4: Prepare Customer Mapping

1. Place the customer mapping file in `source_data/`:
   - Filename format: `{PROJECT}_Customer_Mapping.xlsx`
   - Example: `PROJECT_Customer_Mapping.xlsx`

### Step 1.5: Validate Setup

```bash
cd /path/to/cmj_template
python3 scripts/run_migration.py --validate
```

All prerequisites should show green checkmarks.

---

## Phase 2: Migration Pipeline (Steps 1-6)

### Running Individual Steps

```bash
python3 scripts/run_migration.py --step N    # Run specific step
```

### Running All Pre-Deployment Steps

```bash
python3 scripts/run_migration.py --step 1
python3 scripts/run_migration.py --step 2
python3 scripts/run_migration.py --step 3
# PAUSE: Customer reviews _PROCESSED.xlsx → saves as _PROCESSED_Reviewed.xlsx
python3 scripts/run_migration.py --step 4    # Validate customer review
python3 scripts/run_migration.py --step 5
python3 scripts/run_migration.py --step 6
```

---

### Step 1: Convert Source Data to XLSX

```bash
python3 scripts/run_migration.py --step 1
```

**What it does:**
- Converts source RTF files to Excel for audit trail
- Output: `source_data/source_api_full/source_data_converted.xlsx`

---

### Step 2: Convert Target Pre-Import Data to XLSX

```bash
python3 scripts/run_migration.py --step 2
```

**What it does:**
- Converts target pre-import RTF files to Excel
- Output: `target_data/pre_import/target_data_pre_import_converted.xlsx`

---

### Step 3: Process Customer Mapping

```bash
python3 scripts/run_migration.py --step 3
```

**What it does:**
- Enriches mapping with Source IDs and Target IDs
- Auto-matches objects (exact match, fuzzy match)
- Detects conflicts (multiple sources → same target)
- Adds CMJ snapshot objects not in original mapping

**Output:** `customer_review/{PROJECT}_Customer_Mapping_PROCESSED.xlsx`

---

### Step 3.5: CUSTOMER REVIEW (Manual Step)

**CRITICAL:** This step requires human review.

1. Open `{PROJECT}_Customer_Mapping_PROCESSED.xlsx`
2. Review each sheet (Status, CustomFields, IssueTypes, etc.)
3. For each row, verify/set the **Migration Action**:
   - `MAP` - Map source object to existing target object
   - `CREATE` - Create new object on target
   - `SKIP` - Skip this object (don't migrate)
   - `DELETE` - Delete after migration (cleanup)

4. For `MAP` actions, verify **Target Name** and **Target ID** are correct

5. **Save as:** `{PROJECT}_Customer_Mapping_PROCESSED_Reviewed.xlsx`

---

### Step 4: Validate Customer Review

```bash
python3 scripts/run_migration.py --step 4
```

**What it does:**
- Validates the customer-reviewed mapping file before CMJ template generation
- Catches common errors that would cause migration issues

**Validation checks:**
- Leading/trailing spaces in names
- Copied suggestion text with percentages (e.g., "Name (85%)")
- Objects that don't exist in source/target data
- Misspellings (fuzzy match detection)
- Invalid Migration Actions
- Empty required fields
- Duplicate mappings

**Auto-fix mode:**
```bash
python3 scripts/validate_customer_review.py --auto-fix
```
- Automatically trims spaces from names
- Normalizes Migration Action case (e.g., "map" → "MAP")
- Outputs: `{PROJECT}_Customer_Mapping_PROCESSED_Reviewed_VALIDATED.xlsx`

**Output:** Validation report to console with errors (blocking) and warnings (non-blocking)

---

### Step 5: Filter for CMJ Template

```bash
python3 scripts/run_migration.py --step 5
```

**What it does:**
- Filters reviewed mapping to only CMJ-relevant operations
- Excludes exact matches (no action needed)
- Excludes objects not in CMJ snapshot

**Output:** `customer_review/{PROJECT}_Customer_Mapping_FOR_CMJ.xlsx`

**Warnings to watch for:**
- `MAP action but no Target ID` - Object needs target assignment

---

### Step 6: Create CMJ Templates

```bash
python3 scripts/run_migration.py --step 6
```

**What it does:**
- Generates CMJ XML template files for import

**Output:**
- `cmj_templates/{PROJECT}_global_cmj_template.cmj` - Status, Resolutions, IssueLinkTypes, IssueTypes
- `cmj_templates/{PROJECT}_custom_field_cmj_template.cmj` - Custom Fields only

---

## Phase 3: CMJ Deployment

### Step 3.1: Import CMJ Templates

1. Open CMJ in Jira
2. Import `{PROJECT}_global_cmj_template.cmj` **FIRST**
3. Import `{PROJECT}_custom_field_cmj_template.cmj` **SECOND**
4. Verify rematch operations look correct

### Step 3.2: Deploy CMJ Snapshot

1. Review the CMJ snapshot
2. Deploy to target instance
3. Monitor for errors

### Step 3.3: Collect Post-Import Data

After successful CMJ deployment, export target data again. Choose ONE method:

#### Option A: Consolidated Export (Recommended)

1. Run `scripts/export_all_target_data.groovy` in ScriptRunner Console
2. Copy the entire output and save as `target_all_objects.txt`
3. Place in `target_data/post_import/`

#### Option B: Individual RTF Files (Legacy)

1. **Export Target API Data** again (same endpoints)
2. **Save as RTF files** in `target_data/post_import/`:
   - `target_field_post-import.rtf`
   - `target_status_post-import.rtf`
   - `target_issuetype_post-import.rtf`
   - `target_issuelinktype_post-import.rtf`
   - `target_resolution_post-import.rtf`

---

## Phase 4: Post-Migration Cleanup (Steps 7-11)

### Step 6.5: Check Object Usage (Optional but Recommended)

Before generating cleanup reports, run the usage checker scripts on the **target** instance to identify which IssueTypes and IssueLinkTypes are actually in use. This helps make informed decisions about what to delete.

**Scripts location:** `scripts/`

#### Check IssueType Usage

1. Copy `scripts/check_issuetype_usage.groovy` content
2. Run in target Jira's Script Console (ScriptRunner)
3. Review output:

```
ISSUE TYPE USAGE REPORT
================================================================================
ID     | Issue Type Name                          | Count      | Subtask?   | Status
--------------------------------------------------------------------------------
10001  | Bug                                      | 2847       | No         | IN USE
10002  | Epic                                     | 156        | No         | IN USE
10003  | Legacy Task                              | 0          | No         | NOT USED
...

CANDIDATES FOR DELETION (not in use):
  - Legacy Task (ID: 10003)

DO NOT DELETE (in use):
  - Bug (ID: 10001) - 2847 issues
```

#### Check IssueLinkType Usage

1. Copy `scripts/check_issuelinktype_usage.groovy` content
2. Run in target Jira's Script Console (ScriptRunner)
3. Review output:

```
ISSUE LINK TYPE USAGE REPORT
================================================================================
ID    | Link Type Name                           | Count      | Status
--------------------------------------------------------------------------------
10001 | Blocks                                   | 1523       | IN USE
10002 | Clones                                   | 0          | NOT USED
...

CANDIDATES FOR DELETION (not in use):
  - Clones (ID: 10002)

DO NOT DELETE (in use):
  - Blocks (ID: 10001) - 1523 links
```

**Important:** Even objects showing "NOT USED" may be referenced in:
- Automation rules
- ScriptRunner scripts
- Workflow post-functions
- External integrations

Always verify with stakeholders before including in cleanup.

---

### Step 7: Convert Post-Import Data to XLSX

```bash
python3 scripts/run_migration.py --step 7
```

**What it does:**
- Converts post-import RTF files to Excel for audit trail
- Output: `target_data/post_import/target_data_post_import_converted.xlsx`

---

### Step 8: Generate Cleanup Report

```bash
python3 scripts/run_migration.py --step 8
```

**What it does:**
- Compares pre-import vs post-import target data
- Identifies objects created by CMJ
- Determines what should be deleted vs kept
- Protects objects that:
  - Existed before CMJ (pre-import)
  - Are used in workflows
  - Are on screens (custom fields)
  - Have mapped names

**Output:** `customer_review/{PROJECT}_Customer_Mapping_CLEANUP_REPORT.xlsx`

**Sheets:**
- `SUMMARY` - Overview of deletion vs protection
- `DELETE_*` - Objects marked for deletion in mapping
- `KEEP_*` - Objects protected from deletion
- `CMJ_DELETE_*` - CMJ-created objects to delete
- `CMJ_KEEP_*` - CMJ-created objects to keep

---

### Step 9: Generate Groovy Cleanup Script

```bash
python3 scripts/run_migration.py --step 9
```

**What it does:**
- Generates Groovy script for Jira ScriptRunner
- Includes all objects to delete with their IDs
- Includes JQL safety checks for custom fields

**Output:** `customer_review/{PROJECT}_post_cmj_cleanup.groovy`

---

### Step 9.5: Run Cleanup Script - Dry Run (Manual Step)

1. **Open** the generated Groovy script
2. **Verify** `DRY_RUN = true` (default)
3. **Run** in Jira Script Console (ScriptRunner)
4. **Copy** the output to `target_data/cleaning_validation/target_cleaning_dryrun.rtf`

---

### Step 10: Validate Cleanup Dryrun

```bash
python3 scripts/run_migration.py --step 10
```

**What it does:**
- Validates dryrun output BEFORE running live cleanup
- Ensures all items to be deleted are in the cleanup report
- Flags any unexpected deletions

**Output:** Validation report showing:
- CustomFields to delete
- Statuses to delete
- Resolutions (manual delete required)
- Items skipped and why

**If validation fails:** Review the cleanup report and dryrun output. Do NOT proceed to live cleanup until issues are resolved.

---

### Step 10.5: Run Cleanup Script - Live Run (Manual Step)

1. **Set** `DRY_RUN = false` in the Groovy script
2. **Run** in Jira Script Console (ScriptRunner)
3. **Copy** the output to `target_data/cleaning_validation/target_cleaning_liverun.rtf`

**Note:** Resolutions cannot be deleted programmatically in Jira Server. Delete manually via:
`Jira Admin > Issues > Resolutions`

---

### Step 11: Validate Cleanup Liverun

```bash
python3 scripts/run_migration.py --step 11
```

**What it does:**
- Validates liverun output AFTER cleanup execution
- Ensures liverun matches dryrun (nothing unexpected deleted)
- Confirms all deletions were authorized

**Output:** Final validation report confirming:
- Items deleted match what was expected
- No unexpected deletions occurred
- Cleanup completed successfully

---

## Multiple Project Groups

For multiple POCs or project groups, create separate copies of the entire folder:

```
PythonProject/
├── PROJECT_GROUP_A/           # Copy of cmj_template
│   ├── source_data/
│   ├── target_data/
│   ├── customer_review/
│   ├── cmj_templates/
│   └── scripts/
│
├── PROJECT_GROUP_B/           # Another copy
│   ├── source_data/
│   ├── target_data/
│   ├── customer_review/
│   ├── cmj_templates/
│   └── scripts/
```

**Benefits:**
- Complete isolation between groups
- No risk of conflicts
- Each group can proceed at their own pace
- Simple folder-based organization

---

## Troubleshooting

### Common Issues

#### "No processed mapping file found"
- Ensure Step 3 completed successfully
- Check `customer_review/` for `*_PROCESSED.xlsx`

#### "MAP action but no Target ID"
- The target object doesn't exist in target system
- Options:
  - Change Migration Action to `CREATE`
  - Add the object to target system first
  - Fix the Target Name to match an existing object

#### "Objects created by CMJ but protected"
- Objects are kept if they:
  - Existed in pre-import (by ID or NAME)
  - Are used in workflows
  - Are on screens
  - Have mapped names in customer mapping

#### Groovy script errors
- `HTTP 405` on Resolution deletion - Jira API limitation, delete manually
- `Object in use` - Object is used by issues/workflows, clean up first

### Validation Command

```bash
python3 scripts/run_migration.py --validate
```

### Archive Previous Project

Before starting a new project with the same folder:

```bash
python3 scripts/archive_project.py
```

---

## Quick Reference

| Phase | Step | Command | Output |
|-------|------|---------|--------|
| Pre | Validate | `--validate` | Console output |
| 2 | 1 | `--step 1` | Source xlsx |
| 2 | 2 | `--step 2` | Target pre-import xlsx |
| 2 | 3 | `--step 3` | Processed mapping |
| 2 | *Review* | *Manual* | Reviewed mapping |
| 2 | 4 | `--step 4` | Validation report |
| 2 | 5 | `--step 5` | FOR_CMJ mapping |
| 2 | 6 | `--step 6` | CMJ templates |
| 3 | Deploy | *CMJ UI* | Deployed snapshot |
| 4 | *6.5* | *ScriptRunner* | Usage reports (optional) |
| 4 | 7 | `--step 7` | Post-import xlsx |
| 4 | 8 | `--step 8` | Cleanup report |
| 4 | 9 | `--step 9` | Groovy script |
| 4 | *Dryrun* | *ScriptRunner* | Dryrun output |
| 4 | 10 | `--step 10` | Dryrun validation |
| 4 | *Liverun* | *ScriptRunner* | Liverun output |
| 4 | 11 | `--step 11` | Liverun validation |

---

## Support

For issues or questions, contact the migration team or refer to the CMJ documentation.
