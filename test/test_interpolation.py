import pytest
from prompt_blender.model import Model, ParameterCombination


class TestInterpolationWithEmptyFields:
    """Test suite for variable interpolation with empty/missing field values."""

    def test_interpolate_with_nan_value(self):
        """Test that NaN values (from pandas empty cells) don't break interpolation."""
        data = {
            "prompts": {"test_prompt": "Name: {{name}}, Age: {{age}}"},
            "parameters": {
                "params": [
                    {"name": "Alice", "age": "30"},
                    {"name": "Bob", "age": float('nan')},  # NaN from empty CSV cell
                ]
            },
            "runs": {}
        }
        model = Model(data)

        # Should not raise an error
        combinations = list(model.get_parameter_combinations())
        assert len(combinations) == 2
        assert combinations[0].prompt_content == "Name: Alice, Age: 30"
        # NaN should be converted to empty string, not crash
        assert combinations[1].prompt_content == "Name: Bob, Age: "

    def test_interpolate_with_none_value(self):
        """Test that None values don't break interpolation."""
        data = {
            "prompts": {"test_prompt": "Name: {{name}}, Age: {{age}}"},
            "parameters": {
                "params": [
                    {"name": "Alice", "age": "30"},
                    {"name": "Bob", "age": None},  # None from JSON null
                ]
            },
            "runs": {}
        }
        model = Model(data)

        # Should not raise an error
        combinations = list(model.get_parameter_combinations())
        assert len(combinations) == 2
        assert combinations[0].prompt_content == "Name: Alice, Age: 30"
        # None should be converted to empty string, not crash
        assert combinations[1].prompt_content == "Name: Bob, Age: "

    def test_interpolate_with_empty_string(self):
        """Test that empty string values work correctly."""
        data = {
            "prompts": {"test_prompt": "Name: {{name}}, Age: {{age}}"},
            "parameters": {
                "params": [
                    {"name": "Alice", "age": ""},
                ]
            },
            "runs": {}
        }
        model = Model(data)

        combinations = list(model.get_parameter_combinations())
        assert len(combinations) == 1
        assert combinations[0].prompt_content == "Name: Alice, Age: "

    def test_interpolate_with_numeric_value(self):
        """Test that numeric (non-string) values are properly handled."""
        data = {
            "prompts": {"test_prompt": "Count: {{count}}"},
            "parameters": {
                "params": [
                    {"count": 42},
                    {"count": 3.14},
                ]
            },
            "runs": {}
        }
        model = Model(data)

        combinations = list(model.get_parameter_combinations())
        assert len(combinations) == 2
        assert combinations[0].prompt_content == "Count: 42"
        assert combinations[1].prompt_content == "Count: 3.14"

    def test_interpolate_csv_with_empty_cells(self):
        """Test interpolation with data loaded from CSV containing empty cells."""
        model = Model({
            "prompts": {"test_prompt": "City: {{city}}, Country: {{country}}"},
            "parameters": {},
            "runs": {}
        })

        csv_content = (
            "city,country\n"
            "Paris,France\n"
            "Berlin,\n"   # Empty country
            ",Germany\n"  # Empty city
        )
        model.add_table_from_string(csv_content, 'csv')

        # Should not raise an error
        combinations = list(model.get_parameter_combinations())
        assert len(combinations) == 3
        assert combinations[0].prompt_content == "City: Paris, Country: France"
        # Empty cells should not crash the interpolation
        assert "Berlin" in combinations[1].prompt_content
        assert "Germany" in combinations[2].prompt_content

    def test_interpolate_json_with_null_values(self):
        """Test interpolation with data loaded from JSON containing null values."""
        model = Model({
            "prompts": {"test_prompt": "City: {{city}}, Country: {{country}}"},
            "parameters": {},
            "runs": {}
        })

        json_content = '[{"city": "Paris", "country": "France"}, {"city": "Berlin", "country": null}]'
        model.add_table_from_string(json_content, 'json')

        # Should not raise an error
        combinations = list(model.get_parameter_combinations())
        assert len(combinations) == 2
        assert combinations[0].prompt_content == "City: Paris, Country: France"
        assert combinations[1].prompt_content == "City: Berlin, Country: "

    def test_get_interpolated_prompt_with_nan(self):
        """Test get_interpolated_prompt with NaN selected value."""
        data = {
            "prompts": {"test_prompt": "Value: {{val}}"},
            "parameters": {
                "params": [
                    {"val": float('nan')},
                ]
            },
            "runs": {}
        }
        model = Model(data)

        # Should not raise an error
        result = model.get_interpolated_prompt("test_prompt")
        assert isinstance(result, str)
        assert result == "Value: "

    def test_get_interpolated_prompt_with_none(self):
        """Test get_interpolated_prompt with None selected value."""
        data = {
            "prompts": {"test_prompt": "Value: {{val}}"},
            "parameters": {
                "params": [
                    {"val": None},
                ]
            },
            "runs": {}
        }
        model = Model(data)

        # Should not raise an error
        result = model.get_interpolated_prompt("test_prompt")
        assert isinstance(result, str)
        assert result == "Value: "


if __name__ == '__main__':
    pytest.main([__file__, "-v"])
