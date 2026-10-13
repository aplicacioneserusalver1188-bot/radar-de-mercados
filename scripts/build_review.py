"""Prepara una copia estática independiente para revisar el tablero sin GitHub Pages."""
import shutil
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
DIST = ROOT / "dist"

def main():
    if DIST.exists():
        shutil.rmtree(DIST)
    (DIST / "data").mkdir(parents=True)
    (DIST / ".openai").mkdir()
    shutil.copy2(ROOT / "index.html", DIST / "index.html")
    shutil.copy2(ROOT / "data" / "market.json", DIST / "data" / "market.json")
    shutil.copy2(ROOT / ".openai" / "hosting.json", DIST / ".openai" / "hosting.json")

if __name__ == "__main__":
    main()
