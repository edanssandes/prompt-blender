"""
Test suite for date handling in CSV/Excel files.

Bug: When loading Excel files with date columns via pd.read_excel(),
pandas auto-converts date-like columns to pd.Timestamp objects.
These Timestamp objects are NOT JSON serializable, so when the model
tries to save via json.dump() in save_to_fp(), it raises a TypeError.

The same issue can occur with CSV files when they are loaded without
dtype=str (e.g., through add_table_from_string with csv extension),
or when Excel files contain date columns.
"""

import pytest
import pandas as pd
import json
import io

from prompt_blender.model import Model


class TestDateHandlingInExcel:
    """Test that date columns in Excel files don't break JSON serialization."""

    @pytest.fixture
    def model_from_excel(self, tmp_path):
        """Create a model loaded from an Excel file with date and mixed-type columns."""
        df = pd.DataFrame({
            'name': ['Alice', 'Bob'],
            'age': [30, 25],
            'start_date': pd.to_datetime(['2023-06-01', '2024-01-15']),
            'score': [95.5, 88.0]
        })
        excel_path = tmp_path / "data.xlsx"
        df.to_excel(excel_path, index=False)

        model = Model({})
        model.add_table_from_file(str(excel_path), variable='records')
        return model

    def test_excel_values_are_all_strings(self, model_from_excel):
        """After loading an Excel file, all parameter values should be strings."""
        for row in model_from_excel.get_parameter('records'):
            for key, value in row.items():
                assert isinstance(value, str), \
                    f"Key '{key}' has type {type(value).__name__}, expected str. Value: {value}"

    def test_excel_with_dates_can_be_saved_as_json(self, model_from_excel):
        """
        BUG: pd.Timestamp objects from Excel date columns cause
        json.dump() to raise TypeError: Object of type Timestamp is not JSON serializable.
        """
        fp = io.StringIO()
        model_from_excel.save_to_fp(fp)

        # Verify the saved JSON is valid and parseable
        fp.seek(0)
        saved_data = json.loads(fp.read())
        assert len(saved_data['parameters']['records']) == 2


class TestDateHandlingInCSV:
    """Test that CSV files with date-like data are handled correctly."""

    def test_csv_with_date_column_stays_string(self, tmp_path):
        """CSV loaded with dtype=str should keep dates as strings."""
        model = Model({})

        df = pd.DataFrame({
            'name': ['Alice', 'Bob'],
            'birthday': ['2024-01-15', '2024-03-20']
        })
        csv_path = tmp_path / "data.csv"
        df.to_csv(csv_path, index=False)

        model.add_table_from_file(str(csv_path), variable='people')
        result = model.get_parameter('people')

        assert len(result) == 2
        for row in result:
            assert isinstance(row['birthday'], str)

        # Must serialize to JSON without error
        fp = io.StringIO()
        model.save_to_fp(fp)

    def test_csv_with_nan_can_be_saved(self, tmp_path):
        """CSV with missing values (NaN) should be handled in JSON serialization."""
        model = Model({})

        csv_path = tmp_path / "data.csv"
        csv_path.write_text("name,date\nAlice,2024-01-15\nBob,\n", encoding='utf-8')

        model.add_table_from_file(str(csv_path), variable='people')
        result = model.get_parameter('people')
        assert len(result) == 2

        # Must serialize to JSON without error (NaN is not valid JSON)
        fp = io.StringIO()
        model.save_to_fp(fp)

        fp.seek(0)
        saved_data = json.loads(fp.read())
        assert 'parameters' in saved_data


class TestDateHandlingInPromptInterpolation:
    """Test that date values in parameters work correctly during prompt interpolation."""

    def test_prompt_interpolation_with_date_values(self):
        """Timestamps in parameters should be properly converted to strings during interpolation."""
        data = {
            "prompts": {"greeting": "Hello {{name}}, your appointment is on {{date}}."},
            "parameters": {
                "people": [
                    {"name": "Alice", "date": pd.Timestamp("2024-01-15")},
                ]
            },
            "runs": {}
        }
        model = Model(data)

        # The interpolation should handle Timestamp values via _to_str
        combinations = list(model.get_parameter_combinations())
        assert len(combinations) == 1
        assert "2024-01-15" in combinations[0].prompt_content


if __name__ == '__main__':
    pytest.main([__file__, "-v"])
