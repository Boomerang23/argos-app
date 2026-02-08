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
API_URL = "https://argos-backend-kovx.onrender.com"
st.set_page_config(page_title="ARGOS - KYC Platform", page_icon="👁️", layout="wide")

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
    .main-header {font-size: 30px; font-weight: bold; color: #4B4B4B; text-align: center; margin-bottom: 20px;}
</style>
""", unsafe_allow_html=True)

# --- GESTION DE LA BASE DE DONNÉES LOCALE (Historique) ---
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
    
    if status == "ELEVE" or "ALERTE" in str(status): 
        color = colors.red
        text_status = "REJETÉ / ALERTE"
    else: 
        color = colors.green
        text_status = "VÉRIFIÉ / CONFORME"
        
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
    
    # Correction statuts pour le PDF global
    rejected = len(dataframe[dataframe['Statut'].str.contains("REJETÉ") | dataframe['Statut'].str.contains("ALERTE")])
    total = len(dataframe)
    compliant = total - rejected
    
    stats_text = f"Date : {datetime.now().strftime('%d/%m/%Y')}<br/>Total : {total} | Conformes : {compliant} | <b>Alertes : {rejected}</b>"
    elements.append(Paragraph(stats_text, styles['Normal'])); elements.append(Spacer(1, 20))
    
    data = [["Nom du Client", "ID National", "Statut", "Détail"]]
    for index, row in dataframe.iterrows(): 
        data.append([str(row['Nom']), str(row['ID']), str(row['Statut']), str(row['Détail'])])
        
    table = Table(data)
    table.setStyle(TableStyle([('BACKGROUND', (0, 0), (-1, 0), colors.darkblue), ('TEXTCOLOR', (0, 0), (-1, 0), colors.whitesmoke),
                               ('ALIGN', (0, 0), (-1, -1), 'CENTER'), ('FONTNAME', (0, 0), (-1, 0), 'Helvetica-Bold'),
                               ('BOTTOMPADDING', (0, 0), (-1, 0), 12), ('BACKGROUND', (0, 1), (-1, -1), colors.beige), ('GRID', (0, 0), (-1, -1), 1, colors.black)]))
    elements.append(table); doc.build(elements); buffer.seek(0)
    return buffer

# --- TITRE PRINCIPAL ---
st.markdown("<h1 style='text-align: center;'>👁️ ARGOS KYC 👁️</h1>", unsafe_allow_html=True)
st.markdown("<h3 style='text-align: center;'>Plateforme de Vérification d'Identité</h3>", unsafe_allow_html=True)
st.markdown("<hr>", unsafe_allow_html=True)

# --- GESTION DE SESSION & LOGIN ---
if "token" not in st.session_state: st.session_state["token"] = None

with st.sidebar:
    st.image("https://cdn-icons-png.flaticon.com/512/9370/9370273.png", width=50)
    st.header("🔐 Accès Agent")
    
    if st.session_state["token"] is None:
        email = st.text_input("Email", "admin@sgi.ci")
        password = st.text_input("Mot de passe", type="password")
        if st.button("Se connecter", key="login_btn"):
            try:
                res = requests.post(f"{API_URL}/token", data={"username": email, "password": password})
                if res.status_code == 200: 
                    st.session_state["token"] = res.json().get("access_token")
                    st.success("Connecté")
                    st.rerun()
                else: 
                    st.error("Identifiants incorrects")
            except Exception as e: 
                st.error(f"Erreur connexion: {e}")
    else:
        st.success("🟢 Agent Connecté")
        if st.button("Se déconnecter", key="logout"): 
            st.session_state["token"] = None
            st.rerun()

# --- APPLICATION PRINCIPALE ---
if st.session_state["token"]:
    
    # === MENU DE NAVIGATION ===
    # J'ai ajouté ce menu pour basculer entre les vues
    menu = st.sidebar.radio("Navigation", ["📊 Tableau de Bord", "🔍 Vérifications", "👮 Administration"])

    # HEADER TOKEN
    headers = {"Authorization": f"Bearer {st.session_state['token']}"}

    # ==========================
    # VUE 1 : TABLEAU DE BORD
    # ==========================
    if menu == "📊 Tableau de Bord":
        st.markdown("### 📊 Statistiques en Temps Réel")
        df_history = load_stats()
        
        if df_history.empty:
            st.info("👋 Bienvenue ! Aucune donnée pour l'instant. Lancez une vérification pour activer le tableau de bord.")
        else:
            total_scan = len(df_history)
            total_alertes = len(df_history[df_history['status'].str.contains('ALERTE')])
            total_ok = total_scan - total_alertes
            
            k1, k2, k3 = st.columns(3)
            k1.metric("Total Historique", total_scan)
            k2.metric("✅ Validés", total_ok)
            k3.metric("🚨 Alertes", total_alertes, delta_color="inverse")
            
            st.markdown("---")
            c1, c2 = st.columns(2)
            with c1:
                fig_pie = px.pie(df_history, names='status', title='Répartition des Risques', hole=0.4, 
                                 color='status', color_discrete_map={'CONFORME':'green', 'ALERTE':'red'})
                st.plotly_chart(fig_pie, use_container_width=True)
            with c2:
                df_bar = df_history.groupby('date').size().reset_index(name='counts')
                fig_bar = px.bar(df_bar, x='date', y='counts', title='Activité Journalière')
                st.plotly_chart(fig_bar, use_container_width=True)

    # ==========================
    # VUE 2 : VÉRIFICATIONS (Unitaire & Masse)
    # ==========================
    elif menu == "🔍 Vérifications":
        tab1, tab2 = st.tabs(["👤 Vérification Unitaire", "📂 Scan de Masse (Excel)"])

        # UNITAIRE
        with tab1:
            st.info("Saisie manuelle pour vérification immédiate.")
            c1, c2 = st.columns(2)
            with c1: full_name = st.text_input("Nom & Prénoms"); national_id = st.text_input("Numéro de Pièce")
            with c2: entity_type = st.selectbox("Type", ["Physique", "Morale"]); country = st.text_input("Pays", "Côte d'Ivoire")
            
            if st.button("🔍 Vérifier", type="primary", key="check_unit"):
                if full_name and national_id:
                    try:
                        res = requests.post(f"{API_URL}/clients/", json={"full_name": full_name, "entity_type": entity_type, "national_id": national_id, "country_residence": country, "tenant_id": "MANUAL"}, headers=headers)
                        
                        if res.status_code == 200:
                            data = res.json()
                            risk = data.get("risk_score")
                            
                            # Logique d'affichage
                            if risk == "ELEVE" or risk == "High":
                                st.error(f"🚨 ALERTE : {full_name} est REJETÉ.")
                                txt_risk = "Sanctions / PEP / Blacklist"
                                status_db = "ALERTE"
                                pdf_status = "ELEVE"
                            else:
                                st.success(f"✅ CONFORME : {full_name}.")
                                txt_risk = "RAS"
                                status_db = "CONFORME"
                                pdf_status = "FAIBLE"
                            
                            # Sauvegarde locale
                            save_scan(full_name, status_db, txt_risk)
                            
                            # Affichage détails si alerte
                            if status_db == "ALERTE":
                                st.warning(f"Détails de l'alerte : {data.get('details', 'N/A')}")
                            
                            # PDF
                            pdf = create_kyc_pdf(full_name, national_id, pdf_status, txt_risk)
                            st.download_button("📄 Télécharger Rapport (PDF)", pdf, f"Rapport_{full_name}.pdf", "application/pdf")
                            
                        else:
                            st.error(f"Erreur API: {res.status_code}")
                            
                    except Exception as e: st.error(f"Erreur de connexion: {e}")

        # BULK (EXCEL)
        with tab2:
            st.info("Importez un fichier Excel ou CSV pour analyser une liste de clients.")
            upl = st.file_uploader("Fichier", type=["xlsx", "csv"])
            if upl:
                try:
                    df = pd.read_csv(upl) if upl.name.endswith('.csv') else pd.read_excel(upl)
                    st.dataframe(df.head())
                    
                    if st.button("🚀 Lancer le Scan de Masse", key="bulk_scan"):
                        results = []
                        bar = st.progress(0)
                        
                        for i, row in df.iterrows():
                            # Gestion flexible des noms de colonnes
                            nom = row.get('Nom') or row.get('Name') or row.get('full_name') or "Inconnu"
                            nid = row.get('ID') or row.get('National_ID') or f"BULK-{i}"
                            
                            if nom != "Inconnu":
                                try:
                                    r = requests.post(f"{API_URL}/clients/", json={"full_name": str(nom), "entity_type": "Physique", "national_id": str(nid), "country_residence": "Inconnu", "tenant_id": "BULK"}, headers=headers)
                                    res_json = r.json() if r.status_code == 200 else {}
                                    
                                    risk = res_json.get("risk_score")
                                    if risk == "ELEVE" or risk == "High":
                                        stat = "🔴 REJETÉ"; db_stat = "ALERTE"; det = "Sanctionné"
                                    else:
                                        stat = "🟢 CONFORME"; db_stat = "CONFORME"; det = "RAS"
                                except:
                                    stat = "⚠️ ERREUR"; db_stat = "ERREUR"; det = "Erreur Technique"
                                
                                results.append({"Nom": nom, "ID": nid, "Statut": stat, "Détail": det})
                                save_scan(str(nom), db_stat, det)
                            
                            bar.progress((i + 1) / len(df))
                        
                        st.success("Analyse terminée !")
                        final_df = pd.DataFrame(results)
                        st.dataframe(final_df)
                        
                        c1, c2 = st.columns(2)
                        with c1: st.download_button("📥 Télécharger CSV", final_df.to_csv(index=False).encode('utf-8'), "resultats_kyc.csv", "text/csv")
                        with c2: st.download_button("📄 Télécharger PDF Global", create_global_report(final_df), "Rapport_Global.pdf", "application/pdf", type="primary")
                        st.balloons()
                except Exception as e: st.error(f"Erreur de lecture du fichier : {e}")

    # ==========================
    # VUE 3 : ADMINISTRATION (NOUVEAU !)
    # ==========================
    elif menu == "👮 Administration":
        st.markdown("### 👮 Gestion de la Liste Noire (Blacklist)")
        st.warning("⚠️ Zone réservée aux administrateurs. Les profils ajoutés ici seront marqués comme 'Risque Élevé' lors des vérifications.")
        
        with st.form("add_risk_form"):
            col1, col2 = st.columns(2)
            with col1:
                bad_name = st.text_input("Nom de la personne à signaler")
                risk_type = st.selectbox("Type de Risque", ["Terrorisme", "Blanchiment", "Fraude", "Personne Politiquement Exposée (PEP)", "Autre"])
            with col2:
                details = st.text_area("Détails / Motif du signalement")
                
            submit = st.form_submit_button("AJOUTER À LA LISTE ROUGE 🔴", use_container_width=True)
            
            if submit and bad_name:
                # Payload conforme à ton Backend FastAPI (models.py)
                payload = {
                    "name": bad_name,
                    "risk_level": "High",
                    "details": f"{risk_type}: {details}"
                }
                
                try:
                    # On envoie la requête au Backend
                    response = requests.post(f"{API_URL}/people/", json=payload, headers=headers)
                    
                    if response.status_code == 200:
                        st.success(f"✅ Le profil '{bad_name}' a été ajouté avec succès à la base de données criminelle !")
                    elif response.status_code == 401:
                        st.error("⛔ Session expirée. Veuillez vous reconnecter.")
                    else:
                        st.error(f"❌ Erreur serveur : {response.status_code}")
                except Exception as e:
                    st.error(f"❌ Erreur technique : {e}")

else:
    # Écran d'accueil si non connecté
    st.markdown("<br><br>", unsafe_allow_html=True)
    st.info("🔒 Veuillez vous connecter via le panneau latéral (à gauche) pour accéder à la plateforme.")
