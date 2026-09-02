import logging
import time
from typing import Dict, List, Optional, Any

class PddiktiApiScraper:
    """
    Hybrid In-Browser API Scraper for PDDIKTI.
    Executes JavaScript fetch() calls directly inside the validated browser session,
    seamlessly inheriting Cloudflare Turnstile clearance cookies, User-Agent, and TLS sessions.
    """

    DISCOVERY_API_BASE = "https://pddikti.kemdiktisaintek.go.id/api/v2/pt/search/filter"
    DETAIL_API_BASE = "https://pddikti.kemdiktisaintek.go.id/api/pt/detail"

    def __init__(self, logger: Optional[logging.Logger] = None):
        self.logger = logger or logging.getLogger("PddiktiApiScraper")

    def fetch_json_in_browser(self, page_or_driver: Any, engine_type: str, url: str,
                              retries: int = 3, retry_delay: float = 3.0) -> Optional[Dict]:
        """
        Executes an asynchronous fetch() request inside the active browser context with AbortController timeout safety (30s)
        and exponential backoff retry for handling transient 503 Service Unavailable / timeout responses.
        """
        for attempt in range(1, retries + 1):
            if engine_type == "selenium":
                js = """
                const callback = arguments[arguments.length - 1];
                const targetUrl = arguments[0];
                (async () => {
                    const controller = new AbortController();
                    const timeoutId = setTimeout(() => controller.abort(), 30000);
                    try {
                        const res = await fetch(targetUrl, {
                            method: 'GET',
                            signal: controller.signal,
                            headers: {
                                'Accept': 'application/json, text/plain, */*',
                                'Cache-Control': 'no-cache'
                            }
                        });
                        clearTimeout(timeoutId);
                        if (!res.ok) {
                            callback({ __error: true, status: res.status, statusText: res.statusText });
                            return;
                        }
                        const json = await res.json();
                        callback(json);
                    } catch (err) {
                        clearTimeout(timeoutId);
                        callback({ __error: true, message: err.toString() });
                    }
                })();
                """
                try:
                    result = page_or_driver.execute_async_script(js, url)
                    if isinstance(result, dict) and result.get("__error"):
                        status = result.get("status")
                        msg = result.get("message", "")
                        if attempt < retries:
                            delay = attempt * retry_delay
                            self.logger.warning(f"In-Browser fetch attempt {attempt}/{retries} for {url} returned status {status or msg}. Retrying in {delay}s...")
                            time.sleep(delay)
                            continue
                        else:
                            self.logger.warning(f"In-Browser fetch failed after {retries} attempts for {url}: {result}")
                            return None
                    return result
                except Exception as e:
                    if attempt < retries:
                        delay = attempt * retry_delay
                        self.logger.warning(f"Selenium async script attempt {attempt}/{retries} failed for {url}: {e}. Retrying in {delay}s...")
                        time.sleep(delay)
                        continue
                    else:
                        self.logger.error(f"Selenium async script execution failed after {retries} attempts for {url}: {e}")
                        return None
            else:
                # Playwright
                js = """
                async (targetUrl) => {
                    const controller = new AbortController();
                    const timeoutId = setTimeout(() => controller.abort(), 30000);
                    try {
                        const res = await fetch(targetUrl, {
                            method: 'GET',
                            signal: controller.signal,
                            headers: {
                                'Accept': 'application/json, text/plain, */*',
                                'Cache-Control': 'no-cache'
                            }
                        });
                        clearTimeout(timeoutId);
                        if (!res.ok) {
                            return { __error: true, status: res.status, statusText: res.statusText };
                        }
                        return await res.json();
                    } catch (err) {
                        clearTimeout(timeoutId);
                        return { __error: true, message: err.toString() };
                    }
                }
                """
                try:
                    result = page_or_driver.evaluate(js, url)
                    if isinstance(result, dict) and result.get("__error"):
                        status = result.get("status")
                        msg = result.get("message", "")
                        if attempt < retries:
                            delay = attempt * retry_delay
                            self.logger.warning(f"Playwright fetch attempt {attempt}/{retries} for {url} returned status {status or msg}. Retrying in {delay}s...")
                            time.sleep(delay)
                            continue
                        else:
                            self.logger.warning(f"Playwright fetch failed after {retries} attempts for {url}: {result}")
                            return None
                    return result
                except Exception as e:
                    if attempt < retries:
                        delay = attempt * retry_delay
                        self.logger.warning(f"Playwright evaluate attempt {attempt}/{retries} failed for {url}: {e}. Retrying in {delay}s...")
                        time.sleep(delay)
                        continue
                    else:
                        self.logger.error(f"Playwright evaluate failed after {retries} attempts for {url}: {e}")
                        return None
        return None

    def discover_campuses(self, page_or_driver: Any, engine_type: str,
                          target_count: Optional[int] = None, limit_per_page: int = 15) -> List[Dict]:
        """
        Discovers campus records by querying Endpoint 1 (/api/v2/pt/search/filter) in pages.
        Unwraps double-nested JSON structure: response['data']['data'].
        If target_count is None, fetches all available campuses across all pages in Indonesia.
        """
        import json
        target_label = f"{target_count}" if target_count else "ALL"
        self.logger.info(f"Discovering campuses via API (Target: {target_label}, Limit/Page: {limit_per_page})...")
        discovered: List[Dict] = []
        seen_ids = set()
        page = 1

        while target_count is None or len(discovered) < target_count:
            api_url = f"{self.DISCOVERY_API_BASE}?limit={limit_per_page}&page={page}&"
            self.logger.info(f"Fetching Discovery API Page {page}...")
            
            response = self.fetch_json_in_browser(page_or_driver, engine_type, api_url)
            if not response:
                self.logger.warning(f"Discovery API returned empty response on page {page}.")
                break

            # If response is returned as string from browser, parse it into JSON
            if isinstance(response, str):
                try:
                    response = json.loads(response)
                except Exception as e:
                    self.logger.warning(f"Failed parsing response string as JSON on page {page}: {e}")
                    break

            # Unwrap double-nested response: response["data"]["data"]
            data_layer1 = response.get("data") if isinstance(response, dict) else response
            records = []
            total_items = None
            total_pages = None

            if isinstance(data_layer1, dict):
                records = data_layer1.get("data") or []
                total_items = data_layer1.get("totalItems")
                total_pages = data_layer1.get("totalPages")
            elif isinstance(data_layer1, list):
                records = data_layer1

            if not records:
                self.logger.info(f"No more records found in Discovery API on page {page}.")
                break

            added = 0
            for item in records:
                if not isinstance(item, dict):
                    continue

                if target_count and len(discovered) >= target_count:
                    break

                # Extract campus UUID hash (id_sp)
                id_sp = item.get("id_sp") or item.get("id")
                if not id_sp:
                    continue
                if id_sp in seen_ids:
                    continue
                seen_ids.add(id_sp)

                nama_pt = (item.get("nama_pt") or item.get("nama") or "").strip()
                singkatan = (item.get("nama_singkat") or item.get("singkatan") or "").strip()
                status_pt = (item.get("status_pt") or item.get("status") or "").strip()
                jenis_pt = (item.get("jenis_pt") or "").strip()
                kab_kota = (item.get("kab_kota_pt") or "").strip()
                provinsi = (item.get("provinsi_pt") or "").strip()
                wilayah = f"{kab_kota}, {provinsi}".strip(", ")
                akreditasi = (item.get("akreditasi") or "").strip()
                biaya_kuliah = (item.get("range_biaya_kuliah") or "").strip()
                jumlah_prodi = item.get("jumlah_prodi")

                discovered.append({
                    "id_sp": id_sp,
                    "nama_pt": nama_pt,
                    "nama_singkat": singkatan,
                    "status_pt": status_pt,
                    "jenis_pt": jenis_pt,
                    "kab_kota_pt": kab_kota,
                    "provinsi_pt": provinsi,
                    "wilayah": wilayah,
                    "jumlah_prodi": jumlah_prodi,
                    "range_biaya_kuliah": biaya_kuliah,
                    "akreditasi": akreditasi,
                    "detail_url": f"{self.DETAIL_API_BASE}/{id_sp}",
                    "raw_discovery": item
                })
                added += 1

            target_display = f"/{target_count}" if target_count else ""
            self.logger.info(f"Page {page}: +{added} unique campuses (Total: {len(discovered)}{target_display})")

            # Check if we reached the total available items or pages
            if total_items and len(discovered) >= total_items:
                self.logger.info(f"Reached the total number of available records in PDDIKTI API ({len(discovered)}/{total_items}).")
                break
            if total_pages and page >= total_pages:
                self.logger.info(f"Reached the last page of PDDIKTI API ({page}/{total_pages}).")
                break

            page += 1
            # Small throttle between API page requests
            time.sleep(0.3)

        return discovered

    def get_campus_detail(self, page_or_driver: Any, engine_type: str, campus_id: str) -> Optional[Dict]:
        """
        Fetches complete campus detail data directly from Endpoint 2 (/api/pt/detail/{id_sp}).
        Cleans up string values with whitespace stripping.
        """
        import json
        if not campus_id:
            return None

        detail_url = f"{self.DETAIL_API_BASE}/{campus_id}"
        response = self.fetch_json_in_browser(page_or_driver, engine_type, detail_url)
        if not response:
            return None

        # Parse if returned as string
        if isinstance(response, str):
            try:
                response = json.loads(response)
            except Exception:
                return None

        # Unwrap the data payload
        detail_raw = response
        if isinstance(response, dict) and "data" in response and isinstance(response["data"], dict):
            detail_raw = response["data"]

        if not isinstance(detail_raw, dict):
            return {"raw_detail": detail_raw}

        # Clean string values (whitespace stripping and empty string to None)
        cleaned_detail = {}
        for k, v in detail_raw.items():
            if isinstance(v, str):
                s = v.strip()
                cleaned_detail[k] = s if s else None
            else:
                cleaned_detail[k] = v

        return cleaned_detail
