from __future__ import annotations
import queue, time, json
import sounddevice as sd
from vosk import Model, KaldiRecognizer

class SpeechIn:
    def __init__(self, lang: str = "de", model_path: str | None = None,
                 device: int | None = None, samplerate: int = 16000):
        self.device = device
        self.samplerate = samplerate
        try:
            # 1) Bequemer Weg (auto-download eines kleinen Modells, wenn verfügbar)
            if model_path is None:
                self.model = Model(lang=lang)
            else:
                # 2) Manuell lokales Modell nutzen: z.B. "models/vosk-model-small-de-0.15"
                self.model = Model(model_path)
        except Exception as e:
            raise RuntimeError(
                "Vosk-Modell konnte nicht geladen werden. Entweder Internet (für auto-download) "
                "bereitstellen oder 'model_path' auf lokalen Model-Ordner setzen.\n"
                f"Grund: {e}"
            )

    def listen_once(self, max_seconds: float = 8.0) -> str | None:
        rec = KaldiRecognizer(self.model, self.samplerate)
        q = queue.Queue()

        def _cb(indata, frames, time_info, status):
            if status:  # Status könnte geloggt werden
                pass
            q.put(bytes(indata))

        # 8000 Frames @16kHz ≈ 0,5 s Blöcke
        with sd.RawInputStream(samplerate=self.samplerate, blocksize=8000,
                               dtype='int16', channels=1, callback=_cb, device=self.device):
            start = time.time()
            final_text = ""
            while True:
                if (time.time() - start) > max_seconds:
                    break
                data = q.get()
                if rec.AcceptWaveform(data):
                    res = json.loads(rec.Result())
                    final_text = (res.get("text") or "").strip()
                    break

            if not final_text:
                # Finale Resthypothese
                try:
                    res = json.loads(rec.FinalResult())
                    final_text = (res.get("text") or "").strip()
                except Exception:
                    final_text = ""

            return final_text or None

    @staticmethod
    def list_input_devices() -> None:
        for i, dev in enumerate(sd.query_devices()):
            if dev.get("max_input_channels", 0) > 0:
                print(f"[{i}] {dev['name']}")