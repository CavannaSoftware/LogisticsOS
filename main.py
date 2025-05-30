import streamlit as st
import matplotlib.pyplot as plt
from matplotlib.patches import Rectangle, Polygon
from matplotlib.path import Path
import datetime
import gspread
from oauth2client.service_account import ServiceAccountCredentials
import streamlit_authenticator as stauth
import os
import json

# === CREA IL FILE DI CREDENZIALI SE NON ESISTE ===
if not os.path.exists("streamlit-credentials.json"):
    creds_str = os.environ.get("GOOGLE_CREDS_JSON")
    if creds_str:
        with open("streamlit-credentials.json", "w") as f:
            f.write(creds_str)
    else:
        raise Exception("Variabile d'ambiente GOOGLE_CREDS_JSON non trovata")


def calcola_costo_commessa(codice_commessa, prezzo_mq_giorno=1.5):
    sheet_storico = gspread.authorize(ServiceAccountCredentials.from_json_keyfile_name(CREDENTIALS_FILE, [
        "https://spreadsheets.google.com/feeds",
        "https://www.googleapis.com/auth/spreadsheets",
        "https://www.googleapis.com/auth/drive"
    ])).open(SHEET_NAME).worksheet("Storico Occupazione")

    storico = sheet_storico.get_all_records()
    totale = 0
    giorni = 0

    for r in storico:
        if r["Codice Commessa"] == codice_commessa:
            mq = int(r["MQ Occupati"])
            totale += mq * prezzo_mq_giorno
            giorni += 1

    return totale, giorni


def registra_snapshot_giornaliero():
    today = datetime.date.today().isoformat()

    # Autorizzazione e accesso al foglio
    sheet_storico = gspread.authorize(ServiceAccountCredentials.from_json_keyfile_name(CREDENTIALS_FILE, [
        "https://spreadsheets.google.com/feeds",
        "https://www.googleapis.com/auth/spreadsheets",
        "https://www.googleapis.com/auth/drive"
    ])).open(SHEET_NAME).worksheet("Storico Occupazione")

    commesse = get_commesse()

    for comm in commesse:
        ingresso_raw = comm.get("Data Ingresso", "").strip()
        uscita_raw = comm.get("Uscita Reale", "").strip()

        # Se manca la data di ingresso, salta
        if not ingresso_raw:
            continue

        try:
            ingresso = datetime.datetime.strptime(ingresso_raw, "%Y-%m-%d").date()
        except ValueError:
            st.warning(f"⚠️ Formato data non valido per ingresso: '{ingresso_raw}'")
            continue

        uscita_dt = None
        if uscita_raw:
            try:
                uscita_dt = datetime.datetime.strptime(uscita_raw, "%Y-%m-%d").date()
            except ValueError:
                st.warning(f"⚠️ Formato data non valido per uscita: '{uscita_raw}'")
                continue

        oggi = datetime.date.today()

        if ingresso <= oggi and (not uscita_dt or oggi < uscita_dt):
            try:
                mq = int(comm["MQ Occupati"])
                codice = comm["Codice Commessa"]
                cliente = comm["Cliente"]
                sheet_storico.append_row([today, codice, cliente, mq])
                print(f"[OK] Registrata: {codice} - {mq} m²")
            except Exception as e:
                st.warning(f"Errore nel salvataggio: {e}")



def calcola_spazio_disponibile_per_settore(commesse, settore, capannone):
    # Calcola area settore
    superficie = 0
    for s in SETTORI_DEF.get(capannone, []):
        if s["label"] == settore:
            superficie = s["w"] * s["h"]
    for s in SETTORI_L.get(capannone, []):
        if s["label"] == settore:
            points = s["points"]
            xs, ys = zip(*points)
            superficie = 0.5 * abs(sum(xs[i] * ys[i+1] - xs[i+1] * ys[i] for i in range(-1, len(points)-1)))

    # Totale mq già occupati nel settore
    occupata = sum(
        int(c["MQ Occupati"])
        for c in commesse
        if c["Settore"] == settore and c["Capannone"] == capannone and not c["Uscita Reale"]
    )

    return superficie - occupata


def aggiorna_settore_commessa(codice_commessa, nuovo_settore):
    sheet = gspread.authorize(ServiceAccountCredentials.from_json_keyfile_name(CREDENTIALS_FILE, [
        "https://spreadsheets.google.com/feeds",
        "https://www.googleapis.com/auth/spreadsheets",
        "https://www.googleapis.com/auth/drive"
    ])).open(SHEET_NAME).worksheet("Commesse")
    records = sheet.get_all_records()
    for idx, row in enumerate(records):
        if row["Codice Commessa"] == codice_commessa:
            sheet.update_cell(idx + 2, 4, nuovo_settore)  # colonna 4 = Settore
            break





# === CONFIGURAZIONE GOOGLE SHEET ===
SHEET_NAME = "GestioneCommesse"
SHEET_TAB = "Utenti"
CREDENTIALS_FILE = "streamlit-credentials.json"

# === DEFINIZIONE VISUAL SETTORI ===
SETTORI_DEF = {
    "Capannone Principale": [
        {"label": "1B", "x": 25, "y": 20, "w": 25, "h": 20},
        {"label": "2A", "x": 0, "y": 0, "w": 9, "h": 20},
        {"label": "2B", "x": 25, "y": 0, "w": 6, "h": 20},
        {"label": "3B", "x": 41, "y": 0, "w": 9, "h": 20}
    ],
    "Capannone Secondario": [
        {"label": "1B", "x": 0, "y": 15, "w": 25, "h": 25},
        {"label": "2B", "x": 0, "y": 0, "w": 6, "h": 15},
        {"label": "3B", "x": 16, "y": 0, "w": 9, "h": 15}
    ]
}

SETTORI_L = {
    "Capannone Principale": [
        {"label": "3A", "points": [(19, 0), (25, 0), (25, 20), (9, 20), (9, 15), (19, 15)]},
        {"label": "1A", "points": [(0, 20), (25, 20), (25, 40), (5, 40), (5, 33), (0, 33)]}
    ]
}

# === LOGIN ===
def connect_sheet():
    scope = [
        "https://spreadsheets.google.com/feeds",
        "https://www.googleapis.com/auth/spreadsheets",
        "https://www.googleapis.com/auth/drive"
    ]
    creds = ServiceAccountCredentials.from_json_keyfile_name(CREDENTIALS_FILE, scope)
    client = gspread.authorize(creds)
    return client.open(SHEET_NAME).worksheet(SHEET_TAB)

def load_users():
    sheet = connect_sheet()
    users_data = sheet.get_all_records()
    credentials = {"usernames": {}}

    for user in users_data:
        email = user['Email'].strip().lower()
        credentials["usernames"][email] = {
            "name": user['Nome'],
            "password": user['Password']
        }
    return credentials

def load_commesse():
    sheet = gspread.authorize(ServiceAccountCredentials.from_json_keyfile_name(CREDENTIALS_FILE, [
        "https://spreadsheets.google.com/feeds",
        "https://www.googleapis.com/auth/spreadsheets",
        "https://www.googleapis.com/auth/drive"
    ])).open(SHEET_NAME).worksheet("Commesse")
    return sheet.get_all_records()


@st.cache_data(ttl=60)
def get_commesse():
    return load_commesse()

@st.cache_data(ttl=60)
def get_users_data():
    sheet = connect_sheet()
    return sheet.get_all_records()


def salva_commessa(dati_commessa):
    sheet = gspread.authorize(ServiceAccountCredentials.from_json_keyfile_name(CREDENTIALS_FILE, [
        "https://spreadsheets.google.com/feeds",
        "https://www.googleapis.com/auth/spreadsheets",
        "https://www.googleapis.com/auth/drive"
    ])).open(SHEET_NAME).worksheet("Commesse")
    sheet.append_row(dati_commessa)

# === AGGIORNAMENTO COMMESSA ===
def aggiorna_commessa(codice_commessa, nuovo_stato, nuova_uscita, nuove_note):
    sheet = gspread.authorize(ServiceAccountCredentials.from_json_keyfile_name(CREDENTIALS_FILE, [
        "https://spreadsheets.google.com/feeds",
        "https://www.googleapis.com/auth/spreadsheets",
        "https://www.googleapis.com/auth/drive"
    ])).open(SHEET_NAME).worksheet("Commesse")
    records = sheet.get_all_records()
    for idx, row in enumerate(records):
        if row["Codice Commessa"] == codice_commessa:
            sheet.update_cell(idx + 2, 9, nuova_uscita)   # Uscita Reale
            sheet.update_cell(idx + 2, 10, nuovo_stato)   # Stato Imballo
            sheet.update_cell(idx + 2, 11, nuove_note)    # Note
            break

# === POSIZIONAMENTO COMMESSE ===
def posiziona_commesse(ax, commesse, scelta):
    text_centroids = {}
    grid_size = 1  # ogni cella è 1m²
    non_inserite = []

    # === SETTORI RETTANGOLARI ===
    for settore in SETTORI_DEF.get(scelta, []):
        cols = int(settore["w"] / grid_size)
        rows = int(settore["h"] / grid_size)
        grid = [[None for _ in range(rows)] for _ in range(cols)]
        commesse_settore = [c for c in commesse if c["Settore"] == settore["label"] and c["Capannone"] == scelta]

        for comm in commesse_settore:
            codice_raw = comm["Codice Commessa"]
            codice = codice_raw + "-" + settore["label"]  # rende unico il codice per disegno
            mq = int(comm["MQ Occupati"])
            piazzati = 0
            for i in range(cols):
                for j in range(rows):
                    if grid[i][j] is None and piazzati < mq:
                        grid[i][j] = codice
                        x = settore["x"] + i * grid_size
                        y = settore["y"] + j * grid_size
                        ax.add_patch(Rectangle((x, y), grid_size, grid_size, facecolor='red', edgecolor='black', linewidth=0.2))
                        if codice not in text_centroids:
                            text_centroids[codice] = []
                        text_centroids[codice].append((x + 0.5, y + 0.5))
                        piazzati += 1
                if piazzati >= mq:
                    break
            if piazzati < mq:
                st.warning(f"Commessa {codice_raw} parzialmente inserita in {settore['label']} ({piazzati}/{mq} m²)")
                comm["MQ Piazzati"] = piazzati
                non_inserite.append(comm)

    # === SETTORI A FORMA LIBERA ===
    for settore in SETTORI_L.get(scelta, []):
        bounds = settore["points"]
        path = Path(bounds)
        min_x = min(p[0] for p in bounds)
        max_x = max(p[0] for p in bounds)
        min_y = min(p[1] for p in bounds)
        max_y = max(p[1] for p in bounds)

        available_cells = []
        for x in range(int(min_x), int(max_x)):
            for y in range(int(min_y), int(max_y)):
                # più tollerante nei bordi
                if path.contains_point((x + 0.5, y + 0.5), radius=-0.1):
                    available_cells.append((x, y))

        commesse_settore = [c for c in commesse if c["Settore"] == settore["label"] and c["Capannone"] == scelta]
        used = set()

        for comm in commesse_settore:
            codice_raw = comm["Codice Commessa"]
            mq = int(comm["MQ Occupati"])  # questa riga PRIMA
            codice = f"{codice_raw}-{settore['label']}-{mq}"  # ora funziona

            piazzati = 0
            for cell in available_cells:
                if cell not in used and piazzati < mq:
                    x, y = cell
                    ax.add_patch(Rectangle((x, y), 1, 1, facecolor='red', edgecolor='black', linewidth=0.2))
                    if codice not in text_centroids:
                        text_centroids[codice] = []
                    text_centroids[codice].append((x + 0.5, y + 0.5))
                    used.add(cell)
                    piazzati += 1
            if piazzati < mq:
                st.warning(f"Commessa {codice_raw} parzialmente inserita in {settore['label']} ({piazzati}/{mq} m²)")
                comm["MQ Piazzati"] = piazzati
                non_inserite.append(comm)

    return text_centroids, non_inserite



# === MAIN APP ===
def main_app(name, username):
    st.sidebar.success(f"Utente: {name}")
    authenticator.logout("Logout", "sidebar")

    if "login_timestamp_updated" not in st.session_state:
        users_data = get_users_data()
        for i, user in enumerate(users_data):
            if user['Email'].strip().lower() == username:
                now = datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S")
                sheet = connect_sheet()
                sheet.update_cell(i + 2, 6, now)
                st.session_state["login_timestamp_updated"] = True
                break


    st.title("Gestione Magazzino - Mappa Capannoni")

    scelta = st.selectbox("Seleziona il capannone:", ["Capannone Principale", "Capannone Secondario"])
    commesse = get_commesse()

    with st.sidebar.expander("✏️ Modifica commessa"):
        codici = [c["Codice Commessa"] for c in commesse if c["Codice Commessa"]]
        codice_scelto = st.selectbox("Seleziona commessa", codici)

        comm = next((c for c in commesse if c["Codice Commessa"] == codice_scelto), None)
        if comm:
            nuovo_stato = st.selectbox("Stato Imballo", ["Da Imballare", "Imballato"],
                                       index=["Da Imballare", "Imballato"].index(comm["Stato Imballo"]),
                                       key="modifica_stato_imballo")

            nuovo_settore = st.selectbox("Settore", ["1A", "1B", "2A", "2B", "3A", "3B"],
                                         index=["1A", "1B", "2A", "2B", "3A", "3B"].index(comm["Settore"]),
                                         key="modifica_settore")

            uscita_ok = st.checkbox("✔️ Uscita effettuata", value=bool(comm["Uscita Reale"]))
            if uscita_ok:
                uscita_reale = st.date_input("Data di uscita", value=datetime.datetime.strptime(comm["Uscita Reale"],
                                                                                                "%Y-%m-%d").date() if
                comm["Uscita Reale"] else datetime.date.today())
            else:
                uscita_reale = ""

            nuove_note = st.text_area("Note", value=comm["Note"], key="modifica_note")

            if st.button("Aggiorna commessa"):
                aggiorna_commessa(codice_scelto, nuovo_stato, str(uscita_reale), nuove_note)
                # aggiorna anche il settore se è cambiato
                if nuovo_settore != comm["Settore"]:
                    aggiorna_settore_commessa(codice_scelto, nuovo_settore)
                st.success("Commessa aggiornata.")

    with st.sidebar.expander("➕ Inserisci nuova commessa"):
        codice = st.text_input("Codice Commessa")
        cliente = st.text_input("Cliente")
        settore = st.selectbox("Settore", ["1A", "1B", "2A", "2B", "3A", "3B"])
        capannone = st.selectbox("Capannone", ["Capannone Principale", "Capannone Secondario"])
        mq = st.number_input("Metri Quadri Occupati", min_value=1)
        ingresso = st.date_input("Data Ingresso")
        uscita_prevista = st.date_input("Uscita Prevista")
        uscita_reale = ""
        stato_imballo = st.selectbox("Stato Imballo", ["Da Imballare", "Imballato"])
        note = st.text_area("Note", key="inserimento_note")

        if st.button("Salva Commessa", key="salva_commessa"):
            totale_mq = mq
            settore_corrente = settore
            capannone_corrente = capannone
            codice_commessa = codice
            cliente_commessa = cliente
            ingresso_str = str(ingresso)
            uscita_prevista_str = str(uscita_prevista)
            uscita_reale_str = ""
            stato = stato_imballo
            note_commessa = note

            settori_disponibili = ["1A", "1B", "2A", "2B", "3A", "3B"]
            settori_disponibili.remove(settore_corrente)
            settori_check = [settore_corrente] + settori_disponibili
            commesse_attuali = load_commesse()

            for settore_dest in settori_check:
                spazio = calcola_spazio_disponibile_per_settore(commesse_attuali, settore_dest, capannone_corrente)
                if spazio <= 0:
                    continue
                mq_da_inserire = min(totale_mq, int(spazio))
                nuova_commessa = [
                    "", codice_commessa, cliente_commessa, settore_dest, capannone_corrente,
                    mq_da_inserire, ingresso_str, uscita_prevista_str, uscita_reale_str,
                    stato, note_commessa
                ]
                salva_commessa(nuova_commessa)

                # 🔁 aggiorna lista per tenere conto del nuovo spazio occupato
                commesse_attuali.append({
                    "Codice Commessa": codice_commessa,
                    "Cliente": cliente_commessa,
                    "Settore": settore_dest,
                    "Capannone": capannone_corrente,
                    "MQ Occupati": mq_da_inserire,
                    "Data Ingresso": ingresso_str,
                    "Uscita Prevista": uscita_prevista_str,
                    "Uscita Reale": uscita_reale_str,
                    "Stato Imballo": stato,
                    "Note": note_commessa
                })

                totale_mq -= mq_da_inserire
                if totale_mq <= 0:
                    break

            if totale_mq > 0:
                st.warning(
                    f"Attenzione: non c'è spazio sufficiente per tutta la commessa. Mancano ancora {totale_mq} m².")
            else:
                st.success("Commessa salvata correttamente!")


    @st.cache_data
    def genera_figura(commesse_attive, scelta):
        fig, ax = plt.subplots(figsize=(12, 7))
        capannone_color = 'skyblue'

        if scelta == "Capannone Principale":
            ax.set_xlim(0, 50)
            ax.set_ylim(0, 40)
            ax.add_patch(Rectangle((0, 0), 50, 40, facecolor=capannone_color))
            ax.add_patch(Rectangle((0, 33), 5, 7, facecolor='green'))
            ax.add_patch(Rectangle((9, 0), 10, 15, facecolor='gold'))
            ax.add_patch(Rectangle((31, 0), 10, 20, facecolor='gold'))
        elif scelta == "Capannone Secondario":
            ax.set_xlim(0, 25)
            ax.set_ylim(0, 40)
            ax.add_patch(Rectangle((0, 0), 25, 40, facecolor=capannone_color))
            ax.add_patch(Rectangle((6, 0), 10, 15, facecolor='gold'))

        for settore in SETTORI_DEF.get(scelta, []):
            ax.add_patch(Rectangle((settore["x"], settore["y"]), settore["w"], settore["h"], fill=False, edgecolor="black", linewidth=2))
            ax.text(settore["x"] + settore["w"] / 2, settore["y"] + settore["h"] / 2, settore["label"], ha="center", va="center", fontsize=12, weight="bold")

        for settore in SETTORI_L.get(scelta, []):
            poly = Polygon(settore["points"], closed=True, facecolor=capannone_color, edgecolor='black', linewidth=2)
            ax.add_patch(poly)
            xs, ys = zip(*settore["points"])
            centro_x = sum(xs) / len(xs)
            centro_y = sum(ys) / len(ys)
            if settore["label"] == "1A":
                centro_x += 5
            elif settore["label"] == "3A":
                centro_x += 3  # Sposta verso destra
            ax.text(centro_x, centro_y, settore["label"], ha='center', va='center', fontsize=12, weight='bold')

        # Filtro: solo commesse attive (senza data di uscita)
        commesse_attive = [c for c in commesse if not c["Uscita Reale"]]
        text_centroids, non_inserite = posiziona_commesse(ax, commesse_attive, scelta)

        for codice, points in text_centroids.items():
            cx = sum(p[0] for p in points) / len(points)
            cy = sum(p[1] for p in points) / len(points)
            ax.text(cx, cy, codice, ha='center', va='center', fontsize=6, color='white', weight='bold')

        for codice, points in text_centroids.items():
            cx = sum(p[0] for p in points) / len(points)
            cy = sum(p[1] for p in points) / len(points)
            ax.text(cx, cy, codice, ha='center', va='center', fontsize=6, color='white', weight='bold')

        ax.set_aspect('equal')
        return fig


    
    fig = genera_figura(commesse_attive, scelta)
    st.pyplot(fig)





    
    # === CALCOLO SPAZI ===
    superficie_totale = 0
    for settore in SETTORI_DEF.get(scelta, []):
        superficie_totale += settore["w"] * settore["h"]
    for settore in SETTORI_L.get(scelta, []):
        points = settore["points"]
        xs, ys = zip(*points)
        superficie_l = 0.5 * abs(sum(xs[i] * ys[i + 1] - xs[i + 1] * ys[i] for i in range(-1, len(points) - 1)))
        superficie_totale += superficie_l

    superficie_occupata = sum(
        int(c["MQ Occupati"]) for c in commesse if c["Capannone"] == scelta and not c["Uscita Reale"]
    )

    superficie_disponibile = superficie_totale - superficie_occupata

    st.markdown("---")
    st.subheader("📊 Riepilogo Spazio")
    st.metric("Totale disponibile", f"{int(superficie_totale)} m²")
    st.metric("Occupato", f"{superficie_occupata} m²")
    st.metric("Rimanente", f"{int(superficie_disponibile)} m²")

    if "snapshot_giornaliero" not in st.session_state:
        registra_snapshot_giornaliero()
        st.session_state["snapshot_giornaliero"] = True



# === INIZIO ===
st.set_page_config(layout="wide")

if "authenticator" not in st.session_state:
    credentials = load_users()
    st.session_state.authenticator = stauth.Authenticate(
        credentials,
        cookie_name="cavanna_auth",
        cookie_key="cavanna2025_key",
        cookie_expiry_days=1
    )

authenticator = st.session_state.authenticator

auth_status = st.session_state.get("authentication_status")


if auth_status is None:
    # === LOGO E TITOLO PRIMA DEL LOGIN ===
 from PIL import Image

@st.cache_data
def get_logo():
    return Image.open("logo.png")

st.image(get_logo(), width=350)

 st.markdown("""
<div style='font-size: 28px; font-weight: bold; color: #004080; margin-top: 10px;'>
    Operations System
</div>
""", unsafe_allow_html=True)

if auth_status is None:
    authenticator.login(
        fields={
            'Form name': 'Login',
            'Username': 'Email',
            'Password': 'Password',
            'Login': 'Login'
        }
    )
auth_status = st.session_state.get("authentication_status")
name = st.session_state.get("name")
username = st.session_state.get("username")

if auth_status:
    main_app(name, username)
elif auth_status is False:
    st.error("Credenziali errate.")
else:
    st.warning("Inserisci le credenziali per accedere.")
