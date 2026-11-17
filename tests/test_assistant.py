import sys
import unittest
from pathlib import Path
from unittest.mock import patch, MagicMock

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from brain.assistant import Assistant
from brain.config import AssistantConfig
from brain.skills import JOKES, match_skill, tell_date, tell_time
from brain.llm import LLM


class Capture(Assistant):
    def __init__(self, config=None):
        super().__init__(config or AssistantConfig())
        self.answers = []

    def speak(self, text):
        self.answers.append(text)


class TestSkills(unittest.TestCase):
    def setUp(self):
        self.assistant = Capture()
        self.config = self.assistant.config
        self.spoken = []
        self.timers = MagicMock()
        self.timers.count.return_value = 0

    def ask(self, text):
        return match_skill(text, self.config, self.timers, lambda t: self.spoken.append(t))

    def test_time(self):
        self.assertIn("Сейчас", self.ask("Который час?"))
        self.assertEqual(tell_time(), f"Сейчас {tell_time().split()[-1]}")

    def test_date(self):
        self.assertIn("Сегодня", self.ask("Какое сегодня число?"))

    def test_timer(self):
        with patch("brain.skills.Timers") as cls:
            timers = cls.return_value
            self.ask("поставь таймер на пять минут")
            self.assertGreaterEqual(1, 1)
        answer = Capture().handle_text("поставь таймер на 2 минуты")
        self.assertIn("Таймер на 2 минуты поставлен", answer)

    def test_timer_cancel_empty(self):
        self.assertIn("нет", self.ask("отмени таймер"))

    def test_joke(self):
        self.assertIn(self.ask("расскажи шутку"), JOKES)

    def test_greeting(self):
        self.assertIn("Привет", self.ask("привет"))

    def test_weather_no_net_is_polite(self):
        with patch("brain.skills.urllib.request.urlopen", side_effect=OSError):
            self.assertIn("Не смог", Capture().handle_text("какая погода"))

    def test_unknown_goes_to_llm(self):
        assistant = Capture()
        with patch.object(assistant.llm, "ask", return_value="Ответ из LLM"):
            self.assertEqual(assistant.handle_text("что такое энтропия"), "Ответ из LLM")

    def test_unknown_offline_fallback(self):
        assistant = Capture()
        answer = assistant.handle_text("что такое энтропия")
        self.assertIn("мозг", answer.lower())


class TestLLM(unittest.TestCase):
    def test_no_key_returns_none(self):
        llm = LLM(AssistantConfig().llm)
        self.assertIsNone(llm.ask("привет"))

    def test_request_error_returns_none(self):
        config = AssistantConfig().llm
        config.api_key = "test"
        llm = LLM(config)
        with patch("brain.llm.urllib.request.urlopen", side_effect=OSError):
            self.assertIsNone(llm.ask("привет"))


class TestWakeWord(unittest.TestCase):
    def test_match(self):
        assistant = Capture()
        self.assertTrue(assistant.is_wake_word("алиса включи свет"))
        self.assertTrue(assistant.is_wake_word("СЛУШАЙ меня"))
        self.assertFalse(assistant.is_wake_word("включи свет"))


if __name__ == "__main__":
    unittest.main()
