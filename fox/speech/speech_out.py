from __future__ import annotations
import pyttsx3
import threading

class Speech:
    def __init__(self, enabled: bool = True):
        self.enabled = enabled
        self._lock = threading.Lock()
        self.engine = pyttsx3.init()

        # Stimme setzen (männliche bevorzugt)
        self._force_male_voice()

        # Grundeinstellungen
        try:
            self.engine.setProperty("rate", 190)    # Geschwindigkeit
            self.engine.setProperty("volume", 0.6)  # Lautstärke
        except Exception:
            pass

    def _force_male_voice(self):
        """Versucht eine männliche Stimme auszuwählen (z. B. Stefan, David)."""
        try:
            voices = self.engine.getProperty("voices")
            for v in voices:
                text = f"{getattr(v,'id','')} {getattr(v,'name','')}".lower()
                if any(hint in text for hint in ["male", "stefan", "david"]):
                    self.engine.setProperty("voice", v.id)
                    print(f"[Speech] Stimme gesetzt: {v.name}")
                    return
            print("[Speech] Keine männliche Stimme gefunden, benutze Standard.")
        except Exception as e:
            print(f"[Speech] Fehler bei der Stimmauswahl: {e}")

    def say(self, text: str):
        """Spricht den gegebenen Text."""
        if not self.enabled or not text:
            return
        with self._lock:
            try:
                self.engine.stop()
                self.engine.say(text)
                self.engine.runAndWait()
            except Exception as e:
                print(f"[Speech] Warnung: {e}")

    def set_enabled(self, on: bool):
        """Sprache an- oder ausschalten."""
        self.enabled = bool(on)


# Beispiel:
if __name__ == "__main__":
    speech = Speech()
    speech.say("Hallo, ich bin eine männliche Stimme – wenn verfügbar.")
