# fox/speech_in.py
from __future__ import annotations
import queue, time, json
import sounddevice as sd
from vosk import Model, KaldiRecognizer

def _detect_samplerate(device: int | None) -> int:
    """Ermittle eine sinnvolle Samplerate aus dem Gerät; fallback 16000."""
    try:
        if device is None:
            devinfo = sd.query_devices(kind='input')
        else:
            devinfo = sd.query_devices(device)
        # Bevorzugt 16000 (Vosk-Standard). Wenn Gerät niedriger/komisch ist, nimm 44100/48000.
        candidates = [16000, 44100, 48000]
        for sr in candidates:
            # Viele Treiber akzeptieren jede Rate – wir testen mit None, wählen einfach die erste.
            return sr
    except Exception:
        pass
    return 16000

class SpeechIn:
    def __init__(self, lang: str = "de", model_path: str | None = None,
                 device: int | None = None, samplerate: int | None = None):
        self.device = device
        self.samplerate = samplerate or _detect_samplerate(device)

        # Vosk-Modell laden (Auto-Download für lang="de" oder lokaler Ordner)
        try:
            if model_path is None:
                # Auto: kleines Sprachmodell nachlädt (Internet nötig). Alternativ lokalen Ordner setzen.
                self.model = Model(lang=lang)
            else:
                self.model = Model(model_path)
        except Exception as e:
            raise RuntimeError(
                "Vosk-Modell konnte nicht geladen werden.\n"
                "Optionen:\n"
                "  1) Internet erlauben (Model(lang='de')).\n"
                "  2) Lokales Modell laden und model_path setzen (z.B. 'models/vosk-model-small-de-0.15').\n"
                f"Grund: {e}"
            )

    def listen_once(self, max_seconds: float = 8.0) -> str | None:
        """Hört einmal bis max_seconds zu und gibt erkannten Text zurück (oder None)."""
        rec = KaldiRecognizer(self.model, self.samplerate)
        q = queue.Queue()

        def _cb(indata, frames, time_info, status):
            if status:
                # Status (XRuns etc.) ignorieren, aber nicht crashen
                pass
            q.put(bytes(indata))

        blocksize = max(int(self.samplerate // 2), 8000)  # ~0.5s

        try:
            with sd.RawInputStream(
                samplerate=self.samplerate,
                blocksize=blocksize,
                dtype='int16',
                channels=1,
                callback=_cb,
                device=self.device
            ):
                start = time.time()
                final_text = ""
                while time.time() - start <= max_seconds:
                    try:
                        data = q.get(timeout=1.0)
                    except Exception:
                        continue
                    if rec.AcceptWaveform(data):
                        res = json.loads(rec.Result())
                        final_text = (res.get("text") or "").strip()
                        if final_text:
                            break

                if not final_text:
                    try:
                        res = json.loads(rec.FinalResult())
                        final_text = (res.get("text") or "").strip()
                    except Exception:
                        final_text = ""

                return final_text or None
        except Exception as e:
            raise RuntimeError(
                "Audio-Stream konnte nicht geöffnet werden. Prüfe:\n"
                " - Mikrofonberechtigungen in Windows\n"
                " - Ob ein anderes Programm das Mikro blockiert\n"
                " - Den Geräteindex (nutze 'mikro geraete' & 'mikro device <n>')\n"
                f"Technischer Fehler: {e}"
            )

    @staticmethod
    def list_input_devices() -> None:
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
            print(f"Geräteliste fehlgeschlagen: {e}")

if __name__ == "__main__":
    import sys
    if len(sys.argv) > 1 and sys.argv[1] == "list":
        SpeechIn.list_input_devices()
