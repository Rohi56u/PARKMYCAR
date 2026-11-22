"""
Slot-aware DIN 1451 character disambiguator.
Exploits alternating slot Markov property of Indian license plate structures.
"""
import re
from typing import Optional, Tuple
from anpr_service.validator.constants import (
    VALID_STATE_CODES,
    DIGIT_TO_ALPHA_MAP,
    ALPHA_TO_DIGIT_MAP,
)


def clean_ocr_text(text: Optional[str]) -> str:
    """Strip whitespace, non-alphanumeric noise, and HSRP 'IND' badge prefixes."""
    if not text or not isinstance(text, str):
        return ""
    cleaned = re.sub(r"[^A-Za-z0-9]", "", text).upper()
    if cleaned.startswith("IND") and len(cleaned) > 5:
        sub = cleaned[3:]
        # Verify if stripping 'IND' yields a valid state or 2-digit BH year
        if sub[:2] in VALID_STATE_CODES or (sub[:2].isdigit() and "BH" in sub):
            cleaned = sub
    elif cleaned.startswith("1ND") and len(cleaned) > 5:
        sub = cleaned[3:]
        if sub[:2] in VALID_STATE_CODES or (sub[:2].isdigit() and "BH" in sub):
            cleaned = sub
    return cleaned


def map_char_to_alpha(c: str) -> Tuple[str, bool]:
    """Maps a character to its alpha counterpart in DIN 1451."""
    if c in DIGIT_TO_ALPHA_MAP:
        return DIGIT_TO_ALPHA_MAP[c], True
    return c, False


def map_char_to_digit(c: str) -> Tuple[str, bool]:
    """Maps a character to its numeric counterpart in DIN 1451."""
    if c in ALPHA_TO_DIGIT_MAP:
        return ALPHA_TO_DIGIT_MAP[c], True
    return c, False


def disambiguate_standard_hsrp(text: str) -> Optional[Tuple[str, int]]:
    """
    Disambiguate standard HSRP plate: [State 2A][RTO 1-2D][Series 0-3A][Num 4D].
    Returns (normalized_plate, substitutions_applied) or None.
    """
    cleaned = clean_ocr_text(text)
    if len(cleaned) < 8 or len(cleaned) > 11:
        return None

    subs = 0

    # 1. Vehicle Number: Last 4 characters MUST be digits, and cannot be 0000
    num_chars = []
    for c in cleaned[-4:]:
        mapped, did_sub = map_char_to_digit(c)
        if not mapped.isdigit():
            return None
        num_chars.append(mapped)
        subs += int(did_sub)
    num_part = "".join(num_chars)
    if num_part == "0000":
        return None

    # 2. State Code: First 2 characters MUST be letters
    if cleaned[:2] == "00":
        return None

    s0, sub0 = map_char_to_alpha(cleaned[0])
    s1, sub1 = map_char_to_alpha(cleaned[1])
    state_candidate = s0 + s1
    subs += int(sub0) + int(sub1)

    # Special handling: DIN 1451 '0' in state prefix can be 'D' (e.g. DL, DD, DN)
    # But do not convert '00' to synthetic invalid combinations
    if state_candidate not in VALID_STATE_CODES:
        if cleaned[0] == "0" and ("D" + s1) in VALID_STATE_CODES:
            state_candidate = "D" + s1
            subs += 1
        elif cleaned[1] == "0" and (s0 + "D") in VALID_STATE_CODES and s0 != "O":
            state_candidate = s0 + "D"
            subs += 1

    if state_candidate not in VALID_STATE_CODES:
        if cleaned[:2] in VALID_STATE_CODES:
            state_candidate = cleaned[:2]
        else:
            return None

    # 3. Middle characters: RTO (1-2 digits) + Series (0-3 letters)
    middle = cleaned[2:-4]
    m_len = len(middle)

    # Length 10: 2 digits RTO + 2 letters Series (e.g. DL01AB1234)
    if m_len == 4:
        rto_chars = []
        for c in middle[:2]:
            m, s = map_char_to_digit(c)
            if not m.isdigit():
                return None
            rto_chars.append(m)
            subs += int(s)
        rto_str = "".join(rto_chars)
        if rto_str == "00":
            return None

        ser_chars = []
        for c in middle[2:]:
            m, s = map_char_to_alpha(c)
            if not m.isalpha():
                return None
            ser_chars.append(m)
            subs += int(s)

        return state_candidate + rto_str + "".join(ser_chars) + num_part, subs

    # Length 9: Either 2 digits RTO + 1 letter Series OR 1 digit RTO + 2 letters Series
    elif m_len == 3:
        # Check 0-substitution matches first!
        # Case A: 2 digits + 1 letter (e.g. KA05M5678)
        if middle[0].isdigit() and middle[1].isdigit() and middle[2].isalpha():
            if middle[:2] != "00":
                return state_candidate + middle + num_part, subs

        # Case B: 1 digit + 2 letters (e.g. DL1AB1234)
        if middle[0].isdigit() and middle[1].isalpha() and middle[2].isalpha():
            if middle[0] != "0":
                return state_candidate + middle + num_part, subs

        # Disambiguate with minimal substitutions
        cand_a = None
        subs_a = 999
        r0_a, s0_a = map_char_to_digit(middle[0])
        r1_a, s1_a = map_char_to_digit(middle[1])
        s2_a, sub2_a = map_char_to_alpha(middle[2])
        if r0_a.isdigit() and r1_a.isdigit() and s2_a.isalpha() and (r0_a + r1_a != "00"):
            cand_a = state_candidate + r0_a + r1_a + s2_a + num_part
            subs_a = subs + int(s0_a) + int(s1_a) + int(sub2_a)

        cand_b = None
        subs_b = 999
        r0_b, s0_b = map_char_to_digit(middle[0])
        s1_b, sub1_b = map_char_to_alpha(middle[1])
        s2_b, sub2_b = map_char_to_alpha(middle[2])
        if r0_b.isdigit() and s1_b.isalpha() and s2_b.isalpha() and (r0_b != "0"):
            cand_b = state_candidate + r0_b + s1_b + s2_b + num_part
            subs_b = subs + int(s0_b) + int(sub1_b) + int(sub2_b)

        if cand_a and cand_b:
            return (cand_b, subs_b) if subs_b < subs_a else (cand_a, subs_a)
        elif cand_a:
            return cand_a, subs_a
        elif cand_b:
            return cand_b, subs_b

    # Length 8: 2 digits RTO + 0 series OR 1 digit RTO + 1 letter series
    elif m_len == 2:
        if middle[0].isdigit() and middle[1].isdigit():
            if middle != "00":
                return state_candidate + middle + num_part, subs
        if middle[0].isdigit() and middle[1].isalpha():
            if middle[0] != "0":
                return state_candidate + middle + num_part, subs

        cand_a = None
        subs_a = 999
        r0_a, s0_a = map_char_to_digit(middle[0])
        r1_a, s1_a = map_char_to_digit(middle[1])
        if r0_a.isdigit() and r1_a.isdigit() and (r0_a + r1_a != "00"):
            cand_a = state_candidate + r0_a + r1_a + num_part
            subs_a = subs + int(s0_a) + int(s1_a)

        cand_b = None
        subs_b = 999
        r0_b, s0_b = map_char_to_digit(middle[0])
        s1_b, sub1_b = map_char_to_alpha(middle[1])
        if r0_b.isdigit() and s1_b.isalpha() and (r0_b != "0"):
            cand_b = state_candidate + r0_b + s1_b + num_part
            subs_b = subs + int(s0_b) + int(sub1_b)

        if cand_a and cand_b:
            return (cand_b, subs_b) if subs_b < subs_a else (cand_a, subs_a)
        elif cand_a:
            return cand_a, subs_a
        elif cand_b:
            return cand_b, subs_b

    # Length 11: 2 digits RTO + 3 letters Series (e.g. TN09ABC1234)
    elif m_len == 5:
        rto_chars = []
        for c in middle[:2]:
            m, s = map_char_to_digit(c)
            if not m.isdigit():
                return None
            rto_chars.append(m)
            subs += int(s)
        rto_str = "".join(rto_chars)
        if rto_str == "00":
            return None

        ser_chars = []
        for c in middle[2:]:
            m, s = map_char_to_alpha(c)
            if not m.isalpha():
                return None
            ser_chars.append(m)
            subs += int(s)

        return state_candidate + rto_str + "".join(ser_chars) + num_part, subs

    return None


def disambiguate_bharat_series(text: str) -> Optional[Tuple[str, int]]:
    """
    Disambiguate Bharat Series: [Year 2D]BH[Num 4D][Series 1-2A].
    Returns (normalized_plate, substitutions_applied) or None.
    """
    cleaned = clean_ocr_text(text)
    if len(cleaned) not in (9, 10):
        return None

    # Series cannot be digits; reject broken 5/6-digit Bharat strings
    if len(cleaned) == 9 and cleaned[8].isdigit():
        return None
    if len(cleaned) == 10 and cleaned[8].isdigit() and cleaned[9].isdigit():
        return None

    subs = 0
    # Chars 2:4 must map to 'BH'
    c2, s2 = map_char_to_alpha(cleaned[2])
    c3, s3 = map_char_to_alpha(cleaned[3])
    if c2 + c3 != "BH":
        return None
    subs += int(s2) + int(s3)

    # Chars 0:2 must map to 2 digits (Year)
    y0, sy0 = map_char_to_digit(cleaned[0])
    y1, sy1 = map_char_to_digit(cleaned[1])
    if not (y0.isdigit() and y1.isdigit()):
        return None
    subs += int(sy0) + int(sy1)

    # Chars 4:8 must map to 4 digits, cannot be 0000
    num_chars = []
    for c in cleaned[4:8]:
        m, s = map_char_to_digit(c)
        if not m.isdigit():
            return None
        num_chars.append(m)
        subs += int(s)
    num_part = "".join(num_chars)
    if num_part == "0000":
        return None

    # Remainder must map to 1-2 letters from statutory alphabet (excluding I and O)
    ser_chars = []
    for c in cleaned[8:]:
        m, s = map_char_to_alpha(c)
        if not m.isalpha() or m in ("I", "O"):
            return None
        ser_chars.append(m)
        subs += int(s)

    return y0 + y1 + "BH" + num_part + "".join(ser_chars), subs
