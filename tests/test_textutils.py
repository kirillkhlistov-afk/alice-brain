import sys
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from brain.textutils import humanize_duration, normalize, parse_duration, plural


class TestNormalize(unittest.TestCase):
    def test_lower_and_sparse(self):
        self.assertEqual(normalize("  Алиса,  СЛУШАЙ!  "), "алиса слушай")

    def test_yo(self):
        self.assertEqual(normalize("ёжик"), "ежик")


class TestParseDuration(unittest.TestCase):
    def test_digits(self):
        parsed = parse_duration("поставь таймер на 5 минут")
        self.assertEqual(parsed[0], 300)
        self.assertEqual(parsed[1], "5 минут")

    def test_words(self):
        self.assertEqual(parse_duration("таймер на тридцать секунд")[0], 30)

    def test_hours(self):
        self.assertEqual(parse_duration("один час")[0], 3600)

    def test_none(self):
        self.assertIsNone(parse_duration("поставь таймер"))
        self.assertIsNone(parse_duration("включи музыку"))


class TestHumanize(unittest.TestCase):
    def test_minutes(self):
        self.assertEqual(humanize_duration(300), "5 минут")

    def test_singular(self):
        self.assertEqual(humanize_duration(60), "1 минуту")
        self.assertEqual(plural(1, "hour"), "час")
        self.assertEqual(plural(2, "hour"), "часа")
        self.assertEqual(plural(5, "sec"), "секунд")


if __name__ == "__main__":
    unittest.main()
