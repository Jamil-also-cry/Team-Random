import re


MERIDIEM = re.compile(r"(\d{1,2})\s*(am|pm)\b", re.IGNORECASE)
FROM_TO = re.compile(
    r"(?:from|between)\s+(\d{1,2})\s*(?:am|pm)?\s*"
    r"(?:until|till|to|-|,|and)\s+(\d{1,2})\s*(?:am|pm)?\b",
    re.IGNORECASE,
)
DASH_RANGE = re.compile(r"\b(\d{1,2})\s*[-–]\s*(\d{1,2})\b")


def _hour_from_token(token):
    hour = int(re.search(r"\d+", token).group())
    meridiem = ""
    m = re.search(r'\s(am|pm)', token, re.IGNORECASE)
    if m:
        meridiem = m.group(1).lower()
    if meridiem == "am":
        return 0 if hour == 12 else hour
    if meridiem == "pm":
        return 12 if hour == 12 else (hour + 12) % 24
    if 0 <= hour <= 23:
        return hour
    if 1 <= hour <= 12:
        return hour % 24
    return None


def _expand(start, end):
    start = start % 24
    end = end % 24
    if end <= start:
        end += 24
    return [h % 24 for h in range(start, end)]


def _explicit_hours(text):
    patterns = [
        r"\bhours?\s*[:=]\s*([\d,\s]+)",
        r"\bhours?\s+(?:are\s+)?(\d+\s*(?:,\s*\d+)+)",
        r"\bhours?\s+(\d+\s*[-–]\s*\d+)",
    ]
    for pattern in patterns:
        match = re.search(pattern, text, re.IGNORECASE)
        if match:
            values = [
                int(v)
                for v in re.findall(r"\d+", match.group(1))
                if 0 <= int(v) <= 23
            ]
            if values:
                return sorted(set(values))
    return None


def _clock_range(text):
    matches = list(MERIDIEM.finditer(text))
    if len(matches) >= 2:
        first = _hour_from_token(matches[0].group(0))
        second = _hour_from_token(matches[1].group(0))
        if first is not None and second is not None:
            return _expand(first, second)
    from_to = FROM_TO.search(text)
    if from_to:
        first = _hour_from_token(from_to.group(1))
        second = _hour_from_token(from_to.group(2))
        if first is not None and second is not None:
            return _expand(first, second)
    dash = DASH_RANGE.search(text)
    if dash:
        first = int(dash.group(1))
        second = int(dash.group(2))
        if 0 <= first <= 23 and 0 <= second <= 23:
            return _expand(first, second)
    if len(matches) == 1:
        hour = _hour_from_token(matches[0].group(0))
        if hour is not None:
            return [hour]
    return None


def _window_hours(text):
    explicit = _explicit_hours(text)
    if explicit:
        return explicit
    return _clock_range(text)


def _factor(text):
    reduced_to = re.search(
        r"(?:reduce|curtail|derate|limit|cut|cap)\s+(?:solar|generation|output|pv)?"
        r"[\s\w]*?\bto\s+(\d+(?:\.\d+)?)\s*%", text, re.IGNORECASE
    )
    if reduced_to:
        pct = float(reduced_to.group(1))
        return max(0.0, min(1.0, pct / 100.0))
    by_match = re.search(
        r"(?:reduce|curtail|derate|cut)\s+.*?\bby\s+(\d+(?:\.\d+)?)\s*%", text, re.IGNORECASE
    )
    if by_match:
        pct = float(by_match.group(1))
        return max(0.0, min(1.0, (100.0 - pct) / 100.0))
    plain = re.search(
        r"\b(?:factor|share|usable|output)\s*(?:of)?\s*[:=]?\s*(\d+(?:\.\d+)?)", text, re.IGNORECASE
    )
    if plain and not any(k in text.lower() for k in ("kwh", "kw")):
        value = float(plain.group(1))
        if 0.0 <= value <= 1.0:
            return value
        if value <= 100.0:
            return value / 100.0
    if "solar" in text.lower():
        trailing = re.search(r"(\d+(?:\.\d+)?)\s*%", text)
        if trailing:
            return max(0.0, min(1.0, float(trailing.group(1)) / 100.0))
    return 1.0


def _kwh_value(text):
    match = re.search(r"(\d+(?:\.\d+)?)\s*(?:kwh|kw|k\s*w\s*h)", text, re.IGNORECASE)
    if match:
        return float(match.group(1))
    plain = re.search(
        r"\bat\s+least\s+(\d+(?:\.\d+)?)\b|\breserve\s+(\d+(?:\.\d+)?)\b|\bminimum\s+(\d+(?:\.\d+)?)\b",
        text, re.IGNORECASE,
    )
    if plain:
        for group in plain.groups():
            if group:
                return float(group)
    return None


def _is_solar(text):
    return "solar" in text.lower()


def _is_charge_block(text):
    return any(
        token in text.lower()
        for token in (
            "no charge", "don't charge", "dont charge", "do not charge",
            "no charging", "avoid charging", "skip charging", "stop charging",
            "never charge", "do not recharge", "no recharge",
        )
    )


def _is_discharge_block(text):
    return any(
        token in text.lower()
        for token in (
            "no discharge", "don't discharge", "dont discharge", "do not discharge",
            "no discharging", "avoid discharging", "skip discharging",
            "stop discharging", "hold the battery", "freeze the battery",
            "do not use the battery", "discharge prohibited",
        )
    )


def _is_reserve(text):
    return any(
        token in text.lower()
        for token in (
            "reserve", "keep at least", "maintain at least", "minimum battery",
            "never let the battery", "do not let the battery go below",
            "do not drop below", "floor", "safety buffer",
        )
    )


def _is_grid_cap(text):
    return any(
        token in text.lower()
        for token in (
            "limit grid", "max grid", "cap grid", "grid cap", "grid limit",
            "grid draw limit", "no more than", "not more than", "at most",
            "peak shave", "reduce grid import", "do not draw more than",
        )
    )


def interpret_notes(operator_notes):
    interpretations = []
    for note in operator_notes or []:
        if isinstance(note, dict):
            index = note.get("note_index", 0)
            text = str(note.get("text", "") or "")
        else:
            index = 0
            text = str(note or "")
        lower = text.lower()
        hours = _window_hours(text)

        if _is_solar(lower) and any(
            token in lower
            for token in ("reduc", "curtail", "derate", "limit", "cut", "cap", "factor")
        ):
            factor = _factor(text)
            interpretations.append(
                {
                    "note_index": index,
                    "applies": True,
                    "directive_type": "solar_reduction",
                    "structured_adjustment": {
                        "hours": hours or list(range(24)),
                        "factor": factor,
                    },
                    "explanation": text.strip(),
                }
            )
        elif _is_charge_block(lower) and hours:
            interpretations.append(
                {
                    "note_index": index,
                    "applies": True,
                    "directive_type": "no_charge_window",
                    "structured_adjustment": {"hours": hours},
                    "explanation": text.strip(),
                }
            )
        elif _is_discharge_block(lower) and hours:
            interpretations.append(
                {
                    "note_index": index,
                    "applies": True,
                    "directive_type": "no_discharge_window",
                    "structured_adjustment": {"hours": hours},
                    "explanation": text.strip(),
                }
            )
        elif _is_reserve(lower) and hours:
            value = _kwh_value(text)
            interpretations.append(
                {
                    "note_index": index,
                    "applies": True,
                    "directive_type": "minimum_battery_reserve",
                    "structured_adjustment": {
                        "hours": hours,
                        "reserve_kwh": value if value is not None else 0.0,
                    },
                    "explanation": text.strip(),
                }
            )
        elif _is_grid_cap(lower) and hours:
            value = _kwh_value(text)
            interpretations.append(
                {
                    "note_index": index,
                    "applies": True,
                    "directive_type": "max_grid_window",
                    "structured_adjustment": {
                        "hours": hours,
                        "max_grid_kwh": value if value is not None else 0.0,
                    },
                    "explanation": text.strip(),
                }
            )
        else:
            interpretations.append(
                {
                    "note_index": index,
                    "applies": False,
                    "directive_type": "no_op",
                    "structured_adjustment": None,
                    "explanation": text.strip(),
                }
            )
    return interpretations