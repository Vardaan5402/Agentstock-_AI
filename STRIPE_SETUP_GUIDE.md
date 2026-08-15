# 💳 AgentStock AI — Production Stripe Billing & Subscriptions Guide

This document provides complete instructions for configuring and testing Stripe Subscriptions, Checkout, Customer Portal, and Webhooks for **AgentStock AI**.

---

## 1. Authoritative Pricing Plans & Configuration

AgentStock AI features 3 subscription tiers with authoritative pricing:

| Tier | Monthly Billing | Annual Billing (20% OFF) | Stripe Price ID (Monthly) | Stripe Price ID (Yearly) |
| :--- | :---: | :---: | :--- | :--- |
| **STARTER** | **$19 / mo** | **$15 / mo** | `STRIPE_PRICE_STARTER_MONTHLY` | `STRIPE_PRICE_STARTER_YEARLY` |
| **PROFESSIONAL** | **$49 / mo** | **$39 / mo** | `STRIPE_PRICE_PRO_MONTHLY` | `STRIPE_PRICE_PRO_YEARLY` |
| **ENTERPRISE** | **$149 / mo** | **$119 / mo** | `STRIPE_PRICE_ENTERPRISE_MONTHLY` | `STRIPE_PRICE_ENTERPRISE_YEARLY` |

---

## 2. Environment Variables & Streamlit Secrets

Configure your secrets in `.streamlit/secrets.toml` or environment variables:

```toml
# Google Gemini API Key
GEMINI_API_KEY = "AIzaSy..."

# Stripe Configuration (Test Mode: sk_test_... / Live Mode: sk_live_...)
STRIPE_SECRET_KEY = "sk_test_51..."
STRIPE_PUBLISHABLE_KEY = "pk_test_51..."
STRIPE_WEBHOOK_SECRET = "whsec_..."

# Application Base URL
APP_BASE_URL = "http://localhost:8501"

# Stripe Price IDs (Created in your Stripe Dashboard)
STRIPE_PRICE_STARTER_MONTHLY = "price_starter_monthly_usd_19"
STRIPE_PRICE_STARTER_YEARLY = "price_starter_yearly_usd_15"
STRIPE_PRICE_PRO_MONTHLY = "price_pro_monthly_usd_49"
STRIPE_PRICE_PRO_YEARLY = "price_pro_yearly_usd_39"
STRIPE_PRICE_ENTERPRISE_MONTHLY = "price_enterprise_monthly_usd_149"
STRIPE_PRICE_ENTERPRISE_YEARLY = "price_enterprise_yearly_usd_119"
```

---

## 3. Stripe Dashboard Setup

### A. Create Products & Recurring Prices
1. Log in to [dashboard.stripe.com/test/products](https://dashboard.stripe.com/test/products).
2. Create **Starter** (Recurring monthly ₹499 INR and yearly ₹4,788 INR).
3. Create **Professional** (Recurring monthly ₹1,999 INR and yearly ₹19,188 INR).
4. Create **Enterprise** (Recurring monthly ₹4,999 INR and yearly ₹47,988 INR).
5. Copy each `price_...` ID into your `.streamlit/secrets.toml`.

### B. Enable Stripe Customer Portal
1. Navigate to **Settings > Billing > Customer portal** ([dashboard.stripe.com/test/settings/billing/portal](https://dashboard.stripe.com/test/settings/billing/portal)).
2. Enable:
   - Allow customers to update payment methods.
   - Allow customers to cancel subscriptions.
   - Allow customers to switch plans.
3. Click **Save Changes**.

---

## 4. Local Webhook Testing (with Stripe CLI)

1. Download and install the [Stripe CLI](https://docs.stripe.com/stripe-cli).
2. Forward webhooks to your local Streamlit instance or webhook worker:
   ```bash
   stripe listen --forward-to localhost:8501
   ```
3. Copy the webhook signing secret (`whsec_...`) printed in your terminal and set it as `STRIPE_WEBHOOK_SECRET`.
4. Trigger test events:
   ```bash
   stripe trigger checkout.session.completed
   stripe trigger customer.subscription.updated
   stripe trigger invoice.paid
   ```

---

## 5. Deployment on Streamlit Community Cloud

1. Push your latest code to GitHub:
   ```bash
   git add .
   git commit -m "Add production Stripe subscription system"
   git push origin main
   ```
2. In your Streamlit Cloud app settings under **Secrets**, paste your `GEMINI_API_KEY`, `STRIPE_SECRET_KEY`, `STRIPE_PUBLISHABLE_KEY`, `STRIPE_WEBHOOK_SECRET`, and Price IDs.
3. In your Stripe Dashboard under **Developers > Webhooks**, add your live webhook endpoint: `https://<your-app>.streamlit.app/api/webhook`.
4. Subscribe to the following events:
   - `checkout.session.completed`
   - `customer.subscription.created`
   - `customer.subscription.updated`
   - `customer.subscription.deleted`
   - `invoice.paid`
   - `invoice.payment_failed`

---

## 6. Verification & Automated Tests

Run the full automated test suite covering checkout sessions, webhook signature handling, and entitlement checks:

```bash
python3 -m unittest discover -s . -p "test_*.py"
```

Output:
```
Ran 60 tests in 0.100s - OK
```
