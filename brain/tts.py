import os
import subprocess
import tempfile
import uuid


class TTS:
    def __init__(self, engine: str = "espeak", voice: str = "ru", tts_dir: str = None):
        self.engine = engine
        self.voice = voice
        self.tts_dir = tts_dir or os.path.join(tempfile.gettempdir(), "alice-brain-tts")
        os.makedirs(self.tts_dir, exist_ok=True)
        self._silero_model = None

    def say(self, text: str, play) -> None:
        wav_path = self.synthesize_to_wav(text)
        if not wav_path:
            return
        try:
            play.play_file(wav_path)
        finally:
            self._cleanup(wav_path)

    def synthesize_to_wav(self, text: str) -> str | None:
        if not text.strip():
            return None
        wav_path = os.path.join(self.tts_dir, f"{uuid.uuid4().hex}.wav")
        try:
            if self.engine == "silero":
                return self._silero(text, wav_path)
            return self._espeak(text, wav_path)
        except Exception:
            if os.path.exists(wav_path):
                os.remove(wav_path)
            return None

    def _espeak(self, text: str, wav_path: str) -> str:
        subprocess.run(
            ["espeak-ng", "-v", self.voice, "-s", "150", "-w", wav_path, text],
            check=True,
            stderr=subprocess.DEVNULL,
        )
        return wav_path

    def _silero(self, text: str, wav_path: str) -> str:
        import torch

        if self._silero_model is None:
            self._silero_model, _ = torch.hub.load(
                "snakers4/silero-tts", "v3_ru", trust_repo=True
            )
        audio = self._silero_model.apply_tts(
            text=text, speaker="kseniya", sample_rate=48000
        )
        import torchaudio
        torchaudio.save(wav_path, audio.unsqueeze(0), 48000)
        return wav_path

    def _cleanup(self, wav_path: str):
        try:
            os.remove(wav_path)
        except OSError:
            pass
