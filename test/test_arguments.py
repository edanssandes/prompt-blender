import unittest
from prompt_blender.arguments import _get_data_from_file, _get_data_from_spreadsheet, _get_data_from_directory, _get_data_from_module
from unittest.mock import patch
from unittest.mock import mock_open
import pandas as pd


class GetDataFromFileTestCase(unittest.TestCase):

    def test_get_data_from_file(self):
        argument_file = "/path/to/argument_file.txt"
        expected_data = [{'argument_file': 'data1'}, {'argument_file': 'data2'}, {'argument_file': 'data3'}]

        # Mock the file
        with patch('builtins.open', mock_open(read_data="data1\ndata2\ndata3\n")) as mock_file:
            result = _get_data_from_file(argument_file)
            self.assertEqual(result, expected_data)





class GetDataFromSpreedsheetTestCase(unittest.TestCase):
    expected_data = [{'column1': 'data1', 'column2': 'data2'}, {'column1': 'data3', 'column2': 'data4'}]
    df = pd.DataFrame({'column1': ['data1', 'data3'], 'column2': ['data2', 'data4']})

    def test_get_data_from_spreedsheet_xlsx(self):
        argument_file = "/path/to/argument_file.xlsx"

        # Mock the pd.read_excel function
        with patch('pandas.read_excel') as mock_read_excel:
            mock_read_excel.return_value = GetDataFromSpreedsheetTestCase.df
            result = _get_data_from_spreadsheet(argument_file)
            self.assertEqual(result, GetDataFromSpreedsheetTestCase.expected_data)

    def test_get_data_from_spreedsheet_csv(self):
        argument_file = "/path/to/argument_file.csv"
        expected_data = [{'column1': 'data1', 'column2': 'data2'}, {'column1': 'data3', 'column2': 'data4'}]

        # Mock the pd.read_csv function
        with patch('pandas.read_csv') as mock_read_csv:
            mock_read_csv.return_value = GetDataFromSpreedsheetTestCase.df
            result = _get_data_from_spreadsheet(argument_file)
            self.assertEqual(result, GetDataFromSpreedsheetTestCase.expected_data)

class GetDataFromDirectoryTestCase(unittest.TestCase):

    def test_get_data_from_directory(self):
        argument_file = "/path/to/argument_directory"
        expected_data = [
            {'_id': 'file1.txt', 'argument_directory': 'line1\nline2'},
            {'_id': 'file2.txt', 'argument_directory': 'line3\nline4'},
            {'_id': 'file3.txt', 'argument_directory': 'line5'}
        ]

        # Mock the os.listdir and Path.read_text functions
        with patch('os.listdir') as mock_listdir, patch('pathlib.Path.read_text') as mock_read_text:
            mock_listdir.return_value = ['file1.txt', 'file2.txt', 'file3.txt']
            mock_read_text.side_effect = ['line1\nline2', 'line3\nline4', 'line5']
            result = _get_data_from_directory(argument_file)
            self.assertEqual(result, expected_data)

class GetDataFromModuleTestCase(unittest.TestCase):

    def test_get_data_from_module(self):
            argument_file = "/path/to/argument_file.py"
            expected_data = [{'argument_file': 'data1'}, {'argument_file': 'data2'}, {'argument_file': 'data3'}]

            # Mock the importlib functions
            with patch('importlib.util.spec_from_file_location'), \
                patch('importlib.util.module_from_spec') as mock_module_from_spec:
                mock_module = mock_module_from_spec.return_value
                mock_module.generate.return_value = ['data1', 'data2', 'data3']

                result = _get_data_from_module(argument_file)
                self.assertEqual(result, expected_data)


    
if __name__ == '__main__':
    unittest.main()