#!/bin/bash
set -euo pipefail

if [[ $EUID -ne 0 ]]; then
  echo "Запусти от root: sudo ./install.sh"
  exit 1
fi

TARGET=/opt/alice-brain
CONF_DIR=/etc/alice-brain
SRC="$(cd "$(dirname "$0")" && pwd)"

echo ">> Обновляю пакеты"
if command -v apt-get >/dev/null; then
  apt-get update -qq
  apt-get install -y -qq python3 python3-pip alsa-utils espeak-ng unzip
fi

echo ">> Копирую код в $TARGET"
mkdir -p "$TARGET" "$CONF_DIR"
cp -r "$SRC/brain" "$TARGET/"
cp "$SRC/requirements.txt" "$SRC/pyproject.toml" "$TARGET/"

echo ">> Ставлю зависимости"
pip3 install -q vosk

echo ">> Копирую конфиг"
if [[ ! -f "$CONF_DIR/config.json" ]]; then
  cp "$SRC/config.example.json" "$CONF_DIR/config.json"
else
  echo "   конфиг уже есть, не трогаю: $CONF_DIR/config.json"
fi

echo ">> Скачиваю офлайн-модель распознавания (44 МБ)"
if [[ ! -d "$TARGET/models/vosk-model-small-ru-0.22" ]]; then
  cd "$TARGET" && python3 -c "
from brain.stt import SpeechRecognizer
SpeechRecognizer.download_model('$TARGET/models')
"
else
  echo "   модель уже есть"
fi

echo ">> Ставлю автозапуск сервиса"
cp "$SRC/deploy/alice-brain.service" /etc/systemd/system/
systemctl daemon-reload
systemctl enable alice-brain

echo
echo "Готово! Дальше:"
echo "  1) отредактируй $CONF_DIR/config.json (LLM-ключ, город, wake-слово)"
echo "  2) systemctl start alice-brain"
echo "  3) проверь журнал: journalctl -u alice-brain -f"
