# You may need to install BeautifulSoup: pip install beautifulsoup4 requests
# website used for this https://crs.cookcountyclerkil.gov/Search
import requests
from bs4 import BeautifulSoup
import csv

def read_csv_list(filename):
    with open(filename, "r") as f:
        return [line.strip() for line in f if line.strip()]

lastnames = read_csv_list("lastnames.csv")
townnames = read_csv_list("townnames.csv")

headers = {
    "User-Agent": "Mozilla/5.0"
}

def get_table_data(soup):
    table = soup.find("table", {"id": "tblData"})
    if table:
        rows = table.find_all("tr")
        return [[col.get_text(strip=True) for col in row.find_all(["td", "th"])] for row in rows]
    return None

def get_next_page_url(soup):
    # Try to find a link/button for the next page. Adjust selector as needed.
    next_link = soup.find("a", {"rel":"next"})
    if next_link and next_link.has_attr("href"):
        return "https://crs.cookcountyclerkil.gov" + next_link["href"]
    return None

for townname in townnames:
    print(f"Processing town: {townname}")
    with open(f"{townname}.csv", "w", newline="") as csvfile:
        writer = csv.writer(csvfile)
        for lastname in lastnames:
            url = f"https://crs.cookcountyclerkil.gov/Search/Result?id1={lastname}%20in%20{townname}"
            page_url = url
            first_page = True
            # with open(f"{townname}_{lastname}.csv", "w", newline="") as csvfile:
            # with open(f"{townname}.csv", "w", newline="") as csvfile:
            #     writer = csv.writer(csvfile)
            while page_url:
                response = requests.get(page_url, headers=headers)
                soup = BeautifulSoup(response.text, "html.parser")
                table_data = get_table_data(soup)
                if table_data:
                    header_row = ["View Doc","Doc Number","Doc Recorded","Doc Executed","Doc Type","1st Grantor","1st Grantee","Assoc. Doc#","1st PIN"]
                    for row in table_data:
                        # Skip header rows
                        if row == header_row:
                            continue
                        # Split '1st PIN' field if present
                        if len(row) == 10:
                            pin = row[9][:18]
                            address = row[9][18:]
                            new_row = row[:9] + [pin, address]
                            writer.writerow(new_row)
                        else:
                            writer.writerow(row)
                    print(f"Table data written from {page_url}")
                else:
                    print(f"Document table not found on {page_url}")
                    break
                next_page_url = get_next_page_url(soup)
                print(f"Next page URL: {next_page_url}")
                if next_page_url and next_page_url != page_url:
                    page_url = next_page_url
                    first_page = False
                else:
                    break