import pytest
from prompt_blender.gui.model import Model
import tempfile
import os


class TestPdfConversion:
    """Test suite for PDF text conversion functionality."""

    @staticmethod
    def create_simple_pdf(text_lines=None):
        """Create a simple PDF with the given text lines."""
        # Common PDF structure
        pdf_parts = [
            "%PDF-1.4",
            "1 0 obj\n<< /Type /Catalog /Pages 2 0 R >>\nendobj",
            "2 0 obj\n<< /Type /Pages /Kids [3 0 R] /Count 1 >>\nendobj"
        ]
        
        has_text = text_lines and len(text_lines) > 0
        
        if has_text:
            # Build text commands
            text_commands = []
            for i, line in enumerate(text_lines):
                text_commands.append(f"({line}) Tj")
                if i < len(text_lines) - 1:
                    text_commands.append("0 -20 Td")
            
            content = f"BT /F1 12 Tf 50 750 Td {' '.join(text_commands)} ET"
            
            # Page with content
            pdf_parts.extend([
                "3 0 obj\n<< /Type /Page /Parent 2 0 R /MediaBox [0 0 612 792] /Contents 4 0 R /Resources << /Font << /F1 5 0 R >> >> >>\nendobj",
                f"4 0 obj\n<< /Length {len(content)} >>\nstream\n{content}\nendstream\nendobj",
                "5 0 obj\n<< /Type /Font /Subtype /Type1 /BaseFont /Helvetica >>\nendobj"
            ])
            
        else:
            # Empty page
            pdf_parts.append("3 0 obj\n<< /Type /Page /Parent 2 0 R /MediaBox [0 0 612 792] >>\nendobj")
            
            # Cross-reference table
        trailer = """
trailer
<< /Root 1 0 R >>
startxref
0
%%EOF"""
        
        return f"{chr(10).join(pdf_parts)}\n{trailer}".encode('latin-1')

    def _test_pdf_conversion(self, text_lines, expected_texts=None):
        """Helper method to test PDF conversion with given text lines."""
        model = Model({})
        
        with tempfile.NamedTemporaryFile(mode='wb', suffix='.pdf') as temp_file:
            pdf_content = self.create_simple_pdf(text_lines)
            temp_file.write(pdf_content)
            temp_file.flush()
            
            result_text = model.convert_pdf_to_txt(temp_file.name)
            
            assert result_text is not None
            
            for expected in text_lines:
                assert expected in result_text
            
            return result_text

    def test_convert_pdf_to_txt(self):
        """Test converting a simple PDF file to text."""
        result_text = self._test_pdf_conversion(['Hello World!', 'This is a test PDF.'])
        assert len(result_text) > 0

    def test_convert_pdf_to_txt_empty_pdf(self):
        """Test converting a PDF with no text content."""
        result_text = self._test_pdf_conversion([])
        assert len(result_text.strip()) == 0

    def test_convert_pdf_to_txt_multiline(self):
        """Test converting a PDF with multiple lines of text."""
        self._test_pdf_conversion(['Line one', 'Line two', 'Line three'])
            



if __name__ == '__main__':
    pytest.main([__file__, "-v"])