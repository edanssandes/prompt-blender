import pytest
from prompt_blender.model import Model, ParameterCombination
from unittest.mock import patch
import tempfile
import os


class TestParameterCombinations:
    """Test suite for parameter combinations functionality."""

    def test_parameter_combinations_basic(self):
        """Test basic parameter combinations generation."""
        # Create a model with test data
        data = {
            "prompts": {"test_prompt": "Enter a number: {param1}+{param2}"},
            "parameters": {
                "param1": [{"param1": 1}, {"param1": 2}, {"param1": 3}],
                "param2": [{"param2": 4}, {"param2": 5}]
            },
            "runs": {}
        }
        model = Model(data)

        # Expected results: 3 * 2 = 6 combinations
        combinations = list(model.get_parameter_combinations())
        
        assert len(combinations) == 6
        
        expected = [
            "Enter a number: 1+4",
            "Enter a number: 1+5",
            "Enter a number: 2+4",
            "Enter a number: 2+5",
            "Enter a number: 3+4",
            "Enter a number: 3+5"
        ]

        # Check all combinations
        for combo, exp in zip(combinations, expected):
            assert isinstance(combo, ParameterCombination)
            assert combo.prompt_content == exp
            assert combo.missing_argument is None
            assert combo.filepath.startswith("cache/")
            assert combo.prompt_file.endswith("/prompt.txt")
            assert combo.prompt_file == f"cache/{combo.prompt_hash[:2]}/{combo.prompt_hash}/prompt.txt"
            # prompt_arguments keys
            assert combo._prompt_arguments.keys() == {'param1', 'param2', 'prompt'}
            assert combo._prompt_arguments_masked.keys() == {'param1', 'param2', 'prompt'}
            assert combo._prompt_arguments['prompt'] == data["prompts"]["test_prompt"]
            assert combo._prompt_arguments_masked['prompt'] == "test_prompt"
            assert exp == f"Enter a number: {combo._prompt_arguments['param1']}+{combo._prompt_arguments['param2']}"

    def test_parameter_combinations_with_callback(self):
        """Test parameter combinations with progress callback."""
        data = {
            "prompts": {"test_prompt": "Test {param1}"},
            "parameters": {
                "param1": [{"param1": 1}, {"param1": 2}]
            },
            "runs": {}
        }
        model = Model(data)

        callback_calls = []
        
        def callback(current, total):
            callback_calls.append((current, total))
            return True

        combinations = list(model.get_parameter_combinations(callback))
        
        assert len(combinations) == 2
        assert len(callback_calls) == 3  # 0, 1, 2
        assert callback_calls[0] == (0, 2)
        assert callback_calls[1] == (1, 2)
        assert callback_calls[2] == (2, 2)

    def test_parameter_combinations_missing_argument(self):
        """Test handling of missing arguments in prompt."""
        data = {
            "prompts": {"test_prompt": "Enter a number: {param1}+{missing_param}"},
            "parameters": {
                "param1": [{"param1": 1}, {"param1": 2}]
            },
            "runs": {}
        }
        model = Model(data)

        combinations = list(model.get_parameter_combinations())
        
        assert len(combinations) == 2
        for combo in combinations:
            assert combo.missing_argument == ["'missing_param'"]
            assert combo.prompt_content is None

    def test_blend_prompt_function(self):
        """Test the blend_prompt function with a proper Model instance."""
        from prompt_blender.blend import blend_prompt
        
        # Create a temporary directory for cache
        with tempfile.TemporaryDirectory() as temp_dir:
            # Create a model
            data = {
                "prompts": {"test_prompt": "Hello {name}!"},
                "parameters": {
                    "name": [{"name": "World"}, {"name": "Universe"}]
                },
                "runs": {}
            }
            model = Model(data)

            # Call blend_prompt
            files = blend_prompt(model, temp_dir)
            
            assert len(files) == 2
            
            # Check that files were created
            for filename, params in files:
                assert os.path.exists(filename)
                with open(filename, 'r', encoding='utf-8') as f:
                    content = f.read()
                    assert content in ["Hello World!", "Hello Universe!"]

    def test_parameter_combination_properties(self):
        """Test ParameterCombination properties."""
        combination_data = [
            {"_id": "test_prompt", "prompt": "Hello {name}!"},
            {"name": "World"}
        ]
        
        combo = ParameterCombination(combination_data)
        
        assert combo.prompt_content == "Hello World!"
        assert combo.missing_argument is None
        assert combo.filepath.startswith("cache/")
        assert combo.prompt_file.endswith("/prompt.txt")
        
        # Test result file generation
        test_hash = "test_hash_123"
        result_file = combo.get_result_file(test_hash)
        assert result_file.endswith(f"/result_{test_hash}.json")

    def test_model_get_num_combinations(self):
        """Test calculation of total number of combinations."""
        data = {
            "prompts": {"prompt1": "Test", "prompt2": "Test2"},
            "parameters": {
                "param1": [{"param1": 1}, {"param1": 2}, {"param1": 3}],  # 3 values
                "param2": [{"param2": "a"}, {"param2": "b"}]  # 2 values  
            },
            "runs": {}
        }
        model = Model(data)

        # 2 prompts * 3 param1 values * 2 param2 values = 12
        assert model.get_num_combinations() == 12

    def test_get_current_combination(self):
        """Test getting current combination for a specific prompt."""
        data = {
            "prompts": {"test_prompt": "Hello {name}! Today is {day}."},
            "parameters": {
                "name": [{"name": "World"}, {"name": "Universe"}],
                "day": [{"day": "Monday"}, {"day": "Tuesday"}]
            },
            "runs": {}
        }
        model = Model(data)
        
        # Mock get_selected_values to return first values
        with patch.object(model, 'get_selected_values', return_value={"name": "Universe", "day": "Tuesday"}):
            combo = model.get_current_combination("test_prompt")
            assert combo.prompt_content == "Hello Universe! Today is Tuesday."


if __name__ == '__main__':
    pytest.main([__file__, "-v"])
