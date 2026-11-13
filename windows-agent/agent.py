import json, time, sys
from pathlib import Path
import psutil, requests

CONFIG = Path(__file__).with_name("config.json")
if not CONFIG.exists():
    print("Crie config.json a partir de config.example.json e configure o token.")
    sys.exit(1)
cfg = json.loads(CONFIG.read_text(encoding="utf-8"))
base = cfg["api_base"].rstrip("/")
token = cfg["token"]
names = {x.lower() for x in cfg.get("process_names", [])}
poll = max(3, int(cfg.get("poll_seconds", 8)))
headers = {"Authorization": f"Bearer {token}", "Content-Type":"application/json"}
last = None
print("Soares Reserva AI — agente de atividade iniciado. Ctrl+C para sair.")
while True:
    try:
        found = ""
        for proc in psutil.process_iter(["name"]):
            try:
                name = proc.info.get("name") or ""
                if name.lower() in names:
                    found = name.removesuffix(".exe")
                    break
            except (psutil.NoSuchProcess, psutil.AccessDenied):
                continue
        state = (bool(found), found)
        if state != last:
            response = requests.post(base+"/activity", headers=headers,
                                     json={"is_playing":state[0],"game":state[1],"source":"automatic"},
                                     timeout=10)
            response.raise_for_status()
            print(("Jogando: "+found) if found else "Nenhum jogo detectado.")
            last = state
    except requests.RequestException as exc:
        print("Falha ao atualizar status:", exc)
    except KeyboardInterrupt:
        break
    time.sleep(poll)
