import csv
import time

import requests
from bs4 import BeautifulSoup

HEADERS = {"User-Agent": "price-research-bot/1.0 (contact: research@example.org)"}


def fetch(url: str) -> BeautifulSoup:
    response = requests.get(url, headers=HEADERS, timeout=20)
    response.raise_for_status()
    return BeautifulSoup(response.text, "html.parser")


def parse_listing(page: BeautifulSoup) -> list[dict]:
    rows = []
    for card in page.select("div.product-card"):
        price = card.select_one("span.price")
        rows.append({"name": card.select_one("h2").get_text(strip=True),
                     "price": float(price.get_text(strip=True).replace("$", "").replace(",", "")) if price else None})
    return rows


def crawl(start_urls: list[str], out_path: str, delay: float = 1.5) -> None:
    with open(out_path, "w", newline="", encoding="utf-8") as handle:
        writer = csv.DictWriter(handle, fieldnames=["name", "price"])
        writer.writeheader()
        for url in start_urls:
            writer.writerows(parse_listing(fetch(url)))
            time.sleep(delay)
