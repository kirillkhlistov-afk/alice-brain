#!/bin/sh
# device_setup.sh — установка alice-brain на колонке (YNDX-00025).
# Запускается на устройстве (adb или ssh). Работает на минимальном_busybox sh.
set -u

BASE=/data/alice-brain
PY=""
FIND="${FIND:-}"

say() { echo "[alice] $*"; }

hdr() {
  if [ -x /system/bin/curl ]; then echo /system/bin/curl; return; fi
  if command -v curl >/dev/null 2>&1; then echo curl; return; fi
  if command -v wget >/dev/null 2>&1; then echo wget; return; fi
  echo ""
}

fetch() { # fetch <url> <outfile>
  DL="$(hdr)"
  case "$DL" in
    *curl) "$DL" -fsSL "$1" -o "$2" ;;
    wget) "$DL" -qO "$2" "$1" ;;
    *) say "нет закачки (ни curl, ни wget)"; return 1 ;;
  esac
}

# ---------- 1. python ----------
for CAND in /usr/bin/python3 /usr/local/bin/python3 /system/bin/python3 /bin/python3; do
  if [ -x "$CAND" ]; then PY="$CAND"; break; fi
done
if command -v python3 >/dev/null 2>&1; then PY="$(command -v python3)"; fi

if [ -z "$PY" ]; then
  say "python3 не найден — качаю standalone python (aarch64)"
  ARC=gnu
  if [ -f /etc/alpine-release ] || ! uname -m | grep -q aarch64; then
    # musl-системы alpine; glibc-питон туда не встаёт
    ldd /system/bin/sh >/dev/null 2>&1 || true
  fi
  VER=20261110
  for LIBC in gnu musl; do
    URL="https://github.com/astral-sh/python-build-standalone/releases/download/${VER}/cpython-3.11.18%2B${VER}-aarch64-unknown-linux-${LIBC}-install_only.tar.gz"
    say "пробую ${LIBC}-сборку..."
    if fetch "$URL" /tmp/py.tar.gz && tar -xzf /tmp/py.tar.gz -C "$BASE" 2>/dev/null; then
      PY="$BASE/python/bin/python3"
      break
    fi
  done
fi

if [ -z "$PY" ] || [ ! -x "$PY" ]; then
  say "ОШИБКА: python не установлен. Панель работать не будет."
  exit 1
fi
say "python: $PY"

# ---------- 2. vosk ----------
if ! "$PY" -c "import vosk" >/dev/null 2>&1; then
  say "ставлю vosk (скачивается ~1-2 МБ wheel + модель отдельно)"
  "$PY" -m ensurepip >/dev/null 2>&1 || true
  "$PY" -m pip install --no-index 2>/dev/null || true
  "$PY" -m pip install vosk==0.3.45 2>/dev/null \
    || say "vosk не встал: останется панель без голосового распознавания"
fi

# ---------- 3. плеер ----------
if ! command -v ffmpeg >/dev/null 2>&1 && ! command -v mpv >/dev/null 2>&1; then
  say "ставлю статический ffmpeg (для радио)"
  FURL="https://johnvansickle.com/ffmpeg/releases/ffmpeg-release-arm64-static.tar.xz"
  if fetch "$FURL" /tmp/ff.tar.xz && mkdir -p /tmp/ff && tar -xJf /tmp/ff.tar.xz -C /tmp/ff 2>/dev/null; then
    FFDIR="$(find /tmp/ff -maxdepth 1 -type d -name 'ffmpeg-*' | head -n 1)"
    [ -n "$FFDIR" ] && cp "$FFDIR/ffmpeg" /data/ffmpeg && chmod +x /data/ffmpeg && PATH="$PATH:/data" && export PATH
  else
    say "ffmpeg не поставился — радио может не работать"
  fi
fi

# ---------- 4. конфиг ----------
if [ ! -f "$BASE/config.json" ]; then
  cp "$BASE/config.example.json" "$BASE/config.json"
  say "создан config.json (впиши свой ключ LLM при желании)"
fi

# ---------- 5. автозапуск ----------
if command -v systemctl >/dev/null 2>&1 && [ -d /etc/systemd/system ]; then
  say "настраиваю systemd-сервис"
  sed -e "s|/opt/alice-brain|$BASE|g" "$BASE/deploy/alice-brain.service" > /etc/systemd/system/alice-brain.service
  systemctl daemon-reload 2>/dev/null || true
  systemctl enable --now alice-brain 2>/dev/null || true
  say "сервис запущен"
else
  say "systemd нет — запускаю напрямую"
  if [ -f "$BASE/assistant.pid" ] && kill -0 "$(cat "$BASE/assistant.pid")" 2>/dev/null; then
    kill "$(cat "$BASE/assistant.pid")" 2>/dev/null || true
  fi
  cd "$BASE" || exit 1
  nohup "$PY" -u -m brain.main run > "$BASE/assistant.log" 2>&1 &
  echo $! > "$BASE/assistant.pid"
fi

say "готово. панель: http://<ip-колонки>:8080"
