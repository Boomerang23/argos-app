# 1. On part d'un système Linux léger avec Python
FROM python:3.10-slim

# 2. On installe les dépendances système (Le fameux moteur OCR et la langue française)
RUN apt-get update && apt-get install -y \
    tesseract-ocr \
    tesseract-ocr-fra \
    libgl1 \
    && rm -rf /var/lib/apt/lists/*

# 3. On définit le dossier de travail
WORKDIR /app

# 4. On copie le fichier des librairies et on installe les paquets Python
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# 5. On copie tout le reste du code
COPY . .

# 6. On expose le port de Streamlit
EXPOSE 8501

# 7. La commande pour lancer Streamlit
CMD ["streamlit", "run", "frontend.py", "--server.port=8501", "--server.address=0.0.0.0"]
