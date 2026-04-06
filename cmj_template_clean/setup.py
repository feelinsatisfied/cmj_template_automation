#!/usr/bin/env python3
"""
CMJ Migration Tools - Setup Script

Enables installation via:
    pip install .
    pip install -e .  (development mode)
"""

from setuptools import setup, find_packages
from pathlib import Path

# Read the README for long description
readme_path = Path(__file__).parent / "README.md"
long_description = ""
if readme_path.exists():
    long_description = readme_path.read_text(encoding="utf-8")

setup(
    name="cmj-migration-tools",
    version="3.1.0",
    author="CMJ Migration Team",
    description="Toolkit for CMJ (Configuration Manager for Jira) multi-project migrations",
    long_description=long_description,
    long_description_content_type="text/markdown",
    url="https://github.com/your-org/cmj-migration-tools",

    # Package configuration
    packages=find_packages(where="scripts"),
    package_dir={"": "scripts"},
    py_modules=[
        "run_migration",
        "convert_data_to_xlsx",
        "process_customer_mapping",
        "filter_for_cmj_template",
        "create_cmj_templates",
        "generate_cleanup_report_v2",
        "generate_groovy_cleanup",
    ],

    # Dependencies
    install_requires=[
        "pandas>=2.0.0",
        "openpyxl>=3.1.0",
        "requests>=2.31.0",
    ],

    # Python version requirement
    python_requires=">=3.8",

    # Entry points for command-line scripts
    entry_points={
        "console_scripts": [
            "cmj-migrate=run_migration:main",
        ],
    },

    # Metadata
    classifiers=[
        "Development Status :: 4 - Beta",
        "Intended Audience :: System Administrators",
        "License :: OSI Approved :: MIT License",
        "Operating System :: MacOS",
        "Operating System :: POSIX :: Linux",
        "Programming Language :: Python :: 3",
        "Programming Language :: Python :: 3.8",
        "Programming Language :: Python :: 3.9",
        "Programming Language :: Python :: 3.10",
        "Programming Language :: Python :: 3.11",
        "Programming Language :: Python :: 3.12",
        "Topic :: System :: Systems Administration",
    ],

    # Additional files to include
    include_package_data=True,
    package_data={
        "": ["*.md", "*.txt"],
    },
)