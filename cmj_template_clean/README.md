# CMJ Migration Tools

Production-ready toolkit for CMJ (Configuration Manager for Jira) multi-project migrations.

**Version:** 3.4.0
**Last Updated:** 2026-03-13

## What This Tool Does

This toolkit automates the CMJ migration process for Jira Data Center migrations:

- **Auto-detection** of customer mapping files and project data
- **Multi-project support** - process multiple projects in a single run
- **Automated field matching** with fuzzy logic and confidence scores
- **Conflict detection** (multiple sources → same target)
- **xlsx audit trail** for all data conversions
- **Interactive orchestrator** for step-by-step execution
- **Post-migration cleanup** with Groovy script generation

## Quick Start

### Installation

```bash
# Clone or download this repository
cd cmj_template

# Install dependencies
pip install -r requirements.txt

# Or install as a package
pip install -e .
```

### Prerequisites

- Python 3.8+
- macOS (for `textutil` RTF conversion) or Linux
- Access to source and target Jira instances
- CMJ (Configuration Manager for Jira) installed in target Jira
- ScriptRunner (required - for target data export and post-migration cleanup)

### Basic Workflow

**Using the Orchestrator (Recommended):**

```bash
cd scripts

# Validate prerequisites
python3 run_migration.py --validate

# Run interactive migration (prompts for each step)
python3 run_migration.py

# Or run all steps automatically
python3 run_migration.py --auto
```

**After CMJ Deployment:**

```bash
# Run post-deployment cleanup steps
python3 run_migration.py --post
```

## Directory Structure

```
cmj_template/
├── scripts/                    # Python automation scripts
│   ├── run_migration.py        # Orchestrator (main entry point)
│   ├── convert_data_to_xlsx.py # Data conversion utility
│   ├── process_customer_mapping.py  # Mapping processor
│   ├── filter_for_cmj_template.py   # Template filter
│   ├── create_cmj_templates.py      # CMJ XML generator
│   ├── generate_cleanup_report_v2.py # Cleanup report generator
│   ├── generate_groovy_cleanup.py   # Groovy script generator
│   ├── validate_customer_review.py  # Customer review validation
│   └── validate_cleanup_results.py  # Cleanup validation script
├── source_data/               # Source Jira data
│   ├── {PROJECT}_Customer_Mapping.xlsx  # Customer mapping input (one or more)
│   ├── source_api_full/       # Source API exports (RTF/JSON)
│   │   └── source_data_converted.xlsx   # Generated audit file
│   └── cmj_snapshot_objs/     # CMJ snapshot CSV files (one per project)
├── target_data/               # Target Jira data
│   ├── pre_import/            # Pre-import RTF files (via ScriptRunner)
│   │   └── target_data_pre_import_converted.xlsx  # Generated audit file
│   ├── post_import/           # Post-import RTF files (via ScriptRunner)
│   │   └── target_data_post_import_converted.xlsx # Generated audit file
│   └── cleaning_validation/   # Groovy cleanup script outputs
│       ├── target_cleaning_dryrun.rtf   # Dryrun output (before cleanup)
│       └── target_cleaning_liverun.rtf  # Liverun output (after cleanup)
├── customer_review/           # Processed mapping outputs
├── cmj_templates/             # Generated CMJ XML files
├── requirements.txt           # Python dependencies
├── setup.py                   # Package setup
└── pyproject.toml             # Modern Python packaging
```

## Migration Pipeline

### Pre-Deployment Steps (1-6)

| Step | Script | Description |
|------|--------|-------------|
| 1 | `convert_data_to_xlsx.py --source` | Convert source API data to xlsx |
| 2 | `convert_data_to_xlsx.py --target-pre` | Convert target pre-import data to xlsx |
| 3 | `process_customer_mapping.py` | Process mapping with IDs, matches, conflicts |
| 4 | `validate_customer_review.py` | Validate customer-reviewed mapping file |
| 5 | `filter_for_cmj_template.py` | Filter for CMJ template generation |
| 6 | `create_cmj_templates.py` | Generate CMJ XML templates |

### Customer Review (Between Steps 3 and 4)

After Step 3, customer reviews `customer_review/{PROJECT}_Customer_Mapping_PROCESSED.xlsx`:
1. Review and adjust Migration Actions (MAP, CREATE, SKIP, DELETE)
2. Verify Target Name mappings
3. Save as `{PROJECT}_Customer_Mapping_PROCESSED_Reviewed.xlsx`

Step 4 validates the reviewed file and catches common errors:
- Leading/trailing spaces in names
- Copied suggestion text with percentages (e.g., "Name (85%)")
- Invalid Migration Actions
- Misspellings (fuzzy match detection)

### Manual Steps

After Step 6:
1. Import CMJ templates into target Jira
2. Deploy CMJ snapshot
3. Export post-import target data to `target_data/post_import/`

### Post-Deployment Steps (7-11)

| Step | Script | Description |
|------|--------|-------------|
| 7 | `convert_data_to_xlsx.py --target-post` | Convert post-import data to xlsx |
| 8 | `generate_cleanup_report_v2.py` | Create cleanup report (compares pre/post data) |
| 9 | `generate_groovy_cleanup.py` | Generate Groovy cleanup script (with JQL validation) |
| 10 | `validate_cleanup_results.py --dryrun` | Validate dryrun output before live cleanup |
| 11 | `validate_cleanup_results.py --liverun` | Validate liverun output after cleanup |

### Cleanup Validation Workflow (Steps 10-11)

After Step 9:
1. Run the Groovy cleanup script in **DRY_RUN mode** in ScriptRunner
2. Copy output to `target_data/cleaning_validation/target_cleaning_dryrun.rtf`
3. Run Step 10 to validate - ensures all deletions are authorized
4. If validation passes, run the Groovy script with **DRY_RUN=false**
5. Copy output to `target_data/cleaning_validation/target_cleaning_liverun.rtf`
6. Run Step 11 to validate - confirms only authorized items were deleted

## Input Files Required

### 1. Customer Mapping File(s)

**Location:** `source_data/{PROJECT}_Customer_Mapping.xlsx`

**Multi-project:** Place multiple files (e.g., `PROJECT1_Customer_Mapping.xlsx`, `PROJECT2_Customer_Mapping.xlsx`)

Required sheets:
- Status
- CustomFields
- Resolutions
- IssueLinkTypes
- IssueTypes

Required columns per sheet:
- Project
- Source Name
- Target Name (optional - for manual mappings)
- Migration Action (MAP, CREATE, SKIP, DELETE)

### 2. Source API Data

**Location:** `source_data/source_api_full/`

RTF files containing JSON from Jira REST API:
- `*_field_api.rtf` - Custom fields
- `*_status_api.rtf` - Statuses
- `*_issuetype_api.rtf` - Issue types
- `*_issuelinktype_api.rtf` - Issue link types
- `*_resolution_api.rtf` - Resolutions

### 3. Target Pre-Import Data

**Location:** `target_data/pre_import/`

RTF files exported from target Jira via ScriptRunner Groovy scripts:
- `target_field_pre-import.rtf`
- `target_status_pre-import.rtf`
- `target_issuetype_pre-import.rtf`
- `target_issuelinktype_pre-import.rtf`
- `target_resolution_pre-import.rtf`

### 4. CMJ Snapshot CSVs

**Location:** `source_data/cmj_snapshot_objs/`

CSV exports from CMJ snapshots:
- `{PROJECTKEY}_*_cmj.csv`

## Output Files Generated

### Converted Data (Audit Trail)

- `source_data/source_api_full/source_data_converted.xlsx`
- `target_data/pre_import/target_data_pre_import_converted.xlsx`
- `target_data/post_import/target_data_post_import_converted.xlsx`

### Processed Mapping

- `customer_review/{PROJECT}_Customer_Mapping_PROCESSED.xlsx` (one per project)
  - Enriched with Source/Target IDs
  - Match types: EXACT_MATCH, FUZZY_MATCH, MANUAL_MATCH, NO_MATCH
  - Confidence scores: High, Medium, Low
  - Conflict detection flagged

- `customer_review/COMBINED_Customer_Mapping_FOR_CMJ.xlsx` (multi-project only)
  - Combined filtered mapping from all projects
  - Deduplicated by Source Name

### CMJ Templates

- `cmj_templates/global_cmj_template.cmj` - Status, Resolutions, IssueLinkTypes, IssueTypes
- `cmj_templates/custom_field_cmj_template.cmj` - CustomFields only

### Cleanup Outputs

- `scripts/{PROJECT}_Customer_Mapping_CLEANUP_REPORT.xlsx`
- `scripts/post_cmj_cleanup.groovy`

## Command Reference

### Orchestrator (Recommended)

```bash
cd scripts

# Interactive mode - prompts for each step
python3 run_migration.py

# Validate prerequisites only
python3 run_migration.py --validate

# Run all pre-deployment steps automatically
python3 run_migration.py --auto

# Run specific step (1-8)
python3 run_migration.py --step 3

# Run post-deployment steps
python3 run_migration.py --post
```

### Individual Scripts

```bash
cd scripts

# Convert data to xlsx
python3 convert_data_to_xlsx.py --all
python3 convert_data_to_xlsx.py --source
python3 convert_data_to_xlsx.py --target-pre
python3 convert_data_to_xlsx.py --target-post

# Process customer mapping
python3 process_customer_mapping.py
python3 process_customer_mapping.py --mapping-file /path/to/file.xlsx

# Filter for CMJ template
python3 filter_for_cmj_template.py

# Create CMJ templates
python3 create_cmj_templates.py

# Generate cleanup report
python3 generate_cleanup_report_v2.py

# Generate Groovy cleanup script
python3 generate_groovy_cleanup.py
```

## Key Features

### Auto-Detection

The orchestrator automatically finds:
- Customer mapping file (`*_Customer_Mapping.xlsx`)
- Source API data files
- Target data files
- CMJ snapshot CSVs
- Project key from filename

### Fuzzy Matching

Automatic matching between source and target objects:
- **EXACT_MATCH**: Name (and type for fields) match exactly
- **FUZZY_MATCH**: High similarity (≥85%) with confidence score
- **MANUAL_MATCH**: Customer-specified mapping
- **NO_MATCH**: No match found, will be created

### Conflict Detection

Detects when multiple source objects map to the same target:
```
⚠ CONFLICTS DETECTED (21):
  Target 'Analysis' ← Sources: ['Analysis', 'Analysis', 'Analysis']
  Target 'Approved' ← Sources: ['Approved', 'Approved', 'Approved', 'Approved']
```

### xlsx Audit Trail

All data conversions output xlsx files with:
- Separate tabs per data type (CustomFields, Statuses, etc.)
- Metadata tab with conversion timestamp
- Easy validation and review

## Multi-Project Support

Process multiple projects simultaneously with a single CMJ deployment and cleanup cycle.

### Setup for Multiple Projects

Place multiple mapping files in `source_data/`:
```
source_data/
├── PROJECT1_Customer_Mapping.xlsx
├── PROJECT2_Customer_Mapping.xlsx
├── PROJECT3_Customer_Mapping.xlsx
└── cmj_snapshot_objs/
    ├── PROJECT1_diff_*.csv
    ├── PROJECT2_diff_*.csv
    └── PROJECT3_diff_*.csv
```

### Multi-Project Workflow

1. **Step 3** processes ALL mapping files → outputs separate `*_PROCESSED.xlsx` for each
2. Customer reviews each file → saves as `*_PROCESSED_Reviewed.xlsx`
3. **Step 4** validates ALL reviewed files → shows per-project pass/fail
4. **Step 5** combines ALL reviewed files → ONE `COMBINED_Customer_Mapping_FOR_CMJ.xlsx`
5. **Step 6** generates ONE set of CMJ templates
6. Single CMJ deployment and cleanup cycle

### Benefits

- **Efficiency**: One CMJ integrity check, one snapshot deployment, one cleanup cycle
- **Consistency**: All projects use the same target instance state
- **Simplicity**: Single set of CMJ templates to import

### Output Files (Multi-Project)

| Step | Single Project | Multiple Projects |
|------|---------------|-------------------|
| Step 3 | `PROJECT_PROCESSED.xlsx` | `PROJECT1_PROCESSED.xlsx`, `PROJECT2_PROCESSED.xlsx`, etc. |
| Step 5 | `PROJECT_FOR_CMJ.xlsx` | `COMBINED_Customer_Mapping_FOR_CMJ.xlsx` |

The orchestrator automatically detects multi-project mode and displays:
```
Customer Mapping Files:
✓ Found 3 mapping files (MULTI-PROJECT MODE):
  - PROJECT1_Customer_Mapping.xlsx (Project: PROJECT1)
  - PROJECT2_Customer_Mapping.xlsx (Project: PROJECT2)
  - PROJECT3_Customer_Mapping.xlsx (Project: PROJECT3)
```

## Troubleshooting

### Missing Customer Mapping File

```
❌ Error: No customer mapping file found
   Place a file named {PROJECT_KEY}_Customer_Mapping.xlsx in:
   /path/to/source_data/
```

### Missing Converted Data

```
⚠ Warning: No source data loaded. Run convert_data_to_xlsx.py --source first.
```

Run the conversion script:
```bash
python3 convert_data_to_xlsx.py --source
```

### Validation Fails

```bash
# Check what's missing
python3 run_migration.py --validate
```

### Script Not Found

Ensure you're running from the `scripts/` directory:
```bash
cd /path/to/cmj_template/scripts
python3 run_migration.py
```

## Installation for Distribution

### For End Users

```bash
# Install from source
cd cmj_template
pip install .

# Or install in development mode
pip install -e .
```

### Dependencies

```
pandas>=2.0.0
openpyxl>=3.1.0
requests>=2.31.0
```

### System Requirements

- Python 3.8 or higher
- macOS (uses `textutil` for RTF conversion)
- 4GB RAM minimum (for large mapping files)

## Version History

### v3.4.0 (2026-03-13)
- Added multi-project support for batch processing
- Process multiple `*_Customer_Mapping.xlsx` files in a single run
- Validate all reviewed files with per-project pass/fail summary
- Combine all projects into one `COMBINED_Customer_Mapping_FOR_CMJ.xlsx`
- Single CMJ deployment and cleanup cycle for multiple projects
- Orchestrator shows multi-project mode detection

### v3.3.0 (2026-02-24)
- Added customer review validation step (step 4)
- New script: `validate_customer_review.py` for pre-CMJ validation
- Validates: spaces, percentages, invalid actions, misspellings
- Auto-fix mode trims spaces and normalizes actions
- Renumbered pipeline to 11 steps total

### v3.2.0 (2026-02-24)
- Added cleanup validation steps (10 & 11) to pipeline
- New script: `validate_cleanup_results.py` for dryrun/liverun validation
- Excludes Field Configuration objects from CustomFields deletion
- Fixed Groovy cleanup generator to use converted xlsx file

### v3.1.1 (2026-01-20)
- Reorganized `target_data/` with `pre_import/` subfolder
- ScriptRunner marked as required for target data export
- Fixed validation paths in orchestrator
- Updated documentation

### v3.1.0 (2026-01-19)
- Added orchestrator script (`run_migration.py`)
- Auto-detection of customer mapping files
- xlsx audit trail for data conversions
- Conflict detection for mappings
- Updated documentation

### v3.0.0 (2026-01-17)
- Post-import target data support
- Groovy cleanup script generator
- Fixed CMJ snapshot parsing
- Updated deletion logic

### v2.0.0 (Previous)
- Initial customer mapping processing
- CMJ template generation
- Basic cleanup report

## Support

For issues and questions:
1. Check the troubleshooting section above
2. Run `python3 run_migration.py --validate` to diagnose problems
3. Review generated log output for specific errors

---

**Ready to migrate?** Run `python3 run_migration.py --validate` to get started!