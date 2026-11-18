"""Алиса — панель управления для ПК.

Ничего не устанавливает: стандартный tkinter + HTTP-клиент.
Запуск: python3 alice_desktop.py [адрес_колонки]
Адрес колонки — это IP в домашней Wi-Fi-сети, например 192.168.1.50
"""
import json
import sys
import threading
import urllib.error
import urllib.request
import tkinter as tk
from tkinter import scrolledtext, ttk


class App(tk.Tk):
    def __init__(self, base_url: str):
        super().__init__()
        self.base = base_url.rstrip("/")
        self.title(f"Алиса — {self.base}")
        self.geometry("560x640")
        self.configure(bg="#12141a")

        self.status = tk.Label(self, text="подключение...", bg="#12141a",
                               fg="#8b8fa3", font=("Segoe UI", 10))
        self.status.pack(pady=6)

        self.chat = scrolledtext.ScrolledText(self, bg="#1c1f29", fg="#e8e9ee",
                                              insertbackground="#e8e9ee",
                                              font=("Segoe UI", 11), state="disabled",
                                              relief="flat", wrap="word")
        self.chat.pack(fill="both", expand=True, padx=12, pady=6)

        row = tk.Frame(self, bg="#12141a")
        row.pack(fill="x", padx=12, pady=6)
        self.entry = tk.Entry(row, bg="#1c1f29", fg="#e8e9ee",
                              insertbackground="#e8e9ee", relief="flat",
                              font=("Segoe UI", 12))
        self.entry.pack(side="left", fill="x", expand=True, ipady=8)
        self.entry.bind("<Return>", lambda e: self.send())
        send_btn = tk.Button(row, text="Отправить", command=self.send,
                             bg="#7c6cff", fg="white", relief="flat",
                             font=("Segoe UI", 11), padx=14)
        send_btn.pack(side="left", padx=(8, 0))

        controls = tk.Frame(self, bg="#12141a")
        controls.pack(fill="x", padx=12, pady=6)

        tk.Label(controls, text="Громкость", bg="#12141a", fg="#8b8fa3",
                 font=("Segoe UI", 9)).grid(row=0, column=0, sticky="w")
        self.volume = tk.Scale(controls, from_=0, to=100, orient="horizontal",
                               command=self.set_volume, length=200,
                               bg="#12141a", fg="#e8e9ee", highlightthickness=0,
                               troughcolor="#1c1f29")
        self.volume.grid(row=1, column=0, padx=(0, 16))

        light = tk.LabelFrame(controls, text="Лампа", bg="#12141a", fg="#e8e9ee")
        light.grid(row=0, column=1, rowspan=2, padx=(0, 16))
        for i, (text, cmd) in enumerate((
            ("Вкл", lambda: self.light("on")),
            ("Выкл", lambda: self.light("off")),
        )):
            tk.Button(light, text=text, command=cmd, bg="#7c6cff", fg="white",
                      relief="flat", width=6).grid(row=0, column=i, padx=3, pady=4)
        self.color_var = tk.StringVar(value="красный")
        colors = ("красный", "зелёный", "синий", "жёлтый", "розовый", "белый")
        tk.OptionMenu(light, self.color_var, *colors,
                      ).grid(row=1, column=0, columnspan=2, sticky="we")
        tk.Button(light, text="Цвет", bg="#3a3f52", fg="white", relief="flat",
                  width=8, command=self.set_color).grid(row=2, column=0, columnspan=2,
                                                        sticky="we", padx=3)

        music_box = tk.LabelFrame(controls, text="Музыка", bg="#12141a", fg="#e8e9ee")
        music_box.grid(row=0, column=2, rowspan=2)
        tk.Button(music_box, text="■ Стоп", command=lambda: self.music("stop"),
                  bg="#3a3f52", fg="white", relief="flat", width=8).grid(row=0, column=0, sticky="we", padx=3)
        self.station_var = tk.StringVar(value="Рус хит")
        self.stations = {}
        tk.OptionMenu(music_box, self.station_var, "Рус хит").grid(row=1, column=0, sticky="we")
        tk.Button(music_box, text="▶ Играть", command=self.play_station,
                  bg="#7c6cff", fg="white", relief="flat", width=8).grid(row=2, column=0, sticky="we", padx=3)

        self.after(100, self.refresh)

    def _api(self, path: str, payload: dict | None = None):
        try:
            if payload is None:
                with urllib.request.urlopen(f"{self.base}{path}", timeout=10) as r:
                    return json.loads(r.read())
            request = urllib.request.Request(
                f"{self.base}{path}",
                data=json.dumps(payload).encode("utf-8"),
                headers={"Content-Type": "application/json"},
            )
            with urllib.request.urlopen(request, timeout=10) as r:
                return json.loads(r.read())
        except Exception:
            return None

    def _async(self, fn, *args):
        threading.Thread(target=fn, args=args, daemon=True).start()

    def add(self, who: str, text: str):
        self.chat.configure(state="normal")
        self.chat.insert("end", f"{who}: {text}\n")
        self.chat.configure(state="disabled")
        self.chat.see("end")

    def send(self):
        text = self.entry.get().strip()
        if not text:
            return
        self.entry.delete(0, "end")
        self.add("Ты", text)

        def worker():
            data = self._api("/api/ask", {"text": text})
            answer = (data or {}).get("answer", "(колонка не отвечает)")
            self.after(0, self.add, "Алиса", answer)
        self._async(worker)

    def refresh(self):
        def worker():
            data = self._api("/api/status")
            if data is None:
                self.after(0, lambda: self.status.config(
                    text=f"приложение не может достучаться до {self.base}\n"
                         "проверь: колонка в той же сети и панель запущена (run/serve)"))
                return
            self.after(0, lambda: self.status.config(text=(
                f"{data['name']} • таймеров: {data['timers']} • "
                f"LLM: {'вкл' if data['llm'] else 'выкл (офлайн-режим)'}")))
            stations = self._api("/api/stations")
            if stations and not self.stations:
                self.stations = {s["title"]: s["id"] for s in stations["stations"]}
                titles = list(self.stations)
                self.after(0, lambda: self.rebuild_station_menu(titles))
        self._async(worker)

    def rebuild_station_menu(self, titles: list):
        self.station_var.set(titles[0])
        menu = tk.OptionMenu(self, self.station_var, *titles)
        menu.place(x=1, y=1)
        menu.lower()

    def set_volume(self, value: str):
        self._async(self._api, "/api/volume", {"level": int(value)})

    def light(self, action: str):
        self._async(self._api, "/api/light", {"action": action})

    def set_color(self):
        self._async(self._api, "/api/light", {"action": "textcolor", "text": self.color_var.get()},
                    ) if False else self._send_color()

    def _send_color(self):
        name = self.color_var.get()
        self._async(self._api, "/api/light",
                    {"action": "text_color", "name": name, "text": name})

    def music(self, action: str):
        self._async(self._api, "/api/music", {"action": action})

    def play_station(self):
        title = self.station_var.get()
        station = self.stations.get(title, "record-rus")
        self._async(self._api, "/api/music", {"action": "play", "station": station})


def main():
    base = sys.argv[1] if len(sys.argv) > 1 else "http://192.168.1.50:8080"
    App(base).mainloop()


if __name__ == "__main__":
    main()
