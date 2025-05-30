import datetime
import gspread
from oauth2client.service_account import ServiceAccountCredentials
import json
import os

def registra_snapshot_giornaliero():
    today = datetime.date.today().isoformat()
    print(f"[INFO] Data di oggi: {today}")

    # Carica credenziali da variabile d'ambiente
    creds_dict = json.loads(os.environ["GOOGLE_CREDS_JSON"])
    creds = ServiceAccountCredentials.from_json_keyfile_dict(creds_dict, [
        "https://spreadsheets.google.com/feeds",
        "https://www.googleapis.com/auth/spreadsheets",
        "https://www.googleapis.com/auth/drive"
    ])

    client = gspread.authorize(creds)

    sheet_commesse = client.open("GestioneCommesse").worksheet("Commesse")
    sheet_storico = client.open("GestioneCommesse").worksheet("Storico Occupazione")

    commesse = sheet_commesse.get_all_records()
    print(f"[INFO] Trovate {len(commesse)} commesse.")

    for comm in commesse:
        ingresso = comm.get("Data Ingresso", "")
        uscita = comm.get("Uscita Reale", "")
        codice = comm.get("Codice Commessa", "Sconosciuto")

        print(f"[DEBUG] {codice}: Ingresso='{ingresso}' | Uscita='{uscita}'")

        if not ingresso:
            print(f"[SKIP] Nessuna data di ingresso per {codice}")
            continue

        try:
            ingresso = datetime.datetime.strptime(ingresso, "%Y-%m-%d").date()
        except:
            print(f"[ERROR] Formato ingresso non valido per {codice}: {ingresso}")
            continue

        oggi = datetime.date.today()
        uscita_dt = None
        if uscita:
            try:
                uscita_dt = datetime.datetime.strptime(uscita, "%Y-%m-%d").date()
            except:
                print(f"[WARN] Uscita non valida per {codice}: {uscita}")

        if ingresso <= oggi and (not uscita_dt or oggi < uscita_dt):
            mq = int(comm["MQ Occupati"])
            cliente = comm["Cliente"]
            sheet_storico.append_row([str(today), codice, cliente, mq])
            print(f"[OK] Registrata: {codice} - {mq} m²")

if __name__ == "__main__":
    registra_snapshot_giornaliero()
