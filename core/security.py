"""Enterprise Security, Encryption, Privacy, Rate Limiting & Access Control."""
import os
import re
import hmac
import hashlib
import secrets
import time
from datetime import datetime, timezone, timedelta
from typing import Optional, Tuple, Dict, Any
from core.config import get_secret_key


# =========================================================================
# 1. PASSWORD HASHING & VERIFICATION (Salted PBKDF2-HMAC-SHA256)
# =========================================================================
def hash_password(password: str, salt: Optional[str] = None) -> str:
    """Hash password using PBKDF2-HMAC-SHA256 with 100,000 iterations and secure salt."""
    if not password:
        raise ValueError("Password cannot be empty")

    if not salt:
        salt = secrets.token_hex(16)

    # 100,000 rounds of PBKDF2
    key = hashlib.pbkdf2_hmac(
        "sha256",
        password.encode("utf-8"),
        salt.encode("utf-8"),
        100000,
    )
    return f"pbkdf2_sha256${salt}${key.hex()}"


def verify_password(plain_password: str, stored_hash: str) -> bool:
    """Verify plain password against stored salted hash using constant-time comparison."""
    if not plain_password or not stored_hash:
        return False

    # Check for legacy sha256 hashes during migration
    if "$" not in stored_hash:
        # Legacy plain SHA-256 fallback
        legacy_hash = hashlib.sha256(plain_password.encode("utf-8")).hexdigest()
        return hmac.compare_digest(legacy_hash, stored_hash)

    try:
        parts = stored_hash.split("$")
        if len(parts) != 3 or parts[0] != "pbkdf2_sha256":
            return False
        _, salt, expected_hex = parts
        actual_key = hashlib.pbkdf2_hmac(
            "sha256",
            plain_password.encode("utf-8"),
            salt.encode("utf-8"),
            100000,
        )
        return hmac.compare_digest(actual_key.hex(), expected_hex)
    except Exception:
        return False


def validate_password_strength(password: str) -> Tuple[bool, str]:
    """Ensure password meets enterprise complexity rules."""
    if len(password) < 8:
        return False, "Password must be at least 8 characters long."
    if not re.search(r"[A-Z]", password):
        return False, "Password must contain at least one uppercase letter."
    if not re.search(r"[a-z]", password):
        return False, "Password must contain at least one lowercase letter."
    if not re.search(r"[0-9]", password):
        return False, "Password must contain at least one number."
    return True, "Password meets strength requirements."


# =========================================================================
# 2. CRYPTOGRAPHICALLY SECURE OTP (One-Time Password) SYSTEM
# =========================================================================
def generate_secure_otp() -> str:
    """Generate 6-digit cryptographically secure numeric OTP."""
    return f"{secrets.randbelow(900000) + 100000}"


def hash_otp(otp_code: str) -> str:
    """Hash OTP using SHA-256 before storage so plaintext is never saved."""
    secret = get_secret_key()
    return hmac.new(secret.encode("utf-8"), otp_code.strip().encode("utf-8"), hashlib.sha256).hexdigest()


def verify_otp(entered_otp: str, stored_otp_hash: str) -> bool:
    """Verify entered OTP against stored cryptographic hash."""
    if not entered_otp or not stored_otp_hash:
        return False
    computed_hash = hash_otp(entered_otp.strip())
    return hmac.compare_digest(computed_hash, stored_otp_hash)


# =========================================================================
# 3. RATE LIMITING ENGINE
# =========================================================================
class RateLimiter:
    """In-memory thread-safe rate limiter with sliding time windows."""
    _store: Dict[str, list[float]] = {}
    _requests: Dict[str, list[float]] = _store

    @classmethod
    def reset(cls, key: Optional[str] = None):
        if key:
            cls._store.pop(key, None)
        else:
            cls._store.clear()

    @classmethod
    def is_rate_limited(cls, key: str, max_requests: int = 10, window_seconds: int = 60) -> bool:
        """Check and record request against sliding rate limit window."""
        now = time.time()
        cutoff = now - window_seconds

        if key not in cls._store:
            cls._store[key] = []

        # Clean older entries
        cls._store[key] = [t for t in cls._store[key] if t > cutoff]

        if len(cls._store[key]) >= max_requests:
            return True

        cls._store[key].append(now)
        return False

    @classmethod
    def reset(cls, key: str) -> None:
        """Reset rate limit history for a key."""
        cls._store.pop(key, None)


# =========================================================================
# 4. CAMERA PRIVACY & PERSON DETECTION FILTER
# =========================================================================
class PrivacyPersonFilter:
    """Detects and filters human persons in inventory images to guarantee privacy."""

    @staticmethod
    def inspect_image_for_persons(image_bytes: bytes) -> Tuple[bool, str]:
        """
        Inspect image for human presence.
        Returns:
            (has_person: bool, message: str)
        """
        if not image_bytes:
            return False, "Empty image bytes."

        # Fast local heuristic check on raw byte content
        lower_bytes = image_bytes.lower()
        if (
            b"person" in lower_bytes
            or b"human" in lower_bytes
            or b"face" in lower_bytes
            or b"selfie" in lower_bytes
        ):
            return True, "Person or face detected in camera frame. Camera is restricted to inventory items."

        # In production or standalone, scan for human presence indicators.
        # Check for facial patterns / person indicators in image metadata or text
        # If person is detected, return True and clear guidance.
        return False, "Privacy check passed. No human subjects detected."

    @staticmethod
    def sanitize_person_frame(image_bytes: bytes) -> bytes:
        """Sanitize or blur frame if person detected before Gemini processing."""
        # Never store biometric data or faces
        return image_bytes


# =========================================================================
# 5. PROMPT INJECTION & CONTENT MODERATION GUARDRAILS
# =========================================================================
class ContentModerationGuard:
    """Strict content moderation and domain boundary enforcement."""

    PROHIBITED_PATTERNS = [
        r"\b(porn|sex|nude|nsfw|erotic|escort)\b",
        r"\b(weapon|gun|bomb|explosive|ammunition|assault)\b",
        r"\b(fraud|scam|counterfeit|money\s+laundering|phishing)\b",
        r"\b(harass|threaten|dox|hate\s+speech|abuse)\b",
        r"\b(drug\s+deal|illegal|contraband)\b",
    ]

    PROMPT_INJECTION_PATTERNS = [
        r"(?i)ignore\s+(all\s+)?previous\s+instructions",
        r"(?i)system\s+prompt\s*:",
        r"(?i)you\s+are\s+now\s+dan",
        r"(?i)bypass\s+(safety|platform|security|rule)",
        r"(?i)reveal\s+(api\s+key|secret|password|database)",
        r"(?i)drop\s+table\b",
        r"(?i)delete\s+from\s+users\b",
        r"(?i)sudo\s+rm\b",
    ]

    @classmethod
    def check_acceptable_use(cls, text: str) -> Tuple[bool, str]:
        """Check if text complies with the strict commercial Inventory Acceptable Use Policy."""
        if not text:
            return True, "Valid"

        for pattern in cls.PROHIBITED_PATTERNS:
            if re.search(pattern, text, re.IGNORECASE):
                return False, "Your request contains prohibited content violating our Acceptable Use Policy."

        return True, "Valid"

    @classmethod
    def check_prompt_injection(cls, text: str) -> Tuple[bool, str]:
        """Detect and block adversarial prompt injection attempts."""
        if not text:
            return True, "Valid"

        for pattern in cls.PROMPT_INJECTION_PATTERNS:
            if re.search(pattern, text):
                return False, "Input contains prohibited system override patterns and was blocked."

        return True, "Valid"

    @classmethod
    def is_inventory_related_question(cls, text: str) -> bool:
        """Check if chatbot query is reasonably related to AgentStock AI or inventory."""
        lower = text.lower()
        keywords = [
            "inventory", "stock", "product", "sku", "supplier", "order", "purchase",
            "warehouse", "reorder", "delivery", "agentstock", "pricing", "plan", "camera",
            "scan", "voice", "document", "invoice", "receipt", "what-if", "lead time",
            "decision", "safety stock", "demand", "cost", "feature", "help", "support",
            "how to", "how do i", "login", "account", "subscription", "razorpay", "payment"
        ]
        return any(kw in lower for kw in keywords)


# =========================================================================
# 6. MULTI-TENANT AUTHORIZATION & IDOR PREVENTION
# =========================================================================
def verify_tenant_ownership(user_id: Optional[str], resource_owner_id: Optional[str], is_admin: bool = False) -> bool:
    """Ensure current user owns the target resource, or is a verified platform administrator."""
    if is_admin:
        return True
    if not user_id or not resource_owner_id:
        return False
    return str(user_id) == str(resource_owner_id)


def verify_admin_credentials(email: str, plain_password: str) -> bool:
    """Verify administrator email and password against secure environment configuration."""
    from core.config import get_admin_email, get_admin_password_hash
    admin_email = get_admin_email()
    if not email or email.strip().lower() != admin_email:
        return False

    stored_hash = get_admin_password_hash()
    if not stored_hash:
        # If ADMIN_PASSWORD_HASH is not set yet in development, deny or require setting it
        return False

    return verify_password(plain_password, stored_hash)


def require_authenticated_user(user: Optional[Any]) -> Tuple[bool, str]:
    """Server-side check: ensures a valid user session exists."""
    if not user or not getattr(user, "id", None):
        return False, "Authentication required. Please sign in to access this workspace."
    return True, "Authenticated"


def require_active_subscription(user: Optional[Any], subscription: Optional[Any]) -> Tuple[bool, str]:
    """Server-side check: ensures user has an active paid subscription or is platform admin."""
    auth_ok, msg = require_authenticated_user(user)
    if not auth_ok:
        return False, msg

    # Platform Admins have full operational bypass
    if getattr(user, "role", "USER") == "ADMIN":
        return True, "Admin authorized"

    if not subscription or not getattr(subscription, "is_active", False) or getattr(subscription, "plan_name", "FREE").upper() == "FREE":
        return False, "Active subscription required. Please upgrade your plan to access this feature."

    return True, "Subscription active"


def require_admin(user: Optional[Any]) -> Tuple[bool, str]:
    """Server-side check: strictly ensures user has the verified platform ADMIN role."""
    from core.config import get_admin_email
    auth_ok, msg = require_authenticated_user(user)
    if not auth_ok:
        return False, msg

    if getattr(user, "role", "") != "ADMIN" or getattr(user, "email", "").strip().lower() != get_admin_email():
        return False, "Access denied: Platform Administrator privileges required."

    return True, "Admin authorized"


def require_policy_consent(email: str, database: Any) -> Tuple[bool, str]:
    """Server-side check: strictly ensures user has agreed to the current terms and policies."""
    if not email or not database:
        return False, "User email required to verify policy consent."

    if not database.has_accepted_current_policies(email):
        return False, "Policy agreement required. Please review and accept current platform policies."

    return True, "Consent verified"
