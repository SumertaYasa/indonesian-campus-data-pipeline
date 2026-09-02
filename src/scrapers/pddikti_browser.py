"""
pddikti_browser.py — Multi-engine browser helper for PDDIKTI scraper.
Arsitektur mengikuti project referensi occupation-skillselect-scrapp:
  Priority 1: Camoufox (Firefox anti-detection, non-CDP)
  Priority 2: undetected-chromedriver (Selenium, patched CDP)
  Priority 3: Playwright + stealth (fallback terakhir)

Setiap engine mengembalikan page/driver yang dapat digunakan oleh PddiktiScraper.
"""

import logging
import time
import random
import os
import threading
from typing import Optional, Tuple, Any

logger = logging.getLogger(__name__)

# ── Cek dependensi ───────────────────────────────────────────────────────────

try:
    from camoufox.sync_api import Camoufox
    _CAMOUFOX_AVAILABLE = True
except ImportError:
    _CAMOUFOX_AVAILABLE = False

try:
    import undetected_chromedriver as uc
    from selenium.webdriver.common.by import By
    from selenium.webdriver.support.ui import WebDriverWait
    from selenium.webdriver.support import expected_conditions as EC
    from selenium.webdriver.common.action_chains import ActionChains
    _UC_AVAILABLE = True
except ImportError:
    _UC_AVAILABLE = False

try:
    from playwright.sync_api import sync_playwright
    _PLAYWRIGHT_AVAILABLE = True
except ImportError:
    _PLAYWRIGHT_AVAILABLE = False

try:
    from playwright_stealth import Stealth
    _STEALTH_AVAILABLE = True
except ImportError:
    _STEALTH_AVAILABLE = False


# ── Cloudflare Detection ─────────────────────────────────────────────────────

_CLOUDFLARE_MARKERS = (
    "just a moment", "cloudflare", "security verification",
    "memverifikasi", "tunggu sebentar", "verifikasi bahwa anda",
)

def is_cloudflare_page(html: str) -> bool:
    if not html:
        return False
    snippet = html[:3000].lower()
    return any(marker in snippet for marker in _CLOUDFLARE_MARKERS)

def is_cloudflare_title(title: str) -> bool:
    if not title:
        return False
    lower = title.lower()
    return any(k in lower for k in _CLOUDFLARE_MARKERS)


# ── Engine 1: Camoufox (Firefox anti-detection) ─────────────────────────────

def launch_camoufox(headless: bool = False, timeout_s: int = 30):
    """
    Launches Camoufox browser (Firefox-based anti-detection).
    Returns (browser_context, page, engine_name) or raises on failure.
    Uses a thread with timeout to prevent indefinite hang.
    """
    if not _CAMOUFOX_AVAILABLE:
        raise ImportError("camoufox not installed")

    logger.info(f"[Engine 1] Launching Camoufox (Firefox anti-detection, timeout={timeout_s}s)...")
    result = {}
    error = {}

    def _launch():
        try:
            browser = Camoufox(
                headless=headless,
                geoip=True,
                locale="id-ID",
                os="windows",
                block_images=False,
            ).__enter__()
            page = browser.new_page()
            result["browser"] = browser
            result["page"] = page
        except Exception as e:
            error["exc"] = e

    t = threading.Thread(target=_launch, daemon=True)
    t.start()
    t.join(timeout=timeout_s)

    if t.is_alive():
        logger.warning(f"[Engine 1] Camoufox launch timed out after {timeout_s}s")
        raise TimeoutError(f"Camoufox launch timed out after {timeout_s}s")

    if "exc" in error:
        raise error["exc"]

    if "browser" not in result:
        raise RuntimeError("Camoufox launch returned no result")

    return result["browser"], result["page"], "camoufox"


# ── Engine 2: undetected-chromedriver (Selenium) ─────────────────────────────

def _get_chrome_major_version() -> Optional[int]:
    """Detect installed Chrome major version from Windows registry or CLI."""
    if os.name == "nt":
        try:
            import winreg
            for root in (winreg.HKEY_CURRENT_USER, winreg.HKEY_LOCAL_MACHINE):
                for reg_path in (r"SOFTWARE\Google\Chrome\BLBeacon", r"SOFTWARE\Wow6432Node\Google\Chrome\BLBeacon"):
                    try:
                        key = winreg.OpenKey(root, reg_path)
                        version, _ = winreg.QueryValueEx(key, "version")
                        return int(version.split(".")[0])
                    except Exception:
                        continue
        except Exception:
            pass
    return None


def launch_undetected_chrome(headless: bool = False):
    """
    Launches undetected-chromedriver.
    Returns (driver, None, engine_name) or raises on failure.
    """
    if not _UC_AVAILABLE:
        raise ImportError("undetected-chromedriver not installed")

    chrome_version = _get_chrome_major_version()
    logger.info(f"[Engine 2] Launching undetected-chromedriver (Selenium)... Chrome v{chrome_version or '?'}")
    options = uc.ChromeOptions()
    if headless:
        options.add_argument("--headless=new")
    options.add_argument("--no-sandbox")
    options.add_argument("--disable-dev-shm-usage")
    options.add_argument("--window-size=1280,800")
    options.add_argument("--lang=id-ID")

    driver = uc.Chrome(options=options, use_subprocess=True, version_main=chrome_version)
    # Override navigator.webdriver
    driver.execute_cdp_cmd("Page.addScriptToEvaluateOnNewDocument", {
        "source": "Object.defineProperty(navigator, 'webdriver', {get: () => undefined})"
    })
    return driver, None, "undetected_chrome"


def solve_turnstile_selenium(driver, timeout: int = 15) -> bool:
    """Attempts to click Cloudflare Turnstile checkbox inside iframe."""
    try:
        wait = WebDriverWait(driver, timeout)
        iframe = wait.until(EC.presence_of_element_located(
            (By.CSS_SELECTOR, "iframe[src*='challenges.cloudflare.com']")
        ))
        driver.switch_to.frame(iframe)
        target = wait.until(EC.element_to_be_clickable(
            (By.CSS_SELECTOR, "input[type='checkbox'], #success-grid, .ctp-checksum-container")
        ))
        time.sleep(random.uniform(2.0, 4.0))
        ActionChains(driver).move_to_element(target)\
            .move_by_offset(random.randint(-2, 2), random.randint(-2, 2))\
            .click().perform()
        driver.switch_to.default_content()
        logger.info("[Turnstile] Clicked successfully.")
        time.sleep(5)
        return True
    except Exception as e:
        try:
            driver.switch_to.default_content()
        except Exception:
            pass
        logger.debug(f"[Turnstile] Click attempt failed: {e}")
        return False


def wait_cloudflare_resolve_selenium(driver, timeout_s: int = 60) -> bool:
    """Polls until Cloudflare resolves for Selenium driver."""
    start = time.time()
    while (time.time() - start) < timeout_s:
        html = driver.page_source
        if not is_cloudflare_page(html):
            logger.info(f"[CF] Resolved in {time.time()-start:.1f}s")
            return True
        # Try clicking turnstile
        solve_turnstile_selenium(driver, timeout=5)
        time.sleep(2)
    return False


# ── Engine 3: Playwright + stealth (fallback) ───────────────────────────────

def launch_playwright_stealth(headless: bool = False, profile_dir: Optional[str] = None):
    """
    Launches Playwright with stealth plugin.
    Returns (playwright_instance, context, page, engine_name) or raises.
    """
    if not _PLAYWRIGHT_AVAILABLE:
        raise ImportError("playwright not installed")

    logger.info("[Engine 3] Launching Playwright + stealth (fallback)...")
    pw = sync_playwright().start()

    launch_kwargs = {
        "headless": headless,
        "viewport": {"width": 1280, "height": 800},
        "locale": "id-ID",
        "ignore_default_args": ["--enable-automation"],
        "args": [
            "--disable-blink-features=AutomationControlled",
            "--no-sandbox",
            "--disable-dev-shm-usage",
            "--disable-infobars",
        ]
    }
    if profile_dir:
        launch_kwargs["user_data_dir"] = profile_dir

    # Try real Chrome, then Edge, then bundled Chromium
    context = None
    for channel in ["chrome", "msedge", None]:
        try:
            kw = {**launch_kwargs}
            if channel:
                kw["channel"] = channel
            if profile_dir:
                context = pw.chromium.launch_persistent_context(**kw)
            else:
                browser = pw.chromium.launch(
                    headless=headless,
                    channel=channel,
                    args=launch_kwargs["args"],
                    ignore_default_args=launch_kwargs["ignore_default_args"],
                )
                context = browser.new_context(
                    viewport=launch_kwargs["viewport"],
                    locale=launch_kwargs["locale"],
                )
            break
        except Exception as e:
            logger.debug(f"[Playwright] Channel '{channel}' failed: {e}")
            continue

    if context is None:
        pw.stop()
        raise RuntimeError("Failed to launch any Playwright browser")

    # Apply stealth
    stealth_js = """
    Object.defineProperty(navigator, 'webdriver', { get: () => false });
    if (window.chrome === undefined) { window.chrome = { runtime: {} }; }
    """
    context.add_init_script(stealth_js)
    if _STEALTH_AVAILABLE:
        logger.info("[Playwright] playwright-stealth available.")

    page = context.pages[0] if context.pages else context.new_page()
    return pw, context, page, "playwright"


# ── Multi-Engine Launcher ────────────────────────────────────────────────────

def launch_best_engine(headless: bool = False, profile_dir: Optional[str] = None):
    """
    Tries engines in priority order: Camoufox → undetected-chromedriver → Playwright.
    Returns a dict with engine info and handles.
    """
    # Engine 1: Camoufox
    if _CAMOUFOX_AVAILABLE:
        try:
            browser, page, name = launch_camoufox(headless)
            return {
                "engine": name,
                "type": "camoufox",
                "browser": browser,
                "page": page,
            }
        except Exception as e:
            logger.warning(f"[Engine 1] Camoufox failed: {e}")

    # Engine 2: undetected-chromedriver
    if _UC_AVAILABLE:
        try:
            driver, _, name = launch_undetected_chrome(headless)
            return {
                "engine": name,
                "type": "selenium",
                "driver": driver,
            }
        except Exception as e:
            logger.warning(f"[Engine 2] undetected-chromedriver failed: {e}")

    # Engine 3: Playwright
    if _PLAYWRIGHT_AVAILABLE:
        try:
            pw, context, page, name = launch_playwright_stealth(headless, profile_dir)
            return {
                "engine": name,
                "type": "playwright",
                "pw": pw,
                "context": context,
                "page": page,
            }
        except Exception as e:
            logger.warning(f"[Engine 3] Playwright failed: {e}")

    raise RuntimeError("No browser engine available. Install camoufox, undetected-chromedriver, or playwright.")


def close_engine(engine_info: dict):
    """Safely closes whichever engine was used."""
    engine_type = engine_info.get("type")
    try:
        if engine_type == "camoufox":
            engine_info["browser"].__exit__(None, None, None)
        elif engine_type == "selenium":
            engine_info["driver"].quit()
        elif engine_type == "playwright":
            engine_info["context"].close()
            engine_info["pw"].stop()
    except Exception as e:
        logger.debug(f"Error closing engine: {e}")
