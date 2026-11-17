import json
import os
import urllib.request
import zipfile


MODEL_URL = "https://alphacephei.com/vosk/models/vosk-model-small-ru-0.22.zip"
MODEL_NAME = "vosk-model-small-ru-0.22"


class SpeechRecognizer:
    def __init__(self, model_path: str, sample_rate: int = 16000):
        try:
            from vosk import Model, KaldiRecognizer
        except ImportError as exc:
            raise RuntimeError("Модуль vosk не установлен") from exc
        if not os.path.isdir(model_path):
            raise RuntimeError(f"Модель Vosk не найдена: {model_path}")
        self.model = Model(model_path)
        self.sample_rate = sample_rate
        self.recognizer = KaldiRecognizer(self.model, sample_rate)

    def feed(self, chunk: bytes) -> str | None:
        if self.recognizer.AcceptWaveform(chunk):
            return self._text(self.recognizer.Result())
        return None

    def finish(self) -> str | None:
        text = self._text(self.recognizer.FinalResult())
        self.recognizer.Reset()
        return text

    def get_partial(self) -> str:
        try:
            return json.loads(self.recognizer.PartialResult()).get("partial", "")
        except Exception:
            return ""

    def reset(self):
        self.recognizer.Reset()

    @staticmethod
    def _text(raw: str) -> str | None:
        text = json.loads(raw).get("text", "").strip()
        return text or None

    @staticmethod
    def download_model(dest_dir: str) -> str:
        os.makedirs(dest_dir, exist_ok=True)
        archive = os.path.join(dest_dir, "model.zip")
        with urllib.request.urlopen(MODEL_URL, timeout=600) as response, open(archive, "wb") as fh:
            while True:
                block = response.read(1 << 20)
                if not block:
                    break
                fh.write(block)
        with zipfile.ZipFile(archive) as zf:
            zf.extractall(dest_dir)
        os.remove(archive)
        model_path = os.path.join(dest_dir, MODEL_NAME)
        if not os.path.isdir(model_path):
            raise RuntimeError("Распаковка модели не удалась")
        return model_path
