import re
import subprocess
import threading

STATIONS = {
    "groovesalad": {
        "title": "SomaFM Groove Salad",
        "url": "https://ice1.somafm.com/groovesalad-128-mp3",
    },
    "indiepop": {
        "title": "SomaFM Indie Pop",
        "url": "https://ice1.somafm.com/indiepop-128-mp3",
    },
    "dronezone": {
        "title": "SomaFM Drone Zone",
        "url": "https://ice1.somafm.com/dronezone-128-mp3",
    },
    "defcon": {
        "title": "SomaFM DEF CON Radio",
        "url": "https://ice1.somafm.com/defcon-128-mp3",
    },
    "record-dance": {
        "title": "Радио Record — Dance",
        "url": "https://radiorecord.hostingradio.ru/rr_main96.aacp",
    },
    "record-trap": {
        "title": "Радио Record — Trap",
        "url": "https://radiorecord.hostingradio.ru/tr96.aacp",
    },
    "record-rus": {
        "title": "Радио Record — Русский хит",
        "url": "https://radiorecord.hostingradio.ru/rus96.aacp",
    },
}

GENRE_HINTS = (
    ("чилл|спокойн|расслаб|chill", "groovesalad"),
    ("инди", "indiepop"),
    ("эмбиент|космос", "dronezone"),
    ("электрон|техно|дефкон", "defcon"),
    ("танц|клубн|дэнс", "record-dance"),
    ("трэп|trap", "record-trap"),
    ("русск", "record-rus"),
)


class MusicPlayer:
    def __init__(self, engine: str = "auto", volume: int = 80):
        self.engine = self._pick_engine() if engine == "auto" else engine
        self.process = None
        self.volume = volume
        self.current = None
        self.lock = threading.Lock()

    @staticmethod
    def _pick_engine() -> str:
        for binary in ("mpv", "ffplay"):
            try:
                if subprocess.run(["which", binary], capture_output=True).returncode == 0:
                    return binary
            except OSError:
                pass
        return "mpv"

    def play(self, station_key: str) -> str:
        station = STATIONS[station_key]
        with self.lock:
            self.stop_locked()
            args = {
                "mpv": ["mpv", "--no-video", "--quiet", f"--volume={self.volume}", station["url"]],
                "ffplay": ["ffplay", "-nodisp", "-loglevel", "quiet", station["url"]],
            }
            try:
                self.process = subprocess.Popen(
                    args[self.engine],
                    stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL,
                )
                self.current = station_key
            except Exception:
                return f"Не смог запустить плеер {self.engine}, поставь mpv"
        return f"Включаю: {station['title']}"

    def stop(self) -> bool:
        with self.lock:
            return self.stop_locked()

    def stop_locked(self) -> bool:
        playing = self.process is not None
        if self.process:
            self.process.terminate()
            self.process = None
        self.current = None
        return playing

    @staticmethod
    def find_station(text: str) -> str | None:
        text = text.lower().replace("ё", "е")
        for key, station in STATIONS.items():
            if key in text or station["title"].lower() in text:
                return key
        for pattern, key in GENRE_HINTS:
            if re.search(pattern, text):
                return key
        return None
