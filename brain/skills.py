import datetime
import random
import re
import threading
import urllib.parse
import urllib.request

from .config import AssistantConfig
from .light import COLORS
from .music import STATIONS, MusicPlayer
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


def parse_light_command(text: str) -> dict:
    for word, rgb in COLORS.items():
        stems = {word, word[:-1], word[:-2] if len(word) > 4 else word}
        if any(stem and stem in text for stem in stems):
            return {"action": "color", "rgb": rgb}
    if "выключ" in text:
        return {"action": "off"}
    if re.search(r"яркост|ярче|тускл|темнее", text):
        from .textutils import words_to_number
        value = None
        for token in text.split():
            if token.isdigit():
                value = int(token)
            else:
                num = words_to_number([token])
                if num and num <= 100 and value is None:
                    value = num
        if value:
            return {"action": "brightness", "value": value}
        return {"action": "brightness", "value": 100 if "ярче" in text else 30}
    return {"action": "on"}


def match_skill(text: str, config: AssistantConfig, timers: Timers, speak, player=None, lamp=None) -> str | None:
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

    if re.search(r"музык|радио|песн|трек|станци", text):
        if player is None:
            return "Плеер не найден: поставь mpv или укажи движок в конфиге"
        if "выключ" in text or "стоп" in text or "хватит" in text:
            player.stop()
            return "Музыка выключена"
        station = MusicPlayer.find_station(text)
        if "включ" not in text and "запусти" not in text and "послуш" not in text and "играй" not in text:
            station = station if "станц" in text or "радио" in text else None
        if station:
            return player.play(station)
        if "выключ" not in text:
            return player.play(getattr(config.music, "default_station", "record-rus"))
        return "Музыка уже выключена"

    if re.search(r"свет|ламп|подсвет|ночник|освещен|подсветк", text):
        if lamp is None:
            return "Лампа не подключена: пропиши её в конфиге (секция light)"
        action = parse_light_command(text)
        if action["action"] == "off":
            return lamp.set_power(False)
        if action["action"] == "color":
            r, g, b = action["rgb"]
            lamp.set_power(True)
            return lamp.set_rgb(r, g, b)
        if action["action"] == "brightness":
            lamp.set_power(True)
            return lamp.set_brightness(action["value"])
        return lamp.set_power(True)

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
