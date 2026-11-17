import subprocess


def list_devices() -> list:
    try:
        output = subprocess.run(
            ["arecord", "-l"], capture_output=True, text=True, timeout=10
        ).stdout
    except Exception:
        return []
    return [line.strip() for line in output.splitlines() if line.startswith("card")]


class Microphone:
    def __init__(self, sample_rate: int = 16000, device: str = "default"):
        self.sample_rate = sample_rate
        self.device = device
        self.process = None
        self.warm = False

    def start(self):
        self.process = subprocess.Popen(
            [
                "arecord", "-q", "-D", self.device, "-f", "S16_LE",
                "-r", str(self.sample_rate), "-c", "1", "-t", "raw",
            ],
            stdout=subprocess.PIPE,
            stderr=subprocess.DEVNULL,
        )

    def read_chunk(self) -> bytes | None:
        if self.process is None:
            raise RuntimeError("Микрофон не запущен")
        chunk = self.process.stdout.read(3200)
        return chunk or None

    def stop(self):
        if self.process:
            self.process.terminate()
            self.process.wait()
            self.process = None


class Speaker:
    def __init__(self, device: str = "default", sample_rate: int = 16000):
        self.device = device
        self.sample_rate = sample_rate

    def play_raw(self, data: bytes, sample_rate: int = None):
        rate = sample_rate or self.sample_rate
        subprocess.run(
            [
                "aplay", "-q", "-D", self.device, "-f", "S16_LE",
                "-r", str(rate), "-c", "1", "-t", "raw",
            ],
            input=data,
        )

    def play_file(self, path: str):
        subprocess.run(["aplay", "-q", "-D", self.device, path])
