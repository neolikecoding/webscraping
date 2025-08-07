import pandas as pd
import time
import requests

def geocode_address(address, api_key=None):
    # Use Nominatim (OpenStreetMap) for free geocoding
    url = "https://nominatim.openstreetmap.org/search"
    params = {
        "q": address,
        "format": "json",
        "addressdetails": 1,
        "limit": 1
    }
    headers = {"User-Agent": "GeoCoderScript/1.0"}
    try:
        response = requests.get(url, params=params, headers=headers, timeout=10)
        response.raise_for_status()
        data = response.json()
        if data:
            lat = data[0].get("lat", None)
            lon = data[0].get("lon", None)
            return lat, lon
    except Exception as e:
        print(f"Error geocoding '{address}': {e}")
    return None, None

# Load combined CSV
input_file = "all_towns_combined.csv"
df = pd.read_csv(input_file)

# Assume address column is named 'Property address' (update if needed)
if 'Address' not in df.columns:
    raise Exception("Column 'Property address' not found in CSV.")

lats = []
lons = []
for address in df['Address']:
    lat, lon = geocode_address(address)
    lats.append(lat)
    lons.append(lon)
    time.sleep(1)  # Be polite to the API

df['Latitude'] = lats
df['Longitude'] = lons

df.to_csv("all_towns_combined_geocoded.csv", index=False)
print("Geocoded file saved as all_towns_combined_geocoded.csv")
