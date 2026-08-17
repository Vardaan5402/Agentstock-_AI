# AgentStock AI — Production Deployment Guide

## 1. Prerequisites
- Python 3.10+ (Python 3.12+ recommended)
- SQLite 3.35+ or PostgreSQL 14+
- Valid Google Gemini API Key
- Live Razorpay API Keys (Key ID & Secret)

## 2. Environment Setup
```bash
# Clone the repository
git clone https://github.com/Vardaan5402/Agentstock-_AI.git
cd Agentstock-_AI

# Create virtual environment
python3 -m venv .venv
source .venv/bin/activate

# Install dependencies
pip install -r requirements.txt

# Configure environment variables
cp .env.example .env
# Edit .env with your production credentials
```

## 3. Running the Test Suite
```bash
python -m unittest discover -s . -p "test_*.py"
```

## 4. Launching the Production Streamlit App
```bash
streamlit run app.py --server.port 8501 --server.headless true
```

## 5. Database Initialization
Tables, indexes, and migrations are automatically applied on startup by `Database("agentstock.db").initialize()`.
For PostgreSQL deployment, set `DATABASE_URL=postgresql://user:password@host:5432/dbname`.
