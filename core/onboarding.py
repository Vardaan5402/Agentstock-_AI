"""Guided 12-Step Interactive Onboarding Tour Service."""
from typing import List, Dict, Any


class OnboardingTourService:
    """Provides plain-language guided walkthrough for new business owners."""

    TOUR_STEPS: List[Dict[str, Any]] = [
        {
            "step": 1,
            "title": "Welcome to AgentStock AI! 👋",
            "icon": "⚡",
            "description": "Your AI-powered inventory intelligence platform. We help you stay ahead of stockouts and manage suppliers effortlessly.",
            "action_text": "Let's Get Started ➔",
        },
        {
            "step": 2,
            "title": "Set Up Your Business Profile 🏢",
            "icon": "🏢",
            "description": "Tell us your shop name, currency, location, and monthly budget so we can tailor inventory alerts to your store.",
            "action_text": "Next: Adding Products ➔",
        },
        {
            "step": 3,
            "title": "Add Your Product Inventory 📦",
            "icon": "📦",
            "description": "Add the products you sell, along with your safety stock threshold and daily sales demand.",
            "action_text": "Next: Camera Scanner ➔",
        },
        {
            "step": 4,
            "title": "Scan Stock with AI Camera 📷",
            "icon": "📷",
            "description": "Point your phone or webcam at cartons and shelves to automatically count visible inventory with privacy protection.",
            "action_text": "Next: Voice Assistant ➔",
        },
        {
            "step": 5,
            "title": "Speak Stock Updates with Voice 🎙️",
            "icon": "🎙️",
            "description": "Speak in your preferred language (English, Hindi, Spanish, etc.) like 'Add 20 packets of rice' to update quantities hands-free.",
            "action_text": "Next: Suppliers ➔",
        },
        {
            "step": 6,
            "title": "Connect Your Suppliers 🚚",
            "icon": "🚚",
            "description": "Save your suppliers' phone numbers, delivery contact info, unit prices, and lead times in one organized directory.",
            "action_text": "Next: AI Decision Engine ➔",
        },
        {
            "step": 7,
            "title": "Fact-Bounded AI Recommendations ✨",
            "icon": "✨",
            "description": "When stock runs low, our deterministic engine calculates exact reorder needs and Gemini provides clear supplier recommendations.",
            "action_text": "Next: What-If Analysis ➔",
        },
        {
            "step": 8,
            "title": "Simulate What-If Scenarios 🔮",
            "icon": "🔮",
            "description": "Test price changes, demand surges, or supplier delays to see the financial impact before placing orders.",
            "action_text": "Next: Supplier Dispatch ➔",
        },
        {
            "step": 9,
            "title": "1-Click WhatsApp & Phone PO Dispatch 📞",
            "icon": "📞",
            "description": "Send prefilled purchase orders directly to suppliers via WhatsApp, Email, or direct phone calls in seconds.",
            "action_text": "Next: History & Audit ➔",
        },
        {
            "step": 10,
            "title": "Complete Audit Trail & Reports 🛡️",
            "icon": "🛡️",
            "description": "Every stock update, approval, and order dispatch is recorded in an immutable audit ledger for complete peace of mind.",
            "action_text": "Next: Privacy & Security ➔",
        },
        {
            "step": 11,
            "title": "Bank-Grade Privacy & Security 🔒",
            "icon": "🔒",
            "description": "Your business data is strictly isolated. We never sell your data or use human faces in camera scans.",
            "action_text": "Next: Support ➔",
        },
        {
            "step": 12,
            "title": "24/7 AI Support & Help 🤖",
            "icon": "🤖",
            "description": "Whenever you have questions about inventory or features, ask our AI assistant anytime.",
            "action_text": "Finish Tour & Go to Dashboard ➔",
        },
    ]

    @classmethod
    def get_step(cls, step_number: int) -> Dict[str, Any]:
        """Retrieve step metadata."""
        idx = max(0, min(step_number - 1, len(cls.TOUR_STEPS) - 1))
        return cls.TOUR_STEPS[idx]

    @classmethod
    def total_steps(cls) -> int:
        return len(cls.TOUR_STEPS)
