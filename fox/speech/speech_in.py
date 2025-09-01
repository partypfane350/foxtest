# fox/speech_in.py (Whisper Version mit ffmpeg-Pfad Fix)
from __future__ import annotations
import os, sounddevice as sd, numpy as np
import whisper

# ---- ffmpeg automatisch einbinden ----
USER = os.environ.get("USERNAME") or "User"
FFMPEG_PATH = fr"C:\Users\{USER}\ffmpeg\bin"
if os.path.isdir(FFMPEG_PATH):
    os.environ["PATH"] = FFMPEG_PATH + ";" + os.environ["PATH"]

class SpeechIn:
    def __init__(self, model_name: str = "small", lang: str = "de"):
        """
        Whisper-basiertes SpeechIn.
        model_name: tiny, base, small, medium, large
        lang: Sprachkürzel (z. B. 'de', 'en')
        """
        self.lang = lang
        print(f"[Whisper] Lade Modell '{model_name}' … (einmalig, kann dauern)")
        self.model = whisper.load_model(model_name)

    def listen_once(self, max_seconds: float = 8.0, samplerate: int = 16000) -> str | None:
        """
        Nimmt max_seconds Audio auf und transkribiert mit Whisper.
        """
        print("Sag etwas … (Whisper hört zu)")
        try:
            recording = sd.rec(int(max_seconds * samplerate),
                               samplerate=samplerate,
                               channels=1, dtype="float32")
            sd.wait()

            audio = np.squeeze(recording)
            if not audio.any():
                return None

            result = self.model.transcribe(audio, language=self.lang)
            text = (result.get("text") or "").strip()
            return text if text else None
        except Exception as e:
            print(f"[Whisper] Fehler bei Aufnahme/Erkennung: {e}")
            return None

    @staticmethod
    def list_input_devices() -> None:
        """Listet verfügbare Eingabegeräte (Mikrofone)."""
        try:
            default_in = None
            try:
                default_in = sd.default.device[0]
            except Exception:
                pass
            for i, dev in enumerate(sd.query_devices()):
                if dev.get("max_input_channels", 0) > 0:
                    mark = " (Default)" if default_in is not None and i == default_in else ""
                    sr = dev.get("default_samplerate", "n/a")
                    print(f"[{i}] {dev['name']}  | ch_in={dev.get('max_input_channels')}  | sr={sr}{mark}")
            if default_in is not None:
                print(f"Default input device index: {default_in}")
        except Exception as e:
            print(f"[Whisper] Geräteliste fehlgeschlagen: {e}")


if __name__ == "__main__":
    s = SpeechIn(model_name="small", lang="de")
    txt = s.listen_once(max_seconds=5)
    print("Erkannt:", txt)
