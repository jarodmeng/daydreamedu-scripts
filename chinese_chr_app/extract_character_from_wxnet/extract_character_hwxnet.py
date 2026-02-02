#!/usr/bin/env python3
"""
Extract Chinese character information from 汉文学网 (HWXNet).
Based on conversation: https://chatgpt.com/share/696c8d2b-2dc8-8007-84fa-b253e0fc1b13
"""

import re
import ssl
import urllib.request
import urllib.parse
from bs4 import BeautifulSoup
from typing import Dict, List, Any, Optional


def parse_chinese_number(num_str: str) -> int:
    """
    Parse Chinese number string to integer.
    Supports numbers from 1 to 99.
    
    Examples:
        "一" -> 1
        "十" -> 10
        "十一" -> 11
        "十九" -> 19
        "二十" -> 20
        "二十一" -> 21
    """
    if not num_str:
        return 0
    
    # Single digit characters
    digits = {'一': 1, '二': 2, '三': 3, '四': 4, '五': 5, 
              '六': 6, '七': 7, '八': 8, '九': 9}
    
    # Handle "十" (10) and multiples
    if num_str == '十':
        return 10
    
    # Handle numbers like "十一" (11), "十二" (12), ..., "十九" (19)
    if num_str.startswith('十'):
        if len(num_str) == 1:
            return 10
        elif len(num_str) == 2:
            # "十一" to "十九"
            ones = digits.get(num_str[1], 0)
            return 10 + ones
    
    # Handle numbers like "二十" (20), "二十一" (21), ..., "二十九" (29)
    if num_str.startswith('二') and '十' in num_str:
        if num_str == '二十':
            return 20
        elif len(num_str) == 3 and num_str[1] == '十':
            # "二十一" to "二十九"
            ones = digits.get(num_str[2], 0)
            return 20 + ones
    
    # Handle numbers like "三十" (30), etc. (for future expansion)
    if '十' in num_str:
        # Try to parse tens and ones
        tens_pos = num_str.find('十')
        if tens_pos == 0:
            # "十X" format (11-19)
            if len(num_str) > 1:
                ones = digits.get(num_str[1], 0)
                return 10 + ones
            return 10
        elif tens_pos == 1:
            # "X十" or "X十Y" format (20-99)
            tens = digits.get(num_str[0], 0)
            if len(num_str) == 2:
                # "X十" format (20, 30, ..., 90)
                return tens * 10
            elif len(num_str) == 3:
                # "X十Y" format (21-29, 31-39, ..., 91-99)
                ones = digits.get(num_str[2], 0)
                return tens * 10 + ones
    
    # Fallback: try direct lookup for single digits
    return digits.get(num_str, 0)


def _normalize_pinyin_syllable(p: str) -> str:
    """
    Normalize a single pinyin syllable for storage/display.

    - Convert breve vowels (ă ĕ ĭ ŏ ŭ) to the standard 3rd‑tone caron forms (ǎ ě ǐ ǒ ǔ).
    - Lowercase everything.

    This keeps our JSON/DB pinyin consistent (e.g. 'huĭ' -> 'huǐ').
    """
    if not p:
        return p
    mapping = str.maketrans({
        "ă": "ǎ",
        "ĕ": "ě",
        "ĭ": "ǐ",
        "ŏ": "ǒ",
        "ŭ": "ǔ",
    })
    return p.translate(mapping).lower()


def _normalize_pinyin_list(pinyin_list: List[str]) -> List[str]:
    """Normalize and deduplicate a list of pinyin strings."""
    if not pinyin_list:
        return []
    seen = set()
    out: List[str] = []
    for raw in pinyin_list:
        if not isinstance(raw, str):
            continue
        norm = _normalize_pinyin_syllable(raw.strip())
        if not norm:
            continue
        if norm not in seen:
            seen.add(norm)
            out.append(norm)
    return out


def extract_character_info(character: str) -> Dict[str, Any]:
    """
    Extract character information from HWXNet.
    
    Args:
        character: A single simplified Chinese character
        
    Returns:
        Dictionary containing character information in JSON format
    """
    # Use original keyword URL (not resolved URL)
    base_url = "https://zd.hwxnet.com/search.do"
    source_url = f"{base_url}?keyword={urllib.parse.quote(character)}"
    
    # Create SSL context that doesn't verify certificates
    ssl_context = ssl.create_default_context()
    ssl_context.check_hostname = False
    ssl_context.verify_mode = ssl.CERT_NONE
    
    # Fetch the page
    try:
        req = urllib.request.Request(source_url)
        req.add_header('User-Agent', 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36')
        with urllib.request.urlopen(req, context=ssl_context, timeout=30) as response:
            html_content = response.read().decode('utf-8')
    except Exception as e:
        raise Exception(f"Failed to fetch page: {e}")
    
    # Parse HTML with BeautifulSoup
    soup = BeautifulSoup(html_content, 'lxml')
    
    result = {
        "character": character,
        "source_url": source_url,
        "分类": [],
        "拼音": [],
        "部首": "",
        "总笔画": 0,
        "基本字义解释": [],
        "英文翻译": []
    }
    
    # Extract 分类 (category) using DOM structure - avoid expensive get_text() on entire page
    # Find div with class="introduce" first to limit search scope
    introduce_div = soup.find('div', class_='introduce')
    
    # Extract 分类 (category) using DOM structure
    if introduce_div:
        # Search only within introduce div for better performance
        for text_node in introduce_div.find_all(string=re.compile(r'分类')):
            parent = text_node.parent
            if parent:
                text = parent.get_text()
                # Look for pattern like "分类：通用字、次常用字" or "分类：通用字，常用字"
                match = re.search(r'分类[：:]\s*([^。\n]+)', text)
                if match:
                    fenlei_text = match.group(1)
                    fenlei_matches = re.findall(r'(通用字|常用字|次常用字)', fenlei_text)
                    if fenlei_matches:
                        result["分类"] = list(set(fenlei_matches))
                        break
    
    # Fallback: search in introduce div text if not found
    if not result["分类"] and introduce_div:
        introduce_text = introduce_div.get_text()
        fenlei_matches = re.findall(r'(通用字|常用字|次常用字)', introduce_text)
        if fenlei_matches:
            result["分类"] = list(set(fenlei_matches))
    
    # Extract 拼音 (pinyin) using DOM structure
    # Strategy: Find div with class="introduce", then find div with "拼音：" text,
    # then find all <span class="pinyin"> elements that are siblings after "拼音："
    # This is more accurate than text searching and naturally avoids "Image" tokens
    
    # First, find the div with class="introduce"
    introduce_div = soup.find('div', class_='introduce')
    
    if introduce_div:
        # Find the div containing "拼音：" within the introduce div
        pinyin_label_div = None
        for div in introduce_div.find_all('div'):
            div_text = div.get_text()
            if '拼音' in div_text and ('：' in div_text or ':' in div_text):
                pinyin_label_div = div
                break
        
        if pinyin_label_div:
            # Find all <span class="pinyin"> elements that are siblings of the "拼音：" div
            # The spans are siblings within the same parent (div.label or similar)
            pinyin_spans = []
            
            # Get the parent of the "拼音：" div (likely div.label)
            parent = pinyin_label_div.parent
            if parent:
                # Find all span.pinyin elements within the parent
                # Since the label div and span are siblings in the same parent,
                # any pinyin span in the parent is valid
                all_spans = parent.find_all('span', class_='pinyin')
                
                # Try to filter by position if possible
                for span in all_spans:
                    # Check if this span comes after the pinyin_label_div
                    # by checking if pinyin_label_div appears before span in the parent's children
                    try:
                        # Get all direct children (tags only, not text nodes)
                        parent_children = [child for child in parent.children if hasattr(child, 'name')]
                        label_idx = parent_children.index(pinyin_label_div)
                        span_idx = parent_children.index(span)
                        if span_idx > label_idx:
                            pinyin_spans.append(span)
                        elif span_idx == label_idx:
                            # Same position shouldn't happen, but include it
                            pinyin_spans.append(span)
                    except (ValueError, AttributeError):
                        # If we can't determine order, include it anyway
                        # This handles cases where span is not a direct child
                        pinyin_spans.append(span)
            
            # If we didn't find spans by position, just get all spans in the parent
            # This is a fallback for cases where the structure is different
            if not pinyin_spans and parent:
                pinyin_spans = parent.find_all('span', class_='pinyin')
    else:
        # Fallback: try the old approach
        pinyin_label_div = None
        for div in soup.find_all('div'):
            div_text = div.get_text()
            if '拼音' in div_text and ('：' in div_text or ':' in div_text):
                pinyin_label_div = div
                break
        
        pinyin_spans = []
        if pinyin_label_div:
            parent = pinyin_label_div.parent
            if parent:
                pinyin_spans = parent.find_all('span', class_='pinyin')
        
    # Extract pinyin text from the spans
    if pinyin_spans:
        pinyin_list: List[str] = []
        for span in pinyin_spans:
            # Get the text content of the span (this excludes the img tag)
            pinyin_text = span.get_text(strip=True)
            # Clean up any remaining whitespace or special characters
            pinyin_text = pinyin_text.strip()
            
            # Clean up pinyin: remove zhuyin (ㄌㄧㄤˊ), semicolons, and other non-pinyin characters
            # Keep only pinyin with tone marks or basic latin letters
            # Note: Keep numbers 1-5 at the end (used for tone marks in some cases like "ng4")
            pinyin_clean = re.sub(r'[ㄅ-ㄩˊˇˋ˙；;，,。.]', '', pinyin_text)
            pinyin_clean = pinyin_clean.strip()
            # If it doesn't end with a number 1-5, remove any remaining numbers
            if not re.search(r'[1-5]$', pinyin_clean):
                pinyin_clean = re.sub(r'[0-9]', '', pinyin_clean)
            
            # Extract just the pinyin part (before any semicolons or extra characters)
            if ';' in pinyin_clean:
                # Take the first part before semicolon
                pinyin_clean = pinyin_clean.split(';')[0].strip()
            
            # Validate it looks like pinyin (contains only letters + tone marks, optional trailing 1-5)
            # and has at least one vowel (to exclude things like \"r2\", \"hng5\").
            if pinyin_clean and (
                re.match(r'^[a-zāáǎàăēéěèĕīíǐìĭōóǒòŏūúǔùŭǖǘǚǜü]+$', pinyin_clean, re.IGNORECASE)
                or re.match(r'^[a-zāáǎàăēéěèĕīíǐìĭōóǒòŏūúǔùŭǖǘǚǜü]+[1-5]$', pinyin_clean, re.IGNORECASE)
            ):
                # Require at least one vowel (with or without tone mark).
                if not re.search(r'[aeiouāáǎàăēéěèĕīíǐìĭōóǒòŏūúǔùŭǖǘǚǜü]', pinyin_clean, re.IGNORECASE):
                    continue
                # Filter out compound words:
                # 1. Longer than 6 characters
                # 2. Has multiple tone marks (indicating multiple syllables)
                # Note: includes ă/ĕ/ŏ/ĭ/ŭ (a/e/o/i/u with breve) which some sites use instead of ǎ/ě/ǒ/ǐ/ǔ (caron)
                # Note: ü is a vowel variant, not a tone mark, so exclude it from tone counting
                tone_marks = 'āáǎàăēéěèĕīíǐìĭōóǒòŏūúǔùŭǖǘǚǜ'  # Removed ü - it's a vowel, not a tone mark
                tone_count = sum(1 for c in pinyin_clean if c in tone_marks)
                # Also count numbers 1-5 as tone marks
                if re.search(r'[1-5]$', pinyin_clean):
                    tone_count += 1
                
                if len(pinyin_clean) <= 6 and tone_count <= 1:
                    pinyin_list.append(pinyin_clean)
        
        if pinyin_list:
            # Normalize for storage/display (e.g. huĭ -> huǐ) and dedupe.
            result["拼音"] = _normalize_pinyin_list(pinyin_list)
    
    # Extract 部首 (radical) using DOM structure
    # Strategy: Find div with class="introduce", then find div with "部首：" text,
    # then extract the radical character from nearby elements (similar to pinyin extraction)
    
    introduce_div = soup.find('div', class_='introduce')
    
    if introduce_div:
        # Find the div containing "部首：" within the introduce div
        bushou_label_div = None
        for div in introduce_div.find_all('div'):
            div_text = div.get_text()
            if '部首' in div_text and ('：' in div_text or ':' in div_text):
                bushou_label_div = div
                break
        
        if bushou_label_div:
            # Get the parent container (likely div.label similar to pinyin structure)
            parent = bushou_label_div.parent
            if parent:
                # Get all text from the parent and extract radical after "部首："
                parent_text = parent.get_text()
                bushou_match = re.search(r'部首[：:]\s*([^\s\n，,。.]+)', parent_text)
                if bushou_match:
                    radical_text = bushou_match.group(1).strip()
                    # Extract the first Chinese character (radical is typically a single character)
                    radical_chars = re.findall(r'[\u4e00-\u9fff]', radical_text)
                    if radical_chars:
                        result["部首"] = radical_chars[0]
                    else:
                        # Some radicals might be special characters, try to get first non-whitespace char
                        radical_clean = radical_text.strip()
                        if radical_clean:
                            result["部首"] = radical_clean[0]
    
    # Fallback: use regex on introduce_div text if DOM approach didn't work
    if not result["部首"] and introduce_div:
        introduce_text = introduce_div.get_text()
        bushou_match = re.search(r'部首[：:]\s*([^\s\n，,。.]+)', introduce_text)
        if bushou_match:
            radical = bushou_match.group(1).strip()
            # Extract just the first Chinese character
            radical_chars = re.findall(r'[\u4e00-\u9fff]', radical)
            if radical_chars:
                result["部首"] = radical_chars[0]
            else:
                # Some radicals might be special characters
                if radical:
                    result["部首"] = radical[0]
    
    # Extract 总笔画 (total strokes) using DOM structure
    if introduce_div:
        introduce_text = introduce_div.get_text()
        zongbihua_match = re.search(r'总笔画[：:]\s*(\d+|[一二三四五六七八九十]+[画劃]?)', introduce_text)
        if zongbihua_match:
            num_str = zongbihua_match.group(1)
            # Remove "画" or "劃" if present
            num_str = re.sub(r'[画劃]', '', num_str)
            if num_str.isdigit():
                result["总笔画"] = int(num_str)
            else:
                result["总笔画"] = parse_chinese_number(num_str)
    
    # 
    #     # Extract 基本字义解释 (basic meaning/explanation) using DOM structure
    # Structure: <h1>基本字义解释</h1> followed by <div class="con_basic">
    # Within con_basic: "● " = top level (pronunciation), "◎ " = 2nd level (meaning)
    # Each bullet: explanation and example words separated by "："
    result["基本字义解释"] = extract_meanings(soup)
    # 
    #     # Extract 英文翻译 (English translation) using DOM structure
    # The translation is in a div with class="con_english"
    con_english_div = soup.find('div', class_='con_english')
    
    if con_english_div:
        # Get the text content from the con_english div
        english_text = con_english_div.get_text().strip()
        
        # Extract English words (sequences of letters)
        english_words = re.findall(r'\b[a-z]+\b', english_text, re.IGNORECASE)
        
        # Filter out common non-translation words
        filtered = [w for w in english_words 
                   if w.lower() not in ['english', 'translation', 'trans', 'image', 'summary', 'var', 'title', 'n', 'the', 'and', 'or', 'is', 'are', 'was', 'were', 'be', 'been', 'have', 'has', 'had', 'do', 'does', 'did', 'will', 'would', 'can', 'could', 'should', 'may', 'might', 'must', 'to', 'of', 'in', 'on', 'at', 'for', 'with', 'from', 'by', 'as', 'an', 'a']]
        
        if filtered:
            result["英文翻译"] = list(set([w.lower() for w in filtered]))
    
    return result


def extract_meanings(soup: BeautifulSoup) -> List[Dict[str, Any]]:
    """
    Extract meanings and pronunciations from HTML content using DOM structure.
    
    Structure:
    - <h1>基本字义解释</h1> header
    - <div class="con_basic"> contains the content
    - "● " = top level segment (corresponds to a pronunciation)
    - "◎ " = 2nd level segment (each bullet is one meaning)
    - In each bullet: explanation (解释) and example words (例词) separated by "："
    
    Returns list of meaning entries with structure:
    [
        {
            "读音": "...",
            "释义": [
                {
                    "解释": "...",
                    "例词": [...]
                }
            ]
        }
    ]
    """
    meanings = []
    
    # Find the h1 with "基本字义解释"
    h1 = soup.find('h1', string=re.compile(r'基本字义解释'))
    
    if h1:
        # Find the next div with class="con_basic"
        con_basic_div = None
        
        # Look for the div after the h1
        for sibling in h1.next_siblings:
            if hasattr(sibling, 'get') and sibling.get('class') and 'con_basic' in sibling.get('class'):
                con_basic_div = sibling
                break
        
        # If not found as sibling, try finding it anywhere after h1
        if not con_basic_div:
            con_basic_div = soup.find('div', class_='con_basic')
        
        if con_basic_div:
            # Get the text content
            content_text = con_basic_div.get_text()
            
            # Split by "● " to get top-level segments (pronunciations)
            segments = content_text.split('● ')
            
            for segment in segments[1:]:  # Skip first empty segment before first "● "
                segment = segment.strip()
                if not segment:
                    continue
                
                # Extract pronunciation from the segment
                # The pronunciation is typically at the start, before the first meaning marker ("⊙ " or "◎ ")
                # Find the first occurrence of either marker to separate pronunciation from meanings
                first_marker_pos = len(segment)
                for marker in ['⊙ ', '◎ ']:
                    pos = segment.find(marker)
                    if pos != -1 and pos < first_marker_pos:
                        first_marker_pos = pos
                
                pronunciation_line = segment[:first_marker_pos].strip()
                meanings_text = segment[first_marker_pos:].strip()
                
                # Try to find pinyin in the pronunciation line
                # Look for pattern like "读音: xxx" or just pinyin
                # Note: includes ă/ĕ/ŏ/ĭ/ŭ (a/e/o/i/u with breve) which some sites use instead of ǎ/ě/ǒ/ǐ/ǔ (caron)
                pronunciation = None
                pinyin_match = re.search(r'读音[：:]\s*([a-zāáǎàăēéěèĕīíǐìĭōóǒòŏūúǔùŭǖǘǚǜü]+)', pronunciation_line, re.IGNORECASE)
                if pinyin_match:
                    pronunciation = pinyin_match.group(1).lower()
                else:
                    # Try to extract pinyin directly - look for valid pinyin with tone marks first
                    # Note: includes ă/ĕ/ŏ/ĭ/ŭ (a/e/o/i/u with breve) which some sites use instead of ǎ/ě/ǒ/ǐ/ǔ (caron)
                    tone_marks = 'āáǎàăēéěèĕīíǐìĭōóǒòŏūúǔùŭǖǘǚǜü'
                    # First try to find pinyin with tone marks
                    pinyin_with_tone = re.findall(r'[a-zāáǎàăēéěèĕīíǐìĭōóǒòŏūúǔùŭǖǘǚǜü]+', pronunciation_line, re.IGNORECASE)
                    for p in pinyin_with_tone:
                        p_lower = p.lower()
                        has_tone = any(c in tone_marks for c in p)
                        # Prioritize pinyin with tone marks, 1-6 chars
                        if has_tone and 1 <= len(p) <= 6:
                            pronunciation = p_lower
                            break
                    
                    # If no tone-marked pinyin found, try short pinyin without tone
                    if not pronunciation:
                        for p in pinyin_with_tone:
                            p_lower = p.lower()
                            # Short pinyin without tone (1-4 chars)
                            if not any(c in tone_marks for c in p) and 1 <= len(p) <= 4:
                                # Filter out common English words
                                if p_lower not in ['a', 'an', 'the', 'is', 'are', 'was', 'were', 'be', 'to', 'of', 'in', 'on', 'at']:
                                    pronunciation = p_lower
                                    break
                
                if not pronunciation:
                    continue

                # Normalize pronunciation pinyin for storage/display as well
                pronunciation = _normalize_pinyin_syllable(pronunciation)
                
                # Extract meanings (2nd level segments marked with "◎ " or "⊙ ")
                shiyi_list = []
                # Split by both "◎ " and "⊙ " markers - treat them the same way
                # Use regex to split by either marker
                meaning_bullets = re.split(r'[◎⊙]\s+', meanings_text)
                
                for bullet in meaning_bullets[1:]:  # Skip first part (pronunciation line)
                    bullet = bullet.strip()
                    if not bullet:
                        continue
                    
                    # Split by "：" to separate explanation and example words
                    if '：' in bullet:
                        parts = bullet.split('：', 1)
                        explanation = parts[0].strip()
                        example_words_text = parts[1].strip() if len(parts) > 1 else ""
                    elif ':' in bullet:
                        parts = bullet.split(':', 1)
                        explanation = parts[0].strip()
                        example_words_text = parts[1].strip() if len(parts) > 1 else ""
                    else:
                        # No separator, treat entire bullet as explanation
                        explanation = bullet
                        example_words_text = ""
                    
                    # Extract example words (split by "。" which separates entries)
                    example_words = []
                    if example_words_text:
                        # Split by "。" (Chinese period) which separates entries
                        entries = example_words_text.split('。')
                        for entry in entries:
                            entry = entry.strip()
                            if not entry:
                                continue
                            
                            # Remove parenthetical explanations (e.g., "和合 (a.和谐 - harmony; b.古代神话...)")
                            # Keep only the main word/phrase before the parenthesis
                            if '（' in entry or '(' in entry:
                                # Find the first parenthesis and take text before it
                                paren_pos = len(entry)
                                for paren in ['（', '(']:
                                    pos = entry.find(paren)
                                    if pos != -1 and pos < paren_pos:
                                        paren_pos = pos
                                entry = entry[:paren_pos].strip()
                            
                            # Extract Chinese words/phrases from the entry
                            # Look for sequences of Chinese characters (at least 2 chars)
                            chinese_words = re.findall(r'[\u4e00-\u9fff]{2,}', entry)
                            for word in chinese_words:
                                word = word.strip()
                                if word and word not in example_words:
                                    example_words.append(word)
                    
                    if explanation:
                        shiyi_list.append({
                            "解释": explanation,
                            "例词": example_words
                        })
                
                if shiyi_list:
                    meanings.append({
                        "读音": pronunciation,
                        "释义": shiyi_list
                    })
    
    return meanings
