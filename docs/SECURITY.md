# AgentStock AI — Security Policy & Controls

## 1. Authentication & Password Security
- **Salted PBKDF2-HMAC-SHA256**: All user passwords are encrypted using PBKDF2-HMAC-SHA256 with 260,000 iterations and cryptographically unique per-user salts.
- **Password Strength Enforcement**: Mandatory minimum length of 8 characters, with required uppercase letters and numeric digits.
- **Secure OTP Verification**: 6-digit one-time verification passwords are never stored in plaintext. They are hashed using HMAC-SHA256 before persistence and checked with constant-time string comparison (`hmac.compare_digest`).

## 2. Multi-Tenant Isolation & IDOR Prevention
- **Strict Tenant Filtering**: All catalog products, suppliers, purchase orders, and documents are bound to `user_id` and `business_id`.
- **Ownership Verification**: Endpoints enforce `verify_tenant_ownership(requesting_user_id, resource_owner_id, is_admin)`.

## 3. Rate Limiting & Abuse Prevention
- **Sliding-Window Rate Limiter**: Thread-safe sliding time window rate limits logins, OTP requests, and API calls.
- **Lockout Safeguards**: Account lockouts after repeated failed attempts.

## 4. Payment Security (Razorpay)
- **HMAC-SHA256 Verification**: All payments and webhook events are verified using cryptographic SHA-256 HMACs before granting entitlements.
- **Zero Cardholder Data Stored**: AgentStock AI never stores full debit/credit card numbers or CVVs.

## 5. Privacy Person Detection
- **Biometric Minimization**: Video frames and camera captures are inspected with `PrivacyPersonFilter`. Any frame containing human beings or faces generates a privacy warning and disables vision counting to protect worker privacy.
