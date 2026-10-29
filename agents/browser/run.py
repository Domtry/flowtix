"""Start the browser agent on the host machine.

Usage:
    cd agents/browser
    pip install -e .
    python run.py
"""

import os
import ssl
import subprocess
import sys
import urllib.request
import zipfile

import uvicorn

PLAYWRIGHT_BROWSERS = os.path.expanduser(r"~\AppData\Local\ms-playwright")

BROWSERS_TO_INSTALL = {
    "chromium": None,
    "firefox": {
        "url": "https://cdn.playwright.dev/dbazure/download/playwright/builds/firefox/1555/firefox-win64.zip",
        "dest": os.path.join(PLAYWRIGHT_BROWSERS, "firefox-1555"),
    },
}


def install_browsers() -> None:
    for name, manual_info in BROWSERS_TO_INSTALL.items():
        if manual_info and os.path.isdir(manual_info["dest"]):
            continue
        result = subprocess.run(
            [sys.executable, "-m", "playwright", "install", name],
            capture_output=True,
            text=True,
            timeout=60,
        )
        if result.returncode == 0:
            continue

        if manual_info and not os.path.isdir(manual_info["dest"]):
            _download_via_python(name, manual_info["url"], manual_info["dest"])


def _download_via_python(name: str, url: str, dest: str) -> None:
    """Fallback: download via Python SSL which trusts the Windows cert store."""
    import shutil
    zip_path = os.path.join(os.environ.get("TEMP", "."), f"{name}-win64.zip")
    ctx = ssl.create_default_context()
    ctx.load_default_certs()
    try:
        print(f"[browser-agent] Downloading {name} via Python SSL fallback...")
        with urllib.request.urlopen(url, context=ctx, timeout=120) as resp, open(zip_path, "wb") as f:
            shutil.copyfileobj(resp, f)
        os.makedirs(dest, exist_ok=True)
        with zipfile.ZipFile(zip_path, "r") as zf:
            zf.extractall(dest)
        os.remove(zip_path)
        print(f"[browser-agent] {name} installed to {dest}")
    except Exception as exc:
        print(f"[browser-agent] Failed to install {name}: {exc}")


if __name__ == "__main__":
    install_browsers()
    uvicorn.run(
        "src.agent_server:app",
        host="0.0.0.0",
        port=9090,
    )
