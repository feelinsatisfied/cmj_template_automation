# CMJ Migration - Customer Guide

What to expect and what we need from you during the CMJ migration process.

---

## Quick Reference: Customer Actions

| When | Your Action | Deliverable |
|------|-------------|-------------|
| **Before Migration** | Complete mapping spreadsheet | `{PROJECT}_Customer_Mapping.xlsx` |
| **During Migration** | Review processed mapping | `{PROJECT}_Customer_Mapping_PROCESSED_Reviewed.xlsx` |
| **After Migration** | Validate results | Sign-off on completion |

---

## Before Migration Begins

### 1. Provide Customer Mapping File

We will provide you with a mapping spreadsheet to complete.

**File format:** `{PROJECT}_Customer_Mapping.xlsx`

**Sheets to complete:**
- Status
- CustomFields
- Resolutions
- IssueLinkTypes
- IssueTypes

**For each object, indicate your decision:**

| Migration Action | Meaning |
|------------------|---------|
| **MAP** | Link this source object to an existing target object |
| **CREATE** | Create a new object on the target (doesn't exist yet) |
| **SKIP** | Don't migrate this object |
| **DELETE** | Delete this object after migration (cleanup) |

**Required columns:**
- `Source Name` - The object name from your source instance
- `Target Name` - The object name on target (for MAP actions)
- `Migration Action` - Your decision (MAP, CREATE, SKIP, DELETE)

---

## During Migration

### 2. Review Processed Mapping

After we process your mapping file, you will receive a file for review:

**File:** `{PROJECT}_Customer_Mapping_PROCESSED.xlsx`

**What we've added:**
- Source IDs and Target IDs (looked up automatically)
- Match Type (EXACT_MATCH, FUZZY_MATCH, NO_MATCH)
- Confidence scores
- Suggested matches for unmatched items
- Conflict warnings (multiple sources mapping to same target)

**Your review checklist:**

1. **Check conflicts** - Multiple source objects mapping to the same target
   - Decide which source should map to target
   - Change others to CREATE or different target

2. **Verify fuzzy matches** - Auto-matched items that aren't exact
   - Confirm the match is correct
   - Change to CREATE if the match is wrong

3. **Review NO_MATCH items** - Objects that will be created
   - Check if a target mapping should exist
   - Review suggestions column for potential matches

4. **Confirm DELETE actions** - Objects marked for post-migration cleanup
   - Verify these should be removed

**When finished:**
- Append `_Reviewed` to the filename
- Example: `PROJECT_Customer_Mapping_PROCESSED.xlsx` → `PROJECT_Customer_Mapping_PROCESSED_Reviewed.xlsx`

**Note:** You do not need to delete the suggestion columns (Target Suggestion #1, #2, #3, etc.). Leave them in place - our scripts will ignore them.

### Common Review Mistakes to Avoid

| Mistake | Example | How to Fix |
|---------|---------|------------|
| Extra spaces | `" Status Name "` | Remove leading/trailing spaces |
| Copied suggestions | `"Status Name (85%)"` | Remove the percentage |
| Typos in Target Name | `"Aproved"` instead of `"Approved"` | Correct the spelling |
| Wrong Migration Action | `"map"` or `"Map"` | Use uppercase: `MAP` |

---

## After Migration

### 3. Validate Results

After CMJ deployment and cleanup, we will provide:

- Summary of objects migrated
- Summary of objects created
- Summary of objects deleted
- Any issues encountered

**Your validation:**
- Spot-check sample issues in target Jira
- Verify fields display correctly
- Confirm workflows function as expected
- Sign off on migration completion

---

## Timeline Overview

```
Week 1: Data Collection
├── You: Complete customer mapping file
└── Us: Export source/target data, create CMJ snapshot

Week 2: Processing & Review
├── Us: Process mapping, generate reports
├── You: Review processed mapping (2-3 days)
└── Us: Generate CMJ templates

Week 3: Deployment
├── Us: Import templates, deploy CMJ snapshot
├── Us: Run cleanup scripts
└── You: Validate results and sign off
```

*Actual timeline may vary based on project size and complexity.*

---

## What You Don't Need to Do

We handle all of these:

- Exporting API data from source/target
- Converting data formats
- Running CMJ integrity checks
- Creating CMJ snapshots
- Generating CMJ templates
- Importing templates into CMJ
- Deploying the CMJ snapshot
- Running cleanup scripts
- Validating cleanup results

---

## Questions?

Contact your migration team lead with any questions about:
- How to fill out the mapping spreadsheet
- What Migration Action to choose
- How to handle specific objects
- Timeline or scheduling concerns

---

## Glossary

| Term | Definition |
|------|------------|
| **CMJ** | Configuration Manager for Jira - the migration tool |
| **Source** | Your original Jira instance being migrated from |
| **Target** | The destination Jira instance (TARGET_INSTANCE) |
| **MAP** | Link a source object to an existing target object |
| **CREATE** | Create a new object on target during migration |
| **SKIP** | Exclude object from migration |
| **DELETE** | Remove object from target after migration |
| **Exact Match** | Source and target names match exactly |
| **Fuzzy Match** | Names are similar but not exact (auto-matched) |