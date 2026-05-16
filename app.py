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

# --- CSS PERSONALIZZATO REVISIONATO (Moderno, Allineato e Responsive) ---
st.markdown("""
<link href="https://fonts.googleapis.com/css2?family=Material+Symbols+Rounded:opsz,wght,FILL,GRAD@24,400,1,0" rel="stylesheet" />
<style>
    /* Sfondo e font globale */
    .stApp {
        background-color: #f8fafc;
    }
    
    header {visibility: hidden;}
    
    /* Layout della Card Principale */
    .transport-row {
        background-color: #ffffff;
        border-radius: 12px;
        padding: 14px 20px;
        margin-bottom: 10px;
        display: flex;
        align-items: center;
        box-shadow: 0 1px 3px rgba(0,0,0,0.05), 0 1px 2px rgba(0,0,0,0.02);
        font-family: -apple-system, BlinkMacSystemFont, "Segoe UI", Roboto, sans-serif;
        border: 1px solid #e2e8f0;
        flex-wrap: wrap; /* Permette il riposizionamento su mobile */
    }
    
    /* Icone */
    .icon {
        font-family: 'Material Symbols Rounded';
        font-size: 26px;
        color: #64748b;
        margin-right: 16px;
        display: flex;
        align-items: center;
    }
    
    /* Codice Linea (S5, S6, 90, ecc.) */
    .line-name {
        font-weight: 800;
        font-size: 18px;
        width: 65px;
        color: #0f172a;
        flex-shrink: 0;
    }
    
    /* Destinazione principale */
    .destination {
        flex-grow: 1;
        font-weight: 600;
        font-size: 16px;
        color: #334155;
        min-width: 150px; /* Evita il collasso su schermi medi */
    }
    
    /* Blocco dettagli (Destra su Desktop, Sotto su Mobile) */
    .details {
        display: flex;
        align-items: center;
        gap: 20px;
        font-size: 15px;
        color: #475569;
    }
    
    /* Sotto-colonne dei dettagli con larghezze fisse per allineamento perfetto */
    .det-bin {
        width: 75px;
        font-weight: 700;
        color: #1e40af; /* Colore blu scuro per risaltare il binario */
    }
    .det-time {
        width: 60px;
        font-weight: 700;
        text-align: center;
    }
    .det-status {
        width: 95px; /* Spazio fisso per i badge */
        text-align: center;
    }
    
    /* Badge di Stato Uniformati */
    .status-badge {
        display: inline-block;
        width: 100%;
        padding: 6px 0;
        border-radius: 6px;
        font-size: 13px;
        font-weight: 700;
        text-align: center;
    }
    .status-good { color: #166534; background: #dcfce7; }
    .status-bad { color: #991b1b; background: #fee2e2; }
    .status-wait { color: #9a3412; background: #ffedd5; }
    .status-neutral { color: #334155; background: #f1f5f9; }
    
    /* Titoli delle Sezioni */
    .section-title {
        font-family: -apple-system, BlinkMacSystemFont, "Segoe UI", Roboto;
        color: #0f172a;
        margin-top: 25px;
        margin-bottom: 12px;
        font-size: 20px;
        font-weight: 700;
        display: flex;
        align-items: center;
        gap: 8px;
    }

    /* Regole Responsive per Mobile (Schermi sotto i 640px) */
    @media (max-width: 640px) {
        .transport-row {
            padding: 12px;
        }
        .destination {
            width: calc(100% - 90px); /* Prende lo spazio di fianco alla linea */
            margin-bottom: 8px;
        }
        .details {
            width: 100%; /* Sposta i dettagli sotto */
            justify-content: space-between; /* Li distribuisce uniformemente */
            border-top: 1px dashed #e2e8f0;
            padding-top: 8px;
            gap: 0;
        }
        .det-bin, .det-time, .det-status {
            width: auto; /* Su mobile usano lo spazio necessario */
            text-align: left;
        }
        .det-status {
            width: 100px;
        }
    }
</style>
""", unsafe_allow_html=True)

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
            if not treno.get("arrivato", False):
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

# --- INTERFACCIA WEB ---
ora_attuale_dt = datetime.now(ZoneInfo('Europe/Rome'))
ora_attuale = ora_attuale_dt.strftime('%H:%M')  # Modificato: rimosso %S per nascondere i secondi
ora_corrente = ora_attuale_dt.hour

# Header
st.markdown(f"""
<div style="display: flex; justify-content: space-between; align-items: center; margin-bottom: 20px; border-bottom: 2px solid #e2e8f0; padding-bottom: 10px;">
    <h1 style="margin: 0; color: #0f172a; font-family: sans-serif; font-weight: 800; font-size: 28px;">Info Milano Lancetti</h1>
    <h2 style="margin: 0; color: #475569; font-family: sans-serif; font-weight: 700;">{ora_attuale}</h2>
</div>
""", unsafe_allow_html=True)

# Pausa notturna
inizio_pausa, fine_pausa = 1, 6
if inizio_pausa <= ora_corrente < fine_pausa:
    st.info(f"🌙 **Sospensione notturna attiva ({inizio_pausa}:00 - {fine_pausa}:00).** Il monitoraggio riprenderà in automatico.")
    time.sleep(60)
    st.rerun()

# ==========================================
# SEZIONE TRENI
# ==========================================
st.markdown('<div class="section-title"><span class="icon" style="color: #2563eb;">train</span> Treni da Lancetti</div>', unsafe_allow_html=True)
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
                <div class="det-bin">BIN. {t['binario']}</div>
                <div class="det-time">{t['orario']}</div>
                <div class="det-status">
                    <span class="status-badge {stato_css}">{stato_txt}</span>
                </div>
            </div>
        </div>
        """
        st.markdown(riga_html, unsafe_allow_html=True)
else:
    st.info("Nessun treno in partenza.")

# ==========================================
# SEZIONE BUS ATM
# ==========================================
st.markdown('<div class="section-title"><span class="icon" style="color: #16a34a;">directions_bus</span> Bus & Filobus</div>', unsafe_allow_html=True)

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
                        <div class="destination">per {b['destinazione'].split('-')[-1].split('(')[0].strip()}</div>
                        <div class="details">
                            <div class="det-bin" style="color:#64748b; font-weight:normal;">Bus</div>
                            <div class="det-time">--:--</div>
                            <div class="det-status">
                                <span class="status-badge {stato_css}">{b['attesa']}</span>
                            </div>
                        </div>
                    </div>
                    """
                    st.markdown(riga_html, unsafe_allow_html=True)
        if not bus_trovati:
            st.markdown('<div style="color: #94a3b8; font-size: 14px; margin-left: 5px;">Nessun bus in arrivo o dati non disponibili</div>', unsafe_allow_html=True)

except Exception as e:
    st.warning("⚠️ Servizio API ATM momentaneamente irraggiungibile.")

# Auto-refresh ogni 60 secondi
time.sleep(60)
st.rerun()
