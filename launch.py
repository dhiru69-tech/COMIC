"""
COMIC — Biometric Intelligence Platform
Launch Script v3.0
"""

import subprocess, threading, sys, os, time, shutil, platform
import urllib.request, stat, re, itertools

# ── Terminal colours ────────────────────────────────────────────
R   = "\033[0m"
B   = "\033[1m"
DIM = "\033[2m"
IT  = "\033[3m"

BLK = "\033[30m"
RED = "\033[91m"
GRN = "\033[92m"
YLW = "\033[93m"
BLU = "\033[94m"
MGT = "\033[95m"
CYN = "\033[96m"
WHT = "\033[97m"

BG_BLK = "\033[40m"

PORT   = 8080
DIR    = os.path.dirname(os.path.abspath(__file__))
SERVER = os.path.join(DIR, "server.py")

# ── Helpers ─────────────────────────────────────────────────────

def clear():
    os.system("cls" if platform.system() == "Windows" else "clear")

def move_up(n=1):
    sys.stdout.write(f"\033[{n}A\033[2K")

def hide_cursor():
    sys.stdout.write("\033[?25l"); sys.stdout.flush()

def show_cursor():
    sys.stdout.write("\033[?25h"); sys.stdout.flush()

def sleep(s):
    time.sleep(s)

def write(text, delay=0):
    if delay:
        for ch in text:
            sys.stdout.write(ch); sys.stdout.flush(); time.sleep(delay)
    else:
        sys.stdout.write(text); sys.stdout.flush()

def println(text="", delay=0):
    write(text + "\n", delay)

# ── ASCII Logo ───────────────────────────────────────────────────

LOGO = f"""{MGT}{B}
   ██████╗ ██████╗ ███╗   ███╗██╗ ██████╗
  ██╔════╝██╔═══██╗████╗ ████║██║██╔════╝
  ██║     ██║   ██║██╔████╔██║██║██║
  ██║     ██║   ██║██║╚██╔╝██║██║██║
  ╚██████╗╚██████╔╝██║ ╚═╝ ██║██║╚██████╗
   ╚═════╝ ╚═════╝ ╚═╝     ╚═╝╚═╝ ╚═════╝{R}"""

TAGLINE = f"  {DIM}{IT}Biometric Intelligence Platform  ·  v3.0{R}"

BORDER_TOP    = f"  {DIM}{'─' * 58}{R}"
BORDER_MID    = f"  {DIM}{'─' * 58}{R}"

# ── Spinner ──────────────────────────────────────────────────────

class Spinner:
    FRAMES = ["⠋","⠙","⠹","⠸","⠼","⠴","⠦","⠧","⠇","⠏"]

    def __init__(self, label):
        self.label   = label
        self._stop   = threading.Event()
        self._thread = threading.Thread(target=self._run, daemon=True)

    def _run(self):
        hide_cursor()
        for frame in itertools.cycle(self.FRAMES):
            if self._stop.is_set(): break
            write(f"\r  {MGT}{frame}{R}  {WHT}{self.label}{R}  ")
            sleep(0.08)

    def start(self):
        self._thread.start()
        return self

    def done(self, msg=""):
        self._stop.set()
        self._thread.join()
        write(f"\r  {GRN}✔{R}  {WHT}{msg or self.label}{R}  \n")
        show_cursor()

    def fail(self, msg=""):
        self._stop.set()
        self._thread.join()
        write(f"\r  {RED}✘{R}  {WHT}{msg or self.label}{R}  \n")
        show_cursor()

# ── Intro animation ──────────────────────────────────────────────

def show_intro():
    clear()
    hide_cursor()
    sleep(0.05)

    for line in LOGO.split("\n"):
        println(line)
        sleep(0.04)

    sleep(0.1)
    println(TAGLINE)
    sleep(0.2)
    println(BORDER_TOP)
    sleep(0.1)
    show_cursor()

# ── Main menu ────────────────────────────────────────────────────

MENU_ITEMS = [
    {
        "key":   "1",
        "title": "Local",
        "sub":   f"http://localhost:{PORT}",
        "desc":  "Only you can access. No HTTPS required.",
        "note":  None,
    },
    {
        "key":   "2",
        "title": "Cloudflare Tunnel",
        "sub":   "Public HTTPS URL — auto-generated",
        "desc":  "Share with anyone. Fixes camera in all browsers.",
        "note":  "Requires cloudflared (auto-installed if missing)",
    },
    {
        "key":   "3",
        "title": "Exit",
        "sub":   "",
        "desc":  "Quit the launcher.",
        "note":  None,
    },
]

def print_menu():
    println()
    println(f"  {WHT}{B}  SELECT LAUNCH MODE{R}")
    println(f"  {DIM}{'─' * 58}{R}")
    println()

    for item in MENU_ITEMS:
        key   = item["key"]
        title = item["title"]
        sub   = item["sub"]
        desc  = item["desc"]
        note  = item["note"]

        println(f"  {DIM}[{R}{WHT}{B}{key}{R}{DIM}]{R}  {WHT}{B}{title}{R}  {DIM}{sub}{R}")
        println(f"       {DIM}{IT}{desc}{R}")
        if note:
            println(f"       {DIM}{YLW}{note}{R}")
        println()

    println(f"  {DIM}{'─' * 58}{R}")
    println()


def get_choice():
    valid = {item["key"] for item in MENU_ITEMS}
    while True:
        try:
            write(f"  {DIM}>{R}  {WHT}Enter option [{'/'.join(valid)}]{R}:  ")
            choice = input().strip()
            if choice in valid:
                return choice
            println(f"  {YLW}Invalid option — enter {'/'.join(sorted(valid))}{R}")
        except (KeyboardInterrupt, EOFError):
            println()
            return "3"

# ── cloudflared install ──────────────────────────────────────────

def ensure_cloudflared():
    if shutil.which("cloudflared"):
        return True

    sys_p = platform.system()
    println()
    println(f"  {YLW}{B}cloudflared not found — auto-installing...{R}")
    println()

    sp = Spinner("Installing cloudflared").start()

    try:
        if sys_p == "Darwin":
            if shutil.which("brew"):
                subprocess.check_call(
                    ["brew", "install", "cloudflared"],
                    stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL
                )
            else:
                sp.fail("Homebrew not found")
                println(f"\n  Install Homebrew first:\n  {CYN}https://brew.sh{R}\n")
                return False

        elif sys_p == "Windows":
            if shutil.which("winget"):
                subprocess.check_call(
                    ["winget", "install", "--id", "Cloudflare.cloudflared",
                     "-e", "--silent", "--accept-package-agreements",
                     "--accept-source-agreements"],
                    stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL
                )
            else:
                # Direct binary download
                url  = "https://github.com/cloudflare/cloudflared/releases/latest/download/cloudflared-windows-amd64.exe"
                dest = os.path.join(DIR, "cloudflared.exe")
                urllib.request.urlretrieve(url, dest)
                os.environ["PATH"] = DIR + os.pathsep + os.environ.get("PATH","")

        elif sys_p == "Linux":
            if shutil.which("snap"):
                subprocess.check_call(
                    ["sudo", "snap", "install", "cloudflared", "--classic"],
                    stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL
                )
            elif shutil.which("apt-get"):
                subprocess.check_call(
                    ["sudo", "apt-get", "install", "-y", "cloudflared"],
                    stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL
                )
            else:
                url  = "https://github.com/cloudflare/cloudflared/releases/latest/download/cloudflared-linux-amd64"
                dest = os.path.join(DIR, "cloudflared")
                urllib.request.urlretrieve(url, dest)
                os.chmod(dest, os.stat(dest).st_mode | stat.S_IEXEC | stat.S_IXGRP | stat.S_IXOTH)
                os.environ["PATH"] = DIR + os.pathsep + os.environ.get("PATH","")
        else:
            sp.fail("Unsupported OS")
            println(f"\n  Download manually: {CYN}https://developers.cloudflare.com/cloudflared/install/{R}\n")
            return False

        sp.done("cloudflared installed")
        return True

    except Exception as e:
        sp.fail(f"Install failed: {e}")
        return False

# ── Launch modes ─────────────────────────────────────────────────

def launch_local():
    clear()
    show_intro()
    println()
    println(f"  {GRN}{B}  STARTING LOCAL SERVER{R}")
    println(f"  {DIM}{'─' * 58}{R}")
    println()

    sp = Spinner("Booting server.py").start()
    sleep(0.8)
    sp.done(f"Server ready  →  {CYN}http://localhost:{PORT}{R}")

    println()
    println(f"  {DIM}Open your browser and go to:{R}")
    println(f"  {CYN}{B}  http://localhost:{PORT}{R}")
    println()
    println(f"  {DIM}Press Ctrl + C to stop{R}")
    println()
    println(f"  {DIM}{'─' * 58}{R}")
    println()

    try:
        subprocess.call([sys.executable, SERVER])
    except KeyboardInterrupt:
        println(f"\n\n  {YLW}Server stopped.{R}\n")

def launch_tunnel():
    clear()
    show_intro()
    println()
    println(f"  {MGT}{B}  STARTING CLOUDFLARE TUNNEL{R}")
    println(f"  {DIM}{'─' * 58}{R}")
    println()

    if not ensure_cloudflared():
        println(f"\n  {RED}Cannot start tunnel without cloudflared.{R}\n")
        input(f"  {DIM}Press Enter to return to menu...{R}")
        return

    # Start local server in background
    server_proc = subprocess.Popen(
        [sys.executable, SERVER],
        stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL
    )

    sleep(1.0)  # let server bind

    sp = Spinner("Establishing Cloudflare Tunnel").start()

    tunnel_proc = subprocess.Popen(
        ["cloudflared", "tunnel", "--url", f"http://localhost:{PORT}"],
        stdout=subprocess.PIPE, stderr=subprocess.STDOUT,
        text=True, bufsize=1
    )

    public_url = None
    for line in tunnel_proc.stdout:
        urls = re.findall(r"https://[a-z0-9\-]+\.trycloudflare\.com", line)
        if urls:
            public_url = urls[0]
            break

    sp.done("Tunnel established")

    println()
    println(f"  {DIM}{'─' * 58}{R}")
    println()
    println(f"  {GRN}{B}  PUBLIC URL READY{R}")
    println()
    println(f"  {WHT}Open in any browser:{R}")
    println()
    println(f"  {CYN}{B}  {public_url}{R}")
    println()
    println(f"  {DIM}Camera works in all browsers (HTTPS enabled){R}")
    println(f"  {DIM}Share this link with anyone on the internet{R}")
    println()
    println(f"  {DIM}{'─' * 58}{R}")
    println()
    println(f"  {DIM}Press Ctrl + C to stop{R}")
    println()

    try:
        tunnel_proc.wait()
    except KeyboardInterrupt:
        tunnel_proc.terminate()
        server_proc.terminate()
        println(f"\n\n  {YLW}Tunnel and server stopped.{R}\n")

# ── Entry point ──────────────────────────────────────────────────

def main():
    try:
        show_intro()
        print_menu()
        choice = get_choice()

        if choice == "1":
            launch_local()
        elif choice == "2":
            launch_tunnel()
        elif choice == "3":
            clear()
            println(f"\n  {DIM}Goodbye.{R}\n")

    except KeyboardInterrupt:
        show_cursor()
        println(f"\n\n  {YLW}Interrupted.{R}\n")
        sys.exit(0)
    finally:
        show_cursor()

if __name__ == "__main__":
    main()
