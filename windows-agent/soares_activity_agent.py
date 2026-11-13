import ctypes
import csv
import io
import json
import os
import subprocess
import time
import urllib.request
from pathlib import Path

API_BASE = "https://soares-reserva-ai-heloysa.onrender.com"
CONFIG_PATH = Path(__file__).with_name("agent_config.json")
POLL_SECONDS = 8

# Process names used by common Windows games and launchers.
GAMES = {
    "gta5.exe": "GTA V",
    "gta5_enhanced.exe": "GTA V Enhanced",
    "fivem.exe": "FiveM",
    "ragemp_v.exe": "GTA RP (RAGE Multiplayer)",
    "robloxplayerbeta.exe": "Roblox",
    "valorant-win64-shipping.exe": "VALORANT",
    "cs2.exe": "Counter-Strike 2",
    "csgo.exe": "Counter-Strike",
    "league of legends.exe": "League of Legends",
    "leagueclient.exe": "League of Legends",
    "fortniteclient-win64-shipping.exe": "Fortnite",
    "overwatch.exe": "Overwatch",
    "minecraft.exe": "Minecraft",
    "javaw.exe": "Minecraft / Java",
    "rocketleague.exe": "Rocket League",
    "r5apex.exe": "Apex Legends",
    "eldenring.exe": "Elden Ring",
    "palworld-win64-shipping.exe": "Palworld",
    "deadbydaylight-win64-shipping.exe": "Dead by Daylight",
    "among us.exe": "Among Us",
    "phasmophobia.exe": "Phasmophobia",
    "destiny2.exe": "Destiny 2",
    "rainbowsix.exe": "Rainbow Six Siege",
    "rainbow6.exe": "Rainbow Six Siege",
    "pubg.exe": "PUBG",
    "escapefromtarkov.exe": "Escape from Tarkov",
}

def load_config():
    if not CONFIG_PATH.exists():
        print("Crie agent_config.json ao lado deste arquivo com api_token e agent_token.")
        input("Pressione Enter para sair...")
        raise SystemExit(1)
    config = json.loads(CONFIG_PATH.read_text(encoding="utf-8"))
    if not config.get("agent_token"):
        raise SystemExit("O campo agent_token está vazio no agent_config.json.")
    return config

def foreground_process_name():
    hwnd = ctypes.windll.user32.GetForegroundWindow()
    if not hwnd:
        return ""
    pid = ctypes.c_ulong()
    ctypes.windll.user32.GetWindowThreadProcessId(hwnd, ctypes.byref(pid))
    if not pid.value:
        return ""
    try:
        output = subprocess.check_output(
            ["tasklist", "/FO", "CSV", "/NH", "/FI", f"PID eq {pid.value}"],
            text=True, encoding="utf-8", errors="replace",
            creationflags=getattr(subprocess, "CREATE_NO_WINDOW", 0),
        )
        rows = list(csv.reader(io.StringIO(output)))
        return rows[0][0].lower() if rows and rows[0] else ""
    except Exception:
        return ""

def send_status(token, playing, game):
    payload = json.dumps({
        "is_playing": playing,
        "game": game,
        "source": "automatic"
    }).encode("utf-8")
    request = urllib.request.Request(
        API_BASE + "/activity/agent",
        data=payload,
        headers={"Content-Type": "application/json", "X-Agent-Token": token},
        method="POST",
    )
    with urllib.request.urlopen(request, timeout=15) as response:
        response.read()

def main():
    config = load_config()
    token = config["agent_token"]
    print("Soares Reserva AI — detector de jogos do Windows")
    print("Detectando o jogo em primeiro plano. Deixe esta janela aberta.")
    last = None
    while True:
        process = foreground_process_name()
        game = GAMES.get(process, "")
        state = (bool(game), game)
        if state != last:
            try:
                send_status(token, state[0], state[1])
                print("Jogando: " + game if game else "Nenhum jogo detectado.")
                last = state
            except Exception as exc:
                print("Falha ao atualizar status:", exc)
        time.sleep(POLL_SECONDS)

if __name__ == "__main__":
    if os.name != "nt":
        raise SystemExit("Este agente funciona apenas no Windows.")
    try:
        main()
    except KeyboardInterrupt:
        print("\nDetector encerrado.")
