import time

from .config import AssistantConfig
from .light import build_light
from .llm import LLM
from .music import MusicPlayer
from .skills import Timers, match_skill

OFFLINE_FALLBACKS = (
    "Я тебя поняла, но мозг не подключён. Задай LLM-ключ в конфиге.",
    "Это я запомню. Правда, думать пока не могу: нет ключа нейросети.",
    "Хороший вопрос. Чтобы отвечать на такие, подключи LLM в конфиге.",
)


class Assistant:
    def __init__(self, config: AssistantConfig, tts=None, speak=None):
        self.config = config
        self.tts = tts
        self._speak = speak
        self.llm = LLM(config.llm)
        self.player = None if config.music.engine == "none" else MusicPlayer(
            config.music.engine, config.music.volume
        )
        self.lamp = build_light(config)
        self.timers = Timers(self._raw_speak)
        self.last_answer = None
        self._player = None

    def speak(self, text: str):
        print(f"{self.config.name}: {text}")
        if self.tts:
            self.tts.say(text, self._get_player())

    def _raw_speak(self, text: str):
        self.speak(text)

    def handle_text(self, text: str) -> str:
        text = text.strip()
        if not text:
            return ""
        answer = match_skill(
            text, self.config, self.timers, self.speak,
            player=self.player, lamp=self.lamp,
        )
        if answer is None:
            answer = self.llm.ask(text)
        if answer is None:
            answer = OFFLINE_FALLBACKS[len(text) % len(OFFLINE_FALLBACKS)]
        self.last_answer = answer
        self.speak(answer)
        return answer

    def is_wake_word(self, text: str) -> bool:
        normalized = text.lower().replace("ё", "е")
        return any(word in normalized.split() for word in self.config.speech.wake_words)

    def _get_player(self):
        if self._player is None:
            from .audio import Speaker
            self._player = Speaker(
                self.config.speech.output_device, self.config.speech.sample_rate
            )
        return self._player


class VoiceLoop:
    def __init__(self, assistant: Assistant, mic, recognizer):
        self.assistant = assistant
        self.mic = mic
        self.recognizer = recognizer
        self.listening_for_command = False
        self.deadline = 0.0

    def run_forever(self):
        self.mic.start()
        print("Слушаю... (Ctrl+C чтобы выйти)")
        try:
            while True:
                chunk = self.mic.read_chunk()
                if chunk is None:
                    break
                if self.listening_for_command:
                    self._handle_command_chunk(chunk)
                else:
                    self._handle_wake_chunk(chunk)
        finally:
            self.mic.stop()

    def _handle_wake_chunk(self, chunk: bytes):
        try:
            self.recognizer.feed(chunk)
            partial = self.recognizer.get_partial()
        except Exception:
            return
        if self.assistant.is_wake_word(partial):
            self.recognizer.reset()
            self.listening_for_command = True
            self.assistant.speak("Слушаю")
            self.deadline = time.monotonic() + self.assistant.config.command_timeout

    def _handle_command_chunk(self, chunk: bytes):
        final = None
        try:
            final = self.recognizer.feed(chunk)
        except Exception:
            pass
        if final is None and time.monotonic() > self.deadline:
            final = self.recognizer.finish()
        if final is None:
            return
        self.listening_for_command = False
        if final.strip():
            self.assistant.handle_text(final)
        else:
            self.assistant.speak("Я не расслышала")
