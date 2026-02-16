import streamlit as st
import textwrap
import requests
import pandas as pd
import io
import time
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

# --- GESTION DE LA BASE DE DONNÉES CLOUD ---
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

def get_users():
    try:
        r = requests.get(f"{API_URL}/users/")
        if r.status_code == 200 and r.json():
            return pd.DataFrame(r.json())
    except: pass
    return pd.DataFrame(columns=["id", "email", "full_name", "role", "is_active"])

def create_user(email, password, full_name, role):
    payload = {"email": email, "password": password, "full_name": full_name, "role": role}
    try:
        r = requests.post(f"{API_URL}/users/", json=payload)
        return r.status_code == 200, r.text
    except Exception as e:
        return False, str(e)

def get_alerts():
    try:
        r = requests.get(f"{API_URL}/alerts/")
        if r.status_code == 200:
            return pd.DataFrame(r.json())
    except: pass
    return pd.DataFrame()

def update_alert_api(alert_id, data):
    try:
        r = requests.patch(f"{API_URL}/alerts/{alert_id}", json=data)
        if r.status_code == 200:
            return True, "OK"
        else:
            return False, f"Erreur {r.status_code} : {r.text}"
    except Exception as e: 
        return False, str(e)

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
        c.drawString(50, y_pos, line); y_pos -= 20 
        
    c.save(); buffer.seek(0)
    return buffer

def create_global_report(dataframe):
    buffer = io.BytesIO()
    doc = SimpleDocTemplate(buffer, pagesize=letter)
    elements = []
    styles = getSampleStyleSheet()
    elements.append(Paragraph("<b>Rapport Global de Conformité</b>", styles['Title']))
    elements.append(Spacer(1, 12))
    if 'Statut' in dataframe.columns:
        rejected = len(dataframe[dataframe['Statut'].str.contains("REJETÉ") | dataframe['Statut'].str.contains("ALERTE")])
    else: rejected = 0
    total = len(dataframe); compliant = total - rejected
    stats_text = f"Date : {datetime.now().strftime('%d/%m/%Y')}<br/>Total : {total} | Conformes : {compliant} | <b>Alertes : {rejected}</b>"
    elements.append(Paragraph(stats_text, styles['Normal'])); elements.append(Spacer(1, 20))
    data = [["Nom du Client", "ID National", "Statut", "Détail"]]
    for index, row in dataframe.iterrows(): data.append([str(row.get('Nom', '')), str(row.get('ID', '')), str(row.get('Statut', '')), str(row.get('Détail', ''))])
    table = Table(data)
    table.setStyle(TableStyle([('BACKGROUND', (0, 0), (-1, 0), colors.darkblue), ('TEXTCOLOR', (0, 0), (-1, 0), colors.whitesmoke),
                               ('ALIGN', (0, 0), (-1, -1), 'CENTER'), ('FONTNAME', (0, 0), (-1, 0), 'Helvetica-Bold'),
                               ('BOTTOMPADDING', (0, 0), (-1, 0), 12), ('BACKGROUND', (0, 1), (-1, -1), colors.beige), ('GRID', (0, 0), (-1, -1), 1, colors.black)]))
    elements.append(table); doc.build(elements); buffer.seek(0)
    return buffer

def create_investigation_pdf(row_data):
    buffer = io.BytesIO()
    c = canvas.Canvas(buffer, pagesize=letter)
    width, height = letter
    
    c.setFont("Helvetica-Bold", 24); c.drawString(50, height - 50, "ARGOS 360°")
    c.setFont("Helvetica", 12); c.drawString(50, height - 70, "Rapport Officiel d'Investigation AML/KYC")
    c.setLineWidth(2); c.line(50, height - 80, width - 50, height - 80)
    
    c.setFont("Helvetica-Bold", 16)
    c.drawCentredString(width / 2, height - 120, f"DOSSIER D'ALERTE #{row_data.get('id', 'N/A')}")
    
    c.setFont("Helvetica-Bold", 12); c.drawString(50, height - 160, "1. Détails de la Détection")
    c.setFont("Helvetica", 11)
    c.drawString(60, height - 180, f"Date de création : {row_data.get('created_at_str', row_data.get('created_at', 'N/A'))}")
    c.drawString(60, height - 200, f"Client Scanné : {row_data.get('client_name', 'N/A')}")
    c.drawString(60, height - 220, f"Cible Détectée (Base Sanctions) : {row_data.get('matched_name', 'N/A')}")
    c.drawString(60, height - 240, f"Score de similitude IA : {row_data.get('similarity_score', 0)}%")
    c.drawString(60, height - 260, f"Délai (SLA) : {row_data.get('SLA', 'N/A')}")
    
    c.setFont("Helvetica-Bold", 12); c.drawString(50, height - 300, "2. Décision de Conformité et Traitement")
    c.setFont("Helvetica", 11)
    
    statut = row_data.get('status', 'OUVERT')
    decision = row_data.get('decision', 'EN_ATTENTE')
    if pd.isna(decision) or not decision: decision = "EN_ATTENTE"
    
    if decision == "CONFIRME": color = colors.red
    elif decision == "FAUX_POSITIF": color = colors.green
    else: color = colors.orange
    
    c.drawString(60, height - 320, f"Statut actuel du dossier : {statut}")
    c.setFillColor(color); c.drawString(60, height - 340, f"Décision finale : {decision}")
    c.setFillColor(colors.black)
    
    c.drawString(60, height - 370, "Commentaires de l'analyste / Justification :")
    
    comments = row_data.get('comments', 'Aucun commentaire.')
    if pd.isna(comments) or comments in ["None", "", "nan"]: comments = "Aucun commentaire n'a été saisi pour justifier cette décision."
    
    lines = textwrap.wrap(str(comments), width=80) 
    y_pos = height - 390
    for line in lines:
        c.drawString(70, y_pos, line); y_pos -= 20 
        
    c.setFont("Helvetica-Oblique", 10)
    c.drawString(50, 50, f"Document généré par le système ARGOS le {datetime.now().strftime('%d/%m/%Y à %H:%M:%S')}")
    
    c.save(); buffer.seek(0)
    return buffer

# --- TITRE ---
st.markdown("<h1 style='text-align: center;'>🛡️ ARGOS 360° 🛡️</h1>", unsafe_allow_html=True)
st.markdown("<h4 style='text-align: center;'>Système de Gestion des référentiels KYC</h4>", unsafe_allow_html=True)
st.markdown("<hr>", unsafe_allow_html=True)

# --- LOGIN ---
if "token" not in st.session_state: st.session_state["token"] = None
if "user_email" not in st.session_state: st.session_state["user_email"] = ""
if "role" not in st.session_state: st.session_state["role"] = "" 

with st.sidebar:
    st.title("🛡️")
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
                    data = res.json()
                    st.session_state["token"] = data.get("access_token")
                    st.session_state["user_email"] = email
                    st.session_state["role"] = data.get("role", "AGENT") 
                    st.success("✅ Connexion réussie !")
                    st.rerun()
                else: st.error("❌ Identifiants incorrects")
            except Exception as e: st.error("⛔ Serveur inaccessible (Réveil en cours...)")
    
    else:
        st.success(f"👤 {st.session_state['user_email']} ({st.session_state['role']})")
        if st.button("Se déconnecter"): 
            st.session_state["token"] = None; st.session_state["user_email"] = ""; st.session_state["role"] = ""
            st.rerun()

# --- APP PRINCIPALE ---
if st.session_state["token"]:
    headers = {"Authorization": f"Bearer {st.session_state['token']}"}
    
    menu_options = ["📊 Tableau de Bord", "🔍 Vérifications", "🚦 Alertes", "⚙️ Gestion des Listes"]
    if st.session_state["role"] == "ADMIN": menu_options.append("👥 Utilisateurs") 
        
    menu = st.sidebar.radio("Menu", menu_options)

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
                            risk = d.get("risk_score"); details = d.get("details", "Non spécifié"); sim_score = d.get("similarity_score", 0) 
                            status = "ALERTE" if risk in ["ELEVE", "High"] else "CONFORME"
                            
                            res_col1, res_col2 = st.columns([1, 1])
                            with res_col1:
                                st.write("### 📝 Rapport d'Analyse")
                                if status == "ALERTE": st.error(f"{details}") 
                                else: st.success(f"{details}")
                                pdf = create_kyc_pdf(name, nid, status, details)
                                st.download_button("Télécharger Rapport PDF", pdf, "rapport_kyc.pdf", "application/pdf")
                            
                            with res_col2:
                                score_val = sim_score if status == "ALERTE" else 10
                                bar_color = "red" if status == "ALERTE" else "green"
                                fig = go.Figure(go.Indicator(
                                    mode = "gauge+number", value = score_val, title = {'text': "Niveau de Risque", 'font': {'size': 20}},
                                    gauge = {'axis': {'range': [0, 100]}, 'bar': {'color': bar_color}, 'steps': [{'range': [0, 40], 'color': "#e6ffe6"}, {'range': [40, 75], 'color': "#fff0b3"}, {'range': [75, 100], 'color': "#ffe6e6"}]}
                                ))
                                fig.update_layout(height=250, margin=dict(l=10, r=10, t=40, b=10))
                                st.plotly_chart(fig, use_container_width=True)

                            save_scan(name, status, details)
                            log_action(st.session_state["user_email"], "SCAN_UNITAIRE", name, status)
                        else: st.error(f"❌ Erreur Backend {r.status_code}")
                    except Exception as e: st.error(f"Erreur connexion : {e}")
        with t2:
            st.write("Scan de liste clients (Excel/CSV).")
            upl = st.file_uploader("Fichier Client", type=["xlsx", "csv"])
            if upl and st.button("Scanner Liste"):
                df = pd.read_csv(upl) if upl.name.endswith('.csv') else pd.read_excel(upl)
                res = []; bar = st.progress(0)
                for i, row in df.iterrows():
                    n = row.get('Nom', row.get('Name', 'Inconnu'))
                    client_id = row.get('ID', row.get('Matricule', 'N/A'))
                    try:
                        r = requests.post(f"{API_URL}/clients/", json={"full_name": str(n), "entity_type": "P", "national_id": str(client_id), "country_residence": "CI", "tenant_id": "BULK"}, headers=headers)
                        rk = r.json().get("risk_score", "Low")
                        stt = "🔴 REJETÉ" if rk in ["ELEVE", "High"] else "🟢 CONFORME"
                        res.append({"Nom": n, "ID": client_id, "Statut": stt, "Détail": r.json().get("details", "")})
                        save_scan(str(n), "ALERTE" if "REJETÉ" in stt else "CONFORME", "Bulk Scan")
                    except: res.append({"Nom": n, "ID": client_id, "Statut": "⚠️ ERREUR", "Détail": "Tech Error"})
                    bar.progress((i+1)/len(df))
                
                fin = pd.DataFrame(res)
                st.dataframe(fin)
                st.download_button("Rapport PDF Global", create_global_report(fin), "rapport_global.pdf")

    # === CENTRE D'ALERTES (NOUVEAU WORKFLOW MAKER/CHECKER) ===
    elif menu == "🚦 Alertes":
        st.subheader("🚦 Centre de Traitement (Principe des 4 Yeux)")
        df_a = get_alerts()
        
        if df_a.empty: st.info("RAS : Aucune alerte en attente de traitement.")
        else:
            now = datetime.now()
            def calculate_sla(row):
                if row['status'] == 'FERME': return "✅ Traité"
                try:
                    created_dt = pd.to_datetime(row['created_at']).replace(tzinfo=None)
                    delta_hours = (now - created_dt).total_seconds() / 3600
                    if delta_hours > 48: return "🚨 HORS DÉLAI (>48h)"
                    elif delta_hours > 24: return "⚠️ Attention (>24h)"
                    else: return "🟢 Dans les temps"
                except: return "Inconnu"

            df_a['SLA'] = df_a.apply(calculate_sla, axis=1)
            if 'created_at' in df_a.columns: df_a['created_at_str'] = pd.to_datetime(df_a['created_at']).dt.strftime('%Y-%m-%d %H:%M')

            st.write("### 🗂️ Filtres rapides")
            # Ajout du filtre "A_VALIDER"
            filter_stat = st.radio("Afficher les alertes :", ["Toutes", "OUVERT", "EN_COURS", "A_VALIDER", "FERME"], horizontal=True)
            df_filtered = df_a.copy() if filter_stat == "Toutes" else df_a[df_a['status'] == filter_stat].copy()
            
            if df_filtered.empty: st.warning(f"Aucune alerte trouvée avec le filtre : {filter_stat}")
            else:
                df_filtered['Priorité'] = df_filtered['similarity_score'].apply(lambda x: '🔴 Haute' if x >= 90 else '🟠 Moyenne')
                alert_options = df_filtered.apply(lambda r: f"Dossier #{r['id']} | {r['SLA']} | {r['client_name']} (Similitude: {r['similarity_score']}%)", axis=1).tolist()
                alert_ids = df_filtered['id'].tolist()
                
                sel_index = st.selectbox("🎯 Sélectionner le dossier à traiter", range(len(alert_options)), format_func=lambda x: alert_options[x])
                sel_id = alert_ids[sel_index]
                row = df_filtered.iloc[sel_index]

                col_inf, col_form = st.columns(2)
                
                with col_inf:
                    st.markdown(f"### 📁 Dossier #{sel_id}")
                    if "HORS DÉLAI" in row['SLA']: st.error(f"**Délai de traitement (SLA) : {row['SLA']}**")
                    elif "Attention" in row['SLA']: st.warning(f"**Délai de traitement (SLA) : {row['SLA']}**")
                    else: st.success(f"**Délai de traitement (SLA) : {row['SLA']}**")

                    st.write(f"**Priorité IA :** {row['Priorité']}"); st.write(f"**Client scanné :** {row['client_name']}")
                    st.write(f"**Cible détectée :** {row['matched_name']}"); st.write(f"**Score de similitude :** {row['similarity_score']}%")
                    st.write(f"**Date d'ouverture :** {row.get('created_at_str', 'N/A')}"); st.write(f"**Assigné à :** {row.get('assigned_to', 'Non assigné')}")
                    st.info(f"**Statut actuel :** {row['status']}")
                    st.markdown("---")
                    investigation_pdf = create_investigation_pdf(row.to_dict())
                    st.download_button(label="📄 Télécharger le Rapport d'Investigation", data=investigation_pdf, file_name=f"rapport_investigation_alerte_{sel_id}.pdf", mime="application/pdf", type="secondary")

                with col_form:
                    st.markdown("### ✍️ Décision & Preuves (Maker / Checker)")
                    users_df = get_users()
                    agent_list = ["Non assigné"]
                    if not users_df.empty: agent_list += users_df['email'].tolist()
                    
                    current_assignee = row.get('assigned_to'); current_stat = row.get('status'); current_dec = row.get('decision'); current_comm = row.get('comments')
                    if pd.isna(current_assignee) or current_assignee not in agent_list: current_assignee = "Non assigné"
                    if pd.isna(current_stat) or current_stat not in ["OUVERT", "EN_COURS", "A_VALIDER", "FERME"]: current_stat = "OUVERT"
                    if pd.isna(current_dec) or current_dec not in ["EN_ATTENTE", "FAUX_POSITIF", "CONFIRME"]: current_dec = "EN_ATTENTE"
                    if pd.isna(current_comm) or current_comm == "None": current_comm = ""

                    user_role = st.session_state.get("role", "AGENT")

                    with st.form("alert_update_form", clear_on_submit=True):
                        st.markdown(f"**Votre Rôle Actuel :** `{user_role}`")
                        new_assignee = st.selectbox("👤 Assigner le dossier à :", agent_list, index=agent_list.index(current_assignee))
                        
                        # --- WORKFLOW 1 : CHECKER (L'ADMIN VALIDE) ---
                        if current_stat == "A_VALIDER" and user_role == "ADMIN":
                            st.warning("👁️ Action requise (Checker) : Validez ou rejetez la proposition de l'Agent.")
                            st.text_area("Historique du dossier :", value=str(current_comm), disabled=True)
                            
                            action_checker = st.radio("Décision de supervision :", ["✅ Approuver (Fermer le dossier)", "❌ Rejeter (Retour à l'Agent)"])
                            checker_comm = st.text_input("Commentaire de supervision :")
                            
                            if st.form_submit_button("Valider la Supervision"):
                                final_status = "FERME" if "Approuver" in action_checker else "EN_COURS"
                                final_comm = current_comm + f"\n\n🛑 [CHECKER - {st.session_state['user_email']}] {action_checker} : {checker_comm}"
                                payload = {"status": final_status, "decision": current_dec, "comments": final_comm, "assigned_to": new_assignee}
                                success, message = update_alert_api(sel_id, payload)
                                if success:
                                    st.success("✅ Supervision appliquée !")
                                    log_action(st.session_state["user_email"], "SUPERVISION", str(sel_id), f"Action: {action_checker}")
                                    time.sleep(1.5); st.rerun()
                                else: st.error(f"❌ {message}")
                                
                        # --- WORKFLOW 2 : MAKER (L'AGENT EST BLOQUÉ EN ATTENTE) ---
                        elif current_stat == "A_VALIDER" and user_role == "AGENT":
                            st.info("⏳ Ce dossier a été soumis et est en attente de validation par un Superviseur (Principe des 4 Yeux).")
                            st.text_area("Vos commentaires :", value=str(current_comm), disabled=True)
                            st.form_submit_button("🔒 Dossier verrouillé", disabled=True)
                            
                        # --- WORKFLOW 3 : MAKER (L'AGENT OU L'ADMIN PROPOSE UNE DÉCISION) ---
                        else:
                            st.write("🛠️ **Proposer une action (Maker)**")
                            
                            # BRIDAGE : Un AGENT ne peut plus fermer un dossier tout seul !
                            if user_role == "ADMIN": list_status = ["OUVERT", "EN_COURS", "A_VALIDER", "FERME"]
                            else: list_status = ["OUVERT", "EN_COURS", "A_VALIDER"]
                                
                            new_status = st.selectbox("Changer Statut", list_status, index=list_status.index(current_stat) if current_stat in list_status else 0)
                            new_decision = st.selectbox("Proposition de Décision", ["EN_ATTENTE", "FAUX_POSITIF", "CONFIRME"], index=["EN_ATTENTE", "FAUX_POSITIF", "CONFIRME"].index(current_dec))
                            new_comm = st.text_area("Commentaires / Justification", value=str(current_comm))
                            st.markdown("**📎 Pièces justificatives**")
                            uploaded_file = st.file_uploader("Joindre un fichier (PDF, JPG, PNG)", type=["pdf", "png", "jpg", "jpeg"])

                            if st.form_submit_button("Enregistrer l'action"):
                                final_comm = new_comm
                                if uploaded_file: final_comm += f" \n\n📎 [Preuve jointe : {uploaded_file.name}]"
                                
                                # Si le Maker envoie en validation, on signe son acte
                                if new_status == "A_VALIDER":
                                    final_comm += f"\n\n📝 [MAKER - {st.session_state['user_email']}] Dossier soumis pour validation."

                                payload = {"status": new_status, "decision": new_decision, "comments": final_comm, "assigned_to": new_assignee}
                                success, message = update_alert_api(sel_id, payload)
                                if success:
                                    st.success("✅ Action enregistrée !")
                                    log_action(st.session_state["user_email"], "TRAITEMENT_MAKER", str(sel_id), f"Statut: {new_status}")
                                    time.sleep(1.5); st.rerun()
                                else: st.error(f"❌ {message}")

            st.markdown("---")
            st.write("### 📋 Historique Complet (Filtré)")
            columns_to_show = ['id', 'SLA', 'Priorité', 'client_name', 'status', 'assigned_to', 'created_at_str']
            st.dataframe(df_filtered[columns_to_show], use_container_width=True)

    # === GESTION DES LISTES ===
    elif menu == "⚙️ Gestion des Listes":
        st.subheader("⚙️ Administration des Listes")
        tabs = st.tabs(["📝 Entrée Manuelle", "📂 Import Fichier", "➕ Créer Liste", "🗑️ Supprimer Liste", "📜 Logs"])

        with tabs[0]:
            st.info("Ajouter individuellement une personne à une liste locale.")
            all_lists = get_all_lists()
            manual_lists = [L for L in all_lists if L != "Listes Internationales"]
            c1, c2 = st.columns(2)
            with c1: target_list = st.selectbox("Choisir la Liste cible", manual_lists); bad_name = st.text_input("Nom de la personne / Entité")
            with c2: details = st.text_input("Motif / Détails")
            
            with st.form("manual_add_form", clear_on_submit=True):
                submit_man = st.form_submit_button("Ajouter à la liste", type="primary")
                if submit_man:
                    if bad_name and target_list:
                        payload = {"name": bad_name, "list_source": target_list}
                        try:
                            r = requests.post(f"{API_URL}/sanctions/", json=payload, headers=headers)
                            if r.status_code == 200:
                                st.success(f"✅ '{bad_name}' ajouté à '{target_list}' avec succès.")
                                log_action(st.session_state["user_email"], "AJOUT_MANUEL", bad_name, f"Liste: {target_list}")
                            else:
                                st.error(f"❌ Erreur du serveur (Code {r.status_code}) : {r.text}")
                        except Exception as e:
                            st.error(f"❌ Impossible de joindre le serveur : {e}")
                    else: st.warning("Veuillez remplir le nom et choisir une liste.")

        with tabs[1]:
            # EXIGENCE SP-LS-07 : GESTION MULTI-FORMATS (CSV, EXCEL, JSON, XML)
            st.info("Mettre à jour une liste via import multi-formats (CSV, Excel, JSON, XML).")
            target_list_import = st.selectbox("Sélectionner la Liste à mettre à jour", get_all_lists())
            
            with st.form("import_form", clear_on_submit=True):
                # Ajout des formats json et xml
                upl_file = st.file_uploader("Fichier de données", type=["csv", "xlsx", "json", "xml"])
                submit_imp = st.form_submit_button("Importer les données 📥")
                if submit_imp and upl_file:
                    try:
                        # Moteur de lecture intelligent selon l'extension du fichier
                        if upl_file.name.endswith('.csv'): df = pd.read_csv(upl_file)
                        elif upl_file.name.endswith('.xlsx'): df = pd.read_excel(upl_file)
                        elif upl_file.name.endswith('.json'): df = pd.read_json(upl_file)
                        elif upl_file.name.endswith('.xml'): df = pd.read_xml(upl_file)
                        
                        st.write(f"Aperçu ({len(df)} entrées) :")
                        st.dataframe(df.head(3))
                        progress = st.progress(0); count_ok = 0
                        last_error = "" 
                        
                        for i, row in df.iterrows():
                            # Recherche du nom dans différentes colonnes possibles selon le fichier
                            name_val = row.get('Nom') or row.get('Name') or row.get('Full Name') or "Inconnu"
                            if name_val != "Inconnu":
                                payload = {"name": str(name_val), "list_source": target_list_import}
                                r = requests.post(f"{API_URL}/sanctions/", json=payload, headers=headers)
                                if r.status_code == 200: 
                                    count_ok += 1
                                else: 
                                    last_error = f"Code {r.status_code}: {r.text}"
                            progress.progress((i+1)/len(df))
                        
                        if count_ok > 0:
                            st.success(f"✅ Import terminé ! {count_ok} entrées ont bien été ajoutées à '{target_list_import}'.")
                            log_action(st.session_state["user_email"], "IMPORT_FICHIER", target_list_import, f"Fichier: {upl_file.name}")
                        else: 
                            st.error(f"❌ L'import a échoué. Détail technique : {last_error}")
                    except Exception as e: st.error(f"Erreur technique de lecture du fichier : {e}")

        with tabs[2]:
            # EXIGENCE SP-LS-04 : CRITICITÉ DES LISTES
            st.write("Définir une nouvelle catégorie de liste et son niveau de risque.")
            with st.form("create_list_form", clear_on_submit=True):
                new_list_name = st.text_input("Nom de la nouvelle liste (ex: Liste Noire Fournisseurs)")
                # Nouveau champ : Niveau de criticité
                criticite = st.selectbox("Niveau de Criticité", ["🔴 Bloquant (Rejet Automatique)", "🟠 Renforcé (Investigation Requise)", "🟡 Standard (Alerte Simple)"])
                
                if st.form_submit_button("Créer la Liste"):
                    if new_list_name:
                        # On fusionne le nom et la criticité pour le visuel et la base de données
                        mot_cle_criticite = criticite.split(" ")[1] # Récupère "Bloquant", "Renforcé" ou "Standard"
                        nom_final = f"{new_list_name} [{mot_cle_criticite}]"
                        
                        if nom_final in get_all_lists(): st.warning("Cette liste existe déjà.")
                        else:
                            if add_custom_list(nom_final):
                                st.success(f"Liste '{nom_final}' créée avec succès !")
                                log_action(st.session_state["user_email"], "CREATION_LISTE", nom_final, f"Criticité: {mot_cle_criticite}")
                                time.sleep(1.5)
                                st.rerun()
                            else: st.error("Erreur serveur.")

        with tabs[3]:
            st.write("Supprimer une catégorie de liste personnalisée.")
            default_lists = ["PEP Locale", "Sanction Locale", "Listes Internationales"]
            all_custom = [L for L in get_all_lists() if L not in default_lists]
            
            if not all_custom: st.info("Aucune liste personnalisée à supprimer. (Les listes par défaut ne peuvent pas être supprimées).")
            else:
                list_to_delete = st.selectbox("Choisir la liste à supprimer", all_custom)
                if st.button("Supprimer cette liste"):
                    if delete_custom_list(list_to_delete):
                        st.success(f"Liste '{list_to_delete}' supprimée avec succès !")
                        log_action(st.session_state["user_email"], "SUPPRESSION_LISTE", list_to_delete, "Catégorie supprimée")
                        time.sleep(1.5)
                        st.rerun()
                    else: st.error("Erreur lors de la suppression.")

        with tabs[4]:
            st.write("Historique des actions administratives (Sauvegardé dans le Cloud).")
            df_logs = get_logs()
            if not df_logs.empty and 'id' in df_logs.columns: df_logs = df_logs.drop(columns=['id']) 
            st.dataframe(df_logs, use_container_width=True)
            if st.button("Rafraîchir les logs"): st.rerun()
                
    # === UTILISATEURS ===
    elif menu == "👥 Utilisateurs":
        st.subheader("👥 Gestion de l'Équipe")
        tab_l, tab_a = st.tabs(["📋 Liste", "➕ Ajouter"])
        with tab_l:
            st.dataframe(get_users(), use_container_width=True)
        with tab_a:
            with st.form("new_user", clear_on_submit=True):
                n_em = st.text_input("Email")
                n_nm = st.text_input("Nom")
                n_ps = st.text_input("Pass", type="password")
                n_rl = st.selectbox("Rôle", ["AGENT", "ADMIN"])
                if st.form_submit_button("Créer"):
                    ok, msg = create_user(n_em, n_ps, n_nm, n_rl)
                    if ok: 
                        st.success(f"✅ Le compte de {n_nm} a été créé avec succès !")
                        time.sleep(1.5)
                        st.rerun()
                    else: st.error("Erreur")

else:
    st.info("👈 Veuillez vous connecter via le menu à gauche.")
