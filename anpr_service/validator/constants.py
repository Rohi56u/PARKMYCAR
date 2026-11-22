"""
Indian Vehicle Registration Constants and Regex Grammars.
"""
import re
from typing import Dict, Pattern, Set

# 36 States/UTs + 5 historical aliases (41 valid prefixes)
VALID_STATE_CODES: Set[str] = {
    "AN", "AP", "AR", "AS", "BR", "CH", "CG", "CT", "DD", "DN",
    "DL", "GA", "GJ", "HR", "HP", "JH", "JK", "KA", "KL", "LA",
    "LD", "MP", "MH", "MN", "ML", "MZ", "NL", "OD", "OR", "PB",
    "PY", "RJ", "SK", "TN", "TS", "TG", "TR", "UP", "UK", "UA",
    "WB"
}

# Regex Grammars
STATE_PREFIX_PATTERN = "|".join(sorted(VALID_STATE_CODES))

GRAMMARS: Dict[str, Pattern[str]] = {
    "HSRP_STANDARD": re.compile(
        rf"^({STATE_PREFIX_PATTERN})(?!00)[0-9]{{1,2}}[A-Z]{{0,3}}(?!0000)[0-9]{{4}}$"
    ),
    "BHARAT_SERIES": re.compile(
        r"^[0-9]{2}BH(?!0000)[0-9]{4}[A-HJ-NP-Z]{1,2}$"
    ),
    "DIPLOMATIC": re.compile(
        r"^[0-9]{1,3}(CD|CC|UN)[0-9]{1,4}$"
    ),
    "TEMPORARY": re.compile(
        r"^[A-Z]{2}(?!00)[0-9]{1,2}(TEMP|TR|T)(?!0000)[0-9]{4}$"
    ),
    "MILITARY": re.compile(
        r"^[\^↑]?[0-9]{2}[A-Z][0-9]{5,6}[A-Z]?$"
    ),
}

# Positional DIN 1451 Disambiguation Maps
DIGIT_TO_ALPHA_MAP: Dict[str, str] = {
    "0": "O",
    "1": "I",
    "2": "Z",
    "4": "A",
    "5": "S",
    "6": "G",
    "7": "T",
    "8": "B",
}

ALPHA_TO_DIGIT_MAP: Dict[str, str] = {
    "O": "0",
    "D": "0",
    "Q": "0",
    "I": "1",
    "L": "1",
    "Z": "2",
    "A": "4",
    "S": "5",
    "G": "6",
    "T": "7",
    "B": "8",
}

# Confidence Thresholds
CONFIDENCE_THRESHOLD = 0.75
MIN_CHAR_CONFIDENCE_THRESHOLD = 0.40
DISAMBIGUATION_PENALTY_PER_CHAR = 0.04
