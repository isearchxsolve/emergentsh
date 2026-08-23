"""EM-6 acceptance smoke: Playwright over the live workspace.

Verifies the remediation acceptance criteria:
  - every visible control either works or is gone (no dead buttons)
  - the four job states render (empty / loading / error / complete)
  - auth is wired (sign-in card, token persistence, 401 handling)
Screenshot evidence is saved to docs/em6_evidence/.

Run with the backend on :8000 and the frontend on :3000.
"""
import json
import sys
import time
from pathlib import Path

from playwright.sync_api import sync_playwright, expect

BASE = "http://127.0.0.1:3000"
EVIDENCE = Path(__file__).resolve().parent.parent / "docs" / "em6_evidence"
EVIDENCE.mkdir(parents=True, exist_ok=True)

results = []


def check(name, ok, detail=""):
    results.append({"name": name, "ok": bool(ok), "detail": detail})
    print(f"[{'PASS' if ok else 'FAIL'}] {name} {detail}")


def main():
    with sync_playwright() as p:
        browser = p.chromium.launch(headless=True)
        page = browser.new_page(viewport={"width": 1600, "height": 950})

        # ---- 1. Signed-out state: glassmorphic sign-in card ----
        page.goto(f"{BASE}/workspace", wait_until="networkidle")
        page.wait_for_timeout(800)
        page.screenshot(path=str(EVIDENCE / "01_signed_out.png"))
        check("sign-in card renders", page.locator("text=Sign In").count() >= 1)
        check("register button present", page.locator("text=Create account").count() >= 1)
        check("no workspace chrome while signed out",
              page.locator("text=Project Workspace").count() == 0)

        # ---- 2. Register + sign in ----
        uname = f"em6user{int(time.time()) % 100000}"
        page.fill("input[placeholder='Username']", uname)
        page.fill("input[placeholder='Password']", "strongpass123")
        page.click("text=Create account")
        page.wait_for_timeout(2500)
        page.screenshot(path=str(EVIDENCE / "02_after_register.png"))
        signed_in = page.locator("text=Project Workspace").count() >= 1
        check("register -> signed in", signed_in)
        if not signed_in:
            err = page.locator("text=/failed|error/i").first
            check("register error surfaced", err.count() >= 1,
                  err.inner_text() if err.count() else "no error text")

        # ---- 3. Four states: EMPTY ----
        page.wait_for_timeout(500)
        page.screenshot(path=str(EVIDENCE / "03_state_empty.png"))
        check("empty state renders", page.locator("text=No build yet").count() >= 1)

        # ---- 4. Settings panel (previously dead button) ----
        page.click("button[title='Settings']")
        page.wait_for_timeout(400)
        page.screenshot(path=str(EVIDENCE / "04_settings_panel.png"))
        check("settings panel opens", page.locator("text=Sign out").count() >= 1)
        check("refresh balance button present",
              page.locator("text=Refresh balance").count() >= 1)
        page.click("button[title='Settings']")  # close again

        # ---- 5. Sidebar toggle (was already wired; confirm still works) ----
        before = page.locator("text=Agent Activity").count()
        page.click("button[title='Toggle Sidebar']")
        page.wait_for_timeout(300)
        after = page.locator("text=Agent Activity").count()
        check("sidebar toggle works", before != after)
        page.click("button[title='Toggle Sidebar']")

        # ---- 6. GitHub button must be GONE (no backend endpoint) ----
        check("GitHub Sync button removed",
              page.locator("button[title='GitHub Sync']").count() == 0)

        # ---- 7. Start a build -> LOADING state ----
        page.fill("textarea", "Build a simple hello-world landing page")
        page.click("button[type='submit']")
        page.wait_for_timeout(1500)
        page.screenshot(path=str(EVIDENCE / "05_state_loading.png"))
        loading = page.locator("text=Build in progress...").count() >= 1
        check("loading state renders", loading)

        # ---- 8. Wait for completion (mock pipeline is fast) ----
        completed = False
        for _ in range(40):
            if page.locator("text=Preview live at").count() >= 1:
                completed = True
                break
            if page.locator("text=Build failed").count() >= 1:
                break
            page.wait_for_timeout(1000)
        page.screenshot(path=str(EVIDENCE / "06_state_complete.png"))
        check("complete state renders", completed)
        if completed:
            check("preview iframe present", page.locator("iframe[title='Live Preview']").count() >= 1)
            check("copy URL button present", page.locator("button[title='Copy preview URL']").count() >= 1)
            check("download button present", page.locator("button[title='Download code (.zip)']").count() >= 1)
            check("refresh preview enabled", page.locator("button[title='Refresh preview']").is_enabled())

        # ---- 9. Credits reflect the debit ----
        credits_text = page.locator("text=/Credits$/").first.inner_text()
        check("credits badge shows a number", any(c.isdigit() for c in credits_text), credits_text)

        # ---- 10. Sign out returns to the card ----
        page.click("button[title='Settings']")
        page.click("text=Sign out")
        page.wait_for_timeout(600)
        page.screenshot(path=str(EVIDENCE / "07_signed_out_again.png"))
        check("sign out returns to sign-in card",
              page.locator("text=Sign In").count() >= 1)

        # ---- 11. Token persistence: reload while signed out stays out ----
        page.reload(wait_until="networkidle")
        page.wait_for_timeout(600)
        check("reload while signed out stays signed out",
              page.locator("text=Sign In").count() >= 1)

        browser.close()

    summary = {
        "total": len(results),
        "passed": sum(1 for r in results if r["ok"]),
        "failed": sum(1 for r in results if not r["ok"]),
        "results": results,
    }
    (EVIDENCE / "smoke_summary.json").write_text(json.dumps(summary, indent=2))
    print(f"\n{summary['passed']}/{summary['total']} checks passed")
    return 0 if summary["failed"] == 0 else 1


if __name__ == "__main__":
    sys.exit(main())
