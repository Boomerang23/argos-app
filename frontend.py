import streamlit as st
import requests
import pandas as pd
import io
import sqlite3
import plotly.express as px
from datetime import datetime
from reportlab.lib.pagesizes import letter
from reportlab.pdfgen import canvas
from reportlab.lib import colors
from reportlab.platypus import SimpleDocTemplate, Table, TableStyle, Paragraph, Spacer
from reportlab.lib.styles import getSampleStyleSheet

# --- CONFIGURATION ---
API_URL = "http://127.0.0.1:8000"
st.set_page_config(page_title="ARGOS - KYC Platform", page_icon="🆔", layout="wide")

# --- CSS (Design) ---
st.markdown("""
<style>
    .centered-title { text-align: center; }
    [data-testid='stFileUploaderDropzoneInstructions'] > div > span {display: none;}
    [data-testid='stFileUploaderDropzoneInstructions'] > div::after {content: "📂 Glissez et déposez votre fichier Excel ici"; font-size: 1.2rem; fontWeight: bold; visibility: visible; display: block;}
    [data-testid='stFileUploaderDropzoneInstructions'] > div > small {display: none;}
    [data-testid='stFileUploaderDropzoneInstructions'] > div::before {content: "Limite 200MB • Formats : XLSX, CSV"; font-size: 0.8rem; visibility: visible; display: block; marginBottom: 10px;}
    [data-testid='stFileUploader'] section > button {color: transparent !important; position: relative;}
    [data-testid='stFileUploader'] section > button::after {content: "Parcourir"; color: rgb(49, 51, 63); position: absolute; left: 0; right: 0; top: 0; bottom: 0; display: flex; alignItems: center; justifyContent: center; fontWeight: 600;}
</style>
""", unsafe_allow_html=True)

# --- GESTION DE LA BASE DE DONNÉES (La Mémoire) ---
def init_db():
    conn = sqlite3.connect('argos_history.db')
    c = conn.cursor()
    c.execute('''CREATE TABLE IF NOT EXISTS history
                 (date TEXT, client_name TEXT, status TEXT, details TEXT)''')
    conn.commit()
    conn.close()

def save_scan(client_name, status, details):
    conn = sqlite3.connect('argos_history.db')
    c = conn.cursor()
    now = datetime.now().strftime("%Y-%m-%d")
    c.execute("INSERT INTO history (date, client_name, status, details) VALUES (?, ?, ?, ?)",
              (now, client_name, status, details))
    conn.commit()
    conn.close()

def load_stats():
    conn = sqlite3.connect('argos_history.db')
    df = pd.read_sql_query("SELECT * FROM history", conn)
    conn.close()
    return df

init_db()

# --- FONCTIONS PDF ---
def create_kyc_pdf(client_name, client_id, status, risk_details):
    buffer = io.BytesIO()
    c = canvas.Canvas(buffer, pagesize=letter)
    width, height = letter
    c.setFont("Helvetica-Bold", 24); c.drawString(50, height - 50, "ARGOS")
    c.setFont("Helvetica", 12); c.drawString(50, height - 70, "Plateforme de Conformité & KYC")
    c.setLineWidth(2); c.line(50, height - 80, width - 50, height - 80)
    c.setFont("Helvetica-Bold", 18); c.drawCentredString(width / 2, height - 120, "RAPPORT DE VÉRIFICATION KYC")
    c.setFont("Helvetica", 12)
    c.drawString(50, height - 180, f"Date : {datetime.now().strftime('%d/%m/%Y à %H:%M')}")
    c.drawString(50, height - 210, f"Client : {client_name}"); c.drawString(50, height - 230, f"ID : {client_id}")
    if status == "FAIBLE": color = colors.green; text_status = "VÉRIFIÉ / CONFORME"
    else: color = colors.red; text_status = "REJETÉ / ALERTE"
    c.setFillColor(color); c.setFont("Helvetica-Bold", 16); c.drawString(50, height - 280, f"STATUT : {text_status}")
    c.setFillColor(colors.black); c.setFont("Helvetica", 12); c.drawString(50, height - 310, f"Détail : {risk_details}")
    c.save(); buffer.seek(0)
    return buffer

def create_global_report(dataframe):
    buffer = io.BytesIO()
    doc = SimpleDocTemplate(buffer, pagesize=letter)
    elements = []
    styles = getSampleStyleSheet()
    elements.append(Paragraph("<b>Rapport Global de Conformité</b>", styles['Title']))
    elements.append(Spacer(1, 12))
    total = len(dataframe); rejected = len(dataframe[dataframe['Statut'].str.contains("REJETÉ")]); compliant = total - rejected
    stats_text = f"Date : {datetime.now().strftime('%d/%m/%Y')}<br/>Total : {total} | Conformes : {compliant} | <b>Alertes : {rejected}</b>"
    elements.append(Paragraph(stats_text, styles['Normal'])); elements.append(Spacer(1, 20))
    data = [["Nom du Client", "ID National", "Statut", "Détail"]]
    for index, row in dataframe.iterrows(): data.append([str(row['Nom']), str(row['ID']), str(row['Statut']), str(row['Détail'])])
    table = Table(data)
    table.setStyle(TableStyle([('BACKGROUND', (0, 0), (-1, 0), colors.darkblue), ('TEXTCOLOR', (0, 0), (-1, 0), colors.whitesmoke),
                               ('ALIGN', (0, 0), (-1, -1), 'CENTER'), ('FONTNAME', (0, 0), (-1, 0), 'Helvetica-Bold'),
                               ('BOTTOMPADDING', (0, 0), (-1, 0), 12), ('BACKGROUND', (0, 1), (-1, -1), colors.beige), ('GRID', (0, 0), (-1, -1), 1, colors.black)]))
    elements.append(table); doc.build(elements); buffer.seek(0)
    return buffer

# --- TITRE ---
st.markdown("<h1 style='text-align: center;'>👁️ ARGOS KYC 👁️</h1>", unsafe_allow_html=True)
st.markdown("<h3 style='text-align: center;'>Plateforme de Vérification d'Identité</h3>", unsafe_allow_html=True)
st.markdown("<hr>", unsafe_allow_html=True)

# --- LOGIN ---
if "token" not in st.session_state: st.session_state["token"] = None
with st.sidebar:
    st.header("🔐 Accès Agent")
    if st.session_state["token"] is None:
        email = st.text_input("Email", "admin@sgi.ci")
        password = st.text_input("Mot de passe", type="password")
        if st.button("Se connecter", key="login_btn"):
            login_success = False
            try:
                res = requests.post(f"{API_URL}/token", data={"username": email, "password": password})
                if res.status_code == 200: st.session_state["token"] = res.json().get("access_token"); st.success("Connecté"); login_success = True
                else: st.error("Identifiants incorrects")
            except Exception as e: st.error(f"Erreur connexion: {e}")
            if login_success: st.rerun()
    else:
        st.success("🟢 Agent Connecté")
        if st.button("Se déconnecter", key="logout"): st.session_state["token"] = None; st.rerun()

# --- APP PRINCIPALE ---
if st.session_state["token"]:
    
    # === DASHBOARD (MODIFICATION ICI : Titre simplifié) ===
    st.markdown("### 📊 Tableau de Bord")
    
    # 1. Charger les données
    df_history = load_stats()
    
    if df_history.empty:
        st.info("👋 Bienvenue ! Aucune donnée pour l'instant. Lancez une vérification pour activer le tableau de bord.")
    else:
        # Calculs KPI
        total_scan = len(df_history)
        total_alertes = len(df_history[df_history['status'] == 'ALERTE'])
        total_ok = total_scan - total_alertes
        
        # Affichage KPI
        k1, k2, k3 = st.columns(3)
        k1.metric("Total Historique", total_scan)
        k2.metric("✅ Validés", total_ok)
        k3.metric("🚨 Alertes", total_alertes, delta_color="inverse")
        
        st.markdown("---")
        
        # Graphiques
        c1, c2 = st.columns(2)
        with c1:
            # Camembert
            fig_pie = px.pie(df_history, names='status', title='Répartition des Risques', hole=0.4, 
                             color='status', color_discrete_map={'CONFORME':'green', 'ALERTE':'red'})
            st.plotly_chart(fig_pie, use_container_width=True)
        
        with c2:
            # Barres
            df_bar = df_history.groupby('date').size().reset_index(name='counts')
            fig_bar = px.bar(df_bar, x='date', y='counts', title='Activité Journalière', color='counts')
            st.plotly_chart(fig_bar, use_container_width=True)

    st.markdown("---")

    # === ONGLETS DE TRAVAIL ===
    tab1, tab2 = st.tabs(["👤 Vérification Unitaire", "📂 Scan de Masse (Excel)"])

    # UNITAIRE
    with tab1:
        st.info("Saisie manuelle.")
        c1, c2 = st.columns(2)
        with c1: full_name = st.text_input("Nom & Prénoms"); national_id = st.text_input("Numéro de Pièce")
        with c2: entity_type = st.selectbox("Type", ["Physique", "Morale"]); country = st.text_input("Pays", "Côte d'Ivoire")
        
        if st.button("🔍 Vérifier", type="primary", key="check_unit"):
            if full_name and national_id:
                headers = {"Authorization": f"Bearer {st.session_state['token']}"}
                try:
                    res = requests.post(f"{API_URL}/clients/", json={"full_name": full_name, "entity_type": entity_type, "national_id": national_id, "country_residence": country, "tenant_id": "MANUAL"}, headers=headers)
                    if res.status_code == 200:
                        data = res.json(); risk = data.get("risk_score")
                        if risk == "ELEVE":
                            st.error(f"🚨 ALERTE : {full_name} REJETÉ."); txt_risk = "Sanctions / PEP"; status_db = "ALERTE"
                        else:
                            st.success(f"✅ CONFORME : {full_name}."); txt_risk = "RAS"; status_db = "CONFORME"
                        
                        save_scan(full_name, status_db, txt_risk)
                        
                        pdf = create_kyc_pdf(full_name, national_id, risk, txt_risk)
                        st.download_button("📄 Télécharger Rapport (PDF)", pdf, f"Rapport_{full_name}.pdf", "application/pdf")
                        
                        if st.button("🔄 Actualiser le Tableau de Bord"): st.rerun()
                        
                except Exception as e: st.error(f"Erreur: {e}")

    # BULK
    with tab2:
        st.info("Import Excel")
        upl = st.file_uploader("Fichier", type=["xlsx", "csv"])
        if upl:
            try:
                df = pd.read_csv(upl) if upl.name.endswith('.csv') else pd.read_excel(upl)
                st.dataframe(df.head())
                if st.button("🚀 Scanner", key="bulk_scan"):
                    results = []; bar = st.progress(0); headers = {"Authorization": f"Bearer {st.session_state['token']}"}
                    for i, row in df.iterrows():
                        nom = row.get('Nom') or row.get('Name') or row.get('full_name')
                        nid = row.get('ID') or row.get('National_ID') or f"BULK-{i}"
                        if nom:
                            try:
                                r = requests.post(f"{API_URL}/clients/", json={"full_name": str(nom), "entity_type": "Physique", "national_id": str(nid), "country_residence": "Inconnu", "tenant_id": "BULK"}, headers=headers)
                                res_json = r.json() if r.status_code == 200 else {}
                                if res_json.get("risk_score") == "ELEVE": stat = "🔴 REJETÉ"; db_stat = "ALERTE"; det = "Sanctionné"
                                else: stat = "🟢 CONFORME"; db_stat = "CONFORME"; det = "RAS"
                            except: stat = "⚠️ ERREUR"; db_stat = "ERREUR"; det = "Erreur Technique"
                            
                            results.append({"Nom": nom, "ID": nid, "Statut": stat, "Détail": det})
                            save_scan(str(nom), db_stat, det)
                            
                        bar.progress((i + 1) / len(df))
                    st.success("Terminé !"); final_df = pd.DataFrame(results); st.dataframe(final_df)
                    c1, c2 = st.columns(2)
                    with c1: st.download_button("📥 CSV", final_df.to_csv(index=False).encode('utf-8'), "resultats.csv", "text/csv")
                    with c2: st.download_button("📄 PDF Global", create_global_report(final_df), "Rapport_Global.pdf", "application/pdf", type="primary")
                    st.balloons()
            except Exception as e: st.error(f"Erreur fichier : {e}")
else: st.warning("Veuillez vous connecter.")