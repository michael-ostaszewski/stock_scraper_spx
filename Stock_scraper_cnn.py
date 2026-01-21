import os
import time
from datetime import datetime, timezone
import pandas as pd
import re

from selenium import webdriver
from selenium.webdriver.common.by import By
from selenium.webdriver.chrome.service import Service
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
from selenium.common.exceptions import NoSuchElementException


SEL_PRICE           = "div.price-1zj6yB.cnn-pcl-12tjup5"
SEL_CHANGE          = "div.sub-price-1GODCI.cnn-pcl-12tjup5:not(.percent-2qdeCV)"
SEL_PERCENT_CHANGE  = "div.sub-price-1GODCI.percent-2qdeCV.cnn-pcl-12tjup5"
SEL_SESSION_DATE    = "div.range-description-pp_d8h.cnn-pcl-12tjup5"
SEL_WAIT_FOR_PAGE   = SEL_PRICE                             # użyjemy w WebDriverWait
# SEL_RANGE_LIST      = "div.range-list-1UVUW0.cnn-pcl-kld3m4"
SEL_RANGE_LIST = "div.range-list-CNwGAc.cnn-pcl-12tjup5, div.range-list-1UVUW0.cnn-pcl-kld3m4"

def get_stock_urls(symbol_csv_path, base_url):
    """
    Wczytuje symbole spółek z podanego pliku CSV i tworzy listę URL-i spółek,
    przy czym zapewnia, że lista będzie zawierała tylko unikalne adresy.

    Args:
        symbol_csv_path (str): Ścieżka do pliku CSV z symbolami spółek.
        base_url (str): Bazowy URL, który zostanie dołączony do każdego symbolu.

    Returns:
        list: Lista unikalnych URL-i spółek.
    """
    # Wczytywanie danych z pliku CSV
    symbollist = pd.read_csv(symbol_csv_path)

    # Tworzenie listy URL-i spółek
    stocks = [base_url + symbol for symbol in symbollist["Symbol"]]

    # Sprawdzenie unikalności
    if len(stocks) == len(set(stocks)):
        print("Wszystkie elementy w liście są unikalne.")
    else:
        print("W liście znajdują się duplikaty.")
        # Znalezienie duplikatów
        duplicates = [item for item in stocks if stocks.count(item) > 1]
        print("Duplikaty:", set(duplicates))
        # Usuwanie duplikatów
        stocks = list(set(stocks))
        print("Usunięto duplikaty:", set(duplicates))

    print("Liczba monitorowanych spółek - po obróbce duplikatów:", len(stocks))
    print()
    print("-" * 57)
    return stocks


def get_paths():
    """
    Zwraca stałe ścieżki używane w projekcie:
    - output_csv_path: Ścieżka do pliku CSV, w którym zapisywane są dane.
    - driver_path: Ścieżka do pliku wykonywalnego WebDrivera.

    Returns:
        tuple: (output_csv_path, driver_path)
    """
    output_csv_path = "/Users/michal/PycharmProjects/Stock Scraper/stocks/stocks_data.csv"
    # driver_path = "/Users/michal/Downloads/chromedriver-mac-x64/chromedriver"
    # driver_path = "/Users/michal/.wdm/drivers/chromedriver/mac64/133.0.6943.53/chromedriver-mac-x64/chromedriver" #zaktualizowana wersja do 133
    # driver_path = "/Users/michal/.wdm/drivers/chromedriver/mac64/135.0.7049.42/chromedriver-mac-x64/chromedriver"
    # driver_path = "/Users/michal/.wdm/drivers/chromedriver/mac64/137.0.7151.68/chromedriver-mac-x64/chromedriver"
    # driver_path = "/Users/michal/.wdm/drivers/chromedriver/mac64/139.0.7258.66/chromedriver-mac-x64/chromedriver"
    # driver_path = "/Users/michal/.wdm/drivers/chromedriver/mac64/141.0.7390.37/chromedriver-mac-x64/chromedriver"
    driver_path = "/Users/michal/.wdm/drivers/chromedriver/mac64/143.0.7499.40/chromedriver-mac-x64/chromedriver"
    return output_csv_path, driver_path


def get_current_timestamps():
    """
    Pobiera aktualny czas UTC oraz tworzy dwa formaty czasowe:
    - hour_timestamp: godzina w formacie "HH:MM:SS UTC"
    - date_timestamp: data w formacie "YYYY-MM-DD"

    Zwraca:
        tuple: (current_time, hour_timestamp, date_timestamp)
    """
    current_time = datetime.now(timezone.utc)
    hour_timestamp = current_time.strftime("%H:%M:%S UTC")
    date_timestamp = current_time.strftime("%Y-%m-%d")
    return current_time, hour_timestamp, date_timestamp

#old function 08.09.2025
# def extract_smart_score(driver) -> int | None:
#     """
#     Próbuje wyciągnąć Smart Score z iframe TipRanks dla różnych layoutów.
#     Zwraca int 1-10 lub None, jeśli się nie udało.
#     """
#     css_variants = [
#         # ── layout 2024-12 ──────────────────────────────
#         "div.value.current-value .text-val.is-value",
#         # ── layout 2025-03 (single <text>) ──────────────
#         "text.sc-cRHGzb.fQvttx",
#         # ── layout 2025-04 (div bez klasy .hitpXG) ──────
#         "div.sc-jMsorb:not(.hitpXG) text.sc-cXawGu",
#         # ── layout 2025-06 (aktywny kafelek) ────────────
#         "div.sc-kNOymR.hDVchC text.sc-dYwGCk",
#         # ── fallback – jedyny kafelek, którego *druga*   │
#         #    klasa różni się od sąsiadów                 │
#         #    (czyli nie „jUyesf” jak w Twoim zrzucie) ───┘
#         "div.sc-kNOymR:not(.jUyesf) text.sc-dYwGCk",
#     ]
#
#     for css in css_variants:
#         try:
#             el = driver.find_element(By.CSS_SELECTOR, css)
#             txt = el.get_attribute("textContent").strip()
#             if txt.isdigit():
#                 return int(txt)
#         except NoSuchElementException:
#             continue
#
#     # Ostateczna próba: znajdź kafelek z klasą zaczynającą się na sc-kNOymR,
#     # który ma *tylko dwie* klasy (aktywny zwykle ma 2, pozostałe 2 + jUyesf).
#     try:
#         candidates = driver.find_elements(By.CSS_SELECTOR, "div[class^='sc-kNOymR']")
#         for div in candidates:
#             if len(div.get_attribute("class").split()) == 2:   # np. "sc-kNOymR hDVchC"
#                 txt = div.find_element(By.TAG_NAME, "text").text.strip()
#                 if txt.isdigit():
#                     return int(txt)
#     except Exception:
#         pass
#
#     return None

#new function 08.09.2025
def extract_smart_score(driver) -> int | None:
    """
    Zwraca Smart Score (int 1–10) z aktualnego DOM TipRanks w iframe.
    Obsługuje nowy layout (performanceRange/current-value) i stare warianty.
    """
    selectors_priority = [
        # ── NOWY layout (2025-09): performanceRange + current-value ─────────────
        "div.performanceRange div.value.current-value .text-val.is-value",
        "div.performanceRange div.value.current-value text",
        # ── fallbacki na wypadek braku performanceRange ─────────────────────────
        "div.value.current-value .text-val.is-value",
        "div.value.current-value text",
        "text.text-val.is-value",
        # ── starsze warianty z klasami sc-* (zostawiamy jako rezerwę) ──────────
        "div.value.current-value .text-val.is-value",         # 2024-12
        "text.sc-cRHGzb.fQvttx",                              # 2025-03
        "div.sc-jMsorb:not(.hitpXG) text.sc-cXawGu",          # 2025-04
        "div.sc-kNOymR.hDVchC text.sc-dYwGCk",                # 2025-06
        "div.sc-kNOymR:not(.jUyesf) text.sc-dYwGCk",          # fallback aktywny kafelek
    ]

    # Próba po selektorach
    for css in selectors_priority:
        try:
            els = driver.find_elements(By.CSS_SELECTOR, css)
            for el in els:
                txt = el.get_attribute("textContent").strip()
                if txt.isdigit():
                    return int(txt)
        except NoSuchElementException:
            continue
        except Exception:
            continue

    # Awaryjnie: weź numer z rodzica current-value, jeśli istnieje
    try:
        cur = driver.find_elements(By.CSS_SELECTOR, "div.performanceRange div.value.current-value, div.value.current-value")
        if cur:
            t = cur[0].find_element(By.CSS_SELECTOR, ".text-val, text")
            txt = t.get_attribute("textContent").strip()
            if txt.isdigit():
                return int(txt)
    except Exception:
        pass

    return None



def scrape_data(limit):
    """
    Funkcja, która iteruje po wszystkich spółkach w 'stocks',
    pobiera dane i zwraca je jako DataFrame.
    """
    all_data = []
    drops = []

    # Konfiguracja Selenium (otwieramy raz przeglądarkę na czas całego procesu)
    service = Service(driver_path)
    driver = webdriver.Chrome(service=service)
    wait = WebDriverWait(driver, 30)

    for index, url in enumerate(stocks[:limit], start=1):
        symbol = url.split("/")[-1]
        print()
        print(f"Procesuję spółkę {index}/{limit}: {symbol}")

        stats = {}

        try:
            # Mierzenie czasu ładowania strony
            start_time = time.time()
            driver.get(url)
            end_time = time.time()

            load_time = end_time - start_time
            print(f"Czas ładowania strony {symbol}: {load_time:.2f} sekund")
            time.sleep(1)

            # Akceptacja plików cookie – TYLKO przy pierwszym ładowaniu w pętli
            if index == 1:
                try:
                    accept_cookies_button = WebDriverWait(driver, 10).until(
                        EC.element_to_be_clickable((By.ID, "onetrust-accept-btn-handler"))
                    )
                    accept_cookies_button.click()
                    time.sleep(1)  # krótka pauza, żeby overlay zdążył zniknąć
                except:
                    print("Nie znaleziono/nie kliknięto przycisku accept cookies. "
                          "Może baner się nie pojawił albo selektor jest błędny.")

            # Czekamy na kluczowy element strony zamiast time.sleep()
            try:
                dynamic_element_wait_start = time.time()
                WebDriverWait(driver, 10).until(
                    EC.presence_of_element_located(
                        (By.CSS_SELECTOR, ".price-1zj6yB.cnn-pcl-12tjup5")
                    )
                )
                dynamic_element_wait_end = time.time()
                dynamic_load_time = dynamic_element_wait_end - dynamic_element_wait_start
                print(f"Czas oczekiwania na dynamiczne elementy {symbol}: {dynamic_load_time:.2f} sekund")
                print()
                print("-" * 57)

            except Exception as e:
                print(f"Dynamiczne elementy strony {symbol} nie załadowały się w wyznaczonym czasie.")
                dynamic_load_time = None
                # Łączny czas oczekiwania
                total_wait_time = load_time + (dynamic_load_time if dynamic_load_time else 0)
                print(f"Łączny czas oczekiwania {symbol}: {total_wait_time:.2f} sekund")
                print()
                print("-" * 57)

            # 0. Czas ładowania strony
            stats["Page Load Time (s)"] = round(load_time, 2)
            # Jeśli dynamic_load_time się nie ustawiło (np. w except), chcemy uniknąć błędu:
            if 'dynamic_load_time' not in locals() or dynamic_load_time is None:
                dynamic_load_time = float('nan')  # lub 0.0, w zależności od preferencji
            stats["Dynamic Element Load Time (s)"] = round(dynamic_load_time, 2)



            # 1. Cena akcji
            # price_element = driver.find_element(By.CLASS_NAME, "price-2kQQGw.cnn-pcl-eltrz4")
            # price = price_element.text
            # stats["Price"] = price

            # Próba pobrania ceny poza czasem otwarcia sesji
            try:
                # Metoda dotychczasowa
                # price_element = driver.find_element(By.CSS_SELECTOR, ".price-2kQQGw.cnn-pcl-eltrz4")
                # price = price_element.text
                price_element = driver.find_element(By.CSS_SELECTOR, ".price-1zj6yB.cnn-pcl-12tjup5")
                price = price_element.text
            except NoSuchElementException:
                # Jeśli nie znaleziono elementu, próbujemy pobrać cenę podczas trwania sesji
                try:
                    # Alternatywna ścieżka – wyszukujemy wewnątrz kontenera z danymi o cenie
                    # Używamy CSS_SELECTOR, aby precyzyjnie wskazać element z ceną
                    price_element = driver.find_element(By.CSS_SELECTOR,
                                                        ".price-data-2LZZ5_ .pricing-container-3_SSKi .price-2kQQGw")
                    price = price_element.text
                except NoSuchElementException:
                    # Opcjonalnie możesz obsłużyć sytuację, gdy żaden z elementów nie zostanie znaleziony
                    print("Nie udało się znaleźć elementu z ceną")
                    price = None

            stats["Price"] = price
            print(f"Cena  (od ostatniego zamknięcia) = {price}")

            # # 2. Zmiana ceny
            # change_element = driver.find_element(By.CLASS_NAME, "sub-price-1huDfE.cnn-pcl-eltrz4")
            # change = change_element.text
            # stats["Change"] = change
            #
            # # 3. Zmiana procentowa
            # percent_change_element = driver.find_element(
            #     By.CLASS_NAME,
            #     "sub-price-1huDfE.percent-21eK0W.cnn-pcl-eltrz4"
            # )
            # percent_change = percent_change_element.text
            # stats["Percent Change"] = percent_change

            # # Pobranie zmiany ceny (bez procenta)
            # change_element = driver.find_element(By.CSS_SELECTOR,
            #                                      "div.sub-price-2Q-2oW.cnn-pcl-kld3m4.up-3QsRe9:not(.percent-2vLQBV)")
            # change = change_element.text
            # stats["Change"] = change
            #
            # # Pobranie zmiany procentowej
            # percent_change_element = driver.find_element(By.CSS_SELECTOR,
            #                                              "div.sub-price-2Q-2oW.percent-2vLQBV.cnn-pcl-kld3m4.up-3QsRe9")
            # percent_change = percent_change_element.text
            # stats["Percent Change"] = percent_change

            # # Pobranie zmiany ceny (BEZ procenta)
            # change_element = driver.find_element(
            #     By.CSS_SELECTOR,
            #     "div.sub-price-2Q-2oW.cnn-pcl-kld3m4:not(.percent-2vLQBV)"  # Bez .up-3QsRe9 i bez .down-1UgGgv
            # )
            # change = change_element.text.strip()
            #
            # # Pobranie zmiany procentowej
            # percent_element = driver.find_element(
            #     By.CSS_SELECTOR,
            #     "div.sub-price-2Q-2oW.percent-2vLQBV.cnn-pcl-kld3m4"  # Wyłącznie element z percent-2vLQBV
            # )
            # percent_change = percent_element.text.strip()



            try:
                # ------------------------------
                # 2. Zmiana ceny (bez procenta)
                # ------------------------------
                change_element = driver.find_element(
                    By.CSS_SELECTOR,
                    ".sub-price-1GODCI.cnn-pcl-12tjup5:not(.percent-2vLQBV)"
                    # wychwytuje .sub-price..., ale nie .percent-2vLQBV
                )
                change_text = change_element.text.strip()
                stats["Change"] = change_text

                print(f"Zmiana (od ostatniego zamknięcia) = {change_text}")

                # ------------------------------
                # 3. Zmiana procentowa
                # ------------------------------
                percent_element = driver.find_element(
                    By.CSS_SELECTOR,
                    ".sub-price-1GODCI.percent-2qdeCV.cnn-pcl-12tjup5"
                    # wychwytuje .sub-price... + .percent-2vLQBV
                )
                percent_text = percent_element.text.strip()
                stats["Percent Change"] = percent_text

                print(f"Zmiana procentowa (od ostatniego zamknięcia) = {percent_text}")

            except Exception as e:
                print("Błąd podczas pobierania zmiany ceny i/lub zmiany procentowej:", e)

            # try:
            #     # ------------------------------
            #     # 3. Zmiana procentowa
            #     # ------------------------------
            #     percent_element = driver.find_element(
            #         By.CSS_SELECTOR,
            #         "div.sub-price-2Q-2oW.percent-2vLQBV.cnn-pcl-kld3m4"
            #         # wychwytuje .sub-price... + .percent-2vLQBV
            #     )
            #     raw_percent_text = percent_element.text.strip()  # np. '- 5.24%' lub '3.50%'
            #
            #     # --- Parsujemy, żeby zachować/wyczyścić minus, usunąć zbędne spacje ---
            #     temp = raw_percent_text.replace(" ", "")  # usuń spacje np. '- 5.24%' → '-5.24%'
            #     has_percent = temp.endswith('%')
            #     if has_percent:
            #         temp = temp[:-1]  # usuń '%' z końca, żeby parsować jako float
            #
            #     try:
            #         val = float(temp)  # np. -5.24 lub 3.50
            #         # Jeśli ujemne, wymuś '-', jeśli dodatnie - nic nie dopisuj
            #         sign = '-' if val < 0 else ''
            #         abs_val = abs(val)
            #
            #         # Składamy końcowy string
            #         final_str = f"{sign}{abs_val}"
            #         if has_percent:
            #             final_str += '%'
            #     except ValueError:
            #         # Gdyby float(temp) się nie udał, pozostawiamy oryginalny tekst
            #         final_str = raw_percent_text
            #
            #     stats["Percent Change"] = final_str
            #     print(f"Zmiana procentowa (od ostatniego zamknięcia) = {final_str}")
            #
            # except Exception as e:
            #     print("Błąd podczas pobierania zmiany procentowej:", e)
            #     # Jeśli chcesz wstawić None w razie błędu, możesz to zrobić tu:
            #     stats["Percent Change"] = None
            #
            #

            # 4. Data sesji
            # session_date_element = driver.find_element(By.CSS_SELECTOR, "div.timestamp-2067hl.cnn-pcl-kld3m4")
            session_date_element = driver.find_element(
                By.CSS_SELECTOR,
                ".range-description-pp_d8h.cnn-pcl-12tjup5"
            )  # update 16.07.2025
            session_date = session_date_element.text
            stats["Session Date"] = session_date

            # 5. Cena po zamknięciu - to działa tylko jak sesja jest już zamknięta
            try:
                closing_price_element = driver.find_element(
                    By.CSS_SELECTOR,
                    ".pricing-container-3_SSKi.secondary-160A5Y .price-2kQQGw.secondary-160A5Y.cnn-pcl-eltrz4"
                )
                closing_price = closing_price_element.text
            except NoSuchElementException:
                # Jeśli element nie został znaleziony (czyli sesja jest otwarta), przypisz aktualną cenę
                closing_price = price

            stats["Closing Price"] = closing_price

            # --------------------------
            # 6. Pobieranie danych dla wybranych przedziałów czasowych
            # --------------------------
            time_range_data = {}  # słownik na dane dla poszczególnych przedziałów (np. "1d", "5d", itp.)
            try:
                # range_list = wait.until(
                #     EC.presence_of_element_located(
                #         (By.CSS_SELECTOR, "div.range-list-1UVUW0.cnn-pcl-kld3m4")
                #
                #     )
                # )
                range_list = wait.until(
                    EC.presence_of_element_located(
                        (By.CSS_SELECTOR, "div.range-list-CNwGAc.cnn-pcl-12tjup5")
                    )
                ) #update 16.07.2025
                time_buttons = range_list.find_elements(By.TAG_NAME, "button")
            except Exception as e:
                print(f"Nie udało się pobrać przycisków przedziałów czasowych dla {symbol}: {e}")
                time_buttons = []

            # for button in time_buttons:
            #     # Pobieramy tekst przycisku, np. "1d", "5d", "1m", "6m", "YTD", "1y", "5y"
            #     time_range = button.text.strip()
            #     print(f"  Przetwarzam przedział {symbol}: {time_range}")
            #
            #     try:
            #         # Upewniamy się, że przycisk jest widoczny – przewijamy do niego
            #         driver.execute_script("arguments[0].scrollIntoView({block: 'center'});", button)
            #         time.sleep(0.5)
            #         # Klikamy przycisk, aby załadować dane dla wybranego przedziału
            #         button.click()
            #         time.sleep(2)  # czekamy na aktualizację danych
            #
            #         # Pobieramy różnicę ceny (bez procentowej zmiany)
            #         sub_price_element = wait.until(
            #             EC.visibility_of_element_located(
            #                 (By.CSS_SELECTOR, "div.sub-price-2Q-2oW.cnn-pcl-kld3m4:not(.percent-2vLQBV)")
            #             )
            #         )
            #         sub_price = sub_price_element.text.strip()
            #
            #         # Pobieramy procentową zmianę
            #         percent_element = wait.until(
            #             EC.visibility_of_element_located(
            #                 (By.CSS_SELECTOR, "div.sub-price-2Q-2oW.percent-2vLQBV.cnn-pcl-kld3m4")
            #             )
            #         )
            #         percent_change = percent_element.text.strip()
            #
            #         # Zapisujemy dane dla tego przedziału
            #         time_range_data[time_range] = {"sub_price": sub_price, "percent_change": percent_change}
            #         print(f"    {time_range} -> Różnica ceny {symbol}: {sub_price}, Różnica %: {percent_change}")
            #     except Exception as e:
            #         print(f"    Problem z pobraniem danych dla {time_range} w spółce {symbol}: {e}")

            for button in time_buttons:
                # Pobieramy tekst przycisku, np. "1d", "5d", "1m", "6m", "YTD", "1y", "5y"
                time_range = button.text.strip()
                print(f"  Przetwarzam przedział {symbol}: {time_range}")

                try:
                    # Upewniamy się, że przycisk jest widoczny – przewijamy do niego
                    driver.execute_script("arguments[0].scrollIntoView({block: 'center'});", button)
                    time.sleep(0.5)
                    # Klikamy przycisk, aby załadować dane dla wybranego przedziału
                    button.click()
                    time.sleep(2)  # czekamy na aktualizację danych

                    # Pobieramy różnicę ceny (bez procentowej zmiany)
                    # sub_price_element = wait.until(
                    #     EC.visibility_of_element_located(
                    #         (By.CSS_SELECTOR, "div.sub-price-2Q-2oW.cnn-pcl-kld3m4:not(.percent-2vLQBV)")
                    #     )
                    # )
                    # sub_price = sub_price_element.text.strip()
                    #
                    # # Pobieramy procentową zmianę
                    # percent_element = wait.until(
                    #     EC.visibility_of_element_located(
                    #         (By.CSS_SELECTOR, "div.sub-price-2Q-2oW.percent-2vLQBV.cnn-pcl-kld3m4")
                    #     )
                    # )
                    # percent_change = percent_element.text.strip()
                    sub_price_element = wait.until(
                        EC.visibility_of_element_located(
                            (By.CSS_SELECTOR,
                             "div.sub-price-1GODCI.cnn-pcl-12tjup5:not(.percent-2qdeCV)")
                        )
                    )
                    sub_price = sub_price_element.text.strip()

                    percent_element = wait.until(
                        EC.visibility_of_element_located(
                            (By.CSS_SELECTOR,
                             "div.sub-price-1GODCI.percent-2qdeCV.cnn-pcl-12tjup5")
                        )
                    )
                    percent_change = percent_element.text.strip() #update 16.07.2025

                    # Zapisujemy dane dla tego przedziału
                    time_range_data[time_range] = {"sub_price": sub_price, "percent_change": percent_change}
                    print(f"    {time_range} -> Różnica ceny {symbol}: {sub_price}, Różnica %: {percent_change}")
                except Exception as e:
                    print(f"    Problem z pobraniem danych dla {time_range} w spółce {symbol}: {e}")

            # stats["Time Range Data"] = time_range_data
            # Dla każdego przedziału czasowego z time_range_data
            for time_range, values in time_range_data.items():
                # Utworzenie osobnych kluczy w stats dla sub_price i percent_change
                stats[f"{time_range}-sub_price"] = values.get("sub_price", None)
                stats[f"{time_range}-percent_change"] = values.get("percent_change", None)

            # 6. Key stock statistics
            keys = driver.find_elements(By.CLASS_NAME, "markets-keyfacts__label-2ArNJP")
            values = driver.find_elements(By.CLASS_NAME, "markets-keyfacts__value-1fAhI5")
            for key, value in zip(keys, values):
                key_text = key.text.strip()
                value_text = value.text.strip()
                stats[key_text] = value_text
                print(f"Key: {key_text} -> Value: {value_text}")

            print()
            print("-" * 57)

            # # 7. Smart Score z iframe TipRanks
            # try:
            #     iframe = driver.find_element(By.CSS_SELECTOR, "iframe[src*='tipranks']")
            #     driver.switch_to.frame(iframe)
            #     smart_score_element = driver.find_element(By.CLASS_NAME, "sc-cGXZpB.hINHXp")
            #     smart_score = smart_score_element.text
            #     stats["Smart Score"] = smart_score
            # except Exception as iframe_error:
            #     # Jeżeli nie znajdziemy iframe, wstawiamy None
            #     stats["Smart Score"] = None
            # finally:
            #     # powrót do głównej strony
            #     driver.switch_to.default_content()

            # 7. Smart Score z iframe TipRanks
            # try:
            #     iframe = driver.find_element(By.CSS_SELECTOR, "iframe[src*='tipranks']")
            #     driver.switch_to.frame(iframe)
            #
            #     # Pobieramy element DIV, który posiada klasy "sc-jBIHhB" oraz "bqMmLN"
            #     smart_score_container = driver.find_element(By.CSS_SELECTOR, "div.sc-jBIHhB.bqMmLN")
            #
            #     # Pobieramy element <text> wewnątrz tego DIVa (możesz też bezpośrednio użyć .text na smart_score_container,
            #     # jeśli nie ma innych treści)
            #     smart_score_element = smart_score_container.find_element(By.TAG_NAME, "text")
            #     smart_score = smart_score_element.text
            #
            #     stats["Smart Score"] = smart_score
            # except Exception as iframe_error:
            #     # Jeżeli nie znajdziemy iframe lub elementu, wstawiamy None
            #     stats["Smart Score"] = None
            # finally:
            #     # Powrót do głównej strony
            #     driver.switch_to.default_content()
            # #
            ###### --------------------------------------------

            # 7. Smart Score z iframe TipRanks - nowy smart score 18.03.2025 - działa
            # try:
            #     print("Próba znalezienia iframe TipRanks...")
            #     iframe = driver.find_element(By.CSS_SELECTOR, "iframe[src*='tipranks']")
            #     print("Znaleziono iframe. Przełączam się do niego.")
            #     driver.switch_to.frame(iframe)
            #
            #     # Szukamy elementu text z klasami sc-cRHGzb fQvttx – w treści HTML stoi tam wartość np. "9"
            #     print("Szukam elementu Smart Score przez selektor CSS: text.sc-cRHGzb.fQvttx")
            #     smart_score_element = driver.find_element(By.CSS_SELECTOR, "text.sc-cRHGzb.fQvttx")
            #
            #     smart_score = smart_score_element.text
            #     print(f"Znaleziono Smart Score: {smart_score}")
            #
            #     stats["Smart Score"] = smart_score
            #
            # except Exception as iframe_error:
            #     print("Wystąpił błąd podczas pobierania Smart Score z iframe:")
            #     print(iframe_error)
            #     stats["Smart Score"] = None
            #
            # finally:
            #     print("Powrót do kontekstu głównego (default_content).")
            #     driver.switch_to.default_content()

            # # 7. Smart Score z iframe TipRanks - nowe podejście 06.04.2025 - działa
            # try:
            #     print("Próba znalezienia iframe TipRanks...")
            #     iframe = driver.find_element(By.CSS_SELECTOR, "iframe[src*='tipranks']")
            #     print("Znaleziono iframe. Przełączam się do niego.")
            #     driver.switch_to.frame(iframe)
            #
            #     # Dajemy czas, aby widget TipRanks zdążył się wczytać (React/JS).
            #     time.sleep(1)
            #
            #     # Szukamy diva sc-jMsorb, który nie ma klasy 'hitpXG' – to właśnie aktywny Smart Score
            #     print("Szukam elementu div.sc-jMsorb, który nie ma klasy 'hitpXG' (aktywny Smart Score)...")
            #     active_score_div = driver.find_element(
            #         By.CSS_SELECTOR,
            #         "div.sc-jMsorb:not(.hitpXG)"
            #     )
            #
            #     # We wnetrzu powyższego diva jest <text class="sc-cXawGu ...">X</text>
            #     score_text_el = active_score_div.find_element(By.CSS_SELECTOR, "text.sc-cXawGu")
            #     smart_score = score_text_el.get_attribute("textContent").strip()
            #
            #     print(f"Znaleziono Smart Score: {smart_score}")
            #     stats["Smart Score"] = smart_score
            #
            # except Exception as iframe_error:
            #     print("Wystąpił błąd podczas pobierania Smart Score z iframe:")
            #     print(iframe_error)
            #     stats["Smart Score"] = None
            #
            # finally:
            #     print("Powrót do kontekstu głównego (default_content).")
            #     driver.switch_to.default_content()

            # # 7. Smart Score z iframe TipRanks – aktualizacja 30-04-2025
            # try:
            #     print("Próba znalezienia iframe TipRanks...")
            #     iframe = driver.find_element(By.CSS_SELECTOR, "iframe[src*='tipranks']")
            #     driver.switch_to.frame(iframe)
            #
            #     # czekamy aż w iframe pojawi się div z class="value current-value"
            #     wait.until(
            #         EC.presence_of_element_located(
            #             (By.CSS_SELECTOR, "div.value.current-value .text-val.is-value")
            #         )
            #     )
            #
            #     score_el = driver.find_element(
            #         By.CSS_SELECTOR,
            #         "div.value.current-value .text-val.is-value"
            #     )
            #
            #     smart_score = score_el.text.strip()
            #     print(f"Znaleziono Smart Score: {smart_score}")
            #     stats["Smart Score"] = smart_score
            #
            # except Exception as e:
            #     print("Wystąpił błąd podczas pobierania Smart Score z iframe:")
            #     print(e)
            #     stats["Smart Score"] = None
            #
            # finally:
            #     driver.switch_to.default_content()

            # # 7. Smart Score z iframe TipRanks  – wersja odporna na zmiany layoutu -update 24.06
            # try:
            #     print("Próba znalezienia iframe TipRanks…")
            #     iframe = driver.find_element(By.CSS_SELECTOR, "iframe[src*='tipranks']")
            #     driver.switch_to.frame(iframe)
            #
            #     # poczekaj, aż w iframe pojawi się kontener z kafelkami
            #     wait.until(EC.presence_of_element_located(
            #         (By.CSS_SELECTOR, "div[class^='sc-hwkwBN']")  # kontener z dziesięcioma kafelkami
            #     ))
            #
            #     smart_score = extract_smart_score(driver)
            #     print(f"Znaleziono Smart Score: {smart_score}")
            #     stats["Smart Score"] = smart_score
            #
            # except Exception as e:
            #     print("Wystąpił błąd podczas pobierania Smart Score z iframe:")
            #     print(e)
            #     stats["Smart Score"] = None
            #
            # finally:
            #     driver.switch_to.default_content()

            # 7. Smart Score z iframe TipRanks – wersja odporna na nowy layout (performanceRange) - update 08.09.2025
            try:
                print("Próba znalezienia iframe TipRanks…")
                # Poczekaj aż iframe będzie dostępny i przewiń do niego, żeby wymusić załadowanie
                iframe = wait.until(EC.presence_of_element_located((By.CSS_SELECTOR, "iframe[src*='tipranks']")))
                driver.execute_script("arguments[0].scrollIntoView({block: 'center'});", iframe)
                time.sleep(0.3)

                # Pewne przełączenie: czekamy aż rama będzie gotowa i od razu się przełączamy
                wait.until(EC.frame_to_be_available_and_switch_to_it(iframe))

                # Czekamy na dowolny z charakterystycznych elementów nowego/starego layoutu
                def _any_ready(drv):
                    return (
                            drv.find_elements(By.CSS_SELECTOR, "div.performanceRange") or
                            drv.find_elements(By.CSS_SELECTOR,
                                              "div.value.current-value .text-val, div.value.current-value text") or
                            drv.find_elements(By.CSS_SELECTOR, "text.text-val.is-value")
                    )

                WebDriverWait(driver, 10).until(_any_ready)

                smart_score = extract_smart_score(driver)
                print(f"Znaleziono Smart Score: {smart_score}")
                stats["Smart Score"] = smart_score

            except Exception as e:
                print("Wystąpił błąd podczas pobierania Smart Score z iframe:", e)
                stats["Smart Score"] = None

            finally:
                # ZAWSZE wróć do kontekstu głównego
                try:
                    driver.switch_to.default_content()
                except Exception:
                    pass



            # -----------------------------

            # 8. Dane finansowe (Revenue, Net Income, itp.)
            financial_rows = driver.find_elements(
                By.CLASS_NAME,
                "market-financial-table__row-153LbB"
            )
            for row in financial_rows:
                row_title = row.find_element(
                    By.CLASS_NAME,
                    "market-financial-table__title"
                ).text.strip()
                row_value = row.find_element(
                    By.CLASS_NAME,
                    "market-financial-table__text"
                ).text.strip()
                row_change = row.find_element(
                    By.CLASS_NAME,
                    "market-financial-table__change"
                ).text.strip()

                stats[f"{row_title} Value"] = row_value
                stats[f"{row_title} Change"] = row_change

            # 9. Dodaj identyfikator spółki
            stats["Stock"] = symbol

            # 10. Analyst Ratings
            time.sleep(2)
            number_of_analysts = wait.until(
                EC.presence_of_element_located(
                    (By.CLASS_NAME, "markets-donut-chart__title")
                )
            ).text
            stats["Number of analysts"] = number_of_analysts

            buy_recommendation = wait.until(
                EC.presence_of_element_located(
                    (By.ID, "markets-donut-chart__legend--key-value-buy")
                )
            ).text
            hold_recommendation = wait.until(
                EC.presence_of_element_located(
                    (By.ID, "markets-donut-chart__legend--key-value-hold")
                )
            ).text
            sell_recommendation = wait.until(
                EC.presence_of_element_located(
                    (By.ID, "markets-donut-chart__legend--key-value-sell")
                )
            ).text

            stats["Buy Recommendation"] = buy_recommendation
            stats["Hold Recommendation"] = hold_recommendation
            stats["Sell Recommendation"] = sell_recommendation

            # 11. Forecast (High/Median/Low)
            driver.execute_script("window.scrollTo(0, 2500);")
            time.sleep(2)
            forecast_chart_section = wait.until(
                EC.presence_of_element_located(
                    (By.CSS_SELECTOR, "div.markets-forecast-chart")
                )
            )
            svg_element = forecast_chart_section.find_element(By.CSS_SELECTOR, "svg")

            # High Forecast
            try:
                high_data_g = svg_element.find_element(By.CSS_SELECTOR, "g.high-data")
                high_price_tspans = high_data_g.find_elements(
                    By.CSS_SELECTOR,
                    "text.high-price tspan"
                )
                if len(high_price_tspans) >= 2:
                    stats["High Forecast"] = high_price_tspans[1].text.strip()
                else:
                    stats["High Forecast"] = None
            except:
                stats["High Forecast"] = None

            # Median Forecast
            try:
                median_data_g = svg_element.find_element(By.CSS_SELECTOR, "g.median-data")
                median_price_tspans = median_data_g.find_elements(
                    By.CSS_SELECTOR,
                    "text.median-price tspan"
                )
                if len(median_price_tspans) >= 2:
                    stats["Median Forecast"] = median_price_tspans[1].text.strip()
                else:
                    stats["Median Forecast"] = None
            except:
                stats["Median Forecast"] = None

            # Low Forecast
            try:
                low_data_g = svg_element.find_element(By.CSS_SELECTOR, "g.low-data")
                low_price_tspans = low_data_g.find_elements(
                    By.CSS_SELECTOR,
                    "text.median-price tspan"
                )
                if len(low_price_tspans) >= 2:
                    stats["Low Forecast"] = low_price_tspans[1].text.strip()
                else:
                    stats["Low Forecast"] = None
            except:
                stats["Low Forecast"] = None

            # Dodaj do listy all_data
            all_data.append(stats)

        except Exception as e:
            print(f"Wystąpił błąd podczas przetwarzania spółki {symbol}.")
            drops.append(symbol)
            print(f"Dopisano spółkę {symbol} do listy ponownego przetworzenia.")
            print(e)
            print("-" * 57)

    # Zamykamy driver po zakończeniu pętli
    driver.quit()

    # Tworzymy DataFrame z listy słowników
    df = pd.DataFrame(all_data)

    # # Pobieranie aktualnego czasu UTC
    # current_time = datetime.now(timezone.utc)
    #
    # # Wyodrębnienie daty i godziny
    # hour_timestamp = current_time.strftime("%H:%M:%S UTC")
    # date_timestamp = current_time.strftime("%Y-%m-%d")

    # Dodanie kolumn do DataFrame
    df["Time of record"] = hour_timestamp
    df["Date of record"] = date_timestamp

    return df, drops


# def retry_drops(drops):
#     """
#     Funkcja, która iteruje po spółkach z listy 'drops',
#     próbuje ponownie pobrać dane i zwraca DataFrame oraz nową listę 'drops'.
#
#     Parametry:
#     - drops (list): Lista symboli spółek do ponownego przetworzenia.
#
#     Zwraca:
#     - tuple: (DataFrame z danymi przetworzonych spółek, nowa lista 'drops')
#     """
#     all_data = []  # Przechowuje dane każdej spółki
#     new_drops = []  # Przechowuje spółki, które nadal napotykają błędy
#
#     # Konfiguracja Selenium (otwieramy przeglądarkę na czas procesu)
#     service = Service(driver_path)
#     driver = webdriver.Chrome(service=service)
#     wait = WebDriverWait(driver, 30)
#
#     for index, symbol in enumerate(drops, start=1):
#         # Znajdź URL odpowiadający symbolowi
#         try:
#             url = next(url for url in stocks if url.split("/")[-1] == symbol)
#         except StopIteration:
#             print(f"URL dla symbolu {symbol} nie został znaleziony w liście 'stocks'.")
#             new_drops.append(symbol)
#             continue
#
#         print(f"Ponowna próba pobierania spółki {index}/{len(drops)}: {symbol}")
#
#         # Przygotowanie słownika na dane
#         stats = {}
#
#         try:
#             # Mierzenie czasu ładowania strony
#             start_time = time.time()
#             driver.get(url)
#             end_time = time.time()
#
#             # Obliczenie czasu ładowania strony
#             load_time = end_time - start_time
#             print(f"Czas ładowania strony {symbol}: {load_time:.2f} sekund")
#
#             # Dodatkowy czas oczekiwania po załadowaniu strony
#             time.sleep(1)
#
#             # Czekamy na kluczowy element strony zamiast time.sleep()
#             try:
#                 dynamic_element_wait_start = time.time()
#                 WebDriverWait(driver, 10).until(
#                     EC.presence_of_element_located(
#                         (By.CLASS_NAME, "price-2kQQGw.cnn-pcl-eltrz4")
#                     )
#                 )
#                 dynamic_element_wait_end = time.time()
#                 dynamic_load_time = dynamic_element_wait_end - dynamic_element_wait_start
#                 print(f"Czas oczekiwania na dynamiczne elementy {symbol}: {dynamic_load_time:.2f} sekund")
#                 print("-" * 57)
#             except Exception as e:
#                 print(f"Dynamiczne elementy strony {symbol} nie załadowały się w wyznaczonym czasie.")
#                 dynamic_load_time = float('nan')  # Ustaw NaN jeśli nie załadowały się
#                 print(
#                     f"Łączny czas oczekiwania {symbol}: {load_time + (dynamic_load_time if not pd.isna(dynamic_load_time) else 0):.2f} sekund")
#                 print("-" * 57)
#
#             # 0. Czas ładowania strony
#             stats["Page Load Time (s)"] = round(load_time, 2)
#             # 1. Czas oczekiwania na dynamiczne elementy
#             stats["Dynamic Element Load Time (s)"] = round(dynamic_load_time, 2)
#
#             # 1. Cena akcji
#             # price_element = driver.find_element(By.CLASS_NAME, "price-2kQQGw.cnn-pcl-eltrz4")
#             # price = price_element.text
#             # stats["Price"] = price
#
#             # Próba pobrania ceny poza czasem otwarcia sesji
#             try:
#                 # Metoda dotychczasowa
#                 price_element = driver.find_element(By.CSS_SELECTOR, ".price-2kQQGw.cnn-pcl-eltrz4")
#                 price = price_element.text
#             except NoSuchElementException:
#                 # Jeśli nie znaleziono elementu, próbujemy pobrać cenę podczas trwania sesji
#                 try:
#                     # Alternatywna ścieżka – wyszukujemy wewnątrz kontenera z danymi o cenie
#                     # Używamy CSS_SELECTOR, aby precyzyjnie wskazać element z ceną
#                     price_element = driver.find_element(By.CSS_SELECTOR,
#                                                         ".price-data-2LZZ5_ .pricing-container-3_SSKi .price-2kQQGw")
#                     price = price_element.text
#                 except NoSuchElementException:
#                     # Opcjonalnie możesz obsłużyć sytuację, gdy żaden z elementów nie zostanie znaleziony
#                     print("Nie udało się znaleźć elementu z ceną")
#                     price = None
#
#             stats["Price"] = price
#
#             # 2. Zmiana ceny
#             change_element = driver.find_element(By.CLASS_NAME, "sub-price-1huDfE.cnn-pcl-eltrz4")
#             change = change_element.text
#             stats["Change"] = change
#
#             # 3. Zmiana procentowa
#             percent_change_element = driver.find_element(
#                 By.CLASS_NAME,
#                 "sub-price-1huDfE.percent-21eK0W.cnn-pcl-eltrz4"
#             )
#             percent_change = percent_change_element.text
#             stats["Percent Change"] = percent_change
#
#             # 4. Data sesji
#             session_date_element = driver.find_element(
#                 By.CLASS_NAME,
#                 "timestamp-2-ZRU_.cnn-pcl-eltrz4"
#             )
#             session_date = session_date_element.text
#             stats["Session Date"] = session_date
#
#             # 5. Cena po zamknięciu - to działa tylko jak sesja jest już zamknięta
#             try:
#                 closing_price_element = driver.find_element(
#                     By.CSS_SELECTOR,
#                     ".pricing-container-3_SSKi.secondary-160A5Y .price-2kQQGw.secondary-160A5Y.cnn-pcl-eltrz4"
#                 )
#                 closing_price = closing_price_element.text
#             except NoSuchElementException:
#                 # Jeśli element nie został znaleziony (czyli sesja jest otwarta), przypisz aktualną cenę
#                 closing_price = price
#
#             stats["Closing Price"] = closing_price
#
#             # --------------------------
#             # 12. Pobieranie danych dla wybranych przedziałów czasowych
#             # --------------------------
#             time_range_data = {}  # słownik na dane dla poszczególnych przedziałów (np. "1d", "5d", itp.)
#             try:
#                 range_list = wait.until(
#                     EC.presence_of_element_located((By.CSS_SELECTOR, "div.range-list-1gF64V"))
#                 )
#                 time_buttons = range_list.find_elements(By.TAG_NAME, "button")
#             except Exception as e:
#                 print(f"Nie udało się pobrać przycisków przedziałów czasowych dla {symbol}: {e}")
#                 time_buttons = []
#
#             for button in time_buttons:
#                 # Pobieramy tekst przycisku, np. "1d", "5d", "1m", "6m", "YTD", "1y", "5y"
#                 time_range = button.text.strip()
#                 print(f"  Przetwarzam przedział: {time_range}")
#
#                 try:
#                     # Upewniamy się, że przycisk jest widoczny – przewijamy do niego
#                     driver.execute_script("arguments[0].scrollIntoView({block: 'center'});", button)
#                     time.sleep(0.5)
#                     # Klikamy przycisk, aby załadować dane dla wybranego przedziału
#                     button.click()
#                     time.sleep(2)  # czekamy na aktualizację danych
#
#                     # Pobieramy różnicę ceny
#                     sub_price_element = wait.until(
#                         EC.visibility_of_element_located((By.CSS_SELECTOR, "div.sub-price-1huDfE"))
#                     )
#                     sub_price = sub_price_element.text.strip()
#
#                     # Pobieramy różnicę procentową
#                     percent_element = wait.until(
#                         EC.visibility_of_element_located((By.CSS_SELECTOR, "div.percent-21eK0W"))
#                     )
#                     percent_change = percent_element.text.strip()
#
#                     # Zapisujemy dane dla tego przedziału
#                     time_range_data[time_range] = {"sub_price": sub_price, "percent_change": percent_change}
#                     print(f"    {time_range} -> Różnica ceny: {sub_price}, Różnica %: {percent_change}")
#                 except Exception as e:
#                     print(f"    Problem z pobraniem danych dla {time_range} w spółce {symbol}: {e}")
#
#             # stats["Time Range Data"] = time_range_data
#             # Dla każdego przedziału czasowego z time_range_data
#             for time_range, values in time_range_data.items():
#                 # Utworzenie osobnych kluczy w stats dla sub_price i percent_change
#                 stats[f"{time_range}-sub_price"] = values.get("sub_price", None)
#                 stats[f"{time_range}-percent_change"] = values.get("percent_change", None)
#
#             # 6. Key stock statistics
#             keys = driver.find_elements(By.CLASS_NAME, "markets-keyfacts__label-33Y3Fm")
#             values = driver.find_elements(By.CLASS_NAME, "markets-keyfacts__value-3a2Zj8")
#             for key, value in zip(keys, values):
#                 key_text = key.text.strip()
#                 value_text = value.text.strip()
#                 stats[key_text] = value_text
#
#             # # 7. Smart Score z iframe TipRanks
#             # try:
#             #     iframe = driver.find_element(By.CSS_SELECTOR, "iframe[src*='tipranks']")
#             #     driver.switch_to.frame(iframe)
#             #     smart_score_element = driver.find_element(By.CLASS_NAME, "sc-cGXZpB.hINHXp")
#             #     smart_score = smart_score_element.text
#             #     stats["Smart Score"] = smart_score
#             # except Exception as iframe_error:
#             #     # Jeżeli nie znajdziemy iframe, wstawiamy NaN
#             #     stats["Smart Score"] = float('nan')
#             #     print(f"Brak danych Smart Score dla spółki {symbol}.")
#             #     print(iframe_error)
#             # finally:
#             #     # Powrót do głównej strony
#             #     driver.switch_to.default_content()
#
#             # 7. Smart Score z iframe TipRanks
#             try:
#                 iframe = driver.find_element(By.CSS_SELECTOR, "iframe[src*='tipranks']")
#                 driver.switch_to.frame(iframe)
#
#                 # Pobieramy element DIV, który posiada klasy "sc-jBIHhB" oraz "bqMmLN"
#                 smart_score_container = driver.find_element(By.CSS_SELECTOR, "div.sc-jBIHhB.bqMmLN")
#
#                 # Pobieramy element <text> wewnątrz tego DIVa (możesz też bezpośrednio użyć .text na smart_score_container,
#                 # jeśli nie ma innych treści)
#                 smart_score_element = smart_score_container.find_element(By.TAG_NAME, "text")
#                 smart_score = smart_score_element.text
#
#                 stats["Smart Score"] = smart_score
#             except Exception as iframe_error:
#                 # Jeżeli nie znajdziemy iframe lub elementu, wstawiamy None
#                 stats["Smart Score"] = None
#             finally:
#                 # Powrót do głównej strony
#                 driver.switch_to.default_content()
#
#             # 8. Dane finansowe (Revenue, Net Income, itp.)
#             try:
#                 financial_rows = driver.find_elements(
#                     By.CLASS_NAME,
#                     "market-financial-table__row-153LbB"
#                 )
#                 for row in financial_rows:
#                     try:
#                         row_title = row.find_element(
#                             By.CLASS_NAME,
#                             "market-financial-table__title"
#                         ).text.strip()
#                         row_value = row.find_element(
#                             By.CLASS_NAME,
#                             "market-financial-table__text"
#                         ).text.strip()
#                         row_change = row.find_element(
#                             By.CLASS_NAME,
#                             "market-financial-table__change"
#                         ).text.strip()
#
#                         stats[f"{row_title} Value"] = row_value
#                         stats[f"{row_title} Change"] = row_change
#                     except Exception as e:
#                         print(f"Brak pełnych danych finansowych w wierszu dla spółki {symbol}.")
#                         print(e)
#             except Exception as e:
#                 print(f"Brak danych finansowych dla spółki {symbol}.")
#                 print(e)
#
#             # 9. Dodaj identyfikator spółki
#             stats["Stock"] = symbol
#
#             # 10. Analyst Ratings
#             try:
#                 time.sleep(1)
#                 number_of_analysts = wait.until(
#                     EC.presence_of_element_located(
#                         (By.CLASS_NAME, "markets-donut-chart__title")
#                     )
#                 ).text
#                 stats["Number of analysts"] = number_of_analysts
#             except Exception as e:
#                 stats["Number of analysts"] = float('nan')
#                 print(f"Brak danych o liczbie analityków dla spółki {symbol}.")
#                 print(e)
#
#             # Przetwarzanie rekomendacji
#             recommendation_columns = ["Buy Recommendation", "Hold Recommendation", "Sell Recommendation"]
#             for recommendation in recommendation_columns:
#                 try:
#                     key = recommendation.split()[0].lower()
#                     recommendation_text = wait.until(
#                         EC.presence_of_element_located(
#                             (By.ID, f"markets-donut-chart__legend--key-value-{key}")
#                         )
#                     ).text
#                     stats[recommendation] = recommendation_text
#                 except Exception as e:
#                     stats[recommendation] = float('nan')
#                     print(f"Brak danych o rekomendacji {recommendation} dla spółki {symbol}.")
#                     print(e)
#
#             # 11. Forecast (High/Median/Low)
#             try:
#                 driver.execute_script("window.scrollTo(0, 2500);")
#                 time.sleep(1)
#                 forecast_chart_section = wait.until(
#                     EC.presence_of_element_located(
#                         (By.CSS_SELECTOR, "div.markets-forecast-chart")
#                     )
#                 )
#                 svg_element = forecast_chart_section.find_element(By.CSS_SELECTOR, "svg")
#
#                 # High Forecast
#                 try:
#                     high_data_g = svg_element.find_element(By.CSS_SELECTOR, "g.high-data")
#                     high_price_tspans = high_data_g.find_elements(
#                         By.CSS_SELECTOR,
#                         "text.high-price tspan"
#                     )
#                     if len(high_price_tspans) >= 2:
#                         stats["High Forecast"] = high_price_tspans[1].text.strip()
#                     else:
#                         stats["High Forecast"] = float('nan')
#                 except:
#                     stats["High Forecast"] = float('nan')
#
#                 # Median Forecast
#                 try:
#                     median_data_g = svg_element.find_element(By.CSS_SELECTOR, "g.median-data")
#                     median_price_tspans = median_data_g.find_elements(
#                         By.CSS_SELECTOR,
#                         "text.median-price tspan"
#                     )
#                     if len(median_price_tspans) >= 2:
#                         stats["Median Forecast"] = median_price_tspans[1].text.strip()
#                     else:
#                         stats["Median Forecast"] = float('nan')
#                 except:
#                     stats["Median Forecast"] = float('nan')
#
#                 # Low Forecast
#                 try:
#                     low_data_g = svg_element.find_element(By.CSS_SELECTOR, "g.low-data")
#                     low_price_tspans = low_data_g.find_elements(
#                         By.CSS_SELECTOR,
#                         "text.median-price tspan"
#                     )
#                     if len(low_price_tspans) >= 2:
#                         stats["Low Forecast"] = low_price_tspans[1].text.strip()
#                     else:
#                         stats["Low Forecast"] = float('nan')
#                 except:
#                     stats["Low Forecast"] = float('nan')
#
#             except Exception as e:
#                 print(f"Brak danych forecast dla spółki {symbol}.")
#                 print(e)
#                 stats["High Forecast"] = float('nan')
#                 stats["Median Forecast"] = float('nan')
#                 stats["Low Forecast"] = float('nan')
#
#             # Dodaj do listy all_data
#             all_data.append(stats)
#
#         except Exception as e:
#             print(f"Wystąpił błąd podczas przetwarzania spółki {symbol}.")
#             new_drops.append(symbol)  # Dodaj symbol do new_drops zamiast do drops
#             print(f"Dopisano spółkę {symbol} do listy ponownego przetworzenia.")
#             print(e)
#             print("-" * 57)
#
#     # Zamknij driver po zakończeniu pętli
#     driver.quit()
#
#     # Tworzymy DataFrame z listy słowników
#     df = pd.DataFrame(all_data)
#
#     #  # Pobieranie aktualnego czasu UTC
#     # current_time = datetime.now(timezone.utc)
#     #
#     # # Wyodrębnienie daty i godziny
#     # hour_timestamp = current_time.strftime("%H:%M:%S UTC")
#     # date_timestamp = current_time.strftime("%Y-%m-%d")
#
#     # Dodanie kolumn do DataFrame
#     df["Time of record"] = hour_timestamp
#     df["Date of record"] = date_timestamp
#
#     return df, new_drops  # Zwracamy zarówno DataFrame, jak i nową listę drops


# def retry_drops(drops):
#     """
#     Funkcja, która iteruje po spółkach z listy 'drops',
#     próbuje ponownie pobrać dane i zwraca DataFrame oraz nową listę 'drops'.
#     Zaktualizowana wersja korzysta z nowych selektorów HTML.
#     """
#     all_data = []   # Przechowuje dane każdej spółki
#     new_drops = []  # Przechowuje spółki, które nadal napotykają błędy
#
#     # Konfiguracja Selenium (otwieramy przeglądarkę na czas procesu)
#     service = Service(driver_path)
#     driver = webdriver.Chrome(service=service)
#     wait = WebDriverWait(driver, 30)
#
#     for index, symbol in enumerate(drops, start=1):
#         # Znajdź URL odpowiadający symbolowi
#         try:
#             url = next(url for url in stocks if url.split("/")[-1] == symbol)
#         except StopIteration:
#             print(f"URL dla symbolu {symbol} nie został znaleziony w liście 'stocks'.")
#             new_drops.append(symbol)
#             continue
#
#         print(f"Ponowna próba pobierania spółki {index}/{len(drops)}: {symbol}")
#         stats = {}
#         try:
#             # Mierzenie czasu ładowania strony
#             start_time = time.time()
#             driver.get(url)
#             end_time = time.time()
#             load_time = end_time - start_time
#             print(f"Czas ładowania strony {symbol}: {load_time:.2f} sekund")
#             time.sleep(1)
#
#             # Akceptacja plików cookies tylko przy pierwszej iteracji
#             if index == 1:
#                 try:
#                     accept_cookies_button = WebDriverWait(driver, 10).until(
#                         EC.element_to_be_clickable((By.ID, "onetrust-accept-btn-handler"))
#                     )
#                     accept_cookies_button.click()
#                     time.sleep(1)
#                 except:
#                     print("Nie znaleziono/nie kliknięto przycisku accept cookies. "
#                           "Może baner się nie pojawił albo selektor jest błędny.")
#
#             # Czekamy na dynamiczne elementy – aktualnie oczekujemy elementu ceny
#             try:
#                 dynamic_element_wait_start = time.time()
#                 WebDriverWait(driver, 10).until(
#                     EC.presence_of_element_located(
#                         (By.CSS_SELECTOR, ".price-2tP9m2.cnn-pcl-kld3m4")
#                     )
#                 )
#                 dynamic_element_wait_end = time.time()
#                 dynamic_load_time = dynamic_element_wait_end - dynamic_element_wait_start
#                 print(f"Czas oczekiwania na dynamiczne elementy {symbol}: {dynamic_load_time:.2f} sekund")
#                 print("-" * 57)
#             except Exception as e:
#                 print(f"Dynamiczne elementy strony {symbol} nie załadowały się w wyznaczonym czasie.")
#                 dynamic_load_time = float('nan')
#                 print(f"Łączny czas oczekiwania {symbol}: {load_time + (dynamic_load_time if not pd.isna(dynamic_load_time) else 0):.2f} sekund")
#                 print("-" * 57)
#
#             stats["Page Load Time (s)"] = round(load_time, 2)
#             stats["Dynamic Element Load Time (s)"] = round(dynamic_load_time, 2)
#
#             # 1. Cena akcji
#             try:
#                 price_element = driver.find_element(By.CSS_SELECTOR, ".price-2tP9m2.cnn-pcl-kld3m4")
#                 price = price_element.text
#             except NoSuchElementException:
#                 try:
#                     price_element = driver.find_element(By.CSS_SELECTOR,
#                                                         ".price-data-2LZZ5_ .pricing-container-3_SSKi .price-2kQQGw")
#                     price = price_element.text
#                 except NoSuchElementException:
#                     print("Nie udało się znaleźć elementu z ceną")
#                     price = None
#             stats["Price"] = price
#
#             # 2. Zmiana ceny (używamy nowego selektora – niezależnie czy zmiana jest dodatnia czy ujemna)
#             change_element = driver.find_element(
#                 By.CSS_SELECTOR,
#                 "div.sub-price-2Q-2oW.cnn-pcl-kld3m4.up-2TzyoG:not(.percent-2vLQBV)"
#             )
#             change = change_element.text
#             stats["Change"] = change
#
#             # 3. Zmiana procentowa
#             percent_change_element = driver.find_element(
#                 By.CSS_SELECTOR,
#                 "div.sub-price-2Q-2oW.percent-2vLQBV.cnn-pcl-kld3m4.up-2TzyoG"
#             )
#             percent_change = percent_change_element.text
#             stats["Percent Change"] = percent_change
#
#             # try:
#             #     # ------------------------------
#             #     # 1. Zmiana ceny (bez procenta)
#             #     # ------------------------------
#             #     change_element = driver.find_element(
#             #         By.CSS_SELECTOR,
#             #         "div.sub-price-2Q-2oW.cnn-pcl-kld3m4:not(.percent-2vLQBV)"
#             #         # wychwytuje .sub-price..., ale nie .percent-2vLQBV
#             #     )
#             #     change_text = change_element.text.strip()
#             #     stats["Change"] = change_text
#             #
#             #     print(f">>>> Zmiana (od ostatniego zamknięcia) = {change_text}")
#             #
#             #     # ------------------------------
#             #     # 2. Zmiana procentowa
#             #     # ------------------------------
#             #     percent_element = driver.find_element(
#             #         By.CSS_SELECTOR,
#             #         "div.sub-price-2Q-2oW.percent-2vLQBV.cnn-pcl-kld3m4"
#             #         # wychwytuje .sub-price... + .percent-2vLQBV
#             #     )
#             #     percent_text = percent_element.text.strip()
#             #     stats["Percent Change"] = percent_text
#             #
#             #     print(f">>>> Zmiana procentowa (od ostatniego zamknięcia) = {percent_text}")
#             #
#             # except Exception as e:
#             #     print("Błąd podczas pobierania zmiany ceny i/lub zmiany procentowej:", e)
#
#
#
#             # # 2. Zmiana ceny (bez procenta):
#             # change_element = driver.find_element(
#             #     By.CSS_SELECTOR,
#             #     "div.sub-price-2Q-2oW.cnn-pcl-kld3m4:not(.percent-2vLQBV)"
#             # )
#             # change = change_element.text.strip()
#             # stats["Change"] = change
#             #
#             # # 3. Zmiana procentowa:
#             # percent_change_element = driver.find_element(
#             #     By.CSS_SELECTOR,
#             #     "div.sub-price-2Q-2oW.percent-2vLQBV.cnn-pcl-kld3m4"
#             # )
#             # percent_change = percent_change_element.text.strip()
#             # stats["Percent Change"] = percent_change
#             # print(f"Znaleziono Percent Change: {percent_change:.2f}")
#
#             # 4. Data sesji
#             # session_date_element = driver.find_element(
#             #     By.CSS_SELECTOR,
#             #     "div.timestamp-2067hl.cnn-pcl-kld3m4"
#             # )
#             session_date_element = driver.find_element(
#                 By.CSS_SELECTOR,
#                 ".range-description-pp_d8h.cnn-pcl-12tjup5"
#             ) #update 16.07.2025
#             session_date = session_date_element.text
#             stats["Session Date"] = session_date
#
#             # 5. Cena po zamknięciu (jeśli sesja jest już zamknięta)
#             try:
#                 closing_price_element = driver.find_element(
#                     By.CSS_SELECTOR,
#                     ".pricing-container-3_SSKi.secondary-160A5Y .price-2kQQGw.secondary-160A5Y.cnn-pcl-eltrz4"
#                 )
#                 closing_price = closing_price_element.text
#             except NoSuchElementException:
#                 closing_price = price
#             stats["Closing Price"] = closing_price
#
#             # --------------------------
#             # 12. Pobieranie danych dla wybranych przedziałów czasowych
#             # --------------------------
#             time_range_data = {}
#             try:
#                 range_list = wait.until(
#                     EC.presence_of_element_located(
#                         (By.CSS_SELECTOR, "div.range-list-1UVUW0.cnn-pcl-kld3m4")
#                     )
#                 )
#                 time_buttons = range_list.find_elements(By.TAG_NAME, "button")
#             except Exception as e:
#                 print(f"Nie udało się pobrać przycisków przedziałów czasowych dla {symbol}: {e}")
#                 time_buttons = []
#
#             for button in time_buttons:
#                 time_range = button.text.strip()
#                 print(f"  Przetwarzam przedział {symbol}: {time_range}")
#                 try:
#                     driver.execute_script("arguments[0].scrollIntoView({block: 'center'});", button)
#                     time.sleep(0.5)
#                     button.click()
#                     time.sleep(2)
#                     sub_price_element = wait.until(
#                         EC.visibility_of_element_located(
#                             (By.CSS_SELECTOR, "div.sub-price-2Q-2oW.cnn-pcl-kld3m4:not(.percent-2vLQBV)")
#                         )
#                     )
#                     sub_price = sub_price_element.text.strip()
#                     percent_element = wait.until(
#                         EC.visibility_of_element_located(
#                             (By.CSS_SELECTOR, "div.sub-price-2Q-2oW.percent-2vLQBV.cnn-pcl-kld3m4")
#                         )
#                     )
#                     percent_range = percent_element.text.strip()
#                     time_range_data[time_range] = {"sub_price": sub_price, "percent_change": percent_range}
#                     print(f"    {time_range} -> Różnica ceny {symbol}: {sub_price}, Różnica %: {percent_range}")
#                 except Exception as e:
#                     print(f"    Problem z pobraniem danych dla {time_range} w spółce {symbol}: {e}")
#
#             # Rozpakowywanie danych z zakresów do słownika stats
#             for time_range, values in time_range_data.items():
#                 stats[f"{time_range}-sub_price"] = values.get("sub_price", None)
#                 stats[f"{time_range}-percent_change"] = values.get("percent_change", None)
#
#             # 6. Key stock statistics (aktualizacja selektorów)
#             keys = driver.find_elements(By.CLASS_NAME, "markets-keyfacts__label-2ArNJP")
#             values = driver.find_elements(By.CLASS_NAME, "markets-keyfacts__value-1fAhI5")
#             for key, value in zip(keys, values):
#                 key_text = key.text.strip()
#                 value_text = value.text.strip()
#                 stats[key_text] = value_text
#                 print(f"Key: {key_text} -> Value: {value_text}")
#
#             # 7. Smart Score z iframe TipRanks
#             # try:
#             #     iframe = driver.find_element(By.CSS_SELECTOR, "iframe[src*='tipranks']")
#             #     driver.switch_to.frame(iframe)
#             #     smart_score_container = driver.find_element(By.CSS_SELECTOR, "div.sc-jBIHhB.bqMmLN")
#             #     smart_score_element = smart_score_container.find_element(By.TAG_NAME, "text")
#             #     smart_score = smart_score_element.text
#             #     stats["Smart Score"] = smart_score
#             # except Exception as iframe_error:
#             #     stats["Smart Score"] = None
#             # finally:
#             #     driver.switch_to.default_content()
#
#             # try:
#             #     print("Próba znalezienia iframe TipRanks...")
#             #     iframe = driver.find_element(By.CSS_SELECTOR, "iframe[src*='tipranks']")
#             #     print("Znaleziono iframe. Przełączam się do niego.")
#             #     driver.switch_to.frame(iframe)
#             #
#             #     # Dajemy czas, aby widget TipRanks zdążył się wczytać (React/JS).
#             #     time.sleep(1)
#             #
#             #     # Szukamy diva sc-jMsorb, który nie ma klasy 'hitpXG' – to właśnie aktywny Smart Score
#             #     print("Szukam elementu div.sc-jMsorb, który nie ma klasy 'hitpXG' (aktywny Smart Score)...")
#             #     active_score_div = driver.find_element(
#             #         By.CSS_SELECTOR,
#             #         "div.sc-jMsorb:not(.hitpXG)"
#             #     )
#             #
#             #     # We wnetrzu powyższego diva jest <text class="sc-cXawGu ...">X</text>
#             #     score_text_el = active_score_div.find_element(By.CSS_SELECTOR, "text.sc-cXawGu")
#             #     smart_score = score_text_el.get_attribute("textContent").strip()
#             #
#             #     print(f"Znaleziono Smart Score: {smart_score}")
#             #     stats["Smart Score"] = smart_score
#             #
#             # except Exception as iframe_error:
#             #     print("Wystąpił błąd podczas pobierania Smart Score z iframe:")
#             #     print(iframe_error)
#             #     stats["Smart Score"] = None
#             #
#             # finally:
#             #     print("Powrót do kontekstu głównego (default_content).")
#             #     driver.switch_to.default_content()
#
#             # # 7. Smart Score z iframe TipRanks – aktualizacja 30-04-2025
#             # try:
#             #     print("Próba znalezienia iframe TipRanks...")
#             #     iframe = driver.find_element(By.CSS_SELECTOR, "iframe[src*='tipranks']")
#             #     driver.switch_to.frame(iframe)
#             #
#             #     # czekamy aż w iframe pojawi się div z class="value current-value"
#             #     wait.until(
#             #         EC.presence_of_element_located(
#             #             (By.CSS_SELECTOR, "div.value.current-value .text-val.is-value")
#             #         )
#             #     )
#             #
#             #     score_el = driver.find_element(
#             #         By.CSS_SELECTOR,
#             #         "div.value.current-value .text-val.is-value"
#             #     )
#             #
#             #     smart_score = score_el.text.strip()
#             #     print(f"Znaleziono Smart Score: {smart_score}")
#             #     stats["Smart Score"] = smart_score
#             #
#             # except Exception as e:
#             #     print("Wystąpił błąd podczas pobierania Smart Score z iframe:")
#             #     print(e)
#             #     stats["Smart Score"] = None
#             #
#             # finally:
#             #     driver.switch_to.default_content()
#
#             # # 7. Smart Score z iframe TipRanks  – wersja odporna na zmiany layoutu (retry_drops) - update 24.06.2025
#             # try:
#             #     print("Próba znalezienia iframe TipRanks (retry)…")
#             #     iframe = driver.find_element(By.CSS_SELECTOR, "iframe[src*='tipranks']")
#             #     driver.switch_to.frame(iframe)
#             #
#             #     # poczekaj, aż w iframe pojawi się kontener z kafelkami Smart Score
#             #     wait.until(
#             #         EC.presence_of_element_located(
#             #             (By.CSS_SELECTOR, "div[class^='sc-hwkwBN']")
#             #         )
#             #     )
#             #
#             #     smart_score = extract_smart_score(driver)  # <-- uniwersalna funkcja
#             #     print(f"Znaleziono Smart Score (retry): {smart_score}")
#             #     stats["Smart Score"] = smart_score
#             #
#             # except Exception as e:
#             #     print("Błąd przy pobieraniu Smart Score w retry:", e)
#             #     stats["Smart Score"] = None
#             #
#             # finally:
#             #     driver.switch_to.default_content()
#
#             # 7. Smart Score z iframe TipRanks – wersja odporna na nowy layout (performanceRange) - update 08.09.2025
#             try:
#                 print("Próba znalezienia iframe TipRanks…")
#                 # Poczekaj aż iframe będzie dostępny i przewiń do niego, żeby wymusić załadowanie
#                 iframe = wait.until(EC.presence_of_element_located((By.CSS_SELECTOR, "iframe[src*='tipranks']")))
#                 driver.execute_script("arguments[0].scrollIntoView({block: 'center'});", iframe)
#                 time.sleep(0.3)
#
#                 # Pewne przełączenie: czekamy aż rama będzie gotowa i od razu się przełączamy
#                 wait.until(EC.frame_to_be_available_and_switch_to_it(iframe))
#
#                 # Czekamy na dowolny z charakterystycznych elementów nowego/starego layoutu
#                 def _any_ready(drv):
#                     return (
#                             drv.find_elements(By.CSS_SELECTOR, "div.performanceRange") or
#                             drv.find_elements(By.CSS_SELECTOR,
#                                               "div.value.current-value .text-val, div.value.current-value text") or
#                             drv.find_elements(By.CSS_SELECTOR, "text.text-val.is-value")
#                     )
#
#                 WebDriverWait(driver, 10).until(_any_ready)
#
#                 smart_score = extract_smart_score(driver)
#                 print(f"Znaleziono Smart Score: {smart_score}")
#                 stats["Smart Score"] = smart_score
#
#             except Exception as e:
#                 print("Wystąpił błąd podczas pobierania Smart Score z iframe:", e)
#                 stats["Smart Score"] = None
#
#             finally:
#                 # ZAWSZE wróć do kontekstu głównego
#                 try:
#                     driver.switch_to.default_content()
#                 except Exception:
#                     pass
#
#             # 8. Dane finansowe (Revenue, Net Income, itp.)
#             try:
#                 financial_rows = driver.find_elements(By.CLASS_NAME, "market-financial-table__row-153LbB")
#                 for row in financial_rows:
#                     try:
#                         row_title = row.find_element(By.CLASS_NAME, "market-financial-table__title").text.strip()
#                         row_value = row.find_element(By.CLASS_NAME, "market-financial-table__text").text.strip()
#                         row_change = row.find_element(By.CLASS_NAME, "market-financial-table__change").text.strip()
#                         stats[f"{row_title} Value"] = row_value
#                         stats[f"{row_title} Change"] = row_change
#                     except Exception as e:
#                         print(f"Brak pełnych danych finansowych w wierszu dla spółki {symbol}.")
#                         print(e)
#             except Exception as e:
#                 print(f"Brak danych finansowych dla spółki {symbol}.")
#                 print(e)
#
#             stats["Stock"] = symbol
#
#             # 10. Analyst Ratings
#             try:
#                 time.sleep(1)
#                 number_of_analysts = wait.until(
#                     EC.presence_of_element_located((By.CLASS_NAME, "markets-donut-chart__title"))
#                 ).text
#                 stats["Number of analysts"] = number_of_analysts
#             except Exception as e:
#                 stats["Number of analysts"] = float('nan')
#                 print(f"Brak danych o liczbie analityków dla spółki {symbol}.")
#                 print(e)
#
#             recommendation_columns = ["Buy Recommendation", "Hold Recommendation", "Sell Recommendation"]
#             for recommendation in recommendation_columns:
#                 try:
#                     key_rec = recommendation.split()[0].lower()
#                     rec_text = wait.until(
#                         EC.presence_of_element_located((By.ID, f"markets-donut-chart__legend--key-value-{key_rec}"))
#                     ).text
#                     stats[recommendation] = rec_text
#                 except Exception as e:
#                     stats[recommendation] = float('nan')
#                     print(f"Brak danych o rekomendacji {recommendation} dla spółki {symbol}.")
#                     print(e)
#
#             # 11. Forecast (High/Median/Low)
#             driver.execute_script("window.scrollTo(0, 2500);")
#             time.sleep(1)
#             forecast_chart_section = wait.until(
#                 EC.presence_of_element_located((By.CSS_SELECTOR, "div.markets-forecast-chart"))
#             )
#             svg_element = forecast_chart_section.find_element(By.CSS_SELECTOR, "svg")
#             try:
#                 high_data_g = svg_element.find_element(By.CSS_SELECTOR, "g.high-data")
#                 high_price_tspans = high_data_g.find_elements(By.CSS_SELECTOR, "text.high-price tspan")
#                 if len(high_price_tspans) >= 2:
#                     stats["High Forecast"] = high_price_tspans[1].text.strip()
#                 else:
#                     stats["High Forecast"] = float('nan')
#             except:
#                 stats["High Forecast"] = float('nan')
#             try:
#                 median_data_g = svg_element.find_element(By.CSS_SELECTOR, "g.median-data")
#                 median_price_tspans = median_data_g.find_elements(By.CSS_SELECTOR, "text.median-price tspan")
#                 if len(median_price_tspans) >= 2:
#                     stats["Median Forecast"] = median_price_tspans[1].text.strip()
#                 else:
#                     stats["Median Forecast"] = float('nan')
#             except:
#                 stats["Median Forecast"] = float('nan')
#             try:
#                 low_data_g = svg_element.find_element(By.CSS_SELECTOR, "g.low-data")
#                 low_price_tspans = low_data_g.find_elements(By.CSS_SELECTOR, "text.median-price tspan")
#                 if len(low_price_tspans) >= 2:
#                     stats["Low Forecast"] = low_price_tspans[1].text.strip()
#                 else:
#                     stats["Low Forecast"] = float('nan')
#             except:
#                 stats["Low Forecast"] = float('nan')
#
#             all_data.append(stats)
#
#         except Exception as e:
#             print(f"Wystąpił błąd podczas przetwarzania spółki {symbol}.")
#             new_drops.append(symbol)
#             print(f"Dopisano spółkę {symbol} do listy ponownego przetworzenia.")
#             print(e)
#             print("-" * 57)
#
#     driver.quit()
#
#     df = pd.DataFrame(all_data)
#     df["Time of record"] = hour_timestamp
#     df["Date of record"] = date_timestamp
#
#     return df, new_drops


# zaktualizowana funkcja retry drops 08.09.2025
def retry_drops(drops):
    """
    Retry dla spółek z listy 'drops' – wersja zsynchronizowana z scrape_data.
    Używa aktualnych selektorów i bezpiecznych waitów.
    """
    all_data = []
    new_drops = []

    service = Service(driver_path)
    driver = webdriver.Chrome(service=service)
    wait = WebDriverWait(driver, 30)

    # (opcjonalnie) zrób OR na dwa możliwe layouty listy zakresów
    RANGE_LIST_ANY = "div.range-list-CNwGAc.cnn-pcl-12tjup5, div.range-list-1UVUW0.cnn-pcl-kld3m4"

    for index, symbol in enumerate(drops, start=1):
        try:
            url = next(u for u in stocks if u.split("/")[-1] == symbol)
        except StopIteration:
            print(f"URL dla symbolu {symbol} nie został znaleziony w liście 'stocks'.")
            new_drops.append(symbol)
            continue

        print(f"Ponowna próba pobierania spółki {index}/{len(drops)}: {symbol}")
        stats = {}

        try:
            t0 = time.time()
            driver.get(url)
            load_time = time.time() - t0
            print(f"Czas ładowania strony {symbol}: {load_time:.2f} sekund")
            time.sleep(0.5)

            # cookies tylko raz
            if index == 1:
                try:
                    btn = WebDriverWait(driver, 10).until(
                        EC.element_to_be_clickable((By.ID, "onetrust-accept-btn-handler"))
                    )
                    btn.click()
                    time.sleep(0.3)
                except Exception:
                    pass

            # kluczowy element strony (użyj tych samych selektorów co w scrape_data)
            try:
                t1 = time.time()
                WebDriverWait(driver, 12).until(
                    EC.presence_of_element_located((By.CSS_SELECTOR, SEL_WAIT_FOR_PAGE))
                )
                dyn_time = time.time() - t1
            except Exception:
                dyn_time = float('nan')

            stats["Page Load Time (s)"] = round(load_time, 2)
            stats["Dynamic Element Load Time (s)"] = round(dyn_time, 2)

            # --- PRICE ---
            price = None
            try:
                price = driver.find_element(By.CSS_SELECTOR, SEL_PRICE).text
            except NoSuchElementException:
                # stary fallback (może już rzadko, ale niech zostanie)
                try:
                    price = driver.find_element(
                        By.CSS_SELECTOR,
                        ".price-data-2LZZ5_ .pricing-container-3_SSKi .price-2kQQGw"
                    ).text
                except NoSuchElementException:
                    print("Nie udało się znaleźć elementu z ceną")

            stats["Price"] = price

            # --- CHANGE & PERCENT CHANGE (nowe klasy + waity) ---
            try:
                change_el = WebDriverWait(driver, 5).until(
                    EC.presence_of_element_located((By.CSS_SELECTOR, SEL_CHANGE))
                )
                change_text = change_el.text.strip()
                stats["Change"] = change_text

                percent_el = WebDriverWait(driver, 5).until(
                    EC.presence_of_element_located((By.CSS_SELECTOR, SEL_PERCENT_CHANGE))
                )
                percent_text = percent_el.text.strip()
                stats["Percent Change"] = percent_text
            except Exception as e:
                print("Błąd podczas pobierania Change/Percent Change:", e)
                stats["Change"] = None
                stats["Percent Change"] = None

            # --- SESSION DATE ---
            try:
                session_date = driver.find_element(By.CSS_SELECTOR, SEL_SESSION_DATE).text
            except Exception:
                session_date = None
            stats["Session Date"] = session_date

            # --- CLOSING PRICE ---
            try:
                closing_price = driver.find_element(
                    By.CSS_SELECTOR,
                    ".pricing-container-3_SSKi.secondary-160A5Y .price-2kQQGw.secondary-160A5Y.cnn-pcl-eltrz4"
                ).text
            except NoSuchElementException:
                closing_price = price
            stats["Closing Price"] = closing_price

            # --- TIME RANGES ---
            time_range_data = {}
            try:
                range_list = wait.until(
                    EC.presence_of_element_located((By.CSS_SELECTOR, RANGE_LIST_ANY))
                )
                time_buttons = range_list.find_elements(By.TAG_NAME, "button")
            except Exception as e:
                print(f"Nie udało się pobrać przycisków przedziałów czasowych dla {symbol}: {e}")
                time_buttons = []

            for btn in time_buttons:
                tr = btn.text.strip()
                if not tr:
                    continue
                print(f"  Przetwarzam przedział {symbol}: {tr}")
                try:
                    driver.execute_script("arguments[0].scrollIntoView({block: 'center'});", btn)
                    time.sleep(0.2)
                    btn.click()
                    time.sleep(0.8)

                    sub_price_el = wait.until(
                        EC.visibility_of_element_located(
                            (By.CSS_SELECTOR, "div.sub-price-1GODCI.cnn-pcl-12tjup5:not(.percent-2qdeCV)")
                        )
                    )
                    sub_price = sub_price_el.text.strip()

                    percent_el = wait.until(
                        EC.visibility_of_element_located(
                            (By.CSS_SELECTOR, "div.sub-price-1GODCI.percent-2qdeCV.cnn-pcl-12tjup5")
                        )
                    )
                    percent_change = percent_el.text.strip()

                    time_range_data[tr] = {"sub_price": sub_price, "percent_change": percent_change}
                    print(f"    {tr} -> Różnica ceny {symbol}: {sub_price}, Różnica %: {percent_change}")
                except Exception as e:
                    print(f"    Problem z pobraniem danych dla {tr} ({symbol}): {e}")

            for tr, vals in time_range_data.items():
                stats[f"{tr}-sub_price"] = vals.get("sub_price")
                stats[f"{tr}-percent_change"] = vals.get("percent_change")

            # --- KEY FACTS ---
            keys = driver.find_elements(By.CLASS_NAME, "markets-keyfacts__label-2ArNJP")
            vals = driver.find_elements(By.CLASS_NAME, "markets-keyfacts__value-1fAhI5")
            for k, v in zip(keys, vals):
                stats[k.text.strip()] = v.text.strip()

            # --- SMART SCORE (ta sama wersja co w scrape_data) ---
            try:
                print("Próba znalezienia iframe TipRanks…")
                iframe = wait.until(EC.presence_of_element_located((By.CSS_SELECTOR, "iframe[src*='tipranks']")))
                driver.execute_script("arguments[0].scrollIntoView({block: 'center'});", iframe)
                time.sleep(0.2)
                wait.until(EC.frame_to_be_available_and_switch_to_it(iframe))

                def _any_ready(drv):
                    return (
                        drv.find_elements(By.CSS_SELECTOR, "div.performanceRange") or
                        drv.find_elements(By.CSS_SELECTOR, "div.value.current-value .text-val, div.value.current-value text") or
                        drv.find_elements(By.CSS_SELECTOR, "text.text-val.is-value")
                    )

                WebDriverWait(driver, 10).until(_any_ready)
                smart_score = extract_smart_score(driver)
                stats["Smart Score"] = smart_score
            except Exception as e:
                print("Wystąpił błąd podczas pobierania Smart Score z iframe:", e)
                stats["Smart Score"] = None
            finally:
                try:
                    driver.switch_to.default_content()
                except Exception:
                    pass

            # --- FINANCIALS ---
            try:
                rows = driver.find_elements(By.CLASS_NAME, "market-financial-table__row-153LbB")
                for row in rows:
                    try:
                        rt = row.find_element(By.CLASS_NAME, "market-financial-table__title").text.strip()
                        rv = row.find_element(By.CLASS_NAME, "market-financial-table__text").text.strip()
                        rc = row.find_element(By.CLASS_NAME, "market-financial-table__change").text.strip()
                        stats[f"{rt} Value"] = rv
                        stats[f"{rt} Change"] = rc
                    except Exception:
                        pass
            except Exception:
                pass

            # --- ANALYSTS ---
            try:
                number_of_analysts = wait.until(
                    EC.presence_of_element_located((By.CLASS_NAME, "markets-donut-chart__title"))
                ).text
                stats["Number of analysts"] = number_of_analysts
            except Exception:
                stats["Number of analysts"] = None

            for rec_key in ["buy", "hold", "sell"]:
                try:
                    val = wait.until(
                        EC.presence_of_element_located(
                            (By.ID, f"markets-donut-chart__legend--key-value-{rec_key}")
                        )
                    ).text
                except Exception:
                    val = None
                label = {"buy": "Buy Recommendation", "hold": "Hold Recommendation", "sell": "Sell Recommendation"}[rec_key]
                stats[label] = val

            # --- FORECAST ---
            try:
                driver.execute_script("window.scrollTo(0, 2500);")
                time.sleep(0.8)
                fc = wait.until(EC.presence_of_element_located((By.CSS_SELECTOR, "div.markets-forecast-chart")))
                svg = fc.find_element(By.CSS_SELECTOR, "svg")

                # High
                try:
                    ts = svg.find_element(By.CSS_SELECTOR, "g.high-data").find_elements(By.CSS_SELECTOR, "text.high-price tspan")
                    stats["High Forecast"] = ts[1].text.strip() if len(ts) >= 2 else None
                except Exception:
                    stats["High Forecast"] = None
                # Median
                try:
                    ts = svg.find_element(By.CSS_SELECTOR, "g.median-data").find_elements(By.CSS_SELECTOR, "text.median-price tspan")
                    stats["Median Forecast"] = ts[1].text.strip() if len(ts) >= 2 else None
                except Exception:
                    stats["Median Forecast"] = None
                # Low
                try:
                    ts = svg.find_element(By.CSS_SELECTOR, "g.low-data").find_elements(By.CSS_SELECTOR, "text.median-price tspan")
                    stats["Low Forecast"] = ts[1].text.strip() if len(ts) >= 2 else None
                except Exception:
                    stats["Low Forecast"] = None
            except Exception:
                stats["High Forecast"] = None
                stats["Median Forecast"] = None
                stats["Low Forecast"] = None

            stats["Stock"] = symbol
            all_data.append(stats)

        except Exception as e:
            print(f"Wystąpił błąd podczas przetwarzania spółki {symbol}.")
            new_drops.append(symbol)
            print(f"Dopisano spółkę {symbol} do listy ponownego przetworzenia.")
            print(e)
            print("-" * 57)

    driver.quit()

    df = pd.DataFrame(all_data)
    df["Time of record"] = hour_timestamp
    df["Date of record"] = date_timestamp

    return df, new_drops




def clean_data(df):
    """
    Funkcja czyszcząca dane w DataFrame.

    Parametry:
    - df (pd.DataFrame): DataFrame zawierający dane do wyczyszczenia.

    Zwraca:
    - pd.DataFrame: Oczyszczony DataFrame.
    """

    # 1. Obróbka kolumny "Percent Change"
    if "Percent Change" in df.columns:
        df["Percent Change"] = df["Percent Change"].str.replace("%", "", regex=False)
        df["Percent Change"] = pd.to_numeric(df["Percent Change"],
                                             errors='coerce')  # Konwertujemy na float z obsługą błędów
        # Dodanie znaku + lub - w zależności od kolumny "Change"
        if "Change" in df.columns:
            df["Percent Change"] = df["Percent Change"] * df["Change"].str.contains(r"\+", regex=True).map(
                {True: 1, False: -1})

    # 2. Ucięcie znaku "$" i zamiana na float w kolumnach "High Forecast", "Median Forecast", "Low Forecast"
    forecast_columns = ["High Forecast", "Median Forecast", "Low Forecast"]
    for col in forecast_columns:
        if col in df.columns:
            df[col] = (
                df[col]
                .str.replace('$', '', regex=False)  # Usuń znak dolara
                .str.replace(',', '', regex=False)  # Usuń przecinki
            )
            df[col] = pd.to_numeric(df[col], errors='coerce')  # Konwertuj na float z obsługą błędów

    # 3. Ucięcie znaku "%" i zamiana na float w kolumnach "Buy Recommendation", "Hold Recommendation", "Sell Recommendation"
    recommendation_columns = ["Buy Recommendation", "Hold Recommendation", "Sell Recommendation"]
    for col in recommendation_columns:
        if col in df.columns:
            df[col] = df[col].str.replace('%', '', regex=False)
            df[col] = pd.to_numeric(df[col],
                                    errors='coerce') / 100.0  # Konwertuj na float i przekształć na wartości procentowe

    # 4. Wycięcie tekstu " analyst ratings" z kolumny "Number of analysts" i zamiana na float
    if "Number of analysts" in df.columns:
        df["Number of analysts"] = df["Number of analysts"].str.extract(r'(\d+)')
        df["Number of analysts"] = pd.to_numeric(df["Number of analysts"],
                                                 errors='coerce')  # Konwertuj na float z obsługą błędów

    # 5. Scoring - zaawansowany algorytm
    if "Price" in df.columns:
        df["Price"] = df["Price"].str.replace(',', '', regex=False)
        df["Price"] = pd.to_numeric(df["Price"], errors='coerce')  # Konwertuj na float z obsługą błędów

    # 6. Usuń przecinki w kolumnie "Employees" i zamień na float
    if "Employees" in df.columns:
        df["Employees"] = df["Employees"].str.replace(",", "", regex=False)
        df["Employees"] = pd.to_numeric(df["Employees"], errors='coerce')  # Konwertuj na float z obsługą błędów

    # 7. Konwersja "Smart Score"
    if "Smart Score" in df.columns:
        df["Smart Score"] = pd.to_numeric(df["Smart Score"], errors='coerce')  # Konwertuj na float z obsługą błędów

    # 8. Calculate percentage growth for each forecast
    forecast_percent_columns = ["High Forecast Percent", "Median Forecast Percent", "Low Forecast Percent"]
    for forecast, percent_col in zip(forecast_columns, forecast_percent_columns):
        if forecast in df.columns and "Price" in df.columns:
            df[percent_col] = ((df[forecast] - df["Price"]) / df["Price"]) * 100
            df[percent_col] = pd.to_numeric(df[percent_col], errors='coerce')  # Konwertuj na float z obsługą błędów

    # 9. Ucięcie "x" z P/E ratio i konwersja na float
    if "P/E ratio" in df.columns:
        df["P/E ratio"] = df["P/E ratio"].astype(str).str.replace("x", "", regex=False)
        df["P/E ratio"] = pd.to_numeric(df["P/E ratio"], errors='coerce')  # Konwertuj na float z obsługą błędów

    # 10. Scoring - kontynuacja (po konwersji "Price")
    if "Price" in df.columns and "Score" not in df.columns:
        # Upewnij się, że wszystkie wymagane kolumny są dostępne
        required_cols = ["Low Forecast", "Median Forecast", "High Forecast",
                         "Buy Recommendation", "Sell Recommendation", "Number of analysts"]
        if all(col in df.columns for col in required_cols):
            df["Score"] = (
                    3 * ((df["Low Forecast"] / df["Price"]) - 1)
                    + 2 * ((df["Median Forecast"] / df["Price"]) - 1)
                    + 1 * ((df["High Forecast"] / df["Price"]) - 1)
                    + (df["Buy Recommendation"] - df["Sell Recommendation"])
                    + 0.02 * df["Number of analysts"]
            )
        else:
            df["Score"] = float('nan')  # Lub inna wartość domyślna

    # 11. Konwersja "Market cap" na "Market cap clear"
    if "Market cap" in df.columns:
        # Wyodrębnienie liczby i jednostki
        market_cap_split = df["Market cap"].str.extract(r'([\d\.]+)([TBM])')
        # Definicja mapowania jednostek
        multiplier = {'M': 1e6, 'B': 1e9, 'T': 1e12}
        # Przekształcenie na float z odpowiednim mnożnikiem
        df["Market cap clear"] = pd.to_numeric(market_cap_split[0], errors='coerce') * market_cap_split[1].map(
            multiplier)

    # 12. Konwersja "Dividend yield"
    if "Dividend yield" in df.columns:
        df["Dividend yield"] = df["Dividend yield"].str.replace('%', '', regex=False)
        df["Dividend yield"] = pd.to_numeric(df["Dividend yield"],
                                             errors='coerce')  # Konwertuj na float z obsługą błędów

    # 12. Konwersja dat
    date_columns = ["Ex-dividend date", "Dividend pay date"]
    for col in date_columns:
        if col in df.columns:
            df[col] = pd.to_datetime(df[col], errors='coerce').dt.strftime('%Y-%m-%d')

    # 13. Lista kolumn z cenami historycznymi, które chcemy oczyścić
    percent_cols = [
        '1d-percent_change',
        '5d-percent_change',
        '1m-percent_change',
        '6m-percent_change',
        'YTD-percent_change',
        '1y-percent_change',
        '5y-percent_change'
    ]

    for col in percent_cols:
        if col in df.columns:
            # 1. Usuwamy znak procenta
            df[col] = df[col].str.replace("%", "", regex=False)
            # 2. Usuwamy przecinki, aby liczba była w formacie odpowiednim dla konwersji (obsługa 1,064.62% itp)
            df[col] = df[col].str.replace(",", "", regex=False)
            # 3. Konwertujemy na typ numeryczny (float)
            df[col] = pd.to_numeric(df[col], errors='coerce')

            # 4. Dopasowanie znaku w oparciu o odpowiadającą kolumnę sub_price
            # Zakładamy, że kolumna z wartością zmiany ceny ma nazwę np. "1d-sub_price" dla kolumny "1d-percent_change"
            sub_price_col = col.replace("percent_change", "sub_price")
            if sub_price_col in df.columns:
                # Jeśli sub_price zawiera znak plus, pozostawiamy dodatnią wartość,
                # w przeciwnym wypadku zmieniamy na ujemną
                df[col] = df[col] * df[sub_price_col].str.contains(r"\+", regex=True).map({True: 1, False: -1})

    sub_price_cols = [
        '1d-sub_price',
        '5d-sub_price',
        '1m-sub_price',
        '6m-sub_price',
        'YTD-sub_price',
        '1y-sub_price',
        '5y-sub_price'
    ]

    for col in sub_price_cols:
        if col in df.columns:
            # Najpierw usuwamy zbędne spacje po znakach '+' lub '-' przy użyciu re.sub bez definiowania funkcji,
            # a potem konwertujemy wynik do float.
            df[col] = df[col].apply(lambda x: re.sub(r"([+-])\s+", r"\1", x.strip()) if isinstance(x, str) else x)
            df[col] = pd.to_numeric(df[col], errors='coerce')

    # --- Porządkowanie Kolejności Kolumn ---
    ordered_columns = [
        'Stock', 'Price', 'Change', 'Percent Change', 'Closing Price', 'Sector',
        'Industry', 'Employees', 'Founded', 'Website',
        '1-day range', '52-week range', 'Market cap', "Market cap clear", 'P/E ratio',
        'Next earnings date', 'Dividend yield', 'Ex-dividend date', 'Dividend pay date',
        'Number of analysts', 'Buy Recommendation', 'Hold Recommendation', 'Sell Recommendation',
        'Smart Score', 'Score', 'High Forecast', "High Forecast Percent",
        'Median Forecast', "Median Forecast Percent",
        'Low Forecast', "Low Forecast Percent",
        'Total revenue Value', 'Total revenue Change',
        'Net income Value', 'Net income Change',
        'Earnings per share Value', 'Earnings per share Change',
        'Net profit margin Value', 'Net profit margin Change',
        'Free cash flow Value', 'Free cash flow Change',
        'Debt-to-equity ratio Value', 'Debt-to-equity ratio Change',
        'Date of record', 'Time of record',
        "Page Load Time (s)", "Dynamic Element Load Time (s)", "Fear & Greed Index",
        '1d-sub_price', '1d-percent_change',
        '5d-sub_price', '5d-percent_change',
        '1m-sub_price', '1m-percent_change',
        '6m-sub_price', '6m-percent_change',
        'YTD-sub_price', 'YTD-percent_change',
        '1y-sub_price', '1y-percent_change',
        '5y-sub_price', '5y-percent_change',
        "Dow Index Value", "Dow Index Change", "Dow Index % Change",
        "S&P 500 Value", "S&P 500 Change", "S&P 500 % Change",
        "NASDAQ Value", "NASDAQ Change", "NASDAQ % Change"
    ]

    # Dostosowanie kolejności kolumn, jeśli istnieją
    existing_columns = [col for col in ordered_columns if col in df.columns]
    df = df[existing_columns]

    return df


def scrape_fear_greed_index(driver_path):
    # Inicjalizacja danych
    fgi_data = {
        "Fear & Greed Index": None,
        "FGI Time": None
    }

    try:
        # Konfiguracja Selenium
        service = Service(driver_path)
        options = webdriver.ChromeOptions()
        options.add_argument('--headless')  # Opcjonalnie: uruchomienie w trybie headless
        driver = webdriver.Chrome(service=service, options=options)
        wait = WebDriverWait(driver, 30)

        # Nawigacja do strony Fear & Greed Index
        url = "https://edition.cnn.com/markets/fear-and-greed"
        print(f"Naviguję do strony: {url}")
        driver.get(url)

        # Czekanie na załadowanie elementu z wartością Fear & Greed Index
        print("Czekam na załadowanie elementu z wartością Fear & Greed Index...")
        element = wait.until(
            EC.presence_of_element_located(
                (By.CLASS_NAME, "market-fng-gauge__dial-number-value")
            )
        )

        # Pobranie wartości
        fgi_value = element.text.strip()
        print(f"Znaleziono Fear & Greed Index: {fgi_value}")

        # Konwersja do liczby całkowitej
        try:
            fgi_value = int(fgi_value)
            fgi_data["Fear & Greed Index"] = fgi_value
        except ValueError:
            print(f"Nie udało się przekonwertować wartości FGI na int: '{fgi_value}'")

        # Pobranie aktualnego czasu UTC
        fgi_data["FGI Time"] = current_time.strftime("%Y-%m-%d %H:%M:%S UTC")
        print(f"FGI Time: {fgi_data['FGI Time']}")

    except Exception as e:
        print("Wystąpił błąd podczas pobierania Fear & Greed Index:")
        print(e)
    finally:
        # Zamknięcie przeglądarki
        driver.quit()

    return fgi_data


def scrape_market_indices(driver_path):
    # Przygotowujemy słownik na dane
    market_data = {
        "Dow Index":     {"value": None, "change": None, "change_percent": None},
        "S&P 500 Index": {"value": None, "change": None, "change_percent": None},
        "NASDAQ Index":  {"value": None, "change": None, "change_percent": None},
        "Scrape Time":   None
    }

    # Uruchomienie Selenium
    service = Service(driver_path)
    options = webdriver.ChromeOptions()
    # options.add_argument('--headless')

    driver = None
    try:
        driver = webdriver.Chrome(service=service, options=options)
        wait = WebDriverWait(driver, 30)

        # Przechodzimy na stronę CNN
        url = "https://edition.cnn.com/markets"
        driver.get(url)

        # Czekamy, aż pojawi się główny kontener z tabelą
        wait.until(EC.presence_of_element_located(
            (By.CSS_SELECTOR, ".basic-table__container-view-2PO4ei")
        ))

        # Pobieramy wszystkie wiersze w tej sekcji
        table_rows = driver.find_elements(By.CSS_SELECTOR, ".basic-table__entry-1UF7dk")
        # table_rows = 3

        # Iterujemy przez wiersze w tabeli
        for row in table_rows[:3]:            # Czy w wierszu w ogóle istnieje element .title-column a?
            name_link = row.find_elements(By.CSS_SELECTOR, ".title-column a")
            if not name_link:
                # Brak selektora => pomijamy
                continue

            # Nazwa indeksu:
            index_name = name_link[0].text.strip()

            # Pobieramy wartość indeksu
            value_el = row.find_elements(By.CSS_SELECTOR, ".basic-table__price-16Duv7")
            if not value_el:
                # Jeśli brak – pomijamy
                continue
            index_value = value_el[0].text.strip()
            # Usuwamy przecinki (np. "5,599.30" -> "5599.30")
            index_value = value_el[0].text.strip().replace(",", "")

            # Pobieramy zmianę i procent zmiany
            change_block = row.find_elements(By.CSS_SELECTOR, ".basic-table__change-1zbRwI")
            if not change_block:
                # Jeśli brak – pomijamy
                continue

            # # Usuwamy przecinki np. z "+ 1,200.55" -> "+ 1200.55"
            # index_value = sub_divs[0].text.strip().replace(",", "")
            # # Dla bezpieczeństwa także z wartości procentowej (jeśli kiedykolwiek pojawi się np. "1,20%")
            # change_pc = sub_divs[1].text.strip().replace(",", "")

            # Wewnątrz change_block mamy 2 <div>
            sub_divs = change_block[0].find_elements(By.CSS_SELECTOR, "div")
            if len(sub_divs) < 2:
                # Struktura inna niż oczekiwana => pomijamy
                continue

            index_change = sub_divs[0].text.strip()        # np. '- 82.55'
            index_change_percent = sub_divs[1].text.strip() # np. '0.20%'

            # Zapisujemy do słownika tylko wtedy, gdy klucz istnieje:
            if index_name in market_data:
                market_data[index_name]["value"] = index_value
                market_data[index_name]["change"] = index_change
                market_data[index_name]["change_percent"] = index_change_percent

        # Czas w formacie UTC (z użyciem strefy tz=UTC)
        current_utc_time = datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M:%S UTC")
        market_data["Scrape Time"] = current_utc_time

    except Exception as e:
        print("Wystąpił błąd podczas pobierania danych indeksów:")
        # print(e)

    finally:
        if driver:
            driver.quit()

    return market_data



#update 2.11.2025
# def scrape_market_indices(driver_path, headless=False, timeout=30):
#     # Słownik wynikowy
#     market_data = {
#         "Dow Index":     {"value": None, "change": None, "change_percent": None},
#         "S&P 500 Index": {"value": None, "change": None, "change_percent": None},
#         "NASDAQ Index":  {"value": None, "change": None, "change_percent": None},
#         "Scrape Time":   None
#     }
#
#     service = Service(driver_path)
#     options = webdriver.ChromeOptions()
#     if headless:
#         options.add_argument("--headless=new")
#     options.add_argument("--no-sandbox")
#     options.add_argument("--disable-gpu")
#     options.add_argument("--window-size=1200,1600")
#
#     driver = None
#     try:
#         driver = webdriver.Chrome(service=service, options=options)
#         wait = WebDriverWait(driver, timeout)
#
#         url = "https://edition.cnn.com/markets"
#         driver.get(url)
#
#         # === [NOWOŚĆ] Akceptacja cookies (CNN Consent Manager) ===
#         try:
#             cookie_button = WebDriverWait(driver, 5).until(
#                 EC.element_to_be_clickable((
#                     By.XPATH,
#                     "//button[contains(., 'Agree') or contains(., 'Accept all') or contains(., 'Accept All')]"
#                 ))
#             )
#             cookie_button.click()
#             print("Zaakceptowano cookies.")
#         except Exception:
#             print("Nie znaleziono lub nie trzeba akceptować cookies.")
#
#         # Czekamy na kontener z kartami indeksów
#         container = wait.until(
#             EC.presence_of_element_located(
#                 (By.XPATH, "//div[contains(@class,'cards-container')]")
#             )
#         )
#
#         # Pobieramy wszystkie karty indeksów (3 szt. dla: Dow, S&P 500, NASDAQ)
#         cards = container.find_elements(By.XPATH, ".//div[contains(@class,'index-card')]")
#
#         # Iterujemy po kartach
#         for card in cards:
#             # Pierwsza kolumna: nazwa + wartość
#             try:
#                 index_name_el = card.find_element(
#                     By.XPATH,
#                     ".//div[contains(@class,'index-card__column')][1]//div[contains(@class,'index-card__type')]"
#                 )
#                 index_name = index_name_el.text.strip()
#             except Exception:
#                 continue
#
#             try:
#                 value_el = card.find_element(
#                     By.XPATH,
#                     ".//div[contains(@class,'index-card__column')][1]//div[contains(@class,'index-card__value')]"
#                 )
#                 index_value = value_el.text.strip().replace(",", "")
#             except Exception:
#                 index_value = None
#
#             try:
#                 change_el = card.find_element(
#                     By.XPATH,
#                     ".//div[contains(@class,'index-card__column')][2]//span[contains(@class,'unit-change')]"
#                 )
#                 index_change = change_el.text.strip().replace(",", "")
#                 index_change = index_change.replace("+ ", "+").replace("- ", "-")
#             except Exception:
#                 index_change = None
#
#             try:
#                 change_pc_el = card.find_element(
#                     By.XPATH,
#                     ".//div[contains(@class,'index-card__column')][2]//span[contains(@class,'percent-change')]"
#                 )
#                 index_change_percent = change_pc_el.text.strip().replace(" ", "")
#             except Exception:
#                 index_change_percent = None
#
#             # Zapis tylko dla interesujących nas nazw
#             if index_name in market_data:
#                 market_data[index_name]["value"] = index_value
#                 market_data[index_name]["change"] = index_change
#                 market_data[index_name]["change_percent"] = index_change_percent
#
#         # Czas w UTC
#         market_data["Scrape Time"] = datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M:%S UTC")
#
#     except Exception as e:
#         print("Wystąpił błąd podczas pobierania danych indeksów:")
#         print(repr(e))
#     finally:
#         if driver:
#             driver.quit()
#
#     return market_data




def normalize_market_data_signs(market_data: dict) -> dict:
    """
    Funkcja normalizuje wartości w słowniku market_data z kluczami
    ["Dow Index", "S&P 500 Index", "NASDAQ Index"].
    Usuwa przecinki z liczb, usuwa znak '+' (jeśli występuje na początku),
    zachowuje minus bez zbędnych spacji.

    Struktura market_data zakładana jest taka:
    {
      "Dow Index": {
         "value": "...",
         "change": "...",
         "change_percent": "..."
      },
      "S&P 500 Index": {...},
      "NASDAQ Index": {...},
      "Scrape Time": ...
    }

    Zwraca zmodyfikowany słownik (w miejscu).
    """

    def normalize_sign(value: str) -> str:
        """
        Usuwa przecinki, zbędne spacje oraz znak '+' z początku ciągu.
        Minus jest zachowywany i spacje tuż po nim są usuwane.
        """
        if not value:  # jeśli None lub pusty string
            return value

        val = value.strip().replace(",", "")      # Usuwa przecinki i spacje z brzegów
        val = re.sub(r'^\+\s*', '', val)          # Usuwa plus (jeśli istnieje) z ewentualnymi spacjami
        val = re.sub(r'^-\s*', '-', val)          # Zamienia '- 82.55' na '-82.55'
        return val

    # Lista kluczy indeksów (pomijamy "Scrape Time")
    index_keys = ["Dow Index", "S&P 500 Index", "NASDAQ Index"]

    # Iterujemy po indeksach i sub-kluczach
    for key in index_keys:
        # Upewniamy się, że klucz w ogóle istnieje w słowniku
        if key not in market_data:
            continue

        # Każdy index ma "value", "change", "change_percent"
        for sub_key in ["value", "change", "change_percent"]:
            if sub_key in market_data[key] and market_data[key][sub_key] is not None:
                normalized = normalize_sign(market_data[key][sub_key])
                market_data[key][sub_key] = normalized

    return market_data


def process_retries(drops, df):
    """
    Przetwarza listę spółek do ponownego przetworzenia (drops) poprzez próbę retry.
    Jeżeli po retry wystąpią spółki, które nadal nie zostały przetworzone (new_drops),
    zapisuje je do pliku CSV w lokalizacji:
    /Users/michal/PycharmProjects/Stock Scraper/retrylist.csv.

    Args:
        drops (list): Lista symboli spółek do retry.
        df (pd.DataFrame): Aktualny DataFrame ze spółkami.

    Returns:
        pd.DataFrame: Zaktualizowany DataFrame zawierający dane także z retry.
    """
    print("Spółki do ponownego przetworzenia:")
    for drop in drops:
        print(drop)

    # Sprawdzamy, czy mamy jakiekolwiek spółki do retry
    if drops:
        # Zakładamy, że funkcja retry_drops zwraca krotkę (retry_data, new_drops)
        # gdzie retry_data to dane pobrane przy retry, a new_drops to lista spółek, które nadal nie zostały przetworzone.
        retry_data, new_drops = retry_drops(drops)
        df_retry = pd.DataFrame(retry_data)
        df = pd.concat([df, df_retry], ignore_index=True)

        if new_drops:
            print("Spółki, które nadal nie zostały przetworzone po retry:")
            for drop in new_drops:
                print(drop)
            # Zapisujemy listę spółek do retry do pliku CSV (nadpisujemy poprzedni plik)
            df_retrylist = pd.DataFrame(new_drops, columns=["Symbol"])
            df_retrylist.to_csv("/Users/michal/PycharmProjects/Stock Scraper/retrylist.csv", index=False)
        else:
            print("Wszystkie spółki zostały przetworzone po retry.")
            # Zapisujemy pusty plik z nagłówkiem (nadpisanie)
            pd.DataFrame(columns=["Symbol"]).to_csv("/Users/michal/PycharmProjects/Stock Scraper/retrylist.csv",
                                                    index=False)
    else:
        print("Brak spółek do ponownego przetworzenia.")
        print("")
        print("-" * 57)
        # Jeśli nie było spółek do retry, nadpisujemy plik pustym nagłówkiem
        pd.DataFrame(columns=["Symbol"]).to_csv("/Users/michal/PycharmProjects/Stock Scraper/retrylist.csv",
                                                index=False)

    return df


def update_fear_and_greed_index(df, fgi_data):
    """
    Aktualizuje kolumnę "Fear & Greed Index" w DataFrame df na podstawie danych z fgi_data.

    Jeśli fgi_data["Fear & Greed Index"] nie jest None, ustawia tę wartość,
    w przeciwnym wypadku ustawia wartość NaN.

    Args:
        df (pd.DataFrame): DataFrame do aktualizacji.
        fgi_data (dict): Słownik zawierający klucz "Fear & Greed Index".

    Returns:
        pd.DataFrame: Zaktualizowany DataFrame.
    """
    if fgi_data.get("Fear & Greed Index") is not None:
        df["Fear & Greed Index"] = fgi_data["Fear & Greed Index"]
    else:
        df["Fear & Greed Index"] = float('nan')
    return df


def update_market_indices(df, market_data):
    """
    Aktualizuje w DataFrame df informacje o indeksach Dow, S&P 500 oraz NASDAQ
    na podstawie słownika market_data w formacie:
        {
            "Dow Index": {
                "value": "...",
                "change": "...",
                "change_percent": "..."
            },
            "S&P 500 Index": {...},
            "NASDAQ Index": {...},
            "Scrape Time": "..."
        }

    Tworzy (lub nadpisuje) następujące kolumny:
        - "Dow Index Value"
        - "Dow Index Change"
        - "Dow Index % Change"
        - "S&P 500 Value"
        - "S&P 500 Change"
        - "S&P 500 % Change"
        - "NASDAQ Value"
        - "NASDAQ Change"
        - "NASDAQ % Change"
        - "Market Indices Time"

    Zwraca zaktualizowany DataFrame.
    """

    # Pomocnicza funkcja: pobiera wartość z market_data lub zwraca NaN
    def get_value(d, key, subkey):
        if d.get(key) is not None:
            return d[key].get(subkey, float('nan'))
        return float('nan')

    # Dow Index
    df["Dow Index Value"]     = get_value(market_data, "Dow Index", "value")
    df["Dow Index Change"]    = get_value(market_data, "Dow Index", "change")
    df["Dow Index % Change"]  = get_value(market_data, "Dow Index", "change_percent")

    # S&P 500 Index
    df["S&P 500 Value"]       = get_value(market_data, "S&P 500 Index", "value")
    df["S&P 500 Change"]      = get_value(market_data, "S&P 500 Index", "change")
    df["S&P 500 % Change"]    = get_value(market_data, "S&P 500 Index", "change_percent")

    # NASDAQ Index
    df["NASDAQ Value"]        = get_value(market_data, "NASDAQ Index", "value")
    df["NASDAQ Change"]       = get_value(market_data, "NASDAQ Index", "change")
    df["NASDAQ % Change"]     = get_value(market_data, "NASDAQ Index", "change_percent")

    # Czas scrapowania (Market Indices Time)
    if market_data.get("Scrape Time") is not None:
        df["Market Indices Time"] = market_data["Scrape Time"]
    else:
        df["Market Indices Time"] = float('nan')

    return df

#stara funkcja zapisu - dopisuje do ostatniego wiersza i trzeba to poprawiać ręcznie
# def save_df_to_csv(df, output_csv_path):
#     """
#     Zapisuje DataFrame df do pliku CSV.
#
#     Jeśli plik istnieje, dane są dopisywane (append), a nagłówek nie jest zapisywany.
#     Jeśli plik nie istnieje, tworzy nowy plik z nagłówkiem.
#
#     Args:
#         df (pd.DataFrame): DataFrame do zapisania.
#         output_csv_path (str): Ścieżka do pliku CSV.
#     """
#     file_exists = os.path.isfile(output_csv_path)
#     df.to_csv(
#         output_csv_path,
#         index=False,
#         mode='a',  # 'a' dla dopisywania, 'w' dla nadpisywania
#         header=not file_exists,  # Zapisz nagłówek tylko, jeśli plik nie istnieje
#         sep=';'
#     )


def save_df_to_csv(df, output_csv_path):
    """
    Zapisuje DataFrame df do pliku CSV w trybie append,
    ale upewnia się, że poprzedni zapis zakończył się nową linią.
    """

    file_exists = os.path.isfile(output_csv_path)

    # Jeżeli plik istnieje, upewniamy się, że na końcu jest znak nowej linii:
    if file_exists:
        with open(output_csv_path, 'rb+') as f:
            # Przesuwamy kursor na koniec pliku
            f.seek(0, os.SEEK_END)
            # Jeżeli plik nie jest pusty:
            if f.tell() > 0:
                f.seek(-1, os.SEEK_END)
                last_char = f.read(1)
                # Sprawdzamy, czy ostatni bajt (znak) to '\n'
                if last_char != b'\n':
                    f.write(b'\n')  # Dopisujemy znak nowej linii

    df.to_csv(
        output_csv_path,
        index=False,
        mode='a',  # dopisywanie do pliku
        header=not file_exists,  # nagłówek tylko jeśli plik nie istnieje
        sep=';'   # separator
    )


#Uruchomienie całej aplikacji
if __name__ == "__main__":
    BASE_URL = "https://edition.cnn.com/markets/stocks/"
    SYMBOL_CSV_PATH = "/Users/michal/PycharmProjects/Stock Scraper/sp500symbols.csv"
    # SYMBOL_CSV_PATH = "/Users/michal/PycharmProjects/Stock Scraper/retrylist.csv"
    # SYMBOL_CSV_PATH = "/Users/michal/PycharmProjects/Stock Scraper/Russel 1000 Symbols/russell_1000_constituents_extended.csv"

    # Pobieramy unikalną listę URL-i spółek
    stocks = get_stock_urls(SYMBOL_CSV_PATH, BASE_URL)

    # Pobieramy ścieżki (CSV i WebDriver)
    OUTPUT_CSV_PATH, driver_path = get_paths()

    # Teraz można wykorzystać zmienne stocks, OUTPUT_CSV_PATH i driver_path
    # w dalszej części kodu (np. inicjalizacja WebDrivera lub przetwarzanie danych)

    # Uruchamianie funkcji zwracającej czas
    current_time, hour_timestamp, date_timestamp = get_current_timestamps()

    # uruchamianie głównej funkcji scrapującej
    # df, drops = scrape_data(limit=40) #retry
    df, drops = scrape_data(limit=560) #all 559

    df = process_retries(drops, df)

    # Uruchomienie funkcji pobierającej Fear & Greed Index
    fgi_data = scrape_fear_greed_index(driver_path)

    #funkcja do pobierania indexów
    market_data = scrape_market_indices(driver_path)

    # funkcja do normalizowania indexów (usuwamy + i zostawiaomy - przy ujemnych)
    market_data = normalize_market_data_signs(market_data)

    # Uruchomienie funkcji dodającej dane FGI do DataFrame
    df = update_fear_and_greed_index(df, fgi_data)

    # Uruchomienie funkcji dodającej dane indexów do DataFrame
    df = update_market_indices(df, market_data)

    # funkcja czyszczenia danych
    df = clean_data(df)

    # Zapisz DataFrame do pliku CSV
    save_df_to_csv(df, OUTPUT_CSV_PATH)

