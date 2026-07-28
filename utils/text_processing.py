"""Package: utils. Purpose: Cross-cutting utilities (audit logging, parsing helpers)."""
# Ye module Ingestion Agent ka sabse important utility helper hai. 
# Iska kaam SEC filings (HTML format) ko saaf karna, padhne layak text banana, 
# aur unko chote tukdo (chunks) mein todna hai taaki AI aasaani se search kar sake.

import re
import logging
from pathlib import Path
from bs4 import BeautifulSoup

logger = logging.getLogger(__name__)

def clean_sec_text(raw_text: str) -> str:
    """Removes residual HTML, fixes irregular whitespace, and strips page numbers."""
    # HTML ko hatakar sirf text (clean text) nikalne ke liye BeautifulSoup ka use hota hai.
    # SEC docs me bohot saare ajeeb characters aur multiple spaces hote hain, isliye Regex se unhe theek kiya jata hai.
    if not raw_text:
        return ""
    # Strip HTML tags
    text = BeautifulSoup(raw_text, "html.parser").get_text(separator=" ")
    # Fix irregular whitespace
    text = re.sub(r'\s+', ' ', text)
    # Remove page numbers like Table of Contents F-14 or just Page 14 (kyuki vector DB mein page number ki zaroorat nahi)
    text = re.sub(r'\b(Page|F-)\s*\d+\b', '', text, flags=re.IGNORECASE)
    # Remove multiple spaces again
    text = re.sub(r'\s+', ' ', text)
    return text.strip()

def chunk_text(text: str, chunk_size: int = 600, overlap: int = 100) -> list[str]:
    """Splits text into semantic chunks for vector storage."""
    # LLMs (AI models) ki ek context limit hoti hai. Hum poori SEC file ek baar mein nahi bhej sakte.
    # Isliye hum usse chhote-chhote parts me break karte hain (chunks).
    # Overlap (eg. 100 words) ka concept isliye hai taki do chunks ke beech ka context cut na ho jaye.
    words = text.split()
    chunks = []
    if not words:
        return chunks
        
    i = 0
    while i < len(words):
        chunk = " ".join(words[i:i + chunk_size])
        chunks.append(chunk)
        
        i += chunk_size - overlap
        if len(words) - i <= overlap and i > 0:
            break
    return chunks

def _find_item_boundaries(text: str, items_to_find: list[str]) -> dict[str, str]:
    """Fallback parser for 10-K sections"""
    # 10-K report me bohot saare Items (headings) hote hain (jaise Item 1A, Item 7).
    # Ye function Regex pattern ka use karke report me se in specific sections ka starting point aur ending point nikalta hai.
    results = {k: "" for k in items_to_find}
    
    ordered = ["item_1", "item_1a", "item_1b", "item_2", "item_3", "item_4", "item_5", 
               "item_6", "item_7", "item_7a", "item_8", "item_9", "item_9a", "item_9b", "item_10"]
    
    positions = {}
    
    # We use regex on the text to find Item headings.
    # To avoid Table of Contents, we pick the LAST match before the next item.
    for item in ordered:
        item_str = item.replace('item_', '').replace('a', 'A').replace('b', 'B')
        # match newline, Item, space, number, optional period/space
        pattern = r'\n\s*Item\s+' + item_str + r'[\.\s\-\:]'
        matches = list(re.finditer(pattern, text, flags=re.IGNORECASE))
        if matches:
            # Skip TOC by picking the last match, which is usually the actual section
            positions[item] = matches[-1].start()

    if not positions:
        return {"full_document": text}

    sorted_items = sorted(positions.items(), key=lambda x: x[1])
    for i, (item, start_pos) in enumerate(sorted_items):
        if item in results:
            end_pos = sorted_items[i+1][1] if i + 1 < len(sorted_items) else len(text)
            results[item] = text[start_pos:end_pos]
            
    # Check if we successfully extracted anything
    if not any(results.values()):
        return {"full_document": text}
        
    return {k: v for k, v in results.items() if v}

def parse_10k_sections(html_content: str) -> dict[str, str]:
    """Parse 10-K sections using fallback strategy."""
    # 10-K se specific financial aur risk related items ko nikalna
    sections_to_keep = ["item_1", "item_1a", "item_3", "item_7", "item_7a", "item_8", "item_9a"]
    soup = BeautifulSoup(html_content, "html.parser")
    text = soup.get_text(separator="\n")
    return _find_item_boundaries(text, sections_to_keep)

def parse_proxy_sections(html_content: str) -> dict[str, str]:
    """Parse DEF 14A for governance sections."""
    # Proxy statement me koi definite Items (like Item 1, 2) nahi hote 10-K ki tarah.
    # Isliye hum "ELECTION OF DIRECTORS" jaise key phrases dhoondte hain.
    soup = BeautifulSoup(html_content, "html.parser")
    text = soup.get_text(separator="\n")
    
    keywords = ["ELECTION OF DIRECTORS", "BOARD INDEPENDENCE", "AUDIT COMMITTEE", "NOMINEES FOR DIRECTOR"]
    extracted = []
    found_any = False
    
    for kw in keywords:
        matches = list(re.finditer(r'\n\s*' + kw, text, flags=re.IGNORECASE))
        if matches:
            found_any = True
            for m in matches:
                # grab up to 15000 chars as a rough heuristic for the section
                extracted.append(text[m.start():m.start()+15000])
                
    if not found_any:
        # Fallback: if no specific governance keywords found, just extract the first 100k characters.
        # This ensures we get general proxy data rather than dropping the filing entirely.
        extracted = [text[:100000]]
        
    return {"proxy_directors": "\n".join(extracted)}

def _find_item_boundaries_10q(text: str, items_to_find: list[str]) -> dict[str, str]:
    # 10-Q (Quarterly report) ki parsing 10-K se alag hoti hai kyunki usme "Part I Item 1" is tarah headings hoti hain.
    results = {k: "" for k in items_to_find}
    patterns = {
        "part1_item1": [r'Part\s+I\s+Item\s+1\b', r'Item\s+1\s+of\s+Part\s+I\b', r'Part\s+1\s+Item\s+1\b'],
        "part1_item2": [r'Part\s+I\s+Item\s+2\b', r'Item\s+2\s+of\s+Part\s+I\b', r'Part\s+1\s+Item\s+2\b'],
        "part1_item3": [r'Part\s+I\s+Item\s+3\b', r'Item\s+3\s+of\s+Part\s+I\b', r'Part\s+1\s+Item\s+3\b'],
        "part1_item4": [r'Part\s+I\s+Item\s+4\b', r'Item\s+4\s+of\s+Part\s+I\b', r'Part\s+1\s+Item\s+4\b'],
        "part2_item1": [r'Part\s+II\s+Item\s+1\b', r'Item\s+1\s+of\s+Part\s+II\b', r'Part\s+2\s+Item\s+1\b'],
        "part2_item1a": [r'Part\s+II\s+Item\s+1A\b', r'Item\s+1A\s+of\s+Part\s+II\b', r'Part\s+2\s+Item\s+1A\b'],
        "part2_item2": [r'Part\s+II\s+Item\s+2\b', r'Item\s+2\s+of\s+Part\s+II\b', r'Part\s+2\s+Item\s+2\b'],
    }
    positions = {}
    ordered_keys = ["part1_item1", "part1_item2", "part1_item3", "part1_item4", "part2_item1", "part2_item1a", "part2_item2"]
    
    for key in ordered_keys:
        for pat in patterns.get(key, []):
            matches = list(re.finditer(pat, text, flags=re.IGNORECASE))
            if matches:
                positions[key] = matches[-1].start()
                break
                
    if not positions:
        return {"full_document": text}
        
    sorted_items = sorted(positions.items(), key=lambda x: x[1])
    for i, (item, start_pos) in enumerate(sorted_items):
        if item in results:
            end_pos = sorted_items[i+1][1] if i + 1 < len(sorted_items) else len(text)
            results[item] = text[start_pos:end_pos]
            
    return {k: v for k, v in results.items() if v}

def parse_10q_sections(html_content: str) -> dict[str, str]:
    """Parse 10-Q sections using fallback strategy."""
    sections_to_keep = ["part1_item1", "part1_item2", "part1_item3", "part2_item1", "part2_item1a"]
    soup = BeautifulSoup(html_content, "html.parser")
    text = soup.get_text(separator="\n")
    return _find_item_boundaries_10q(text, sections_to_keep)

def extract_text_from_file(file_path: Path) -> str:
    """Extract and clean text from a .txt or .pdf file."""
    # Ye user files (jaise PDF ya TXT reports) parse karne ke liye phase 3 mein use hota hai.
    if not file_path.exists():
        raise FileNotFoundError(f"File not found: {file_path}")
        
    ext = file_path.suffix.lower()
    if ext == ".txt":
        text = file_path.read_text(encoding="utf-8", errors="replace")
        return clean_sec_text(text)
        
    elif ext == ".pdf":
        try:
            import fitz  # PyMuPDF
        except ImportError:
            raise ImportError("pymupdf is required for PDF parsing. Please 'pip install pymupdf'.")
            
        text_parts = []
        try:
            with fitz.open(file_path) as doc:
                for page in doc:
                    text_parts.append(page.get_text("text"))
            raw_text = "\n".join(text_parts)
            return clean_sec_text(raw_text)
        except Exception as e:
            logger.error(f"Failed to parse PDF {file_path}: {e}")
            raise ValueError(f"Failed to parse PDF: {e}")
            
    else:
        raise ValueError(f"Unsupported file format '{ext}'. Only .txt and .pdf are supported.")
