import tomllib
import pytest
from prompt_blender import info


class TestVersionConsistency:
    """Test suite for version consistency across the project."""

    def test_pyproject_toml_version_matches_info_py(self):
        """Test that the version in pyproject.toml matches __version__ in info.py."""
        # Read version from pyproject.toml
        with open('pyproject.toml', 'rb') as f:
            pyproject_data = tomllib.load(f)
        
        pyproject_version = pyproject_data['project']['version']
        
        # Compare with info.py version
        assert pyproject_version == info.__version__, (
            f"Version mismatch: pyproject.toml has '{pyproject_version}', "
            f"but info.py has '{info.__version__}'"
        )


if __name__ == '__main__':
    pytest.main([__file__, "-v"])