import json
import logging
from playwright.sync_api import sync_playwright

logging.basicConfig(level=logging.INFO, format="%(message)s")
logger = logging.getLogger("pddikti_stealth_test")

DOMAIN_URL = "https://pddikti.kemdiktisaintek.go.id/"
SEARCH_PAGE_URL = "https://pddikti.kemdiktisaintek.go.id/perguruan-tinggi"
API_URL = "https://pddikti.kemdiktisaintek.go.id/api/v2/pt/search/filter?limit=10&page=1"

def test_stealth_and_page_fetch():
    logger.info("============================================================")
    logger.info("TEST: PLAYWRIGHT STEALTH + IN-PAGE FETCH + INTERCEPTION")
    logger.info("============================================================")
    
    # Check if playwright_stealth is available
    stealth_available = False
    try:
        from playwright_stealth import Stealth
        stealth_available = True
        logger.info("[Stealth] Library 'playwright-stealth' terdeteksi.")
    except ImportError:
        try:
            from playwright_stealth import stealth_sync
            stealth_available = True
            logger.info("[Stealth] Library 'playwright-stealth' (stealth_sync) terdeteksi.")
        except ImportError:
            logger.warning("[Stealth] 'playwright-stealth' belum diinstall, menggunakan args anti-automation dasar.")

    with sync_playwright() as p:
        # Launch Chromium dengan anti-automation flags
        browser = p.chromium.launch(
            headless=True,
            args=[
                "--no-sandbox",
                "--disable-setuid-sandbox",
                "--disable-dev-shm-usage",
                "--disable-blink-features=AutomationControlled",
            ]
        )
        
        context = browser.new_context(
            user_agent="Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/131.0.0.0 Safari/537.36",
            viewport={"width": 1920, "height": 1080},
            locale="id-ID",
            timezone_id="Asia/Jakarta",
        )
        
        page = context.new_page()
        
        # Terapkan stealth jika ada
        if stealth_available:
            try:
                from playwright_stealth import Stealth
                stealth = Stealth()
                stealth.apply_stealth_sync(page)
                logger.info("[Stealth] Stealth script berhasil diaplikasikan.")
            except Exception:
                try:
                    from playwright_stealth import stealth_sync
                    stealth_sync(page)
                    logger.info("[Stealth] stealth_sync berhasil diaplikasikan.")
                except Exception as e:
                    logger.warning(f"[Stealth] Gagal mengaplikasikan stealth: {e}")

        # Intercept background API responses
        intercepted_api_responses = []
        def handle_response(response):
            if "/api/" in response.url:
                try:
                    intercepted_api_responses.append({
                        "url": response.url,
                        "status": response.status,
                        "content_type": response.headers.get("content-type", "")
                    })
                except Exception:
                    pass

        page.on("response", handle_response)

        try:
            # 1. Buka Domain / Halaman Utama
            logger.info(f"\n[1] Membuka Website: {DOMAIN_URL}")
            resp = page.goto(DOMAIN_URL, wait_until="domcontentloaded", timeout=30000)
            logger.info(f"→ HTTP Status Halaman: {resp.status if resp else 'None'}")
            page.wait_for_timeout(3000)

            # Simpan screenshot diagnostik awal
            page.screenshot(path="debug_pddikti_homepage.png")
            logger.info("→ Screenshot disimpan ke: debug_pddikti_homepage.png")

            # 2. Uji in-page fetch (Fetch dieksekusi oleh mesin JS browser, mewarisi semua security context)
            logger.info(f"\n[2] Mengeksekusi In-Page fetch() ke API Discovery...")
            js_code = f"""
            async () => {{
                try {{
                    const response = await fetch("{API_URL}", {{
                        method: "GET",
                        headers: {{
                            "Accept": "application/json",
                            "Accept-Language": "id-ID,id;q=0.9,en-US;q=0.8,en;q=0.7"
                        }}
                    }});
                    const text = await response.text();
                    let json = null;
                    try {{
                        json = JSON.parse(text);
                    }} catch (e) {{}}
                    return {{
                        status: response.status,
                        headers: Object.fromEntries(response.headers.entries()),
                        text: text.substring(0, 300),
                        jsonStatus: json ? json.status : null,
                        dataCount: (json && json.data && Array.isArray(json.data.pt)) ? json.data.pt.length : (json && Array.isArray(json.data) ? json.data.length : null)
                    }};
                }} catch (err) {{
                    return {{ error: err.toString() }};
                }}
            }}
            """
            result = page.evaluate(js_code)
            
            logger.info("------------------------------------------------------------")
            logger.info("HASIL IN-PAGE FETCH:")
            logger.info(f"→ HTTP Status : {result.get('status')}")
            logger.info(f"→ JSON Status : {result.get('jsonStatus')}")
            logger.info(f"→ Record Count: {result.get('dataCount')}")
            logger.info(f"→ Raw Snippet : {result.get('text')}")
            if "error" in result:
                logger.info(f"→ JS Error    : {result.get('error')}")
            logger.info("------------------------------------------------------------")

            # 3. Laporkan Intercepted API calls jika ada
            if intercepted_api_responses:
                logger.info(f"\n[3] Intercepted {len(intercepted_api_responses)} API Calls saat navigasi:")
                for call in intercepted_api_responses[:5]:
                    logger.info(f"→ [{call['status']}] {call['url']}")

        except Exception as e:
            logger.error(f"[Error] Terjadi kesalahan: {e}")
            page.screenshot(path="debug_pddikti_error.png")
            logger.info("→ Screenshot error disimpan ke: debug_pddikti_error.png")
        finally:
            browser.close()

if __name__ == "__main__":
    test_stealth_and_page_fetch()
