import pytest
import tempfile
import os
import json
import zipfile
import pandas as pd
from unittest.mock import Mock, patch
from prompt_blender import result_file
from prompt_blender.model import Model, ParameterCombination


class TestResultFile:
    """Test suite for result file operations."""

    @pytest.fixture
    def sample_config(self):
        """Create a sample configuration for testing."""
        data = {
            "prompts": {
                "test_prompt": "Hello {name}!",
                "another_prompt": "Goodbye {name}!"
            },
            "parameters": {
                "name": [{"name": "World"}, {"name": "Universe"}]
            },
            "runs": {}
        }
        return Model(data)

    @pytest.fixture
    def sample_analysis_results(self):
        """Sample analysis results."""
        return {
            "run1": {
                "gpt_cost": [
                    {"tokens in": 100, "tokens out": 50, "cost in": 0.1, "cost out": 0.05},
                    {"tokens in": 120, "tokens out": 60, "cost in": 0.12, "cost out": 0.06}
                ],
                "response_analysis": [
                    {"length": 25, "sentiment": "positive"},
                    {"length": 30, "sentiment": "neutral"}
                ]
            },
            "run2": {
                "gpt_cost": [
                    {"tokens in": 80, "tokens out": 40, "cost in": 0.08, "cost out": 0.04}
                ]
            }
        }

    @pytest.fixture
    def sample_run_args(self):
        """Sample run arguments."""
        return {
            "run1": {
                "module_name": "chatgpt",
                "module_info": {
                    "id": "test-module-1",
                    "description": "Test ChatGPT module",
                    "version": "1.0.0"
                },
                "run_hash": "abc123",
                "args": {"temperature": 0.7, "max_tokens": 150}
            },
            "run2": {
                "module_name": "chatgpt_manual",
                "module_info": {
                    "id": "test-module-2",
                    "description": "Manual ChatGPT module",
                    "version": "1.1.0"
                },
                "run_hash": "def456",
                "args": {"temperature": 0.9}
            }
        }

    def test_merge_analysis_results(self, sample_config, sample_analysis_results, sample_run_args):
        """Test merging of analysis results."""
        merged = result_file._merge_analysis_results(
            sample_config, sample_analysis_results, sample_run_args
        )
        
        # Check that merged results contain expected modules
        assert "gpt_cost" in merged
        assert "response_analysis" in merged
        assert "prompts" in merged
        assert "runs" in merged
        
        # Check gpt_cost results
        gpt_cost_results = merged["gpt_cost"]
        assert len(gpt_cost_results) == 3  # 2 from run1 + 1 from run2
        
        # Check that _run field is added
        run_names = [result["_run"] for result in gpt_cost_results]
        assert "run1" in run_names
        assert "run2" in run_names
        
        # Check response_analysis results
        response_results = merged["response_analysis"]
        assert len(response_results) == 2  # Only from run1
        assert all(result["_run"] == "run1" for result in response_results)
        
        # Check prompts
        prompts = merged["prompts"]
        assert len(prompts) == 2
        prompt_names = [p["Prompt Name"] for p in prompts]
        assert "test_prompt" in prompt_names
        assert "another_prompt" in prompt_names
        
        # Check runs
        runs = merged["runs"]
        assert len(runs) == 2
        run_names = [r["Run Name"] for r in runs]
        assert "run1" in run_names
        assert "run2" in run_names

    def test_save_and_read_result_file(self, sample_config, sample_analysis_results, sample_run_args):
        """Test saving and reading result files."""
        with tempfile.TemporaryDirectory() as temp_dir:
            # Create cache directory structure and prompt files
            cache_dir = os.path.join(temp_dir, "cache")
            os.makedirs(cache_dir, exist_ok=True)
            
            # Generate prompt files using the model
            from prompt_blender.blend import blend_prompt
            prompt_files = blend_prompt(sample_config, cache_dir)
            
            # Test saving
            result_zip_path = os.path.join(temp_dir, "test_results.zip")
            result_file.save_analysis_results(
                result_zip_path, cache_dir, sample_analysis_results, sample_config, sample_run_args
            )
            
            # Verify the ZIP file was created
            assert os.path.exists(result_zip_path)
            
            # Test reading
            read_results = result_file.read_result_file(result_zip_path)
            
            # Verify structure
            assert "gpt_cost" in read_results
            assert "response_analysis" in read_results
            assert "prompts" in read_results
            assert "runs" in read_results
            
            # Verify content
            assert len(read_results["gpt_cost"]) == 3
            assert len(read_results["response_analysis"]) == 2
            assert len(read_results["prompts"]) == 2
            assert len(read_results["runs"]) == 2




    def test_read_result_file_structure(self, sample_config, sample_analysis_results, sample_run_args):
        """Test the internal structure of saved ZIP files."""
        with tempfile.TemporaryDirectory() as temp_dir:
            cache_dir = os.path.join(temp_dir, "cache")
            os.makedirs(cache_dir, exist_ok=True)
            
            # Generate prompt files
            from prompt_blender.blend import blend_prompt
            blend_prompt(sample_config, cache_dir)
            
            # Create mock result files
            for combination in sample_config.get_parameter_combinations():
                for run_hash in ["abc123", "def456"]:
                    result_file_path = os.path.join(cache_dir, combination.get_result_file(run_hash))
                    os.makedirs(os.path.dirname(result_file_path), exist_ok=True)
                    
                    # Create a mock result file
                    mock_result = {
                        "model": "gpt-4o-mini",
                        "choices": [{"message": {"content": "Mock response"}}],
                        "usage": {"prompt_tokens": 10, "completion_tokens": 5}
                    }
                    with open(result_file_path, 'w') as f:
                        json.dump(mock_result, f)


            result_zip_path = os.path.join(temp_dir, "test_results.zip")
            result_file.save_analysis_results(
                result_zip_path, cache_dir, sample_analysis_results, sample_config, sample_run_args
            )
            
            # Check zip contents
            with zipfile.ZipFile(result_zip_path, 'r') as zipf:
                file_list = zipf.namelist()
                
                # Check required files
                assert "result.xlsx" in file_list
                assert "config.pbp" in file_list
                
                # Check prompt files are included
                prompt_files_in_zip = [f for f in file_list if f.endswith("prompt.txt")]
                assert len(prompt_files_in_zip) == 4  # 2 prompts × 2 parameter combinations

                result_files_in_zip = [f for f in file_list if 'result_' in f and f.endswith('.json')]
                assert len(result_files_in_zip) == 8  # 2 prompts × 2 parameter combinations  × 2 runs

                # Check config file content
                with zipf.open("config.pbp") as config_file:
                    config_content = config_file.read().decode('utf-8')
                    config_data = json.loads(config_content)
                    assert "prompts" in config_data
                    assert "parameters" in config_data


    def test_empty_analysis_results(self, sample_config, sample_run_args):
        """Test handling of empty analysis results."""
        empty_results = {}
        
        merged = result_file._merge_analysis_results(
            sample_config, empty_results, sample_run_args
        )
        
        # Should still contain prompts and runs
        assert "prompts" in merged
        assert "runs" in merged
        assert len(merged["prompts"]) == 2
        assert len(merged["runs"]) == 2


if __name__ == '__main__':
    pytest.main([__file__, "-v"])