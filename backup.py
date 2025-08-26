from __future__ import annotations
from pathlib import Path
from datetime import datetime
import shutil

# Standard-Zielordner für Snapshots, z. B. <projekt>/backups/2025-08-26_10-55-12/
BACKUP_ROOT = Path("backups")

def _ts() -> str:
    return datetime.now().strftime("%Y-%m-%d_%H-%M-%S")

def make_snapshot(files_or_dirs, tag: str | None = None) -> Path:
    """
    Erstellt einen Zeitstempel-Ordner und kopiert alle angegebenen Dateien/Ordner hinein.
    - files_or_dirs: Iterable[Path | str]
    - tag: optionaler Zusatz wie 'learn', 'manual', 'autosave'
    """
    BACKUP_ROOT.mkdir(parents=True, exist_ok=True)
    folder_name = _ts() + (f"_{tag}" if tag else "")
    dest = BACKUP_ROOT / folder_name
    dest.mkdir(parents=True, exist_ok=True)

    for item in files_or_dirs:
        p = Path(item)
        if not p.exists():
            continue
        if p.is_file():
            shutil.copy2(p, dest / p.name)
        else:
            shutil.copytree(p, dest / p.name, dirs_exist_ok=True)

    return dest
