import streamlit as st
import time
from curl_cffi import requests as requests_cffi
import requests
from typing import List, Dict, Any
from dataclasses import dataclass
from datetime import datetime
from zoneinfo import ZoneInfo

# --- CONFIGURAZIONE PAGINA ---
st.set_page_config(page_title="Info Milano Lancetti", layout="wide", initial_sidebar_state="collapsed")

# --- CSS PERSONALIZZATO (Il motore del nuovo design) ---
st.markdown("""
<link href="https://fonts.googleapis.com/css2?family=Material+Symbols+Rounded:opsz,wght,FILL,GRAD@24,400,1,0" rel="stylesheet" />
<style>
    /* Forza lo sfondo chiaro su tutta l'app */
    .stApp {
        background-color: #f3f4f6;
    }
    
    /* Nasconde l'header di default di Streamlit per fare più spazio */
    header {visibility: hidden;}
    
    /* Stile della singola riga (Card) */
    .transport-row {
        background-color: #ffffff;
        border-radius: 8px;
        padding: 12px 20px;
        margin-bottom: 8px; /* Spazio ridotto tra le righe */
        display: flex;
        align-items: center;
        box-shadow: 0 1px 2px rgba(0,0,0,0.05);
        font-family: -apple-system, BlinkMacSystemFont, "Segoe UI", Roboto, Helvetica, Arial, sans-serif;
        border: 1px solid #e5e7eb;
    }
    
    /* Stile per le icone moderne */
    .icon {
        font-family: 'Material Symbols Rounded';
        font-size: 28px;
        color: #6b7280;
        margin-right: 16px;
    }
    
    /* Stile dei testi */
    .line-name {
        font-weight: 700;
        font-size: 18px;
        width: 80px;
        color: #111827;
    }
    .destination {
        flex-grow: 1;
        font-weight: 600;
        font-size: 16px;
        color: #374151;
    }
    .details {
        display: flex;
        gap: 30px;
        font-size: 15px;
        color: #4b5563;
        align-items: center;
    }
    
    /* Colori degli stati (Ritardi/Attese) */
    .status-good { color: #059669; font-weight: 700; background: #d1fae5; padding: 4px 8px; border-radius: 4px; }
    .status-bad { color: #dc2626; font-weight: 700; background: #fee2e2; padding: 4px 8px; border-radius: 4px; }
    .status-wait { color: #d97706; font-weight: 700; background: #fef3c7; padding: 4px 8px; border-radius: 4px; }
    .status-neutral { color: #374151; font-weight: 600; }
    
    /* Intestazioni di sezione */
    .section-title {
        font-family: -apple-system, BlinkMacSystemFont, "Segoe UI", Roboto;
        color: #111827;
        margin-top: 20px;
        margin-bottom: 15px;
        font-size: 22px;
        display: flex;
        align-items: center;
        gap: 10px;
    }
</style>
""", unsafe_allow_html=True)

# --- BACKEND LOGIC (Invariato) ---
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
    FermataAtm(nome_identificativo="92 Lancetti -> Bovisa", poi_id="5641319"),
    FermataAtm(nome_identificativo="92 Lancetti -> Lodi", poi_id="5644379"),
    FermataAtm(nome_identificativo="90 Jenner -> Lodi", poi_id="5641332"),
    FermataAtm(nome_identificativo="91 Jenner -> Lotto", poi_id="5641333")
]


def get_treni(codice_stazione: str) -> List[Dict[str, Any]]:
    dt_rome = datetime.now(ZoneInfo("Europe/Rome"))
    orario_attuale = dt_rome.strftime("%a %b %d %Y %H:%M:%S GMT%z")
    url = f"http://www.viaggiatreno.it/infomobilita/resteasy/viaggiatreno/partenze/{codice_stazione}/{orario_attuale}"
    try:
        response = requests.get(url, timeout=10)
        if response.status_code != 200: return []
        treni_json = response.json()

        if not isinstance(treni_json, list):
            return []
        
        treni_monitor = []
        for treno in treni_json:
            arrivato = treno.get("arrivato", False)
            if not arrivato:
                destinazione = treno.get("destinazione", "N/D")
                binario = (treno.get("binarioEffettivoPartenzaDescrizione") or 
                        treno.get("binarioProgrammatoPartenzaDescrizione") or "-")
                treni_monitor.append({
                    "linea": MAPPA_LINEE_S.get(destinazione, "--"),
                    "destinazione": destinazione,
                    "orario": treno.get("compOrarioPartenza", "--:--"),
                    "ritardo": treno.get("ritardo", 0),
                    "binario": binario
                }) 
                if len(treni_monitor) == 5:
                    break 
        return treni_monitor
    except Exception:
        return []

def get_atm(fermata: FermataAtm, session: requests_cffi.Session) -> List[Dict[str, Any]]:
    url = f"https://giromilano.atm.it/proxy.tpportal/api/tpPortal/geodata/pois/{fermata.poi_id}?lang=it"
    try:
        response = session.get(url, headers=HEADERS_ATM, timeout=10)
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
    except Exception:
        return []

# --- INTERFACCIA WEB (HTML GENERATO DINAMICAMENTE) ---
ora_attuale_dt = datetime.now(ZoneInfo('Europe/Rome'))
ora_attuale = ora_attuale_dt.strftime('%H:%M:%S')
ora_corrente = ora_attuale_dt.hour

# Header in HTML
st.markdown(f"""
<div style="display: flex; justify-content: space-between; align-items: center; margin-bottom: 20px;">
    <h1 style="margin: 0; color: #111827; font-family: sans-serif;">Info Milano Lancetti</h1>
    <h3 style="margin: 0; color: #6b7280; font-family: sans-serif;">{ora_attuale}</h3>
</div>
""", unsafe_allow_html=True)


# ==========================================
# CONTROLLI DI ESECUZIONE (Pausa notturna)
# ==========================================

inizio_pausa = 1
fine_pausa = 6
pausa_notturna = inizio_pausa <= ora_corrente < fine_pausa

# Se la pausa è attiva, mostriamo un messaggio, aspettiamo e ricarichiamo la pagina 
# SENZA eseguire il resto del codice (che contiene le chiamate API)
if pausa_notturna:
    st.info(f"🌙 **Sospensione notturna attiva ({inizio_pausa}:00 - {fine_pausa}:00).** Nessuna chiamata API in corso. Il monitoraggio riprenderà in automatico.")
    
    # Aspettiamo 60 secondi e ricarichiamo, così l'orologio in alto avanza e 
    # l'app può "svegliarsi" da sola alle 6:00
    time.sleep(60)
    st.rerun()


# ==========================================
# SEZIONE TRENI
# ==========================================
st.markdown('<div class="section-title"><span class="icon" style="color: #1d4ed8;">train</span> Treni da Lancetti</div>', unsafe_allow_html=True)
treni_data = get_treni("S01643")

if treni_data:
    for t in treni_data:
        ritardo_val = t['ritardo']
        if ritardo_val > 0:
            stato_css = "status-bad"
            stato_txt = f"+{ritardo_val}'"
        else:
            stato_css = "status-good"
            stato_txt = "In orario"
            
        riga_html = f"""
        <div class="transport-row">
            <span class="icon">train</span>
            <div class="line-name">{t['linea']}</div>
            <div class="destination">{t['destinazione']}</div>
            <div class="details">
                <span>Binario <b>{t['binario']}</b></span>
                <span><b>{t['orario']}</b></span>
                <span class="{stato_css}">{stato_txt}</span>
            </div>
        </div>
        """
        st.markdown(riga_html, unsafe_allow_html=True)
else:
    st.info("Nessun treno in partenza.")

# ==========================================
# SEZIONE BUS ATM
# ==========================================
st.markdown('<div class="section-title"><span class="icon" style="color: #047857;">directions_bus</span> Bus & Filobus</div>', unsafe_allow_html=True)

try:
    with requests_cffi.Session(impersonate="chrome110") as s:
        s.get("https://giromilano.atm.it/", headers=HEADERS_ATM, timeout=10)
        
        bus_trovati = False
        for fermata in fermate_atm:
            buses_data = get_atm(fermata, s)
            
            if buses_data:
                bus_trovati = True
                for b in buses_data:
                    attesa = b['attesa'].lower()
                    if "in arrivo" in attesa:
                        stato_css = "status-good"
                    elif "min" in attesa:
                        stato_css = "status-wait"
                    else:
                        stato_css = "status-neutral"
                    
                    riga_html = f"""
                    <div class="transport-row">
                        <span class="icon">directions_bus</span>
                        <div class="line-name">{b['linea']}</div>
                        <div class="destination">per {b['destinazione'].split('-')[-1].split('(')[0]}</div>
                        <div class="details">
                            <span class="{stato_css}">{b['attesa']}</span>
                        </div>
                    </div>
                    """
                    st.markdown(riga_html, unsafe_allow_html=True)
        if not bus_trovati:
            st.markdown('<div style="color: #9ca3af; font-size: 14px; margin-left: 5px;">Nessun bus in arrivo o dati non disponibili al momento</div>', unsafe_allow_html=True)

except Exception as e:
    # Se il sito ATM è irraggiungibile o va in timeout, mostra un avviso senza bloccarsi
    st.warning("⚠️ Servizio API ATM momentaneamente irraggiungibile.")

# Logica di auto-aggiornamento ogni 60 secondi
time.sleep(60)
st.rerun()
