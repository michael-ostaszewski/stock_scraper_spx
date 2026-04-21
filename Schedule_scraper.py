#poniższy kod tylko do linii 49 odpala tylko scraper CNN

# # import os
# import subprocess
# import schedule
# import time
# import datetime
#
# def run_stock_scraper():
#     # Sprawdzamy, czy dzisiaj jest dzień roboczy (poniedziałek-piątek)
#     if datetime.datetime.today().weekday() < 5:  # 0 = poniedziałek, 4 = piątek
#         # Ścieżki do środowiska wirtualnego i skryptu
#         venv_activate = "/Users/michal/PycharmProjects/Parsymonia_excel/.venv/bin/activate"
#         script_path = "/Users/michal/PycharmProjects/Stock Scraper/Stock_scraper_cnn.py"
#         print("\nUruchamiam scraper...")
#         # Uruchomienie komendy w shellu – aktywacja środowiska i uruchomienie skryptu
#         command = f"source {venv_activate} && python3 '{script_path}'"
#         subprocess.call(command, shell=True)
#     else:
#         print("\nDzisiaj jest weekend, scraper nie jest uruchamiany.")
#
# # Ustawiamy zadanie: codziennie o 02:00 scraper ma się uruchomić
# schedule.every().day.at("02:10").do(run_stock_scraper)
#
# print("Program czeka na następną aktywację scrapera:")
#
# while True:
#     # Pobieramy zadania harmonogramu (zakładamy, że mamy tylko jedno)
#     jobs = schedule.get_jobs()
#     if jobs:
#         next_run_time = jobs[0].next_run
#         # Obliczamy czas pozostały do następnego uruchomienia
#         time_left = next_run_time - datetime.datetime.now()
#         total_seconds = int(time_left.total_seconds())
#         if total_seconds < 0:
#             total_seconds = 0  # zabezpieczenie gdy czas ujemny
#         hours, remainder = divmod(total_seconds, 3600)
#         minutes, seconds = divmod(remainder, 60)
#         countdown_str = f"{hours:02d}:{minutes:02d}:{seconds:02d}"
#         # Używamy end="\r" aby wypisywać na tej samej linii (przykrywanie poprzedniego wydruku)
#         print(f"Scraper odpali się za: {countdown_str}", end="\r")
#     schedule.run_pending()
#     time.sleep(60)  # odświeżanie co minutę


# ============================================================
# Harmonogram uruchamiania scraperów CNN i Finviz (dni robocze)
# Z ciągłym odliczaniem co sekundę do następnego startu
# ============================================================




# poprzepdni tylko do cnn i fv
# import os
# import subprocess
# import schedule
# import time
# from datetime import datetime
#
# # ─────────────────────────────────────────────────────────────
# # KONFIGURACJA
# # ─────────────────────────────────────────────────────────────
# VENV_PYTHON = "/Users/michal/PycharmProjects/Parsymonia_excel/.venv/bin/python"
#
# SCRIPTS = [
#     "/Users/michal/PycharmProjects/Stock Scraper/Stock_scraper_cnn.py",
#     "/Users/michal/PycharmProjects/Stock Scraper/Stock_scraper_fv.py",
# ]
#
# LAUNCH_TIME = "02:05"          # codziennie o 02:05
#
# # ─────────────────────────────────────────────────────────────
# # FUNKCJA ZADANIA
# # ─────────────────────────────────────────────────────────────
# def run_stock_scrapers() -> None:
#     """Startuje oba scrapery równolegle, ale tylko w dni robocze."""
#     now_txt = datetime.now().isoformat(timespec="seconds")
#     if datetime.today().weekday() < 5:   # 0-pon, …, 4-pt
#         print(f"\n[{now_txt}] ▶ Uruchamiam scrapery…")
#         for path in SCRIPTS:
#             print(f"    • start {os.path.basename(path)}")
#             subprocess.Popen([VENV_PYTHON, path])
#     else:
#         print(f"\n[{now_txt}] ⏸ Weekend – scrapery nie są uruchamiane.")
#
# # ─────────────────────────────────────────────────────────────
# # REJESTRACJA ZADANIA W HARMONOGRAMIE
# # ─────────────────────────────────────────────────────────────
# schedule.every().day.at(LAUNCH_TIME).do(run_stock_scrapers)
# print(f"Harmonogram aktywny – zadania o {LAUNCH_TIME} (pon-pt).")
#
# # ─────────────────────────────────────────────────────────────
# # PĘTLA GŁÓWNA  (aktualizacja odliczania co sekundę)
# # ─────────────────────────────────────────────────────────────
# def fmt_delta(sec: float) -> str:
#     sec = max(int(sec), 0)
#     h, rem = divmod(sec, 3600)
#     m, s = divmod(rem, 60)
#     return f"{h:02d}:{m:02d}:{s:02d}"
#
# while True:
#     next_run = schedule.next_run()
#     if next_run:
#         seconds_left = (next_run - datetime.now()).total_seconds()
#         print(f"\rScrapery odpalą się za: {fmt_delta(seconds_left)}", end="", flush=True)
#     else:
#         # (teoretycznie nigdy tu nie trafisz, bo zadanie jest cykliczne)
#         print("\rBrak zaplanowanych zadań.", end="", flush=True)
#
#     schedule.run_pending()
#     time.sleep(1)          # odświeżanie co sekundę






#  nowy do cnn, fv i indeksów:
# ============================================================
# Harmonogram uruchamiania scraperów (dni robocze)
# - 02:05: CNN + Finviz
# - 23:30: Index_scraper_inv (Investing)
# Z ciągłym odliczaniem co sekundę do najbliższego startu
# ============================================================

# import os
# import subprocess
# import schedule
# import time
# from datetime import datetime
#
# # ─────────────────────────────────────────────────────────────
# # KONFIGURACJA
# # ─────────────────────────────────────────────────────────────
# VENV_PYTHON = "/Users/michal/PycharmProjects/Parsymonia_excel/.venv/bin/python"
#
# SCRIPTS_2AM = [
#     "/Users/michal/PycharmProjects/Stock Scraper/Stock_scraper_cnn.py",
#     "/Users/michal/PycharmProjects/Stock Scraper/Stock_scraper_fv.py",
# ]
#
# INDEX_SCRIPT = "/Users/michal/PycharmProjects/Stock Scraper/Index_scraper_inv.py"
#
# LAUNCH_TIME_2AM   = "02:05"   # codziennie o 02:05 (pon-pt)
# LAUNCH_TIME_INDEX = "23:30"   # codziennie o 23:30 (pon-pt)
#
# # ─────────────────────────────────────────────────────────────
# # FUNKCJE POMOCNICZE
# # ─────────────────────────────────────────────────────────────
# def is_weekday() -> bool:
#     """Zwraca True, gdy dziś jest dzień roboczy (pon–pt)."""
#     return datetime.today().weekday() < 5  # 0=pon, 4=pt
#
# def start_process(py_path: str, script_path: str) -> None:
#     """Uruchamia skrypt w osobnym procesie przy użyciu zadanego interpretera."""
#     print(f"    • start {os.path.basename(script_path)}")
#     subprocess.Popen([py_path, script_path])
#
# def run_group(label: str, scripts: list[str]) -> None:
#     """Uruchamia grupę skryptów równolegle (tylko w dni robocze)."""
#     now_txt = datetime.now().isoformat(timespec="seconds")
#     if is_weekday():
#         print(f"\n[{now_txt}] ▶ Uruchamiam: {label}")
#         for path in scripts:
#             start_process(VENV_PYTHON, path)
#     else:
#         print(f"\n[{now_txt}] ⏸ Weekend – {label} nie uruchamiam.")
#
# # ─────────────────────────────────────────────────────────────
# # ZADANIA
# # ─────────────────────────────────────────────────────────────
# def run_stock_scrapers() -> None:
#     """02:05 – CNN + Finviz"""
#     run_group("scrapery (CNN + Finviz)", SCRIPTS_2AM)
#
# def run_index_scraper() -> None:
#     """23:30 – Index_scraper_inv"""
#     run_group("Index_scraper_inv (Investing)", [INDEX_SCRIPT])
#
# # ─────────────────────────────────────────────────────────────
# # REJESTRACJA ZADAŃ W HARMONOGRAMIE + TAGI
# # ─────────────────────────────────────────────────────────────
# job_2am = schedule.every().day.at(LAUNCH_TIME_2AM).do(run_stock_scrapers).tag("02:05 – CNN+Finviz")
# job_idx = schedule.every().day.at(LAUNCH_TIME_INDEX).do(run_index_scraper).tag("23:30 – Index (Investing)")
#
# print("Harmonogram aktywny:")
# print(f"  • {', '.join(job_2am.tags)} (pon–pt)")
# print(f"  • {', '.join(job_idx.tags)} (pon–pt)")
#
# # ─────────────────────────────────────────────────────────────
# # PĘTLA GŁÓWNA – odliczanie do najbliższego startu
# # ─────────────────────────────────────────────────────────────
# def fmt_delta(sec: float) -> str:
#     sec = max(int(sec), 0)
#     h, rem = divmod(sec, 3600)
#     m, s = divmod(rem, 60)
#     return f"{h:02d}:{m:02d}:{s:02d}"
#
# def next_job_info():
#     jobs = schedule.get_jobs()
#     if not jobs:
#         return None, None
#     # Najbliższe zadanie po next_run
#     next_job = min(jobs, key=lambda j: j.next_run)
#     # Nazwa z taga (jeśli jest wiele tagów, bierzemy pierwszy do opisu)
#     name = next(iter(next_job.tags), "zadanie")
#     return name, next_job.next_run
#
# while True:
#     name, next_run = next_job_info()
#     if next_run:
#         seconds_left = (next_run - datetime.now()).total_seconds()
#         print(f"\rNajbliższe: {name} za {fmt_delta(seconds_left)}", end="", flush=True)
#     else:
#         print("\rBrak zaplanowanych zadań.", end="", flush=True)
#
#     schedule.run_pending()
#     time.sleep(1)  # odświeżanie co sekundę








# czas letni:

# # ============================================================
# # Harmonogram uruchamiania scraperów (dni robocze)
# # - 02:05: CNN + Finviz  → wyciszenie countdowunu do zakończenia ich pracy
# #                          LUB maks. do 07:00 (cokolwiek nastąpi wcześniej)
# # - 23:30: Index_scraper_inv → wyciszenie countdownu na 5 minut
# # Z ciągłym odliczaniem do najbliższego startu (gdy nie jest wyciszone)
# # ============================================================
#
# import os
# import subprocess
# import schedule
# import time
# from datetime import datetime, timedelta
#
# # ─────────────────────────────────────────────────────────────
# # KONFIGURACJA
# # ─────────────────────────────────────────────────────────────
# VENV_PYTHON = "/Users/michal/PycharmProjects/Parsymonia_excel/.venv/bin/python"
#
# SCRIPTS_2AM = [
#     "/Users/michal/PycharmProjects/Stock Scraper/Stock_scraper_cnn.py",
#     "/Users/michal/PycharmProjects/Stock Scraper/Stock_scraper_fv.py",
# ]
# INDEX_SCRIPT = "/Users/michal/PycharmProjects/Stock Scraper/Index_scraper_inv.py"
#
# LAUNCH_TIME_2AM   = "01:05"   # codziennie (pon-pt)
# LAUNCH_TIME_INDEX = "22:30"   # codziennie (pon-pt)
#
# # ─────────────────────────────────────────────────────────────
# # STAN (globalny)
# # ─────────────────────────────────────────────────────────────
# ACTIVE_PROCS = {
#     "02:05": [],   # list[subprocess.Popen]
#     "23:30": [],   # list[subprocess.Popen]
# }
# last_2am_start_ts: datetime | None = None         # kiedy odpalono grupę 02:05 (dzisiaj)
# index_silence_until_ts: datetime | None = None    # cisza po 23:30 przez 5 minut
#
# # ─────────────────────────────────────────────────────────────
# # POMOCNICZE
# # ─────────────────────────────────────────────────────────────
# def is_weekday() -> bool:
#     return datetime.today().weekday() < 5  # 0=pon, 4=pt
#
# def start_process(script_path: str) -> subprocess.Popen:
#     print(f"    • start {os.path.basename(script_path)}")
#     return subprocess.Popen([VENV_PYTHON, script_path])
#
# def run_group(label: str, scripts: list[str]) -> list[subprocess.Popen]:
#     """Uruchamia grupę skryptów równolegle (tylko w dni robocze). Zwraca listę Popen."""
#     now_txt = datetime.now().isoformat(timespec="seconds")
#     if is_weekday():
#         print(f"\n[{now_txt}] ▶ Uruchamiam: {label}")
#         procs = [start_process(p) for p in scripts]
#         return procs
#     else:
#         print(f"\n[{now_txt}] ⏸ Weekend – {label} nie uruchamiam.")
#         return []
#
# def fmt_delta(sec: float) -> str:
#     sec = max(int(sec), 0)
#     h, rem = divmod(sec, 3600)
#     m, s = divmod(rem, 60)
#     return f"{h:02d}:{m:02d}:{s:02d}"
#
# def next_job_info():
#     jobs = schedule.get_jobs()
#     if not jobs:
#         return None, None
#     next_job = min(jobs, key=lambda j: j.next_run)
#     name = next(iter(next_job.tags), "zadanie")
#     return name, next_job.next_run
#
# def cleanup_and_log_finished(group_key: str) -> None:
#     """Sprząta zakończone procesy i wypisuje ich status zakończenia (raz)."""
#     alive = []
#     for p in ACTIVE_PROCS[group_key]:
#         ret = p.poll()
#         if ret is None:
#             alive.append(p)
#         else:
#             # jednorazowy log zakończenia
#             print(f"\n[{datetime.now().isoformat(timespec='seconds')}] ✓ {group_key}: "
#                   f"proces PID={p.pid} zakończony (exit={ret})")
#     ACTIVE_PROCS[group_key] = alive
#
# def any_alive(group_key: str) -> bool:
#     return any(p.poll() is None for p in ACTIVE_PROCS[group_key])
#
# def seven_am_of(date_ref: datetime) -> datetime:
#     return date_ref.replace(hour=7, minute=0, second=0, microsecond=0)
#
# def is_countdown_muted(now: datetime) -> bool:
#     """
#     Countdown jest wyciszony gdy:
#     1) trwa 5-minutowe okno ciszy po starcie Index_scraper_inv (23:30), LUB
#     2) po starcie 02:05 (CNN+Finviz) – dopóki którykolwiek z tych procesów działa
#        I jednocześnie jest przed 07:00 tego samego dnia.
#        (czyli: wyciszenie trwa do MIN(07:00, koniec ostatniego procesu))
#     """
#     # 1) okno ciszy po 23:30
#     if index_silence_until_ts and now < index_silence_until_ts:
#         return True
#
#     # 2) cisza po 02:05 – do zakończenia ostatniego procesu lub max do 07:00
#     if last_2am_start_ts:
#         if now >= last_2am_start_ts:  # mamy tegodniowe odpalenie
#             before_7 = now < seven_am_of(last_2am_start_ts)
#             if before_7 and any_alive("02:05"):
#                 return True
#
#     return False
#
# # ─────────────────────────────────────────────────────────────
# # ZADANIA HARMONOGRAMU
# # ─────────────────────────────────────────────────────────────
# def run_stock_scrapers() -> None:
#     """02:05 – uruchamia CNN + Finviz i włącza tryb ciszy wg reguły MIN(07:00, koniec procesów)."""
#     global last_2am_start_ts
#     procs = run_group("scrapery (CNN + Finviz)", SCRIPTS_2AM)
#     if procs:
#         ACTIVE_PROCS["02:05"] = procs
#         last_2am_start_ts = datetime.now()
#
# def run_index_scraper() -> None:
#     """23:30 – uruchamia Index_scraper_inv i wycisza countdown na 5 minut."""
#     global index_silence_until_ts
#     procs = run_group("Index_scraper_inv (Investing)", [INDEX_SCRIPT])
#     if procs:
#         ACTIVE_PROCS["23:30"] = procs
#         index_silence_until_ts = datetime.now() + timedelta(minutes=5)
#
# # ─────────────────────────────────────────────────────────────
# # REJESTRACJA ZADAŃ
# # ─────────────────────────────────────────────────────────────
# job_2am = schedule.every().day.at(LAUNCH_TIME_2AM).do(run_stock_scrapers).tag("02:05 – CNN+Finviz")
# job_idx = schedule.every().day.at(LAUNCH_TIME_INDEX).do(run_index_scraper).tag("23:30 – Index (Investing)")
#
# print("Harmonogram aktywny:")
# print(f"  • {', '.join(job_2am.tags)} (pon–pt)")
# print(f"  • {', '.join(job_idx.tags)} (pon–pt)")
#
# # ─────────────────────────────────────────────────────────────
# # PĘTLA GŁÓWNA – odliczanie (gdy nie wyciszone)
# # ─────────────────────────────────────────────────────────────
# last_countdown_line = ""  # żeby nie przeładowywać tej samej linijki bez potrzeby
#
# while True:
#     now = datetime.now()
#
#     # Sprzątanie i jednorazowe logi zakończenia procesów:
#     cleanup_and_log_finished("02:05")
#     cleanup_and_log_finished("23:30")
#
#     # Countdown tylko jeśli nie jest wyciszony wg reguł:
#     muted = is_countdown_muted(now)
#     if not muted:
#         name, next_run = next_job_info()
#         if next_run:
#             seconds_left = (next_run - now).total_seconds()
#             line = f"Najbliższe: {name} za {fmt_delta(seconds_left)}"
#         else:
#             line = "Brak zaplanowanych zadań."
#         # unikaj spamowania tym samym tekstem
#         if line != last_countdown_line:
#             print("\r" + line + " " * max(0, len(last_countdown_line) - len(line)), end="", flush=True)
#             last_countdown_line = line
#     else:
#         # kiedy jest wyciszenie – jeśli poprzednio coś wypisywaliśmy, wyczyść linię, potem milcz
#         if last_countdown_line:
#             print("\r" + " " * len(last_countdown_line) + "\r", end="", flush=True)
#             last_countdown_line = ""
#
#     schedule.run_pending()
#     time.sleep(1)







# czas zimowy:

# ============================================================
# Harmonogram uruchamiania scraperów (dni robocze)
# - 01:05: CNN + Finviz  → wyciszenie countdowunu do zakończenia ich pracy
#                          LUB maks. do 07:00 (cokolwiek nastąpi wcześniej)
# - 22:30: Index_scraper_inv → wyciszenie countdownu na 5 minut
# Z ciągłym odliczaniem do najbliższego startu (gdy nie jest wyciszone)
# ============================================================

import os
import subprocess
import schedule
import time
from datetime import datetime, timedelta

# ─────────────────────────────────────────────────────────────
# KONFIGURACJA
# ─────────────────────────────────────────────────────────────
VENV_PYTHON = "/Users/michal/PycharmProjects/Parsymonia_excel/.venv/bin/python"

SCRIPTS_STOCK = [
    "/Users/michal/PycharmProjects/Stock Scraper/Stock_scraper_cnn.py",
    "/Users/michal/PycharmProjects/Stock Scraper/Stock_scraper_fv.py",
]
INDEX_SCRIPT = "/Users/michal/PycharmProjects/Stock Scraper/Index_scraper_inv.py"

LAUNCH_TIME_STOCK = "01:05"   # codziennie (pon-pt)
LAUNCH_TIME_INDEX = "22:30"   # codziennie (pon-pt)

TAG_STOCK = "01:05 – CNN+Finviz"
TAG_INDEX = "22:30 – Index (Investing)"

# ─────────────────────────────────────────────────────────────
# STAN (globalny)
# ─────────────────────────────────────────────────────────────
ACTIVE_PROCS = {
    "stock": [],   # list[subprocess.Popen] dla grupy CNN+Finviz
    "index": [],   # list[subprocess.Popen] dla indeksów
}
last_stock_start_ts: datetime | None = None      # kiedy odpalono grupę 01:05 (dziś)
index_silence_until_ts: datetime | None = None   # cisza po starcie indeksów przez 5 minut

# ─────────────────────────────────────────────────────────────
# POMOCNICZE
# ─────────────────────────────────────────────────────────────
def is_weekday() -> bool:
    return datetime.today().weekday() < 5  # 0=pon, 4=pt

def start_process(script_path: str) -> subprocess.Popen:
    print(f"    • start {os.path.basename(script_path)}")
    return subprocess.Popen([VENV_PYTHON, script_path])

def run_group(label: str, scripts: list[str]) -> list[subprocess.Popen]:
    """Uruchamia grupę skryptów równolegle (tylko w dni robocze). Zwraca listę Popen."""
    now_txt = datetime.now().isoformat(timespec="seconds")
    if is_weekday():
        print(f"\n[{now_txt}] ▶ Uruchamiam: {label}")
        return [start_process(p) for p in scripts]
    else:
        print(f"\n[{now_txt}] ⏸ Weekend – {label} nie uruchamiam.")
        return []

def fmt_delta(sec: float) -> str:
    sec = max(int(sec), 0)
    h, rem = divmod(sec, 3600)
    m, s = divmod(rem, 60)
    return f"{h:02d}:{m:02d}:{s:02d}"

def next_job_info():
    jobs = schedule.get_jobs()
    if not jobs:
        return None, None
    next_job = min(jobs, key=lambda j: j.next_run)
    name = next(iter(next_job.tags), "zadanie")
    return name, next_job.next_run

def cleanup_and_log_finished(group_key: str) -> None:
    """Sprząta zakończone procesy i jednorazowo loguje ich zakończenie."""
    alive = []
    for p in ACTIVE_PROCS[group_key]:
        ret = p.poll()
        if ret is None:
            alive.append(p)
        else:
            print(f"\n[{datetime.now().isoformat(timespec='seconds')}] ✓ {group_key}: "
                  f"PID={p.pid} zakończony (exit={ret})")
    ACTIVE_PROCS[group_key] = alive

def any_alive(group_key: str) -> bool:
    return any(p.poll() is None for p in ACTIVE_PROCS[group_key])

def seven_am_of(date_ref: datetime) -> datetime:
    return date_ref.replace(hour=7, minute=0, second=0, microsecond=0)

def is_countdown_muted(now: datetime) -> bool:
    """
    Countdown jest wyciszony gdy:
    1) trwa 5-minutowe okno ciszy po starcie zadań indeksowych (22:30), LUB
    2) po starcie zadań stockowych (01:05) – dopóki którykolwiek z tych procesów działa
       i jednocześnie jest przed 07:00 tego samego dnia.
       (czyli: wyciszenie trwa do MIN(07:00, koniec ostatniego procesu))
    """
    # 1) okno ciszy po indeksach
    if index_silence_until_ts and now < index_silence_until_ts:
        return True

    # 2) cisza po 01:05 – do zakończenia ostatniego procesu lub max do 07:00
    if last_stock_start_ts and now >= last_stock_start_ts:
        if now < seven_am_of(last_stock_start_ts) and any_alive("stock"):
            return True

    return False

# ─────────────────────────────────────────────────────────────
# ZADANIA HARMONOGRAMU
# ─────────────────────────────────────────────────────────────
def run_stock_scrapers() -> None:
    """01:05 – uruchamia CNN + Finviz i włącza tryb ciszy wg reguły MIN(07:00, koniec procesów)."""
    global last_stock_start_ts
    procs = run_group("scrapery (CNN + Finviz)", SCRIPTS_STOCK)
    if procs:
        ACTIVE_PROCS["stock"] = procs
        last_stock_start_ts = datetime.now()

def run_index_scraper() -> None:
    """22:30 – uruchamia Index_scraper_inv i wycisza countdown na 5 minut."""
    global index_silence_until_ts
    procs = run_group("Index_scraper_inv (Investing)", [INDEX_SCRIPT])
    if procs:
        ACTIVE_PROCS["index"] = procs
        index_silence_until_ts = datetime.now() + timedelta(minutes=5)

# ─────────────────────────────────────────────────────────────
# REJESTRACJA ZADAŃ
# ─────────────────────────────────────────────────────────────
job_stock = schedule.every().day.at(LAUNCH_TIME_STOCK).do(run_stock_scrapers).tag(TAG_STOCK)
job_index = schedule.every().day.at(LAUNCH_TIME_INDEX).do(run_index_scraper).tag(TAG_INDEX)

print("Harmonogram aktywny:")
print(f"  • {', '.join(job_stock.tags)} (pon–pt)")
print(f"  • {', '.join(job_index.tags)} (pon–pt)")

# ─────────────────────────────────────────────────────────────
# PĘTLA GŁÓWNA – odliczanie (gdy nie wyciszone)
# ─────────────────────────────────────────────────────────────
last_countdown_line = ""  # żeby nie przeładowywać tej samej linijki bez potrzeby

while True:
    now = datetime.now()

    # Sprzątanie i jednorazowe logi zakończenia procesów:
    cleanup_and_log_finished("stock")
    cleanup_and_log_finished("index")

    # Countdown tylko jeśli nie jest wyciszony wg reguł:
    if not is_countdown_muted(now):
        name, next_run = next_job_info()
        if next_run:
            seconds_left = (next_run - now).total_seconds()
            line = f"Najbliższe: {name} za {fmt_delta(seconds_left)}"
        else:
            line = "Brak zaplanowanych zadań."
        if line != last_countdown_line:
            print("\r" + line + " " * max(0, len(last_countdown_line) - len(line)), end="", flush=True)
            last_countdown_line = line
    else:
        if last_countdown_line:
            print("\r" + " " * len(last_countdown_line) + "\r", end="", flush=True)
            last_countdown_line = ""

    schedule.run_pending()
    time.sleep(1)

