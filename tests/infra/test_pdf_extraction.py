import pytest
from pathlib import Path
from utils.text_processing import extract_text_from_file

def test_extract_text_from_txt(tmp_path):
    txt_file = tmp_path / "test.txt"
    txt_file.write_text("Hello, this is a plain text file. Page 1", encoding="utf-8")
    
    text = extract_text_from_file(txt_file)
    assert "Hello, this is a plain text file." in text
    assert "Page 1" not in text  # Cleaned by clean_sec_text

def test_extract_text_invalid_extension(tmp_path):
    csv_file = tmp_path / "test.csv"
    csv_file.write_text("a,b,c")
    
    with pytest.raises(ValueError, match="Unsupported file format"):
        extract_text_from_file(csv_file)
