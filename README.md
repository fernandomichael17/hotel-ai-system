# Hotel AI Chatbot System

Sistem chatbot AI untuk perhotelan yang terintegrasi dengan WhatsApp dan sistem manajemen hotel (HMS).

## Cara Menjalankan

1. Jalankan infrastructure dependencies dengan Docker Compose:
   ```bash
   docker compose up -d
   ```
2. Install Python dependencies:
   ```bash
   pip install -r requirements.txt
   ```
3. Jalankan server backend:
   ```bash
   python -m uvicorn backend.main:app --reload
   ```
