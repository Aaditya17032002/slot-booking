from __future__ import annotations

import logging
import shutil
import subprocess
import time
from contextlib import contextmanager
from pathlib import Path
from typing import Generator, List, Optional

from playwright.sync_api import Browser, BrowserContext, Page, Playwright, sync_playwright

from .config import Settings


log = logging.getLogger(__name__)


def find_chrome_executable(chrome_path: str = "") -> Optional[Path]:
    """Locate Google Chrome on Windows / common paths."""
    if chrome_path:
        p = Path(chrome_path)
        if p.exists():
            return p
    candidates: List[Path] = []
    local = Path.home() / "AppData" / "Local" / "Google" / "Chrome" / "Application" / "chrome.exe"
    candidates.append(local)
    candidates.extend(
        [
            Path(r"C:\Program Files\Google\Chrome\Application\chrome.exe"),
            Path(r"C:\Program Files (x86)\Google\Chrome\Application\chrome.exe"),
            Path("/usr/bin/google-chrome"),
            Path("/usr/bin/google-chrome-stable"),
            Path("/Applications/Google Chrome.app/Contents/MacOS/Google Chrome"),
        ]
    )
    which = shutil.which("chrome") or shutil.which("google-chrome") or shutil.which("google-chrome-stable")
    if which:
        candidates.insert(0, Path(which))
    for path in candidates:
        if path and path.exists():
            return path
    return None


def launch_real_chrome(settings: Settings, *, open_url: bool = True) -> subprocess.Popen:
    """
    Start real Google Chrome (not Playwright-controlled) with a dedicated profile
    and remote debugging enabled so we can attach later.
    """
    chrome = find_chrome_executable(settings.chrome_path)
    if not chrome:
        raise RuntimeError(
            "Google Chrome not found. Install Chrome, or set CHROME_PATH in .env"
        )

    profile = Path(settings.session_dir).resolve()
    profile.mkdir(parents=True, exist_ok=True)
    port = settings.cdp_port
    args = [
        str(chrome),
        f"--remote-debugging-port={port}",
        f"--user-data-dir={profile}",
        "--no-first-run",
        "--no-default-browser-check",
        "--disable-features=Translate",
    ]
    if open_url:
        args.append(settings.base_url)

    log.info("Launching real Chrome | profile=%s | cdp=http://127.0.0.1:%s", profile, port)
    # DETACHED on Windows so Chrome survives if the launcher exits
    creationflags = 0
    if hasattr(subprocess, "DETACHED_PROCESS"):
        creationflags = subprocess.DETACHED_PROCESS | subprocess.CREATE_NEW_PROCESS_GROUP

    return subprocess.Popen(
        args,
        creationflags=creationflags,
        stdout=subprocess.DEVNULL,
        stderr=subprocess.DEVNULL,
    )


def wait_for_cdp(cdp_url: str, timeout_s: float = 45.0) -> None:
    import httpx

    deadline = time.time() + timeout_s
    last_err = None
    while time.time() < deadline:
        try:
            with httpx.Client(timeout=2.0) as client:
                r = client.get(f"{cdp_url.rstrip('/')}/json/version")
                if r.status_code == 200:
                    return
        except Exception as exc:
            last_err = exc
        time.sleep(0.5)
    raise RuntimeError(f"Chrome CDP not reachable at {cdp_url} ({last_err})")


class BrowserSession:
    """
    Attach to real Chrome via CDP (preferred), or launch a persistent profile.

    CDP mode uses YOUR normal Chrome process — Cloudflare sees a real browser.
    """

    def __init__(
        self,
        settings: Settings,
        *,
        headless: Optional[bool] = None,
        mode: Optional[str] = None,
    ) -> None:
        self.settings = settings
        self.headless = settings.headless if headless is None else headless
        self.mode = (mode or settings.browser_mode).lower()
        self._pw: Optional[Playwright] = None
        self._browser: Optional[Browser] = None
        self.context: Optional[BrowserContext] = None
        self.page: Optional[Page] = None
        self._owns_browser = False  # if False, closing must NOT kill user's Chrome

    def start(self) -> Page:
        self.settings.ensure_dirs()
        self._pw = sync_playwright().start()

        if self.mode == "cdp":
            return self._start_cdp()
        return self._start_launch()

    def _start_cdp(self) -> Page:
        cdp = self.settings.cdp_url
        log.info("Connecting to real Chrome over CDP: %s", cdp)
        try:
            wait_for_cdp(cdp, timeout_s=5.0)
        except RuntimeError:
            log.info("No Chrome on CDP yet — launching real Chrome for you…")
            launch_real_chrome(self.settings, open_url=True)
            wait_for_cdp(cdp, timeout_s=45.0)

        assert self._pw is not None
        self._browser = self._pw.chromium.connect_over_cdp(cdp)
        self._owns_browser = False

        if self._browser.contexts:
            self.context = self._browser.contexts[0]
        else:
            self.context = self._browser.new_context()

        # Prefer an existing tab on the visa site; else reuse first page; else new tab
        self.page = self._pick_page(self.context)
        self.page.set_default_timeout(45_000)
        log.info("Attached to Chrome | pages=%d | url=%s", len(self.context.pages), self.page.url)
        return self.page

    def _pick_page(self, context: BrowserContext) -> Page:
        needle = "usvisascheduling"
        for page in context.pages:
            if needle in (page.url or "").lower():
                return page
        if context.pages:
            return context.pages[0]
        return context.new_page()

    def _start_launch(self) -> Page:
        """Fallback: Playwright-managed persistent context (more often CF-blocked)."""
        assert self._pw is not None
        user_data = Path(self.settings.session_dir).resolve()
        user_data.mkdir(parents=True, exist_ok=True)
        launch_kwargs = dict(
            user_data_dir=str(user_data),
            headless=self.headless,
            slow_mo=self.settings.slow_mo_ms,
            viewport={"width": 1366, "height": 850},
            locale="en-US",
            timezone_id="Asia/Kolkata",
            channel="chrome",
            args=["--disable-blink-features=AutomationControlled", "--no-first-run"],
            ignore_default_args=["--enable-automation"],
        )
        try:
            self.context = self._pw.chromium.launch_persistent_context(**launch_kwargs)
        except Exception:
            launch_kwargs.pop("channel", None)
            self.context = self._pw.chromium.launch_persistent_context(**launch_kwargs)

        self._owns_browser = True
        self.page = self.context.pages[0] if self.context.pages else self.context.new_page()
        self.page.set_default_timeout(45_000)
        log.info("Launched Playwright Chrome (headless=%s)", self.headless)
        return self.page

    def screenshot(self, name: str) -> Path:
        path = Path("screenshots") / name
        path.parent.mkdir(parents=True, exist_ok=True)
        assert self.page is not None
        self.page.screenshot(path=str(path), full_page=True)
        return path

    def close(self) -> None:
        """
        Detach Playwright. In CDP mode we do NOT quit the user's Chrome —
        cookies and login stay alive in that window.
        """
        try:
            if self._owns_browser and self.context:
                try:
                    self.context.close()
                except Exception as exc:
                    log.debug("Context close: %s", exc)
            elif self._browser:
                try:
                    self._browser.close()  # disconnect only
                except Exception as exc:
                    log.debug("CDP disconnect: %s", exc)
        finally:
            if self._pw:
                try:
                    self._pw.stop()
                except Exception:
                    pass
            self._browser = None
            self.context = None
            self.page = None
            self._pw = None


@contextmanager
def open_browser(
    settings: Settings,
    *,
    headless: Optional[bool] = None,
    mode: Optional[str] = None,
) -> Generator[BrowserSession, None, None]:
    session = BrowserSession(settings, headless=headless, mode=mode)
    try:
        session.start()
        yield session
    finally:
        session.close()
