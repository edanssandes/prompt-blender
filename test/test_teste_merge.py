import unittest
import prompt_blender
from prompt_blender import blend
from pathlib import Path
from unittest.mock import patch
import itertools


class MergeTestCase(unittest.TestCase):

    def test_generate_prompt(self):
        input_list = {
            'id0': {0:1, 1:2, 2:3},
            'id1': {0:4, 1:5}
        }
        prompt = "Enter a number: {id0}+{id1}"
        expected_prompts = [(['0000', '0000'], {'id0': 1, 'id1': 4}, 'Enter a number: 1+4'),
                            (['0000', '0001'], {'id0': 1, 'id1': 5}, 'Enter a number: 1+5'),
                            (['0001', '0000'], {'id0': 2, 'id1': 4}, 'Enter a number: 2+4'),
                            (['0001', '0001'], {'id0': 2, 'id1': 5}, 'Enter a number: 2+5'),
                            (['0002', '0000'], {'id0': 3, 'id1': 4}, 'Enter a number: 3+4'),
                            (['0002', '0001'], {'id0': 3, 'id1': 5}, 'Enter a number: 3+5')]
        with patch('prompt_blender.blend._get_argument_values') as mock_blend:
            mock_blend.side_effect = input_list
            generated_prompts = list(blend.generate_argument_combinations(input_list))

        self.assertEqual(generated_prompts, expected_prompts)

    def test_process_arguments_file(self):
        input_list = {
            'id0': [1, 2, 3],
            'id1': [Path('teste', '4.txt'), Path('teste', '5.txt')]
        }
        prompt = "Enter a number: {id0}+{id1}"
        expected_prompts = [(['0000', '4.txt'], {'id0': 1, 'id1': '4.txt'}, 'Enter a number: 1+Teste4'),
                            (['0000', '5.txt'], {'id0': 1, 'id1': '5.txt'}, 'Enter a number: 1+Teste5'),
                            (['0001', '4.txt'], {'id0': 2, 'id1': '4.txt'}, 'Enter a number: 2+Teste4'),
                            (['0001', '5.txt'], {'id0': 2, 'id1': '5.txt'}, 'Enter a number: 2+Teste5'),
                            (['0002', '4.txt'], {'id0': 3, 'id1': '4.txt'}, 'Enter a number: 3+Teste4'),
                            (['0002', '5.txt'], {'id0': 3, 'id1': '5.txt'}, 'Enter a number: 3+Teste5')]

        with patch('pathlib.Path.read_text') as mock_path:
            mock_path.side_effect = itertools.cycle(['Teste4', 'Teste5'])
            with patch('prompt_blender.blend._get_argument_values') as mock_blend:
                mock_path.side_effect = input_list
                generated_prompts = list(
                    blend.generate_argument_combinations(input_list))
                print(generated_prompts)
        self.assertEqual(generated_prompts, expected_prompts)


if __name__ == '__main__':
    unittest.main()
