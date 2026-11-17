import datetime
import random
import re
import threading
import urllib.parse
import urllib.request

from .config import AssistantConfig
from .textutils import humanize_duration, normalize, parse_duration

JOKES = (
    "Программист ставит на ночь два стакана: один с водой — попить, второй пустой — не попить.",
    "Заходит бесконечный цикл в бар. Заказывает пиво. Заказывает пиво. Заказывает пиво.",
    "Почему программисты путают Хэллоуин и Рождество? Потому что OCT 31 равно DEC 25.",
)


class Timers:
    def __init__(self, speak):
        self.timers = {}
        self.speak = speak
        self.lock = threading.Lock()
        self.next_id = 1

    def add(self, seconds: int, description: str) -> int:
        with self.lock:
            timer_id = self.next_id
            self.next_id += 1
        timer = threading.Timer(seconds, self._fire, args=(timer_id, description))
        self.timers[timer_id] = timer
        timer.daemon = True
        timer.start()
        return timer_id

    def _fire(self, timer_id: int, description: str):
        with self.lock:
            self.timers.pop(timer_id, None)
        self.speak(f"Время вышло. {description}")

    def cancel_all(self):
        with self.lock:
            for timer in self.timers.values():
                timer.cancel()
            self.timers.clear()

    def count(self) -> int:
        return len(self.timers)


def match_skill(text: str, config: AssistantConfig, timers: Timers, speak) -> str | None:
    text = normalize(text)

    if "таймер" in text:
        parsed = parse_duration(text)
        if parsed:
            seconds, human = parsed
            timers.add(seconds, "Таймер!")
            return f"Таймер на {human} поставлен"
        if "отмен" in text or "стоп" in text or "убери" in text:
            if timers.count() == 0:
                return "Активных таймеров нет"
            timers.cancel_all()
            return "Таймеры отменены"
        return "Скажи, например: поставь таймер на пять минут"

    if re.search(r"кот(орый|орое)\s+час|сколько\s+времени|текущее\s+время", text):
        return tell_time()

    if re.search(r"как(ое|\s+сегодня)?\s+(число|дата)|сегодня\s+число", text):
        return tell_date()

    if re.search(r"погод[аыу]", text):
        return tell_weather(config.city)

    if re.search(r"шутк|анекдот|рассмеши", text):
        return random.choice(JOKES)

    if re.search(r"(привет|здравствуй|здорово|добр(ый|ое)\s+(день|утро|вечер))\b", text):
        return f"Привет! Я {config.name}, слушаю."

    if re.search(r"\bспасибо\b|\bмолодец\b", text):
        return random.choice(("Всегда пожалуйста!", "Обращайся!", "Не за что."))

    if re.search(r"повтори\s.*сказал", text):
        return "Повторяю: " + re.sub(r"^.*сказал\w*\s*", "", text)

    return None


def tell_time() -> str:
    now = datetime.datetime.now()
    return f"Сейчас {now.hour}:{now.minute:02d}"


def tell_date() -> str:
    months = ("января", "февраля", "марта", "апреля", "мая", "июня", "июля",
              "августа", "сентября", "октября", "ноября", "декабря")
    today = datetime.date.today()
    return f"Сегодня {today.day} {months[today.month - 1]} {today.year} года"


def tell_weather(city: str) -> str:
    query = urllib.parse.quote(f"{city}?format=3&lang=ru")
    try:
        with urllib.request.urlopen(f"https://wttr.in/{query}", timeout=10) as resp:
            return resp.read().decode("utf-8", "ignore").strip()
    except Exception:
        return "Не смог узнать погоду, проверь интернет"
