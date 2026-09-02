import os
import sys
import time
from pathlib import Path
import json
import datetime
import argparse
from collections import Counter

# Add src directory to path
sys.path.append(str(Path(__file__).parent.parent))

from src.config import INPUT_CSV, BASE_URL, DATA_DIR, OUTPUT_DIR
from src.loaders.csv_loader import load_campus_names
from src.utils.slug_generator import generate_slug
from src.scrapers.http_scraper import fetch_html
from src.extractors.quipper_extractor import extract_siteroot_json, extract_quipper_data
from src.mappers.quipper_mapper import QuipperMapper
from src.validators.data_validator import DataValidator
from src.storage.json_storage import JsonStorage
from src.storage.csv_storage import CsvStorage
from src.utils.logger import setup_logger
from src.enrichers.image_enricher import ExternalImageEnricher

def print_progress(logger, index, total, name, status, duration, stages, error=None):
    logger.info(f"[{index:03d}/{total:03d}] {name}")
    logger.info(f"    Status: {status} ({duration:.2f}s)")
    if error:
        logger.info(f"    Error : {error}")
    
    keys = list(stages.keys())
    for i, key in enumerate(keys):
        prefix = "    └─ " if i == len(keys) - 1 else "    ├─ "
        mark = stages[key]
        if mark:  # Only print if stage has a mark (was attempted)
            logger.info(f"{prefix}{key:<10} {mark}")

def parse_warning(warn_str: str) -> str:
    """Extracts a stable warning code/category from the warning string."""
    if warn_str.startswith("UNMAPPED_CAMPUS_TYPE"):
        return "UNMAPPED_CAMPUS_TYPE"
    if warn_str.startswith("Prodi Akreditasi Warning"):
        return "ACCREDITATION_UNRECOGNIZED"
    if warn_str.startswith("WARNING:"):
        return warn_str.split(":", 1)[1].strip()
    return warn_str

def run_pddikti_poc(args, logger):
    from src.scrapers.pddikti_scraper import PddiktiScraper
    from src.scrapers.pddikti_browser import launch_best_engine, close_engine
    from src.storage.pddikti_json_storage import PddiktiJsonStorage
    
    logger.info("=" * 60)
    logger.info("PDDIKTI CAMPUS SCRAPER (PoC)")
    logger.info("=" * 60)
    logger.info(f"Started : {datetime.datetime.now().astimezone().strftime('%Y-%m-%d %H:%M:%S %z')}")
    logger.info(f"Mode    : PDDIKTI-POC")
    logger.info("=" * 60)
    logger.info("")
    
    scraper = PddiktiScraper(logger=logger)
    storage = PddiktiJsonStorage(OUTPUT_DIR)
    
    search_url = getattr(args, 'pddikti_url', None) or "https://pddikti.kemdiktisaintek.go.id/search/pt/Universitas"
    is_headless = getattr(args, 'headless', False)
    pipeline_start_time = time.time()

    # Launch browser with multi-engine fallback: Camoufox → undetected-chromedriver → Playwright
    logger.info("Starting browser session...")
    engine_info = None
    try:
        profile_dir = str(DATA_DIR / 'pddikti_browser_profile')
        os.makedirs(profile_dir, exist_ok=True)
        engine_info = launch_best_engine(headless=is_headless, profile_dir=profile_dir)
        engine_type = engine_info["type"]
        engine_name = engine_info["engine"]
        logger.info(f"Browser Engine: {engine_name} ({engine_type})")

        # Get the page/driver handle
        if engine_type == "selenium":
            page_or_driver = engine_info["driver"]
        else:
            page_or_driver = engine_info["page"]

        # 1. Entry Point: Root Domain + CAPTCHA Checkpoint Handling + UI Navigation
        nav_ok = scraper.navigate_root_and_handle_checkpoint(page_or_driver, engine_type, search_url=search_url)
        if not nav_ok:
            logger.error("Root domain navigation or CAPTCHA resolution failed. Aborting PoC.")
            logger.info("DISCOVERY ✗")
            return

        # 2. Discovery Phase via DOM
        try:
            discovery_records = scraper.discover(page_or_driver, engine_type, max_records=100)
        except Exception as e:
            logger.error(f"DISCOVERY FAILED: {e}")
            logger.info("DISCOVERY ✗")
            return

        if not discovery_records:
            logger.error("No discovery records found. Aborting PoC.")
            logger.info("DISCOVERY ✗")
            return

        logger.info(f"DISCOVERY ✓ ({len(discovery_records)} targets found)\n")

        success_count = 0
        failure_count = 0
        failed_campuses = []

        # 3. Detail Phase in the same browser session
        for i, record in enumerate(discovery_records, 1):
            campus_name = record.get('nama_pt') or f"Campus {record.get('kode_pt')}"
            detail_url = record.get('detail_url')

            logger.info(f"[{i:03d}/{len(discovery_records):03d}] {campus_name}")

            if not detail_url:
                logger.info("    Status: FAILED")
                logger.info("    ├─ DETAIL  ✗")
                logger.info("    └─ STORE   -")
                failure_count += 1
                failed_campuses.append(campus_name)
                continue

            try:
                detail_data = scraper.get_detail(page_or_driver, engine_type, detail_url)
                storage.add({"discovery": record, "detail": detail_data})
                logger.info("    Status: SUCCESS")
                logger.info("    ├─ DETAIL  ✓")
                logger.info("    └─ STORE   ✓")
                success_count += 1
            except Exception as e:
                logger.warning(f"Failed extracting detail for {campus_name}: {e}")
                logger.info("    Status: FAILED")
                logger.info("    ├─ DETAIL  ✗")
                logger.info("    └─ STORE   -")
                failure_count += 1
                failed_campuses.append(campus_name)

    except Exception as e:
        logger.error(f"Browser Session Error: {e}")
        return
    finally:
        if engine_info:
            close_engine(engine_info)

    output_file = storage.finalize()

    logger.info("\n" + "=" * 60)
    logger.info("PDDIKTI PoC SUMMARY")
    logger.info("=" * 60)
    logger.info(f"Targets : {len(discovery_records)}")
    logger.info(f"Success : {success_count}")
    logger.info(f"Failed  : {failure_count}")
    logger.info(f"Output  : {output_file}")
    logger.info("=" * 60)


def run_pddikti_directory_poc(args, logger):
    from src.scrapers.pddikti_scraper import PddiktiScraper
    from src.scrapers.pddikti_browser import launch_best_engine, close_engine
    from src.storage.pddikti_json_storage import PddiktiJsonStorage
    
    target_count = getattr(args, 'target_count', 100) or 100
    is_resuming = getattr(args, 'resume', False)
    is_headless = getattr(args, 'headless', False)
    
    logger.info("=" * 60)
    logger.info("PDDIKTI CAMPUS DIRECTORY SCRAPER (Card Mode)")
    logger.info("=" * 60)
    logger.info(f"Started : {datetime.datetime.now().astimezone().strftime('%Y-%m-%d %H:%M:%S %z')}")
    logger.info(f"Mode    : PDDIKTI-DIRECTORY (Target: {target_count})")
    logger.info(f"Resume  : {is_resuming}")
    logger.info("=" * 60)
    logger.info("")

    storage = PddiktiJsonStorage(OUTPUT_DIR)
    already_saved = 0
    if is_resuming:
        already_saved = storage.load_existing()
        logger.info(f"Resuming session: {already_saved} campus records loaded from checkpoint.\n")

    scraper = PddiktiScraper(logger=logger)
    engine_info = None
    success_count = already_saved
    failure_count = 0

    try:
        profile_dir = str(DATA_DIR / 'pddikti_browser_profile')
        os.makedirs(profile_dir, exist_ok=True)
        engine_info = launch_best_engine(headless=is_headless, profile_dir=profile_dir)
        engine_type = engine_info["type"]
        engine_name = engine_info["engine"]
        logger.info(f"Browser Engine: {engine_name} ({engine_type})")

        page_or_driver = engine_info["driver"] if engine_type == "selenium" else engine_info["page"]

        # 1. Entry Point: Navigate to /perguruan-tinggi directory via menu card
        nav_ok = scraper.navigate_to_directory(page_or_driver, engine_type)
        if not nav_ok:
            logger.error("Directory navigation failed. Aborting.")
            return

        # 2. Adjust Pagination Limit to 48 per page
        scraper._try_set_pagination_limit(page_or_driver, engine_type, "48")

        page_num = storage.last_page if is_resuming else 1
        
        # Fast-forward to checkpoint page if resuming beyond page 1
        if is_resuming and page_num > 1:
            logger.info(f"Fast-forwarding to checkpoint page {page_num}...")
            for _ in range(page_num - 1):
                scraper._click_directory_next_page(page_or_driver, engine_type)
                scraper._wait(page_or_driver, 2000, engine_type)

        while success_count < target_count:
            curr_page_label = scraper._get_directory_page_number(page_or_driver, engine_type)
            logger.info(f"\n--- Directory Page {page_num} ({curr_page_label or f'Page {page_num}'}) ---")

            # Wait for cards in grid
            cards_ready = scraper._wait_for_directory_cards(page_or_driver, engine_type, timeout_s=30)
            if not cards_ready:
                logger.warning(f"Cards not rendering on page {page_num}. Attempting reload...")
                scraper._reload(page_or_driver, engine_type)
                scraper._wait(page_or_driver, 3000, engine_type)

            cards = scraper._extract_directory_cards(page_or_driver, engine_type)
            if not cards:
                logger.warning(f"No cards found on page {page_num}. Directory scanning finished.")
                break

            logger.info(f"Discovered {len(cards)} campus cards on page {page_num}.")

            # Process each card on the current page
            for card in cards:
                if success_count >= target_count:
                    break

                campus_name = card.get("nama_pt", "Unknown Campus")
                card_idx = card.get("card_index", 0)

                # Skip if already in storage checkpoint
                if storage.is_completed(detail_url="", kode_pt=campus_name):
                    continue

                logger.info(f"[{success_count + 1:03d}/{target_count:03d}] {campus_name}")

                # Retry loop for network tolerance
                retries = 3
                detail_saved = False
                for attempt in range(1, retries + 1):
                    try:
                        # Click "Lihat Detail" button on card
                        if engine_type == "selenium":
                            from selenium.webdriver.common.by import By
                            btns = page_or_driver.find_elements(By.XPATH, "//div[contains(@class,'h-[380px]')]//button[contains(text(),'Lihat Detail')] | //button[contains(text(),'Lihat Detail')]")
                            if card_idx < len(btns):
                                btns[card_idx].click()
                            else:
                                raise RuntimeError("Detail button index out of range")
                        else:
                            all_btns = page_or_driver.query_selector_all("button:has-text('Lihat Detail')")
                            if card_idx < len(all_btns):
                                all_btns[card_idx].click()
                            else:
                                raise RuntimeError("Detail button index out of range")

                        # Wait for transition to detail page
                        scraper._wait_for_url_contains(page_or_driver, "/detail-pt/", 10, engine_type)
                        detail_url = scraper._get_page_url(page_or_driver, engine_type)
                        card["detail_url"] = detail_url

                        # Extract detail data with skeleton placeholder polling & sanitization
                        scraper._dismiss_survey(page_or_driver, engine_type)
                        scraper._wait_for_detail_ready(page_or_driver, engine_type, timeout_s=8)

                        detail_data = {}
                        poll_start = time.time()
                        while (time.time() - poll_start) < 5:
                            detail_data = scraper._extract_detail_dom(page_or_driver, engine_type)
                            if detail_data.get("kode") and detail_data.get("kode") != "..." and detail_data.get("status") != "...":
                                break
                            scraper._wait(page_or_driver, 500, engine_type)

                        detail_data = scraper._sanitize_detail(detail_data)

                        # Atomic Streaming Flush to disk
                        storage.add_and_flush({"discovery": card, "detail": detail_data}, current_page=page_num)
                        logger.info("    Status: SUCCESS")
                        logger.info("    ├─ DETAIL  ✓")
                        logger.info("    └─ STORE   ✓ (Saved to disk)")
                        success_count += 1
                        detail_saved = True

                        # Navigate back to directory
                        scraper._goto(page_or_driver, "https://pddikti.kemdiktisaintek.go.id/perguruan-tinggi", engine_type)
                        scraper._wait_for_directory_cards(page_or_driver, engine_type, timeout_s=15)
                        break

                    except Exception as e:
                        if attempt < retries:
                            logger.warning(f"    Attempt {attempt} failed ({e}). Retrying in {attempt * 2}s...")
                            time.sleep(attempt * 2)
                            scraper._goto(page_or_driver, "https://pddikti.kemdiktisaintek.go.id/perguruan-tinggi", engine_type)
                            scraper._wait_for_directory_cards(page_or_driver, engine_type, timeout_s=15)
                        else:
                            logger.error(f"    Failed extracting {campus_name} after {retries} attempts: {e}")
                            logger.info("    Status: FAILED")
                            logger.info("    ├─ DETAIL  ✗")
                            logger.info("    └─ STORE   -")
                            failure_count += 1
                            scraper._goto(page_or_driver, "https://pddikti.kemdiktisaintek.go.id/perguruan-tinggi", engine_type)
                            scraper._wait_for_directory_cards(page_or_driver, engine_type, timeout_s=15)

            if success_count >= target_count:
                break

            # Next Page Transition
            logger.info("Navigating to next directory page...")
            before_page = scraper._get_directory_page_number(page_or_driver, engine_type)
            next_clicked = scraper._click_directory_next_page(page_or_driver, engine_type)
            if not next_clicked:
                logger.info("No active Next button. Directory traversal complete.")
                break

            # Smart Page-State Change Wait (wait up to 15s for page indicator to change)
            page_changed = False
            start_wait = time.time()
            while (time.time() - start_wait) < 15:
                scraper._wait(page_or_driver, 1000, engine_type)
                after_page = scraper._get_directory_page_number(page_or_driver, engine_type)
                if after_page and after_page != before_page:
                    page_changed = True
                    break

            page_num += 1
            storage.save_checkpoint(last_page=page_num)

    except KeyboardInterrupt:
        logger.info("\n[INTERRUPT] Received Ctrl+C. Performing graceful shutdown and saving progress...")
    except Exception as e:
        logger.error(f"Directory Session Error: {e}")
    finally:
        if engine_info:
            close_engine(engine_info)

    output_file = storage.finalize()

    logger.info("\n" + "=" * 60)
    logger.info("PDDIKTI DIRECTORY SUMMARY")
    logger.info("=" * 60)
    logger.info(f"Target Count: {target_count}")
    logger.info(f"Success     : {success_count}")
    logger.info(f"Failed      : {failure_count}")
    logger.info(f"Output File : {output_file}")
    logger.info(f"Checkpoint  : {storage.checkpoint_path}")
    logger.info("=" * 60)


def run_pddikti_api_pipeline(args, logger):
    from src.scrapers.pddikti_api_scraper import PddiktiApiScraper
    from src.scrapers.pddikti_browser import launch_best_engine, close_engine
    from src.scrapers.pddikti_scraper import PddiktiScraper
    from src.storage.pddikti_json_storage import PddiktiJsonStorage

    target_count = getattr(args, 'target_count', None)
    target_label = f"{target_count}" if target_count else "ALL (~6,765)"
    is_resuming = getattr(args, 'resume', False)
    is_headless = getattr(args, 'headless', False)

    logger.info("=" * 60)
    logger.info("PDDIKTI IN-BROWSER API SCRAPER (Option B)")
    logger.info("=" * 60)
    logger.info(f"Started : {datetime.datetime.now().astimezone().strftime('%Y-%m-%d %H:%M:%S %z')}")
    logger.info(f"Mode    : PDDIKTI-API (Target: {target_label})")
    logger.info(f"Resume  : {is_resuming}")
    logger.info("=" * 60)
    logger.info("")

    storage = PddiktiJsonStorage(OUTPUT_DIR)
    already_saved = 0
    if is_resuming:
        already_saved = storage.load_existing()
        logger.info(f"Resuming session: {already_saved} campus records loaded from checkpoint.\n")

    api_scraper = PddiktiApiScraper(logger=logger)
    dom_scraper = PddiktiScraper(logger=logger)
    engine_info = None
    success_count = already_saved
    failure_count = 0

    try:
        profile_dir = str(DATA_DIR / 'pddikti_browser_profile')
        os.makedirs(profile_dir, exist_ok=True)
        engine_info = launch_best_engine(headless=is_headless, profile_dir=profile_dir)
        engine_type = engine_info["type"]
        engine_name = engine_info["engine"]
        logger.info(f"Browser Engine: {engine_name} ({engine_type})")

        page_or_driver = engine_info["driver"] if engine_type == "selenium" else engine_info["page"]
        if engine_type == "selenium":
            try:
                page_or_driver.set_script_timeout(45)
            except Exception:
                pass

        # 1. Entry Point: Open Root Domain & Solve Cloudflare Turnstile to obtain session clearance
        logger.info("Resolving Cloudflare on Root Domain...")
        dom_scraper._goto(page_or_driver, "https://pddikti.kemdiktisaintek.go.id/", engine_type)
        dom_scraper._wait(page_or_driver, 2000, engine_type)
        if dom_scraper._is_checkpoint_active(page_or_driver, engine_type):
            if not dom_scraper._wait_for_checkpoint(page_or_driver, engine_type, "Root Domain"):
                logger.error("Failed resolving Cloudflare Turnstile checkpoint. Aborting.")
                return

        logger.info("Cloudflare Handshake Complete ✓. Waiting 3s for session settlement...\n")
        time.sleep(3)

        # 2. Discovery Phase via API
        discovery_records = api_scraper.discover_campuses(
            page_or_driver, engine_type, target_count=target_count, limit_per_page=15
        )

        if not discovery_records:
            logger.error("No discovery records returned by API. Aborting.")
            return

        total_targets = len(discovery_records)
        logger.info(f"\nDiscovery API Complete ✓ ({total_targets} targets retrieved)\n")

        # 3. Detail Phase via API
        for i, record in enumerate(discovery_records, 1):
            if target_count and success_count >= target_count:
                break

            campus_name = record.get("nama_pt", "Unknown Campus")
            campus_id = record.get("id_sp") or record.get("id") or record.get("kode_pt")

            # Check if already completed
            if storage.is_completed(detail_url=record.get("detail_url", ""), kode_pt=campus_id):
                continue

            target_display = f"{target_count:04d}" if target_count else f"{total_targets:04d}"
            logger.info(f"[{success_count + 1:04d}/{target_display}] {campus_name} (ID: {campus_id})")

            # Fetch detail via API
            try:
                detail_data = api_scraper.get_campus_detail(page_or_driver, engine_type, campus_id)
                if not detail_data:
                    # Fallback to direct URL if API payload empty
                    detail_url = f"https://pddikti.kemdiktisaintek.go.id/detail-pt/{campus_id}"
                    detail_data = dom_scraper.get_detail(page_or_driver, engine_type, detail_url)

                storage.add_and_flush({"discovery": record, "detail": detail_data})
                logger.info("    Status: SUCCESS")
                logger.info("    ├─ DETAIL  ✓ (API)")
                logger.info("    └─ STORE   ✓ (Saved to disk)")
                success_count += 1
            except Exception as e:
                logger.warning(f"    Failed detail for {campus_name}: {e}")
                logger.info("    Status: FAILED")
                logger.info("    ├─ DETAIL  ✗")
                logger.info("    └─ STORE   -")
                failure_count += 1

            # Micro-throttle between API detail requests
            time.sleep(0.2)

    except KeyboardInterrupt:
        logger.info("\n[INTERRUPT] Received Ctrl+C. Performing graceful shutdown and saving progress...")
    except Exception as e:
        logger.error(f"API Session Error: {e}")
    finally:
        if engine_info:
            close_engine(engine_info)

    output_file = storage.finalize()

    # Auto-export to CSV
    csv_file = None
    try:
        from src.storage.pddikti_csv_storage import PddiktiCsvStorage
        csv_storage = PddiktiCsvStorage(OUTPUT_DIR)
        csv_file = csv_storage.save_all(storage.campuses)
    except Exception as ce:
        logger.warning(f"Failed auto-exporting to CSV: {ce}")

    logger.info("\n" + "=" * 60)
    logger.info("PDDIKTI API PIPELINE SUMMARY")
    logger.info("=" * 60)
    logger.info(f"Target Count: {target_label}")
    logger.info(f"Success     : {success_count}")
    logger.info(f"Failed      : {failure_count}")
    logger.info(f"Output JSON : {output_file}")
    if csv_file:
        logger.info(f"Output CSV  : {csv_file}")
    logger.info(f"Checkpoint  : {storage.checkpoint_path}")
    logger.info("=" * 60)


def load_env_file():
    """Loads environment variables from .env file if present in workspace root."""
    env_file = Path(__file__).parent.parent / ".env"
    if env_file.exists():
        try:
            with open(env_file, 'r', encoding='utf-8') as f:
                for line in f:
                    line = line.strip()
                    if line and not line.startswith('#') and '=' in line:
                        k, v = line.split('=', 1)
                        k = k.strip()
                        v = v.strip().strip('"').strip("'")
                        if k not in os.environ:
                            os.environ[k] = v
        except Exception:
            pass


def run_enrich_kampus_pipeline(args, logger):
    """
    Enriches scraped PDDIKTI campus data using Google Places API (New) & Geocoding API,
    and extracts official campus logos directly from official campus websites
    to produce the exact 10-field KAMPUS dataset matching Table 3.1 in docs/data-structure.md:
    1. kode_kampus
    2. nama_kampus
    3. singkatan_kampus
    4. akreditasi
    5. alamat
    6. website_url
    7. logo_url
    8. banner_url
    9. deskripsi
    10. koordinat
    """
    import csv
    from src.extractors.gmaps_enricher import GoogleMapsEnricher
    from src.extractors.wikipedia_enricher import WikipediaEnricher
    from src.extractors.logo_extractor import CampusLogoExtractor
    from src.utils.factual_description_generator import generate_factual_description
    from src.validators.duplicate_auditor import DuplicateAuditor
    from src.storage.kampus_extracted_storage import KampusExtractedStorage

    # 1. Resolve API Key
    api_key = getattr(args, 'gmaps_key', None) or os.getenv('GOOGLE_MAPS_API_KEY')
    if not api_key:
        logger.error("Error: Google Maps API Key not found! Please define GOOGLE_MAPS_API_KEY in .env or pass --gmaps-key.")
        return

    # 2. Source Data Resolution (Prefer pddikti_campuses.csv, fallback to JSON)
    source_csv = OUTPUT_DIR / "pddikti_campuses.csv"
    if not source_csv.exists():
        logger.error(f"Error: Source data file {source_csv} does not exist. Please run scraping first.")
        return

    target_count = getattr(args, 'target_count', None)
    is_resuming = getattr(args, 'resume', False)

    target_label = f"{target_count}" if target_count else "ALL Eligible (~4,300)"
    logger.info("=" * 60)
    logger.info("GOOGLE MAPS, WIKIPEDIA & WEBSITE LOGO CAMPUS ENRICHMENT")
    logger.info("=" * 60)
    logger.info(f"Started     : {datetime.datetime.now().astimezone().strftime('%Y-%m-%d %H:%M:%S %z')}")
    logger.info(f"Source Data : {source_csv}")
    logger.info(f"Target Count: {target_label}")
    logger.info(f"Resume Mode : {is_resuming}")
    logger.info("=" * 60)
    logger.info("")

    # 3. Read Source Rows & Filter by Status (Aktif & Pembinaan)
    all_rows = []
    with open(source_csv, 'r', encoding='utf-8-sig') as f:
        reader = csv.DictReader(f)
        for r in reader:
            all_rows.append(r)

    total_scanned = len(all_rows)
    aktif_rows = [r for r in all_rows if r.get("status_pt", "").strip().lower() == "aktif"]
    pembinaan_rows = [r for r in all_rows if r.get("status_pt", "").strip().lower() == "pembinaan"]
    eligible_rows = aktif_rows + pembinaan_rows
    excluded_count = total_scanned - len(eligible_rows)

    # 4. Deduplicate rows with IDENTICAL kode_pt (Retaining different kode_pt even if names are identical)
    seen_kode_pt = set()
    deduped_rows = []
    duplicate_codes_count = 0
    for r in eligible_rows:
        k_pt = r.get("kode_pt", "").strip()
        if k_pt and k_pt in seen_kode_pt:
            duplicate_codes_count += 1
            continue
        if k_pt:
            seen_kode_pt.add(k_pt)
        deduped_rows.append(r)

    logger.info(f"Source Records  : {total_scanned}")
    logger.info(f"├─ Status Aktif      : {len(aktif_rows)} (Priority 1)")
    logger.info(f"├─ Status Pembinaan  : {len(pembinaan_rows)} (Priority 2)")
    logger.info(f"├─ Total Eligible    : {len(eligible_rows)}")
    logger.info(f"├─ Deduped Identical : {duplicate_codes_count} duplicate rows (same kode_pt) removed")
    logger.info(f"├─ Total Unique PT   : {len(deduped_rows)} to be processed")
    logger.info(f"└─ Excluded (Other)  : {excluded_count} (Tutup, Alih Bentuk, Alih Kelola)\n")

    total_available = len(deduped_rows)

    # Run Duplicate Name Audit Indicator on Unique Eligible Campuses
    auditor = DuplicateAuditor(logger=logger)
    indicator_json = OUTPUT_DIR / "duplicate_campus_indicator.json"
    auditor.audit_records(deduped_rows, output_json_path=indicator_json)

    storage = KampusExtractedStorage(OUTPUT_DIR)
    already_saved = 0
    if is_resuming:
        already_saved = storage.load_checkpoint()
        logger.info(f"Resuming session: {already_saved} records loaded from checkpoint.")

    enricher = GoogleMapsEnricher(api_key=api_key, logger=logger)
    wiki_enricher = WikipediaEnricher(logger=logger)
    logo_extractor = CampusLogoExtractor(logger=logger)
    success_count = already_saved
    processed_count = 0

    try:
        for idx, row in enumerate(deduped_rows, 1):
            if target_count and processed_count >= target_count:
                break

            kode_pt = row.get("kode_pt", "").strip()
            nama_pt = row.get("nama_pt", "").strip()
            status_pt = row.get("status_pt", "").strip()
            singkatan = row.get("singkatan", "").strip()
            akreditasi = row.get("akreditasi", "").strip()
            pddikti_alamat = row.get("alamat", "").strip()
            kab_kota = row.get("kab_kota", "").strip()
            provinsi = row.get("provinsi", "").strip()

            # Skip if already completed in checkpoint
            if is_resuming and storage.is_completed(kode_pt, nama_pt):
                continue

            target_display = f"{target_count:04d}" if target_count else f"{total_available:04d}"
            logger.info(f"[{processed_count + 1:04d}/{target_display}] {nama_pt} (Kode: {kode_pt or '-'}, Status: {status_pt})")

            location_hint = f"{kab_kota} {provinsi}".strip()

            # 1. Google Places API Search (Address, Fresh Website, Location Coordinates)
            place = enricher.search_place(nama_pt, location_hint=location_hint)

            alamat_final = pddikti_alamat
            website_final = ""  # Fresh resolution only (ignoring raw PDDIKTI website)
            banner_url = ""     # Postponed per specification
            koordinat_wkt = ""

            if place:
                gmaps_addr = place.get("formattedAddress", "")
                if gmaps_addr:
                    alamat_final = gmaps_addr
                
                gmaps_web = place.get("websiteUri", "")
                if gmaps_web:
                    website_final = gmaps_web.strip()
                
                loc = place.get("location", {})
                if loc and isinstance(loc, dict):
                    lat = loc.get("latitude")
                    lng = loc.get("longitude")
                    koordinat_wkt = enricher.format_wkt_point(lat, lng)

            # Fallback Geocoding for coordinates if still missing
            if not koordinat_wkt and (alamat_final or location_hint):
                geo_query = f"{nama_pt}, {alamat_final or location_hint}"
                geo_res = enricher.geocode_address(geo_query)
                if geo_res:
                    koordinat_wkt = enricher.format_wkt_point(geo_res.get("lat"), geo_res.get("lng"))

            # 2. Wikipedia API Search (High-res Logo & Pure Narrative Description)
            wiki_data = wiki_enricher.search_campus(nama_pt, location_hint=location_hint)
            deskripsi = ""
            logo_url = ""
            logo_source = ""
            desc_source = ""

            if wiki_data:
                deskripsi = wiki_data.get("description", "").strip()
                logo_url = wiki_data.get("logo_url", "").strip()
                if logo_url:
                    logo_source = "Wiki"
                if deskripsi:
                    desc_source = "Wiki"

            # 3. Hybrid Fallback for Logo: Crawl Official Campus Website if Wikipedia has no logo
            if not logo_url and website_final:
                logo_url = logo_extractor.extract_logo(website_final)
                if logo_url:
                    logo_source = "Web"

            # 4. Fallback for Deskripsi (Priority 2): Factual Generator if Wikipedia description is empty
            if not deskripsi:
                deskripsi = generate_factual_description(row)
                desc_source = "Factual"

            # Assemble strictly the 10 fields matching Table 3.1 KAMPUS
            record_10 = {
                "kode_kampus": kode_pt,
                "nama_kampus": nama_pt,
                "singkatan_kampus": singkatan,
                "akreditasi": akreditasi,
                "alamat": alamat_final,
                "website_url": website_final,
                "logo_url": logo_url,
                "banner_url": banner_url,
                "deskripsi": deskripsi,
                "koordinat": koordinat_wkt
            }

            storage.add_and_flush(record_10)
            processed_count += 1
            success_count += 1

            status_tags = []
            if koordinat_wkt:
                status_tags.append("Coords ✓")
            if website_final:
                status_tags.append("Web (GMaps) ✓")
            if logo_url and logo_source == "Wiki":
                status_tags.append("Logo (Wiki) ✓")
            elif logo_url and logo_source == "Web":
                status_tags.append("Logo (Web) ✓")
            if deskripsi and desc_source == "Wiki":
                status_tags.append("Desc (Wiki) ✓")
            elif deskripsi and desc_source == "Factual":
                status_tags.append("Desc (Factual) ✓")
            
            tag_str = ", ".join(status_tags) if status_tags else "Basic ✓"
            logger.info(f"    Status: ENRICHED ({tag_str})")

            # Small throttle to be courteous with APIs
            time.sleep(0.1)

    except KeyboardInterrupt:
        logger.info("\n[INTERRUPT] Received Ctrl+C. Performing graceful shutdown and saving progress...")
    except Exception as e:
        logger.error(f"Enrichment Pipeline Error: {e}")

    out_csv = storage.finalize()
    logger.info("\n" + "=" * 60)
    logger.info("CAMPUS ENRICHMENT SUMMARY (10-COLUMN STRICT SCHEMA)")
    logger.info("=" * 60)
    logger.info(f"Processed   : {processed_count}")
    logger.info(f"Output CSV  : {out_csv}")
    logger.info(f"Output JSON : {storage.json_path}")
    logger.info(f"Checkpoint  : {storage.checkpoint_path}")
    logger.info(f"Duplicates  : {indicator_json}")
    logger.info("=" * 60)


def run_duplicate_audit(args, logger):
    from src.validators.duplicate_auditor import DuplicateAuditor
    source_csv = OUTPUT_DIR / "pddikti_campuses.csv"
    if not source_csv.exists():
        source_csv = OUTPUT_DIR / "kampus_extracted.csv"
    
    if not source_csv.exists():
        logger.error(f"Error: Source data file {source_csv} does not exist!")
        return

    auditor = DuplicateAuditor(logger=logger)
    indicator_json = OUTPUT_DIR / "duplicate_campus_indicator.json"
    auditor.audit_csv(source_csv, output_json_path=indicator_json)


def run_pddikti_export_csv(args, logger):
    from src.storage.pddikti_csv_storage import PddiktiCsvStorage
    json_path = OUTPUT_DIR / "pddikti_campuses.json"
    csv_storage = PddiktiCsvStorage(OUTPUT_DIR)
    
    logger.info("=" * 60)
    logger.info("PDDIKTI STANDALONE CSV EXPORTER")
    logger.info("=" * 60)
    logger.info(f"Source JSON : {json_path}")
    
    if not json_path.exists():
        logger.error(f"Error: {json_path} does not exist!")
        return
        
    csv_file = csv_storage.export_from_json(json_path)
    logger.info(f"CSV Output  : {csv_file}")
    logger.info("=" * 60)


def main():
    load_env_file()
    parser = argparse.ArgumentParser(description="Indonesian Campus Scraper Pipeline")
    input_group = parser.add_mutually_exclusive_group(required=True)
    input_group.add_argument('--master', action='store_true', help="Use master CSV as target source")
    input_group.add_argument('--discover', action='store_true', help="Discover targets from Quipper directory")
    input_group.add_argument('--pddikti-poc', action='store_true', help="Run PDDIKTI Search-based Scraper PoC")
    input_group.add_argument('--pddikti-dir', action='store_true', help="Run PDDIKTI Directory-based Card Scraper")
    input_group.add_argument('--pddikti-api', action='store_true', help="Run PDDIKTI Pure In-Browser API Scraper (Option B)")
    input_group.add_argument('--pddikti-export-csv', action='store_true', help="Export existing PDDIKTI JSON data to 23-column CSV")
    input_group.add_argument('--enrich-kampus', action='store_true', help="Enrich campus data using Google Places & Geocoding API (10-column strict schema)")
    input_group.add_argument('--audit-duplicates', action='store_true', help="Run duplicate campus name audit indicator (without modifying data)")
    
    parser.add_argument('--pddikti-url', type=str, default="https://pddikti.kemdiktisaintek.go.id/search/pt/Universitas", help="Custom PDDIKTI search discovery URL")
    parser.add_argument('--target-count', type=int, default=None, help="Target number of campuses to process (default: ALL available)")
    parser.add_argument('--resume', action='store_true', help="Resume processing from last saved checkpoint")
    parser.add_argument('--headless', action='store_true', help="Run Playwright in headless mode (default is headful for manual CAPTCHA completion)")
    parser.add_argument('--gmaps-key', type=str, default=None, help="Google Maps Platform API Key (or set GOOGLE_MAPS_API_KEY in .env)")
    
    output_group = parser.add_mutually_exclusive_group()
    output_group.add_argument('--json', action='store_true', help="Output only JSON")
    output_group.add_argument('--csv', action='store_true', help="Output only CSV")
    output_group.add_argument('--all', action='store_true', help="Output both JSON and CSV (default)")
    
    args = parser.parse_args()
    if not args.json and not args.csv and not args.all:
        args.all = True

    log_dir = DATA_DIR / 'logs'
    logger = setup_logger(log_dir)

    if args.audit_duplicates:
        run_duplicate_audit(args, logger)
        return

    if args.enrich_kampus:
        run_enrich_kampus_pipeline(args, logger)
        return

    if args.pddikti_export_csv:
        run_pddikti_export_csv(args, logger)
        return

    if args.pddikti_api:
        run_pddikti_api_pipeline(args, logger)
        return

    if args.pddikti_dir:
        run_pddikti_directory_poc(args, logger)
        return

    if args.pddikti_poc:
        run_pddikti_poc(args, logger)
        return

    mode_str = "MASTER" if args.master else "DISCOVER"
    output_str = "ALL" if args.all else ("JSON" if args.json else "CSV")
    
    logger.info("=" * 60)
    logger.info("QUIPPER CAMPUS SCRAPER")
    logger.info("=" * 60)
    logger.info(f"Started : {datetime.datetime.now().astimezone().strftime('%Y-%m-%d %H:%M:%S %z')}")
    logger.info(f"Mode    : {mode_str}")
    logger.info(f"Output  : {output_str}")
    logger.info("=" * 60)
    logger.info("")

    # Initialize components
    mapper = QuipperMapper()
    validator = DataValidator()
    json_storage = JsonStorage(OUTPUT_DIR)
    csv_storage = CsvStorage(OUTPUT_DIR)
    image_enricher = ExternalImageEnricher()
    
    scraped_at = datetime.datetime.now().astimezone().isoformat()
    
    # 1. Target Collection
    targets = []
    if args.master:
        logger.info(f"Input Source : {INPUT_CSV.name}")
        campus_names = load_campus_names(str(INPUT_CSV))
        logger.info(f"Total Target : {len(campus_names)}\n")
        for name in campus_names:
            slug = generate_slug(name)
            targets.append({
                'nama_kampus': name,
                'slug': slug,
                'url': f"{BASE_URL}/{slug}"
            })
    elif args.discover:
        logger.info(f"Input Source : Quipper Campus Directory")
        from src.scrapers.discovery import QuipperDiscovery
        discovery = QuipperDiscovery()
        targets = discovery.discover_campuses()
        logger.info(f"Total Found  : {len(targets)}\n")
        
    if not targets:
        logger.error("No targets found to process. Exiting.")
        return
    
    if args.csv or args.all:
        logger.debug("Initializing consolidated CSV files...")
        csv_storage.initialize()
        
    success_count = 0
    failure_count = 0
    warning_count = 0
    skipped_count = 0
    
    failed_campuses = []
    warning_counter = Counter()
    
    pipeline_start_time = time.time()
    
    for i, target in enumerate(targets, 1):
        campus_name = target['nama_kampus']
        slug = target['slug']
        target_url = target['url']
        
        # Initial scraping state message (minimal)
        logger.info(f"\n[{(i):03d}/{len(targets):03d}] {campus_name}")
        logger.info(f"        URL     : {target_url}")
        logger.info(f"        Status  : SCRAPING")
        
        stages = {'FETCH': '', 'EXTRACT': '', 'MAP': '', 'VALIDATE': '', 'ENRICH': '', 'STORE': ''}
        campus_start_time = time.time()
        campus_status = "SUCCESS"
        error_msg = None
        
        # 2. HTTP GET
        logger.debug(f"Fetching HTML for {target_url}")
        html_content, err = fetch_html(target_url)
        if err:
            stages['FETCH'] = '✗'
            campus_status = "FAILED"
            error_msg = err
        else:
            stages['FETCH'] = '✓'
            
            # 3. SiteRoot extraction
            logger.debug(f"Extracting SiteRoot for {slug}")
            siteroot_json, err = extract_siteroot_json(html_content)
            if err:
                stages['EXTRACT'] = '✗'
                campus_status = "FAILED"
                error_msg = err
            else:
                # 4. Extract raw data
                logger.debug(f"Extracting Quipper data for {slug}")
                raw_data, err = extract_quipper_data(siteroot_json)
                if err:
                    stages['EXTRACT'] = '✗'
                    campus_status = "FAILED"
                    error_msg = err
                else:
                    stages['EXTRACT'] = '✓'
                    
                    # 5. Mapping
                    logger.debug(f"Mapping data for {slug}")
                    mapped_data = mapper.map_school(raw_data, slug, scraped_at)
                    stages['MAP'] = '✓'
                    
                    # 6. Validation
                    logger.debug(f"Validating data for {slug}")
                    val_status, issues = validator.validate(mapped_data, mapper.warnings)
                    
                    for issue in issues:
                        parsed_warn = parse_warning(issue)
                        warning_counter[parsed_warn] += 1
                        logger.debug(f"Validation Issue: {issue}")
                        
                    if val_status == "ERROR":
                        stages['VALIDATE'] = '✗'
                        campus_status = "FAILED"
                        error_msg = "Validation failed"
                    else:
                        if val_status == "WARNING":
                            stages['VALIDATE'] = '⚠'
                            campus_status = "WARNING"
                        else:
                            stages['VALIDATE'] = '✓'
                            
                        # 7. Image Enrichment
                        logger.debug(f"Enriching image data for {slug}")
                        enrich_status = image_enricher.enrich(mapped_data)
                        if enrich_status == 'SUCCESS':
                            stages['ENRICH'] = '✓'
                        elif enrich_status == 'WARNING':
                            stages['ENRICH'] = '⚠'
                        elif enrich_status == 'ERROR':
                            stages['ENRICH'] = '✗'
                            
                        # 8. Storage
                        logger.debug(f"Saving data for {slug}")
                        if args.json or args.all:
                            json_storage.add(mapped_data)
                        if args.csv or args.all:
                            csv_storage.save(mapped_data)
                        stages['STORE'] = '✓'
                        
        duration = time.time() - campus_start_time
        
        if campus_status == "FAILED":
            failure_count += 1
            failed_campuses.append({'name': campus_name, 'url': target_url, 'error': error_msg})
        elif campus_status == "WARNING":
            warning_count += 1
            success_count += 1 # WARNING still counts as successfully saved
        elif campus_status == "SKIPPED":
            skipped_count += 1
        else:
            success_count += 1
            
        # Print progress tree
        print_progress(logger, i, len(targets), campus_name, campus_status, duration, stages, error=error_msg)
        
    pipeline_duration = time.time() - pipeline_start_time
    m, s = divmod(pipeline_duration, 60)
    h, m = divmod(m, 60)
    duration_str = f"{int(h):02d}:{int(m):02d}:{int(s):02d}"
    
    if args.json or args.all:
        json_storage.finalize()
        
    logger.info("\n" + "=" * 60)
    logger.info("SCRAPING SUMMARY")
    logger.info("=" * 60)
    logger.info(f"Mode                : {mode_str}")
    logger.info(f"Total targets       : {len(targets)}\n")
    logger.info(f"Successful           : {success_count - warning_count}")
    logger.info(f"Warnings             : {warning_count}")
    logger.info(f"Failed               : {failure_count}")
    if skipped_count > 0:
        logger.info(f"Skipped              : {skipped_count}")
    
    logger.info("-" * 60)
    logger.info("OUTPUT")
    logger.info("-" * 60)
    
    if args.json or args.all:
        logger.info("JSON:")
        logger.info("  ✓ data/output/campuses.json\n")
        
    if args.csv or args.all:
        logger.info("CSV:")
        logger.info("  ✓ data/output/kampus.csv")
        logger.info("  ✓ data/output/fakultas.csv")
        logger.info("  ✓ data/output/prodi.csv\n")
        
    logger.info("-" * 60)
    logger.info(f"Duration            : {duration_str}")
    logger.info("=" * 60)
    
    if failure_count > 0:
        logger.info("\nFAILED CAMPUSES")
        logger.info("-" * 60)
        for idx, fc in enumerate(failed_campuses, 1):
            logger.info(f"{idx}. {fc['name']}")
            logger.info(f"   URL   : {fc['url']}")
            logger.info(f"   Error : {fc['error']}\n")
        logger.info("-" * 60)
    else:
        logger.info("\nFailed campuses: 0")
        
    if warning_counter:
        logger.info("\nWARNING SUMMARY")
        logger.info("-" * 60)
        for warn_code, count in warning_counter.most_common():
            logger.info(f"{warn_code:<30} : {count}")
        logger.info("-" * 60)

if __name__ == "__main__":
    main()
