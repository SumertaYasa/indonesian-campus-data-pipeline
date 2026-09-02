import logging
import json
import time
import urllib.request
import urllib.parse
import urllib.error
from typing import Dict, Optional, Any

class GoogleMapsEnricher:
    """
    Google Maps Platform client for campus entity enrichment.
    Utilizes Places API (New) and Geocoding API to retrieve:
    - Koordinat (PostGIS WKT POINT(lng lat))
    - Banner image URL (Google Places photo media)
    - Formatted official address
    - Verified official website URI
    - Editorial descriptive summary
    """

    PLACES_SEARCH_URL = "https://places.googleapis.com/v1/places:searchText"
    GEOCODING_URL = "https://maps.googleapis.com/maps/api/geocode/json"

    def __init__(self, api_key: str, logger: Optional[logging.Logger] = None):
        self.api_key = api_key.strip().strip('"').strip("'")
        self.logger = logger or logging.getLogger("GoogleMapsEnricher")

    def search_place(self, campus_name: str, location_hint: Optional[str] = None) -> Optional[Dict[str, Any]]:
        """
        Queries Google Places API (New) using Text Search with Field Masking.
        Returns the top matching place dictionary or None.
        """
        if not self.api_key:
            self.logger.warning("Google Maps API Key is missing.")
            return None

        query = campus_name.strip()
        if location_hint and location_hint.strip():
            query = f"{query} {location_hint.strip()}"

        headers = {
            "Content-Type": "application/json",
            "X-Goog-Api-Key": self.api_key,
            "X-Goog-FieldMask": (
                "places.id,"
                "places.displayName,"
                "places.formattedAddress,"
                "places.location,"
                "places.websiteUri,"
                "places.editorialSummary"
            )
        }

        payload = {
            "textQuery": query,
            "languageCode": "id"
        }

        try:
            req = urllib.request.Request(
                self.PLACES_SEARCH_URL,
                data=json.dumps(payload).encode("utf-8"),
                headers=headers,
                method="POST"
            )
            with urllib.request.urlopen(req, timeout=15) as resp:
                result = json.loads(resp.read().decode("utf-8"))
                places = result.get("places", [])
                if places and isinstance(places, list):
                    return places[0]
                return None
        except urllib.error.HTTPError as e:
            error_msg = e.read().decode("utf-8", errors="ignore")
            self.logger.warning(f"Places API HTTPError for '{query}': {e.code} - {error_msg}")
            return None
        except Exception as e:
            self.logger.warning(f"Places API request failed for '{query}': {e}")
            return None

    def build_photo_url(self, photo_name: Optional[str], max_width: int = 1200, max_height: int = 800) -> str:
        """
        Builds a direct Place Photo Media URL using Google Places API (New).
        """
        if not photo_name or not isinstance(photo_name, str):
            return ""
        
        # photo_name format is usually 'places/{place_id}/photos/{photo_reference}'
        clean_name = photo_name.strip()
        return f"https://places.googleapis.com/v1/{clean_name}/media?maxHeightPx={max_height}&maxWidthPx={max_width}&key={self.api_key}"

    def build_banner_url(self, photo_name: Optional[str], kode_kampus: Optional[str] = None) -> str:
        """
        Returns permanent CDN banner URL if Cloudinary is configured, or direct Google Place Photo URL.
        """
        direct_url = self.build_photo_url(photo_name)
        if not direct_url:
            return ""

        # Check if Cloudinary is configured
        import os
        cloud_name = os.getenv("CLOUDINARY_CLOUD_NAME")
        c_key = os.getenv("CLOUDINARY_API_KEY")
        c_secret = os.getenv("CLOUDINARY_API_SECRET")

        if cloud_name and c_key and c_secret:
            try:
                import cloudinary
                import cloudinary.uploader
                cloudinary.config(
                    cloud_name=cloud_name.strip().strip('"').strip("'"),
                    api_key=c_key.strip().strip('"').strip("'"),
                    api_secret=c_secret.strip().strip('"').strip("'"),
                    secure=True
                )
                pub_id = f"kampus_banner_{str(kode_kampus).strip()}" if kode_kampus else None
                res = cloudinary.uploader.upload(
                    direct_url,
                    folder="kampus/banner",
                    public_id=pub_id,
                    overwrite=True,
                    resource_type="image"
                )
                if res and res.get("secure_url"):
                    return res["secure_url"]
            except Exception as ce:
                self.logger.debug(f"Cloudinary upload skipped/failed: {ce}")

        return direct_url

    def geocode_address(self, address: str) -> Optional[Dict[str, float]]:
        """
        Fallback using Geocoding API to resolve coordinates from raw address string.
        """
        if not self.api_key or not address or not address.strip():
            return None

        params = urllib.parse.urlencode({
            "address": address.strip(),
            "key": self.api_key
        })
        url = f"{self.GEOCODING_URL}?{params}"

        try:
            req = urllib.request.Request(url, headers={"User-Agent": "Mozilla/5.0"})
            with urllib.request.urlopen(req, timeout=12) as resp:
                data = json.loads(resp.read().decode("utf-8"))
                if data.get("status") == "OK" and data.get("results"):
                    location = data["results"][0].get("geometry", {}).get("location", {})
                    lat = location.get("lat")
                    lng = location.get("lng")
                    if lat is not None and lng is not None:
                        return {"lat": float(lat), "lng": float(lng)}
                return None
        except Exception as e:
            self.logger.warning(f"Geocoding API failed for '{address}': {e}")
            return None

    @staticmethod
    def format_wkt_point(lat: Optional[float], lng: Optional[float]) -> str:
        """
        Converts latitude and longitude into PostGIS WKT Point string: 'POINT(lng lat)'.
        Returns empty string if invalid or 0.0.
        """
        if lat is None or lng is None:
            return ""
        try:
            f_lat = float(lat)
            f_lng = float(lng)
            # Filter out 0.0 or out of bounds for Indonesia / world
            if f_lat == 0.0 and f_lng == 0.0:
                return ""
            if not (-90.0 <= f_lat <= 90.0 and -180.0 <= f_lng <= 180.0):
                return ""
            return f"POINT({f_lng:.6f} {f_lat:.6f})"
        except (ValueError, TypeError):
            return ""
