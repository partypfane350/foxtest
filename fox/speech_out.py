from __future__ import annotations
import pyttsx3
import threading

class Speech:
    def __init__(self, enabled: bool = True):
        self.enabled = enabled
        self._lock = threading.Lock()
        self.engine = pyttsx3.init()

        # ==== Standard-Einstellungen ====
        self._select_voice("stefan")      
        try:
            self.engine.setProperty("rate", 190)    
            self.engine.setProperty("volume", 0.9)  
        except Exception:
            pass

    def _select_voice(self, hint: str):
        """Stimme nach Teilstring auswählen (z. B. 'stefan')."""
        hint = (hint or "").lower()
        try:
            voices = self.engine.getProperty("voices")
            # Desktop-Stimmen bevorzugen
            preferred = [v for v in voices if "desktop" in (getattr(v,"name","")+getattr(v,"id","")).lower()]
            pool = preferred + [v for v in voices if v not in preferred]
            for v in pool:
                text = f"{getattr(v,'id','')} {getattr(v,'name','')}".lower()
                if hint in text:
                    self.engine.setProperty("voice", v.id)
                    return
        except Exception:
            pass

    def say(self, text: str):
        """Synchron: Spricht den Text (wenn enabled)."""
        if not self.enabled or not text:
            return
        with self._lock:
            try:
                self.engine.setProperty("rate", 190)
                self.engine.setProperty("volume", 0.9)
                self.engine.stop()
            except Exception:
                pass
            try:
                self.engine.say(str(text))
                self.engine.runAndWait()
            except Exception as e:
                print(f"[Speech] Warnung: {e}")

    def set_enabled(self, on: bool):
        self.enabled = bool(on)
        