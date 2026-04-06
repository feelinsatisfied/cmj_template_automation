#!/usr/bin/env python3
"""
Archive Project Data

Moves all project-specific data to an archive folder before starting a new project.
This keeps the workspace clean and organized.

Usage:
    python3 archive_project.py [PROJECT_KEY]

If PROJECT_KEY is not provided, it will auto-detect from existing files.
"""

import shutil
import sys
from pathlib import Path
from datetime import datetime

# Base paths (relative to script location: scripts/ -> cmj_template/)
BASE_DIR = Path(__file__).resolve().parent.parent
ARCHIVE_DIR = BASE_DIR / 'archive'
SOURCE_DATA_DIR = BASE_DIR / 'source_data'
TARGET_DATA_DIR = BASE_DIR / 'target_data'
CUSTOMER_REVIEW_DIR = BASE_DIR / 'customer_review'
CMJ_TEMPLATES_DIR = BASE_DIR / 'cmj_templates'


def detect_project_key():
    """Auto-detect project key from existing files."""
    # Try to find from customer_review files
    patterns = [
        '*_Customer_Mapping_PROCESSED_Reviewed.xlsx',
        '*_Customer_Mapping_PROCESSED.xlsx',
        '*_Customer_Mapping.xlsx',
        '*_Customer_Mapping_CLEANUP_REPORT.xlsx'
    ]

    for pattern in patterns:
        matches = list(CUSTOMER_REVIEW_DIR.glob(pattern))
        if matches:
            filename = matches[0].stem
            # Extract project key (first part before _Customer_Mapping)
            if '_Customer_Mapping' in filename:
                return filename.split('_Customer_Mapping')[0]

    # Try source_data
    matches = list(SOURCE_DATA_DIR.glob('*_Customer_Mapping.xlsx'))
    if matches:
        filename = matches[0].stem
        return filename.replace('_Customer_Mapping', '')

    return None


def archive_project(project_key):
    """Archive all project data to a dated folder."""

    print("=" * 80)
    print("ARCHIVE PROJECT DATA")
    print("=" * 80)
    print(f"Project Key: {project_key}")
    print(f"Timestamp: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
    print("-" * 80)

    # Create archive folder with date
    date_str = datetime.now().strftime('%Y%m%d')
    archive_folder = ARCHIVE_DIR / f"{date_str}_{project_key}"

    # If folder exists, add a counter
    counter = 1
    original_folder = archive_folder
    while archive_folder.exists():
        archive_folder = Path(f"{original_folder}_{counter}")
        counter += 1

    archive_folder.mkdir(parents=True, exist_ok=True)
    print(f"\nArchive folder: {archive_folder.name}/")

    # Track what we archive
    archived_files = []

    # 1. Archive source_data
    print("\n📁 Archiving source_data/...")
    source_archive = archive_folder / 'source_data'
    if SOURCE_DATA_DIR.exists():
        files_to_archive = []

        # Customer mapping file
        for f in SOURCE_DATA_DIR.glob('*_Customer_Mapping*.xlsx'):
            files_to_archive.append(f)

        # CMJ snapshot files for this project
        cmj_dir = SOURCE_DATA_DIR / 'cmj_snapshot_objs'
        if cmj_dir.exists():
            for f in cmj_dir.glob(f'{project_key}*.csv'):
                files_to_archive.append(f)

        # Source API data
        source_api_dir = SOURCE_DATA_DIR / 'source_api_full'
        if source_api_dir.exists():
            files_to_archive.extend(source_api_dir.glob('*.rtf'))
            files_to_archive.extend(source_api_dir.glob('*.xlsx'))

        if files_to_archive:
            source_archive.mkdir(parents=True, exist_ok=True)
            for f in files_to_archive:
                dest = source_archive / f.name
                shutil.copy2(f, dest)
                print(f"  ✓ {f.name}")
                archived_files.append(f)

    # 2. Archive target_data
    print("\n📁 Archiving target_data/...")
    target_archive = archive_folder / 'target_data'

    # Pre-import
    pre_import_dir = TARGET_DATA_DIR / 'pre_import'
    if pre_import_dir.exists():
        pre_archive = target_archive / 'pre_import'
        pre_archive.mkdir(parents=True, exist_ok=True)
        for f in pre_import_dir.glob('*'):
            if f.is_file() and not f.name.startswith('.'):
                shutil.copy2(f, pre_archive / f.name)
                print(f"  ✓ pre_import/{f.name}")
                archived_files.append(f)

    # Post-import
    post_import_dir = TARGET_DATA_DIR / 'post_import'
    if post_import_dir.exists():
        post_archive = target_archive / 'post_import'
        post_archive.mkdir(parents=True, exist_ok=True)
        for f in post_import_dir.glob('*'):
            if f.is_file() and not f.name.startswith('.'):
                shutil.copy2(f, post_archive / f.name)
                print(f"  ✓ post_import/{f.name}")
                archived_files.append(f)

    # Cleaning validation
    cleaning_dir = TARGET_DATA_DIR / 'cleaning_validation'
    if cleaning_dir.exists():
        cleaning_archive = target_archive / 'cleaning_validation'
        cleaning_archive.mkdir(parents=True, exist_ok=True)
        for f in cleaning_dir.glob('*'):
            if f.is_file() and not f.name.startswith('.'):
                shutil.copy2(f, cleaning_archive / f.name)
                print(f"  ✓ cleaning_validation/{f.name}")
                archived_files.append(f)

    # 3. Archive customer_review
    print("\n📁 Archiving customer_review/...")
    review_archive = archive_folder / 'customer_review'
    if CUSTOMER_REVIEW_DIR.exists():
        review_archive.mkdir(parents=True, exist_ok=True)
        for f in CUSTOMER_REVIEW_DIR.glob('*'):
            if f.is_file() and not f.name.startswith('.'):
                shutil.copy2(f, review_archive / f.name)
                print(f"  ✓ {f.name}")
                archived_files.append(f)

    # 4. Archive cmj_templates
    print("\n📁 Archiving cmj_templates/...")
    cmj_archive = archive_folder / 'cmj_templates'
    if CMJ_TEMPLATES_DIR.exists():
        cmj_archive.mkdir(parents=True, exist_ok=True)
        for f in CMJ_TEMPLATES_DIR.glob('*'):
            if f.is_file() and not f.name.startswith('.'):
                shutil.copy2(f, cmj_archive / f.name)
                print(f"  ✓ {f.name}")
                archived_files.append(f)

    print("\n" + "=" * 80)
    print("CLEANING UP WORKING DIRECTORIES")
    print("=" * 80)

    # Clean up source_data (keep directory structure)
    print("\n🧹 Cleaning source_data/...")
    for f in SOURCE_DATA_DIR.glob('*_Customer_Mapping*.xlsx'):
        f.unlink()
        print(f"  ✗ Removed {f.name}")

    cmj_dir = SOURCE_DATA_DIR / 'cmj_snapshot_objs'
    if cmj_dir.exists():
        for f in cmj_dir.glob(f'{project_key}*.csv'):
            f.unlink()
            print(f"  ✗ Removed cmj_snapshot_objs/{f.name}")

    source_api_dir = SOURCE_DATA_DIR / 'source_api_full'
    if source_api_dir.exists():
        for f in source_api_dir.glob('*'):
            if f.is_file() and not f.name.startswith('.'):
                f.unlink()
                print(f"  ✗ Removed source_api_full/{f.name}")

    # Clean up target_data
    print("\n🧹 Cleaning target_data/...")
    for subdir in ['pre_import', 'post_import', 'cleaning_validation']:
        target_subdir = TARGET_DATA_DIR / subdir
        if target_subdir.exists():
            for f in target_subdir.glob('*'):
                if f.is_file() and not f.name.startswith('.'):
                    f.unlink()
                    print(f"  ✗ Removed {subdir}/{f.name}")

    # Clean up customer_review
    print("\n🧹 Cleaning customer_review/...")
    for f in CUSTOMER_REVIEW_DIR.glob('*'):
        if f.is_file() and not f.name.startswith('.'):
            f.unlink()
            print(f"  ✗ Removed {f.name}")

    # Clean up cmj_templates
    print("\n🧹 Cleaning cmj_templates/...")
    for f in CMJ_TEMPLATES_DIR.glob('*'):
        if f.is_file() and not f.name.startswith('.'):
            f.unlink()
            print(f"  ✗ Removed {f.name}")

    # Summary
    print("\n" + "=" * 80)
    print("ARCHIVE COMPLETE")
    print("=" * 80)
    print(f"\nProject: {project_key}")
    print(f"Archived to: archive/{archive_folder.name}/")
    print(f"Files archived: {len(archived_files)}")
    print("\nWorkspace is now clean for the next project!")
    print("=" * 80)

    return archive_folder


def main():
    """Main function."""
    # Get project key from argument or auto-detect
    if len(sys.argv) > 1:
        project_key = sys.argv[1]
    else:
        print("🔍 Auto-detecting project key...")
        project_key = detect_project_key()

        if not project_key:
            print("❌ Could not detect project key.")
            print("Usage: python3 archive_project.py PROJECT_KEY")
            return

        print(f"✓ Detected project: {project_key}")

    # Confirm with user
    print(f"\nThis will archive all data for project '{project_key}' and clean the workspace.")
    response = input("Continue? (y/n): ").strip().lower()

    if response != 'y':
        print("Cancelled.")
        return

    archive_project(project_key)


if __name__ == "__main__":
    main()
