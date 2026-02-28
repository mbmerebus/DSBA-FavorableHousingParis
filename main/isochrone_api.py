import requests
import json
import os
from datetime import datetime

def call_API(TIME_STUDIED, NAVITIA_TOKEN, start_lon, start_lat):
    # --- Config ---
    MAX_DURATION = TIME_STUDIED*60        # time in minutes converted to seconds
    CACHE_FILE = f"isochrone_paris_{TIME_STUDIED}min.json"

    # --- Call the API (only if cache doesn't exist) ---
    if os.path.exists(CACHE_FILE):
        print(f"✅ Loading cached response from {CACHE_FILE}")
        with open(CACHE_FILE, "r") as f:
            data = json.load(f)
    else:
        print("🌐 Making API call...")

        url = "https://prim.iledefrance-mobilites.fr/marketplace/v2/navitia/isochrones/isochrones"

        params = {
            "from": f"{start_lon};{start_lat}",   # lon;lat format for Navitia
            "max_duration": MAX_DURATION,
        }

        headers = {
            "apiKey": NAVITIA_TOKEN
        }

        response = requests.get(url, params=params, headers=headers)

        print(f"Status code: {response.status_code}")

        if response.status_code != 200:
            print("❌ Error response:")
            print(response.text)
            raise Exception(f"API call failed with status {response.status_code}")

        data = response.json()

        # Save full raw response to disk
        with open(CACHE_FILE, "w") as f:
            json.dump(data, f, ensure_ascii=False, indent=2)

        print(f"✅ Response saved to {CACHE_FILE}")

    # --- Inspect the response ---
    print(f"\nTop-level keys: {list(data.keys())}")

    if "isochrones" in data:
        isos = data["isochrones"]
        print(f"Number of isochrone zones returned: {len(isos)}")
        if isos:
            print(f"Keys in first isochrone object: {list(isos[0].keys())}")
            # Show a sample of the first zone's metadata (not the full geometry)
            first = {k: v for k, v in isos[0].items() if k != "geojson"}
            print(f"\nFirst isochrone (without geometry):\n{json.dumps(first, indent=2)}")
    else:
        print("Unexpected response structure. Full data:")
        print(json.dumps(data, indent=2)[:2000])  # Print first 2000 chars to avoid flooding