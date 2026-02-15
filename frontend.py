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
    
    if "ALERTE" in str(status) or "ELEVE" in str(status): color = colors.red; text_status = "REJETÉ
