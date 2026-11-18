import json
import socket
import urllib.request

COLORS = {
    "красный": (255, 0, 0),
    "алый": (255, 0, 0),
    "зелёный": (0, 255, 0),
    "зеленый": (0, 255, 0),
    "синий": (0, 0, 255),
    "голубой": (0, 191, 255),
    "жёлтый": (255, 220, 0),
    "желтый": (255, 220, 0),
    "оранжевый": (255, 140, 0),
    "розовый": (255, 105, 180),
    "фиолетовый": (160, 32, 240),
    "бирюзовый": (64, 224, 208),
    "белый": (255, 255, 255),
    "тёплый": (255, 214, 170),
    "теплый": (255, 214, 170),
}


class Yeelight:
    def __init__(self, host: str, port: int = 55490):
        self.host = host
        self.port = port
        self._id = 0

    def _send(self, method: str, params: list) -> dict:
        self._id += 1
        payload = json.dumps({"id": self._id, "method": method, "params": params})
        with socket.create_connection((self.host, self.port), timeout=5) as sock:
            sock.sendall((payload + "\r\n").encode("utf-8"))
            data = sock.makefile().readline()
        return json.loads(data) if data else {}

    def set_power(self, on: bool) -> str:
        result = self._send("set_power", ["on" if on else "off", "smooth", 300])
        return self._describe(result, "включена" if on else "выключена")

    def set_rgb(self, r: int, g: int, b: int) -> str:
        result = self._send("set_rgb", [r * 65536 + g * 256 + b, "smooth", 300])
        return self._describe(result, "цвет поставила")

    def set_brightness(self, percent: int) -> str:
        percent = max(1, min(100, int(percent)))
        result = self._send("set_bright", [percent, "smooth", 300])
        return self._describe(result, f"яркость {percent}%")

    @staticmethod
    def _describe(result: dict, text: str) -> str:
        if result.get("result") == "ok":
            return f"Лампа {text}"
        return "Лампа не ответила"


class HomeAssistantLight:
    def __init__(self, base_url: str, token: str, entity_id: str):
        self.base_url = base_url.rstrip("/")
        self.token = token
        self.entity_id = entity_id

    def _call(self, service: str, data: dict) -> dict:
        request = urllib.request.Request(
            f"{self.base_url}/api/services/light/{service}",
            data=json.dumps({"entity_id": self.entity_id, **data}).encode("utf-8"),
            headers={
                "Content-Type": "application/json",
                "Authorization": f"Bearer {self.token}",
            },
        )
        with urllib.request.urlopen(request, timeout=10) as response:
            return json.loads(response.read() or b"[]")

    def set_power(self, on: bool) -> str:
        self._call("turn_on" if on else "turn_off", {})
        return f"Лампа {'включена' if on else 'выключена'}"

    def set_rgb(self, r: int, g: int, b: int) -> str:
        self._call("turn_on", {"rgb_color": [r, g, b]})
        return "Цвет поставила"

    def set_brightness(self, percent: int) -> str:
        percent = max(1, min(100, int(percent)))
        self._call("turn_on", {"brightness_pct": percent})
        return f"Яркость {percent}%"


def build_light(config) -> object | None:
    light_cfg = getattr(config, "light", None)
    if not light_cfg:
        return None
    if light_cfg.type == "yeelight" and light_cfg.host:
        return Yeelight(light_cfg.host, light_cfg.port)
    if light_cfg.type == "homeassistant" and light_cfg.ha_url and light_cfg.ha_token:
        return HomeAssistantLight(
            light_cfg.ha_url, light_cfg.ha_token, light_cfg.entity_id
        )
    return None
