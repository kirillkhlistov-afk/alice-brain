import json
import os
from dataclasses import dataclass, field


@dataclass
class ServerConfig:
    host: str = "0.0.0.0"
    port: int = 8080


@dataclass
class LLMConfig:
    api_base: str = "https://api.openai.com/v1"
    api_key: str = ""
    model: str = "gpt-4o-mini"
    system_prompt: str = (
        "Ты — голосовой помощник Алиса, встроенный в домашнюю колонку. "
        "Отвечай по-русски, коротко и по делу, 1-2 предложения, без смайликов."
    )


@dataclass
class SpeechConfig:
    wake_words: tuple = ("алиса", "начала", "слушай")
    vosk_model_path: str = "/opt/alice-brain/models/vosk-model-small-ru-0.22"
    tts_engine: str = "espeak"
    tts_voice: str = "ru"
    sample_rate: int = 16000
    input_device: str = "default"
    output_device: str = "default"


@dataclass
class AssistantConfig:
    llm: LLMConfig = field(default_factory=LLMConfig)
    speech: SpeechConfig = field(default_factory=SpeechConfig)
    server: ServerConfig = field(default_factory=ServerConfig)
    command_timeout: float = 7.0
    silence_threshold: float = 1.2
    city: str = "Москва"
    name: str = "Алиса"


DEFAULT_PATHS = (
    "/etc/alice-brain/config.json",
    os.path.expanduser("~/.config/alice-brain/config.json"),
    "config.json",
)


def load_config(path: str = None) -> AssistantConfig:
    candidates = [path] if path else list(DEFAULT_PATHS)
    for candidate in candidates:
        if candidate and os.path.isfile(candidate):
            with open(candidate, encoding="utf-8") as fh:
                return from_dict(json.load(fh))
    return AssistantConfig()


def from_dict(data: dict) -> AssistantConfig:
    config = AssistantConfig()
    if "llm" in data:
        config.llm = LLMConfig(**data["llm"])
    if "speech" in data:
        speech = data["speech"]
        speech["wake_words"] = tuple(speech.get("wake_words", SpeechConfig.wake_words))
        speech = {k: v for k, v in speech.items() if k in SpeechConfig.__dataclass_fields__}
        config.speech = SpeechConfig(**speech)
    if "server" in data:
        server = {k: v for k, v in data["server"].items() if k in ServerConfig.__dataclass_fields__}
        config.server = ServerConfig(**server)
    for key in ("command_timeout", "silence_threshold", "city", "name"):
        if key in data:
            setattr(config, key, data[key])
    return config
