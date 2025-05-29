import datetime
import gspread
from oauth2client.service_account import ServiceAccountCredentials

def registra_snapshot_giornaliero():
    today = datetime.date.today().isoformat()

    creds = ServiceAccountCredentials.from_json_keyfile_name("creds.json", [
        "https://spreadsheets.google.com/feeds",
        "https://www.googleapis.com/auth/spreadsheets",
        "https://www.googleapis.com/auth/drive"
    ])
    client = gspread.authorize(creds)

    sheet_commesse = client.open("GestioneCommesse").worksheet("Commesse")
    sheet_storico = client.open("GestioneCommesse").worksheet("Storico Occupazione")

    commesse = sheet_commesse.get_all_records()

    for comm in commesse:
        ingresso = comm.get("Data Ingresso", "")
        uscita = comm.get("Uscita Reale", "")
        if not ingresso:
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

if __name__ == "__main__":
    registra_snapshot_giornaliero()

