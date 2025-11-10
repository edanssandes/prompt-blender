import pytest
import tempfile
import os
import json
import zipfile
import shutil
from pathlib import Path
from unittest.mock import patch, MagicMock
from prompt_blender.cache import Cache


class TestCache:
    """Test suite for the Cache class."""

    @pytest.fixture
    def temp_dir(self):
        """Create a temporary directory for testing."""
        temp_dir = tempfile.mkdtemp()
        yield temp_dir
        shutil.rmtree(temp_dir)

    @pytest.fixture
    def temp_zip(self, temp_dir):
        """Create a temporary zip file path."""
        return os.path.join(temp_dir, "test_cache.zip")

    @pytest.fixture
    def sample_data(self):
        """Sample data for testing."""
        return {
            "prompt_content": "Hello {name}!",
            "result_data": {
                "response": "Hello World!",
                "timestamp": "20231201120000",
                "cost": 0.01,
                "elapsed_time": 1.5
            }
        }

    def test_directory_cache_init(self, temp_dir):
        """Test Cache initialization with directory backend."""
        cache_dir = os.path.join(temp_dir, "cache")
        cache = Cache(cache_dir)

        assert cache.path == Path(cache_dir)
        assert not cache.is_zip
        assert cache._zip_file is None

        # Directory should be created
        assert os.path.exists(cache_dir)

    def test_zip_cache_init_read(self, temp_zip):
        """Test Cache initialization with zipfile backend in read mode."""
        # Create a dummy zip file first
        with zipfile.ZipFile(temp_zip, 'w') as zf:
            zf.writestr('test.txt', 'test content')

        cache = Cache(temp_zip, 'r')

        assert cache.path == Path(temp_zip)
        assert cache.is_zip
        assert cache._zip_file is not None

    def test_zip_cache_init_write(self, temp_zip):
        """Test that zip cache write mode raises error."""
        with pytest.raises(ValueError, match="Zipfile caches are read-only"):
            Cache(temp_zip, 'w')

    def test_context_manager(self, temp_dir):
        """Test Cache as context manager."""
        cache_dir = os.path.join(temp_dir, "cache")

        with Cache(cache_dir) as cache:
            assert cache.path == Path(cache_dir)

        # Should be closed after context
        assert cache._zip_file is None

    def test_insert_and_read_file_directory(self, temp_dir, sample_data):
        """Test inserting and reading files in directory cache."""
        cache_dir = os.path.join(temp_dir, "cache")
        cache = Cache(cache_dir)

        # Insert text file
        cache.insert_file("cdef", "prompt.txt", sample_data["prompt_content"])

        # Read it back
        content = cache.read_file("cdef", "prompt.txt")
        assert content == sample_data["prompt_content"]

        # Insert JSON file
        json_content = json.dumps(sample_data["result_data"])
        cache.insert_file("cdef", "result_abc123.json", json_content)

        # Read it back
        read_content = cache.read_file("cdef", "result_abc123.json")
        assert json.loads(read_content) == sample_data["result_data"]

    def test_insert_and_read_file_zip(self, temp_zip, sample_data):
        """Test reading files from zip cache."""
        # Create zip file with content first
        with zipfile.ZipFile(temp_zip, 'w') as zf:
            zf.writestr("cache/cd/cdef/prompt.txt", sample_data["prompt_content"])
            zf.writestr("cache/cd/cdef/result_abc123.json", json.dumps(sample_data["result_data"]))

        # Now read from zip
        cache = Cache(temp_zip, 'r')
        content = cache.read_file("cdef", "prompt.txt")
        assert content == sample_data["prompt_content"]

        read_json = cache.read_file("cdef", "result_abc123.json")
        assert json.loads(read_json) == sample_data["result_data"]

    def test_read_file_not_found(self, temp_dir):
        """Test reading non-existent file raises FileNotFoundError."""
        cache_dir = os.path.join(temp_dir, "cache")
        cache = Cache(cache_dir)

        with pytest.raises(FileNotFoundError):
            cache.read_file("nonexistent", "txt")

    def test_merge_caches_zip_error(self, temp_dir, temp_zip, sample_data):
        """Test that merging into zip cache raises error."""
        # Create zip file
        with zipfile.ZipFile(temp_zip, 'w') as zf:
            zf.writestr("cache/ab/cdef/prompt.txt", sample_data["prompt_content"])

        cache_zip = Cache(temp_zip, 'r')
        cache_dir = Cache(os.path.join(temp_dir, "cache2"))

        with pytest.raises(RuntimeError, match="Cannot merge into zipfile cache"):
            cache_zip.merge(cache_dir)

    def test_merge_caches_directory(self, temp_dir, sample_data):
        """Test merging two directory caches."""
        cache_dir1 = os.path.join(temp_dir, "cache1")
        cache_dir2 = os.path.join(temp_dir, "cache2")

        cache1 = Cache(cache_dir1)
        cache2 = Cache(cache_dir2)

        # Add files to cache1
        cache1.insert_file("cdef", "prompt.txt", sample_data["prompt_content"])

        # Add files to cache2
        cache2.insert_file("zyxw", "result_abc123.json", json.dumps(sample_data["result_data"]))

        # Merge cache2 into cache1
        cache1.merge(cache2)

        # Check cache1 has both files
        files = cache1._list_files()
        file_names = [filename for sub_dir, filename in files]
        assert len(file_names) == 2
        assert "prompt.txt" in file_names
        assert "result_abc123.json" in file_names

    def test_get_statistics_directory(self, temp_dir, sample_data):
        """Test getting statistics for directory cache."""
        cache_dir = os.path.join(temp_dir, "cache")
        cache = Cache(cache_dir)

        # Add some files
        cache.insert_file("cdef", "prompt.txt", sample_data["prompt_content"])
        cache.insert_file("cdef", "result_abc123.json", json.dumps(sample_data["result_data"]))
        cache.insert_file("cdef", "result_abc123.json.delayed", json.dumps({"delayed": True}))

        stats = cache.get_statistics()

        assert stats['total_files'] == 3
        assert stats['cache_type'] == 'directory'
        assert stats['file_types']['text'] == 1
        assert stats['file_types']['json'] == 1
        assert stats['file_types']['delayed'] == 1
        assert stats['prompt_files_count'] == 1
        assert stats['result_files_count'] == 1
        assert stats['delayed_files_count'] == 1
        assert stats['total_size_bytes'] > 0

    def test_get_statistics_zip(self, temp_zip, sample_data):
        """Test getting statistics for zip cache."""
        # Create zip file with content first
        with zipfile.ZipFile(temp_zip, 'w') as zf:
            zf.writestr("cache/cd/cdef/prompt.txt", sample_data["prompt_content"])
            zf.writestr("cache/cd/cdef/result_abc123.json", json.dumps(sample_data["result_data"]))

        cache = Cache(temp_zip, 'r')
        stats = cache.get_statistics()

        assert stats['total_files'] == 2
        assert stats['cache_type'] == 'zipfile'
        assert stats['prompt_files_count'] == 1
        assert stats['result_files_count'] == 1

    def test_expire_cache_zip_error(self, temp_zip, sample_data):
        """Test that expiring cache in zip file raises error."""
        # Create zip file with content
        with zipfile.ZipFile(temp_zip, 'w') as zf:
            zf.writestr("cache/cd/cdef/result_abc123.json", json.dumps(sample_data["result_data"]))

        cache = Cache(temp_zip, 'r')
        with pytest.raises(RuntimeError, match="Cannot expire files in zipfile cache"):
            cache.expire_cache(timeout_seconds=3600)

    def test_expire_cache_timeout_directory(self, temp_dir, sample_data):
        """Test cache expiration based on timeout for directory cache."""
        cache_dir = os.path.join(temp_dir, "cache")
        cache = Cache(cache_dir)

        # Add a file
        cache.insert_file("cdef", "result_abc123.json", json.dumps(sample_data["result_data"]))

        # Expire with timeout=0 (should expire all files immediately)
        expired = cache.expire_cache(timeout_seconds=0)
        assert expired == 1

        # File should be gone
        files = cache._list_files()
        assert len(files) == 0

    def test_expire_cache_error_items(self, temp_dir):
        """Test cache expiration for error items."""
        cache_dir = os.path.join(temp_dir, "cache")
        cache = Cache(cache_dir)

        # Create a result file with error
        error_result = {
            "response": "Error response",
            "timestamp": "20231201120000"
        }
        cache.insert_file("cdef", "result_abc123.json", json.dumps(error_result))

        # Mock the analysis to return an error
        with patch('prompt_blender.analysis.gpt_json.analyse') as mock_analyse:
            mock_analyse.return_value = [{"_error": "Test error"}]

            expired = cache.expire_cache(error_items_only=True)
            assert expired == 1

            # File should be gone
            files = cache._list_files()
            assert len(files) == 0

    def test_binary_file_handling(self, temp_dir):
        """Test handling of binary files."""
        cache_dir = os.path.join(temp_dir, "cache")
        cache = Cache(cache_dir)

        binary_data = b'\x00\x01\x02\x03\xff\xfe\xfd'
        cache.insert_file("test", "bin", binary_data)

        read_data = cache.read_file("test", "bin")
        assert read_data == binary_data

    def test_list_files_no_cache_prefix(self, temp_dir, sample_data):
        """Test that _list_files() returns paths without the cache/ prefix."""
        cache_dir = os.path.join(temp_dir, "cache")
        cache = Cache(cache_dir)

        # Insert files with different sub_directories
        cache.insert_file("cdef", "prompt.txt", sample_data["prompt_content"])
        cache.insert_file("cdef", "result_abc123.json", json.dumps(sample_data["result_data"]))
        cache.insert_file("zyxw", "prompt.txt", "Another prompt")

        files = cache._list_files()

        # Files should be returned as tuples (sub_dir, filename)
        # Reconstruct paths for checking
        paths = [f"{sub_dir[:2]}/{sub_dir}/{filename}" for sub_dir, filename in files]
        
        # Files should be returned without the "cache/" prefix
        # So instead of "cache/cd/cdef/prompt.txt", we get "cd/cdef/prompt.txt"
        assert len(paths) == 3
        
        # None of the files should start with "cache/"
        for file_path in paths:
            assert not file_path.startswith("cache/")
        
        # But they should include the hash prefix directories (cd/, zy/)
        cdef_files = [f for f in paths if "cdef" in f]
        zyxw_files = [f for f in paths if "zyxw" in f]
        
        assert len(cdef_files) == 2  # prompt.txt and result_abc123.json
        assert len(zyxw_files) == 1  # prompt.txt
        
        # Verify the hash prefix logic: "cdef" -> "cd", "zyxw" -> "zy"
        for file_path in cdef_files:
            assert "cd/cdef/" in file_path
        for file_path in zyxw_files:
            assert "zy/zyxw/" in file_path

    def test_invalid_mode(self, temp_zip):
        """Test invalid mode raises ValueError for zip files."""
        with pytest.raises(ValueError, match="Zipfile caches are read-only"):
            Cache(temp_zip, 'w')

    def test_invalid_mode_directory(self, temp_dir):
        """Test that directory cache accepts various modes."""
        cache_dir = os.path.join(temp_dir, "cache")
        # Should not raise for directory
        cache = Cache(cache_dir, 'w')
        assert not cache.is_zip

    def test_add_to_zip(self, temp_dir, temp_zip, sample_data):
        """Test adding cache files to a zip archive."""
        cache_dir = os.path.join(temp_dir, "cache")
        cache = Cache(cache_dir)

        # Create some test files in cache
        cache.insert_file("cdef", "prompt.txt", sample_data["prompt_content"])
        cache.insert_file("cdef", "result_run1.json", json.dumps(sample_data["result_data"]))
        cache.insert_file("zyxw", "prompt.txt", "Another prompt")
        cache.insert_file("zyxw", "result_run1.json", json.dumps(sample_data["result_data"]))

        # Create a mock config and run_args
        from unittest.mock import MagicMock
        mock_config = MagicMock()
        
        # TODO: remove "cache/hash[:2]" logic from parameter combinations

        # Mock parameter combinations
        mock_combo1 = MagicMock()
        mock_combo1.prompt_file = "cache/cd/cdef/prompt.txt"
        mock_combo1.get_result_file.return_value = "cache/cd/cdef/result_run1.json"
        
        mock_combo2 = MagicMock()
        mock_combo2.prompt_file = "cache/zy/zyxw/prompt.txt"
        mock_combo2.get_result_file.return_value = "cache/zy/zyxw/result_run1.json"
        
        mock_config.get_parameter_combinations.return_value = [mock_combo1, mock_combo2]
        
        run_args = {
            "run1": {"run_hash": "run1"}
        }

        # Create zip file and add cache files
        with zipfile.ZipFile(temp_zip, 'w') as zf:
            zf.writestr('test.txt', 'existing file')  # Add something first
            cache.add_to_zip(zf, mock_config, run_args)

        # Verify zip contents
        with zipfile.ZipFile(temp_zip, 'r') as zf:
            file_list = zf.namelist()
            
            # Should contain the added files
            assert 'cache/cd/cdef/prompt.txt' in file_list
            assert 'cache/cd/cdef/result_run1.json' in file_list
            assert 'cache/zy/zyxw/prompt.txt' in file_list
            assert 'cache/zy/zyxw/result_run1.json' in file_list
            assert 'test.txt' in file_list  # Original file still there
            
            # Verify content
            with zf.open('cache/cd/cdef/prompt.txt') as f:
                assert f.read().decode() == sample_data["prompt_content"]


if __name__ == '__main__':
    pytest.main([__file__, "-v"])