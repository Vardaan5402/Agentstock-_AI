"""A small SQLite repository for AgentStock's structured business memory."""

import sqlite3
from datetime import datetime
from enum import Enum
from pathlib import Path
from typing import Any

from models.business import Business
from models.decision import Decision, DecisionOption, Outcome
from models.inventory import Product, Purchase, SalesRecord
from models.policy import Policy
from models.supplier import Supplier, SupplierProduct


class Database:
    """Persist validated models using SQLite without introducing an ORM."""

    def __init__(self, database_path: str | Path = "agentstock.db") -> None:
        self.database_path = str(database_path)
        self.connection: sqlite3.Connection | None = None

    def connect(self) -> sqlite3.Connection:
        """Open the database connection and enable foreign-key enforcement."""
        if self.connection is None:
            self.connection = sqlite3.connect(self.database_path)
            self.connection.row_factory = sqlite3.Row
            self.connection.execute("PRAGMA foreign_keys = ON")
        return self.connection

    def close(self) -> None:
        """Close the open connection, if any."""
        if self.connection is not None:
            self.connection.close()
            self.connection = None

    def initialize(self) -> None:
        """Create the Milestone 1 tables when they do not already exist."""
        connection = self.connect()
        connection.executescript(
            """
            CREATE TABLE IF NOT EXISTS businesses (
                id TEXT PRIMARY KEY,
                name TEXT NOT NULL,
                country TEXT NOT NULL,
                currency TEXT NOT NULL,
                industry TEXT NOT NULL,
                inventory_budget REAL NOT NULL CHECK (inventory_budget >= 0),
                created_at TEXT NOT NULL
            );

            CREATE TABLE IF NOT EXISTS products (
                id TEXT PRIMARY KEY,
                business_id TEXT NOT NULL,
                sku TEXT NOT NULL,
                name TEXT NOT NULL,
                current_stock INTEGER NOT NULL CHECK (current_stock >= 0),
                unit_cost REAL NOT NULL CHECK (unit_cost >= 0),
                daily_demand REAL NOT NULL CHECK (daily_demand >= 0),
                safety_stock INTEGER NOT NULL DEFAULT 0 CHECK (safety_stock >= 0),
                FOREIGN KEY (business_id) REFERENCES businesses(id),
                UNIQUE (business_id, sku)
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
                email TEXT,
                lead_time_days REAL NOT NULL CHECK (lead_time_days >= 0),
                reliability_score REAL NOT NULL DEFAULT 0.5
                    CHECK (reliability_score >= 0 AND reliability_score <= 1),
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
                created_at TEXT NOT NULL,
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
                created_at TEXT NOT NULL,
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
            """
        )
        connection.commit()

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

    def _insert_decision_option(
        self, decision_id: str, option: DecisionOption, commit: bool
    ) -> None:
        values = {"decision_id": decision_id, **self._model_values(option)}
        self._insert("decision_options", values, commit=commit)

    def _insert(self, table: str, values: dict[str, Any], commit: bool = True) -> None:
        columns = ", ".join(values)
        placeholders = ", ".join("?" for _ in values)
        self.connect().execute(
            f"INSERT INTO {table} ({columns}) VALUES ({placeholders})", tuple(values.values())
        )
        if commit:
            self.connect().commit()

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
