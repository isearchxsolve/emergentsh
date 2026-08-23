#!/usr/bin/env python3
"""Smoke: prompt -> multi-agent pipeline -> artifacts -> optional preview server."""
from __future__ import annotations
import argparse, asyncio, json, os, sys, threading, time
from http.server import SimpleHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
ROOT = Path(__file__).resolve().parents[1]
sys.path[:0] = [str(ROOT), str(ROOT/"src"), str(ROOT/"backend")]
PREVIEW_ROOT = ROOT / "preview_apps"

def _index(project_dir: Path, prompt: str, artifacts: list) -> Path:
    rows = "".join(f"<li><a href='{a}'><code>{a}</code></a></li>" for a in sorted(artifacts))
    html = f"""<!DOCTYPE html><html><head><meta charset=utf-8><title>EmergentSH Preview</title>
<style>body{{margin:0;font-family:system-ui;background:#0A0A0B;color:#F5F5F7}}header{{padding:1.5rem;background:#131316;border-bottom:1px solid #26262C}}
h1 span{{color:#76B900}}main{{padding:2rem;max-width:900px;margin:auto}}a{{color:#76B900}}</style></head>
<body><header><h1>Emergent<span>SH</span> Preview</h1></header><main>
<p><b>Prompt:</b> {prompt}</p><h2>Artifacts ({len(artifacts)})</h2><ul>{rows}</ul></main></body></html>"""
    p = project_dir/"index.html"; p.write_text(html, encoding="utf-8"); return p

async def run(prompt: str, use_mock: bool) -> dict:
    from backend.agent_pipeline import AgentPipeline
    job_id = f"smoke-{int(time.time())}"
    project_dir = PREVIEW_ROOT/job_id; project_dir.mkdir(parents=True, exist_ok=True)
    if use_mock or not (os.getenv("NIM_API_KEY") or os.getenv("NVIDIA_API_KEY")):
        from backend.app.api.pipeline import _make_mock_client
        client, mode = _make_mock_client(), "mock"
    else:
        from backend.app.services.nim_client import AsyncNIMClient
        client, mode = AsyncNIMClient(), "live-NIM"
    print(f"[smoke] mode={mode} dir={project_dir}")
    ctx = await AgentPipeline(client).run(user_prompt=prompt, project_dir=str(project_dir))
    arts = list(getattr(ctx, "artifacts", {}) or {})
    for p in project_dir.rglob("*"):
        if p.is_file() and p.name != "index.html":
            rel = str(p.relative_to(project_dir)).replace("\\","/")
            if rel not in arts: arts.append(rel)
    _index(project_dir, prompt, arts)
    status = getattr(getattr(ctx,"status",None),"value", str(getattr(ctx,"status","ok")))
    return {"job_id": job_id, "status": status, "mode": mode, "project_dir": str(project_dir), "artifacts": arts, "errors": list(getattr(ctx,"errors",[]) or [])}

def main():
    ap = argparse.ArgumentParser(); ap.add_argument("--prompt", default="Build a todo SaaS with auth")
    ap.add_argument("--live", action="store_true"); ap.add_argument("--serve", action="store_true"); ap.add_argument("--port", type=int, default=3001)
    args = ap.parse_args()
    result = asyncio.run(run(args.prompt, use_mock=not args.live))
    print(json.dumps(result, indent=2))
    if args.serve:
        os.chdir(result["project_dir"])
        print(f"[smoke] http://127.0.0.1:{args.port}/")
        ThreadingHTTPServer(("0.0.0.0", args.port), SimpleHTTPRequestHandler).serve_forever()
    return 0 if not result.get("errors") else 1
if __name__ == "__main__":
    raise SystemExit(main())
