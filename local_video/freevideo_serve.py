"""Serve FreeVideo's ComfyUI headless (what its Windows app does, minus the GUI).

Runs under FreeVideo's own engine Python, not this project's venv:
    <FreeVideo>/envs/unified/Scripts/python.exe -B local_video/freevideo_serve.py --root <FreeVideo> --port 8190
local_video.freevideo starts it automatically when MiniMax is needed.
"""
import argparse
import json
import os
from pathlib import Path
import subprocess
import sys
import time


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--root", type=Path, required=True, help="FreeVideo installation folder")
    parser.add_argument("--port", type=int, default=8190)
    parser.add_argument("--models", type=Path, help="extra folder with checkpoints/ (FLUX keyframes)")
    args = parser.parse_args()
    engine = args.root.resolve()
    sys.path.insert(0, str(engine))
    from freevideo_engine.comfy_environment import isolated_environment

    comfy = engine / "ComfyUI"
    host = json.loads((engine / "launcher" / "comfy-host.json").read_text(encoding="utf-8"))
    env = isolated_environment(engine, engine)
    env.pop("PYTHONPATH", None)
    env.update(PYTHONDONTWRITEBYTECODE="1", PYTHONUNBUFFERED="1", PYTHONUTF8="1", PYTHONIOENCODING="utf-8")
    # HTTPS-scanning antivirus (Norton) re-signs traffic with a root only Windows trusts.
    bundle = engine / "launcher" / "windows-ca-bundle.pem"
    if bundle.is_file():
        env.setdefault("SSL_CERT_FILE", str(bundle))
        env.setdefault("REQUESTS_CA_BUNDLE", str(bundle))
    log_dir = engine / "launcher" / "comfy-runs" / time.strftime("%Y%m%dT%H%M%S")
    log_dir.mkdir(parents=True, exist_ok=True)
    log_path = log_dir / "comfy.log"
    env["FREEVIDEO_COMFY_LOG"] = str(log_path)
    command = [host["python"], "-u", "-B", str(comfy / "main.py"), "--listen", "127.0.0.1", "--port", str(args.port),
               "--disable-auto-launch", "--disable-all-custom-nodes", "--whitelist-custom-nodes", "FreeVideo"]
    if args.models and args.models.is_dir():
        extra = log_dir / "extra_model_paths.yaml"
        extra.write_text(f"keyframes:\n  base_path: {args.models.resolve().as_posix()}\n"
                         "  checkpoints: checkpoints\n", encoding="utf-8")
        command += ["--extra-model-paths-config", str(extra)]
    print(f"FreeVideo ComfyUI on http://127.0.0.1:{args.port}  (log: {log_path})", flush=True)
    with open(log_path, "ab") as log:
        return subprocess.call(command, cwd=str(comfy), env=env, stdout=log, stderr=subprocess.STDOUT)


if __name__ == "__main__":
    sys.exit(main())
