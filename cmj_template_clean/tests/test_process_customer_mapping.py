#!/usr/bin/env python3
"""
Tests for process_customer_mapping.py

Verifies the 'On Screen' logic:
1. Existing 'Yes' values from customer mapping are preserved
2. Empty/missing 'On Screen' values default to 'No'
3. Objects added from CMJ snapshot get 'On Screen = No'
"""

import sys
import unittest
import pandas as pd
from pathlib import Path
from unittest.mock import patch, MagicMock

# Add scripts directory to path
sys.path.insert(0, str(Path(__file__).parent.parent / 'scripts'))

from process_customer_mapping import process_sheet, add_snapshot_objects


class TestOnScreenLogic(unittest.TestCase):
    """Test the 'On Screen' column logic."""

    def test_preserves_existing_yes_value(self):
        """Existing 'On Screen = Yes' from customer mapping should be preserved."""
        df = pd.DataFrame({
            'Source Name': ['Field A', 'Field B'],
            'Source ID': ['1001', '1002'],
            'Target Name': ['Field A', 'Field B'],
            'Target ID': ['2001', '2002'],
            'On Screen': ['Yes', 'Yes'],
            'Migration Action': [None, None]
        })

        source_data = {'CustomFields': {
            'Field A': {'id': '1001', 'type': 'text'},
            'Field B': {'id': '1002', 'type': 'text'}
        }}
        target_data = {'CustomFields': {
            'Field A': {'id': '2001', 'type': 'text'},
            'Field B': {'id': '2002', 'type': 'text'}
        }}
        snapshot_objects = {'CustomFields': set()}

        result_df, stats = process_sheet(df, 'CustomFields', source_data, target_data, snapshot_objects)

        # Both should still be 'Yes'
        self.assertEqual(result_df.loc[0, 'On Screen'], 'Yes')
        self.assertEqual(result_df.loc[1, 'On Screen'], 'Yes')

    def test_empty_on_screen_defaults_to_no(self):
        """Empty 'On Screen' values should default to 'No'."""
        df = pd.DataFrame({
            'Source Name': ['Field A', 'Field B'],
            'Source ID': ['1001', '1002'],
            'Target Name': ['Field A', 'Field B'],
            'Target ID': ['2001', '2002'],
            'On Screen': [None, ''],  # Empty values
            'Migration Action': [None, None]
        })

        source_data = {'CustomFields': {
            'Field A': {'id': '1001', 'type': 'text'},
            'Field B': {'id': '1002', 'type': 'text'}
        }}
        target_data = {'CustomFields': {
            'Field A': {'id': '2001', 'type': 'text'},
            'Field B': {'id': '2002', 'type': 'text'}
        }}
        snapshot_objects = {'CustomFields': set()}

        result_df, stats = process_sheet(df, 'CustomFields', source_data, target_data, snapshot_objects)

        # Both should be 'No'
        self.assertEqual(result_df.loc[0, 'On Screen'], 'No')
        self.assertEqual(result_df.loc[1, 'On Screen'], 'No')

    def test_snapshot_presence_does_not_set_yes(self):
        """Being in snapshot should NOT automatically set 'On Screen = Yes'."""
        df = pd.DataFrame({
            'Source Name': ['Field A'],
            'Source ID': ['1001'],
            'Target Name': ['Field A'],
            'Target ID': ['2001'],
            'On Screen': [None],  # Empty - should become 'No'
            'Migration Action': [None]
        })

        source_data = {'CustomFields': {
            'Field A': {'id': '1001', 'type': 'text'}
        }}
        target_data = {'CustomFields': {
            'Field A': {'id': '2001', 'type': 'text'}
        }}
        # Field A is in the snapshot
        snapshot_objects = {'CustomFields': {'Field A'}}

        result_df, stats = process_sheet(df, 'CustomFields', source_data, target_data, snapshot_objects)

        # Should be 'No' because original was empty, NOT 'Yes' just because it's in snapshot
        self.assertEqual(result_df.loc[0, 'On Screen'], 'No')


class TestAddSnapshotObjects(unittest.TestCase):
    """Test the add_snapshot_objects function."""

    def test_added_snapshot_objects_get_on_screen_no(self):
        """Objects added from CMJ snapshot should have 'On Screen = No'."""
        df = pd.DataFrame({
            'Source Name': ['Existing Field'],
            'Source ID': ['1001'],
            'Target Name': ['Existing Field'],
            'Target ID': ['2001'],
            'On Screen': ['Yes'],
            'Match Type': ['EXACT_MATCH'],
            'Migration Action': ['MAP']
        })

        source_data = {'CustomFields': {
            'Existing Field': {'id': '1001', 'type': 'text'},
            'New Snapshot Field': {'id': '1002', 'type': 'text'}
        }}
        target_data = {'CustomFields': {
            'Existing Field': {'id': '2001', 'type': 'text'}
        }}
        # New field in snapshot that's not in the mapping
        snapshot_objects = {'CustomFields': {'Existing Field', 'New Snapshot Field'}}

        result_df = add_snapshot_objects(df, 'CustomFields', snapshot_objects, source_data, target_data)

        # Find the newly added row
        new_row = result_df[result_df['Source Name'] == 'New Snapshot Field']

        self.assertEqual(len(new_row), 1)
        self.assertEqual(new_row.iloc[0]['On Screen'], 'No')
        self.assertEqual(new_row.iloc[0]['Project'], 'CMJ_SNAPSHOT')


class TestIntegration(unittest.TestCase):
    """Integration tests using actual project data."""

    def test_project_processed_file_on_screen_values(self):
        """Verify the PROJECT processed file has correct 'On Screen' values."""
        processed_file = Path(__file__).parent.parent / 'customer_review' / 'PROJECT_Customer_Mapping_PROCESSED.xlsx'

        if not processed_file.exists():
            self.skipTest(f"Processed file not found: {processed_file}")

        df = pd.read_excel(processed_file, sheet_name='CustomFields')

        # All CMJ_SNAPSHOT objects should have 'On Screen = No'
        snapshot_objects = df[df['Project'] == 'CMJ_SNAPSHOT']
        snapshot_yes = snapshot_objects[snapshot_objects['On Screen'] == 'Yes']

        self.assertEqual(
            len(snapshot_yes), 0,
            f"Found {len(snapshot_yes)} CMJ_SNAPSHOT objects with 'On Screen = Yes'. "
            f"All should be 'No'.\nObjects: {snapshot_yes['Source Name'].tolist()}"
        )

    def test_original_mapping_yes_values_preserved(self):
        """Verify original customer mapping 'Yes' values are preserved."""
        processed_file = Path(__file__).parent.parent / 'customer_review' / 'PROJECT_Customer_Mapping_PROCESSED.xlsx'

        if not processed_file.exists():
            self.skipTest(f"Processed file not found: {processed_file}")

        df = pd.read_excel(processed_file, sheet_name='CustomFields')

        # Objects from original mapping (not CMJ_SNAPSHOT) should have their values preserved
        original_objects = df[df['Project'] != 'CMJ_SNAPSHOT']

        # Should have some 'Yes' values (from original customer mapping)
        yes_count = (original_objects['On Screen'] == 'Yes').sum()

        self.assertGreater(
            yes_count, 0,
            "Expected some 'On Screen = Yes' values from original customer mapping"
        )


if __name__ == '__main__':
    unittest.main(verbosity=2)
