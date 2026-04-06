# CMJ Migration Quick Reference

---

## Pipeline Overview

```
PRE-MIGRATION          PIPELINE              DEPLOYMENT           CLEANUP
─────────────────────────────────────────────────────────────────────────────
Collect Data    →    Steps 1-6    →    Import & Deploy    →    Steps 7-11
                          ↓                    ↓                    ↓
                   Customer Review        CMJ Snapshot      Groovy + Validation
```

---

## Phase 1: Pre-Migration

| Task | Owner |
|------|-------|
| Export source API data (5 RTF files) | Source Admin |
| Export target pre-import data (run `export_all_target_data.groovy`) | Target Admin |
| Run CMJ integrity check + quick fixes | Source Admin |
| Re-index projects | Source Admin |
| Create & export CMJ snapshot | Source Admin |
| Provide customer mapping file | Customer |

---

## Phase 2: Pipeline (Steps 1-6)

```bash
python3 scripts/run_migration.py --step 1    # Convert source data
python3 scripts/run_migration.py --step 2    # Convert target pre-import
python3 scripts/run_migration.py --step 3    # Process customer mapping
```

**⏸ PAUSE: Customer reviews `_PROCESSED.xlsx` → saves as `_PROCESSED_Reviewed.xlsx`**

```bash
python3 scripts/run_migration.py --step 4    # Validate customer review
python3 scripts/run_migration.py --step 5    # Filter for CMJ
python3 scripts/run_migration.py --step 6    # Create CMJ templates
```

**Output:** `cmj_templates/*.cmj`

---

## Phase 3: CMJ Deployment

| Step | Action |
|------|--------|
| 1 | Import `global_cmj_template.cmj` into CMJ |
| 2 | Import `custom_field_cmj_template.cmj` into CMJ |
| 3 | Deploy CMJ snapshot to target |
| 4 | Export target post-import data (run `export_all_target_data.groovy`) |

---

## Phase 4: Cleanup (Steps 7-11)

**Optional: Check object usage BEFORE cleanup (run in target ScriptRunner):**
```
scripts/check_issuetype_usage.groovy      # See which IssueTypes have issues
scripts/check_issuelinktype_usage.groovy  # See which LinkTypes have links
```

```bash
python3 scripts/run_migration.py --step 7    # Convert post-import data
python3 scripts/run_migration.py --step 8    # Generate cleanup report
python3 scripts/run_migration.py --step 9    # Generate Groovy script
```

**Run Groovy cleanup script in Jira ScriptRunner (DRY RUN):**
1. Run with `DRY_RUN = true` (preview)
2. Copy output to `target_data/cleaning_validation/target_cleaning_dryrun.rtf`

```bash
python3 scripts/run_migration.py --step 10   # Validate dryrun
```

**Run Groovy cleanup script in Jira ScriptRunner (LIVE RUN):**
1. Set `DRY_RUN = false` and execute
2. Copy output to `target_data/cleaning_validation/target_cleaning_liverun.rtf`

```bash
python3 scripts/run_migration.py --step 11   # Validate liverun
```

---

## Required Files

### Input (You Provide)

| Location | Files |
|----------|-------|
| `source_data/` | `{PROJECT}_Customer_Mapping.xlsx` |
| `source_data/source_api_full/` | `source_*.rtf` (5 files) |
| `source_data/cmj_snapshot_objs/` | `*_diff_*.csv` |
| `target_data/pre_import/` | `target_all_objects.txt` (1 file) OR `target_*.rtf` (5 files) |
| `target_data/post_import/` | `target_all_objects.txt` (1 file) OR `target_*.rtf` (5 files) |

### Output (Pipeline Generates)

| Location | Files |
|----------|-------|
| `customer_review/` | `_PROCESSED.xlsx`, `_CLEANUP_REPORT.xlsx`, `.groovy` |
| `cmj_templates/` | `_global_cmj_template.cmj`, `_custom_field_cmj_template.cmj` |

---

## Migration Actions

| Action | Meaning |
|--------|---------|
| **MAP** | Link source object to existing target object |
| **CREATE** | Create new object on target |
| **SKIP** | Don't migrate this object |
| **DELETE** | Delete after migration (cleanup) |

---

## Common Commands

```bash
# Validate setup
python3 scripts/run_migration.py --validate

# Run specific step
python3 scripts/run_migration.py --step N

# Archive completed project
python3 scripts/archive_project.py
```

**Export target data (run in Jira ScriptRunner):**
```
scripts/export_all_target_data.groovy   # Exports all 5 object types in 1 file
```
Save output as `target_all_objects.txt` in pre_import/ or post_import/

---

## Troubleshooting

| Issue | Solution |
|-------|----------|
| "No processed mapping file found" | Run Step 3 first |
| "MAP action but no Target ID" | Change to CREATE or fix Target Name |
| Groovy script errors | Check DRY_RUN output; verify object IDs |
| Resolutions won't delete | Manual deletion via Jira Admin UI |

---

## Multiple Project Groups

Copy entire folder per group:
```
PROJECT_GROUP_A/    ← Full copy of cmj_template
PROJECT_GROUP_B/    ← Another copy
```

Complete isolation. No conflicts. Same process for each.
