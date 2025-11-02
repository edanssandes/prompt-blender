import pytest
from prompt_blender.gui.model import Model
import pandas as pd
import tempfile
import os
import json



class TestGetDataFromFile:
    """Test suite for loading data from files."""

    def test_add_table_from_file_txt(self):
        """Test loading data from text file."""
        # Create a model
        model = Model({})
        
        # Create a temporary text file
        with tempfile.NamedTemporaryFile(mode='w', suffix='.txt', delete=True, encoding='utf-8') as temp_file:
            temp_file.write("data1\ndata2\ndata3\n")
            temp_file_path = temp_file.name
            temp_file.flush()
        
            # Load data from file
            model.add_table_from_file(temp_file_path, variable='test_param')
            
            # Get the loaded parameter
            result = model.get_parameter('test_param')
            
            # Expected data format for text files
            expected_data = [
                {'test_param': 'data1'}, 
                {'test_param': 'data2'}, 
                {'test_param': 'data3'}
            ]
            
            assert result == expected_data


class TestGetDataFromSpreadsheet:
    """Test suite for loading data from spreadsheet files."""
    
    @pytest.fixture
    def sample_data(self):
        return [{'column1': 'data1', 'column2': 'data2'}, {'column1': 'data3', 'column2': 'data4'}]
    
    @pytest.fixture
    def sample_df(self):
        return pd.DataFrame({'column1': ['data1', 'data3'], 'column2': ['data2', 'data4']})

    def test_add_table_from_file_xlsx(self, sample_data, sample_df):
        """Test loading data from Excel file."""
        model = Model({})
        
        # Create a temporary Excel file
        with tempfile.NamedTemporaryFile(suffix='.xlsx') as temp_file:
            sample_df.to_excel(temp_file.name, index=False)
            temp_file_path = temp_file.name
        
            # Load data from file
            model.add_table_from_file(temp_file_path, variable='test_param')
            
            # Get the loaded parameter
            result = model.get_parameter('test_param')
            
            assert result == sample_data


    def test_add_table_from_file_csv(self, sample_data, sample_df):
        """Test loading data from CSV file."""
        model = Model({})
        
        # Create a temporary CSV file
        with tempfile.NamedTemporaryFile(mode='w', suffix='.csv') as temp_file:
            sample_df.to_csv(temp_file.name, index=False)
            temp_file_path = temp_file.name
        
            # Load data from file
            model.add_table_from_file(temp_file_path, variable='test_param')
            
            # Get the loaded parameter
            result = model.get_parameter('test_param')
            
            assert result == sample_data

class TestGetDataFromDirectory:
    """Test suite for loading data from directory."""

    def test_add_table_from_directory(self):
        """Test loading data from directory with text files."""
        model = Model({})
        
        # Create a temporary directory with test files
        with tempfile.TemporaryDirectory() as temp_dir:
            # Create test files
            test_files = {
                'file1.txt': 'line1\nline2',
                'file2.txt': 'line3\nline4', 
                'file3.txt': 'line5'
            }
            
            for filename, content in test_files.items():
                file_path = os.path.join(temp_dir, filename)
                with open(file_path, 'w', encoding='utf-8') as f:
                    f.write(content)
            
            # Load data from directory
            model.add_table_from_directory(temp_dir, variable='test_param')
            
            # Get the loaded parameter
            result = model.get_parameter('test_param')
            
            # Expected data format for directory loading
            expected_data = [
                {'_id': 'file1.txt', 'document_text': 'line1\nline2', 'document_size': 11},
                {'_id': 'file2.txt', 'document_text': 'line3\nline4', 'document_size': 11},
                {'_id': 'file3.txt', 'document_text': 'line5', 'document_size': 5}
            ]
            
            # Sort both lists by _id for consistent comparison
            result_sorted = sorted(result, key=lambda x: x['_id'])
            expected_sorted = sorted(expected_data, key=lambda x: x['_id'])
            
            assert result_sorted == expected_sorted

class TestGetDataFromModule:
    """Test suite for loading data from Python modules."""

    def test_add_table_from_file_python_module(self):
        """Test loading data from Python module file."""
        model = Model({})
        
        # Create a temporary Python module file
        with tempfile.NamedTemporaryFile(mode='w', suffix='.py', encoding='utf-8') as temp_file:
            temp_file.write("""
def generate():
    return [
        {'param1': 'data1', 'param2': 'value1'}, 
        {'param1': 'data2', 'param2': 'value2'}, 
        {'param1': 'data3', 'param2': 'value3'}
    ]
""")
            temp_file.flush()
            temp_file_path = temp_file.name
        
            # Load data from Python module
            model.add_table_from_file(temp_file_path, variable='test_param')
            
            # Get the loaded parameter
            result = model.get_parameter('test_param')
            
            expected_data = [
                {'param1': 'data1', 'param2': 'value1'}, 
                {'param1': 'data2', 'param2': 'value2'}, 
                {'param1': 'data3', 'param2': 'value3'}
            ]
            
            assert result == expected_data


    def test_add_table_from_file_json(self):
        """Test loading data from JSON file."""
        model = Model({})
        
        test_data = [
            {'param1': 'data1', 'param2': 'value1'}, 
            {'param1': 'data2', 'param2': 'value2'}, 
            {'param1': 'data3', 'param2': 'value3'}
        ]
        
        # Create a temporary JSON file
        with tempfile.NamedTemporaryFile(mode='w', suffix='.json', encoding='utf-8') as temp_file:
            json.dump(test_data, temp_file)
            temp_file_path = temp_file.name
            temp_file.flush()
        
            # Load data from JSON file
            model.add_table_from_file(temp_file_path, variable='test_param')
            
            # Get the loaded parameter
            result = model.get_parameter('test_param')
            
            assert result == test_data


    def test_parameter_operations(self):
        """Test basic parameter operations."""
        model = Model({})
        
        # Test add_param directly
        test_data = [{'key1': 'value1'}, {'key1': 'value2'}]
        model.add_param('test_param', test_data)
        
        # Test get_parameter
        result = model.get_parameter('test_param')
        assert result == test_data
        
        # Test remove_param
        model.remove_param('test_param')
        result = model.get_parameter('test_param')
        assert result is None

    def test_maximum_rows_limit(self):
        """Test maximum rows limit when loading files."""
        model = Model({})
        
        # Create data that exceeds maximum_rows
        large_data = [{'id': i, 'value': f'data{i}'} for i in range(51)]
        
        # Create a temporary JSON file with too many rows
        with tempfile.NamedTemporaryFile(mode='w', suffix='.json', encoding='utf-8') as temp_file:
            json.dump(large_data, temp_file)
            temp_file_path = temp_file.name
            temp_file.flush()
        
            # Should raise ValueError for exceeding maximum_rows (default 1000)
            with pytest.raises(ValueError, match="more than 50 rows"):
                model.add_table_from_file(temp_file_path, variable='test_param', maximum_rows=50)

            # Test other limits
            with pytest.raises(ValueError, match="more than 30 rows"):
                model.add_table_from_file(temp_file_path, variable='test_param', maximum_rows=30)

            # Test should not raise exception since data is within limits
            model.add_table_from_file(temp_file_path, variable='test_param', maximum_rows=100)
                



if __name__ == '__main__':
    pytest.main([__file__, "-v"])