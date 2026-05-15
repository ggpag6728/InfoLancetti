import streamlit as st
import time
from curl_cffi import requests as requests_cffi
import requests
from typing import List, Dict, Any
from dataclasses import dataclass
from datetime import datetime
from zoneinfo import ZoneInfo

# --- CONFIGURAZIONE PAGINA STREAMLIT ---
# Layout "wide" per sfruttare tutto lo schermo come un vero monitor
st.set_page_config(page_title="Tabellone Trasporti", page_icon="🚆", layout="wide")

# --- BACKEND LOGIC ---
MAPPA_LINEE_S = {
    "VARESE": "S5", "TREVIGLIO": "S5",
    "NOVARA": "S6", "PIOLTELLO LIMITO": "S6",
    "LODI": "S1", "SARONNO": "S1", 
    "SEVESO": "S2", "MILANO ROGOREDO": "S2",
    "PAVIA": "S13", "MELEGNANO": "S12",
    "MILANO BOVISA POLITECNICO": "S13" 
}

@dataclass
class FermataAtm:
    nome_identificativo: str
    poi_id: str 

HEADERS_ATM = {
    'accept': 'application/json, text/plain, */*',
    'accept-language': 'it-IT,it;q=0.9,en-US;q=0.8,en;q=0.7',
    'referer': 'https://giromilano.atm.it/'
}

fermate_atm = [
    FermataAtm(nome_identificativo="90 Jenner -> Lodi", poi_id="5641332"),
    FermataAtm(nome_identificativo="91 Jenner -> Lotto", poi_id="5641333"),
    FermataAtm(nome_identificativo="92 Lancetti -> Bovisa", poi_id="5641319"),
    FermataAtm(nome_identificativo="92 Lancetti -> Lodi", poi_id="5644379")
]

def get_treni(codice_stazione: str) -> List[Dict[str, Any]]:
    dt_rome = datetime.now(ZoneInfo("Europe/Rome"))
    orario_attuale = dt_rome.strftime("%a %b %d %Y %H:%M:%S GMT%z")
    url = f"http://www.viaggiatreno.it/infomobilita/resteasy/viaggiatreno/partenze/{codice_stazione}/{orario_attuale}"
    try:
        response = requests.get(url, timeout=10)
        if response.status_code != 200: return []
        treni_json = response.json()
        treni_monitor = []
        for treno in treni_json[:5]:
            destinazione = treno.get("destinazione", "N/D")
            binario = (treno.get("binarioEffettivoPartenzaDescrizione") or 
                       treno.get("binarioProgrammatoPartenzaDescrizione") or "-")
            treni_monitor.append({
                "linea": MAPPA_LINEE_S.get(destinazione, "REG"),
                "destinazione": destinazione,
                "orario": treno.get("compOrarioPartenza", "--:--"),
                "ritardo": treno.get("ritardo", 0),
                "binario": binario
            })
        return treni_monitor
    except:
        return []

def get_atm(fermata: FermataAtm, session: requests_cffi.Session) -> List[Dict[str, Any]]:
    url = f"https://giromilano.atm.it/proxy.tpportal/api/tpPortal/geodata/pois/{fermata.poi_id}?lang=it"
    try:
        response = session.get(url, headers=HEADERS_ATM)
        if response.status_code != 200: return []
        fermata_json = response.json()
        nome_fermata = fermata_json.get("Description", fermata.nome_identificativo)
        bus_monitor = []
        for bus in fermata_json.get("Lines", []):
            dati_linea = bus.get("Line", {})
            bus_monitor.append({
                "fermata": nome_fermata,
                "linea": dati_linea.get("LineCode", "-"),
                "destinazione": dati_linea.get("LineDescription", "N/D"),
                "attesa": bus.get("WaitMessage", "-")
            })
        return bus_monitor
    except:
        return []

# --- INTERFACCIA WEB STREAMLIT (STILE TABELLONE) ---
ora_attuale = datetime.now(ZoneInfo('Europe/Rome')).strftime('%H:%M:%S')

# Intestazione Monitor
col_titolo, col_ora = st.columns([3, 1])
with col_titolo:
    st.title("🏙️ Monitor Partenze")
with col_ora:
    st.markdown(f"<h3 style='text-align: right; color: gray;'>🕒 {ora_attuale}</h3>", unsafe_allow_html=True)

st.markdown("<br>", unsafe_allow_html=True)

# ==========================================
# SEZIONE TRENI
# ==========================================
st.subheader("🚆 Treni in partenza da Milano Lancetti")
treni_data = get_treni("S01643")

if treni_data:
    # Intestazione Colonne Tabellone Treni
    h1, h2, h3, h4, h5 = st.columns([1, 3, 1, 1, 1])
    h1.markdown("**Treno**")
    h2.markdown("**Destinazione**")
    h3.markdown("**Binario**")
    h4.markdown("**Orario**")
    h5.markdown("**Stato**")
    st.markdown("---") # Linea di demarcazione spessa
    
    # Righe Dati Treni
    for t in treni_data:
        c1, c2, c3, c4, c5 = st.columns([1, 3, 1, 1, 1])
        
        c1.markdown(f"### {t['linea']}")
        c2.markdown(f"#### {t['destinazione']}")
        c3.markdown(f"#### {t['binario']}")
        c4.markdown(f"#### {t['orario']}")
        
        # Gestione colori ritardo
        ritardo_val = t['ritardo']
        if ritardo_val > 0:
            c5.markdown(f"#### :red[+{ritardo_val}']")
        else:
            c5.markdown("#### :green[In orario]")
            
        st.divider() # Linea di separazione sottile
else:
    st.warning("Nessun treno trovato o errore di connessione.")

st.markdown("<br><br>", unsafe_allow_html=True)

# ==========================================
# SEZIONE BUS ATM
# ==========================================
st.subheader("🚌 Partenze Bus & Filobus")

with requests_cffi.Session(impersonate="chrome110") as s:
    s.get("https://giromilano.atm.it/", headers=HEADERS_ATM) # Validazione sessione
    
    for fermata in fermate_atm:
        st.markdown(f"**🚏 {fermata.nome_identificativo}**")
        buses_data = get_atm(fermata, s)
        
        if buses_data:
            # Intestazione Colonne Tabellone Bus
            bh1, bh2, bh3 = st.columns([1, 4, 2])
            bh1.markdown("**Linea**")
            bh2.markdown("**Destinazione**")
            bh3.markdown("**Attesa**")
            st.markdown("---")
            
            # Righe Dati Bus
            for b in buses_data:
                bc1, bc2, bc3 = st.columns([1, 4, 2])
                
                bc1.markdown(f"### {b['linea']}")
                bc2.markdown(f"#### {b['destinazione']}")
                
                # Gestione colori attesa
                attesa = b['attesa']
                if "in arrivo" in attesa.lower():
                    bc3.markdown(f"#### :green[{attesa}]")
                elif "min" in attesa.lower():
                    bc3.markdown(f"#### :orange[{attesa}]")
                else:
                    bc3.markdown(f"#### {attesa}")
                    
                st.divider()
        else:
            st.write("*Nessun dato per questa fermata.*")
            st.divider()

# Logica di auto-aggiornamento ogni 60 secondi
time.sleep(60)
st.rerun()
