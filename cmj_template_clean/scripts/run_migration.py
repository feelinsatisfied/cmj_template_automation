#!/usr/bin/env python3
"""
CMJ Migration Orchestrator

Single entry point for the CMJ migration process with:
- Auto-detection of all required files
- Prerequisites validation
- Interactive step-by-step execution
- Progress tracking and status reporting

Usage:
    python3 run_migration.py              # Interactive mode
    python3 run_migration.py --auto       # Run all steps automatically
    python3 run_migration.py --step N     # Run specific step only
    python3 run_migration.py --validate   # Validate prerequisites only

Pipeline Steps (Pre-Deployment):
    1. Convert source data to xlsx
    2. Convert target pre-import data to xlsx
    3. Process customer mapping
    --- Customer reviews mapping file ---
    4. Validate customer review (catches errors before CMJ generation)
    5. Filter for CMJ template
    6. Create CMJ templates

Post-CMJ Deployment (run with --post):
    7. Convert target post-import data to xlsx
    8. Generate cleanup report (compares pre/post data)
    9. Generate Groovy cleanup script (with JQL validation)
    10. Validate cleanup dryrun (before live execution)
    11. Validate cleanup liverun (after live execution)
"""

import subprocess
import sys
from pathlib import Path
from datetime import datetime
import argparse
import json


# Base paths (relative to script location: scripts/ -> cmj_template/)
BASE_DIR = Path(__file__).resolve().parent.parent
SCRIPTS_DIR = BASE_DIR / 'scripts'
SOURCE_DATA_DIR = BASE_DIR / 'source_data'
SOURCE_API_DIR = SOURCE_DATA_DIR / 'source_api_full'
TARGET_DATA_DIR = BASE_DIR / 'target_data'
TARGET_PRE_DIR = TARGET_DATA_DIR / 'pre_import'
TARGET_POST_DIR = TARGET_DATA_DIR / 'post_import'
CLEANING_VALIDATION_DIR = TARGET_DATA_DIR / 'cleaning_validation'
CMJ_SNAPSHOT_DIR = SOURCE_DATA_DIR / 'cmj_snapshot_objs'
CMJ_TEMPLATES_DIR = BASE_DIR / 'cmj_templates'
CUSTOMER_REVIEW_DIR = BASE_DIR / 'customer_review'
STATE_FILE = BASE_DIR / '.migration_state.json'


# ANSI colors for terminal output
class Colors:
    HEADER = '\033[95m'
    BLUE = '\033[94m'
    CYAN = '\033[96m'
    GREEN = '\033[92m'
    YELLOW = '\033[93m'
    RED = '\033[91m'
    ENDC = '\033[0m'
    BOLD = '\033[1m'


def load_state():
    """Load migration state from file."""
    if STATE_FILE.exists():
        try:
            with open(STATE_FILE, 'r') as f:
                return json.load(f)
        except (json.JSONDecodeError, IOError):
            return {}
    return {}


def save_state(state):
    """Save migration state to file."""
    try:
        with open(STATE_FILE, 'w') as f:
            json.dump(state, f, indent=2, default=str)
    except IOError as e:
        print_warning(f"Could not save state: {e}")


def clear_state():
    """Clear the migration state file."""
    if STATE_FILE.exists():
        STATE_FILE.unlink()


def get_last_completed_step(state):
    """Get the last successfully completed step number."""
    completed = state.get('completed_steps', [])
    if completed:
        return max(completed)
    return 0


def mark_step_completed(step_num):
    """Mark a step as completed and save state."""
    state = load_state()
    if 'completed_steps' not in state:
        state['completed_steps'] = []
    if step_num not in state['completed_steps']:
        state['completed_steps'].append(step_num)
        state['completed_steps'].sort()
    state['last_updated'] = datetime.now().isoformat()
    state['last_step'] = step_num
    save_state(state)


def print_state_summary():
    """Print current state summary."""
    state = load_state()
    completed = state.get('completed_steps', [])

    if not completed:
        print_info("No previous progress found")
        return

    last_updated = state.get('last_updated', 'Unknown')
    print(f"\n{Colors.BOLD}Previous Progress:{Colors.ENDC}")
    print_info(f"Last updated: {last_updated}")

    step_names = {
        1: "Convert source data to xlsx",
        2: "Convert target pre-import data to xlsx",
        3: "Process customer mapping",
        4: "Validate customer review",
        5: "Filter for CMJ template",
        6: "Create CMJ templates",
        7: "Convert target post-import data to xlsx",
        8: "Generate cleanup report",
        9: "Generate Groovy cleanup script",
        10: "Validate cleanup dryrun",
        11: "Validate cleanup liverun",
    }

    for step_num in range(1, 12):
        name = step_names.get(step_num, f"Step {step_num}")
        if step_num in completed:
            print_success(f"Step {step_num}: {name}")
        else:
            print_info(f"Step {step_num}: {name} (pending)")


def print_header(text):
    """Print formatted header."""
    print(f"\n{Colors.BOLD}{Colors.HEADER}{'=' * 80}{Colors.ENDC}")
    print(f"{Colors.BOLD}{Colors.HEADER}{text.center(80)}{Colors.ENDC}")
    print(f"{Colors.BOLD}{Colors.HEADER}{'=' * 80}{Colors.ENDC}\n")


def print_step(step_num, text):
    """Print step header."""
    print(f"\n{Colors.BOLD}{Colors.CYAN}[Step {step_num}] {text}{Colors.ENDC}")
    print(f"{Colors.CYAN}{'-' * 60}{Colors.ENDC}")


def print_success(text):
    """Print success message."""
    print(f"{Colors.GREEN}✓ {text}{Colors.ENDC}")


def print_warning(text):
    """Print warning message."""
    print(f"{Colors.YELLOW}⚠ {text}{Colors.ENDC}")


def print_error(text):
    """Print error message."""
    print(f"{Colors.RED}✗ {text}{Colors.ENDC}")


def print_info(text):
    """Print info message."""
    print(f"{Colors.BLUE}ℹ {text}{Colors.ENDC}")


def check_python_dependencies():
    """Check required Python packages are installed."""
    required = ['pandas', 'openpyxl']
    missing = []

    for package in required:
        try:
            __import__(package)
        except ImportError:
            missing.append(package)

    return missing


def find_files_by_pattern(directory, pattern):
    """Find files matching a pattern in a directory."""
    if not directory.exists():
        return []
    return list(directory.glob(pattern))


def detect_project_keys():
    """Detect all project keys from customer mapping files.

    Returns:
        list: List of (project_key, file_path) tuples for all found mapping files.
    """
    matches = find_files_by_pattern(SOURCE_DATA_DIR, '*_Customer_Mapping.xlsx')
    # Filter out sample templates
    matches = [m for m in matches if not m.name.startswith('SAMPLE_')]
    result = []
    for match in sorted(matches):
        project_key = match.stem.replace('_Customer_Mapping', '')
        result.append((project_key, match))
    return result


def detect_project_key():
    """Detect primary project key from customer mapping file (backwards compatible).

    Returns:
        tuple: (project_key, file_path) for the first found mapping file, or (None, None).
    """
    projects = detect_project_keys()
    if projects:
        return projects[0][0], projects[0][1]
    return None, None


def validate_prerequisites():
    """Validate all prerequisites for migration."""
    print_header("VALIDATING PREREQUISITES")

    all_valid = True

    # Check Python dependencies
    print(f"{Colors.BOLD}Python Dependencies:{Colors.ENDC}")
    missing = check_python_dependencies()
    if missing:
        print_error(f"Missing packages: {', '.join(missing)}")
        print_info(f"Install with: pip install {' '.join(missing)}")
        all_valid = False
    else:
        print_success("All required packages installed (pandas, openpyxl)")

    # Check directories
    print(f"\n{Colors.BOLD}Directory Structure:{Colors.ENDC}")
    directories = [
        (SOURCE_DATA_DIR, "source_data/"),
        (SOURCE_API_DIR, "source_data/source_api_full/"),
        (TARGET_DATA_DIR, "target_data/"),
        (CMJ_SNAPSHOT_DIR, "source_data/cmj_snapshot_objs/"),
    ]

    for dir_path, name in directories:
        if dir_path.exists():
            print_success(f"{name} exists")
        else:
            print_warning(f"{name} not found")

    # Check for customer mapping files (supports multiple projects)
    print(f"\n{Colors.BOLD}Customer Mapping Files:{Colors.ENDC}")
    projects = detect_project_keys()
    if projects:
        if len(projects) == 1:
            project_key, mapping_file = projects[0]
            print_success(f"Found: {mapping_file.name}")
            print_info(f"Project key: {project_key}")
        else:
            print_success(f"Found {len(projects)} mapping files (MULTI-PROJECT MODE):")
            for project_key, mapping_file in projects:
                print_info(f"  - {mapping_file.name} (Project: {project_key})")
            # Use first project key for backwards compatibility
            project_key = projects[0][0]
    else:
        print_error("No *_Customer_Mapping.xlsx found in source_data/")
        all_valid = False
        project_key = None

    # Check source API files
    print(f"\n{Colors.BOLD}Source API Data (RTF/TXT files):{Colors.ENDC}")
    # Look for RTF or TXT files containing these keywords
    source_keywords = ['field', 'status', 'issuetype', 'issuelinktype', 'resolution']

    source_found = 0
    for keyword in source_keywords:
        # Check for any RTF or TXT file matching the keyword pattern
        # Supports: *_{keyword}_api.* and source_{keyword}_pre-import.*
        all_files = find_files_by_pattern(SOURCE_API_DIR, '*.rtf') + find_files_by_pattern(SOURCE_API_DIR, '*.txt')
        matches = [f for f in all_files if keyword in f.name.lower() and
                   ('api' in f.name.lower() or ('source' in f.name.lower() and 'pre-import' in f.name.lower()))]
        if matches:
            print_success(f"Found: {matches[0].name}")
            source_found += 1
        else:
            print_warning(f"Missing: *{keyword}*_api.rtf/.txt or source_{keyword}_pre-import.rtf/.txt")

    if source_found == 0:
        print_error("No source API files found")
        all_valid = False

    # Check target data files
    print(f"\n{Colors.BOLD}Target Pre-Import Data (RTF/TXT files):{Colors.ENDC}")
    target_files = find_files_by_pattern(TARGET_PRE_DIR, '*.rtf') + find_files_by_pattern(TARGET_PRE_DIR, '*.txt')
    if target_files:
        for f in target_files[:5]:
            print_success(f"Found: {f.name}")
        if len(target_files) > 5:
            print_info(f"... and {len(target_files) - 5} more")
    else:
        print_warning("No RTF/TXT files found in target_data/pre_import/")

    # Check CMJ snapshots
    print(f"\n{Colors.BOLD}CMJ Snapshot Files (CSV):{Colors.ENDC}")
    csv_files = find_files_by_pattern(CMJ_SNAPSHOT_DIR, '*.csv')
    if csv_files:
        for f in csv_files[:5]:
            print_success(f"Found: {f.name}")
        if len(csv_files) > 5:
            print_info(f"... and {len(csv_files) - 5} more")
    else:
        print_warning("No CSV files found in source_data/cmj_snapshot_objs/")

    # Check converted data files
    print(f"\n{Colors.BOLD}Converted Data Files (xlsx):{Colors.ENDC}")
    converted_files = [
        (SOURCE_API_DIR / 'source_data_converted.xlsx', 'Source data'),
        (TARGET_PRE_DIR / 'target_data_pre_import_converted.xlsx', 'Target pre-import data'),
    ]

    for file_path, name in converted_files:
        if file_path.exists():
            print_success(f"{name}: {file_path.name}")
        else:
            print_info(f"{name}: Not yet converted (will be created in Step 1-2)")

    return all_valid, project_key


def run_script(script_name, args=None, description=None):
    """Run a Python script and capture output."""
    script_path = SCRIPTS_DIR / script_name

    if not script_path.exists():
        print_error(f"Script not found: {script_path}")
        return False

    cmd = [sys.executable, str(script_path)]
    if args:
        cmd.extend(args)

    if description:
        print_info(f"Running: {description}")
    print_info(f"Command: python3 {script_name} {' '.join(args or [])}")
    print()

    try:
        result = subprocess.run(
            cmd,
            cwd=str(SCRIPTS_DIR),
            capture_output=False,
            text=True
        )

        if result.returncode == 0:
            print_success(f"{script_name} completed successfully")
            return True
        else:
            print_error(f"{script_name} failed with return code {result.returncode}")
            return False

    except Exception as e:
        print_error(f"Error running {script_name}: {e}")
        return False


def prompt_continue(message="Continue?"):
    """Prompt user to continue."""
    try:
        response = input(f"\n{Colors.YELLOW}{message} [Y/n]: {Colors.ENDC}").strip().lower()
        return response in ['', 'y', 'yes']
    except KeyboardInterrupt:
        print("\n")
        return False


def run_step_1():
    """Step 1: Convert source data to xlsx."""
    print_step(1, "Convert Source Data to XLSX")
    print_info("Converting source API RTF files to xlsx for audit trail")
    return run_script('convert_data_to_xlsx.py', ['--source'])


def run_step_2():
    """Step 2: Convert target pre-import data to xlsx."""
    print_step(2, "Convert Target Pre-Import Data to XLSX")
    print_info("Converting target RTF files to xlsx for audit trail")
    return run_script('convert_data_to_xlsx.py', ['--target-pre'])


def run_step_3():
    """Step 3: Process customer mapping."""
    print_step(3, "Process Customer Mapping")
    projects = detect_project_keys()
    if len(projects) > 1:
        print_info(f"Processing {len(projects)} mapping files (multi-project mode)")
    print_info("Enriching mappings with IDs, detecting matches and conflicts")
    return run_script('process_customer_mapping.py')


def run_step_4():
    """Step 4: Validate customer review."""
    print_step(4, "Validate Customer Review")
    print_info("Validating customer-reviewed mapping file(s)")
    print_info("Checking for: spaces, invalid actions, misspellings, copied suggestions")

    # Check if reviewed file exists
    reviewed_pattern = '*_Customer_Mapping_PROCESSED_Reviewed.xlsx'
    processed_pattern = '*_Customer_Mapping_PROCESSED.xlsx'

    reviewed_files = list(CUSTOMER_REVIEW_DIR.glob(reviewed_pattern))
    processed_files = list(CUSTOMER_REVIEW_DIR.glob(processed_pattern))

    if not reviewed_files and not processed_files:
        print_error("No reviewed mapping file found!")
        print_info("Customer must review the PROCESSED mapping file(s) first.")
        return False

    if len(reviewed_files) > 1:
        print_info(f"Found {len(reviewed_files)} reviewed files to validate")

    return run_script('validate_customer_review.py', ['--auto-fix'])


def run_step_5():
    """Step 5: Filter for CMJ template."""
    print_step(5, "Filter for CMJ Template")
    reviewed_files = list(CUSTOMER_REVIEW_DIR.glob('*_Customer_Mapping_PROCESSED_Reviewed.xlsx'))
    if len(reviewed_files) > 1:
        print_info(f"Combining {len(reviewed_files)} reviewed files into one CMJ template file")
    else:
        print_info("Filtering processed mapping for CMJ template generation")
    return run_script('filter_for_cmj_template.py')


def run_step_6():
    """Step 6: Create CMJ templates."""
    print_step(6, "Create CMJ Templates")
    print_info("Generating CMJ XML template files")
    return run_script('create_cmj_templates.py')


def run_step_7():
    """Step 7: Convert target post-import data to xlsx."""
    print_step(7, "Convert Target Post-Import Data to XLSX")
    print_info("Converting post-deployment target data to xlsx")
    return run_script('convert_data_to_xlsx.py', ['--target-post'])


def run_step_8():
    """Step 8: Generate cleanup report."""
    print_step(8, "Generate Cleanup Report")
    print_info("Comparing pre/post data to identify objects for cleanup")
    return run_script('generate_cleanup_report_v2.py')


def run_step_9():
    """Step 9: Generate Groovy cleanup script."""
    print_step(9, "Generate Groovy Cleanup Script")
    print_info("Creating Groovy script with JQL validation to safely delete unused objects")
    return run_script('generate_groovy_cleanup.py')


def run_step_10():
    """Step 10: Validate cleanup dryrun."""
    print_step(10, "Validate Cleanup Dryrun")
    print_info("Validating dryrun output before live cleanup execution")
    print_info(f"Looking for: {CLEANING_VALIDATION_DIR / 'target_cleaning_dryrun.rtf'}")

    dryrun_file = CLEANING_VALIDATION_DIR / 'target_cleaning_dryrun.rtf'
    if not dryrun_file.exists():
        print_error("Dryrun file not found!")
        print_info("Run the Groovy cleanup script in DRY_RUN mode in ScriptRunner,")
        print_info("then copy the output to target_data/cleaning_validation/target_cleaning_dryrun.rtf")
        return False

    return run_script('validate_cleanup_results.py', ['--dryrun'])


def run_step_11():
    """Step 11: Validate cleanup liverun."""
    print_step(11, "Validate Cleanup Liverun")
    print_info("Validating liverun output after cleanup execution")
    print_info(f"Looking for: {CLEANING_VALIDATION_DIR / 'target_cleaning_liverun.rtf'}")

    liverun_file = CLEANING_VALIDATION_DIR / 'target_cleaning_liverun.rtf'
    if not liverun_file.exists():
        print_error("Liverun file not found!")
        print_info("Run the Groovy cleanup script with DRY_RUN=false in ScriptRunner,")
        print_info("then copy the output to target_data/cleaning_validation/target_cleaning_liverun.rtf")
        return False

    return run_script('validate_cleanup_results.py', ['--liverun'])


def run_pre_deployment_pipeline(auto_mode=False, start_from=1):
    """Run steps 1-6 (pre-deployment)."""
    steps = [
        (1, run_step_1, "Convert source data to xlsx"),
        (2, run_step_2, "Convert target pre-import data to xlsx"),
        (3, run_step_3, "Process customer mapping"),
        (4, run_step_4, "Validate customer review"),
        (5, run_step_5, "Filter for CMJ template"),
        (6, run_step_6, "Create CMJ templates"),
    ]

    results = []

    for step_num, step_func, description in steps:
        # Skip steps before start_from
        if step_num < start_from:
            print_info(f"Skipping Step {step_num}: {description} (already completed)")
            results.append((step_num, 'skipped'))
            continue

        if not auto_mode:
            if not prompt_continue(f"Run Step {step_num}: {description}?"):
                print_warning(f"Skipped Step {step_num}")
                results.append((step_num, 'skipped'))
                continue

        success = step_func()
        results.append((step_num, 'success' if success else 'failed'))

        if success:
            mark_step_completed(step_num)

        if not success and not auto_mode:
            if not prompt_continue("Step failed. Continue anyway?"):
                break

    return results


def run_post_deployment_pipeline(auto_mode=False, start_from=7):
    """Run steps 7-11 (post-deployment)."""
    print_header("POST-DEPLOYMENT STEPS")
    print_warning("These steps should be run AFTER CMJ deployment completes")
    print_info("Make sure you have exported post-import target data to:")
    print_info(f"  {TARGET_POST_DIR}/")

    if not auto_mode:
        if not prompt_continue("Have you completed CMJ deployment and exported post-import data?"):
            return []

    steps = [
        (7, run_step_7, "Convert target post-import data to xlsx"),
        (8, run_step_8, "Generate cleanup report"),
        (9, run_step_9, "Generate Groovy cleanup script"),
        (10, run_step_10, "Validate cleanup dryrun"),
        (11, run_step_11, "Validate cleanup liverun"),
    ]

    results = []

    for step_num, step_func, description in steps:
        # Skip steps before start_from
        if step_num < start_from:
            print_info(f"Skipping Step {step_num}: {description} (already completed)")
            results.append((step_num, 'skipped'))
            continue

        if not auto_mode:
            if not prompt_continue(f"Run Step {step_num}: {description}?"):
                print_warning(f"Skipped Step {step_num}")
                results.append((step_num, 'skipped'))
                continue

        success = step_func()
        results.append((step_num, 'success' if success else 'failed'))

        if success:
            mark_step_completed(step_num)

        if not success and not auto_mode:
            if not prompt_continue("Step failed. Continue anyway?"):
                break

    return results


def print_summary(results, project_key):
    """Print execution summary."""
    print_header("EXECUTION SUMMARY")

    projects = detect_project_keys()
    if len(projects) > 1:
        print(f"{Colors.BOLD}Projects ({len(projects)}):{Colors.ENDC}")
        for pk, _ in projects:
            print(f"  - {pk}")
        print()
    else:
        print(f"{Colors.BOLD}Project: {project_key}{Colors.ENDC}\n")

    for step_num, status in results:
        if status == 'success':
            print_success(f"Step {step_num}: Completed")
        elif status == 'skipped':
            print_warning(f"Step {step_num}: Skipped")
        else:
            print_error(f"Step {step_num}: Failed")

    # Print output locations
    print(f"\n{Colors.BOLD}Output Locations:{Colors.ENDC}")

    outputs = [
        (SOURCE_API_DIR / 'source_data_converted.xlsx', "Source data (xlsx)"),
        (TARGET_DATA_DIR / 'target_data_pre_import_converted.xlsx', "Target pre-import (xlsx)"),
        (CMJ_TEMPLATES_DIR / 'global_cmj_template.cmj', "Global CMJ template"),
        (CMJ_TEMPLATES_DIR / 'custom_field_cmj_template.cmj', "Custom field CMJ template"),
    ]

    for path, name in outputs:
        if path.exists():
            print_success(f"{name}: {path}")
        else:
            print_info(f"{name}: Not yet created")

    # Show processed mapping files (multiple if multi-project)
    processed_files = list(CUSTOMER_REVIEW_DIR.glob('*_Customer_Mapping_PROCESSED.xlsx'))
    if processed_files:
        if len(processed_files) == 1:
            print_success(f"Processed mapping: {processed_files[0]}")
        else:
            print_success(f"Processed mappings ({len(processed_files)} files):")
            for f in processed_files:
                print_info(f"  - {f.name}")

    # Show combined FOR_CMJ file
    combined_file = CUSTOMER_REVIEW_DIR / 'COMBINED_Customer_Mapping_FOR_CMJ.xlsx'
    single_file = CUSTOMER_REVIEW_DIR / f'{project_key}_Customer_Mapping_FOR_CMJ.xlsx'
    if combined_file.exists():
        print_success(f"Combined CMJ file: {combined_file}")
    elif single_file.exists():
        print_success(f"CMJ mapping file: {single_file}")
    else:
        print_info("CMJ mapping file: Not yet created")


def main():
    parser = argparse.ArgumentParser(
        description='CMJ Migration Orchestrator',
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  python3 run_migration.py              # Interactive mode
  python3 run_migration.py --auto       # Run all pre-deployment steps
  python3 run_migration.py --step 3     # Run only step 3
  python3 run_migration.py --validate   # Check prerequisites only
  python3 run_migration.py --post       # Run post-deployment steps
  python3 run_migration.py --resume     # Resume from last completed step
  python3 run_migration.py --status     # Show current progress
  python3 run_migration.py --reset      # Clear progress and start fresh
  python3 run_migration.py --archive    # Archive completed project
        """
    )

    parser.add_argument('--auto', action='store_true',
                        help='Run all steps automatically without prompts')
    parser.add_argument('--step', type=int, choices=range(1, 12),
                        help='Run only the specified step (1-11)')
    parser.add_argument('--validate', action='store_true',
                        help='Only validate prerequisites, do not run')
    parser.add_argument('--post', action='store_true',
                        help='Run post-deployment steps (7-8)')
    parser.add_argument('--resume', action='store_true',
                        help='Resume from last completed step')
    parser.add_argument('--reset', action='store_true',
                        help='Clear saved progress and start fresh')
    parser.add_argument('--status', action='store_true',
                        help='Show current progress status')
    parser.add_argument('--archive', action='store_true',
                        help='Archive completed project to archive/ folder')

    args = parser.parse_args()

    # Print banner
    print_header("CMJ MIGRATION ORCHESTRATOR")
    print(f"Timestamp: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
    print(f"Base directory: {BASE_DIR}")

    # Handle --status flag (show progress and exit)
    if args.status:
        print_state_summary()
        return 0

    # Handle --archive flag (archive project and exit)
    if args.archive:
        print_header("ARCHIVE PROJECT")
        print_info("Archiving completed project to archive/ folder")
        success = run_script('archive_project.py', description="Archive project")
        if success:
            clear_state()  # Clear migration state after archiving
            print_success("Project archived and state cleared")
        return 0 if success else 1

    # Handle --reset flag (clear progress)
    if args.reset:
        clear_state()
        print_success("Progress cleared. Starting fresh.")
        if not args.auto and not args.step:
            return 0

    # Validate prerequisites
    valid, project_key = validate_prerequisites()

    if args.validate:
        if valid:
            print_success("\nAll prerequisites validated successfully")
        else:
            print_error("\nSome prerequisites are missing")
        return 0 if valid else 1

    if not valid:
        print_error("\nCannot proceed - fix missing prerequisites first")
        return 1

    # Run specific step
    if args.step:
        step_funcs = {
            1: run_step_1, 2: run_step_2, 3: run_step_3,
            4: run_step_4, 5: run_step_5, 6: run_step_6,
            7: run_step_7, 8: run_step_8, 9: run_step_9,
            10: run_step_10, 11: run_step_11
        }
        success = step_funcs[args.step]()
        if success:
            mark_step_completed(args.step)
        return 0 if success else 1

    # Run post-deployment steps
    if args.post:
        start_from = 7
        if args.resume:
            state = load_state()
            last_completed = get_last_completed_step(state)
            if last_completed >= 7:
                start_from = last_completed + 1
                print_state_summary()
                if last_completed >= 11:
                    print_success("\nAll steps already completed!")
                    return 0
                print_success(f"\nResuming from Step {start_from}")

        results = run_post_deployment_pipeline(args.auto or args.resume, start_from)
        print_summary(results, project_key)
        return 0

    # Run pre-deployment pipeline
    print_header("PRE-DEPLOYMENT PIPELINE")
    print("This will run steps 1-5 to prepare for CMJ deployment.\n")

    # Determine starting step
    start_from = 1
    if args.resume:
        state = load_state()
        last_completed = get_last_completed_step(state)
        if last_completed > 0 and last_completed < 6:
            start_from = last_completed + 1
            print_state_summary()
            print_success(f"\nResuming from Step {start_from}")
        elif last_completed >= 6:
            print_state_summary()
            print_success("\nPre-deployment steps already completed!")
            print_info("Run with --post for post-deployment steps, or --reset to start over")
            return 0
        else:
            print_info("No previous progress found, starting from Step 1")

    if not args.auto and not args.resume:
        print(f"{Colors.BOLD}Steps to execute:{Colors.ENDC}")
        print("  1. Convert source data to xlsx")
        print("  2. Convert target pre-import data to xlsx")
        print("  3. Process customer mapping")
        print("  --- Customer reviews mapping file ---")
        print("  4. Validate customer review")
        print("  5. Filter for CMJ template")
        print("  6. Create CMJ templates")

        if not prompt_continue("\nProceed with pre-deployment pipeline?"):
            print_warning("Aborted by user")
            return 0

    results = run_pre_deployment_pipeline(args.auto or args.resume, start_from)
    print_summary(results, project_key)

    # Prompt for post-deployment
    print(f"\n{Colors.BOLD}Next Steps:{Colors.ENDC}")
    print("  1. Import CMJ templates into target Jira")
    print("  2. Deploy CMJ snapshot")
    print("  3. Export post-import target data")
    print("  4. Run: python3 run_migration.py --post")

    return 0


if __name__ == "__main__":
    sys.exit(main())