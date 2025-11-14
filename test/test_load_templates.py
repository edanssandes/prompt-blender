import pytest
import os
from prompt_blender.gui.MainMenu import MainMenu
from prompt_blender.model import Model


def test_load_templates():
    """Test various aspects of load_templates function."""
    templates = MainMenu.load_templates()
    
    assert isinstance(templates, list), "load_templates should return a list"
    assert len(templates) > 1, "Should load more than one template"
    assert templates == sorted(templates), "Templates should be returned in sorted order"


def test_load_templates_validity():
    """Test that each loaded template is valid and can be loaded as a model."""
    templates = MainMenu.load_templates()
    
    for template in templates:
        assert os.path.isfile(template), f"Template file does not exist: {template}"
        assert template.endswith('.pbp'), f"Template file does not have .pbp extension: {template}"
        try:
            # Carregue o modelo para verificar se é válido
            model = Model.create_from_example(template)
            assert model is not None, f"Failed to load model from template: {template}"
        except Exception as e:
            pytest.fail(f"Error loading template {template}: {str(e)}")
    
