# 🚀 AGENTSTOCK AI — 100% Free Online Deployment Guide

Get your **AGENTSTOCK AI** web application live on the web in **under 3 minutes** so potential customers and competition judges around the world can access it natively!

---

## ⚡ Option 1: Streamlit Community Cloud (RECOMMENDED — 100% Free Forever)

**Why Streamlit Cloud?**
- 100% Free hosting directly from GitHub.
- Automatic SSL (`https://...streamlit.app`).
- Live updates every time you push code to GitHub.
- Secure environment secrets management for your `GEMINI_API_KEY`.

### Step-by-Step Instructions:

1. **Push your code to GitHub**:
   Open your terminal in the project directory (`/Users/vardaav/Desktop/agentstock_ai`) and run:
   ```bash
   git init
   git add .
   git commit -m "Deploy AGENTSTOCK AI to Streamlit Cloud"
   git branch -M main
   git remote add origin https://github.com/YOUR_GITHUB_USERNAME/agentstock-ai.git
   git push -u origin main
   ```
   *(Replace `YOUR_GITHUB_USERNAME` with your actual GitHub username)*

2. **Sign in to Streamlit Community Cloud**:
   - Go to [share.streamlit.io](https://share.streamlit.io/)
   - Click **"Continue with GitHub"** and sign in.

3. **Deploy the Web App**:
   - Click the **"New app"** button.
   - Fill in the details:
     - **Repository**: `YOUR_GITHUB_USERNAME/agentstock-ai`
     - **Branch**: `main`
     - **Main file path**: `app.py`
     - **App URL**: Choose a custom sub-domain like `agentstock.streamlit.app`

4. **Add your Gemini API Key Secret**:
   - Click **"Advanced settings..."** ➔ **Secrets**.
   - Paste the following:
     ```toml
     GEMINI_API_KEY = "your_actual_gemini_api_key_here"
     ```
   - Click **Save**.

5. **Click "Deploy!"** 🎉
   - In less than 60 seconds, your app will be live globally at `https://agentstock.streamlit.app`!

---

## 🤗 Option 2: Hugging Face Spaces (100% Free Docker / Streamlit Hosting)

1. Go to [huggingface.co/spaces](https://huggingface.co/spaces) and log in.
2. Click **"Create new Space"**.
3. Name your Space: `agentstock-ai`.
4. Select **Streamlit** as the Space SDK and set Visibility to **Public**.
5. Go to **Settings ➔ Repository Secrets** and add:
   - Name: `GEMINI_API_KEY`
   - Value: `your_actual_gemini_api_key_here`
6. Push your repository files to Hugging Face:
   ```bash
   git remote add hf https://huggingface.co/spaces/YOUR_HF_USERNAME/agentstock-ai
   git push hf main
   ```
7. Your app is live at `https://huggingface.co/spaces/YOUR_HF_USERNAME/agentstock-ai`!

---

## 🌟 Pro Tip for Competition Showcase
- Share your live link (`https://agentstock.streamlit.app`) directly on LinkedIn, Twitter/X, and competition portals.
- Highlight the **1-Click WhatsApp & Direct Phone PO Dispatch** during live demos to demonstrate real-world commercial automation value to judges!
