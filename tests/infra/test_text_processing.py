import pytest
from utils.text_processing import clean_sec_text, chunk_text, parse_10k_sections, parse_proxy_sections

def test_clean_sec_text():
    raw_html = "<html><body>  <p>Hello <b>World</b></p> <a name='page1'>Page 14</a> \n<p>More text</p> </body></html>"
    clean = clean_sec_text(raw_html)
    assert clean == "Hello World More text"

def test_chunk_text():
    words = [f"word{i}" for i in range(100)]
    text = " ".join(words)
    # chunk size 40, overlap 10
    chunks = chunk_text(text, chunk_size=40, overlap=10)
    assert len(chunks) == 3
    assert len(chunks[0].split()) == 40
    assert len(chunks[1].split()) == 40
    # chunk 0: 0 to 40
    # chunk 1: 30 to 70
    # chunk 2: 60 to 100
    assert chunks[1].startswith("word30")
    assert chunks[2].startswith("word60")
    assert len(chunks[2].split()) == 40

def test_parse_10k_sections_finds_items():
    html = """
    <html><body>
    <div>
    Item 1. Business
    <p>We sell apples.</p>
    Item 1A. Risk Factors
    <p>Apples might rot.</p>
    Item 1B. Unresolved Staff Comments
    </div></body></html>
    """
    sections = parse_10k_sections(html)
    assert "We sell apples." in sections["item_1"]
    assert "Apples might rot." in sections["item_1a"]
    assert "item_3" not in sections or not sections["item_3"]

def test_parse_proxy_sections():
    html = """
    <html><body>
    ELECTION OF DIRECTORS
    <p>John Doe</p>
    BOARD INDEPENDENCE
    <p>All independent</p>
    </body></html>
    """
    sections = parse_proxy_sections(html)
    assert "John Doe" in sections["proxy_directors"]
    assert "All independent" in sections["proxy_directors"]
