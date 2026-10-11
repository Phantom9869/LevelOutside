import argparse, shutil, subprocess, sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

from leveloutside.card import render_card
from leveloutside.games import get_profile
from leveloutside.llm import make_generator
from leveloutside.pipeline import generate_with_retries
from leveloutside.validator import MissionContext


def find_browser():
    for p in (
        r"C:\Program Files (x86)\Microsoft\Edge\Application\msedge.exe",
        r"C:\Program Files\Microsoft\Edge\Application\msedge.exe",
        r"C:\Program Files\Google\Chrome\Application\chrome.exe",
        r"C:\Program Files (x86)\Google\Chrome\Application\chrome.exe",
    ):
        if Path(p).exists():
            return p
    return shutil.which("msedge") or shutil.which("chrome")


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--game", default="Pokemon")
    ap.add_argument("--age", default="8-10")
    ap.add_argument("--minutes", type=int, default=20)
    ap.add_argument("--objects", default="tree,stick,stone,bench,leaf")
    ap.add_argument("--out", default="card_out")
    a = ap.parse_args()

    profile = get_profile(a.game)
    if profile is None:
        sys.exit(f"Unknown game: {a.game}")
    objects = {o.strip() for o in a.objects.split(",") if o.strip()}
    ctx = MissionContext(confirmed_objects=objects, age_band=a.age, duration_min=a.minutes)

    print("Calling Ollama...")
    try:
        result = generate_with_retries(make_generator(profile, objects, ctx), ctx)
    except Exception as exc:
        sys.exit(f"Generation failed: {exc}")
    print(f"Attempts: {result.attempts} | Fallback used: {result.used_fallback}")
    for t in result.mission.tasks:
        print(f"  [{t.mechanic}] {t.instruction} ({t.minutes} min)")

    out = ROOT / a.out
    out.mkdir(exist_ok=True)
    html_path = out / "mission_card.html"
    html_path.write_text(render_card(result.mission, ctx, profile["title"]), encoding="utf-8")
    print(f"Card: {html_path}")

    browser = find_browser()
    if not browser:
        print("No Edge/Chrome found. Open the HTML and print to PDF manually.")
        return
    pdf_path = out / "mission_card.pdf"
    subprocess.run([browser, "--headless=new", "--disable-gpu", "--no-pdf-header-footer",
                    f"--print-to-pdf={pdf_path}", html_path.as_uri()],
                   check=False, timeout=90)
    print(f"PDF: {pdf_path}" if pdf_path.exists() else "PDF step failed. Print the HTML manually.")


if __name__ == "__main__":
    main()
