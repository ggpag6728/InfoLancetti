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

# --- CSS PERSONALIZZATO (Testi grandi, margini ridotti e ottimizzazione mobile) ---
st.markdown("""
<link href="https://fonts.googleapis.com/css2?family=Material+Symbols+Rounded:opsz,wght,FILL,GRAD@24,400,1,0" rel="stylesheet" />
<style>
    /* Sfondo globale */
    .stApp {
        background-color: #f8fafc;
    }
    
    header {visibility: hidden;}
    
    /* Layout della Card - Spazi e margini ridotti */
    .transport-row {
        background-color: #ffffff;
        border-radius: 10px;
        padding: 8px 16px; /* Padding ridotto per risparmiare spazio verticalmente */
        margin-bottom: 6px; /* Meno spazio tra le righe */
        display: flex;
        align-items: center;
        box-shadow: 0 1px 2px rgba(0,0,0,0.05);
        font-family: -apple-system, BlinkMacSystemFont, "Segoe UI", Roboto, sans-serif;
        border: 1px solid #e2e8f0;
        justify-content: space-between;
    }
    
    /* Gruppo Info Principali (Icona + Linea + Destinazione) per tenerli sempre uniti */
    .main-info {
        display: flex;
        align-items: center;
        flex-grow: 1;
        min-width: 0; /* Permette il corretto troncamento del testo se troppo lungo */
        margin-right: 15px;
    }
    
    /* Icone */
    .icon {
        font-family: 'Material Symbols Rounded';
        font-size: 28px; /* Icona leggermente più grande */
        color: #64748b;
        margin-right: 12px;
        display: flex;
        align-items: center;
        flex-shrink: 0;
    }
    
    /* Codice Linea (S5, S6, 90, ecc.) */
    .line-name {
        font-weight: 800;
        font-size: 20px; /* Scritta più grande */
        width: 65px;
        color: #0f172a;
        flex-shrink: 0;
    }
    
    /* Destinazione principale */
    .destination {
        font-weight: 700;
        font-size: 18px; /* Scritta più grande */
        color: #1e293b;
        white-space: nowrap;
        overflow: hidden;
        text-overflow: ellipsis; /* Se la scritta è troppo lunga mette i tre puntini anziché andare a capo */
    }
    
    /* Blocco dettagli */
    .details {
        display: flex;
        align-items: center;
        gap: 20px;
        font-size: 16px; /* Scritta più grande */
        color: #334155;
        flex-shrink: 0;
    }
    
    /* Sotto-colonne dei dettagli allineate */
    .det-bin {
        width: 80px;
        font-weight: 800;
        color: #1e40af; 
    }
    .det-time {
        width: 65px;
        font-weight: 700;
        text-align: center;
    }
    .det-status {
        width: 105px; 
        text-align: center;
    }
    
    /* Badge di Stato Uniformati */
    .status-badge {
        display: inline-block;
        width: 100%;
        padding: 5px 0;
        border-radius: 6px;
        font-size: 14px; /* Scritta più grande */
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
        margin-top: 18px;
        margin-bottom: 8px;
        font-size: 22px;
        font-weight: 800;
        display: flex;
        align-items: center;
        gap: 8px;
    }

    /* Regole Responsive per Smartphone */
    @media (max-width: 680px) {
        .transport-row {
            flex-direction: column; /* Separa le macro-info dai dettagli orari */
            align-items: flex-start;
            padding: 10px 12px;
        }
        .main-info {
            width: 100%;
            margin-right: 0;
            margin-bottom: 6px; /* Spazio ridotto tra scritte e orari sotto */
        }
        .details {
            width: 100%; /* I dettagli occupano tutto lo spazio sotto */
            justify-content: space-between; /* Distribuzione perfetta su mobile */
            border-top: 1px dashed #e2e8f0;
            padding-top: 6px;
            gap: 0;
        }
        .det-bin, .det-time, .det-status {
            width: auto; 
            text-align: left;
        }
        .det-status {
            width: 110px;
            text-align: right;
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
ora_attuale = ora_attuale_dt.strftime('%H:%M')
ora_corrente = ora_attuale_dt.hour

# Header h1/h2 con scritte più evidenti
st.markdown(f"""
<div style="display: flex; justify-content: space-between; align-items: center; margin-bottom: 15px; border-bottom: 2px solid #e2e8f0; padding-bottom: 8px;">
    <h1 style="margin: 0; color: #0f172a; font-family: sans-serif; font-weight: 800; font-size: 32px;">Info Milano Lancetti</h1>
    <h2 style="margin: 0; color: #475569; font-family: sans-serif; font-weight: 700; font-size: 26px;">{ora_attuale}</h2>
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
            <div class="main-info">
                <span class="icon">train</span>
                <div class="line-name">{t['linea']}</div>
                <div class="destination">{t['destinazione']}</div>
            </div>
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
                        <div class="main-info">
                            <span class="icon">directions_bus</span>
                            <div class="line-name">{b['linea']}</div>
                            <div class="destination">per {b['destinazione'].split('-')[-1].split('(')[0].strip()}</div>
                        </div>
                        <div class="details">
                            <div class="det-bin" style="color:#64748b; font-weight:normal;">{b['fermata']}</div>
                            <div class="det-time"></div>
                            <div class="det-status">
                                <span class="status-badge {stato_css}">{b['attesa']}</span>
                            </div>
                        </div>
                    </div>
                    """
                    st.markdown(riga_html, unsafe_allow_html=True)
        if not bus_trovati:
            st.markdown('<div style="color: #94a3b8; font-size: 15px; margin-left: 5px;">Nessun bus in arrivo o dati non disponibili</div>', unsafe_allow_html=True)

except Exception as e:
    st.warning("⚠️ Servizio API ATM momentaneamente irraggiungibile.")

# Auto-refresh ogni 60 secondi
time.sleep(60)
st.rerun()
