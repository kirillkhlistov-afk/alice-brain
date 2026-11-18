"""Alice Install — авто-установка Alice Brain на колонку по Wi-Fi.

Работает на ПК в той же Wi-Fi-сети, что и колонка (нужен root на колонке).
Ничего не требует, кроме Python 3 на ПК и adb в PATH (или SSH-доступа).

Запуск:      python alice_install.py
Свой IP:     python alice_install.py --host 192.168.1.50
Через SSH:   python alice_install.py --method ssh --host 192.168.1.50 --user root
"""
import argparse
import ipaddress
import os
import shutil
import socket
import stat
import subprocess
import sys
import urllib.request
import zipfile
from concurrent.futures import ThreadPoolExecutor

PROJECT_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
SKIP_DIRS = {".git", "__pycache__", ".venv", "node_modules"}
ADB_PORT = 5555
SSH_PORTS = (22, 2222, 22222)
PANEL_PORT = 8080
DEVICE_DIR = "/data/alice-brain"
PLATFORM_TOOLS = {
    "win32": "https://dl.google.com/android/repository/platform-tools-latest-windows.zip",
    "linux": "https://dl.google.com/android/repository/platform-tools-latest-linux.zip",
    "darwin": "https://dl.google.com/android/repository/platform-tools-latest-darwin.zip",
}
ADB_BIN = "adb"
ROOT_DNS = "179.254.167.126"
ROUTER_HINT = "http://192.168.1.1 или http://192.168.0.1"
ROOT_GUIDE = [
    "ROOT-ПОМОЩНИК: DNS-метод для Станции Лайт (YNDX-00025).",
    "Делается ОДИН раз, ~15 минут. Ниже — ФИЗИЧЕСКИЕ шаги, которые",
    "нужно сделать руками. Всё остальное я сделаю сам.",
    "",
    "ГДЕ ЧТО: кнопки — на верхней крышке колонки (пауза и микрофон);",
    "подсветка — кольцо в основании. Работай рядом с колонкой и роутером.",
    "",
    "ШАГ 1. СБРОС КОЛОНКИ (руки на колонке):",
    "  а) вытащи кабель питания из колонки, подожди пару секунд;",
    "  б) вставь кабель обратно;",
    "  в) СРАЗУ, как только кольцо начнёт светиться, зажми кнопку ПАУЗЫ;",
    "  г) держи 6-10 секунд, пока кольцо не станет ЖЁЛТО-ЗЕЛЁНЫМ;",
    "  д) отпусти. Кольцо пульсирует голубым — колонка ждёт настройки.",
    "  (Если зажать кнопку ДО включения питания — сброс не сработает.)",
    "",
    "ШАГ 2. ТЕЛЕФОН (приложение «Дом с Алисой»):",
    "  а) включи на телефоне Bluetooth и геолокацию;",
    "  б) лучше: выключи на телефоне Wi-Fi (пусть работает мобильный интернет);",
    "  в) открой приложение: «+» → «Устройство с Алисой» → выбери Лайт;",
    "  г) дойди до экрана, где нужно выбрать Wi-Fi сеть и ввести пароль,",
    "     и ОСТАНОВИСЬ ЗДЕСЬ. Не жми «Подключиться»!",
    "",
    "ШАГ 3. РОУТЕР (займёт 2 минуты, каталог: настройки роутера в браузере):",
    "  Найди поле DNS и впиши туда: " + ROOT_DNS,
    "  (второе поле DNS 2 — очисти, оставь пустым)",
    "  Keenetic: Сетевые правила → Домашняя сеть → Параметры IP и DHCP → DNS 1",
    "  TP-Link: Дополнительно → Сеть → DHCP-сервер → Предпочитаемый DNS-сервер",
    "  Ростелеком/др.: раздел «Локальная сеть» → «DHCP» → «DNS-серверы»",
    "  Сохрани настройки роутера.",
    "",
    "  ЕСЛИ К РОУТЕРУ НЕТ ДОСТУПА:",
    "  ПОПРОБУЙ СПЕРВА: логин/пароль роутера часто написаны на наклейке",
    "  СНИЗУ роутера. Открой в браузере " + ROUTER_HINT +
    ", логин admin (или с наклейки).",
    "",
    "  Если доступа всё равно нет — раздача с Android (по инструкции hackalice):",
    "  1) возьми ВТОРОЙ телефон и включи на нём точку доступа Wi-Fi;",
    "  2) на нём же поставь из Play Market приложение «DNS Changer»",
    "     и задай там DNS: " + ROOT_DNS + ";",
    "  3) в приложении «Дом с Алисой» на ДРУГОМ телефоне привязывай колонку",
    "     к этой точке доступа (пароль — от точки доступа).",
    "",
    "ШАГ 4. ТЕЛЕФОН: в приложении выбери свою Wi-Fi сеть, введи пароль",
    "  и жми «Подключиться». Колонка сходит на сервер разблокировки.",
    "",
    "Дальше всё само: я буду каждые 15 секунд проверять, не включился",
    "ли ADB, и как только root появится — закончу установку без тебя.",
    "",
    "ПОСЛЕ установки: верни на роутере DNS, какой был (иначе интернет не заработает).",
]


def log(text: str) -> None:
    print(f"==> {text}", flush=True)


def local_networks() -> list:
    probe = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
    try:
        probe.connect(("8.8.8.8", 80))
        local_ip = probe.getsockname()[0]
    except OSError:
        local_ip = "127.0.0.1"
    finally:
        probe.close()
    return [ipaddress.ip_network(f"{local_ip}/24", strict=False)]


def ping_port(ip: str, port: int, timeout: float = 0.35) -> bool:
    try:
        with socket.create_connection((ip, port), timeout=timeout):
            return True
    except OSError:
        return False


def scan_network(network: ipaddress.ip_network, ports: tuple) -> list:
    hosts = [str(h) for h in network.hosts()]
    log(f"Сканирую сеть {network} ({len(hosts)} адресов)...")
    found = []
    with ThreadPoolExecutor(max_workers=64) as pool:
        futures = {
            (ip, port): pool.submit(ping_port, ip, port)
            for ip in hosts for port in ports
        }
        for (ip, port), future in futures.items():
            if future.result():
                found.append((ip, port))
    return sorted(found, key=lambda pair: tuple(map(int, pair[0].split("."))))


def find_speaker() -> str | None:
    candidates = []
    for network in local_networks():
        candidates += scan_network(network, (ADB_PORT,) + SSH_PORTS + (PANEL_PORT,))
    if not candidates:
        return None
    adb_hosts = [ip for ip, port in candidates if port == ADB_PORT]
    if adb_hosts:
        return adb_hosts[0]
    print("\nНайдены узлы:")
    for ip, port in candidates:
        role = {PANEL_PORT: "панель Alice Brain", 22: "SSH", 2222: "SSH", 22222: "SSH"}.get(port, "?")
        print(f"  {ip}:{port}  {role}")
    return None


def _kill_adb() -> None:
    if sys.platform == "win32":
        subprocess.run(["taskkill", "/F", "/IM", "adb.exe"],
                       capture_output=True)
    else:
        subprocess.run(["pkill", "-f", "adb"], capture_output=True)


def _find_cached_adb() -> str | None:
    root = os.path.join(os.path.expanduser("~"), ".alice-tools")
    exe = ".exe" if sys.platform == "win32" else ""
    if not os.path.isdir(root):
        return None
    for name in sorted(os.listdir(root), reverse=True):
        p = os.path.join(root, name, "adb" + exe)
        if os.path.isfile(p):
            return p
    p = os.path.join(root, "adb" + exe)
    return p if os.path.isfile(p) else None


def ensure_adb() -> bool:
    global ADB_BIN
    if shutil.which("adb"):
        ADB_BIN = shutil.which("adb")
        return True
    cached = _find_cached_adb()
    if cached:
        ADB_BIN = cached
        return True
    url = PLATFORM_TOOLS.get(sys.platform)
    if not url:
        log("adb не найден в PATH — поставь platform-tools: https://developer.android.com/tools/releases/platform-tools")
        return False
    root = os.path.join(os.path.expanduser("~"), ".alice-tools")
    os.makedirs(root, exist_ok=True)
    zpath = os.path.join(root, "platform-tools.zip")
    log("adb не найден в PATH — скачиваю Android platform-tools (~10 МБ, один раз)...")
    try:
        try:
            urllib.request.urlretrieve(url, zpath)
        except PermissionError:
            _kill_adb()
            urllib.request.urlretrieve(url, zpath)
        extracted = False
        for attempt in range(3):
            target = os.path.join(root, f"platform-tools-{attempt}" if attempt else "platform-tools")
            try:
                with zipfile.ZipFile(zpath) as zf:
                    zf.extractall(target)
                extracted = True
                break
            except PermissionError:
                log("файл adb занят (висит старый adb) — перезапускаю...")
                _kill_adb()
        os.remove(zpath)
        if not extracted:
            log("не смог распаковать platform-tools — файл adb заблокирован")
            log("закрой другие окна установщика или перезагрузи ПК и запусти ещё раз")
            return False
    except Exception as exc:
        log(f"не смог скачать platform-tools: {exc}")
        log("поставь вручную: https://developer.android.com/tools/releases/platform-tools")
        return False
    exe = ".exe" if sys.platform == "win32" else ""
    ADB_BIN = os.path.join(target, "adb" + exe)
    if not os.path.isfile(ADB_BIN):
        log(f"platform-tools распакованы, но adb не найден: {ADB_BIN}")
        return False
    if sys.platform != "win32":
        os.chmod(ADB_BIN, os.stat(ADB_BIN).st_mode | stat.S_IXUSR | stat.S_IXGRP | stat.S_IXOTH)
        for f in ("fastboot", "mke2fs"):
            p = os.path.join(target, f)
            if os.path.isfile(p):
                os.chmod(p, os.stat(p).st_mode | stat.S_IXUSR | stat.S_IXGRP | stat.S_IXOTH)
    probe = subprocess.run([ADB_BIN, "version"], capture_output=True, text=True)
    if probe.returncode != 0:
        log("adb скачался, но не запускается (на Linux может не хватать libc-i386)")
        return False
    log(f"adb готов: {ADB_BIN}")
    return True


def run(cmd: list, **kwargs) -> subprocess.CompletedProcess:
    log(" ".join(cmd[:8]) + (" ..." if len(cmd) > 8 else ""))
    return subprocess.run(cmd, **kwargs)


def guide_root() -> None:
    print("\n" + "=" * 56)
    for line in ROOT_GUIDE:
        print(line)
    print("=" * 56 + "\n")


def wait_root(host: str, attempts: int = 20, delay: float = 15) -> bool:
    import time
    for attempt in range(attempts):
        log(f"жду root на колонке (попытка {attempt + 1}/{attempts}, следующая через {int(delay)} сек)...")
        time.sleep(delay)
        run([ADB_BIN, "connect", f"{host}:{ADB_PORT}"], capture_output=True, text=True)
        probe = subprocess.run([ADB_BIN, "-s", f"{host}:{ADB_PORT}", "shell", "id"],
                               capture_output=True, text=True)
        out = (probe.stdout or "") + (probe.stderr or "")
        if "uid=0" in out:
            log("ROOT ПОЛУЧЕН! Колонка разблокирована.")
            return True
    log("root так и не появился — проверь шаги выше (особенно DNS на роутере)")
    return False


def harden(host: str) -> None:
    s = f"{host}:{ADB_PORT}"
    log("Закрепляю ADB (root переживёт перезагрузки и обновления)")
    run([ADB_BIN, "-s", s, "shell",
         "mkdir -p /data/quasar && "
         "touch /data/quasar/activate_adb_quasmodrom /data/quasar/activate_network_adb && "
         "chattr +i /data/quasar/activate_adb_quasmodrom /data/quasar/activate_network_adb"])
    if run([ADB_BIN, "-s", s, "shell", "test -f /data/opt/yandex-noupdate.sh"]).returncode == 0:
        log("Обновления уже отключены — пропускаю")
        return
    log("Отключаю обновления Яндекса (чтобы root не закрылся)")
    kit = os.path.join(os.path.expanduser("~"), ".alice-tools")
    script = os.path.join(kit, "yandex-noupdate.sh")
    url = "https://raw.githubusercontent.com/Marker284/yandex-station-extended/main/contrib/yandex-noupdate.sh"
    try:
        urllib.request.urlretrieve(url, script)
    except Exception as exc:
        log(f"не смог скачать скрипт — обновления останутся включены (не критично): {exc}")
        return
    run([ADB_BIN, "-s", s, "push", script, "/data/opt/yandex-noupdate.sh"])
    if run([ADB_BIN, "-s", s, "shell", "sh /data/opt/yandex-noupdate.sh"]).returncode != 0:
        log("скрипт отключения обновлений вернул ошибку — продолжаю без него")
        return
    run([ADB_BIN, "-s", s, "pull", "/data/opt/backup", os.path.join(kit, "backup-kolonka")],
        stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
    log("перезагружаю колонку, чтобы всё закрепилось (2-3 мин)")
    run([ADB_BIN, "-s", s, "shell", "reboot"], capture_output=True)
    import time
    for _ in range(60):
        time.sleep(5)
        if ping_port(host, ADB_PORT):
            break
    run([ADB_BIN, "connect", s], capture_output=True)
    log("колонка вернулась в строй")


def push_via_adb(host: str) -> bool:
    if not ensure_adb():
        return False
    if not ping_port(host, ADB_PORT):
        log(f"На {host} нет открытого порта {ADB_PORT} (ADB по сети).")
        log("Root ADB сначала нужно включить на колонке — https://hackalice.me/start/root/")
        return False
    run([ADB_BIN, "connect", f"{host}:{ADB_PORT}"], capture_output=True, text=True)
    devices = run([ADB_BIN, "devices"], capture_output=True, text=True)
    state = ""
    for line in devices.stdout.splitlines():
        if line.startswith(f"{host}:{ADB_PORT}"):
            state = line.split()[-1]
            break
    if state == "unauthorized":
        log("Колонка подключена, но не авторизовала этот ПК (unauthorized)")
        guide_root()
        if not wait_root(host):
            return False
    if state == "offline":
        log("Колонка offline — переподключаю...")
        run([ADB_BIN, "disconnect", f"{host}:{ADB_PORT}"], capture_output=True)
        run([ADB_BIN, "connect", f"{host}:{ADB_PORT}"])
    probe = run([ADB_BIN, "-s", f"{host}:{ADB_PORT}", "shell", "echo", "ok"], capture_output=True, text=True)
    if probe.stdout.strip() != "ok":
        log("ADB не отвечает на команды")
        if probe.stderr.strip():
            log(f"причина: {probe.stderr.strip()}")
        if probe.stdout.strip():
            log(f"ответ: {probe.stdout.strip()}")
        guide_root()
        if not wait_root(host):
            return False
    harden(host)
    log(f"Копирую проект в {DEVICE_DIR} ...")
    if run([ADB_BIN, "-s", f"{host}:{ADB_PORT}", "shell", f"mkdir -p {DEVICE_DIR}"]).returncode != 0:
        log("mkdir вернул ошибку (нет прав?)")
        return False
    for item in os.listdir(PROJECT_ROOT):
        if item in SKIP_DIRS:
            continue
        run([ADB_BIN, "-s", f"{host}:{ADB_PORT}", "push", os.path.join(PROJECT_ROOT, item), DEVICE_DIR],
            stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
    run([ADB_BIN, "-s", f"{host}:{ADB_PORT}", "shell",
         f"su 0 sh {DEVICE_DIR}/tools/device_setup.sh || sh {DEVICE_DIR}/tools/device_setup.sh"])
    return True


def push_via_ssh(host: str, user: str) -> bool:
    if run(["ssh", "-o", "ConnectTimeout=5", "-o", "BatchMode=yes",
            f"{user}@{host}", "echo", "ok"], capture_output=True, text=True).stdout.strip() != "ok":
        log("SSH недоступен без пароля. Пропиши ключ: ssh-copy-id root@" + host)
        return False
    log(f"Копирую проект в {DEVICE_DIR} ...")
    run(["ssh", f"{user}@{host}", f"mkdir -p {DEVICE_DIR}"])
    run(["scp", "-r", *[os.path.join(PROJECT_ROOT, i) for i in os.listdir(PROJECT_ROOT) if i not in SKIP_DIRS],
         f"{user}@{host}:{DEVICE_DIR}"], stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
    run(["ssh", f"{user}@{host}", f"sh {DEVICE_DIR}/tools/device_setup.sh"])
    return True


def wait_panel(host: str, tries: int = 20) -> bool:
    import json
    url = f"http://{host}:{PANEL_PORT}/api/status"
    for _ in range(tries):
        try:
            with urllib.request.urlopen(url, timeout=3) as resp:
                status = json.loads(resp.read())
            log(f"Панель жива: {status['name']}, LLM-мозг: {'вкл' if status['llm'] else 'выкл'}")
            log(f"Открой с телефона: http://{host}:{PANEL_PORT}")
            return True
        except Exception:
            pass
    return False


def main() -> int:
    parser = argparse.ArgumentParser(description="Авто-установка Alice Brain на колонку по Wi-Fi")
    parser.add_argument("--host", help="IP колонки (если не указан — авто-поиск по сети)")
    parser.add_argument("--method", choices=("adb", "ssh"), default="adb")
    parser.add_argument("--user", default="root", help="пользователь SSH (по умолчанию root)")
    args = parser.parse_args()

    host = args.host or find_speaker()
    if not host:
        print("Колонка не найдена в сети. Укажи IP вручную: python alice_install.py --host 192.168.1.50")
        return 1
    log(f"Колонка: {host}")

    ok = push_via_adb(host) if args.method == "adb" else push_via_ssh(host, args.user)
    if not ok:
        print("\nАвтоматически не получилось. Ручной путь — README.md, раздел «Установка».")
        return 1
    if wait_panel(host):
        print("\nГотово! Скажи в микрофон: «Алиса» → «включи музыку»")
        return 0
    print("\nПроект установлен, но панель пока не отвечает — смотри журнал на колонке:")
    print(f"  {ADB_BIN} -s {host}:{ADB_PORT} shell cat /data/alice-brain/assistant.log")
    return 1


if __name__ == "__main__":
    sys.exit(main())
