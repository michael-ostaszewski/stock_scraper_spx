# ============================================================
# Stock scraper with CSV append – Finviz
# ============================================================
import os
import time
import pandas as pd
from datetime import datetime, timezone
from bs4 import BeautifulSoup
from time import perf_counter

from selenium import webdriver
from selenium.webdriver.chrome.service import Service
from selenium.webdriver.chrome.options import Options
from selenium.webdriver.common.by import By
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
from selenium.common.exceptions import TimeoutException
from requests.exceptions import ReadTimeout

# ============================================================
# 1) Ścieżki i konfiguracja
# ============================================================

# driver_path = "/Users/michal/.wdm/drivers/chromedriver/mac64/137.0.7151.68/chromedriver-mac-x64/chromedriver"  # ścieżka do chromedrivera
# driver_path = "/Users/michal/.wdm/drivers/chromedriver/mac64/139.0.7258.66/chromedriver-mac-x64/chromedriver"
driver_path = "/Users/michal/.wdm/drivers/chromedriver/mac64/141.0.7390.37/chromedriver-mac-x64/chromedriver"

# csv_path = "/Users/michal/PycharmProjects/Stock Scraper/sp500symbols.csv"  # lista tickerów (S&P 500) - 548 spółek
csv_path = "/Users/michal/PycharmProjects/Stock Scraper/Russel 1000 Symbols/russell_1000_constituents_extended.csv"  # lista tickerów (Russel1000 oraz moja selekcja) - 1061 spółek
# csv_path     ="/Users/michal/PycharmProjects/Stock Scraper/Stocks fv/finviz_retry.csv"

# katalog i plik wyjściowy na dane Finviz
output_dir = "/Users/michal/PycharmProjects/Stock Scraper/Stocks fv"
output_csv_path = os.path.join(output_dir, "finviz_snapshot.csv")

max_tickers = 1071  # ile pierwszych spółek pobierać
wait_secs = 2  # czekanie na dane jednej spółki
sleep_sec = 1  # odstęp między żądaniami

# znacznik czasu dla całej sesji (UTC)
now_utc = datetime.now(timezone.utc)
date_str = now_utc.strftime("%Y-%m-%d")
time_str = now_utc.strftime("%H:%M:%S UTC")

# upewniamy się, że katalog docelowy istnieje
os.makedirs(output_dir, exist_ok=True)


# ============================================================
# 2) Funkcja zapisu do CSV z automatycznym dopisywaniem
# ============================================================

def save_df_to_csv(df: pd.DataFrame, output_csv_path: str):
    """Appenduje `df` do pliku CSV (tworzy plik, jeśli nie istnieje)."""
    file_exists = os.path.isfile(output_csv_path)

    # Jeśli plik istnieje, upewnij się, że ostatni zapis zakończył się nową linią
    if file_exists:
        with open(output_csv_path, "rb+") as f:
            f.seek(0, os.SEEK_END)
            if f.tell() > 0:
                f.seek(-1, os.SEEK_END)
                if f.read(1) != b"\n":
                    f.write(b"\n")

    df.to_csv(
        output_csv_path,
        index=False,
        mode="a",  # append
        header=not file_exists,  # nagłówki tylko przy pierwszym zapisie
        sep=";"  # delimiter
    )


# ============================================================
# 3) WebDriver i pomocnicze
# ============================================================

def init_driver(headless: bool = True):
    opts = Options()
    if headless:
        opts.add_argument("--headless=new")
    opts.add_argument("--window-size=720,420")
    return webdriver.Chrome(service=Service(driver_path), options=opts)


def wait_for_data(drv, timeout: int = 5):
    WebDriverWait(drv, timeout).until(
        EC.presence_of_element_located((By.CSS_SELECTOR, "td.snapshot-td2"))
    )


def parse_snapshot_to_dict(html: str, ticker: str) -> dict:
    soup = BeautifulSoup(html, "html.parser")
    cells = soup.select("td.snapshot-td2")

    row = {
        "Ticker": ticker.upper(),
        "Date of record fv": date_str,
        "Time of record fv": time_str,
    }
    for i in range(0, len(cells), 2):
        metric = cells[i].get_text(" ", strip=True)
        value = cells[i + 1].get_text(" ", strip=True)
        row[metric] = value
    return row


def scrape_one_ticker(drv, tkr: str) -> dict:
    url = f"https://finviz.com/quote.ashx?t={tkr}&p=d"
    drv.get(url)

    # jednorazowa próba kliknięcia banera cookies
    try:
        WebDriverWait(drv, 3).until(
            EC.element_to_be_clickable((By.XPATH, "//button[contains(.,'Accept') or contains(.,'Zgadzam')]"))
        ).click()
    except TimeoutException:
        pass

    wait_for_data(drv, wait_secs)
    scroll_to_snapshot_table(drv)  # ← DODAJ TO
    return parse_snapshot_to_dict(drv.page_source, tkr)


def scroll_to_snapshot_table(drv):
    """Przewija stronę do tabeli snapshot, żeby upewnić się, że elementy są widoczne/renderowane."""
    try:
        tbl = drv.find_element(By.CSS_SELECTOR, "table.snapshot-table2")
        drv.execute_script(
            "arguments[0].scrollIntoView({behavior: 'instant', block: 'center'});", tbl
        )
    except Exception:
        # jeśli tabeli nie ma (np. captcha), nie przerywamy – obsłuży to wait_for_data
        pass


# ============================================================
# 4) Wczytanie listy symboli
# ============================================================

tickers_df = pd.read_csv(csv_path)
tickers_list = tickers_df["Symbol"].str.upper().head(max_tickers).tolist()

print(f"\n🔹 Start – {len(tickers_list)} spółek: {', '.join(tickers_list)}")

# ============================================================
# 5) Główna pętla z restartem drivera co 50 spółek
# ============================================================

rows = []
chunk_rows = []  # tylko bieżąca pięćdziesiątka
retry_list = []
driver = init_driver(headless=False)

for idx, tkr in enumerate(tickers_list, start=1):

    start_t = perf_counter()  # ← START pomiaru

    # ► informacji o postępie
    print(f"\n===== {tkr} =====")
    print(f"akcja {idx}/{len(tickers_list)}")

    # ► pobieranie jednej spółki
    try:
        row = scrape_one_ticker(driver, tkr)
        rows.append(row)
        chunk_rows.append(row)  # zbieramy do zapisu co 50
        print(f"[{tkr}] ✅  pobrano {len(row) - 1} metryk")
    except (TimeoutException, ReadTimeout) as e:
        print(f"[{tkr}] ❌ timeout: {e}")
        retry_list.append(tkr)
        driver.quit()  # natychmiastowy restart sesji
        driver = init_driver(headless=False)
        time.sleep(10)
    except Exception as e:
        print(f"[{tkr}] ❌  błąd: {e}")
        retry_list.append(tkr)

    elapsed = perf_counter() - start_t  # ← KONIEC pomiaru
    print(f"⏱ {tkr} w {elapsed:.1f} s")  # komunikat z czasem

    time.sleep(sleep_sec)

    # ► co 50 spółek – zapisujemy partię i restartujemy drivera
    if idx % 50 == 0 or idx == len(tickers_list):
        if chunk_rows:  # zapis tylko gdy coś zebrano
            save_df_to_csv(pd.DataFrame(chunk_rows), output_csv_path)
            chunk_rows.clear()  # zerujemy bufor
            print(f"💾 Zapisano partię do {output_csv_path}")

        driver.quit()  # zamykamy starą sesję
        if idx < len(tickers_list):  # uruchamiamy nową, jeśli są kolejne tickery
            driver = init_driver(headless=False)
            time.sleep(5)  # mała przerwa po restarcie

# koniec – driver już zamknięty, bo ostatnia iteracja też wykona quit()

# ============================================================
# 5b) Zapis listy retry
# ============================================================

retry_csv_path = os.path.join(output_dir, "finviz_retry.csv")
pd.DataFrame({"Symbol": pd.Series(retry_list).drop_duplicates()}) \
    .to_csv(retry_csv_path, index=False)  # tworzy / nadpisuje plik
print(f"⏪ Zapisano listę retry: {retry_csv_path}")

# ============================================================
# 5c) Ponowna próba pobrania tickerów z finviz_retry.csv
# ============================================================

if os.path.isfile(retry_csv_path):
    retry_df = pd.read_csv(retry_csv_path)
    retry_df = retry_df[~retry_df["Symbol"].isin(["DFS", "BF.B", "JNPR"])]  # ← odrzucamy błędne tickery
    retry_tickers = retry_df["Symbol"].drop_duplicates().tolist()

    if retry_tickers:
        print(f"\n🔄 Retry dla {len(retry_tickers)} spółek: {', '.join(retry_tickers)}")

        driver_retry = init_driver(headless=False)
        still_retry = []  # tickery, które znów się nie udały
        retry_rows_buf = []  # udane retrysy

        for tkr in retry_tickers:
            try:
                row = scrape_one_ticker(driver_retry, tkr)
                rows.append(row)  # dodajemy do głównej listy
                retry_rows_buf.append(row)
                print(f"[{tkr}] ✅  retry udany")
            except Exception as e:
                print(f"[{tkr}] ❌  retry błąd: {e}")
                still_retry.append(tkr)
            time.sleep(sleep_sec)

        driver_retry.quit()

        # dopisujemy udane retrysy do pliku wynikowego
        if retry_rows_buf:
            save_df_to_csv(pd.DataFrame(retry_rows_buf), output_csv_path)
            print(f"💾 Dodano {len(retry_rows_buf)} retrysy do {output_csv_path}")

        # aktualizujemy (nadpisujemy) plik retry
        pd.DataFrame({"Ticker": still_retry}).to_csv(retry_csv_path, index=False)
        if still_retry:
            print(f"⏪ Pozostało {len(still_retry)} tickerów w retry: {retry_csv_path}")
        else:
            print("✅ Plik retry pusty – wszystkie tickery pobrane.")

# ============================================================
# 6) DataFrame i zapis do CSV
# ============================================================

df_wide = pd.DataFrame(rows)

# ustawiamy Ticker jako pierwszą kolumnę – reszta w kolejności oryginalnej
df_wide = df_wide[["Ticker"] + [c for c in df_wide.columns if c != "Ticker"]]

print(f"\n✔️  Gotowe – {df_wide.shape[0]} spółek, {df_wide.shape[1]} kolumn.")
print(df_wide.head())

# zapis/append do pliku
# save_df_to_csv(df_wide, output_csv_path)
print(f"📁 Dane dopisano do: {output_csv_path}\n")