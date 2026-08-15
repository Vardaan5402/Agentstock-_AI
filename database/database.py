"""SQLite Database Layer with Schema Migration Support."""

import json
import sqlite3
from datetime import datetime
from enum import Enum
from pathlib import Path
from typing import Any

from models.business import Business
from models.decision import Decision, DecisionOption, Outcome
from models.inventory import Product, SalesRecord, Purchase
from models.policy import Policy
from models.supplier import Supplier, SupplierProduct
from models.user import User, OTPRecord
from models.subscription import UserSubscription, SubscriptionStatus, PlanTier


import threading

class Database:
    """SQLite database manager for AGENTSTOCK AI."""

    def __init__(self, db_path: str = "agentstock.db"):
        self.db_path = db_path
        self._local = threading.local()
        self.init_db()

    def initialize(self):
        """Alias for init_db for backwards compatibility with test suite."""
        self.init_db()

    def connect(self) -> sqlite3.Connection:
        """Get or create a thread-local SQLite connection with busy timeout."""
        if not hasattr(self._local, "connection") or self._local.connection is None:
            conn = sqlite3.connect(self.db_path, timeout=10.0, isolation_level=None)
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
        """Initialize all database tables."""
        connection = self.connect()
        with connection:
            connection.executescript(
                """
                CREATE TABLE IF NOT EXISTS users (
                    id TEXT PRIMARY KEY,
                    name TEXT NOT NULL,
                    email TEXT NOT NULL UNIQUE,
                    password_hash TEXT NOT NULL,
                    is_verified INTEGER NOT NULL DEFAULT 1,
                    created_at TEXT NOT NULL DEFAULT (datetime('now'))
                );

                CREATE TABLE IF NOT EXISTS otp_codes (
                    email TEXT PRIMARY KEY,
                    otp_code TEXT NOT NULL,
                    expires_at TEXT NOT NULL,
                    created_at TEXT NOT NULL DEFAULT (datetime('now'))
                );

                CREATE TABLE IF NOT EXISTS user_subscriptions (
                    id TEXT PRIMARY KEY,
                    user_id TEXT NOT NULL,
                    stripe_customer_id TEXT,
                    stripe_subscription_id TEXT,
                    stripe_price_id TEXT,
                    plan_name TEXT NOT NULL DEFAULT 'FREE',
                    subscription_status TEXT NOT NULL DEFAULT 'inactive',
                    current_period_start TEXT,
                    current_period_end TEXT,
                    cancel_at_period_end INTEGER NOT NULL DEFAULT 0,
                    created_at TEXT NOT NULL DEFAULT (datetime('now')),
                    updated_at TEXT NOT NULL DEFAULT (datetime('now')),
                    FOREIGN KEY (user_id) REFERENCES users(id)
                );

                CREATE TABLE IF NOT EXISTS businesses (
                    id TEXT PRIMARY KEY,
                    name TEXT NOT NULL,
                    country TEXT NOT NULL,
                    currency TEXT NOT NULL,
                    industry TEXT NOT NULL,
                    inventory_budget REAL NOT NULL CHECK (inventory_budget >= 0),
                    created_at TEXT NOT NULL DEFAULT (datetime('now'))
                );

                CREATE TABLE IF NOT EXISTS products (
                    id TEXT PRIMARY KEY,
                    business_id TEXT NOT NULL,
                    sku TEXT NOT NULL,
                    name TEXT NOT NULL,
                    current_stock INTEGER NOT NULL CHECK (current_stock >= 0),
                    unit_cost REAL NOT NULL CHECK (unit_cost >= 0),
                    daily_demand REAL NOT NULL CHECK (daily_demand >= 0),
                    safety_stock INTEGER NOT NULL CHECK (safety_stock >= 0),
                    created_at TEXT NOT NULL DEFAULT (datetime('now')),
                    FOREIGN KEY (business_id) REFERENCES businesses(id)
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

                CREATE TABLE IF NOT EXISTS suppliers (
                    id TEXT PRIMARY KEY,
                    business_id TEXT NOT NULL,
                    name TEXT NOT NULL,
                    phone TEXT,
                    email TEXT,
                    lead_time_days REAL NOT NULL CHECK (lead_time_days >= 0),
                    reliability_score REAL NOT NULL DEFAULT 0.5
                        CHECK (reliability_score >= 0 AND reliability_score <= 1),
                    created_at TEXT NOT NULL DEFAULT (datetime('now')),
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
                    entity_type TEXT NOT NULL,
                    entity_id TEXT NOT NULL,
                    event_type TEXT NOT NULL,
                    metadata_json TEXT NOT NULL,
                    created_at TEXT NOT NULL DEFAULT (datetime('now'))
                );

                CREATE INDEX IF NOT EXISTS idx_subscriptions_user_id ON user_subscriptions(user_id);
                CREATE INDEX IF NOT EXISTS idx_subscriptions_stripe_sub ON user_subscriptions(stripe_subscription_id);
                CREATE INDEX IF NOT EXISTS idx_subscriptions_stripe_cust ON user_subscriptions(stripe_customer_id);
                CREATE INDEX IF NOT EXISTS idx_decision_snapshots_history
                    ON decision_snapshots (business_id, product_id, status, created_at DESC);
                CREATE INDEX IF NOT EXISTS idx_what_if_scenarios_history
                    ON what_if_scenarios (decision_snapshot_id, created_at DESC);
                CREATE INDEX IF NOT EXISTS idx_audit_events_history
                    ON audit_events (created_at DESC);
                """
            )
            # Migration check for phone column in suppliers table if existing db
            cursor = connection.cursor()
            table_info = cursor.execute("PRAGMA table_info(suppliers);").fetchall()
            columns = [col[1] for col in table_info]
            if "phone" not in columns:
                cursor.execute("ALTER TABLE suppliers ADD COLUMN phone TEXT;")
            connection.commit()

    def save_subscription(self, subscription: UserSubscription) -> UserSubscription:
        """Idempotently save or update a user subscription."""
        connection = self.connect()
        with connection:
            connection.execute(
                """
                INSERT INTO user_subscriptions (
                    id, user_id, stripe_customer_id, stripe_subscription_id,
                    stripe_price_id, plan_name, subscription_status,
                    current_period_start, current_period_end, cancel_at_period_end,
                    created_at, updated_at
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                ON CONFLICT(id) DO UPDATE SET
                    stripe_customer_id=excluded.stripe_customer_id,
                    stripe_subscription_id=excluded.stripe_subscription_id,
                    stripe_price_id=excluded.stripe_price_id,
                    plan_name=excluded.plan_name,
                    subscription_status=excluded.subscription_status,
                    current_period_start=excluded.current_period_start,
                    current_period_end=excluded.current_period_end,
                    cancel_at_period_end=excluded.cancel_at_period_end,
                    updated_at=excluded.updated_at;
                """,
                (
                    subscription.id,
                    subscription.user_id,
                    subscription.stripe_customer_id,
                    subscription.stripe_subscription_id,
                    subscription.stripe_price_id,
                    subscription.plan_name,
                    subscription.subscription_status,
                    subscription.current_period_start,
                    subscription.current_period_end,
                    1 if subscription.cancel_at_period_end else 0,
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

    def get_subscription_by_stripe_customer_id(self, stripe_customer_id: str) -> UserSubscription | None:
        """Retrieve subscription by Stripe Customer ID."""
        row = self._fetch_one(
            "SELECT * FROM user_subscriptions WHERE stripe_customer_id = ? ORDER BY updated_at DESC LIMIT 1",
            (stripe_customer_id,),
        )
        if not row:
            return None
        d = dict(row)
        d["cancel_at_period_end"] = bool(d.get("cancel_at_period_end", 0))
        return UserSubscription.model_validate(d)

    def get_subscription_by_stripe_subscription_id(self, stripe_subscription_id: str) -> UserSubscription | None:
        """Retrieve subscription by Stripe Subscription ID."""
        row = self._fetch_one(
            "SELECT * FROM user_subscriptions WHERE stripe_subscription_id = ? LIMIT 1",
            (stripe_subscription_id,),
        )
        if not row:
            return None
        d = dict(row)
        d["cancel_at_period_end"] = bool(d.get("cancel_at_period_end", 0))
        return UserSubscription.model_validate(d)

    def list_all_subscriptions(self) -> list[UserSubscription]:
        """List all subscriptions for admin/owner review."""
        rows = self._fetch_all("SELECT * FROM user_subscriptions ORDER BY updated_at DESC")
        res = []
        for r in rows:
            d = dict(r)
            d["cancel_at_period_end"] = bool(d.get("cancel_at_period_end", 0))
            res.append(UserSubscription.model_validate(d))
        return res

    def create_user(self, user: User) -> User:
        """Insert a user into database."""
        vals = self._model_values(user)
        if not vals.get("created_at"):
            vals["created_at"] = datetime.now(timezone.utc).isoformat()
        self._insert("users", vals)
        return user

    def get_user_by_email(self, email: str) -> User | None:
        """Retrieve user record by email address."""
        row = self._fetch_one("SELECT * FROM users WHERE LOWER(email) = LOWER(?)", (email,))
        return User.model_validate(dict(row)) if row else None

    def verify_user(self, email: str) -> bool:
        """Mark user account as email verified."""
        connection = self.connect()
        with connection:
            cursor = connection.execute("UPDATE users SET is_verified = 1 WHERE LOWER(email) = LOWER(?)", (email,))
            return cursor.rowcount > 0

    def save_otp(self, email: str, otp_code: str, expires_at: str) -> None:
        """Save or overwrite an email OTP verification code."""
        connection = self.connect()
        with connection:
            connection.execute(
                "INSERT OR REPLACE INTO otp_codes (email, otp_code, expires_at) VALUES (?, ?, ?)",
                (email.lower(), otp_code, expires_at),
            )

    def get_otp(self, email: str) -> str | None:
        """Retrieve latest pending OTP for email."""
        row = self._fetch_one("SELECT otp_code FROM otp_codes WHERE LOWER(email) = LOWER(?)", (email,))
        return row["otp_code"] if row else None

    def delete_otp(self, email: str) -> None:
        """Delete OTP record after verification."""
        connection = self.connect()
        with connection:
            connection.execute("DELETE FROM otp_codes WHERE LOWER(email) = LOWER(?)", (email,))

    def create_business(self, business: Business) -> Business:
        """Insert a business."""
        self._insert("businesses", self._model_values(business))
        return business

    def get_business(self, business_id: str) -> Business | None:
        """Retrieve a business by ID."""
        row = self._fetch_one("SELECT * FROM businesses WHERE id = ?", (business_id,))
        return Business.model_validate(dict(row)) if row else None

    def create_product(self, product: Product) -> Product:
        """Insert a product."""
        self._insert("products", self._model_values(product))
        return product

    def get_product(self, product_id: str) -> Product | None:
        """Retrieve a product by ID."""
        row = self._fetch_one("SELECT * FROM products WHERE id = ?", (product_id,))
        return Product.model_validate(dict(row)) if row else None

    def create_supplier(self, supplier: Supplier) -> Supplier:
        """Insert a supplier."""
        self._insert("suppliers", self._model_values(supplier))
        return supplier

    def get_supplier(self, supplier_id: str) -> Supplier | None:
        """Retrieve a supplier by ID."""
        row = self._fetch_one("SELECT * FROM suppliers WHERE id = ?", (supplier_id,))
        return Supplier.model_validate(dict(row)) if row else None

    def create_policy(self, policy: Policy) -> Policy:
        """Insert a policy."""
        values = self._model_values(policy)
        values["allowed_auto_actions"] = self._json_list(policy.allowed_auto_actions)
        self._insert("policies", values)
        return policy

    def get_policy(self, policy_id: str) -> Policy | None:
        """Retrieve a policy by ID."""
        row = self._fetch_one("SELECT * FROM policies WHERE id = ?", (policy_id,))
        if not row:
            return None
        values = dict(row)
        values["allowed_auto_actions"] = self._parse_json_list(values["allowed_auto_actions"])
        return Policy.model_validate(values)

    def create_sales_record(self, sales_record: SalesRecord) -> SalesRecord:
        """Insert a sales record."""
        self._insert("sales_records", self._model_values(sales_record))
        return sales_record

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

    def create_purchase(self, purchase: Purchase) -> Purchase:
        """Insert a purchase."""
        self._insert("purchases", self._model_values(purchase))
        return purchase

    def create_decision(self, decision: Decision) -> Decision:
        """Insert a decision and all of its validated options atomically."""
        values = self._model_values(decision, exclude={"options"})
        connection = self.connect()
        with connection:
            self._insert("decisions", values, commit=False)
            for option in decision.options:
                self._insert_decision_option(decision.id, option, commit=False)
        return decision

    def create_decision_option(
        self, decision_id: str, decision_option: DecisionOption
    ) -> DecisionOption:
        """Insert an additional option for an existing decision."""
        self._insert_decision_option(decision_id, decision_option, commit=True)
        return decision_option

    def create_outcome(self, outcome: Outcome) -> Outcome:
        """Insert an outcome record for a decision."""
        self._insert("outcomes", self._model_values(outcome))
        return outcome

    def list_businesses(self) -> list[Business]:
        """Return persisted businesses in creation order."""
        rows = self.connect().execute("SELECT * FROM businesses ORDER BY created_at, id").fetchall()
        return [Business.model_validate(dict(row)) for row in rows]

    def list_products(self, business_id: str) -> list[Product]:
        """Return products for one validated business."""
        rows = self.connect().execute(
            "SELECT * FROM products WHERE business_id = ? ORDER BY sku, id", (business_id,)
        ).fetchall()
        return [Product.model_validate(dict(row)) for row in rows]

    def list_all_products(self) -> list[Product]:
        """Return all catalog products across all businesses."""
        rows = self.connect().execute(
            "SELECT * FROM products ORDER BY name, sku, id"
        ).fetchall()
        return [Product.model_validate(dict(row)) for row in rows]

    def get_product_by_sku(self, sku: str, business_id: str | None = None) -> Product | None:
        """Find a product by exact or case-insensitive SKU."""
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

    def list_suppliers(self, business_id: str) -> list[Supplier]:
        """Return suppliers for one business."""
        rows = self.connect().execute(
            "SELECT * FROM suppliers WHERE business_id = ? ORDER BY name, id", (business_id,)
        ).fetchall()
        return [Supplier.model_validate(dict(row)) for row in rows]

    def list_supplier_products(self, product_id: str) -> list[SupplierProduct]:
        """Return commercial terms for one product."""
        rows = self.connect().execute(
            "SELECT * FROM supplier_products WHERE product_id = ? ORDER BY supplier_id", (product_id,)
        ).fetchall()
        return [SupplierProduct.model_validate(dict(row)) for row in rows]

    def save_decision_snapshot(self, values: dict[str, Any], audit_values: dict[str, Any]) -> bool:
        """Insert immutable evidence and its creation audit atomically."""
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
        self,
        business: Business,
        product: Product,
        suppliers: tuple[Supplier, ...],
        supplier_products: tuple[SupplierProduct, ...],
        values: dict[str, Any],
        audit_values: dict[str, Any],
    ) -> bool:
        """Persist missing catalog records, immutable evidence, and audit atomically."""
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
        """Retrieve one immutable decision snapshot row."""
        return self._fetch_one("SELECT * FROM decision_snapshots WHERE snapshot_id = ?", (snapshot_id,))

    def list_decision_snapshots(
        self, *, business_id: str | None = None, product_id: str | None = None, status: str | None = None
    ) -> list[sqlite3.Row]:
        """List immutable snapshots with optional equality filters."""
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
        """Insert immutable scenario evidence and creation audit atomically."""
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
        """Retrieve one saved counterfactual result."""
        return self._fetch_one("SELECT * FROM what_if_scenarios WHERE id = ?", (saved_id,))

    def list_what_if_scenarios(self, decision_snapshot_id: str | None = None) -> list[sqlite3.Row]:
        """List saved what-if results, optionally for one decision review."""
        if decision_snapshot_id is None:
            return self.connect().execute(
                "SELECT * FROM what_if_scenarios ORDER BY created_at DESC, id DESC"
            ).fetchall()
        return self.connect().execute(
            "SELECT * FROM what_if_scenarios WHERE decision_snapshot_id = ? ORDER BY created_at DESC, id DESC",
            (decision_snapshot_id,),
        ).fetchall()

    def create_audit_event(self, values: dict[str, Any]) -> None:
        """Append a non-secret audit event."""
        self._insert("audit_events", values)

    def list_audit_events(self) -> list[sqlite3.Row]:
        """List audit events in reverse chronological order."""
        return self.connect().execute(
            "SELECT * FROM audit_events ORDER BY created_at DESC, id DESC"
        ).fetchall()

    def _insert_decision_option(
        self, decision_id: str, option: DecisionOption, commit: bool
    ) -> None:
        values = {"decision_id": decision_id, **self._model_values(option)}
        self._insert("decision_options", values, commit=commit)

    def _insert(self, table: str, values: dict[str, Any], commit: bool = True) -> None:
        if "created_at" in values and values["created_at"] is None:
            values["created_at"] = datetime.now(timezone.utc).isoformat()
        columns = ", ".join(values)
        placeholders = ", ".join("?" for _ in values)
        conn = self.connect()
        conn.execute(
            f"INSERT INTO {table} ({columns}) VALUES ({placeholders})", tuple(values.values())
        )
        if commit:
            conn.commit()

    def _insert_or_ignore(self, table: str, values: dict[str, Any]) -> None:
        columns = ", ".join(values)
        placeholders = ", ".join("?" for _ in values)
        conn = self.connect()
        conn.execute(
            f"INSERT OR IGNORE INTO {table} ({columns}) VALUES ({placeholders})", tuple(values.values())
        )
        conn.commit()

    def _fetch_one(self, sql: str, parameters: tuple[Any, ...]) -> sqlite3.Row | None:
        return self.connect().execute(sql, parameters).fetchone()

    @staticmethod
    def _model_values(model: Any, exclude: set[str] | None = None) -> dict[str, Any]:
        """Convert a Pydantic model into SQLite-compatible scalar values."""
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
        import json

        return json.dumps(values)

    @staticmethod
    def _parse_json_list(value: str) -> list[str]:
        import json

        return json.loads(value)
