from pathlib import Path
import subprocess
import pymupdf as pdf

def convert(source, target):
    result = subprocess.run(["powershell", "-NoProfile", "-ExecutionPolicy", "Bypass",
        "-File", str(Path(__file__).with_name("convert.ps1")), str(source), str(target)],
        capture_output=True, creationflags=subprocess.CREATE_NO_WINDOW, timeout=180)
    if result.returncode:
        raise ValueError(result.stderr.decode(errors="replace"))
    return pdf.open(target)
