from __future__ import annotations

import json
import logging
import os
import shutil
import time
from pathlib import Path
from typing import Any

from video_factory.config import ROOT

LOG = logging.getLogger("arena-stealth-provider")


class ArenaStealthError(RuntimeError):
    """Failure during LMSYS Arena web automation."""
    pass


class ArenaStealthProvider:
    """Automated Playwright Stealth adapter for lmarena.ai / arena.ai.
    
    Uses Playwright launch_persistent_context('arena_session') and anti-detect
    options to interact with LMSYS Chatbot Arena for automated video generation.
    """

    def __init__(self, session_dir: Path | str | None = None) -> None:
        self.session_dir = Path(session_dir) if session_dir else ROOT / ".arena/arena_session"
        self.session_dir.mkdir(parents=True, exist_ok=True)

    def _get_stealth_args(self) -> list[str]:
        return [
            "--disable-blink-features=AutomationControlled",
            "--no-sandbox",
            "--disable-setuid-sandbox",
            "--disable-infobars",
            "--window-position=0,0",
            "--ignore-certificate-errors",
            "--ignore-certificate-errors-spki-list",
            "--user-agent=Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/124.0.0.0 Safari/537.36"
        ]

    def health(self) -> dict[str, Any]:
        """Check persistent context session status."""
        has_session = self.session_dir.exists() and any(self.session_dir.iterdir())
        return {
            "provider": "lmarena_persistent_context",
            "session_active": has_session,
            "session_dir": str(self.session_dir)
        }

    def generate_video(
        self,
        prompt: str,
        output_path: str | Path,
        timeout_seconds: int = 180,
        headless: bool = True
    ) -> Path:
        """Connects to lmarena.ai using persistent context session, submits prompt, downloads video."""
        from playwright.sync_api import sync_playwright

        output = Path(output_path).resolve()
        output.parent.mkdir(parents=True, exist_ok=True)
        prompt = prompt.strip()

        LOG.info("🤖 [Arena Persistent Autopilot] Launching context at %s...", self.session_dir)
        with sync_playwright() as p:
            context = p.chromium.launch_persistent_context(
                str(self.session_dir),
                headless=headless,
                args=self._get_stealth_args(),
                viewport={"width": 1280, "height": 800}
            )

            page = context.pages[0] if context.pages else context.new_page()
            page.add_init_script("""
                Object.defineProperty(navigator, 'webdriver', {get: () => undefined});
                window.chrome = { runtime: {} };
            """)

            try:
                LOG.info("🌐 [Arena Autopilot] Navigating to https://lmarena.ai...")
                page.goto("https://lmarena.ai", timeout=60000)
                time.sleep(3)

                # Check title for Cloudflare Turnstile block
                title = page.title()
                if "Just a moment..." in title or "Attention Required" in title:
                    LOG.warning("🛡️ [Arena Autopilot] Waiting for Cloudflare Turnstile...")
                    time.sleep(10)
                    if "Just a moment..." in page.title():
                        raise ArenaStealthError(
                            "Cloudflare Turnstile challenge page blocked automated request. "
                            "Session needs initial manual verification."
                        )

                # 1. Fill prompt in textarea
                textarea = page.locator("textarea").first
                if not textarea.is_visible():
                    raise ArenaStealthError("Prompt textarea not visible on Arena page")

                LOG.info("✍️ [Arena Autopilot] Entering prompt: '%s'", prompt[:60])
                textarea.fill(prompt)
                time.sleep(1)

                # 2. Press Enter or click send button
                send_btn = page.locator('button[type="submit"], button:has-text("Send")').first
                if send_btn.is_visible():
                    send_btn.click()
                else:
                    textarea.press("Enter")
                time.sleep(2)

                # 3. Dismiss Agree modal if visible
                agree_btn = page.locator('button:has-text("Agree")').first
                if agree_btn.is_visible():
                    LOG.info("Clicking Terms Agree button...")
                    agree_btn.click()
                    time.sleep(2)

                # 4. Check if Login modal is blocking
                login_modal = page.locator('text="Log In or Create Account"').first
                if login_modal.is_visible():
                    raise ArenaStealthError(
                        "LMSYS Arena requires a logged-in session in 'arena_session'. "
                        "Run 'python -m video_factory.providers.arena_stealth --login' once to authenticate."
                    )

                # 5. Wait for generated video element
                LOG.info("⏳ [Arena Autopilot] Waiting for video generation on Arena (up to %ds)...", timeout_seconds)
                start_time = time.monotonic()
                video_url = None

                while time.monotonic() - start_time < timeout_seconds:
                    videos = page.locator("video").all()
                    for v in videos:
                        src = v.get_attribute("src")
                        if src and (src.startswith("http") or src.startswith("blob:")):
                            video_url = src
                            break
                    if video_url:
                        break
                    time.sleep(3)

                if not video_url:
                    links = page.locator('a[href$=".mp4"]').all()
                    if links:
                        video_url = links[0].get_attribute("href")

                if not video_url:
                    raise ArenaStealthError("Timeout waiting for video element on Arena")

                LOG.info("🔗 [Arena Autopilot] Generated video URL: %s", video_url)

                # 6. Download video data
                if video_url.startswith("http"):
                    res = page.request.get(video_url)
                    output.write_bytes(res.body())
                else:
                    video_element = page.locator("video").first
                    blob_data = video_element.evaluate("""
                        async (v) => {
                            const res = await fetch(v.src);
                            const blob = await res.blob();
                            return new Promise((resolve) => {
                                const reader = new FileReader();
                                reader.onloadend = () => resolve(reader.result);
                                reader.readAsDataURL(blob);
                            });
                        }
                    """)
                    import base64
                    header, encoded = blob_data.split(",", 1)
                    data = base64.b64decode(encoded)
                    output.write_bytes(data)

                LOG.info("🎉 [Arena Autopilot] Saved video -> %s (%d bytes)", output, output.stat().st_size)
                return output

            finally:
                context.close()


def interactive_login() -> None:
    """One-time helper script to launch persistent context browser for session authentication."""
    from playwright.sync_api import sync_playwright

    provider = ArenaStealthProvider()
    print("=======================================================")
    print("🔑 LMSYS Arena Persistent Context Session Setup")
    print("=======================================================")
    print(f"Opening browser at session directory: {provider.session_dir}")

    with sync_playwright() as p:
        context = p.chromium.launch_persistent_context(
            str(provider.session_dir),
            headless=False,
            args=provider._get_stealth_args(),
            viewport={"width": 1280, "height": 800}
        )
        page = context.pages[0] if context.pages else context.new_page()
        page.add_init_script("Object.defineProperty(navigator, 'webdriver', {get: () => undefined});")
        page.goto("https://lmarena.ai", timeout=60000)

        print("\n🌐 Page loaded. Please log in or complete any verification on page.")
        print("⏳ Waiting 120 seconds for login completion...")
        time.sleep(120)

        context.close()
        print(f"\n✅ Session saved successfully in {provider.session_dir}!")


if __name__ == "__main__":
    import argparse
    parser = argparse.ArgumentParser(description="Arena Stealth Autopilot Provider")
    parser.add_argument("--login", action="store_true", help="Launch headful persistent context for one-time login")
    parser.add_argument("--prompt", type=str, help="Prompt to generate video on Arena")
    parser.add_argument("--output", type=Path, default=ROOT / "outputs/arena_autopilot_test.mp4")
    args = parser.parse_args()

    if args.login:
        interactive_login()
    elif args.prompt:
        provider = ArenaStealthProvider()
        provider.generate_video(args.prompt, args.output)
    else:
        provider = ArenaStealthProvider()
        print(json.dumps(provider.health(), indent=2))
