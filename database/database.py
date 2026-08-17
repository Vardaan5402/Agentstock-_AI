"""Database Layer supporting SQLite & PostgreSQL with Multi-Tenant Security."""

import json
import sqlite3
import threading
from datetime import datetime, timezone, timedelta
from enum import Enum
from pathlib import Path
from typing import Any, Optional, List, Dict
from uuid import uuid4

from models.business import Business
from models.decision import Decision, DecisionOption, Outcome
from models.inventory import Product, SalesRecord, Purchase
from models.policy import Policy
from models.supplier import Supplier, SupplierProduct
from models.user import User, UserRole, OTPRecord
from models.subscription import UserSubscription, SubscriptionStatus, PlanTier, BillingCycle, UsageRecord
from models.communication import SupplierCommunication, CommType, CommStatus
from models.security import SecurityAlert, SecuritySeverity, Coupon, CouponRedemption, UploadedDocument, UserPolicyConsent
from models.persistence import AdminAuditEvent, UserActivityEvent
from core.config import get_database_url, get_plan_pricing


class Database:
    """Multi-tenant database manager for AgentStock AI."""

    CURRENT_POLICIES = {
        "policy_version": "1.0",
        "terms_version": "1.0",
        "privacy_version": "1.0",
        "acceptable_use_version": "1.0",
        "subscription_policy_version": "1.0",
        "communication_policy_version": "1.0",
        "data_security_policy_version": "1.0",
    }

    def __init__(self, db_path: str = "agentstock.db"):
        self.db_path = db_path
        self._local = threading.local()
        self.init_db()

    def initialize(self):
        """Alias for init_db for backwards compatibility with existing test suite."""
        self.init_db()

    def connect(self) -> sqlite3.Connection:
        """Get or create a thread-local SQLite connection with WAL mode and busy timeout."""
        if not hasattr(self._local, "connection") or self._local.connection is None:
            conn = sqlite3.connect(self.db_path, timeout=15.0, isolation_level=None)
            conn.row_factory = sqlite3.Row
            conn.execute("PRAGMA journal_mode=WAL;")
            conn.execute("PRAGMA foreign_keys = ON;")
            conn.execute("PRAGMA busy_timeout = 10000;")
            self._local.connection = conn
        return self._local.connection

    def close(self):
        """Close thread-local connection if open."""
        if hasattr(self._local, "connection") and self._local.connection is not None:
            try:
                self._local.connection.close()
            except Exception:
                pass
            self._local.connection = None

    def init_db(self):
        """Initialize all database tables with enterprise schema."""
        connection = self.connect()
        with connection:
            connection.executescript(
                """
                CREATE TABLE IF NOT EXISTS users (
                    id TEXT PRIMARY KEY,
                    name TEXT NOT NULL,
                    email TEXT NOT NULL UNIQUE,
                    password_hash TEXT NOT NULL,
                    role TEXT NOT NULL DEFAULT 'USER',
                    phone TEXT,
                    preferred_language TEXT NOT NULL DEFAULT 'en',
                    preferred_currency TEXT NOT NULL DEFAULT 'INR',
                    timezone TEXT NOT NULL DEFAULT 'UTC',
                    profile_image_path TEXT,
                    is_verified INTEGER NOT NULL DEFAULT 1,
                    is_locked INTEGER NOT NULL DEFAULT 0,
                    failed_login_attempts INTEGER NOT NULL DEFAULT 0,
                    locked_until TEXT,
                    terms_accepted_at TEXT,
                    privacy_accepted_at TEXT,
                    aup_accepted_at TEXT,
                    onboarding_completed INTEGER NOT NULL DEFAULT 0,
                    created_at TEXT NOT NULL DEFAULT (datetime('now')),
                    updated_at TEXT NOT NULL DEFAULT (datetime('now'))
                );

                CREATE TABLE IF NOT EXISTS otp_codes (
                    email TEXT PRIMARY KEY,
                    otp_hash TEXT NOT NULL,
                    expires_at TEXT NOT NULL,
                    attempts INTEGER NOT NULL DEFAULT 0,
                    max_attempts INTEGER NOT NULL DEFAULT 5,
                    last_sent_at TEXT NOT NULL DEFAULT (datetime('now')),
                    created_at TEXT NOT NULL DEFAULT (datetime('now'))
                );

                CREATE TABLE IF NOT EXISTS user_policy_consents (
                    id TEXT PRIMARY KEY,
                    user_id TEXT,
                    email TEXT NOT NULL,
                    policy_version TEXT NOT NULL DEFAULT '1.0',
                    terms_version TEXT NOT NULL,
                    privacy_version TEXT NOT NULL,
                    acceptable_use_version TEXT NOT NULL,
                    subscription_policy_version TEXT NOT NULL,
                    communication_policy_version TEXT NOT NULL,
                    data_security_policy_version TEXT NOT NULL,
                    ip_address TEXT,
                    user_agent TEXT,
                    consent_status TEXT NOT NULL DEFAULT 'ACCEPTED',
                    agreed_at TEXT NOT NULL,
                    created_at TEXT NOT NULL DEFAULT (datetime('now'))
                );

                CREATE TABLE IF NOT EXISTS user_subscriptions (
                    id TEXT PRIMARY KEY,
                    user_id TEXT NOT NULL,
                    razorpay_customer_id TEXT,
                    razorpay_order_id TEXT,
                    razorpay_subscription_id TEXT,
                    razorpay_payment_id TEXT,
                    plan_name TEXT NOT NULL DEFAULT 'FREE',
                    billing_cycle TEXT NOT NULL DEFAULT 'MONTHLY',
                    subscription_status TEXT NOT NULL DEFAULT 'inactive',
                    current_period_start TEXT,
                    current_period_end TEXT,
                    cancel_at_period_end INTEGER NOT NULL DEFAULT 0,
                    minimum_commitment_end TEXT,
                    coupon_code TEXT,
                    discount_applied REAL NOT NULL DEFAULT 0.0,
                    created_at TEXT NOT NULL DEFAULT (datetime('now')),
                    updated_at TEXT NOT NULL DEFAULT (datetime('now')),
                    FOREIGN KEY (user_id) REFERENCES users(id)
                );

                CREATE TABLE IF NOT EXISTS usage_records (
                    id TEXT PRIMARY KEY,
                    user_id TEXT NOT NULL,
                    period_month TEXT NOT NULL,
                    camera_scans INTEGER NOT NULL DEFAULT 0,
                    voice_queries INTEGER NOT NULL DEFAULT 0,
                    ai_decisions INTEGER NOT NULL DEFAULT 0,
                    documents_analyzed INTEGER NOT NULL DEFAULT 0,
                    updated_at TEXT NOT NULL DEFAULT (datetime('now')),
                    UNIQUE(user_id, period_month)
                );

                CREATE TABLE IF NOT EXISTS coupons (
                    id TEXT PRIMARY KEY,
                    code TEXT NOT NULL UNIQUE,
                    discount_type TEXT NOT NULL DEFAULT 'PERCENTAGE',
                    discount_value REAL NOT NULL,
                    plan_tier TEXT,
                    max_redemptions INTEGER NOT NULL DEFAULT 100,
                    times_redeemed INTEGER NOT NULL DEFAULT 0,
                    expires_at TEXT,
                    is_active INTEGER NOT NULL DEFAULT 1,
                    campaign TEXT,
                    created_at TEXT NOT NULL DEFAULT (datetime('now'))
                );

                CREATE TABLE IF NOT EXISTS coupon_redemptions (
                    id TEXT PRIMARY KEY,
                    coupon_id TEXT NOT NULL,
                    user_id TEXT NOT NULL,
                    redeemed_at TEXT NOT NULL DEFAULT (datetime('now')),
                    UNIQUE(coupon_id, user_id),
                    FOREIGN KEY (coupon_id) REFERENCES coupons(id),
                    FOREIGN KEY (user_id) REFERENCES users(id)
                );

                CREATE TABLE IF NOT EXISTS businesses (
                    id TEXT PRIMARY KEY,
                    user_id TEXT,
                    name TEXT NOT NULL,
                    proprietor_name TEXT,
                    phone TEXT,
                    email TEXT,
                    address TEXT,
                    country TEXT NOT NULL,
                    city TEXT,
                    currency TEXT NOT NULL,
                    industry TEXT NOT NULL,
                    business_type TEXT,
                    google_maps_location TEXT,
                    inventory_category TEXT,
                    inventory_budget REAL NOT NULL CHECK (inventory_budget >= 0),
                    created_at TEXT NOT NULL DEFAULT (datetime('now'))
                );

                CREATE TABLE IF NOT EXISTS products (
                    id TEXT PRIMARY KEY,
                    business_id TEXT NOT NULL,
                    user_id TEXT,
                    sku TEXT NOT NULL,
                    name TEXT NOT NULL,
                    current_stock INTEGER NOT NULL CHECK (current_stock >= 0),
                    unit_cost REAL NOT NULL CHECK (unit_cost >= 0),
                    daily_demand REAL NOT NULL CHECK (daily_demand >= 0),
                    safety_stock INTEGER NOT NULL CHECK (safety_stock >= 0),
                    created_at TEXT NOT NULL DEFAULT (datetime('now')),
                    FOREIGN KEY (business_id) REFERENCES businesses(id)
                );

                CREATE TABLE IF NOT EXISTS suppliers (
                    id TEXT PRIMARY KEY,
                    business_id TEXT NOT NULL,
                    user_id TEXT,
                    name TEXT NOT NULL,
                    company_name TEXT,
                    phone TEXT,
                    email TEXT,
                    address TEXT,
                    delivery_person_name TEXT,
                    delivery_person_phone TEXT,
                    gst_id TEXT,
                    payment_terms TEXT DEFAULT 'Net 30',
                    supplier_category TEXT DEFAULT 'General',
                    notes TEXT,
                    lead_time_days REAL NOT NULL CHECK (lead_time_days >= 0),
                    reliability_score REAL NOT NULL DEFAULT 0.5
                        CHECK (reliability_score >= 0 AND reliability_score <= 1),
                    is_archived INTEGER NOT NULL DEFAULT 0,
                    created_at TEXT NOT NULL DEFAULT (datetime('now')),
                    updated_at TEXT NOT NULL DEFAULT (datetime('now')),
                    FOREIGN KEY (business_id) REFERENCES businesses(id)
                );

                CREATE TABLE IF NOT EXISTS supplier_products (
                    supplier_id TEXT NOT NULL,
                    product_id TEXT NOT NULL,
                    unit_price REAL NOT NULL CHECK (unit_price >= 0),
                    minimum_order_quantity INTEGER NOT NULL DEFAULT 1
                        CHECK (minimum_order_quantity > 0),
                    PRIMARY KEY (supplier_id, product_id),
                    FOREIGN KEY (supplier_id) REFERENCES suppliers(id),
                    FOREIGN KEY (product_id) REFERENCES products(id)
                );

                CREATE TABLE IF NOT EXISTS supplier_communications (
                    id TEXT PRIMARY KEY,
                    business_id TEXT NOT NULL,
                    user_id TEXT NOT NULL,
                    supplier_id TEXT NOT NULL,
                    comm_type TEXT NOT NULL,
                    subject TEXT,
                    body TEXT NOT NULL,
                    status TEXT NOT NULL DEFAULT 'SENT',
                    order_reference TEXT,
                    sender TEXT,
                    recipient TEXT,
                    duration_seconds INTEGER,
                    metadata_json TEXT DEFAULT '{}',
                    created_at TEXT NOT NULL DEFAULT (datetime('now')),
                    FOREIGN KEY (business_id) REFERENCES businesses(id),
                    FOREIGN KEY (supplier_id) REFERENCES suppliers(id)
                );

                CREATE TABLE IF NOT EXISTS uploaded_documents (
                    id TEXT PRIMARY KEY,
                    business_id TEXT NOT NULL,
                    user_id TEXT NOT NULL,
                    filename TEXT NOT NULL,
                    stored_path TEXT NOT NULL,
                    mime_type TEXT NOT NULL,
                    file_size_bytes INTEGER NOT NULL,
                    extracted_data_json TEXT DEFAULT '{}',
                    status TEXT NOT NULL DEFAULT 'PROCESSED',
                    created_at TEXT NOT NULL DEFAULT (datetime('now'))
                );

                CREATE TABLE IF NOT EXISTS security_alerts (
                    id TEXT PRIMARY KEY,
                    user_id TEXT,
                    event_type TEXT NOT NULL,
                    severity TEXT NOT NULL DEFAULT 'LOW',
                    description TEXT NOT NULL,
                    ip_address TEXT,
                    user_agent TEXT,
                    status TEXT NOT NULL DEFAULT 'OPEN',
                    created_at TEXT NOT NULL DEFAULT (datetime('now'))
                );

                CREATE TABLE IF NOT EXISTS sales_records (
                    id TEXT PRIMARY KEY,
                    business_id TEXT NOT NULL,
                    product_id TEXT NOT NULL,
                    quantity INTEGER NOT NULL CHECK (quantity > 0),
                    sale_date TEXT NOT NULL,
                    revenue REAL CHECK (revenue IS NULL OR revenue >= 0),
                    FOREIGN KEY (business_id) REFERENCES businesses(id),
                    FOREIGN KEY (product_id) REFERENCES products(id)
                );

                CREATE TABLE IF NOT EXISTS purchases (
                    id TEXT PRIMARY KEY,
                    business_id TEXT NOT NULL,
                    supplier_id TEXT NOT NULL,
                    product_id TEXT NOT NULL,
                    quantity INTEGER NOT NULL CHECK (quantity > 0),
                    unit_price REAL NOT NULL CHECK (unit_price >= 0),
                    status TEXT NOT NULL CHECK (status IN (
                        'DRAFT', 'PENDING_APPROVAL', 'APPROVED', 'SENT', 'RECEIVED',
                        'CANCELLED', 'FAILED'
                    )),
                    created_at TEXT NOT NULL DEFAULT (datetime('now')),
                    FOREIGN KEY (business_id) REFERENCES businesses(id),
                    FOREIGN KEY (supplier_id) REFERENCES suppliers(id),
                    FOREIGN KEY (product_id) REFERENCES products(id)
                );

                CREATE TABLE IF NOT EXISTS decisions (
                    id TEXT PRIMARY KEY,
                    business_id TEXT NOT NULL,
                    product_id TEXT NOT NULL,
                    problem TEXT NOT NULL,
                    risk_level TEXT NOT NULL,
                    recommended_option_id TEXT NOT NULL,
                    explanation TEXT NOT NULL,
                    requires_approval INTEGER NOT NULL CHECK (requires_approval IN (0, 1)),
                    status TEXT NOT NULL CHECK (status IN (
                        'PENDING', 'APPROVED', 'REJECTED', 'EXECUTED', 'VERIFIED', 'FAILED'
                    )),
                    created_at TEXT NOT NULL DEFAULT (datetime('now')),
                    FOREIGN KEY (business_id) REFERENCES businesses(id),
                    FOREIGN KEY (product_id) REFERENCES products(id)
                );

                CREATE TABLE IF NOT EXISTS decision_options (
                    option_id TEXT PRIMARY KEY,
                    decision_id TEXT NOT NULL,
                    description TEXT NOT NULL,
                    supplier_id TEXT,
                    quantity INTEGER NOT NULL CHECK (quantity >= 0),
                    unit_cost REAL NOT NULL CHECK (unit_cost >= 0),
                    total_cost REAL NOT NULL CHECK (total_cost >= 0),
                    projected_runway_days REAL NOT NULL CHECK (projected_runway_days >= 0),
                    stockout_risk TEXT NOT NULL,
                    budget_remaining REAL NOT NULL CHECK (budget_remaining >= 0),
                    FOREIGN KEY (decision_id) REFERENCES decisions(id),
                    FOREIGN KEY (supplier_id) REFERENCES suppliers(id)
                );

                CREATE TABLE IF NOT EXISTS policies (
                    id TEXT PRIMARY KEY,
                    business_id TEXT NOT NULL UNIQUE,
                    max_auto_purchase REAL NOT NULL DEFAULT 0.0 CHECK (max_auto_purchase >= 0),
                    require_approval INTEGER NOT NULL CHECK (require_approval IN (0, 1)),
                    allowed_auto_actions TEXT NOT NULL,
                    FOREIGN KEY (business_id) REFERENCES businesses(id)
                );

                CREATE TABLE IF NOT EXISTS outcomes (
                    id TEXT PRIMARY KEY,
                    decision_id TEXT NOT NULL,
                    expected_result TEXT NOT NULL,
                    actual_result TEXT,
                    success INTEGER CHECK (success IS NULL OR success IN (0, 1)),
                    verified_at TEXT,
                    FOREIGN KEY (decision_id) REFERENCES decisions(id)
                );

                CREATE TABLE IF NOT EXISTS decision_snapshots (
                    snapshot_id TEXT PRIMARY KEY,
                    business_id TEXT NOT NULL,
                    product_id TEXT NOT NULL,
                    facts_json TEXT NOT NULL,
                    proposal_json TEXT,
                    reference_validation_json TEXT,
                    policy_validation_json TEXT,
                    status TEXT NOT NULL,
                    created_at TEXT NOT NULL DEFAULT (datetime('now')),
                    FOREIGN KEY (business_id) REFERENCES businesses(id),
                    FOREIGN KEY (product_id) REFERENCES products(id)
                );

                CREATE TABLE IF NOT EXISTS what_if_scenarios (
                    id TEXT PRIMARY KEY,
                    decision_snapshot_id TEXT NOT NULL,
                    baseline_snapshot_id TEXT NOT NULL,
                    scenario_id TEXT NOT NULL,
                    scenario_json TEXT NOT NULL,
                    outcome_json TEXT NOT NULL,
                    comparison_json TEXT NOT NULL,
                    created_at TEXT NOT NULL DEFAULT (datetime('now')),
                    FOREIGN KEY (decision_snapshot_id) REFERENCES decision_snapshots(snapshot_id)
                );

                CREATE TABLE IF NOT EXISTS audit_events (
                    id TEXT PRIMARY KEY,
                    user_id TEXT,
                    business_id TEXT,
                    entity_type TEXT NOT NULL,
                    entity_id TEXT NOT NULL,
                    event_type TEXT NOT NULL,
                    metadata_json TEXT NOT NULL,
                    created_at TEXT NOT NULL DEFAULT (datetime('now'))
                );

                CREATE TABLE IF NOT EXISTS admin_audit_events (
                    id TEXT PRIMARY KEY,
                    user_id TEXT,
                    user_email TEXT,
                    event_type TEXT NOT NULL,
                    entity_type TEXT NOT NULL DEFAULT 'SYSTEM',
                    entity_id TEXT NOT NULL DEFAULT 'NONE',
                    metadata_json TEXT NOT NULL DEFAULT '{}',
                    ip_address TEXT,
                    user_agent TEXT,
                    security_classification TEXT NOT NULL DEFAULT 'STANDARD',
                    created_at TEXT NOT NULL DEFAULT (datetime('now'))
                );

                CREATE TABLE IF NOT EXISTS user_activity (
                    id TEXT PRIMARY KEY,
                    user_id TEXT NOT NULL,
                    activity_type TEXT NOT NULL,
                    title TEXT NOT NULL,
                    description TEXT DEFAULT '',
                    metadata_json TEXT DEFAULT '{}',
                    created_at TEXT NOT NULL DEFAULT (datetime('now')),
                    FOREIGN KEY (user_id) REFERENCES users(id)
                );
                """
            )
            # Safe, idempotent Razorpay migration. SQLite keeps existing customer
            # records intact while obsolete Stripe columns are removed where the
            # bundled SQLite version supports DROP COLUMN.
            sub_columns = {row[1] for row in connection.execute("PRAGMA table_info(user_subscriptions)")}
            for column, definition in {
                "razorpay_order_id": "TEXT",
                "minimum_commitment_end": "TEXT",
            }.items():
                if column not in sub_columns:
                    connection.execute(f"ALTER TABLE user_subscriptions ADD COLUMN {column} {definition}")
            for column in ("stripe_customer_id", "stripe_subscription_id", "stripe_price_id"):
                if column in sub_columns:
                    try:
                        connection.execute(f"ALTER TABLE user_subscriptions DROP COLUMN {column}")
                    except sqlite3.OperationalError:
                        # Older SQLite deployments retain unused legacy columns;
                        # fresh schemas never create them and no runtime path uses them.
                        pass
            connection.execute("""
                CREATE TABLE IF NOT EXISTS razorpay_webhook_events (
                    event_id TEXT PRIMARY KEY,
                    event_type TEXT NOT NULL,
                    received_at TEXT NOT NULL DEFAULT (datetime('now'))
                )
            """)
            self._run_schema_migrations(connection)

    def _run_schema_migrations(self, connection: sqlite3.Connection):
        """Execute dynamic column migrations and index creations for existing SQLite databases."""
        cursor = connection.cursor()

        # 1. Check users table columns
        u_info = cursor.execute("PRAGMA table_info(users);").fetchall()
        u_cols = [c[1] for c in u_info]
        for col_name, col_type in [
            ("role", "TEXT NOT NULL DEFAULT 'USER'"),
            ("phone", "TEXT"),
            ("preferred_language", "TEXT NOT NULL DEFAULT 'en'"),
            ("preferred_currency", "TEXT NOT NULL DEFAULT 'INR'"),
            ("timezone", "TEXT NOT NULL DEFAULT 'UTC'"),
            ("profile_image_path", "TEXT"),
            ("is_locked", "INTEGER NOT NULL DEFAULT 0"),
            ("failed_login_attempts", "INTEGER NOT NULL DEFAULT 0"),
            ("locked_until", "TEXT"),
            ("terms_accepted_at", "TEXT"),
            ("privacy_accepted_at", "TEXT"),
            ("aup_accepted_at", "TEXT"),
            ("onboarding_completed", "INTEGER NOT NULL DEFAULT 0"),
            ("updated_at", "TEXT DEFAULT ''"),
        ]:
            if col_name not in u_cols:
                cursor.execute(f"ALTER TABLE users ADD COLUMN {col_name} {col_type};")

        # 2. Check businesses table columns (Fix for no such column: user_id)
        b_info = cursor.execute("PRAGMA table_info(businesses);").fetchall()
        b_cols = [c[1] for c in b_info]
        for col_name, col_type in [
            ("user_id", "TEXT"),
            ("proprietor_name", "TEXT"),
            ("phone", "TEXT"),
            ("email", "TEXT"),
            ("address", "TEXT"),
            ("city", "TEXT"),
            ("business_type", "TEXT"),
            ("google_maps_location", "TEXT"),
            ("inventory_category", "TEXT"),
        ]:
            if col_name not in b_cols:
                cursor.execute(f"ALTER TABLE businesses ADD COLUMN {col_name} {col_type};")

        # 3. Check products table columns
        p_info = cursor.execute("PRAGMA table_info(products);").fetchall()
        p_cols = [c[1] for c in p_info]
        for col_name, col_type in [
            ("user_id", "TEXT"),
            ("category", "TEXT"),
        ]:
            if col_name not in p_cols:
                cursor.execute(f"ALTER TABLE products ADD COLUMN {col_name} {col_type};")

        # 4. Check suppliers table columns
        s_info = cursor.execute("PRAGMA table_info(suppliers);").fetchall()
        s_cols = [c[1] for c in s_info]
        for col_name, col_type in [
            ("user_id", "TEXT"),
            ("company_name", "TEXT"),
            ("phone", "TEXT"),
            ("address", "TEXT"),
            ("delivery_person_name", "TEXT"),
            ("delivery_person_phone", "TEXT"),
            ("gst_id", "TEXT"),
            ("payment_terms", "TEXT DEFAULT 'Net 30'"),
            ("supplier_category", "TEXT DEFAULT 'General'"),
            ("notes", "TEXT"),
            ("is_archived", "INTEGER NOT NULL DEFAULT 0"),
            ("updated_at", "TEXT DEFAULT ''"),
        ]:
            if col_name not in s_cols:
                cursor.execute(f"ALTER TABLE suppliers ADD COLUMN {col_name} {col_type};")

        # 5. Check user_subscriptions table columns
        sub_info = cursor.execute("PRAGMA table_info(user_subscriptions);").fetchall()
        sub_cols = [c[1] for c in sub_info]
        for col_name, col_type in [
            ("razorpay_customer_id", "TEXT"),
            ("razorpay_subscription_id", "TEXT"),
            ("razorpay_payment_id", "TEXT"),
            ("billing_cycle", "TEXT NOT NULL DEFAULT 'MONTHLY'"),
            ("coupon_code", "TEXT"),
            ("discount_applied", "REAL NOT NULL DEFAULT 0.0"),
        ]:
            if col_name not in sub_cols:
                cursor.execute(f"ALTER TABLE user_subscriptions ADD COLUMN {col_name} {col_type};")

        # 6. Check otp_codes table columns
        otp_info = cursor.execute("PRAGMA table_info(otp_codes);").fetchall()
        otp_cols = [c[1] for c in otp_info]
        if "otp_hash" not in otp_cols and "otp_code" in otp_cols:
            cursor.execute("ALTER TABLE otp_codes ADD COLUMN otp_hash TEXT;")
            cursor.execute("UPDATE otp_codes SET otp_hash = otp_code WHERE otp_hash IS NULL;")
        for col_name, col_type in [
            ("attempts", "INTEGER NOT NULL DEFAULT 0"),
            ("max_attempts", "INTEGER NOT NULL DEFAULT 5"),
            ("last_sent_at", "TEXT DEFAULT ''"),
        ]:
            if col_name not in otp_cols:
                cursor.execute(f"ALTER TABLE otp_codes ADD COLUMN {col_name} {col_type};")

        # Create Indexes safely AFTER all columns are verified
        cursor.execute("CREATE INDEX IF NOT EXISTS idx_users_email ON users(email);")
        cursor.execute("CREATE INDEX IF NOT EXISTS idx_businesses_user ON businesses(user_id);")
        cursor.execute("CREATE INDEX IF NOT EXISTS idx_products_business ON products(business_id);")
        cursor.execute("CREATE INDEX IF NOT EXISTS idx_products_user ON products(user_id);")
        cursor.execute("CREATE INDEX IF NOT EXISTS idx_subscriptions_user_id ON user_subscriptions(user_id);")
        cursor.execute("CREATE INDEX IF NOT EXISTS idx_suppliers_biz ON suppliers(business_id);")
        cursor.execute("CREATE INDEX IF NOT EXISTS idx_suppliers_user ON suppliers(user_id);")
        cursor.execute("CREATE INDEX IF NOT EXISTS idx_communications_user ON supplier_communications(user_id);")
        cursor.execute("CREATE INDEX IF NOT EXISTS idx_security_alerts_status ON security_alerts(status);")
        cursor.execute("CREATE INDEX IF NOT EXISTS idx_audit_events_history ON audit_events(created_at DESC);")
        cursor.execute("CREATE INDEX IF NOT EXISTS idx_admin_audit_history ON admin_audit_events(created_at DESC);")
        cursor.execute("CREATE INDEX IF NOT EXISTS idx_user_activity_history ON user_activity(user_id, created_at DESC);")
        cursor.execute("CREATE INDEX IF NOT EXISTS idx_user_consents_email ON user_policy_consents(email, agreed_at DESC);")

        connection.commit()

    # =========================================================================
    # MANDATORY LEGAL POLICY CONSENT CRUD
    # =========================================================================
    def record_policy_consent(self, consent: UserPolicyConsent) -> None:
        """Store immutable user legal consent record with exact policy versions."""
        self._insert("user_policy_consents", self._model_values(consent))

    def get_latest_user_consent(self, email: str) -> Optional[UserPolicyConsent]:
        """Fetch the most recent policy consent record for an email address."""
        row = self._fetch_one(
            "SELECT * FROM user_policy_consents WHERE LOWER(email) = LOWER(?) ORDER BY agreed_at DESC LIMIT 1",
            (email.strip(),),
        )
        if row:
            return UserPolicyConsent(**dict(row))
        return None

    def has_accepted_current_policies(self, email: str) -> bool:
        """Check if user has accepted the exact current policy versions."""
        consent = self.get_latest_user_consent(email)
        if not consent:
            return False

        return (
            consent.terms_version == self.CURRENT_POLICIES["terms_version"]
            and consent.privacy_version == self.CURRENT_POLICIES["privacy_version"]
            and consent.acceptable_use_version == self.CURRENT_POLICIES["acceptable_use_version"]
            and consent.subscription_policy_version == self.CURRENT_POLICIES["subscription_policy_version"]
            and consent.communication_policy_version == self.CURRENT_POLICIES["communication_policy_version"]
            and consent.data_security_policy_version == self.CURRENT_POLICIES["data_security_policy_version"]
            and consent.consent_status == "ACCEPTED"
        )

    def list_user_consents(self, user_id: Optional[str] = None) -> List[sqlite3.Row]:
        """List all policy consent events for audit and compliance inspection."""
        if user_id:
            return self.connect().execute(
                "SELECT * FROM user_policy_consents WHERE user_id = ? ORDER BY agreed_at DESC", (user_id,)
            ).fetchall()
        return self.connect().execute(
            "SELECT * FROM user_policy_consents ORDER BY agreed_at DESC"
        ).fetchall()

    # =========================================================================
    # USER & AUTHENTICATION CRUD
    # =========================================================================
    def create_user(self, user: User) -> User:
        """Insert a user into database."""
        vals = self._model_values(user)
        if not vals.get("created_at"):
            vals["created_at"] = datetime.now(timezone.utc).isoformat()
        if not vals.get("updated_at"):
            vals["updated_at"] = datetime.now(timezone.utc).isoformat()
        self._insert("users", vals)
        return user

    def update_user(self, user: User) -> User:
        """Update existing user record."""
        connection = self.connect()
        with connection:
            connection.execute(
                """
                UPDATE users SET
                    name = ?, phone = ?, preferred_language = ?, preferred_currency = ?,
                    timezone = ?, profile_image_path = ?, is_verified = ?, is_locked = ?,
                    failed_login_attempts = ?, locked_until = ?, terms_accepted_at = ?,
                    privacy_accepted_at = ?, aup_accepted_at = ?, onboarding_completed = ?,
                    updated_at = ?
                WHERE id = ?
                """,
                (
                    user.name, user.phone, user.preferred_language, user.preferred_currency,
                    user.timezone, user.profile_image_path, int(user.is_verified), int(user.is_locked),
                    user.failed_login_attempts, user.locked_until, user.terms_accepted_at,
                    user.privacy_accepted_at, user.aup_accepted_at, int(user.onboarding_completed),
                    datetime.now(timezone.utc).isoformat(), user.id,
                ),
            )
        return user

    def get_user_by_email(self, email: str) -> User | None:
        """Retrieve user record by email address."""
        row = self._fetch_one("SELECT * FROM users WHERE LOWER(email) = LOWER(?)", (email.strip(),))
        if not row:
            return None
        d = dict(row)
        d["is_verified"] = bool(d.get("is_verified", 1))
        d["is_locked"] = bool(d.get("is_locked", 0))
        d["onboarding_completed"] = bool(d.get("onboarding_completed", 0))
        return User.model_validate(d)

    def get_user_by_id(self, user_id: str) -> User | None:
        """Retrieve user record by ID."""
        row = self._fetch_one("SELECT * FROM users WHERE id = ?", (user_id,))
        if not row:
            return None
        d = dict(row)
        d["is_verified"] = bool(d.get("is_verified", 1))
        d["is_locked"] = bool(d.get("is_locked", 0))
        d["onboarding_completed"] = bool(d.get("onboarding_completed", 0))
        return User.model_validate(d)

    def list_all_users(self) -> List[User]:
        """List all registered users for Admin view."""
        rows = self._fetch_all("SELECT * FROM users ORDER BY created_at DESC")
        res = []
        for r in rows:
            d = dict(r)
            d["is_verified"] = bool(d.get("is_verified", 1))
            d["is_locked"] = bool(d.get("is_locked", 0))
            d["onboarding_completed"] = bool(d.get("onboarding_completed", 0))
            res.append(User.model_validate(d))
        return res

    def verify_user(self, email: str) -> bool:
        """Mark user account as email verified."""
        connection = self.connect()
        with connection:
            cursor = connection.execute("UPDATE users SET is_verified = 1 WHERE LOWER(email) = LOWER(?)", (email.strip(),))
            return cursor.rowcount > 0

    def save_otp(self, email: str, otp_hash: str, expires_at: str) -> None:
        """Save or overwrite an email OTP verification hash."""
        connection = self.connect()
        cursor = connection.cursor()
        otp_info = cursor.execute("PRAGMA table_info(otp_codes);").fetchall()
        otp_cols = [c[1] for c in otp_info]

        with connection:
            if "otp_code" in otp_cols:
                connection.execute(
                    """
                    INSERT INTO otp_codes (email, otp_code, otp_hash, expires_at, attempts, last_sent_at, created_at)
                    VALUES (?, ?, ?, ?, 0, datetime('now'), datetime('now'))
                    ON CONFLICT(email) DO UPDATE SET
                        otp_code=excluded.otp_code,
                        otp_hash=excluded.otp_hash,
                        expires_at=excluded.expires_at,
                        attempts=0,
                        last_sent_at=datetime('now');
                    """,
                    (email.lower().strip(), otp_hash, otp_hash, expires_at),
                )
            else:
                connection.execute(
                    """
                    INSERT INTO otp_codes (email, otp_hash, expires_at, attempts, last_sent_at, created_at)
                    VALUES (?, ?, ?, 0, datetime('now'), datetime('now'))
                    ON CONFLICT(email) DO UPDATE SET
                        otp_hash=excluded.otp_hash,
                        expires_at=excluded.expires_at,
                        attempts=0,
                        last_sent_at=datetime('now');
                    """,
                    (email.lower().strip(), otp_hash, expires_at),
                )

    def get_otp_record(self, email: str) -> OTPRecord | None:
        """Retrieve latest pending OTP record for email."""
        row = self._fetch_one("SELECT * FROM otp_codes WHERE LOWER(email) = LOWER(?)", (email.lower().strip(),))
        if not row:
            return None
        row_dict = dict(row)
        if "otp_hash" not in row_dict or not row_dict["otp_hash"]:
            row_dict["otp_hash"] = row_dict.get("otp_code", "")
        return OTPRecord.model_validate(row_dict)

    def get_otp(self, email: str) -> str | None:
        """Backward compatibility for existing test suite."""
        row = self._fetch_one("SELECT * FROM otp_codes WHERE LOWER(email) = LOWER(?)", (email.lower().strip(),))
        if not row:
            return None
        return row["otp_hash"] if ("otp_hash" in row.keys() and row["otp_hash"]) else row.get("otp_code")

    def increment_otp_attempts(self, email: str) -> int:
        """Increment failed OTP attempts count."""
        connection = self.connect()
        with connection:
            connection.execute("UPDATE otp_codes SET attempts = attempts + 1 WHERE LOWER(email) = LOWER(?)", (email.lower().strip(),))
            rec = self.get_otp_record(email)
            return rec.attempts if rec else 0

    def delete_otp(self, email: str) -> None:
        """Delete OTP record after verification."""
        connection = self.connect()
        with connection:
            connection.execute("DELETE FROM otp_codes WHERE LOWER(email) = LOWER(?)", (email.lower().strip(),))

    # =========================================================================
    # SUBSCRIPTION & USAGE CRUD
    # =========================================================================
    def save_subscription(self, subscription: UserSubscription) -> UserSubscription:
        """Idempotently save or update a user subscription."""
        connection = self.connect()
        with connection:
            connection.execute(
                """
                INSERT INTO user_subscriptions (
                    id, user_id, razorpay_customer_id, razorpay_order_id, razorpay_subscription_id, razorpay_payment_id,
                    plan_name, billing_cycle, subscription_status,
                    current_period_start, current_period_end, cancel_at_period_end,
                    minimum_commitment_end, coupon_code, discount_applied, created_at, updated_at
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                ON CONFLICT(id) DO UPDATE SET
                    razorpay_customer_id=excluded.razorpay_customer_id,
                    razorpay_order_id=excluded.razorpay_order_id,
                    razorpay_subscription_id=excluded.razorpay_subscription_id,
                    razorpay_payment_id=excluded.razorpay_payment_id,
                    plan_name=excluded.plan_name,
                    billing_cycle=excluded.billing_cycle,
                    subscription_status=excluded.subscription_status,
                    current_period_start=excluded.current_period_start,
                    current_period_end=excluded.current_period_end,
                    cancel_at_period_end=excluded.cancel_at_period_end,
                    minimum_commitment_end=excluded.minimum_commitment_end,
                    coupon_code=excluded.coupon_code,
                    discount_applied=excluded.discount_applied,
                    updated_at=excluded.updated_at;
                """,
                (
                    subscription.id,
                    subscription.user_id,
                    subscription.razorpay_customer_id,
                    subscription.razorpay_order_id,
                    subscription.razorpay_subscription_id,
                    subscription.razorpay_payment_id,
                    subscription.plan_name,
                    subscription.billing_cycle,
                    subscription.subscription_status,
                    subscription.current_period_start,
                    subscription.current_period_end,
                    1 if subscription.cancel_at_period_end else 0,
                    subscription.minimum_commitment_end,
                    subscription.coupon_code,
                    subscription.discount_applied,
                    subscription.created_at,
                    subscription.updated_at,
                ),
            )
        return subscription

    def get_subscription_by_user_id(self, user_id: str) -> UserSubscription | None:
        """Retrieve active subscription for user."""
        row = self._fetch_one(
            "SELECT * FROM user_subscriptions WHERE user_id = ? ORDER BY updated_at DESC LIMIT 1",
            (user_id,),
        )
        if not row:
            return None
        d = dict(row)
        d["cancel_at_period_end"] = bool(d.get("cancel_at_period_end", 0))
        return UserSubscription.model_validate(d)

    def get_subscription_by_razorpay_id(self, razorpay_id: str) -> UserSubscription | None:
        row = self._fetch_one(
            "SELECT * FROM user_subscriptions WHERE razorpay_subscription_id = ? OR razorpay_order_id = ? OR razorpay_payment_id = ? ORDER BY updated_at DESC LIMIT 1",
            (razorpay_id, razorpay_id, razorpay_id),
        )
        if not row:
            return None
        d = dict(row)
        d["cancel_at_period_end"] = bool(d.get("cancel_at_period_end", 0))
        return UserSubscription.model_validate(d)

    def claim_razorpay_webhook_event(self, event_id: str, event_type: str) -> bool:
        """Atomically claim a verified webhook delivery; False means duplicate."""
        with self.connect():
            cur = self.connect().execute(
                "INSERT OR IGNORE INTO razorpay_webhook_events (event_id, event_type) VALUES (?, ?)",
                (event_id, event_type),
            )
        return cur.rowcount == 1

    def list_all_subscriptions(self) -> List[UserSubscription]:
        """List all subscriptions for admin review."""
        rows = self._fetch_all("SELECT * FROM user_subscriptions ORDER BY updated_at DESC")
        res = []
        for r in rows:
            d = dict(r)
            d["cancel_at_period_end"] = bool(d.get("cancel_at_period_end", 0))
            res.append(UserSubscription.model_validate(d))
        return res

    def save_usage_record(self, record: UsageRecord) -> UsageRecord:
        """Save or update monthly metered usage."""
        connection = self.connect()
        with connection:
            connection.execute(
                """
                INSERT INTO usage_records (id, user_id, period_month, camera_scans, voice_queries, ai_decisions, documents_analyzed, updated_at)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?)
                ON CONFLICT(user_id, period_month) DO UPDATE SET
                    camera_scans=excluded.camera_scans,
                    voice_queries=excluded.voice_queries,
                    ai_decisions=excluded.ai_decisions,
                    documents_analyzed=excluded.documents_analyzed,
                    updated_at=excluded.updated_at;
                """,
                (
                    record.id, record.user_id, record.period_month, record.camera_scans,
                    record.voice_queries, record.ai_decisions, record.documents_analyzed, record.updated_at
                ),
            )
        return record

    def get_usage_record(self, user_id: str, period_month: str) -> UsageRecord | None:
        """Retrieve usage for user in target month."""
        row = self._fetch_one("SELECT * FROM usage_records WHERE user_id = ? AND period_month = ?", (user_id, period_month))
        return UsageRecord.model_validate(dict(row)) if row else None

    # =========================================================================
    # BUSINESS & PRODUCTS CRUD
    # =========================================================================
    def create_business(self, business: Business) -> Business:
        """Insert a business."""
        self._insert("businesses", self._model_values(business))
        return business

    def get_business(self, business_id: str) -> Business | None:
        """Retrieve a business by ID."""
        row = self._fetch_one("SELECT * FROM businesses WHERE id = ?", (business_id,))
        return Business.model_validate(dict(row)) if row else None

    def list_businesses(self, user_id: Optional[str] = None) -> List[Business]:
        """Return persisted businesses, optionally filtered by user_id."""
        if user_id:
            rows = self.connect().execute("SELECT * FROM businesses WHERE user_id = ? ORDER BY created_at, id", (user_id,)).fetchall()
        else:
            rows = self.connect().execute("SELECT * FROM businesses ORDER BY created_at, id").fetchall()
        return [Business.model_validate(dict(row)) for row in rows]

    def create_product(self, product: Product) -> Product:
        """Insert a product."""
        self._insert("products", self._model_values(product))
        return product

    def get_product(self, product_id: str) -> Product | None:
        """Retrieve a product by ID."""
        row = self._fetch_one("SELECT * FROM products WHERE id = ?", (product_id,))
        return Product.model_validate(dict(row)) if row else None

    def list_products(self, business_id: str, user_id: Optional[str] = None) -> List[Product]:
        """Return products for a business, optionally constrained to its owner."""
        if user_id is not None:
            rows = self.connect().execute(
                "SELECT * FROM products WHERE business_id = ? AND user_id = ? ORDER BY sku, id",
                (business_id, user_id),
            ).fetchall()
            return [Product.model_validate(dict(row)) for row in rows]
        rows = self.connect().execute(
            "SELECT * FROM products WHERE business_id = ? ORDER BY sku, id", (business_id,)
        ).fetchall()
        return [Product.model_validate(dict(row)) for row in rows]

    def list_all_products(self) -> List[Product]:
        """Return all catalog products across all businesses."""
        rows = self.connect().execute(
            "SELECT * FROM products ORDER BY name, sku, id"
        ).fetchall()
        return [Product.model_validate(dict(row)) for row in rows]

    def get_product_by_sku(self, sku: str, business_id: str | None = None) -> Product | None:
        """Find a product by SKU."""
        if business_id:
            row = self._fetch_one(
                "SELECT * FROM products WHERE LOWER(sku) = LOWER(?) AND business_id = ?",
                (sku.strip(), business_id),
            )
        else:
            row = self._fetch_one(
                "SELECT * FROM products WHERE LOWER(sku) = LOWER(?)",
                (sku.strip(),),
            )
        return Product.model_validate(dict(row)) if row else None

    def update_product_stock(
        self, product_id: str, new_stock: int, audit_values: dict[str, Any] | None = None
    ) -> tuple[int, int]:
        """Atomically set product stock to an exact value with transaction safety."""
        if new_stock < 0:
            raise ValueError("Stock level cannot be negative")
        connection = self.connect()
        with connection:
            row = connection.execute("SELECT current_stock FROM products WHERE id = ?", (product_id,)).fetchone()
            if row is None:
                raise ValueError(f"Product with ID '{product_id}' does not exist")
            previous_stock = int(row["current_stock"])
            connection.execute(
                "UPDATE products SET current_stock = ? WHERE id = ?",
                (new_stock, product_id),
            )
            if audit_values:
                self._insert("audit_events", audit_values, commit=False)
            return previous_stock, new_stock

    def adjust_product_stock(
        self, product_id: str, delta: int, audit_values: dict[str, Any] | None = None
    ) -> tuple[int, int]:
        """Atomically add or subtract stock from a product."""
        connection = self.connect()
        with connection:
            row = connection.execute("SELECT current_stock FROM products WHERE id = ?", (product_id,)).fetchone()
            if row is None:
                raise ValueError(f"Product with ID '{product_id}' does not exist")
            previous_stock = int(row["current_stock"])
            new_stock = previous_stock + delta
            if new_stock < 0:
                raise ValueError(
                    f"Adjustment of {delta} units would result in negative stock ({new_stock}). Current: {previous_stock}"
                )
            connection.execute(
                "UPDATE products SET current_stock = ? WHERE id = ?",
                (new_stock, product_id),
            )
            if audit_values:
                self._insert("audit_events", audit_values, commit=False)
            return previous_stock, new_stock

    def batch_reconcile_inventory(
        self, adjustments: list[dict[str, Any]], audit_values: dict[str, Any] | None = None
    ) -> list[dict[str, Any]]:
        """Atomically execute multiple inventory reconciliation updates in one single transaction."""
        results = []
        connection = self.connect()
        with connection:
            for item in adjustments:
                prod_id = item["product_id"]
                target_stock = item["new_stock"]
                if target_stock < 0:
                    raise ValueError(f"Target stock for product {prod_id} cannot be negative")
                row = connection.execute("SELECT current_stock, name, sku FROM products WHERE id = ?", (prod_id,)).fetchone()
                if row is None:
                    continue
                prev = int(row["current_stock"])
                connection.execute("UPDATE products SET current_stock = ? WHERE id = ?", (target_stock, prod_id))
                results.append({
                    "product_id": prod_id,
                    "name": row["name"],
                    "sku": row["sku"],
                    "previous_stock": prev,
                    "new_stock": target_stock,
                    "delta": target_stock - prev,
                })
            if audit_values:
                self._insert("audit_events", audit_values, commit=False)
        return results

    # =========================================================================
    # SUPPLIERS CRUD WITH SOFT-DELETE & AUDIT
    # =========================================================================
    def create_supplier(self, supplier: Supplier) -> Supplier:
        """Insert a supplier."""
        self._insert("suppliers", self._model_values(supplier))
        return supplier

    def update_supplier(self, supplier: Supplier) -> Supplier:
        """Update existing supplier record."""
        connection = self.connect()
        with connection:
            connection.execute(
                """
                UPDATE suppliers SET
                    name = ?, company_name = ?, phone = ?, email = ?, address = ?,
                    delivery_person_name = ?, delivery_person_phone = ?, gst_id = ?,
                    payment_terms = ?, supplier_category = ?, notes = ?,
                    lead_time_days = ?, reliability_score = ?, is_archived = ?,
                    updated_at = ?
                WHERE id = ?
                """,
                (
                    supplier.name, supplier.company_name, supplier.phone, supplier.email, supplier.address,
                    supplier.delivery_person_name, supplier.delivery_person_phone, supplier.gst_id,
                    supplier.payment_terms, supplier.supplier_category, supplier.notes,
                    supplier.lead_time_days, supplier.reliability_score, int(supplier.is_archived),
                    datetime.now(timezone.utc).isoformat(), supplier.id,
                ),
            )
        return supplier

    def archive_supplier(self, supplier_id: str, user_id: Optional[str] = None) -> bool:
        """Soft-delete/archive a supplier."""
        connection = self.connect()
        with connection:
            if user_id is None:
                # Legacy internal callers; customer-facing callers pass user_id.
                cursor = connection.execute(
                    "UPDATE suppliers SET is_archived = 1, updated_at = datetime('now') WHERE id = ?",
                    (supplier_id,),
                )
                return cursor.rowcount > 0
            cursor = connection.execute(
                "UPDATE suppliers SET is_archived = 1, updated_at = datetime('now') WHERE id = ? AND user_id IS ?",
                (supplier_id, user_id),
            )
            return cursor.rowcount > 0

    def restore_supplier(self, supplier_id: str, user_id: Optional[str] = None) -> bool:
        """Restore an archived supplier."""
        connection = self.connect()
        with connection:
            if user_id is None:
                cursor = connection.execute(
                    "UPDATE suppliers SET is_archived = 0, updated_at = datetime('now') WHERE id = ?",
                    (supplier_id,),
                )
                return cursor.rowcount > 0
            cursor = connection.execute(
                "UPDATE suppliers SET is_archived = 0, updated_at = datetime('now') WHERE id = ? AND user_id IS ?",
                (supplier_id, user_id),
            )
            return cursor.rowcount > 0

    def delete_supplier(self, supplier_id: str, user_id: str) -> bool:
        """Permanently delete a supplier and its terms."""
        connection = self.connect()
        with connection:
            owned = connection.execute("SELECT id FROM suppliers WHERE id = ? AND user_id = ?", (supplier_id, user_id)).fetchone()
            if not owned:
                return False
            connection.execute("DELETE FROM supplier_products WHERE supplier_id = ?", (supplier_id,))
            cursor = connection.execute("DELETE FROM suppliers WHERE id = ? AND user_id = ?", (supplier_id, user_id))
            return cursor.rowcount > 0

    def get_supplier(self, supplier_id: str, user_id: str) -> Supplier | None:
        """Retrieve a supplier by ID."""
        row = self._fetch_one("SELECT * FROM suppliers WHERE id = ? AND user_id = ?", (supplier_id, user_id))
        if not row:
            return None
        d = dict(row)
        d["is_archived"] = bool(d.get("is_archived", 0))
        return Supplier.model_validate(d)

    def list_suppliers(self, business_id: str, user_id: Optional[str] = None, include_archived: bool = False) -> List[Supplier]:
        """Return suppliers for one business, constrained to an owner when supplied."""
        clauses, params = ["business_id = ?"], [business_id]
        if user_id is not None:
            clauses.append("user_id = ?")
            params.append(user_id)
        if not include_archived:
            clauses.append("is_archived = 0")
        rows = self.connect().execute(
            f"SELECT * FROM suppliers WHERE {' AND '.join(clauses)} ORDER BY name, id", tuple(params)
        ).fetchall()
        res = []
        for r in rows:
            d = dict(r)
            d["is_archived"] = bool(d.get("is_archived", 0))
            res.append(Supplier.model_validate(d))
        return res

    def create_supplier_product(self, supplier_product: SupplierProduct) -> SupplierProduct:
        """Insert terms for a supplier/product pairing."""
        self._insert("supplier_products", self._model_values(supplier_product))
        return supplier_product

    def create_supplier_with_product(
        self, supplier: Supplier, supplier_product: SupplierProduct
    ) -> Supplier:
        """Atomically create a supplier and its commercial terms."""
        if supplier_product.supplier_id != supplier.id:
            raise ValueError("supplier_product must belong to the supplier")
        connection = self.connect()
        with connection:
            self._insert("suppliers", self._model_values(supplier), commit=False)
            self._insert("supplier_products", self._model_values(supplier_product), commit=False)
        return supplier

    def list_supplier_products(self, product_id: str) -> List[SupplierProduct]:
        """Return commercial terms for one product."""
        rows = self.connect().execute(
            "SELECT * FROM supplier_products WHERE product_id = ? ORDER BY supplier_id", (product_id,)
        ).fetchall()
        return [SupplierProduct.model_validate(dict(row)) for row in rows]

    # =========================================================================
    # SUPPLIER COMMUNICATIONS CRUD
    # =========================================================================
    def create_supplier_communication(self, comm: SupplierCommunication) -> SupplierCommunication:
        """Record supplier communication in the audit log."""
        self._insert("supplier_communications", self._model_values(comm))
        return comm

    def list_supplier_communications(
        self, business_id: Optional[str] = None, supplier_id: Optional[str] = None, user_id: Optional[str] = None
    ) -> List[SupplierCommunication]:
        """List supplier communications with optional filters."""
        clauses = []
        params = []
        if business_id:
            clauses.append("business_id = ?")
            params.append(business_id)
        if supplier_id:
            clauses.append("supplier_id = ?")
            params.append(supplier_id)
        if user_id:
            clauses.append("user_id = ?")
            params.append(user_id)
        where = f" WHERE {' AND '.join(clauses)}" if clauses else ""
        rows = self.connect().execute(
            f"SELECT * FROM supplier_communications{where} ORDER BY created_at DESC", tuple(params)
        ).fetchall()
        return [SupplierCommunication.model_validate(dict(r)) for r in rows]

    # =========================================================================
    # SECURITY ALERTS CRUD
    # =========================================================================
    def create_security_alert(self, alert: SecurityAlert) -> SecurityAlert:
        """Insert a security alert event."""
        self._insert("security_alerts", self._model_values(alert))
        return alert

    def list_security_alerts(self, status: Optional[str] = None) -> List[SecurityAlert]:
        """List security alerts."""
        if status:
            rows = self.connect().execute("SELECT * FROM security_alerts WHERE status = ? ORDER BY created_at DESC", (status,)).fetchall()
        else:
            rows = self.connect().execute("SELECT * FROM security_alerts ORDER BY created_at DESC").fetchall()
        return [SecurityAlert.model_validate(dict(r)) for r in rows]

    # =========================================================================
    # DECISION SNAPSHOTS, WHAT-IF & AUDIT EVENTS
    # =========================================================================
    def create_policy(self, policy: Policy) -> Policy:
        values = self._model_values(policy)
        values["allowed_auto_actions"] = self._json_list(policy.allowed_auto_actions)
        self._insert("policies", values)
        return policy

    def get_policy(self, policy_id: str) -> Policy | None:
        row = self._fetch_one("SELECT * FROM policies WHERE id = ?", (policy_id,))
        if not row:
            return None
        values = dict(row)
        values["allowed_auto_actions"] = self._parse_json_list(values["allowed_auto_actions"])
        return Policy.model_validate(values)

    def create_sales_record(self, sales_record: SalesRecord) -> SalesRecord:
        self._insert("sales_records", self._model_values(sales_record))
        return sales_record

    def create_purchase(self, purchase: Purchase) -> Purchase:
        self._insert("purchases", self._model_values(purchase))
        return purchase

    def create_decision(self, decision: Decision) -> Decision:
        values = self._model_values(decision, exclude={"options"})
        connection = self.connect()
        with connection:
            self._insert("decisions", values, commit=False)
            for option in decision.options:
                self._insert_decision_option(decision.id, option, commit=False)
        return decision

    def create_decision_option(self, decision_id: str, decision_option: DecisionOption) -> DecisionOption:
        self._insert_decision_option(decision_id, decision_option, commit=True)
        return decision_option

    def create_outcome(self, outcome: Outcome) -> Outcome:
        self._insert("outcomes", self._model_values(outcome))
        return outcome

    def save_decision_snapshot(self, values: dict[str, Any], audit_values: dict[str, Any]) -> bool:
        connection = self.connect()
        with connection:
            cursor = connection.execute(
                """INSERT OR IGNORE INTO decision_snapshots (
                    snapshot_id, business_id, product_id, facts_json, proposal_json,
                    reference_validation_json, policy_validation_json, status, created_at
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)""",
                (
                    values["snapshot_id"], values["business_id"], values["product_id"],
                    values["facts_json"], values["proposal_json"],
                    values["reference_validation_json"], values["policy_validation_json"],
                    values["status"], values["created_at"],
                ),
            )
            if cursor.rowcount:
                self._insert("audit_events", audit_values, commit=False)
                return True
        return False

    def save_review_bundle(
        self, business: Business, product: Product, suppliers: tuple[Supplier, ...],
        supplier_products: tuple[SupplierProduct, ...], values: dict[str, Any], audit_values: dict[str, Any]
    ) -> bool:
        connection = self.connect()
        with connection:
            self._insert_or_ignore("businesses", self._model_values(business))
            self._insert_or_ignore("products", self._model_values(product))
            for supplier in suppliers:
                self._insert_or_ignore("suppliers", self._model_values(supplier))
            for terms in supplier_products:
                self._insert_or_ignore("supplier_products", self._model_values(terms))
            cursor = connection.execute(
                """INSERT OR IGNORE INTO decision_snapshots (
                    snapshot_id, business_id, product_id, facts_json, proposal_json,
                    reference_validation_json, policy_validation_json, status, created_at
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)""",
                (
                    values["snapshot_id"], values["business_id"], values["product_id"],
                    values["facts_json"], values["proposal_json"],
                    values["reference_validation_json"], values["policy_validation_json"],
                    values["status"], values["created_at"],
                ),
            )
            if cursor.rowcount:
                self._insert("audit_events", audit_values, commit=False)
                return True
        return False

    def get_decision_snapshot(self, snapshot_id: str) -> sqlite3.Row | None:
        return self._fetch_one("SELECT * FROM decision_snapshots WHERE snapshot_id = ?", (snapshot_id,))

    def list_decision_snapshots(
        self, *, business_id: str | None = None, product_id: str | None = None, status: str | None = None
    ) -> list[sqlite3.Row]:
        clauses: list[str] = []
        parameters: list[Any] = []
        for column, value in (("business_id", business_id), ("product_id", product_id), ("status", status)):
            if value is not None:
                clauses.append(f"{column} = ?")
                parameters.append(value)
        where = f" WHERE {' AND '.join(clauses)}" if clauses else ""
        return self.connect().execute(
            f"SELECT * FROM decision_snapshots{where} ORDER BY created_at DESC, snapshot_id DESC",
            tuple(parameters),
        ).fetchall()

    def save_what_if_scenario(self, values: dict[str, Any], audit_values: dict[str, Any]) -> bool:
        connection = self.connect()
        with connection:
            cursor = connection.execute(
                """INSERT OR IGNORE INTO what_if_scenarios (
                    id, decision_snapshot_id, baseline_snapshot_id, scenario_id, scenario_json, outcome_json, comparison_json, created_at
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?)""",
                (
                    values["id"], values["decision_snapshot_id"], values["baseline_snapshot_id"], values["scenario_id"],
                    values["scenario_json"], values.get("outcome_json", "{}"), values["comparison_json"], values["created_at"],
                ),
            )
            if cursor.rowcount:
                self._insert("audit_events", audit_values, commit=False)
                return True
        return False

    def get_what_if_scenario(self, saved_id: str) -> sqlite3.Row | None:
        return self._fetch_one("SELECT * FROM what_if_scenarios WHERE id = ?", (saved_id,))

    def list_what_if_scenarios(self, decision_snapshot_id: str | None = None) -> list[sqlite3.Row]:
        if decision_snapshot_id is None:
            return self.connect().execute("SELECT * FROM what_if_scenarios ORDER BY created_at DESC, id DESC").fetchall()
        return self.connect().execute("SELECT * FROM what_if_scenarios WHERE decision_snapshot_id = ? ORDER BY created_at DESC, id DESC", (decision_snapshot_id,)).fetchall()

    def create_audit_event(self, values: dict[str, Any]) -> None:
        self._insert("audit_events", values)

    def list_audit_events(self) -> list[sqlite3.Row]:
        return self.connect().execute("SELECT * FROM audit_events ORDER BY created_at DESC, id DESC").fetchall()

    def create_admin_audit_event(self, event: AdminAuditEvent) -> None:
        """Append-only immutable administrator audit record."""
        self._insert("admin_audit_events", self._model_values(event))

    def list_admin_audit_events(
        self, limit: int = 100, user_id: Optional[str] = None, event_type: Optional[str] = None
    ) -> List[sqlite3.Row]:
        """Query immutable admin audit records with filters."""
        clauses = []
        params: List[Any] = []
        if user_id:
            clauses.append("user_id = ?")
            params.append(user_id)
        if event_type:
            clauses.append("event_type = ?")
            params.append(event_type)
        where = f" WHERE {' AND '.join(clauses)}" if clauses else ""
        sql = f"SELECT * FROM admin_audit_events{where} ORDER BY created_at DESC LIMIT ?"
        params.append(limit)
        return self.connect().execute(sql, tuple(params)).fetchall()

    def create_user_activity(self, event: UserActivityEvent) -> None:
        """Record user-visible operational activity."""
        self._insert("user_activity", self._model_values(event))

    def list_user_activity(
        self, user_id: str, limit: int = 50, offset: int = 0
    ) -> List[sqlite3.Row]:
        """List paginated activity history for a specific user."""
        return self.connect().execute(
            "SELECT * FROM user_activity WHERE user_id = ? ORDER BY created_at DESC LIMIT ? OFFSET ?",
            (user_id, limit, offset),
        ).fetchall()

    def get_admin_telemetry(self) -> Dict[str, Any]:
        """Aggregate real-time platform telemetry for Superadmin dashboard."""
        conn = self.connect()
        users = self.list_all_users()
        subs = self.list_all_subscriptions()
        active_subs = [s for s in subs if s.is_active and s.plan_name != "FREE"]
        expired_subs = [s for s in subs if not s.is_active and s.plan_name != "FREE"]

        # Calculate revenue
        monthly_rev = sum(
            get_plan_pricing(s.plan_name).get("monthly_usd", 0.0)
            for s in active_subs
        )

        # Plan breakdown
        plans_dist = {}
        for s in active_subs:
            p = s.plan_name.upper()
            plans_dist[p] = plans_dist.get(p, 0) + 1

        # Activity by user summary
        activity_by_user = []
        for u in users:
            u_bizs = self.list_businesses(u.id)
            b_ids = [b.id for b in u_bizs]
            prod_count = sum(len(self.list_products(bid)) for bid in b_ids)
            sup_count = sum(len(self.list_suppliers(bid, include_archived=True)) for bid in b_ids)
            comm_count = len(self.list_supplier_communications(user_id=u.id))
            sub = self.get_subscription_by_user_id(u.id)

            activity_by_user.append({
                "user_id": u.id,
                "name": u.name,
                "email": u.email,
                "role": u.role,
                "status": "Locked" if u.is_locked else "Active",
                "plan": sub.plan_name.upper() if (sub and sub.is_active) else "FREE",
                "businesses": len(u_bizs),
                "products": prod_count,
                "suppliers": sup_count,
                "orders_dispatched": comm_count,
                "joined_date": u.created_at[:10] if u.created_at else "—",
            })

        return {
            "total_users": len(users),
            "verified_users": sum(1 for u in users if u.is_verified),
            "active_subscriptions": len(active_subs),
            "expired_subscriptions": len(expired_subs),
            "monthly_mrr_usd": monthly_rev,
            "plan_distribution": plans_dist,
            "users_activity_matrix": activity_by_user,
            "total_security_alerts": len(self.list_security_alerts()),
            "total_admin_audits": len(self.list_admin_audit_events(limit=1000)),
        }

    def get_user_detailed_activity(self, user_id: str) -> Dict[str, Any]:
        """Fetch complete historical telemetry breakdown for one inspected user."""
        user = self.get_user_by_id(user_id)
        if not user:
            return {}

        businesses = self.list_businesses(user_id)
        biz_ids = [b.id for b in businesses]

        products = []
        suppliers = []
        for bid in biz_ids:
            products.extend([p.model_dump() for p in self.list_products(bid)])
            suppliers.extend([s.model_dump() for s in self.list_suppliers(bid, include_archived=True)])

        comms = [c.model_dump() for c in self.list_supplier_communications(user_id=user_id)]
        current_month = datetime.now(timezone.utc).strftime("%Y-%m")
        usage = self.get_usage_record(user_id, current_month)
        sub = self.get_subscription_by_user_id(user_id)
        user_acts = self.list_user_activity(user_id, limit=100)

        return {
            "user": user.model_dump(exclude={"password_hash"}),
            "subscription": sub.model_dump() if sub else None,
            "usage_current_month": usage.model_dump() if usage else {},
            "businesses_count": len(businesses),
            "products_count": len(products),
            "suppliers_count": len(suppliers),
            "communications_count": len(comms),
            "recent_communications": comms[:10],
            "activity_timeline": [dict(r) for r in user_acts],
        }

    def clean_audit_logs_retention(self, retention_days: int = 90) -> int:
        """Admin retention policy: remove non-critical audit records older than configured days."""
        cutoff = (datetime.now(timezone.utc) - timedelta(days=retention_days)).isoformat()
        connection = self.connect()
        with connection:
            cursor = connection.execute(
                "DELETE FROM audit_events WHERE created_at < ? AND event_type NOT IN ('SUBSCRIPTION_CREATED', 'PAYMENT_SUCCESS', 'PAYMENT_FAILED')",
                (cutoff,),
            )
            return cursor.rowcount

    # =========================================================================
    # DATA EXPORT & ACCOUNT DELETION (GDPR / Privacy Compliance)
    # =========================================================================
    def export_user_data(self, user_id: str) -> Dict[str, Any]:
        """Export all user-owned data in portable JSON format."""
        user = self.get_user_by_id(user_id)
        if not user:
            return {}

        businesses = self.list_businesses(user_id)
        biz_ids = [b.id for b in businesses]

        products = []
        suppliers = []
        for bid in biz_ids:
            products.extend([p.model_dump() for p in self.list_products(bid)])
            suppliers.extend([s.model_dump() for s in self.list_suppliers(bid, include_archived=True)])

        subscription = self.get_subscription_by_user_id(user_id)
        comms = [c.model_dump() for c in self.list_supplier_communications(user_id=user_id)]

        return {
            "user_profile": user.model_dump(exclude={"password_hash"}),
            "businesses": [b.model_dump() for b in businesses],
            "products": products,
            "suppliers": suppliers,
            "communications": comms,
            "subscription": subscription.model_dump() if subscription else None,
            "exported_at": datetime.now(timezone.utc).isoformat(),
        }

    def delete_user_account_data(self, user_id: str) -> bool:
        """Delete user personal & catalog data while retaining necessary billing/audit records."""
        connection = self.connect()
        with connection:
            # Find businesses owned by user
            rows = connection.execute("SELECT id FROM businesses WHERE user_id = ?", (user_id,)).fetchall()
            biz_ids = [r["id"] for r in rows]

            for bid in biz_ids:
                connection.execute("DELETE FROM supplier_products WHERE supplier_id IN (SELECT id FROM suppliers WHERE business_id = ?)", (bid,))
                connection.execute("DELETE FROM suppliers WHERE business_id = ?", (bid,))
                connection.execute("DELETE FROM products WHERE business_id = ?", (bid,))
                connection.execute("DELETE FROM businesses WHERE id = ?", (bid,))

            connection.execute("DELETE FROM products WHERE user_id = ?", (user_id,))
            connection.execute("DELETE FROM supplier_communications WHERE user_id = ?", (user_id,))
            connection.execute("DELETE FROM usage_records WHERE user_id = ?", (user_id,))
            connection.execute("DELETE FROM users WHERE id = ?", (user_id,))
            return True

    # =========================================================================
    # INTERNAL HELPERS
    # =========================================================================
    def _insert_decision_option(self, decision_id: str, option: DecisionOption, commit: bool) -> None:
        values = {"decision_id": decision_id, **self._model_values(option)}
        self._insert("decision_options", values, commit=commit)

    def _insert(self, table: str, values: dict[str, Any], commit: bool = True) -> None:
        if "created_at" in values and values["created_at"] is None:
            values["created_at"] = datetime.now(timezone.utc).isoformat()
        columns = ", ".join(values)
        placeholders = ", ".join("?" for _ in values)
        conn = self.connect()
        conn.execute(f"INSERT INTO {table} ({columns}) VALUES ({placeholders})", tuple(values.values()))
        if commit:
            conn.commit()

    def _insert_or_ignore(self, table: str, values: dict[str, Any]) -> None:
        columns = ", ".join(values)
        placeholders = ", ".join("?" for _ in values)
        conn = self.connect()
        conn.execute(f"INSERT OR IGNORE INTO {table} ({columns}) VALUES ({placeholders})", tuple(values.values()))
        conn.commit()

    def _fetch_one(self, sql: str, parameters: tuple[Any, ...]) -> sqlite3.Row | None:
        return self.connect().execute(sql, parameters).fetchone()

    def _fetch_all(self, sql: str, parameters: tuple[Any, ...] = ()) -> list[sqlite3.Row]:
        return self.connect().execute(sql, parameters).fetchall()

    @staticmethod
    def _model_values(model: Any, exclude: set[str] | None = None) -> dict[str, Any]:
        values = model.model_dump(exclude=exclude or set())
        return {key: Database._sqlite_value(value) for key, value in values.items()}

    @staticmethod
    def _sqlite_value(value: Any) -> Any:
        if isinstance(value, datetime):
            return value.isoformat()
        if isinstance(value, Enum):
            return value.value
        if isinstance(value, bool):
            return int(value)
        return value

    @staticmethod
    def _json_list(values: list[str]) -> str:
        return json.dumps(values)

    @staticmethod
    def _parse_json_list(value: str) -> list[str]:
        return json.loads(value)
