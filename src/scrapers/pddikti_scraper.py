"""
pddikti_scraper.py — HTML/DOM-based scraper for PDDIKTI.
Supports multiple browser engines: Camoufox, undetected-chromedriver (Selenium), Playwright.
All DOM extraction logic is engine-agnostic using helper methods.
"""

import logging
import urllib.parse
import time
from typing import List, Dict, Optional, Set

from .pddikti_browser import (
    is_cloudflare_page,
    is_cloudflare_title,
    solve_turnstile_selenium,
    wait_cloudflare_resolve_selenium,
)


class PddiktiScraper:
    """HTML/DOM-based scraper for PDDIKTI using multi-engine browser approach."""

    def __init__(self, logger: Optional[logging.Logger] = None):
        self.logger = logger or logging.getLogger("pddikti_scraper")
        self.root_url = "https://pddikti.kemdiktisaintek.go.id/"

    # ══════════════════════════════════════════════════════════════════════════
    # Engine-agnostic page interaction helpers
    # ══════════════════════════════════════════════════════════════════════════

    def _get_page_html(self, page_or_driver, engine_type: str) -> str:
        if engine_type == "selenium":
            return page_or_driver.page_source
        else:
            return page_or_driver.content()

    def _get_page_title(self, page_or_driver, engine_type: str) -> str:
        if engine_type == "selenium":
            return page_or_driver.title
        else:
            return page_or_driver.title()

    def _get_page_url(self, page_or_driver, engine_type: str) -> str:
        if engine_type == "selenium":
            return page_or_driver.current_url
        else:
            return page_or_driver.url

    def _goto(self, page_or_driver, url: str, engine_type: str):
        if engine_type == "selenium":
            page_or_driver.get(url)
        else:
            page_or_driver.goto(url, timeout=60000, wait_until="domcontentloaded")

    def _wait(self, page_or_driver, ms: int, engine_type: str):
        if engine_type == "selenium":
            time.sleep(ms / 1000)
        else:
            page_or_driver.wait_for_timeout(ms)

    def _reload(self, page_or_driver, engine_type: str):
        """Reload/refresh the current page."""
        try:
            if engine_type == "selenium":
                page_or_driver.refresh()
            else:
                page_or_driver.reload(wait_until="domcontentloaded")
        except Exception as e:
            self.logger.warning(f"Reload failed: {e}")

    def _wait_for_url_contains(self, page_or_driver, substring: str, timeout_s: int, engine_type: str) -> bool:
        """Dynamically wait until the current browser URL contains the given substring."""
        start = time.time()
        while (time.time() - start) < timeout_s:
            try:
                curr_url = self._get_page_url(page_or_driver, engine_type)
                if substring in curr_url:
                    return True
            except Exception:
                pass
            self._wait(page_or_driver, 500, engine_type)
        return False

    def _screenshot(self, page_or_driver, path: str, engine_type: str):
        try:
            if engine_type == "selenium":
                page_or_driver.save_screenshot(path)
            else:
                page_or_driver.screenshot(path=path)
        except Exception:
            pass

    def _execute_js(self, page_or_driver, js_code: str, engine_type: str):
        if engine_type == "selenium":
            trimmed = js_code.strip()
            # In Selenium execute_script, returning from an IIFE/expression requires an outer 'return'
            if not trimmed.startswith("return ") and not trimmed.startswith("var ") and not trimmed.startswith("let ") and not trimmed.startswith("const "):
                trimmed = "return " + trimmed
            return page_or_driver.execute_script(trimmed)
        else:
            return page_or_driver.evaluate(js_code)

    # ══════════════════════════════════════════════════════════════════════════
    # Checkpoint Detection & Handling
    # ══════════════════════════════════════════════════════════════════════════

    def _is_checkpoint_active(self, page_or_driver, engine_type: str) -> bool:
        try:
            title = self._get_page_title(page_or_driver, engine_type)
            if is_cloudflare_title(title):
                return True
            html = self._get_page_html(page_or_driver, engine_type)
            if is_cloudflare_page(html):
                return True
            # Check in-page reCAPTCHA popup
            if "silahkan verifikasi terlebih dahulu" in html[:5000].lower():
                return True
        except Exception:
            pass
        return False

    def _wait_for_checkpoint(self, page_or_driver, engine_type: str, stage: str) -> bool:
        """Wait for checkpoint to resolve. For Selenium, tries to solve Turnstile automatically."""
        self.logger.info("\n" + "=" * 60)
        self.logger.info("[CHECKPOINT]")
        self.logger.info("reCAPTCHA / Cloudflare checkpoint detected.")
        if engine_type == "selenium":
            self.logger.info("Attempting automatic Turnstile resolution...")
        else:
            self.logger.info("Please complete the verification manually in the browser.")
        self.logger.info("Waiting for completion...")
        self.logger.info("=" * 60 + "\n")

        max_wait_s = 300
        start = time.time()

        while (time.time() - start) < max_wait_s:
            try:
                # For Selenium, try automatic Turnstile solving
                if engine_type == "selenium":
                    solve_turnstile_selenium(page_or_driver, timeout=5)

                self._wait(page_or_driver, 3000, engine_type)

                if not self._is_checkpoint_active(page_or_driver, engine_type):
                    self.logger.info("CAPTCHA ✓\n")
                    return True
            except Exception:
                return False

        self.logger.warning(f"Checkpoint timed out at: {stage}")
        return False

    # ══════════════════════════════════════════════════════════════════════════
    # Navigation: Root Domain → Search
    # ══════════════════════════════════════════════════════════════════════════

    def navigate_root_and_handle_checkpoint(self, page_or_driver, engine_type: str,
                                             search_url: Optional[str] = None) -> bool:
        self.logger.info(f"Opening Root Domain: {self.root_url}")
        try:
            self._goto(page_or_driver, self.root_url, engine_type)
            self.logger.info("ROOT DOMAIN ✓")
        except Exception as e:
            self.logger.error(f"Failed opening root domain: {e}")
            return False

        # 1. Checkpoint on root
        self._wait(page_or_driver, 2000, engine_type)
        if self._is_checkpoint_active(page_or_driver, engine_type):
            if not self._wait_for_checkpoint(page_or_driver, engine_type, "Root Domain"):
                return False

        # 2. Navigate to search
        target_url = search_url or "https://pddikti.kemdiktisaintek.go.id/search/pt/Universitas"
        try:
            # Try using search bar on root domain first
            search_found = self._try_search_from_root(page_or_driver, engine_type)
            if not search_found:
                self.logger.info(f"Navigating directly to search URL: {target_url}")
                self._goto(page_or_driver, target_url, engine_type)
                self._wait_for_url_contains(page_or_driver, "/search/pt", 15, engine_type)

            self._wait(page_or_driver, 2000, engine_type)

            # 3. Checkpoint on search page
            if self._is_checkpoint_active(page_or_driver, engine_type):
                if not self._wait_for_checkpoint(page_or_driver, engine_type, "Search Page"):
                    return False

            # 4. Click "Lanjutkan" button if reCAPTCHA popup present
            self._try_click_lanjutkan(page_or_driver, engine_type)

            return True
        except Exception as e:
            self.logger.error(f"Error navigating to search: {e}")
            return False

    def _try_search_from_root(self, page_or_driver, engine_type: str) -> bool:
        """Try to use the search bar on the root domain homepage, selecting 'Perguruan Tinggi' category."""
        try:
            if engine_type == "selenium":
                from selenium.webdriver.common.by import By
                from selenium.webdriver.common.keys import Keys

                # 1. Click Category dropdown button (role='combobox') to open the options list
                dropdown_btns = page_or_driver.find_elements(By.CSS_SELECTOR, "button[role='combobox'], button[aria-haspopup='listbox']")
                if dropdown_btns and dropdown_btns[0].is_displayed():
                    self.logger.info("Opening Category dropdown on Root Domain...")
                    dropdown_btns[0].click()
                    time.sleep(0.5)

                    # 2. Select 'Perguruan Tinggi' option from the listbox
                    pt_options = page_or_driver.find_elements(By.XPATH, "//li[@role='option' and contains(., 'Perguruan Tinggi')] | //li[@id='material-tailwind-select-1']")
                    if pt_options and pt_options[0].is_displayed():
                        self.logger.info("Selecting 'Perguruan Tinggi' category option...")
                        pt_options[0].click()
                        time.sleep(0.5)

                # 3. Enter search keyword and submit
                inputs = page_or_driver.find_elements(By.CSS_SELECTOR, "input[placeholder*='Kata kunci']")
                if inputs and inputs[0].is_displayed():
                    self.logger.info("Interacting with Search Bar on Root Domain...")
                    inputs[0].clear()
                    inputs[0].send_keys("Universitas")
                    time.sleep(0.5)
                    
                    # Try clicking parent div of search icon or press ENTER
                    search_divs = page_or_driver.find_elements(By.CSS_SELECTOR, "div.cursor-pointer")
                    clicked = False
                    for div in search_divs:
                        if div.is_displayed() and div.find_elements(By.CSS_SELECTOR, "img[alt='cari']"):
                            div.click()
                            clicked = True
                            break
                    if not clicked:
                        inputs[0].send_keys(Keys.ENTER)

                    # Wait dynamically for URL transition
                    self.logger.info("Waiting for URL transition to search page...")
                    url_changed = self._wait_for_url_contains(page_or_driver, "/search/pt", 15, engine_type)
                    return url_changed
            else:
                # 1. Click Category dropdown button (role='combobox') to open the options list
                dropdown_btn = page_or_driver.query_selector("button[role='combobox'], button[aria-haspopup='listbox']")
                if dropdown_btn and dropdown_btn.is_visible():
                    self.logger.info("Opening Category dropdown on Root Domain...")
                    dropdown_btn.click()
                    page_or_driver.wait_for_timeout(500)

                    # 2. Select 'Perguruan Tinggi' option from the listbox
                    pt_option = page_or_driver.query_selector("li[role='option']:has-text('Perguruan Tinggi'), #material-tailwind-select-1")
                    if pt_option and pt_option.is_visible():
                        self.logger.info("Selecting 'Perguruan Tinggi' category option...")
                        pt_option.click()
                        page_or_driver.wait_for_timeout(500)

                # 3. Enter search keyword and submit
                search_input = page_or_driver.query_selector("input[placeholder*='Kata kunci']")
                if search_input and search_input.is_visible():
                    self.logger.info("Interacting with Search Bar on Root Domain...")
                    search_input.fill("Universitas")
                    page_or_driver.wait_for_timeout(500)
                    search_icon = page_or_driver.query_selector("img[alt='cari']")
                    if search_icon and search_icon.is_visible():
                        search_icon.click()
                    else:
                        search_input.press("Enter")

                    # Wait dynamically for URL transition
                    self.logger.info("Waiting for URL transition to search page...")
                    url_changed = self._wait_for_url_contains(page_or_driver, "/search/pt", 15, engine_type)
                    return url_changed
        except Exception as e:
            self.logger.debug(f"Search from root failed: {e}")
        return False

    # ══════════════════════════════════════════════════════════════════════════
    # Navigation: Root Domain → Perguruan Tinggi Directory (/perguruan-tinggi)
    # ══════════════════════════════════════════════════════════════════════════

    def navigate_to_directory(self, page_or_driver, engine_type: str) -> bool:
        """Navigates from root domain to /perguruan-tinggi directory via menu card."""
        self.logger.info(f"Opening Root Domain: {self.root_url}")
        try:
            self._goto(page_or_driver, self.root_url, engine_type)
            self.logger.info("ROOT DOMAIN ✓")
        except Exception as e:
            self.logger.error(f"Failed opening root domain: {e}")
            return False

        # 1. Checkpoint on root domain
        self._wait(page_or_driver, 2000, engine_type)
        if self._is_checkpoint_active(page_or_driver, engine_type):
            if not self._wait_for_checkpoint(page_or_driver, engine_type, "Root Domain"):
                return False

        # 2. Click 'Perguruan Tinggi' menu card
        self.logger.info("Navigating to 'Perguruan Tinggi' directory card...")
        try:
            card_clicked = False
            if engine_type == "selenium":
                from selenium.webdriver.common.by import By
                cards = page_or_driver.find_elements(By.CSS_SELECTOR, "a#buildings-wrapper, a[href='/perguruan-tinggi']")
                if cards and cards[0].is_displayed():
                    cards[0].click()
                    card_clicked = True
            else:
                card = page_or_driver.query_selector("a#buildings-wrapper, a[href='/perguruan-tinggi']")
                if card and card.is_visible():
                    card.click()
                    card_clicked = True

            if not card_clicked:
                self.logger.info("Directory card not clickable directly. Navigating via URL...")
                self._goto(page_or_driver, "https://pddikti.kemdiktisaintek.go.id/perguruan-tinggi", engine_type)

            # Wait for URL transition
            self._wait_for_url_contains(page_or_driver, "/perguruan-tinggi", 15, engine_type)
            self._wait(page_or_driver, 2000, engine_type)

            # 3. Checkpoint on /perguruan-tinggi page
            if self._is_checkpoint_active(page_or_driver, engine_type):
                if not self._wait_for_checkpoint(page_or_driver, engine_type, "Directory Page"):
                    return False

            self.logger.info("PERGURUAN TINGGI DIRECTORY ✓\n")
            return True
        except Exception as e:
            self.logger.error(f"Error navigating to directory: {e}")
            return False

    def _try_set_pagination_limit(self, page_or_driver, engine_type: str, limit: str = "48") -> bool:
        """Sets the pagination dropdown to limit (e.g. 48) to accelerate scraping."""
        js = f"""
        (() => {{
            const sel = document.querySelector('select[name="pagination"]');
            if (!sel) return false;
            const opt = Array.from(sel.options).find(o => o.value === '{limit}');
            if (!opt) return false;
            sel.value = '{limit}';
            sel.dispatchEvent(new Event('change', {{ bubbles: true }}));
            return true;
        }})()
        """
        try:
            changed = self._execute_js(page_or_driver, js, engine_type)
            if changed:
                self.logger.info(f"Pagination limit adjusted to: {limit} items per page ✓")
                self._wait(page_or_driver, 3000, engine_type)
                return True
        except Exception:
            pass
        return False

    def _get_directory_page_number(self, page_or_driver, engine_type: str) -> str:
        """Reads the current page indicator from directory pagination."""
        js = """
        (() => {
            const pageDiv = document.querySelector('div.flex.items-center.gap-3 div.rounded-\\[5px\\]');
            if (pageDiv) return (pageDiv.innerText || '').trim();
            const allSpan = Array.from(document.querySelectorAll('span'));
            const halSpan = allSpan.find(s => (s.innerText || '').includes('Halaman'));
            if (halSpan) return (halSpan.innerText || '').trim();
            return '';
        })()
        """
        try:
            return str(self._execute_js(page_or_driver, js, engine_type) or '')
        except Exception:
            return ''

    def _wait_for_directory_cards(self, page_or_driver, engine_type: str, timeout_s: int = 30) -> bool:
        """Waits until campus cards are rendered in the grid container."""
        js = """
        (() => {
            const buttons = Array.from(document.querySelectorAll('button')).filter(b => (b.innerText || '').trim().includes('Lihat Detail'));
            return buttons.length > 0;
        })()
        """
        start = time.time()
        while (time.time() - start) < timeout_s:
            try:
                ready = self._execute_js(page_or_driver, js, engine_type)
                if ready:
                    return True
            except Exception:
                pass
            self._wait(page_or_driver, 1000, engine_type)
        return False

    def _extract_directory_cards(self, page_or_driver, engine_type: str) -> List[Dict]:
        """Extracts campus card items from the directory grid."""
        js = """
        (() => {
            const buttons = Array.from(document.querySelectorAll('button')).filter(b => (b.innerText || '').trim().includes('Lihat Detail'));
            const results = [];
            buttons.forEach((btn, idx) => {
                const card = btn.closest('div.rounded-md') || btn.parentElement?.parentElement;
                if (!card) return;
                const nameEl = card.querySelector('p.font-semibold, p.text-base, div.absolute p');
                const name = nameEl ? (nameEl.innerText || '').trim() : '';
                if (!name) return;

                const badgeEl = card.querySelector('div[class*="bg-info-main"], div[class*="bg-warning-main"], div[class*="bg-"]');
                const status = badgeEl ? (badgeEl.innerText || '').trim() : '';

                const locEl = card.querySelector('h5');
                const lokasi = locEl ? (locEl.innerText || '').trim() : '';

                results.push({
                    nama_pt: name,
                    status_badge: status,
                    lokasi: lokasi,
                    card_index: idx
                });
            });
            return results;
        })()
        """
        try:
            raw = self._execute_js(page_or_driver, js, engine_type)
            return raw or []
        except Exception as e:
            self.logger.warning(f"Directory card extraction error: {e}")
            return []

    def _click_directory_next_page(self, page_or_driver, engine_type: str) -> bool:
        """Clicks the Next page right-arrow button on directory pagination."""
        js = """
        (() => {
            const rightBtn = document.querySelector('button:has(img[alt="right"]), button img[alt="right"]')?.closest('button') 
                || document.querySelectorAll('div.flex.items-center.gap-1 button')[1];
            if (!rightBtn || rightBtn.disabled || rightBtn.getAttribute('disabled') !== null) {
                return false;
            }
            rightBtn.click();
            return true;
        })()
        """
        try:
            return bool(self._execute_js(page_or_driver, js, engine_type))
        except Exception:
            return False

    # ══════════════════════════════════════════════════════════════════════════
    # Discovery
    # ══════════════════════════════════════════════════════════════════════════

    def discover(self, page_or_driver, engine_type: str, max_records: int = 100) -> List[Dict]:
        self.logger.info("Waiting for discovery table in DOM...")

        # Protect against race condition: Ensure we are on search page
        curr_url = self._get_page_url(page_or_driver, engine_type)
        if "/search/pt" not in curr_url:
            self.logger.warning(f"Browser URL is not on search page ({curr_url}). Navigating directly to search target...")
            self._goto(page_or_driver, "https://pddikti.kemdiktisaintek.go.id/search/pt/Universitas", engine_type)
            self._wait_for_url_contains(page_or_driver, "/search/pt", 15, engine_type)

        # Diagnostic
        try:
            url = self._get_page_url(page_or_driver, engine_type)
            title = self._get_page_title(page_or_driver, engine_type)
            self.logger.info(f"  Page URL  : {url}")
            self.logger.info(f"  Page Title: {title}")
        except Exception:
            pass

        # Check for in-page reCAPTCHA popup
        try:
            html = self._get_page_html(page_or_driver, engine_type)
            if "silahkan verifikasi terlebih dahulu" in html[:5000].lower():
                self.logger.info("  [DETECTED] In-page reCAPTCHA popup. Please verify and click 'Lanjutkan'.")
                self._try_click_lanjutkan(page_or_driver, engine_type)
        except Exception:
            pass

        # Wait for table with auto-recovery
        table_found = self._wait_for_table(page_or_driver, engine_type, timeout_s=60)
        if not table_found:
            self._screenshot(page_or_driver, "debug_discovery_page_state.png", engine_type)
            try:
                body_text = self._execute_js(page_or_driver, "return document.body.innerText.substring(0, 500)", engine_type)
                self.logger.info(f"  Page body (500 chars):\n{body_text}")
            except Exception:
                pass
            raise Exception("Discovery table not found in DOM")

        # Extract records with pagination
        discovered: List[Dict] = []
        seen_urls: Set[str] = set()
        page_num = 1
        base_url = self._get_page_url(page_or_driver, engine_type)

        while len(discovered) < max_records:
            self.logger.info(f"Scanning table rows on page {page_num}...")

            # Active polling up to 10s to ensure React has finished populating rows
            rows = []
            poll_start = time.time()
            while (time.time() - poll_start) < 10:
                rows = self._extract_table_rows(page_or_driver, engine_type, base_url)
                if rows:
                    break
                self._wait(page_or_driver, 1000, engine_type)

            added = 0
            for row in rows:
                if len(discovered) >= max_records:
                    break
                if row["detail_url"] in seen_urls:
                    continue
                seen_urls.add(row["detail_url"])
                discovered.append(row)
                added += 1

            self.logger.info(f"Page {page_num}: +{added} unique records (Total: {len(discovered)}/{max_records})")

            if len(discovered) >= max_records:
                break

            if not rows or not self._click_next_page(page_or_driver, engine_type):
                self.logger.info("No active Next button or no more rows. Discovery complete.")
                break

            # Wait for next page transition
            self._wait(page_or_driver, 2000, engine_type)
            page_num += 1

        return discovered

    def _wait_for_table(self, page_or_driver, engine_type: str, timeout_s: int = 60) -> bool:
        """Wait for campus data table rows with detail links to appear, with auto-recovery reload if stuck."""
        target_selector = "table tbody tr td a[href*='/detail-pt/']"

        # Phase 1: Wait up to 15s for the specific table rows
        if self._check_table_presence(page_or_driver, target_selector, engine_type, timeout_s=15):
            return True

        # Phase 2: If not found within 15s, possible blank screen / silent challenge. Try auto-recovery reload.
        self.logger.warning("Table rows with '/detail-pt/' links not appearing yet. Attempting auto-reload recovery...")
        self._reload(page_or_driver, engine_type)
        self._wait(page_or_driver, 3000, engine_type)

        # Check if reload triggered a Turnstile or reCAPTCHA checkpoint
        if self._is_checkpoint_active(page_or_driver, engine_type):
            self._wait_for_checkpoint(page_or_driver, engine_type, "Recovery Checkpoint")

        # Check in-page reCAPTCHA popup
        self._try_click_lanjutkan(page_or_driver, engine_type)

        # Phase 3: Wait up to 45s for table rows to appear after recovery
        return self._check_table_presence(page_or_driver, target_selector, engine_type, timeout_s=45)

    def _check_table_presence(self, page_or_driver, selector: str, engine_type: str, timeout_s: int) -> bool:
        """Helper to wait for a selector's presence across Selenium and Playwright."""
        if engine_type == "selenium":
            from selenium.webdriver.common.by import By
            from selenium.webdriver.support.ui import WebDriverWait
            from selenium.webdriver.support import expected_conditions as EC
            try:
                WebDriverWait(page_or_driver, timeout_s).until(
                    EC.presence_of_element_located((By.CSS_SELECTOR, selector))
                )
                return True
            except Exception:
                return False
        else:
            try:
                page_or_driver.wait_for_selector(selector, timeout=timeout_s * 1000)
                return True
            except Exception:
                return False

    def _extract_table_rows(self, page_or_driver, engine_type: str, base_url: str) -> List[Dict]:
        """Extract discovery records from table rows based on struktur_tabel_pt.txt DOM."""
        js = """
        (() => {
            const rows = document.querySelectorAll('table tbody tr');
            const results = [];
            rows.forEach(row => {
                const cols = row.querySelectorAll('td');
                if (cols.length < 4) return;
                const link = row.querySelector("a[href*='/detail-pt/']") || cols[3].querySelector('a');
                if (!link || !link.getAttribute('href')) return;
                results.push({
                    kode_pt: (cols[0].innerText || '').trim(),
                    singkatan: (cols[1].innerText || '').trim(),
                    nama_pt: (cols[2].innerText || '').trim(),
                    href: link.getAttribute('href')
                });
            });
            return results;
        })()
        """
        try:
            raw = self._execute_js(page_or_driver, js, engine_type)
        except Exception as e:
            self.logger.warning(f"JS extraction execution error: {e}")
            return []

        if not raw:
            return []

        records = []
        for item in (raw or []):
            href = item.get("href", "")
            full_url = urllib.parse.urljoin(base_url, href)
            parsed = urllib.parse.urlparse(full_url)
            if parsed.scheme not in ("http", "https") or not parsed.netloc:
                continue
            records.append({
                "kode_pt": item.get("kode_pt", ""),
                "singkatan": item.get("singkatan", ""),
                "nama_pt": item.get("nama_pt", ""),
                "detail_url": full_url,
            })
        return records

    def _click_next_page(self, page_or_driver, engine_type: str) -> bool:
        """Click the Next pagination button based on reference DOM structure."""
        js = """
        (() => {
            const container = document.querySelector('div.flex.justify-center.mt-10') || document.querySelector("div[class*='justify-center'][class*='mt-10']");
            if (!container) return false;
            const buttons = container.querySelectorAll('button');
            if (buttons.length < 2) return false;
            const nextBtn = buttons[buttons.length - 1];
            if (nextBtn.disabled || nextBtn.getAttribute('disabled') !== null || nextBtn.getAttribute('aria-disabled') === 'true') {
                return false;
            }
            nextBtn.click();
            return true;
        })()
        """
        try:
            clicked = self._execute_js(page_or_driver, js, engine_type)
            return bool(clicked)
        except Exception:
            return False

    # ══════════════════════════════════════════════════════════════════════════
    # Detail Extraction
    # ══════════════════════════════════════════════════════════════════════════

    def get_detail(self, page_or_driver, engine_type: str, detail_url: str) -> Dict:
        try:
            self._goto(page_or_driver, detail_url, engine_type)
            self._wait(page_or_driver, 1000, engine_type)
        except Exception as e:
            raise Exception(f"Failed loading detail page: {e}")

        # Dismiss survey popup
        self._dismiss_survey(page_or_driver, engine_type)

        # Wait for detail data readiness (value is not placeholder '...')
        self._wait_for_detail_ready(page_or_driver, engine_type, timeout_s=8)

        # Active polling extraction (up to 5s if values are still placeholder)
        detail_data = {}
        poll_start = time.time()
        while (time.time() - poll_start) < 5:
            detail_data = self._extract_detail_dom(page_or_driver, engine_type)
            # If critical fields like kode or status are valid and not '...', finish early
            if detail_data.get("kode") and detail_data.get("kode") != "..." and detail_data.get("status") != "...":
                break
            self._wait(page_or_driver, 500, engine_type)

        # Sanitize any remaining placeholder '...' to None/null
        return self._sanitize_detail(detail_data)

    def _wait_for_detail_ready(self, page_or_driver, engine_type: str, timeout_s: int = 8) -> bool:
        """Wait until detail page fields are populated with actual data (not skeleton '...')."""
        js_check = """
        (() => {
            const allP = Array.from(document.querySelectorAll('p, span, div, h1'));
            const kodeLabel = allP.find(el => (el.innerText || '').trim().toLowerCase() === 'kode');
            if (!kodeLabel || !kodeLabel.nextElementSibling) return false;
            const val = (kodeLabel.nextElementSibling.innerText || '').trim();
            return val.length > 0 && val !== '...';
        })()
        """
        start = time.time()
        while (time.time() - start) < timeout_s:
            try:
                ready = self._execute_js(page_or_driver, js_check, engine_type)
                if ready:
                    return True
            except Exception:
                pass
            self._wait(page_or_driver, 500, engine_type)
        return False

    def _dismiss_survey(self, page_or_driver, engine_type: str):
        """Hide survey form if present."""
        try:
            self._execute_js(page_or_driver,
                "var f = document.querySelector('#form-survey'); if(f) f.style.display = 'none';",
                engine_type)
        except Exception:
            pass

    def _sanitize_detail(self, data: Dict) -> Dict:
        """Sanitizes raw extracted detail data by converting skeleton placeholder '...' to None."""
        if not data:
            return {}

        def _clean_val(v):
            if v is None:
                return None
            if isinstance(v, str):
                s = v.strip()
                if s in ("...", ""):
                    return None
                return s
            return v

        kontak = data.get("kontak") or {}
        return {
            "kode": _clean_val(data.get("kode")),
            "status": _clean_val(data.get("status")),
            "akreditasi": _clean_val(data.get("akreditasi")),
            "biaya_kuliah": _clean_val(data.get("biaya_kuliah")),
            "indikator_kelengkapan_data": _clean_val(data.get("indikator_kelengkapan_data")),
            "tanggal_berdiri": _clean_val(data.get("tanggal_berdiri")),
            "no_sk_pendirian": _clean_val(data.get("no_sk_pendirian")),
            "tanggal_sk_pendirian": _clean_val(data.get("tanggal_sk_pendirian")),
            "kontak": {
                "telepon": _clean_val(kontak.get("telepon")),
                "fax": _clean_val(kontak.get("fax")),
                "email": _clean_val(kontak.get("email")),
            },
            "website": _clean_val(data.get("website")),
            "alamat": _clean_val(data.get("alamat")),
        }

    def _extract_detail_dom(self, page_or_driver, engine_type: str) -> Dict:
        js = """
        (() => {
            const clean = (t) => t ? t.replace(/\\s+/g, ' ').trim() : null;
            const data = {};
            const allP = document.querySelectorAll('p, span, div, h1');

            allP.forEach(el => {
                const label = clean(el.innerText);
                if (!label) return;
                const getVal = (node) => {
                    const sib = node.nextElementSibling;
                    return sib ? clean(sib.innerText) : null;
                };
                const lower = label.toLowerCase();
                if ((lower === 'kode' || lower === 'kode pt') && !data.kode) data.kode = getVal(el);
                else if ((lower === 'status' || lower === 'status pt') && !data.status) data.status = getVal(el);
                else if ((lower === 'akreditasi' || lower === 'akreditasi pt') && !data.akreditasi) data.akreditasi = getVal(el);
                else if ((lower === 'biaya kuliah' || lower === 'uang kuliah') && !data.biaya_kuliah) data.biaya_kuliah = getVal(el);
                else if ((lower === 'indikator kelengkapan data' || lower === 'kelengkapan data') && !data.indikator_kelengkapan_data) data.indikator_kelengkapan_data = getVal(el);
                else if ((lower === 'tanggal berdiri' || lower === 'tgl berdiri') && !data.tanggal_berdiri) data.tanggal_berdiri = getVal(el);
                else if ((lower === 'no sk pendirian' || lower === 'nomor sk pendirian') && !data.no_sk_pendirian) data.no_sk_pendirian = getVal(el);
                else if ((lower === 'tanggal sk pendirian' || lower === 'tgl sk pendirian') && !data.tanggal_sk_pendirian) data.tanggal_sk_pendirian = getVal(el);
                else if ((lower === 'alamat' || lower === 'alamat pt') && !data.alamat) {
                    const parent = el.parentElement;
                    if (parent) {
                        const addrP = parent.querySelector('p.font-semibold');
                        data.alamat = addrP ? clean(addrP.innerText) : getVal(el);
                    }
                }
            });

            // Kontak group
            const kontak = { telepon: null, fax: null, email: null };
            let website = null;
            const kontakDiv = Array.from(document.querySelectorAll('div')).find(d => {
                const p = d.querySelector('p');
                return p && clean(p.innerText) === 'Kontak';
            });
            if (kontakDiv) {
                const items = Array.from(kontakDiv.querySelectorAll('p.font-semibold'))
                    .map(p => clean(p.innerText)).filter(Boolean);
                items.forEach(text => {
                    if (text.includes('@')) { kontak.email = text; }
                    else if (text.startsWith('www.') || text.includes('.ac.id') || text.includes('.id') || text.startsWith('http')) { website = text; }
                    else if (/^[0-9\\-\\(\\)\\+\\s]+$/.test(text)) {
                        if (!kontak.telepon) kontak.telepon = text;
                        else if (!kontak.fax) kontak.fax = text;
                    }
                });
            }
            data.kontak = kontak;
            data.website = website;
            return data;
        })()
        """
        try:
            extracted = self._execute_js(page_or_driver, js, engine_type)
        except Exception as e:
            self.logger.warning(f"Detail extraction error: {e}")
            extracted = {}

        k = (extracted or {}).get("kontak") or {}
        return {
            "kode": (extracted or {}).get("kode") or None,
            "status": (extracted or {}).get("status") or None,
            "akreditasi": (extracted or {}).get("akreditasi") or None,
            "biaya_kuliah": (extracted or {}).get("biaya_kuliah") or None,
            "indikator_kelengkapan_data": (extracted or {}).get("indikator_kelengkapan_data") or None,
            "tanggal_berdiri": (extracted or {}).get("tanggal_berdiri") or None,
            "no_sk_pendirian": (extracted or {}).get("no_sk_pendirian") or None,
            "tanggal_sk_pendirian": (extracted or {}).get("tanggal_sk_pendirian") or None,
            "kontak": {
                "telepon": k.get("telepon") or None,
                "fax": k.get("fax") or None,
                "email": k.get("email") or None,
            },
            "website": (extracted or {}).get("website") or None,
            "alamat": (extracted or {}).get("alamat") or None,
        }
