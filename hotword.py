from __future__ import annotations
import os, sys, time
import requests

from fox.speech.speech_in import SpeechIn
from fox.speech.speech_out import Speech

USE_SERVER   = True
SERVER_URL   = os.getenv("FOX_SERVER_URL", "http://127.0.0.1:8010/handle")
LANG         = os.getenv("FOX_LANG", "de")
DEVICE_INDEX = os.getenv("FOX_MIC", None)
MAX_HOTWORD_WINDOW = 4.0
MAX_COMMAND_WINDOW = 10.0
HOTWORDS = ("hey fox", "hey fuchs", "hi fox", "hallo fox")

fox = None
if not USE_SERVER:
    from main import FoxAssistant
    fox = FoxAssistant()

def contains_hotword(text: str) -> bool:
    t = (text or "").strip().lower()
    if not t: return False
    return any(hw in t for hw in HOTWORDS)

def ask_server(text: str) -> str:
    try:
        r = requests.post(SERVER_URL, json={"text": text}, timeout=20)
        if r.ok:
            data = r.json()
            return (data.get("reply") or "").strip()
        return f"Server-Fehler: {r.status_code}"
    except Exception as e:
        return f"Server nicht erreichbar: {e}"

def main():
    device = int(DEVICE_INDEX) if DEVICE_INDEX and DEVICE_INDEX.isdigit() else None
    mic = SpeechIn(lang=LANG, model_path=None, device=device)
    tts = Speech(enabled=True)
    tts.say("Hotword aktiviert.")

    while True:
        try:
            hot = mic.listen_once(max_seconds=MAX_HOTWORD_WINDOW)
            if not hot or not contains_hotword(hot):
                continue
            tts.say("Ja?")
            cmd = mic.listen_once(max_seconds=MAX_COMMAND_WINDOW)
            if not cmd:
                tts.say("Ich habe nichts verstanden.")
                continue
            reply = ask_server(cmd) if USE_SERVER else fox.handle(cmd)
            print(f"[User]: {cmd}")
            print(f"[Fox ]: {reply}")
            tts.say(reply)
        except KeyboardInterrupt:
            tts.say("Hotword aus.")
            break
        except Exception as e:
            print(f"[Hotword] Warnung: {e}")
            time.sleep(0.5)

if __name__ == "__main__":
    main()
