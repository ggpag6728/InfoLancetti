import streamlit as st
import time
from curl_cffi import requests as requests_cffi
import requests
from typing import List, Dict, Any
from dataclasses import dataclass
from datetime import datetime
from zoneinfo import ZoneInfo

# --- CONFIGURAZIONE PAGINA STREAMLIT ---
st.set_page_config(page_title="Monitor Trasporti Milano", page_icon="🚆", layout="wide")

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
        for treno in treni_json[:8]: # Mostriamo i prossimi 8 treni
            destinazione = treno.get("destinazione", "N/D")
            binario = (treno.get("binarioEffettivoPartenzaDescrizione") or 
                       treno.get("binarioProgrammatoPartenzaDescrizione") or "N/D")
            treni_monitor.append({
                "linea": MAPPA_LINEE_S.get(destinazione, "REG"),
                "destinazione": destinazione,
                "orario": treno.get("compOrarioPartenza", "N/D"),
                "ritardo": treno.get("ritardo", 0),
                "binario": binario
            })
        return treni_monitor
    except Exception as e:
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
                "linea": dati_linea.get("LineCode", "N/D"),
                "destinazione": dati_linea.get("LineDescription", "N/D"),
                "attesa": bus.get("WaitMessage", "N/D")
            })
        return bus_monitor
    except:
        return []

# --- INTERFACCIA WEB STREAMLIT ---
st.title("🏙️ Monitor Trasporti Milano")
st.caption(f"Ultimo aggiornamento: {datetime.now(ZoneInfo('Europe/Rome')).strftime('%H:%M:%S')}")

# Creiamo due colonne per affiancare Treni e Bus su schermi grandi
col_treni, col_bus = st.columns(2)

with col_treni:
    st.header("🚆 Treni (Milano Lancetti)")
    treni_data = get_treni("S01643")
    
    if treni_data:
        for t in treni_data:
            # Box per ogni treno
            with st.container(border=True):
                ritardo_val = t['ritardo']
                colore_ritardo = "red" if ritardo_val > 0 else "green"
                testo_ritardo = f"+{ritardo_val}'" if ritardo_val > 0 else "In orario"
                
                st.markdown(f"### {t['linea']} ➔ {t['destinazione']}")
                st.markdown(f"**🕒 Orario:** {t['orario']} | **🛤️ Binario:** {t['binario']} | **⏱️ Stato:** :{colore_ritardo}[{testo_ritardo}]")
    else:
        st.warning("Nessun treno trovato o errore di connessione.")

with col_bus:
    st.header("🚌 Bus & Filobus")
    
    with requests_cffi.Session(impersonate="chrome110") as s:
        s.get("https://giromilano.atm.it/", headers=HEADERS_ATM) # Validazione sessione
        
        for fermata in fermate_atm:
            st.subheader(f"🚏 {fermata.nome_identificativo}")
            buses_data = get_atm(fermata, s)
            
            if buses_data:
                for b in buses_data:
                    # Colora l'attesa se è "in arrivo"
                    attesa = b['attesa']
                    if "in arrivo" in attesa.lower():
                        attesa_formattata = f":green[**{attesa}**]"
                    elif "min" in attesa.lower():
                        attesa_formattata = f":orange[**{attesa}**]"
                    else:
                        attesa_formattata = attesa

                    st.markdown(f"**{b['linea']}** {b['destinazione']} ➔ {attesa_formattata}")
            else:
                st.write("*Nessun dato per questa fermata.*")
            st.divider()

# Logica di auto-aggiornamento ogni 60 secondi
time.sleep(60)
st.rerun()