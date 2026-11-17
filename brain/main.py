import argparse
import sys
import time

from .assistant import Assistant, VoiceLoop
from .config import load_config


def cmd_chat(args):
    config = load_config(args.config)
    assistant = Assistant(config)
    if args.voice:
        from .tts import TTS
        assistant.tts = TTS(config.speech.tts_engine, config.speech.tts_voice)
    print("Текстовый режим. 'выход' — завершить.")
    while True:
        try:
            line = input("> ")
        except (EOFError, KeyboardInterrupt):
            break
        if line.strip().lower() in ("выход", "exit", "quit"):
            break
        assistant.handle_text(line)


def cmd_run(args):
    config = load_config(args.config)
    from .audio import Microphone
    from .server import ControlServer
    from .stt import SpeechRecognizer
    from .tts import TTS

    tts = TTS(config.speech.tts_engine, config.speech.tts_voice)
    assistant = Assistant(config, tts=tts)
    mic = Microphone(config.speech.sample_rate, config.speech.input_device)
    recognizer = SpeechRecognizer(config.speech.vosk_model_path, config.speech.sample_rate)
    panel = ControlServer(assistant, config.server.host, config.server.port)
    panel.start_background()
    print(f"Панель управления: http://{panel.host}:{panel.port}")
    try:
        VoiceLoop(assistant, mic, recognizer).run_forever()
    finally:
        panel.stop()


def cmd_serve(args):
    config = load_config(args.config)
    if args.host:
        config.server.host = args.host
    if args.port:
        config.server.port = args.port
    from .server import ControlServer

    assistant = Assistant(config)
    panel = ControlServer(assistant, config.server.host, config.server.port)
    panel.start_background()
    print(f"Панель управления: http://{panel.host}:{panel.port}  (Ctrl+C — выход)")
    try:
        while True:
            time.sleep(1)
    except KeyboardInterrupt:
        panel.stop()


def cmd_say(args):
    config = load_config(args.config)
    from .audio import Speaker
    from .tts import TTS

    tts = TTS(config.speech.tts_engine, config.speech.tts_voice)
    tts.say(args.text, Speaker(config.speech.output_device, config.speech.sample_rate))


def cmd_setup_model(args):
    from .stt import SpeechRecognizer
    path = SpeechRecognizer.download_model(args.dest)
    print(f"Модель скачана: {path}")


def cmd_devices(args):
    from .audio import list_devices
    devices = list_devices()
    print("\n".join(devices) if devices else "Устройства записи не найдены")


def main():
    parser = argparse.ArgumentParser(
        prog="alice-brain", description="Свой голосовой помощник для колонки"
    )
    parser.add_argument("--config", help="путь к config.json")
    sub = parser.add_subparsers(dest="command", required=True)

    sub.add_parser("run", help="голосовой режим на колонке").set_defaults(func=cmd_run)

    chat = sub.add_parser("chat", help="текстовый режим для отладки")
    chat.add_argument("--voice", action="store_true", help="озвучивать ответы")
    chat.set_defaults(func=cmd_chat)

    setup = sub.add_parser("setup-model", help="скачать офлайн-модель распознавания")
    setup.add_argument("--dest", default="/opt/alice-brain/models")
    setup.set_defaults(func=cmd_setup_model)

    serve = sub.add_parser("serve", help="только веб-панель управления")
    serve.add_argument("--host", default=None)
    serve.add_argument("--port", type=int, default=None)
    serve.set_defaults(func=cmd_serve)

    say = sub.add_parser("say", help="произнести фразу и выйти")
    say.add_argument("text")
    say.set_defaults(func=cmd_say)

    sub.add_parser("devices", help="список аудиоустройств").set_defaults(func=cmd_devices)

    args = parser.parse_args()
    args.func(args)
    return 0


if __name__ == "__main__":
    sys.exit(main())
