import streamlit as st
import textwrap
import requests
import pandas as pd
import io
import plotly.express as px
import plotly.graph_objects as go
from datetime import datetime
from reportlab.lib.pagesizes import letter
from reportlab.pdfgen import canvas
from reportlab.lib import colors
from reportlab.platypus import SimpleDocTemplate, Table, TableStyle, Paragraph, Spacer
from reportlab.lib.styles import getSampleStyleSheet

# --- CONFIGURATION ---
API_URL = "https://argos-backend-kovx.onrender.com"
st.set_page_config(page_title="ARGOS - Gestion des Risques", page_icon="🛡️", layout="wide")

# --- CSS (Design Pro) ---
st.markdown("""
<style>
    .main-header {font-size: 30px; font-weight: bold; color: #4B4B4B; text-align: center; margin-bottom: 20px;}
    .stAlert {box-shadow: 2px 2px 5px rgba(0,0,0,0.1);}
    div[data-testid="stMetricValue"] {font-size: 24px;}
</style>
""", unsafe_allow_html=True)

# --- GESTION DE LA BASE DE DONNÉES CLOUD (Via API Render) ---
def log_action(user, action, target, details):
    now = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    payload = {"timestamp": now, "user_email": user, "action": action, "target": target, "details": details}
    try: requests.post(f"{API_URL}/logs/", json=payload)
    except: pass

def get_logs():
    try:
        r = requests.get(f"{API_URL}/logs/")
        if r.status_code == 200 and r.json():
            return pd.DataFrame(r.json())
    except: pass
    return pd.DataFrame(columns=["timestamp", "user_email", "action", "target", "details"])

def get_all_lists():
    default_lists = ["PEP Locale", "Sanction Locale", "Listes Internationales"]
    try:
        r = requests.get(f"{API_URL}/lists/")
        if r.status_code == 200:
            custom_lists = [item["name"] for item in r.json()]
            return default_lists + custom_lists
    except: pass
    return default_lists

def add_custom_list(name):
    try:
        r = requests.post(f"{API_URL}/lists/", json={"name": name})
        return r.status_code == 200
    except: return False

def delete_custom_list(name):
    try:
        r = requests.delete(f"{API_URL}/lists/{name}")
        return r.status_code == 200
    except: return False

def save_scan(client_name, status, details):
    now = datetime.now().strftime("%Y-%m-%d")
    payload = {"date": now, "client_name": client_name, "status": status, "details": details}
    try: requests.post(f"{API_URL}/history/", json=payload)
    except: pass

def load_stats():
    try:
        r = requests.get(f"{API_URL}/history/")
        if r.status_code == 200 and r.json():
            return pd.DataFrame(r.json())
    except: pass
    return pd.DataFrame(columns=["date", "client_name", "status", "details"])


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
    
    if "ALERTE" in str(status) or "ELEVE" in str(status): color = colors.red; text_status = "REJETÉ / ALERTE"
    else: color = colors.green; text_status = "VÉRIFIÉ / CONFORME"
    
    c.setFillColor(color); c.setFont("Helvetica-Bold", 16); c.drawString(50, height - 280, f"STATUT : {text_status}")
    c.setFillColor(colors.black); c.setFont("Helvetica", 12)
    
    lines = textwrap.wrap(f"Détail : {risk_details}", width=80) 
    y_pos = height - 310
    for line in lines:
        c.drawString(50, y_pos, line)
        y_pos -= 20 
        
    c.save(); buffer.seek(0)
    return buffer

def create_global_report(dataframe):
    buffer = io.BytesIO()
    doc = SimpleDocTemplate(buffer, pagesize=letter)
    elements = []
    styles = getSampleStyleSheet()
    elements.append(Paragraph("<b>Rapport Global de Conformité</b>", styles['Title']))
    elements.append(Spacer(1, 12))
    rejected = len(dataframe[dataframe['Statut'].str.contains("REJETÉ") | dataframe['Statut'].str.contains("ALERTE")])
    total = len(dataframe); compliant = total - rejected
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
st.markdown("<h1 style='text-align: center;'>🛡️ ARGOS 360° 🛡️</h1>", unsafe_allow_html=True)
st.markdown("<h4 style='text-align: center;'>Système de Gestion des référentiels KYC</h4>", unsafe_allow_html=True)
st.markdown("<hr>", unsafe_allow_html=True)

# --- LOGIN ---
if "token" not in st.session_state: st.session_state["token"] = None
if "user_email" not in st.session_state: st.session_state["user_email"] = ""

with st.sidebar:
    st.image("https://cdn-icons-png.flaticon.com/512/9370/9370273.png", width=50)
    st.header("🔐 Accès Sécurisé")
    
    if st.session_state["token"] is None:
        with st.form("login_form"):
            email = st.text_input("Email", "admin@sgi.ci")
            password = st.text_input("Mot de passe", type="password")
            submit = st.form_submit_button("Se connecter")
            
        if submit:
            try:
                res = requests.post(f"{API_URL}/token", data={"username": email, "password": password})
                if res.status_code == 200: 
                    st.session_state["token"] = res.json().get("access_token")
                    st.session_state["user_email"] = email
                    st.success("✅ Connexion réussie !")
                    st.rerun()
                else: 
                    st.error("❌ Identifiants incorrects")
            except Exception as e:
                st.error("⛔ Serveur inaccessible (Réveil en cours...)")
    
    else:
        st.success(f"👤 {st.session_state['user_email']}")
        if st.button("Se déconnecter"): 
            st.session_state["token"] = None
            st.session_state["user_email"] = ""
            st.rerun()

# --- APP PRINCIPALE ---
if st.session_state["token"]:
    headers = {"Authorization": f"Bearer {st.session_state['token']}"}
    
    # NAVIGATION
    menu = st.sidebar.radio("Menu", ["📊 Tableau de Bord", "🔍 Vérifications", "⚙️ Gestion des Listes"])

    # === TABLEAU DE BORD ===
    if menu == "📊 Tableau de Bord":
        st.subheader("Vue d'ensemble")
        df = load_stats()
        if not df.empty:
            c1, c2, c3 = st.columns(3)
            c1.metric("Vérifications Totales", len(df))
            c2.metric("✅ Conformes", len(df) - len(df[df['status'].str.contains('ALERTE')]))
            c3.metric("🚨 Alertes", len(df[df['status'].str.contains('ALERTE')]))
            
            g1, g2 = st.columns(2)
            with g1: st.plotly_chart(px.pie(df, names='status', title='Ratio Conformité', color_discrete_sequence=['green', 'red']), use_container_width=True)
            with g2: st.plotly_chart(px.bar(df, x='date', title='Volume Quotidien'), use_container_width=True)
        else:
            st.info("Aucune donnée disponible. Lancez un scan pour alimenter les statistiques !")

    # === VÉRIFICATIONS ===
    elif menu == "🔍 Vérifications":
        t1, t2 = st.tabs(["👤 Unitaire", "📂 Masse (Excel)"])
        
        with t1:
            st.write("Scan rapide d'un individu.")
            col1, col2 = st.columns(2)
            with col1: name = st.text_input("Nom Complet")
            with col2: nid = st.text_input("ID / Matricule")
            
            if st.button("Lancer Scan", type="primary"):
                if name:
                    try:
                        r = requests.post(f"{API_URL}/clients/", json={"full_name": name, "entity_type": "Physique", "national_id": nid, "country_residence": "CI", "tenant_id": "MANUAL"}, headers=headers)
                        if r.status_code == 200:
                            d = r.json()
                            risk = d.get("risk_score")
                            details = d.get("details", "Non spécifié")
                            status = "ALERTE" if risk in ["ELEVE", "High"] else "CONFORME"
                            
                            res_col1, res_col2 = st.columns([1, 1])
                            
                            with res_col1:
                                st.write("### 📝 Rapport d'Analyse")
                                if status == "ALERTE": 
                                    st.error(f"🚨 {details}") 
                                else: 
                                    st.success(f"✅ RAS - Client Conforme")
                                    details = "RAS"
                                
                                pdf = create_kyc_pdf(name, nid, status, details)
                                st.download_button("Télécharger Rapport PDF", pdf, "rapport_kyc.pdf", "application/pdf")
                            
                            with res_col2:
                                score_val = 95 if status == "ALERTE" else 10
                                bar_color = "red" if status == "ALERTE" else "green"
                                
                                fig = go.Figure(go.Indicator(
                                    mode = "gauge+number",
                                    value = score_val,
                                    title = {'text': "Niveau de Risque", 'font': {'size': 20}},
                                    gauge = {
                                        'axis': {'range': [0, 100]},
                                        'bar': {'color': bar_color},
                                        'steps': [
                                            {'range': [0, 40], 'color': "#e6ffe6"}, 
                                            {'range': [40, 75], 'color': "#fff0b3"}, 
                                            {'range': [75, 100], 'color': "#ffe6e6"} 
                                        ]
                                    }
                                ))
                                fig.update_layout(height=250, margin=dict(l=10, r=10, t=40, b=10))
                                st.plotly_chart(fig, use_container_width=True)

                            # Sauvegarde CLOUD
                            save_scan(name, status, details)
                            log_action(st.session_state["user_email"], "SCAN_UNITAIRE", name, status)
                            
                        else:
                            st.error(f"❌ Le Backend a renvoyé une erreur {r.status_code}. Détails: {r.text}")
                    except Exception as e: 
                        st.error(f"Erreur de connexion au serveur : {e}")
        with t2:
            st.write("Scan de liste clients (Excel/CSV).")
            upl = st.file_uploader("Fichier Client", type=["xlsx", "csv"])
            if upl and st.button("Scanner Liste"):
                df = pd.read_csv(upl) if upl.name.endswith('.csv') else pd.read_excel(upl)
                res = []
                bar = st.progress(0)
                for i, row in df.iterrows():
                    n = row.get('Nom', row.get('Name', 'Inconnu'))
                    client_id = row.get('ID', row.get('Matricule', 'N/A'))
                    
                    try:
                        r = requests.post(f"{API_URL}/clients/", json={"full_name": str(n), "entity_type": "P", "national_id": str(client_id), "country_residence": "CI", "tenant_id": "BULK"}, headers=headers)
                        rk = r.json().get("risk_score", "Low")
                        stt = "🔴 REJETÉ" if rk in ["ELEVE", "High"] else "🟢 CONFORME"
                        
                        res.append({"Nom": n, "ID": client_id, "Statut": stt, "Détail": r.json().get("details", "")})
                        # Sauvegarde CLOUD
                        save_scan(str(n), "ALERTE" if "REJETÉ" in stt else "CONFORME", "Bulk Scan")
                    except: 
                        res.append({"Nom": n, "ID": client_id, "Statut": "⚠️ ERREUR", "Détail": "Tech Error"})
                        
                    bar.progress((i+1)/len(df))
                
                fin = pd.DataFrame(res)
                st.dataframe(fin)
                log_action(st.session_state["user_email"], "SCAN_MASSE", upl.name, f"{len(df)} lignes")
                st.download_button("Rapport PDF", create_global_report(fin), "rapport_global.pdf", "application/pdf")

    # === GESTION DES LISTES ===
    elif menu == "⚙️ Gestion des Listes":
        st.subheader("⚙️ Administration des Listes de Sanctions & PEP")
        
        tabs = st.tabs(["📝 Entrée Manuelle", "📂 Import Fichier", "➕ Créer Liste", "🗑️ Supprimer Liste", "📜 Logs"])

        with tabs[0]:
            st.info("Ajouter individuellement une personne à une liste locale.")
            all_lists = get_all_lists()
            manual_lists = [L for L in all_lists if L != "Listes Internationales"]
            
            c1, c2 = st.columns(2)
            with c1:
                target_list = st.selectbox("Choisir la Liste cible", manual_lists)
                bad_name = st.text_input("Nom de la personne / Entité")
            with c2:
                details = st.text_input("Motif / Détails")
            
            if st.button("Ajouter à la liste", type="primary"):
                if bad_name and target_list:
                    full_details = f"[{target_list}] {details}"
                    payload = {"name": bad_name, "list_source": target_list}
                    try:
                        r = requests.post(f"{API_URL}/sanctions/", json=payload, headers=headers)
                        if r.status_code == 200:
                            st.success(f"✅ {bad_name} ajouté à '{target_list}' avec succès.")
                            log_action(st.session_state["user_email"], "AJOUT_MANUEL", bad_name, f"Liste: {target_list}")
                        else: st.error("Erreur serveur ou format de donnée incorrect.")
                    except Exception as e: st.error(f"Erreur: {e}")
                else: st.warning("Veuillez remplir le nom et choisir une liste.")

        with tabs[1]:
            st.info("Mettre à jour une liste (Locale ou Internationale) via Excel/CSV.")
            target_list_import = st.selectbox("Sélectionner la Liste à mettre à jour", get_all_lists())
            upl_file = st.file_uploader("Fichier de mise à jour", type=["csv", "xlsx"])
            
            if upl_file and st.button("Importer les données 📥"):
                try:
                    df = pd.read_csv(upl_file) if upl_file.name.endswith('.csv') else pd.read_excel(upl_file)
                    st.write(f"Aperçu ({len(df)} entrées) :")
                    st.dataframe(df.head(3))
                    progress = st.progress(0); count_ok = 0
                    for i, row in df.iterrows():
                        name_val = row.get('Nom') or row.get('Name') or row.get('Full Name') or "Inconnu"
                        if name_val != "Inconnu":
                            payload = {"name": str(name_val), "list_source": target_list_import}
                            r = requests.post(f"{API_URL}/sanctions/", json=payload, headers=headers)
                            if r.status_code == 200: 
                                count_ok += 1
                        progress.progress((i+1)/len(df))
                    
                    if count_ok > 0:
                        st.success(f"✅ Import terminé ! {count_ok} entrées ajoutées à '{target_list_import}'.")
                        log_action(st.session_state["user_email"], "IMPORT_FICHIER", target_list_import, f"Fichier: {upl_file.name}")
                    else:
                        st.error("❌ L'import a échoué. Vérifie que le Backend fonctionne.")
                except Exception as e: st.error(f"Erreur de lecture : {e}")

        with tabs[2]:
            st.write("Définir une nouvelle catégorie de liste.")
            new_list_name = st.text_input("Nom de la nouvelle liste (ex: Liste Noire Fournisseurs)")
            if st.button("Créer la Liste"):
                if new_list_name:
                    if new_list_name in get_all_lists(): st.warning("Cette liste existe déjà.")
                    else:
                        if add_custom_list(new_list_name):
                            st.success(f"Liste '{new_list_name}' créée !")
                            log_action(st.session_state["user_email"], "CREATION_LISTE", new_list_name, "Nouvelle catégorie")
                            st.rerun()
                        else: st.error("Erreur serveur.")

        with tabs[3]:
            st.write("Supprimer une catégorie de liste personnalisée.")
            default_lists = ["PEP Locale", "Sanction Locale", "Listes Internationales"]
            all_custom = [L for L in get_all_lists() if L not in default_lists]
            
            if not all_custom:
                st.info("Aucune liste personnalisée à supprimer. (Les listes par défaut ne peuvent pas être supprimées).")
            else:
                list_to_delete = st.selectbox("Choisir la liste à supprimer", all_custom)
                if st.button("Supprimer cette liste"):
                    if delete_custom_list(list_to_delete):
                        st.success(f"Liste '{list_to_delete}' supprimée avec succès !")
                        log_action(st.session_state["user_email"], "SUPPRESSION_LISTE", list_to_delete, "Catégorie supprimée")
                        st.rerun()
                    else: 
                        st.error("Erreur lors de la suppression.")

        with tabs[4]:
            st.write("Historique des actions administratives (Sauvegardé dans le Cloud).")
            df_logs = get_logs()
            if not df_logs.empty and 'id' in df_logs.columns:
                df_logs = df_logs.drop(columns=['id']) # On cache l'ID technique
            st.dataframe(df_logs, use_container_width=True)
            if st.button("Rafraîchir les logs"): st.rerun()
else:
    st.info("👈 Veuillez vous connecter via le menu à gauche.")
