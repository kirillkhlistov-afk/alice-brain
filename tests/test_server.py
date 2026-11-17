import json
import sys
import unittest
import urllib.error
import urllib.request
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from brain.assistant import Assistant
from brain.config import AssistantConfig
from brain.server import ControlServer


class Capture(Assistant):
    def __init__(self):
        super().__init__(AssistantConfig())
        self.answers = []

    def speak(self, text):
        self.answers.append(text)


class TestServer(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.assistant = Capture()
        cls.server = ControlServer(cls.assistant, host="127.0.0.1", port=0)
        cls.server.start_background()
        cls.base = f"http://127.0.0.1:{cls.server.port}"

    @classmethod
    def tearDownClass(cls):
        cls.server.stop()

    def _post(self, path: str, payload: dict):
        request = urllib.request.Request(
            f"{self.base}{path}",
            data=json.dumps(payload).encode("utf-8"),
            headers={"Content-Type": "application/json"},
        )
        return urllib.request.urlopen(request)

    def test_page(self):
        with urllib.request.urlopen(f"{self.base}/") as resp:
            html = resp.read().decode("utf-8")
        self.assertIn("Алиса", html)
        self.assertIn("/api/status", html)

    def test_status(self):
        with urllib.request.urlopen(f"{self.base}/api/status") as resp:
            data = json.loads(resp.read())
        self.assertEqual(data["name"], "Алиса")
        self.assertFalse(data["llm"])
        self.assertEqual(data["timers"], 0)

    def test_ask(self):
        with self._post("/api/ask", {"text": "который час"}) as resp:
            data = json.loads(resp.read())
        self.assertIn("Сейчас", data["answer"])
        self.assertEqual(self.assistant.answers[-1], data["answer"])

    def test_ask_empty(self):
        with self.assertRaises(urllib.error.HTTPError) as ctx:
            self._post("/api/ask", {"text": ""}).read()
        self.assertEqual(ctx.exception.code, 400)

    def test_volume_failure_is_reported(self):
        try:
            with self._post("/api/volume", {"level": 50}) as resp:
                data = json.loads(resp.read())
            self.assertIn(data["ok"], (True, False))
        except urllib.error.HTTPError as exc:
            self.assertEqual(exc.code, 400)

    def test_not_found(self):
        with self.assertRaises(urllib.error.HTTPError):
            urllib.request.urlopen(f"{self.base}/nope").read()

    def test_config_server_fields(self):
        config = AssistantConfig()
        self.assertEqual(config.server.host, "0.0.0.0")
        self.assertEqual(config.server.port, 8080)


if __name__ == "__main__":
    unittest.main()
