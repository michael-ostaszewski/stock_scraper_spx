# import os
import subprocess
import schedule
import time
import datetime

def run_stock_scraper():
    # Sprawdzamy, czy dzisiaj jest dzień roboczy (poniedziałek-piątek)
    if datetime.datetime.today().weekday() < 5:  # 0 = poniedziałek, 4 = piątek
        # Ścieżki do środowiska wirtualnego i skryptu
        venv_activate = "/Users/michal/PycharmProjects/Parsymonia_excel/.venv/bin/activate"
        script_path = "/Users/michal/PycharmProjects/Stock Scraper/Stock_scraper_cnn.py"
        print("\nUruchamiam scraper...")
        # Uruchomienie komendy w shellu – aktywacja środowiska i uruchomienie skryptu
        command = f"source {venv_activate} && python3 '{script_path}'"
        subprocess.call(command, shell=True)
    else:
        print("\nDzisiaj jest weekend, scraper nie jest uruchamiany.")

# Ustawiamy zadanie: codziennie o 02:00 scraper ma się uruchomić
schedule.every().day.at("02:00").do(run_stock_scraper)

print("Program czeka na następną aktywację scrapera:")

while True:
    # Pobieramy zadania harmonogramu (zakładamy, że mamy tylko jedno)
    jobs = schedule.get_jobs()
    if jobs:
        next_run_time = jobs[0].next_run
        # Obliczamy czas pozostały do następnego uruchomienia
        time_left = next_run_time - datetime.datetime.now()
        total_seconds = int(time_left.total_seconds())
        if total_seconds < 0:
            total_seconds = 0  # zabezpieczenie gdy czas ujemny
        hours, remainder = divmod(total_seconds, 3600)
        minutes, seconds = divmod(remainder, 60)
        countdown_str = f"{hours:02d}:{minutes:02d}:{seconds:02d}"
        # Używamy end="\r" aby wypisywać na tej samej linii (przykrywanie poprzedniego wydruku)
        print(f"Scraper odpali się za: {countdown_str}", end="\r")
    schedule.run_pending()
    time.sleep(60)  # odświeżanie co minutę
