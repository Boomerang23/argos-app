# README.md

````markdown
# ARGOS 360

Plateforme KYC & AML-CFT conçue pour automatiser les vérifications de conformité, la gestion des alertes et la génération de rapports d’audit.

ARGOS 360 permet :
- Vérification contre listes de sanctions et PEP
- Scan unitaire et scan de masse (Excel/CSV)
- Filtrage continu
- Gestion des alertes (Maker / Checker)
- Génération de certificats PDF
- Export registre d’audit
- API pour intégration externe

---

## 🏗 Architecture

Backend :
- FastAPI
- SQLAlchemy
- JWT Authentication
- SQLite (par défaut, configurable)

Frontend :
- Streamlit (interface interne)

Structure :

argos-app/
├── app/
│   ├── main.py
│   ├── models.py
│   ├── schemas.py
│   ├── services.py
│   ├── database.py
│   ├── auth.py
│   └── frontend.py
├── requirements.txt
└── packages.txt

---

## ⚙️ Installation

### 1️⃣ Cloner le projet

```bash
git clone https://github.com/Boomerang23/argos-app.git
cd argos-app
````

### 2️⃣ Créer un environnement virtuel

```bash
python -m venv venv
source venv/bin/activate   # macOS/Linux
venv\Scripts\activate      # Windows
```

### 3️⃣ Installer les dépendances

```bash
pip install -r requirements.txt
```

---

## 🔐 Variables d’environnement

Créer un fichier `.env` à la racine :

```env
DATABASE_URL=sqlite:///./argos.db
SECRET_KEY=change_this_secret_key
ALGORITHM=HS256
ACCESS_TOKEN_EXPIRE_MINUTES=60
```

⚠️ Ne jamais exposer le SECRET_KEY en production.

---

## 🚀 Lancer le Backend (API)

```bash
uvicorn app.main:app --reload
```

API disponible sur :

```
http://127.0.0.1:8000
```

Documentation interactive :

```
http://127.0.0.1:8000/docs
```

---

## 🖥 Lancer le Frontend (Streamlit)

Dans un nouveau terminal :

```bash
streamlit run app/frontend.py
```

Interface disponible sur :

```
http://localhost:8501
```

---

## 👥 Rôles utilisateurs

ARGOS 360 fonctionne avec séparation des tâches :

* AGENT :

  * Lance des scans
  * Traite les alertes
  * Ajoute commentaires
  * Met à valider

* ADMIN :

  * Valide ou rejette les alertes
  * Gère les utilisateurs
  * Gère les listes internes
  * Clôture les dossiers

---

## 📦 Fonctionnalités principales

### 🔍 Vérifications KYC

* Scan unitaire
* Scan de masse (CSV/Excel)
* Filtrage continu
* Certificat PDF d’absence de sanctions

### 🚦 Case Management

* File d’attente
* Score de similarité
* Gestion faux positifs
* Rapport officiel horodaté

### 📊 Audit & Registre

* Journal d’activité
* Export Excel/CSV
* Traçabilité complète

### 🔌 API & Intégration

* JWT sécurisé
* Vérifications en arrière-plan
* Intégration possible à des systèmes tiers

---

## 🛡 Sécurité

* Authentification JWT
* Séparation des rôles
* Journalisation des actions
* Protection des endpoints sensibles

---

## 🌍 Déploiement recommandé

Pour production :

* PostgreSQL au lieu de SQLite
* Variables d’environnement sécurisées
* Reverse proxy (Nginx)
* HTTPS obligatoire
* Docker (recommandé)
* Hébergement cloud (AWS / Azure / GCP)

---

## 📈 Roadmap (SaaS)

Prochaines évolutions :

* Multi-tenant (Organisation par client)
* Billing Stripe
* Gestion plans (Starter / Pro / Enterprise)
* Frontend Next.js premium
* Monitoring & observabilité
* CI/CD pipeline

---

## 📄 Licence

Propriétaire – Tous droits réservés.

---

## Contact

ARGOS 360
Plateforme KYC & AML-CFT
