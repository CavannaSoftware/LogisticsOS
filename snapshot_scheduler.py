import datetime
import gspread
from oauth2client.service_account import ServiceAccountCredentials

# === CONFIG ===
SHEET_NAME = "GestioneCommesse"
CREDENTIALS_FILE = "streamlit-credentials.json"

def registra_snapshot_giornaliero():
    today = datetime.date.today().isoformat()

    # Autenticazione
    creds = ServiceAccountCredentials.from_json_keyfile_name(CREDENTIALS_FILE, [
        "https://spreadsheets.google.com/feeds",
        "https://www.googleapis.com/auth/spreadsheets",
        "https://www.googleapis.com/auth/drive"
    ])
    client = gspread.authorize(creds)

    sheet_commesse = client.open(SHEET_NAME).worksheet("Commesse")
    sheet_storico = client.open(SHEET_NAME).worksheet("Storico Occupazione")

    commesse = sheet_commesse.get_all_records()

    for comm in commesse:
        uscita = comm.get("Uscita Reale", "")
        ingresso = comm.get("Ingresso", "")
        if not ingresso:
            print(f"[SKIP] Nessuna data di ingresso per {comm['Codice Commessa']}")
            continue

        ingresso = datetime.datetime.strptime(ingresso, "%Y-%m-%d").date()
        oggi = datetime.date.today()
        uscita_dt = None
        if uscita:
            uscita_dt = datetime.datetime.strptime(uscita, "%Y-%m-%d").date()

        if ingresso <= oggi and (not uscita_dt or oggi < uscita_dt):
            mq = int(comm["MQ Occupati"])
            codice = comm["Codice Commessa"]
            cliente = comm["Cliente"]
            sheet_storico.append_row([str(today), codice, cliente, mq])
            print(f"[OK] Registrata: {codice} - {mq} m²")

    print(f"Snapshot salvato per il {today}")

if __name__ == "__main__":
    registra_snapshot_giornaliero()
