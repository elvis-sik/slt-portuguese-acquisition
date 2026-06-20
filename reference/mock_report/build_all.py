from __future__ import annotations

import shutil
import subprocess
import sys
from pathlib import Path
from zipfile import ZIP_DEFLATED, ZipFile

ROOT = Path(__file__).resolve().parent
BUILD = ROOT / "build"
TEMPLATE = ROOT / "template/slt_portuguese_mock_template.docx"
OUTPUT_DOCX = BUILD / "slt_portuguese_synthetic_mock_submission.docx"

MEDIA_MAP = {
    "word/media/image1.png": ROOT / "figures/figure_s1_sampler_diagnostic.png",
    "word/media/image2.png": ROOT / "figures/figure_1a_target_loss.png",
    "word/media/image3.png": ROOT / "figures/figure_1b_grammar_margin.png",
    "word/media/image4.png": ROOT / "figures/figure_1c_llc_trajectory.png",
    "word/media/image5.png": ROOT / "figures/figure_2_phase_alignment.png",
    "word/media/image6.png": ROOT / "figures/figure_3_component_localization.png",
    "word/media/image7.png": ROOT / "figures/figure_4_freeze_intervention.png",
}


def rebuild_docx() -> None:
    BUILD.mkdir(parents=True, exist_ok=True)
    tmp = BUILD / "tmp.docx"
    with ZipFile(TEMPLATE, "r") as zin, ZipFile(tmp, "w", ZIP_DEFLATED) as zout:
        for item in zin.infolist():
            data = MEDIA_MAP[item.filename].read_bytes() if item.filename in MEDIA_MAP else zin.read(item.filename)
            zout.writestr(item, data)
    tmp.replace(OUTPUT_DOCX)


def convert_pdf() -> None:
    lo = shutil.which("libreoffice") or shutil.which("soffice")
    if not lo:
        print("LibreOffice not installed; DOCX rebuilt but PDF conversion skipped.")
        return
    subprocess.run([lo, "--headless", "--convert-to", "pdf", "--outdir", str(BUILD), str(OUTPUT_DOCX)], check=True)


def main() -> None:
    subprocess.run([sys.executable, str(ROOT / "generate_synthetic_results.py")], check=True)
    rebuild_docx()
    convert_pdf()
    print(f"Built outputs in {BUILD}")


if __name__ == "__main__":
    main()
