import json
import logging
from pathlib import Path
from playwright.sync_api import sync_playwright

logging.basicConfig(level=logging.INFO, format="%(message)s")
logger = logging.getLogger("pddikti_user_session")

DOMAIN_URL = "https://pddikti.kemdiktisaintek.go.id/perguruan-tinggi"
API_URL = "https://pddikti.kemdiktisaintek.go.id/api/v2/pt/search/filter?limit=10&page=1"
USER_DATA_DIR = Path("data/pddikti_browser_profile")

def run_user_assisted_session():
    logger.info("============================================================")
    logger.info("PDDIKTI USER-ASSISTED SESSION (HEADFUL BROWSER)")
    logger.info("============================================================")
    logger.info("Petunjuk:")
    logger.info("1. Jendela browser Chromium akan terbuka di layar Anda.")
    logger.info("2. Jika muncul verifikasi Cloudflare / Turnstile, silakan klik")
    logger.info("   atau selesaikan verifikasi secara manual di jendela browser.")
    logger.info("3. Setelah halaman berhasil dimuat, skrip akan otomatis")
    logger.info("   mengeksekusi request API menggunakan sesi yang valid.")
    logger.info("============================================================\n")

    USER_DATA_DIR.mkdir(parents=True, exist_ok=True)

    with sync_playwright() as p:
        # Buka persistent context agar cookies dan session tersimpan
        context = p.chromium.launch_persistent_context(
            user_data_dir=str(USER_DATA_DIR),
            headless=False,  # Jendela browser ditampilkan ke user
            viewport={"width": 1280, "height": 800},
            locale="id-ID",
            args=[
                "--disable-blink-features=AutomationControlled",
            ]
        )

        page = context.pages[0] if context.pages else context.new_page()

        try:
            logger.info(f"Membuka halaman: {DOMAIN_URL}")
            page.goto(DOMAIN_URL, timeout=60000)

            print("\n" + "=" * 60)
            print("[AKSI DIPERLUKAN]")
            print("1. Lihat jendela browser yang terbuka.")
            print("2. Centang/selesaikan verifikasi Turnstile/Cloudflare secara manual.")
            print("3. Tunggu hingga halaman daftar perguruan tinggi terbuka penuh.")
            print("4. KEMUDIAN, tekan ENTER di terminal ini untuk melanjutkan.")
            print("=" * 60 + "\n")
            
            input("Tekan [ENTER] di sini setelah halaman website PDDIKTI berhasil terbuka...")

            # Ambil title dan URL saat ini
            current_title = page.title()
            logger.info(f"✓ Melanjutkan dengan Title: '{current_title}' | URL: {page.url}")

            # Eksekusi in-page fetch menggunakan session yang sudah terverifikasi
            logger.info(f"\nMengeksekusi In-Page fetch ke: {API_URL}")
            js_code = f"""
            async () => {{
                try {{
                    const response = await fetch("{API_URL}", {{
                        method: "GET",
                        headers: {{
                            "Accept": "application/json"
                        }}
                    }});
                    const text = await response.text();
                    let json = null;
                    try {{
                        json = JSON.parse(text);
                    }} catch (e) {{}}
                    return {{
                        status: response.status,
                        jsonStatus: json ? json.status : null,
                        dataPreview: json ? json.data : text.substring(0, 300)
                    }};
                }} catch (err) {{
                    return {{ error: err.toString() }};
                }}
            }}
            """
            result = page.evaluate(js_code)

            logger.info("------------------------------------------------------------")
            logger.info("HASIL PENGUJIAN SESI:")
            logger.info(f"→ HTTP Status : {result.get('status')}")
            logger.info(f"→ JSON Status : {result.get('jsonStatus')}")
            
            data_preview = result.get("dataPreview")
            if isinstance(data_preview, dict) and "pt" in data_preview:
                pt_list = data_preview["pt"]
                logger.info(f"→ Jumlah Kampus Ditemukan: {len(pt_list)}")
                if pt_list:
                    logger.info(f"→ Contoh Kampus Pertama  : {pt_list[0].get('nama_pt', 'N/A')}")
            else:
                logger.info(f"→ Data Snippet: {data_preview}")
                
            logger.info("------------------------------------------------------------")

        except Exception as e:
            logger.error(f"Terjadi error: {e}")
        finally:
            logger.info("\nMenutup browser session...")
            context.close()

if __name__ == "__main__":
    run_user_assisted_session()
