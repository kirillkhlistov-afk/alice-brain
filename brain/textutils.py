import re

NUMBER_WORDS = {
    "ноль": 0, "один": 1, "одну": 1, "одна": 1, "два": 2, "две": 2,
    "три": 3, "четыре": 4, "пять": 5, "шесть": 6, "семь": 7,
    "восемь": 8, "девять": 9, "десять": 10, "одиннадцать": 11,
    "двенадцать": 12, "тринадцать": 13, "четырнадцать": 14, "пятнадцать": 15,
    "шестнадцать": 16, "семнадцать": 17, "восемнадцать": 18, "девятнадцать": 19,
    "двадцать": 20, "тридцать": 30, "сорок": 40, "пятьдесят": 50,
    "шестьдесят": 60, "семьдесят": 70, "восемьдесят": 80, "девяносто": 90,
    "полминуты": 30, "полчаса": 30,
}

UNIT_WORDS = {
    "секунд": "sec", "секунду": "sec", "секунды": "sec",
    "минут": "min", "минуту": "min", "минуты": "min",
    "час": "hour", "часа": "hour", "часов": "hour",
}

PLURALS = {
    ("sec", 1): "секунду",
    ("sec", 2): "секунды",
    ("sec", 5): "секунд",
    ("min", 1): "минуту",
    ("min", 2): "минуты",
    ("min", 5): "минут",
    ("hour", 1): "час",
    ("hour", 2): "часа",
    ("hour", 5): "часов",
}


def normalize(text: str) -> str:
    text = text.lower().replace("ё", "е")
    text = re.sub(r"[^a-zа-я0-9\s]", " ", text)
    return re.sub(r"\s+", " ", text).strip()


def words_to_number(words: list) -> int | None:
    total = 0
    found = False
    for word in words:
        word = normalize(word)
        if word.isdigit():
            total += int(word)
            found = True
        elif word in NUMBER_WORDS:
            total += NUMBER_WORDS[word]
            found = True
    return total if found else None


def parse_duration(text: str) -> tuple | None:
    tokens = normalize(text).split()
    duration = 0
    found = False
    buffer = []
    for token in tokens:
        if token in NUMBER_WORDS or token.isdigit():
            buffer.append(token)
            continue
        if token in UNIT_WORDS and buffer:
            value = words_to_number(buffer)
            if value:
                duration += value_to_seconds(value, UNIT_WORDS[token])
                found = True
            buffer = []
    if not found:
        return None
    return duration, humanize_duration(duration)


def value_to_seconds(value: int, unit: str) -> int:
    return value * {"sec": 1, "min": 60, "hour": 3600}[unit]


def humanize_duration(seconds: int) -> str:
    parts = []
    for unit, size in (("hour", 3600), ("min", 60), ("sec", 1)):
        value, seconds = divmod(seconds, size)
        if value:
            parts.append(f"{value} {plural(value, unit)}")
        if unit == "min":
            seconds = 0 if parts else seconds
    return " ".join(parts)


def plural(value: int, unit: str) -> str:
    if value % 100 in (11, 12, 13, 14):
        return PLURALS[(unit, 5)]
    if value % 10 == 1:
        return PLURALS[(unit, 1)]
    if value % 10 in (2, 3, 4):
        return PLURALS[(unit, 2)]
    return PLURALS[(unit, 5)]
