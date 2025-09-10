from __future__ import annotations
import pyttsx3
import threading
import re

class Speech:
    def __init__(self, enabled: bool = True):
        self.enabled = enabled
        self._lock = threading.Lock()
        self.engine = pyttsx3.init()

        # ==== Standard-Einstellungen ====
        self._select_voice("matthias")  
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
            # Spezielle Behandlung für Uhrzeiten
            if "Es ist" in text and "Uhr" in text:
                # Text in einzelne Wörter zerlegen und nur die relevanten Teile behalten
                words = text.split()
                # Nur "Es ist X Uhr Y" behalten
                text = " ".join(words[:5]) if len(words) >= 5 else text
                
            self.engine.say(text)
            self.engine.runAndWait()
        except Exception as e:
            print(f"[Speech] Warnung: {e}")

    def set_enabled(self, on: bool):
        self.enabled = bool(on)
        