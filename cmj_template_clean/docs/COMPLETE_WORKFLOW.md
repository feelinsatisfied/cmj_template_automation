# Complete CMJ Migration Workflow

**Version:** 3.3.0
**Last Updated:** 2026-02-25

## Overview

This workflow automates the CMJ (Configuration Manager for Jira) migration process for multi-project Jira Data Center migrations. It provides:

- **Auto-detection** of customer mapping files and project data
- **Automated field matching** with fuzzy logic and confidence scores
- **Conflict detection** (multiple sources mapping to same target)
- **xlsx audit trail** for all data conversions
- **Interactive orchestrator** for step-by-step execution
- **Post-migration cleanup** with Groovy script generation

---

## Prerequisites

### Software Requirements

- Python 3.8 or higher
- macOS (uses `textutil` for RTF conversion)
- pip package manager

### Python Dependencies

```bash
pip install -r requirements.txt
```

Required packages:
- `pandas>=2.0.0`
- `openpyxl>=3.1.0`
- `requests>=2.31.0`

### Access Requirements

- Source Jira instance (for API data export)
- Target Jira instance (for data export via ScriptRunner Groovy scripts)
- CMJ (Configuration Manager for Jira) installed on target
- ScriptRunner (required - for target data export and post-migration cleanup)

---

## Directory Structure

```
cmj_template/
├── scripts/                           # Python automation scripts
│   ├── run_migration.py               # Orchestrator (main entry point)
│   ├── convert_data_to_xlsx.py        # RTF to xlsx converter
│   ├── process_customer_mapping.py    # Mapping processor
│   ├── validate_customer_review.py    # Customer review validator
│   ├── filter_for_cmj_template.py     # Template filter
│   ├── create_cmj_templates.py        # CMJ XML generator
│   ├── generate_cleanup_report_v2.py  # Cleanup report generator
│   ├── generate_groovy_cleanup.py     # Groovy script generator
│   └── validate_cleanup_results.py    # Cleanup validation
│
├── source_data/                       # Source Jira data
│   ├── {PROJECT}_Customer_Mapping.xlsx    # Customer mapping input
│   ├── source_api_full/               # Source API exports (RTF/JSON)
│   │   ├── *_field_api.rtf            # Custom fields
│   │   ├── *_status_api.rtf           # Statuses
│   │   ├── *_issuetype_api.rtf        # Issue types
│   │   ├── *_issuelinktype_api.rtf    # Issue link types
│   │   ├── *_resolution_api.rtf       # Resolutions
│   │   └── source_data_converted.xlsx # Generated audit file
│   └── cmj_snapshot_objs/             # CMJ snapshot CSV exports
│       └── {PROJECTKEY}_*_cmj.csv     # Per-project snapshots
│
├── target_data/                       # Target Jira data
│   ├── pre_import/                    # Pre-deployment data (via ScriptRunner)
│   │   ├── target_field_pre-import.rtf
│   │   ├── target_status_pre-import.rtf
│   │   ├── target_issuetype_pre-import.rtf
│   │   ├── target_issuelinktype_pre-import.rtf
│   │   ├── target_resolution_pre-import.rtf
│   │   └── target_data_pre_import_converted.xlsx  # Generated audit file
│   └── post_import/                   # Post-deployment data (via ScriptRunner)
│       ├── target_field_post_import.rtf
│       ├── target_status_post_import.rtf
│       ├── target_issuetype_post_import.rtf
│       ├── target_issuelinktype_post_import.rtf
│       ├── target_resolution_post_import.rtf
│       └── target_data_post_import_converted.xlsx
│
├── customer_review/                   # Processed mapping outputs
│   └── {PROJECT}_Customer_Mapping_PROCESSED.xlsx
│
├── cmj_templates/                     # Generated CMJ XML files
│   ├── global_cmj_template.cmj
│   └── custom_field_cmj_template.cmj
│
├── requirements.txt
├── setup.py
├── pyproject.toml
└── README.md
```

---

## Migration Pipeline Overview

The migration process consists of 11 steps, split into pre-deployment (1-6) and post-deployment (7-11):

### Pre-Deployment Steps

| Step | Script | Description |
|------|--------|-------------|
| 1 | `convert_data_to_xlsx.py --source` | Convert source API data to xlsx |
| 2 | `convert_data_to_xlsx.py --target-pre` | Convert target pre-import data to xlsx |
| 3 | `process_customer_mapping.py` | Process mapping with IDs, matches, conflicts |
| 4 | `validate_customer_review.py` | Validate customer-reviewed mapping file |
| 5 | `filter_for_cmj_template.py` | Filter for CMJ template generation |
| 6 | `create_cmj_templates.py` | Generate CMJ XML templates |

### Manual Steps (Between Pre and Post)

1. Review processed mapping file
2. Import CMJ templates into target Jira
3. Deploy CMJ snapshot
4. Export post-import target data

### Post-Deployment Steps

| Step | Script | Description |
|------|--------|-------------|
| 7 | `convert_data_to_xlsx.py --target-post` | Convert post-import data to xlsx |
| 8 | `generate_cleanup_report_v2.py` | Create cleanup report |
| 9 | `generate_groovy_cleanup.py` | Generate Groovy cleanup script |
| 10 | `validate_cleanup_results.py --dryrun` | Validate dryrun output |
| 11 | `validate_cleanup_results.py --liverun` | Validate liverun output |

---

## Phase 1: Data Collection

### Step 1.1: Prepare Customer Mapping File

Create or obtain the customer mapping file with their desired mappings.

**File Location:** `source_data/{PROJECT}_Customer_Mapping.xlsx`

**Naming Convention:** The project key (e.g., "ACME") is extracted from the filename:
- `ACME_Customer_Mapping.xlsx` → Project key: "ACME"
- `ACME_Customer_Mapping.xlsx` → Project key: "ACME"

**Required Sheets:**

| Sheet | Description |
|-------|-------------|
| Status | Status mappings |
| CustomFields | Custom field mappings |
| Resolutions | Resolution mappings |
| IssueLinkTypes | Issue link type mappings |
| IssueTypes | Issue type mappings |

**Required Columns per Sheet:**

| Column | Required | Description |
|--------|----------|-------------|
| Project | Yes | Project key (e.g., PROJCMR, PROJTER) |
| Source Name | Yes | Name of source object |
| Target Name | No | Name of target object (if mapping) |
| Migration Action | No | MAP, CREATE, SKIP, DELETE |
| Source ID | No | Will be enriched automatically |
| Target ID | No | Will be enriched automatically |
| Match Type | No | Will be set automatically |
| Confidence | No | Will be set automatically |

**Additional Columns for CustomFields:**

| Column | Description |
|--------|-------------|
| Screen | Screen name (if applicable) |
| On Screen | Yes/No - is field on project screens |
| Source Type | Field type (e.g., Text Field, Select List) |
| Target Type | Target field type |

### Step 1.2: Export Source API Data

Export data from your **source Jira instance** using the REST API.

**API Endpoints:**

| Data Type | Endpoint |
|-----------|----------|
| Custom Fields | `/rest/api/2/field` |
| Statuses | `/rest/api/2/status` |
| Issue Types | `/rest/api/2/issuetype` |
| Issue Link Types | `/rest/api/2/issueLinkType` |
| Resolutions | `/rest/api/2/resolution` |

**How to Export:**

1. Navigate to each API endpoint in your browser
2. Copy the JSON response
3. Paste into a text editor (TextEdit on Mac)
4. Save as RTF format
5. Place in `source_data/source_api_full/`

**Expected Files:**

```
source_data/source_api_full/
├── {project}_source_field_api.rtf
├── {project}_source_status_api.rtf
├── {project}_source_issuetype_api.rtf
├── {project}_source_issuelinktype_api.rtf
└── {project}_source_resolution_api.rtf
```

### Step 1.3: Export Target Pre-Import Data

Export data from your **target Jira instance** BEFORE CMJ deployment using ScriptRunner Groovy scripts.

**Why Groovy scripts?**
- REST API has limitations that prevent exporting all objects
- Groovy scripts provide complete data access for all object types

**Expected Files:**

```
target_data/pre_import/
├── target_field_pre-import.rtf
├── target_status_pre-import.rtf
├── target_issuetype_pre-import.rtf
├── target_issuelinktype_pre-import.rtf
└── target_resolution_pre-import.rtf
```

**Format:** Target files can be either:
- JSON format (direct API response)
- CSV-like format with quoted values

### Step 1.4: Export CMJ Snapshot CSVs

Export the CMJ snapshot data for each project being migrated.

**Location:** `source_data/cmj_snapshot_objs/`

**Naming Convention:** `{PROJECTKEY}_*_cmj.csv`

**Examples:**
```
source_data/cmj_snapshot_objs/
├── PROJCMR_JSM_Project_Configuration_cmj.csv
├── PROJCR_Software_Project_Configuration_cmj.csv
├── PROJTER_Project_Configuration_cmj.csv
└── PROJRIP_Software_Project_Configuration_cmj.csv
```

**Required Columns in CSV:**

| Column | Description |
|--------|-------------|
| category | Object category (e.g., "Custom Fields", "Statuses") |
| type | Object type (e.g., "Custom Field", "Status") |
| name | Object name |
| changeKind | CMJ change type: Added, Changed, Unchanged |

**What Gets Included:**
- Objects with `changeKind` = "Added" or "Changed"
- These are objects that CMJ will create or modify

---

## Phase 2: Data Conversion (Steps 1-2)

### Using the Orchestrator (Recommended)

```bash
cd scripts

# Validate all prerequisites first
python3 run_migration.py --validate

# Run steps 1-2 interactively
python3 run_migration.py
```

### Running Steps Individually

**Step 1: Convert Source Data to xlsx**

```bash
python3 convert_data_to_xlsx.py --source
```

**What This Does:**
1. Reads RTF files from `source_data/source_api_full/`
2. Extracts JSON data using `textutil`
3. Creates `source_data_converted.xlsx` with tabs:
   - CustomFields
   - Statuses
   - IssueTypes
   - IssueLinkTypes
   - Resolutions
   - _Metadata (conversion timestamp)

**Output:**
```
source_data/source_api_full/source_data_converted.xlsx
```

**Step 2: Convert Target Pre-Import Data to xlsx**

```bash
python3 convert_data_to_xlsx.py --target-pre
```

**What This Does:**
1. Reads RTF files from `target_data/pre_import/`
2. Handles both JSON and CSV-like formats
3. Creates `target_data_pre_import_converted.xlsx` with same tabs

**Output:**
```
target_data/pre_import/target_data_pre_import_converted.xlsx
```

### xlsx Audit Trail

The converted xlsx files provide:
- **Audit trail** - Record of all data at conversion time
- **Easy validation** - Open in Excel to verify data
- **Consistent format** - Same structure for source and target
- **Metadata** - Conversion timestamp and record counts

---

## Phase 3: Process Customer Mapping (Step 3)

### Running the Processor

```bash
python3 process_customer_mapping.py
```

Or specify a file explicitly:

```bash
python3 process_customer_mapping.py --mapping-file /path/to/file.xlsx
```

### What This Does

1. **Auto-detects customer mapping file**
   - Looks for `*_Customer_Mapping.xlsx` in `source_data/`
   - Extracts project key from filename

2. **Loads source data from converted xlsx**
   - CustomFields with IDs and types
   - Statuses, IssueTypes, IssueLinkTypes, Resolutions

3. **Loads target data from converted xlsx**
   - Same structure as source

4. **Parses CMJ snapshots**
   - Reads all CSV files in `cmj_snapshot_objs/`
   - Identifies objects with changeKind = Added or Changed
   - Marks "On Screen" status for objects in snapshot

5. **Processes each sheet:**

   **Enriches Source IDs:**
   - Looks up Source ID from source data by name
   - Adds Source Type for CustomFields

   **Enriches Target IDs:**
   - Looks up Target ID from target data by name
   - Adds Target Type for CustomFields

   **Determines Match Type:**

   | Match Type | Criteria |
   |------------|----------|
   | EXACT_MATCH | Source Name = Target Name (and Type for fields) |
   | FUZZY_MATCH | Similarity ratio >= 85% |
   | MANUAL_MATCH | Customer specified different names |
   | NO_MATCH | No target specified, will be created |

   **Sets Confidence:**

   | Match Type | Confidence |
   |------------|------------|
   | EXACT_MATCH | High |
   | FUZZY_MATCH (>=90%) | Medium |
   | FUZZY_MATCH (<90%) | Low |
   | MANUAL_MATCH | Medium |
   | NO_MATCH | N/A |

   **Sets Migration Action (if not already set):**

   | Match Type | Default Action |
   |------------|----------------|
   | EXACT_MATCH | MAP |
   | FUZZY_MATCH | MAP |
   | MANUAL_MATCH | MAP |
   | NO_MATCH | CREATE |

6. **Detects Conflicts**
   - Identifies when multiple source objects map to the same target
   - Reports conflicts in console output
   - Example: Target 'Approved' ← Sources: ['Approved', 'Approved', 'Approved']

7. **Adds Snapshot Objects**
   - Objects in CMJ snapshot but not in customer mapping
   - Automatically matched to target if possible
   - Marked as "On Screen" = Yes

8. **Removes Duplicates**
   - Deduplicates by Source Name (case-insensitive)
   - Keeps first occurrence

### Output

**File:** `customer_review/{PROJECT}_Customer_Mapping_PROCESSED.xlsx`

**Sheets:**
- Status
- CustomFields
- Resolutions
- IssueLinkTypes
- IssueTypes
- _Metadata

### Console Output Example

```
================================================================================
CUSTOMER MAPPING PROCESSOR
================================================================================
Timestamp: 2026-01-19 14:07:14

🔍 Auto-detecting customer mapping file...

📁 Input file: source_data/ACME_Customer_Mapping.xlsx
📋 Project key: ACME

📊 Loading Source API Data...
  ✓ CustomFields: 666 loaded
  ✓ Status: 284 loaded
  ✓ IssueTypes: 75 loaded

📊 Loading Target Data...
  ✓ CustomFields: 1745 loaded
  ✓ Status: 890 loaded

📊 Parsing CMJ Snapshots...
  ✓ Status: 13 objects found
  ✓ CustomFields: 206 objects found

================================================================================
PROCESSING: Status
================================================================================

📝 Processing Status...
  ⚠ CONFLICTS DETECTED (21):
    Target 'Analysis' ← Sources: ['Analysis', 'Analysis', 'Analysis']
    Target 'Approved' ← Sources: ['Approved', 'Approved', 'Approved']
  ✓ Enriched 84 source IDs
  ✓ Enriched 83 target IDs
  ✓ Exact matches: 71
  ✓ Fuzzy matches: 12
  ✓ Manual matches: 10
  ✓ No matches: 10

================================================================================
PROCESSING SUMMARY
================================================================================

Status:
  Total objects: 42
  ⚠ Conflicts: 21
    EXACT_MATCH: 25
    FUZZY_MATCH: 7
    MANUAL_MATCH: 5
    NO_MATCH: 5

✅ PROCESSING COMPLETE!
Total records processed: 289
⚠ Total conflicts detected: 65

Output: customer_review/ACME_Customer_Mapping_PROCESSED.xlsx
```

---

## Phase 4: Review Processed Mapping

### Step 4.1: Open Processed File

Open the processed mapping file:

```
customer_review/{PROJECT}_Customer_Mapping_PROCESSED.xlsx
```

### Step 4.2: Understand the Columns

| Column | Description |
|--------|-------------|
| Project | Source project key |
| Source ID | Enriched from source API data |
| Source Name | Original source object name |
| Target ID | Enriched from target API data |
| Target Name | Mapped target object name |
| Match Type | EXACT_MATCH, FUZZY_MATCH, MANUAL_MATCH, NO_MATCH |
| Confidence | High, Medium, Low, N/A |
| Migration Action | MAP, CREATE, SKIP, DELETE |
| On Screen | Yes/No - is object in CMJ snapshot |

**Additional for CustomFields:**

| Column | Description |
|--------|-------------|
| Source Type | Source field type |
| Target Type | Target field type |
| Target Suggestion #1/2/3 | Fuzzy match suggestions with confidence |

### Step 4.3: Review by Priority

**Priority Order:**

1. **Conflicts** - Multiple sources → same target
   - Search for duplicates in Target Name column
   - Decide which source should map to target
   - Change others to CREATE or different target

2. **NO_MATCH items** - Will be created
   - Review if a target mapping exists
   - Check suggestions for potential matches
   - Change to MAP if appropriate

3. **FUZZY_MATCH items** - Auto-matched
   - Verify the match is correct
   - Check Source Type vs Target Type for fields
   - Change to CREATE if match is wrong

4. **MANUAL_MATCH items** - Customer specified
   - Verify the mapping is intentional
   - Ensure Target ID is correct

### Step 4.4: Update Migration Actions

| Action | Meaning | When to Use |
|--------|---------|-------------|
| MAP | Remap to existing target | Source → Target mapping |
| CREATE | Create new in target | New object needed |
| SKIP | Ignore this object | Don't include in template |
| DELETE | Mark for deletion | Post-migration cleanup |

### Step 4.5: Save Changes

Save the file after review. The subsequent steps will read from this file.

---

## Phase 5: Generate CMJ Templates (Steps 4-6)

### Running with Orchestrator

```bash
python3 run_migration.py
# Choose to run steps 4, 5, 6
```

Or run all remaining pre-deployment steps:

```bash
python3 run_migration.py --auto
```

### Step 4: Validate Customer Review

```bash
python3 validate_customer_review.py
```

**What This Does:**
- Validates the customer-reviewed mapping file
- Catches common errors before CMJ template generation:
  - Leading/trailing spaces in names
  - Copied suggestion text with percentages (e.g., "Name (85%)")
  - Objects that don't exist in source/target data
  - Misspellings (fuzzy match detection)
  - Invalid Migration Actions
  - Duplicate mappings

**Auto-fix mode:**
```bash
python3 validate_customer_review.py --auto-fix
```

### Step 5: Filter for CMJ Template

```bash
python3 filter_for_cmj_template.py
```

**What This Does:**
- Reads processed mapping file
- Filters objects based on Migration Action
- Prepares data for CMJ template generation

### Step 6: Create CMJ Templates

```bash
python3 create_cmj_templates.py
```

**What This Does:**
- Generates CMJ XML template files
- Creates two files for import order

**Output Files:**

```
cmj_templates/
├── global_cmj_template.cmj      # Statuses, Resolutions, IssueLinkTypes, IssueTypes
└── custom_field_cmj_template.cmj # CustomFields only
```

**Why Two Files?**
- Global objects must be imported first
- Custom fields may reference global objects
- Import order prevents dependency errors

---

## Phase 6: CMJ Deployment (Manual)

### Step 6.1: Import CMJ Templates

**Order is critical - follow this sequence:**

1. **Import global_cmj_template.cmj FIRST**
   - CMJ > Import Template
   - Select `cmj_templates/global_cmj_template.cmj`
   - Review and confirm

2. **Import custom_field_cmj_template.cmj SECOND**
   - CMJ > Import Template
   - Select `cmj_templates/custom_field_cmj_template.cmj`
   - Review and confirm

### Step 6.2: Configure CMJ Migration

In CMJ, configure:
- Source project key(s)
- Target project key(s)
- Migration mode
- User mapping
- Attachment handling

### Step 6.3: Deploy CMJ Snapshot

1. Click "Start Migration" in CMJ
2. Monitor progress
3. Review logs for errors
4. Verify completion

### Step 6.4: Export Post-Import Target Data

After deployment completes:

1. Export target data using same API endpoints
2. Save RTF files to `target_data/post_import/`:

```
target_data/post_import/
├── target_field_post_import.rtf
├── target_status_post_import.rtf
├── target_issuetype_post_import.rtf
├── target_linkissuetype_post_import.rtf
└── target_resolution_post_import.rtf
```

---

## Phase 7: Post-Deployment Cleanup (Steps 7-11)

### Running Post-Deployment Steps

```bash
python3 run_migration.py --post
```

### Step 7: Convert Post-Import Data

```bash
python3 convert_data_to_xlsx.py --target-post
```

**Output:**
```
target_data/post_import/target_data_post_import_converted.xlsx
```

### Step 8: Generate Cleanup Report

```bash
python3 generate_cleanup_report_v2.py
```

**What This Does:**
- Compares pre-import vs post-import target data
- Identifies objects created by CMJ
- Determines what should be deleted vs kept

**Output:**
```
customer_review/{PROJECT}_Customer_Mapping_CLEANUP_REPORT.xlsx
```

### Step 9: Generate Groovy Cleanup Script

```bash
python3 generate_groovy_cleanup.py
```

**What This Does:**
- Reads cleanup report
- Matches source objects to new target IDs
- Generates ScriptRunner Groovy script with JQL safety checks

**Output:**
```
customer_review/{PROJECT}_post_cmj_cleanup.groovy
```

### Running the Cleanup Script (Dry Run)

1. Open target Jira
2. Navigate to: Settings > Manage Apps > ScriptRunner > Console
3. Paste script contents
4. **Verify `DRY_RUN = true` (default)**
5. Run and copy output to `target_data/cleaning_validation/target_cleaning_dryrun.rtf`

### Step 10: Validate Dryrun Output

```bash
python3 validate_cleanup_results.py --dryrun
```

**What This Does:**
- Validates dryrun output BEFORE running live cleanup
- Ensures all items to be deleted are in the cleanup report
- Flags any unexpected deletions

### Running the Cleanup Script (Live Run)

1. Set `DRY_RUN = false` in the Groovy script
2. Run in ScriptRunner Console
3. Copy output to `target_data/cleaning_validation/target_cleaning_liverun.rtf`

### Step 11: Validate Liverun Output

```bash
python3 validate_cleanup_results.py --liverun
```

**What This Does:**
- Validates liverun output AFTER cleanup execution
- Ensures liverun matches dryrun (nothing unexpected deleted)
- Confirms all deletions were authorized

---

## Quick Command Reference

### Orchestrator Commands

```bash
cd scripts

# Validate prerequisites
python3 run_migration.py --validate

# Interactive mode (recommended)
python3 run_migration.py

# Run all pre-deployment steps automatically
python3 run_migration.py --auto

# Run specific step (1-11)
python3 run_migration.py --step 3

# Run post-deployment steps
python3 run_migration.py --post
```

### Individual Script Commands

```bash
cd scripts

# Data conversion
python3 convert_data_to_xlsx.py --all
python3 convert_data_to_xlsx.py --source
python3 convert_data_to_xlsx.py --target-pre
python3 convert_data_to_xlsx.py --target-post

# Mapping processing
python3 process_customer_mapping.py
python3 process_customer_mapping.py --mapping-file /path/to/file.xlsx

# Template generation
python3 filter_for_cmj_template.py
python3 create_cmj_templates.py

# Cleanup
python3 generate_cleanup_report_v2.py
python3 generate_groovy_cleanup.py
```

---

## Troubleshooting

### "No customer mapping file found"

**Problem:** Orchestrator can't find the mapping file.

**Solution:**
- Ensure file is in `source_data/` directory
- Filename must match pattern: `*_Customer_Mapping.xlsx`
- Example: `ACME_Customer_Mapping.xlsx`

### "Source data file not found"

**Problem:** Converted xlsx file doesn't exist.

**Solution:**
```bash
python3 convert_data_to_xlsx.py --source
```

### "Target data file not found"

**Problem:** Converted xlsx file doesn't exist.

**Solution:**
```bash
python3 convert_data_to_xlsx.py --target-pre
```

### Conflicts Detected

**Problem:** Multiple source objects map to same target.

**Solution:**
1. Open processed mapping file
2. Search for duplicate Target Name values
3. Decide which source should map to target
4. Change other sources to CREATE or different target

### Wrong Match Type

**Problem:** Fuzzy match is incorrect.

**Solution:**
1. Open processed mapping file
2. Find the row
3. Clear Target Name and Target ID
4. Change Match Type to NO_MATCH
5. Change Migration Action to CREATE

### CMJ Template Import Fails

**Problem:** CMJ rejects the template file.

**Solution:**
- Verify XML is valid (open in browser)
- Check file encoding is UTF-8
- Import global template before custom fields
- Review CMJ logs for specific error

### ScriptRunner Permission Error

**Problem:** Groovy script fails to run.

**Solution:**
- Ensure logged in as Jira admin
- Verify ScriptRunner is licensed
- Check system admin permissions
- Review ScriptRunner logs

---

## Best Practices

### Data Collection

- **Export fresh data** - Don't use stale exports
- **Verify RTF format** - Some editors corrupt the format
- **Check file sizes** - Empty files indicate export problems

### Mapping Review

- **Address conflicts first** - These will cause CMJ errors
- **Verify field types** - Incompatible types cause data loss
- **Check suggestions** - Fuzzy match suggestions may be correct
- **Document decisions** - Add notes for future reference

### CMJ Deployment

- **Test in staging first** - Never deploy directly to production
- **Import in correct order** - Global before custom fields
- **Monitor logs** - Watch for errors during deployment
- **Verify sample issues** - Check data migrated correctly

### Post-Migration

- **Always dry-run first** - Test cleanup script before live
- **Backup before cleanup** - In case of unexpected deletions
- **Verify after cleanup** - Check target instance still works

---

## Glossary

| Term | Definition |
|------|------------|
| **CMJ** | Configuration Manager for Jira - migration tool |
| **Source** | Original Jira instance being migrated from |
| **Target** | Destination Jira instance being migrated to |
| **Snapshot** | CMJ snapshot of objects to be migrated |
| **EXACT_MATCH** | Source and target names match exactly |
| **FUZZY_MATCH** | Names are similar but not exact |
| **MANUAL_MATCH** | Customer specified a different target |
| **NO_MATCH** | No target exists, object will be created |
| **Conflict** | Multiple sources mapping to same target |
| **On Screen** | Object appears in CMJ snapshot |

---

## Version History

### v3.3.0 (2026-02-25)
- Added customer review validation step (step 4)
- Added cleanup validation steps (steps 10 & 11)
- New scripts: `validate_customer_review.py`, `validate_cleanup_results.py`
- Pipeline expanded from 8 to 11 steps
- Validates: spaces, percentages, invalid actions, misspellings
- Auto-fix mode for common customer errors

### v3.2.0 (2026-02-24)
- Added cleanup validation steps to pipeline
- Excludes Field Configuration objects from CustomFields deletion
- Fixed Groovy cleanup generator to use converted xlsx file

### v3.1.1 (2026-01-20)
- Reorganized target_data with `pre_import/` subfolder
- ScriptRunner marked as required for target data export
- Updated documentation for Groovy script usage

### v3.1.0 (2026-01-19)
- Added orchestrator script (`run_migration.py`)
- Auto-detection of customer mapping files
- xlsx audit trail for data conversions
- Conflict detection for mappings
- New directory structure (`customer_review/`)
- Updated all documentation

### v3.0.0 (2026-01-17)
- Post-import target data support
- Groovy cleanup script generator
- Fixed CMJ snapshot parsing

### v2.0.0 (Previous)
- Initial customer mapping processing
- CMJ template generation
- Basic cleanup report

---

## Summary

**Complete Migration Workflow:**

```
Phase 1: Data Collection
├── Customer mapping file → source_data/{PROJECT}_Customer_Mapping.xlsx
├── Source API exports → source_data/source_api_full/*.rtf
├── Target pre-import exports → target_data/pre_import/*.rtf
└── CMJ snapshots → source_data/cmj_snapshot_objs/*.csv

Phase 2: Data Conversion (Steps 1-2)
├── Step 1: python3 convert_data_to_xlsx.py --source
└── Step 2: python3 convert_data_to_xlsx.py --target-pre

Phase 3: Process Mapping (Step 3)
└── Step 3: python3 process_customer_mapping.py
    └── Output: customer_review/{PROJECT}_Customer_Mapping_PROCESSED.xlsx

Phase 4: Review (Manual)
└── Review and update processed mapping in Excel

Phase 5: Generate Templates (Steps 4-6)
├── Step 4: python3 validate_customer_review.py
├── Step 5: python3 filter_for_cmj_template.py
└── Step 6: python3 create_cmj_templates.py

Phase 6: CMJ Deployment (Manual)
├── Import global_cmj_template.cmj
├── Import custom_field_cmj_template.cmj
├── Deploy CMJ snapshot
└── Export post-import target data

Phase 7: Post-Deployment (Steps 7-11)
├── Step 7: python3 convert_data_to_xlsx.py --target-post
├── Step 8: python3 generate_cleanup_report_v2.py
├── Step 9: python3 generate_groovy_cleanup.py
├── Run Groovy script (DRY_RUN=true) → save to cleaning_validation/
├── Step 10: python3 validate_cleanup_results.py --dryrun
├── Run Groovy script (DRY_RUN=false) → save to cleaning_validation/
└── Step 11: python3 validate_cleanup_results.py --liverun
```

**Or use the orchestrator:**

```bash
cd scripts
python3 run_migration.py --validate  # Check prerequisites
python3 run_migration.py             # Interactive mode
python3 run_migration.py --post      # After CMJ deployment
```

---

**Ready to migrate?** Start with `python3 run_migration.py --validate`
