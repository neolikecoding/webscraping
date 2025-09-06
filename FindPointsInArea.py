import requests
from fastkml import kml
import requests
from shapely.geometry import Point, Polygon
import xml.etree.ElementTree as ET
import time
import csv
import json
import os


def get_boundary_polygon(area_kml_path):
    tree = ET.parse(area_kml_path)
    root = tree.getroot()
    ns = {'kml': 'http://www.opengis.net/kml/2.2'}
    coords_elem = root.find('.//kml:LineString/kml:coordinates', ns)
    if coords_elem is None or not coords_elem.text:
        raise Exception('No LineString coordinates found in boundary KML.')
    coords_text = coords_elem.text.strip()
    coords = []
    for token in coords_text.split():
        parts = token.split(',')
        if len(parts) >= 2:
            lon, lat = float(parts[0]), float(parts[1])
            coords.append((lon, lat))
    if not coords:
        raise Exception('No coordinates parsed from boundary KML.')
    if coords[0] != coords[-1]:
        coords.append(coords[0])
    return Polygon(coords)


def parse_placemarks_from_kml_string(kml_string):
    ns = {'kml': 'http://www.opengis.net/kml/2.2'}
    root = ET.fromstring(kml_string)
    placemarks = []
    for pm in root.findall('.//kml:Placemark', ns):
        name_el = pm.find('kml:name', ns)
        name = name_el.text.strip() if name_el is not None and name_el.text else ''
        desc_el = pm.find('kml:description', ns)
        desc = desc_el.text if desc_el is not None else ''
        addr_el = pm.find('kml:address', ns)
        address_tag = addr_el.text.strip() if addr_el is not None and addr_el.text else ''
        coord_el = pm.find('.//kml:Point/kml:coordinates', ns)
        lon = lat = None
        if coord_el is not None and coord_el.text:
            parts = coord_el.text.strip().split(',')
            if len(parts) >= 2:
                lon, lat = float(parts[0]), float(parts[1])
        extended = {}
        for data_el in pm.findall('.//kml:ExtendedData//kml:Data', ns):
            key = data_el.get('name')
            val_el = data_el.find('kml:value', ns)
            val = val_el.text.strip() if val_el is not None and val_el.text else ''
            if key:
                extended[key] = val
        placemarks.append({
            'name': name,
            'description': desc,
            'address_tag': address_tag,
            'lon': lon,
            'lat': lat,
            'extended': extended,
            'element': pm,
        })
    return placemarks


def get_address_placemarks(points_kml_path):
    tree = ET.parse(points_kml_path)
    root = tree.getroot()
    ns = {'kml': 'http://www.opengis.net/kml/2.2'}
    hrefs = [e.text.strip() for e in root.findall('.//kml:NetworkLink//kml:href', ns) if e.text and e.text.strip()]
    placemarks = []
    if hrefs:
        for href in hrefs:
            try:
                resp = requests.get(href, timeout=15)
                resp.raise_for_status()
                placemarks.extend(parse_placemarks_from_kml_string(resp.text))
            except Exception as e:
                print(f'Failed to fetch remote KML {href}: {e}')
    else:
        with open(points_kml_path, 'rt', encoding='utf-8') as f:
            doc = f.read()
        placemarks = parse_placemarks_from_kml_string(doc)
    return placemarks


def load_clustering_csv(path):
    """Load clustering CSV that contains precomputed Latitude/Longitude.
    Returns two dicts: by_placemark_name and by_normalized_address.
    """
    by_name = {}
    by_addr = {}
    if not os.path.exists(path):
        return by_name, by_addr
    with open(path, 'rt', encoding='utf-8', newline='') as f:
        reader = csv.DictReader(f)
        for row in reader:
            try:
                lat = float(row.get('Latitude') or row.get('Lat') or 0)
                lon = float(row.get('Longitude') or row.get('Lon') or 0)
            except Exception:
                continue
            name = row.get('placemark_name') or row.get('placemark') or ''
            if name:
                by_name[str(name).strip()] = (lon, lat)
            addr = row.get('Address') or row.get('Address Line 1') or ''
            if addr:
                norm = normalize_address(addr)
                by_addr[norm] = (lon, lat)
    return by_name, by_addr


def normalize_address(addr):
    if not addr:
        return ''
    s = addr.upper().strip()
    # remove extra whitespace and commas
    s = ' '.join(s.replace(',', ' ').split())
    return s


def geocode_address(address, cache, email=None):
    if not address:
        return None, None
    if address in cache:
        return cache[address]
    url = 'https://nominatim.openstreetmap.org/search'
    params = {'q': address, 'format': 'json', 'limit': 1}
    ua = 'FindPointsInArea/1.0'
    if email:
        ua = ua + f' ({email})'
    headers = {'User-Agent': ua}
    try:
        resp = requests.get(url, params=params, headers=headers, timeout=10)
        resp.raise_for_status()
        data = resp.json()
        if data:
            lat = float(data[0]['lat'])
            lon = float(data[0]['lon'])
            cache[address] = (lon, lat)
            return lon, lat
    except Exception as e:
        print(f"Geocode error for '{address}': {e}")
    cache[address] = (None, None)
    return None, None


def load_geocode_cache(path):
    if os.path.exists(path):
        try:
            with open(path, 'rt', encoding='utf-8') as f:
                return json.load(f)
        except Exception:
            return {}
    return {}


def save_geocode_cache(path, cache):
    try:
        with open(path, 'wt', encoding='utf-8') as f:
            json.dump(cache, f, ensure_ascii=False, indent=2)
    except Exception as e:
        print(f'Failed to save geocode cache: {e}')


def write_kml_with_points(placemarks, output_path):
    ns = 'http://www.opengis.net/kml/2.2'
    kml_el = ET.Element(f'{{{ns}}}kml')
    doc_el = ET.SubElement(kml_el, f'{{{ns}}}Document')
    for p in placemarks:
        pm_el = ET.SubElement(doc_el, f'{{{ns}}}Placemark')
        name_el = ET.SubElement(pm_el, f'{{{ns}}}name')
        name_el.text = p.get('name', '')
        desc_el = ET.SubElement(pm_el, f'{{{ns}}}description')
        desc_el.text = p.get('description', '')
        ext = p.get('extended', {})
        if ext:
            ext_el = ET.SubElement(pm_el, f'{{{ns}}}ExtendedData')
            for k, v in ext.items():
                data_el = ET.SubElement(ext_el, f'{{{ns}}}Data')
                data_el.set('name', k)
                val_el = ET.SubElement(data_el, f'{{{ns}}}value')
                val_el.text = v
        lon = p.get('lon')
        lat = p.get('lat')
        if lon is not None and lat is not None:
            point_el = ET.SubElement(pm_el, f'{{{ns}}}Point')
            coords_el = ET.SubElement(point_el, f'{{{ns}}}coordinates')
            coords_el.text = f"{lon},{lat},0"
    tree = ET.ElementTree(kml_el)
    tree.write(output_path, encoding='utf-8', xml_declaration=True)


if __name__ == '__main__':
    area_kml = 'Data/DesPlainesKendraArea.kml'
    points_kml = 'Data/DesplainesPocketPoints.kml'
    cache_path = 'geocode_cache.json'
    max_geocode_sample = None  # number of missing coords to geocode; None => all
    email = None  # set to your contact email for Nominatim policy compliance

    boundary_polygon = get_boundary_polygon(area_kml)
    all_placemarks = get_address_placemarks(points_kml)
    print(f'Total placemarks found: {len(all_placemarks)}')

    # Load cache
    cache = load_geocode_cache(cache_path)

    # Load clustering CSV maps
    clustering_csv = 'Data/Desplaines Clustering.csv'
    by_name_map, by_addr_map = load_clustering_csv(clustering_csv)

    # Find placemarks missing coordinates
    missing = [p for p in all_placemarks if p.get('lon') is None or p.get('lat') is None]
    print(f'Placemarks missing coordinates: {len(missing)}')

    # Geocode a small sample to verify (prefer clustering CSV where available)
    sample = missing[:max_geocode_sample] if max_geocode_sample else missing
    for p in sample:
        # build an address string: prefer <address>, else use ExtendedData fields
        addr = p.get('address_tag') or ''
        if not addr:
            ext = p.get('extended', {})
            parts = []
            for key in ('Address Line 1', 'City', 'Town', '1st PIN'):
                v = ext.get(key)
                if v:
                    parts.append(v.strip())
            addr = ', '.join(parts)
        if not addr:
            continue
        # Try clustering CSV by placemark_name first
        used = False
        pm_name = p.get('name')
        if pm_name and str(pm_name).strip() in by_name_map:
            lon, lat = by_name_map[str(pm_name).strip()]
            p['lon'] = lon
            p['lat'] = lat
            print(f"Used clustering CSV (name): {pm_name} -> {lon},{lat}")
            used = True
        else:
            # try normalized address match
            norm = normalize_address(addr)
            if norm in by_addr_map:
                lon, lat = by_addr_map[norm]
                p['lon'] = lon
                p['lat'] = lat
                print(f"Used clustering CSV (addr): {addr} -> {lon},{lat}")
                used = True
        if used:
            continue
        lonlat = geocode_address(addr, cache, email=email)
        if lonlat and lonlat != (None, None):
            lon, lat = lonlat
            p['lon'] = lon
            p['lat'] = lat
            print(f"Geocoded: {addr} -> {lon},{lat}")
        else:
            print(f"Geocode failed for: {addr}")
        time.sleep(1.1)

    save_geocode_cache(cache_path, cache)

    # Now filter by bbox and polygon
    minx, miny, maxx, maxy = boundary_polygon.bounds
    in_bbox = []
    for p in all_placemarks:
        lon = p.get('lon')
        lat = p.get('lat')
        if lon is None or lat is None:
            continue
        if minx <= lon <= maxx and miny <= lat <= maxy:
            in_bbox.append(p)
    print(f'Placemarks within bounding box: {len(in_bbox)}')

    inside = [p for p in in_bbox if boundary_polygon.covers(Point(p.get('lon'), p.get('lat')))]
    print(f'Found {len(inside)} addresses inside the boundary')

    write_kml_with_points(inside, 'Data/AddressesWithinBoundary.kml')
    print('Wrote Data/AddressesWithinBoundary.kml')