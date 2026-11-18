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
import subprocess
import sys
import urllib.request
from concurrent.futures import ThreadPoolExecutor

PROJECT_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
SKIP_DIRS = {".git", "__pycache__", ".venv", "node_modules"}
ADB_PORT = 5555
SSH_PORTS = (22, 2222, 22222)
PANEL_PORT = 8080
DEVICE_DIR = "/data/alice-brain"


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


def run(cmd: list, **kwargs) -> subprocess.CompletedProcess:
    log(" ".join(cmd[:8]) + (" ..." if len(cmd) > 8 else ""))
    return subprocess.run(cmd, **kwargs)


def push_via_adb(host: str) -> bool:
    if shutil.which("adb") is None:
        log("adb не найден в PATH — установи platform-tools (https://developer.android.com/tools/releases/platform-tools)")
        return False
    if not ping_port(host, ADB_PORT):
        log(f"На {host} нет открытого порта {ADB_PORT} (ADB по сети).")
        log("Root ADB сначала нужно включить на колонке — https://hackalice.me/start/root/")
        return False
    run(["adb", "connect", f"{host}:{ADB_PORT}"])
    probe = run(["adb", "-s", f"{host}:{ADB_PORT}", "shell", "echo", "ok"], capture_output=True, text=True)
    if probe.stdout.strip() != "ok":
        log("ADB не отвечает: доступ не root или порт закрыт")
        return False
    log(f"Копирую проект в {DEVICE_DIR} ...")
    if run(["adb", "-s", f"{host}:{ADB_PORT}", "shell", f"mkdir -p {DEVICE_DIR}"]).returncode != 0:
        log("mkdir вернул ошибку (нет прав?)")
        return False
    for item in os.listdir(PROJECT_ROOT):
        if item in SKIP_DIRS:
            continue
        run(["adb", "-s", f"{host}:{ADB_PORT}", "push", os.path.join(PROJECT_ROOT, item), DEVICE_DIR],
            stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
    run(["adb", "-s", f"{host}:{ADB_PORT}", "shell",
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
    print(f"  adb -s {host}:{ADB_PORT} shell cat /data/alice-brain/assistant.log")
    return 1


if __name__ == "__main__":
    sys.exit(main())
