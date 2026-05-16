import streamlit as st
import time
from curl_cffi import requests as requests_cffi
import requests
from typing import List, Dict, Any
from dataclasses import dataclass
from datetime import datetime
from zoneinfo import ZoneInfo

# --- INIZIALIZZAZIONE STATO ---
if "num_treni" not in st.session_state:
    st.session_state.num_treni = 5
if "filtro_precedente" not in st.session_state:
    st.session_state.filtro_precedente = "Tutti"

# --- CONFIGURAZIONE PAGINA ---
st.set_page_config(page_title="Infotrasporti Milano Lancetti", layout="wide", initial_sidebar_state="collapsed")

# --- CSS PERSONALIZZATO ---
st.markdown("""
<link href="https://fonts.googleapis.com/css2?family=Material+Symbols+Rounded:opsz,wght,FILL,GRAD@24,400,1,0" rel="stylesheet" />
<style>
    /* FORZATURA MODALITA' CHIARA VIA CSS */
    :root, [data-theme="dark"], .stApp {
        --text-color: #0f172a !important;
        --background-color: #f8fafc !important;
        --secondary-background-color: #ffffff !important;
        background-color: #f8fafc !important;
        color: #0f172a !important;
    }
    
    header {visibility: hidden;}
    
    .block-container {
        padding-top: 1rem;
        padding-bottom: 1rem;
    }
    
    .transport-row {
        background-color: #ffffff;
        border-radius: 10px;
        padding: 8px 16px;
        margin-bottom: 6px;
        display: flex;
        align-items: center;
        box-shadow: 0 1px 2px rgba(0,0,0,0.05);
        font-family: -apple-system, BlinkMacSystemFont, "Segoe UI", Roboto, sans-serif;
        border: 1px solid #e2e8f0;
        justify-content: space-between;
    }
    
    .main-info {
        display: flex;
        align-items: center;
        flex-grow: 1;
        min-width: 0;
        margin-right: 15px;
    }
    
    /* BADGE RIDOTTO */
    .badge-line {
        display: flex;
        align-items: center;
        justify-content: center;
        width: 38px;  /* <-- Dimensione ridotta */
        height: 38px; /* <-- Dimensione ridotta */
        border-radius: 8px;
        color: #ffffff;
        font-weight: 800;
        font-size: 16px; /* <-- Testo più piccolo proporzionato */
        margin-right: 12px;
        flex-shrink: 0;
        box-shadow: 0 2px 4px rgba(0,0,0,0.1);
        text-shadow: 0 1px 2px rgba(0,0,0,0.3); /* Aiuta la lettura sui colori chiari come il giallo */
    }
    
    .icon {
        font-family: 'Material Symbols Rounded';
        font-size: 28px;
        color: #64748b;
        margin-right: 8px;
        display: flex;
        align-items: center;
    }
    
    .destination {
        font-weight: 700;
        font-size: 18px;
        color: #1e293b;
        white-space: nowrap;
        overflow: hidden;
        text-overflow: ellipsis;
    }
    
    .details {
        display: flex;
        align-items: center;
        gap: 20px;
        font-size: 16px;
        color: #334155;
        flex-shrink: 0;
    }
    
    .det-bin { width: 80px; font-weight: 800; color: #1e40af; }
    .det-time { width: 75px; font-weight: 900; font-size: 22px; text-align: center; }
    .det-status { width: 115px; text-align: center; }
    
    .status-badge {
        display: inline-block;
        width: 100%;
        padding: 6px 0;
        border-radius: 6px;
        font-size: 18px;
        font-weight: 700;
        text-align: center;
    }
    .status-good { color: #166534; background: #dcfce7; }
    .status-bad { color: #991b1b; background: #fee2e2; }
    .status-wait { color: #9a3412; background: #ffedd5; }
    .status-neutral { color: #334155; background: #f1f5f9; }
    
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

    .stButton>button {
        width: 100%;
        background-color: #e2e8f0;
        color: #0f172a;
        font-weight: 600;
        border: none;
        border-radius: 8px;
        padding: 10px;
        margin-top: 5px;
        transition: all 0.2s;
    }
    .stButton>button:hover { background-color: #cbd5e1; color: #0f172a;}

    @media (max-width: 680px) {
        .block-container { padding-top: 0.5rem; }
        .transport-row { flex-direction: column; align-items: flex-start; padding: 10px 12px; }
        .main-info { width: 100%; margin-right: 0; margin-bottom: 6px; }
        .details { width: 100%; justify-content: space-between; border-top: 1px dashed #e2e8f0; padding-top: 6px; gap: 0; }
        .det-bin, .det-time, .det-status { width: auto; text-align: left; }
        .det-status { width: 120px; text-align: right; }
    }
</style>
""", unsafe_allow_html=True)

# --- BACKEND LOGIC ---
COLORI_LINEE = {
    "S1": "#dc2626",   # Rosso
    "S2": "#0d9488",   # Verde acqua (Teal)
    "S5": "#ea580c",   # Arancione
    "S6": "#ca8a04",   # Giallo (leggermente scuro per visibilità del testo bianco)
    "S12": "#15803d",  # Verde scuro
    "S13": "#78350f",  # Marrone
    "BUS": "#16a34a"   # Verde ATM
}

def individua_linea(treno: Dict[str, Any]) -> str:
    """Capisce la linea S guardando il numero treno e non solo la destinazione"""
    # 1. Cerca nel compNumeroTreno (a volte API Trenord lo inserisce es. S13 24314)
    comp_numero = str(treno.get("compNumeroTreno", "")).upper()
    for linea in ["S1", "S2", "S5", "S6", "S12", "S13"]:
        if linea in comp_numero.split():
            return linea
            
    # 2. Riconoscimento infallibile tramite i prefissi numerici Trenord del Passante
    numero = str(treno.get("numeroTreno", ""))
    if numero.startswith(("241", "231", "232")): return "S1"
    if numero.startswith(("226", "228", "229")): return "S2"
    if numero.startswith(("245", "230")): return "S5"
    if numero.startswith(("246", "233")): return "S6"
    if numero.startswith(("256", "242")): return "S12"
    if numero.startswith(("243", "244")): return "S13"
    
    # 3. Fallback sulla destinazione se il numero treno è strano o cambiato
    dest = str(treno.get("destinazione", "")).upper()
    if "LODI" in dest or "SARONNO" in dest: return "S1"
    if "SEVESO" in dest or "MEDA" in dest or "MARIANO" in dest: return "S2"
    if "VARESE" in dest or "TREVIGLIO" in dest: return "S5"
    if "NOVARA" in dest or "PIOLTELLO" in dest: return "S6"
    if "MELEGNANO" in dest or "CORMANO" in dest: return "S12"
    if "PAVIA" in dest or "GARBAGNATE" in dest: return "S13"
    
    return "--"

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

@st.cache_data(ttl=30)
def get_treni(codice_stazione: str) -> List[Dict[str, Any]]:
    dt_rome = datetime.now(ZoneInfo("Europe/Rome"))
    orario_attuale = dt_rome.strftime("%a %b %d %Y %H:%M:%S GMT%z")
    url = f"http://www.viaggiatreno.it/infomobilita/resteasy/viaggiatreno/partenze/{codice_stazione}/{orario_attuale}"
    try:
        response = requests.get(url, timeout=10)
        if response.status_code != 200: return []
        treni_json = response.json()

        if not isinstance(treni_json, list): return []
        
        treni_monitor = []
        for treno in treni_json:
            if not treno.get("arrivato", False):
                destinazione = treno.get("destinazione", "N/D")
                binario = str(treno.get("binarioEffettivoPartenzaDescrizione") or 
                              treno.get("binarioProgrammatoPartenzaDescrizione") or "-").strip()
                treni_monitor.append({
                    "linea": individua_linea(treno), # <-- Nuovo sistema di calcolo
                    "destinazione": destinazione,
                    "orario": treno.get("compOrarioPartenza", "--:--"),
                    "ritardo": treno.get("ritardo", 0),
                    "binario": binario
                }) 
        return treni_monitor
    except Exception:
        return []

@st.cache_data(ttl=20)
def get_atm(nome_identificativo: str, poi_id: str) -> List[Dict[str, Any]]:
    url = f"https://giromilano.atm.it/proxy.tpportal/api/tpPortal/geodata/pois/{poi_id}?lang=it"
    try:
        with requests_cffi.Session(impersonate="chrome110") as session:
            session.get("https://giromilano.atm.it/", headers=HEADERS_ATM, timeout=10)
            response = session.get(url, headers=HEADERS_ATM, timeout=10)
            if response.status_code != 200: return []
            fermata_json = response.json()
            nome_fermata = fermata_json.get("Description", nome_identificativo)
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
secondi_attuali = ora_attuale_dt.strftime('%H:%M:%S')

st.markdown(f"""
<div style="display: flex; justify-content: space-between; align-items: center; margin-bottom: 15px; border-bottom: 2px solid #e2e8f0; padding-bottom: 8px;">
    <h1 style="margin: 0; color: #0f172a; font-family: sans-serif; font-weight: 800; font-size: 32px; line-height: 1.2;">
        Info Milano Lancetti
    </h1>
    <h2 style="margin: 0; color: #475569; font-family: sans-serif; font-weight: 700; font-size: 26px;">{ora_attuale}</h2>
</div>
""", unsafe_allow_html=True)

inizio_pausa, fine_pausa = 1, 5
if inizio_pausa <= ora_corrente < fine_pausa:
    st.info(f"🌙 **Sospensione notturna attiva ({inizio_pausa}:00 - {fine_pausa}:00).** Il monitoraggio riprenderà in automatico.")
    time.sleep(60)
    st.rerun()

# ==========================================
# SEZIONE TRENI
# ==========================================
col_title, col_filter = st.columns([3, 1])

with col_title:
    st.markdown('<div class="section-title" style="margin-top: 0;"><span class="icon" style="color: #2563eb;">train</span>Treni da Milano Lancetti</div>', unsafe_allow_html=True)

with col_filter:
    filtro_scelto = st.selectbox(
        "Filtro", 
        ["Tutti", "Binario 1", "Binario 2", "Binari 1 e 2", "Binario 3", "Binario 4", "Binari 3 e 4"],
        label_visibility="collapsed"
    )

if filtro_scelto != st.session_state.filtro_precedente:
    st.session_state.num_treni = 5
    st.session_state.filtro_precedente = filtro_scelto

treni_data = get_treni("S01643")

if treni_data:
    treni_filtrati = []
    for t in treni_data:
        b = str(t['binario'])
        if filtro_scelto == "Tutti": treni_filtrati.append(t)
        elif filtro_scelto == "Binario 1" and b == "1": treni_filtrati.append(t)
        elif filtro_scelto == "Binario 2" and b == "2": treni_filtrati.append(t)
        elif filtro_scelto == "Binari 1 e 2" and b in ["1", "2"]: treni_filtrati.append(t)
        elif filtro_scelto == "Binario 3" and b == "3": treni_filtrati.append(t)
        elif filtro_scelto == "Binario 4" and b == "4": treni_filtrati.append(t)
        elif filtro_scelto == "Binari 3 e 4" and b in ["3", "4"]: treni_filtrati.append(t)

    treni_da_mostrare = treni_filtrati[:st.session_state.num_treni]

    if not treni_da_mostrare:
        st.info(f"Nessun treno previsto per i criteri selezionati ({filtro_scelto}).")
    else:
        for t in treni_da_mostrare:
            ritardo_val = t['ritardo']
            if ritardo_val > 0:
                stato_css = "status-bad"
                stato_txt = f"+{ritardo_val}'"
            else:
                stato_css = "status-good"
                stato_txt = "In orario"
            
            colore_badge = COLORI_LINEE.get(t['linea'], "#94a3b8")
                
            riga_html = f"""
            <div class="transport-row">
                <div class="main-info">
                    <div class="badge-line" style="background-color: {colore_badge};">{t['linea']}</div>
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
        
        if len(treni_filtrati) > st.session_state.num_treni:
            if st.button("➕ Carica altri 5 treni", use_container_width=True):
                st.session_state.num_treni += 5
                st.rerun()
else:
    st.info("Nessun treno in partenza.")

# ==========================================
# SEZIONE BUS ATM
# ==========================================
st.markdown('<div class="section-title"><span class="icon" style="color: #16a34a;">directions_bus</span>Bus & Filobus</div>', unsafe_allow_html=True)

try:
    bus_trovati = False
    for fermata in fermate_atm:
        buses_data = get_atm(fermata.nome_identificativo, fermata.poi_id)
        if buses_data:
            bus_trovati = True
            for b in buses_data:
                attesa = b['attesa'].lower()
                if "in arrivo" in attesa: stato_css = "status-good"
                elif "min" in attesa: stato_css = "status-wait"
                else: stato_css = "status-neutral"
                
                colore_badge = COLORI_LINEE["BUS"]
                
                riga_html = f"""
                <div class="transport-row">
                    <div class="main-info">
                        <div class="badge-line" style="background-color: {colore_badge};">{b['linea']}</div>
                        <div class="destination">{b['destinazione'].split('-')[-1].split('(')[0].strip()}</div>
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

# ==========================================
# FOOTER AGGIORNAMENTO
# ==========================================
st.markdown(f"""
<div style="text-align: center; color: #94a3b8; font-size: 14px; margin-top: 25px; margin-bottom: 15px;">
    Ultimo aggiornamento: <b>{secondi_attuali}</b> • Auto-refresh ogni 60s
</div>
""", unsafe_allow_html=True)

time.sleep(60)
st.rerun()
