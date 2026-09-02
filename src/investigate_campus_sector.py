import csv
from collections import Counter
from src.config import DATA_DIR, BASE_URL
from src.loaders.csv_loader import load_campus_names
from src.utils.slug_generator import generate_slug
from src.scrapers.http_scraper import fetch_html
from src.extractors.quipper_extractor import extract_siteroot_json, extract_quipper_data

def main():
    input_csv = DATA_DIR / 'input' / 'master_data_top_100_indonesian_campus.csv'
    output_csv = DATA_DIR / 'output' / 'campus_sector.csv'
    
    print(f"Loading campus names from {input_csv}...")
    try:
        campus_names = load_campus_names(str(input_csv))
    except Exception as e:
        print(f"Failed to load CSV: {e}")
        return
        
    results = []
    sector_counts = Counter()
    
    for i, nama_kampus in enumerate(campus_names, 1):
        slug = generate_slug(nama_kampus)
        target_url = f"{BASE_URL}/{slug}"
        print(f"[{i}/{len(campus_names)}] Investigating: {nama_kampus}")
        
        html, err = fetch_html(target_url)
        if err:
            results.append({'nama_kampus': nama_kampus, 'slug': slug, 'campus_sector': 'null', 'status': f'ERROR: {err}'})
            continue
            
        siteroot, err = extract_siteroot_json(html)
        if err:
            results.append({'nama_kampus': nama_kampus, 'slug': slug, 'campus_sector': 'null', 'status': f'ERROR: {err}'})
            continue
            
        raw_data, err = extract_quipper_data(siteroot)
        if err:
            results.append({'nama_kampus': nama_kampus, 'slug': slug, 'campus_sector': 'null', 'status': f'ERROR: {err}'})
            continue
            
        campus_sector = raw_data.get('campus_sector')
        if campus_sector is None:
            sector_val = 'null'
        else:
            sector_val = str(campus_sector)
            
        sector_counts[sector_val] += 1
        results.append({'nama_kampus': nama_kampus, 'slug': slug, 'campus_sector': sector_val, 'status': 'SUCCESS'})
        
    # Write to CSV
    try:
        with open(output_csv, mode='w', newline='', encoding='utf-8-sig') as f:
            writer = csv.DictWriter(f, fieldnames=['nama_kampus', 'slug', 'campus_sector', 'status'])
            writer.writeheader()
            writer.writerows(results)
    except Exception as e:
        print(f"\nFailed to write CSV: {e}")
        return
        
    # Print summary
    print("\n----------------------------------------")
    print("CAMPUS SECTOR SUMMARY")
    print("----------------------------------------")
    for sector, count in sorted(sector_counts.items(), key=lambda x: x[1], reverse=True):
        print(f"{sector}: {count}")
    print("----------------------------------------")
    print(f"TOTAL UNIQUE VALUES: {len(sector_counts)}")
    print("----------------------------------------")
    print(f"Saved investigation results to {output_csv}")

if __name__ == '__main__':
    main()
