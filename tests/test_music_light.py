import sys
import unittest
from pathlib import Path
from unittest.mock import MagicMock

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from brain.assistant import Assistant
from brain.config import AssistantConfig
from brain.light import COLORS, Yeelight
from brain.music import STATIONS, MusicPlayer
from brain.skills import match_skill, parse_light_command


class FakePlayer:
    def __init__(self):
        self.played = []
        self.stopped = 0

    def play(self, station):
        self.played.append(station)
        return f"Включаю: {station}"

    def stop(self):
        self.stopped += 1
        return True


class FakeLamp:
    def __init__(self):
        self.calls = []

    def set_power(self, on):
        self.calls.append(("power", on))
        return "Лампа ок"

    def set_rgb(self, r, g, b):
        self.calls.append(("rgb", (r, g, b)))
        return "Цвет поставила"

    def set_brightness(self, value):
        self.calls.append(("bright", value))
        return f"Яркость {value}%"


class TestMusicSkills(unittest.TestCase):
    def setUp(self):
        self.config = AssistantConfig()
        self.player = FakePlayer()
        self.timers = MagicMock()

    def ask(self, text, player=..., lamp=None):
        return match_skill(text, self.config, self.timers, lambda t: None,
                           player=self.player if player is ... else player,
                           lamp=lamp)

    def test_play_default(self):
        answer = self.ask("включи музыку")
        self.assertTrue(self.player.played)
        self.assertIn("Включаю", answer)

    def test_play_by_genre(self):
        self.ask("включи чилловую музыку")
        self.assertEqual(self.player.played, ["groovesalad"])

    def test_play_russian(self):
        self.ask("включи русскую музыку")
        self.assertEqual(self.player.played, ["record-rus"])

    def test_stop(self):
        self.ask("выключи музыку")
        self.assertEqual(self.player.stopped, 1)

    def test_no_player(self):
        answer = self.ask("включи музыку", player=None)
        self.assertIn("Плеер не найден", answer)

    def test_stations_exist(self):
        for station in STATIONS.values():
            self.assertTrue(station["url"].startswith("http"))

    def test_find_station(self):
        self.assertEqual(MusicPlayer.find_station("поставь трэп"), "record-trap")


class TestLightSkills(unittest.TestCase):
    def setUp(self):
        self.config = AssistantConfig()
        self.lamp = FakeLamp()
        self.timers = MagicMock()

    def ask(self, text, lamp=...):
        return match_skill(text, self.config, self.timers, lambda t: None,
                           player=None, lamp=self.lamp if lamp is ... else lamp)

    def test_on(self):
        self.ask("включи свет")
        self.assertIn(("power", True), self.lamp.calls)

    def test_off(self):
        self.ask("выключи свет")
        self.assertIn(("power", False), self.lamp.calls)

    def test_color_red(self):
        self.ask("поставь красную подсветку")
        self.assertIn(("rgb", (255, 0, 0)), self.lamp.calls)

    def test_color_pink(self):
        self.ask("лампочка розовая")
        self.assertIn(("rgb", (255, 105, 180)), self.lamp.calls)

    def test_brightness(self):
        self.ask("яркость 50 на лампе")
        self.assertIn(("bright", 50), self.lamp.calls)

    def test_no_lamp(self):
        answer = self.ask("включи свет", lamp=None)
        self.assertIn("подключ", answer.lower())


class TestLightClient(unittest.TestCase):
    def test_yeelight_rgb_packet(self):
        lamp = Yeelight("127.0.0.1")
        r, g, b = (255, 32, 16)
        self.assertEqual(r * 65536 + g * 256 + b, 16719888)

    def test_colors_has_common(self):
        for word in ("красный", "синий", "белый", "жёлтый"):
            self.assertIn(word, COLORS)

    def test_parse_off(self):
        self.assertEqual(parse_light_command("выключи свет")["action"], "off")

    def test_parse_color(self):
        parsed = parse_light_command("сделай синюю подсветку")
        self.assertEqual(parsed["action"], "color")
        self.assertEqual(parsed["rgb"], (0, 0, 255))


class TestServerMusicLight(unittest.TestCase):
    pass


if __name__ == "__main__":
    unittest.main()
