#!/usr/bin/env python3
"""V20: Generate airports.json from OpenFlights airports.dat

Source: https://openflights.org/data/airports.dat
Format: CSV with 14 columns:
  id,name,city,country,IATA,ICAO,lat,lon,altitude,timezone,DST,tz_database,type,source

Output: lib/global-airports/airports.json
  {
    "total": <int>,
    "countries": <int>,
    "by_country": { country: count, ... top 30 sorted desc },
    "airports": [ { iata, name, city, country, lat, lon }, ... ]
  }
"""
import csv
import json
import os
import sys
from collections import defaultdict

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(HERE)  # aog-web/frontend
DAT = os.path.join(ROOT, "lib", "global-airports", "airports.dat")
JSON_OUT = os.path.join(ROOT, "lib", "global-airports", "airports.json")


def main():
    if not os.path.isfile(DAT):
        print(f"ERROR: {DAT} not found. Run: curl -L -o {DAT} https://openflights.org/data/airports.dat")
        sys.exit(1)

    airports = []
    skipped_no_iata = 0
    skipped_bad_coord = 0
    with open(DAT, "r", encoding="utf-8") as f:
        reader = csv.reader(f)
        for row in reader:
            if len(row) < 8:
                continue
            iata = row[4].strip() if len(row) > 4 else ""
            if not iata or iata == "\\N" or iata == r"\N":
                skipped_no_iata += 1
                continue
            try:
                lat = float(row[6])
                lon = float(row[7])
            except (ValueError, IndexError):
                skipped_bad_coord += 1
                continue
            airports.append({
                "iata": iata,
                "name": row[1].strip() if len(row) > 1 else "",
                "city": row[2].strip() if len(row) > 2 else "",
                "country": row[3].strip() if len(row) > 3 else "",
                "lat": round(lat, 6),
                "lon": round(lon, 6),
            })

    by_country = defaultdict(int)
    for a in airports:
        by_country[a["country"]] += 1

    top_countries = sorted(by_country.items(), key=lambda x: -x[1])[:30]

    payload = {
        "total": len(airports),
        "countries": len(by_country),
        "by_country": dict(top_countries),
        "airports": airports,
    }

    with open(JSON_OUT, "w", encoding="utf-8") as f:
        json.dump(payload, f, ensure_ascii=False, separators=(",", ":"))

    size_kb = os.path.getsize(JSON_OUT) / 1024
    print(f"OK  total: {len(airports)} airports (skipped {skipped_no_iata} no-IATA, {skipped_bad_coord} bad-coord)")
    print(f"OK  countries: {len(by_country)}")
    print(f"OK  output: {JSON_OUT} ({size_kb:.1f} KB)")
    print("Top 12 countries:")
    for c, n in top_countries[:12]:
        print(f"     {c}: {n}")


if __name__ == "__main__":
    main()
