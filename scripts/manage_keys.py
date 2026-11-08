"""Uso: python scripts/manage_keys.py create <key_id> <sociedad,...> | revoke <key_id> | list
La clave en claro se muestra UNA vez; guarde solo el JSON con hashes como secreto montado."""
import json
import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from app.auth.api_keys import generate_key

PATH = Path("config/api_keys.json")


def load() -> dict:
    return json.loads(PATH.read_text()) if PATH.exists() else {"keys": []}


def main() -> None:
    cmd, data = sys.argv[1], load()
    if cmd == "create":
        kid, socs = sys.argv[2], [int(s) for s in sys.argv[3].split(",")]
        raw, h = generate_key(kid)
        data["keys"] = [k for k in data["keys"] if k["key_id"] != kid]  # rotación = recrear
        data["keys"].append({"key_id": kid, "hash": h, "sociedades": socs, "rate_per_hour": 100, "active": True})
        print(f"Clave (copiar ahora, no se volverá a mostrar): {raw}")
    elif cmd == "revoke":
        for k in data["keys"]:
            if k["key_id"] == sys.argv[2]:
                k["active"] = False
    elif cmd == "list":
        for k in data["keys"]:
            print(k["key_id"], k["sociedades"], "activa" if k["active"] else "revocada")
        return
    PATH.write_text(json.dumps(data, indent=2))


if __name__ == "__main__":
    main()
