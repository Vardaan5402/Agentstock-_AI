"""Centralized Entitlement, Subscription Gating & Metered Usage Service."""
from datetime import datetime, timezone
from typing import Optional, Tuple, Dict, Any
from uuid import uuid4
from database.database import Database
from models.subscription import UserSubscription, SubscriptionStatus, PlanTier, BillingCycle, UsageRecord
from core.config import get_plan_pricing, is_demo_mode


class SubscriptionService:
    """Centralized server-side access control evaluating user entitlements and usage limits."""

    def __init__(self, database: Database):
        self.database = database

    def get_user_subscription(self, user_id: Optional[str]) -> UserSubscription:
        """Retrieve user's active subscription, or return default Free tier."""
        if not user_id:
            return UserSubscription(
                id=uuid4().hex,
                user_id="anonymous",
                plan_name=PlanTier.FREE.value,
                subscription_status=SubscriptionStatus.ACTIVE.value,
            )

        # Internal developer demo mode bypass if explicitly configured
        if is_demo_mode() and user_id.startswith("dev_test_"):
            return UserSubscription(
                id=f"sub_{user_id}",
                user_id=user_id,
                plan_name=PlanTier.ENTERPRISE.value,
                subscription_status=SubscriptionStatus.ACTIVE.value,
            )

        sub = self.database.get_subscription_by_user_id(user_id)
        if sub and sub.is_active:
            return sub

        return UserSubscription(id=uuid4().hex, user_id=user_id, plan_name=PlanTier.FREE.value)

    def is_subscription_active(self, user_id: Optional[str]) -> bool:
        """Check if user has an active, paid subscription."""
        sub = self.get_user_subscription(user_id)
        return sub.is_active and sub.plan_name.upper() != PlanTier.FREE.value

    def get_user_plan(self, user_id: Optional[str]) -> str:
        """Get current plan tier name."""
        sub = self.get_user_subscription(user_id)
        return sub.plan_name.upper()

    def has_feature(self, user_id: Optional[str], feature_name: str) -> bool:
        """Check if user has entitlement for specific platform feature."""
        plan = self.get_user_plan(user_id)

        if plan == PlanTier.ENTERPRISE.value:
            return True

        feature_matrix = {
            "deterministic_simulation": {PlanTier.FREE.value, PlanTier.STARTER.value, PlanTier.PROFESSIONAL.value, PlanTier.ENTERPRISE.value},
            "gemini_reasoning": {PlanTier.FREE.value, PlanTier.STARTER.value, PlanTier.PROFESSIONAL.value, PlanTier.ENTERPRISE.value},
            "supplier_dispatch_suite": {PlanTier.FREE.value, PlanTier.STARTER.value, PlanTier.PROFESSIONAL.value, PlanTier.ENTERPRISE.value},
            "what_if_analysis": {PlanTier.FREE.value, PlanTier.STARTER.value, PlanTier.PROFESSIONAL.value, PlanTier.ENTERPRISE.value},
            "audit_trail": {PlanTier.FREE.value, PlanTier.STARTER.value, PlanTier.PROFESSIONAL.value, PlanTier.ENTERPRISE.value},
            "voice_inventory": {PlanTier.FREE.value, PlanTier.STARTER.value, PlanTier.PROFESSIONAL.value, PlanTier.ENTERPRISE.value},
            "vision_inventory_scan": {PlanTier.FREE.value, PlanTier.STARTER.value, PlanTier.PROFESSIONAL.value, PlanTier.ENTERPRISE.value},
            "inventory_reconciliation": {PlanTier.STARTER.value, PlanTier.PROFESSIONAL.value, PlanTier.ENTERPRISE.value},
            "unlimited_decisions": {PlanTier.PROFESSIONAL.value, PlanTier.ENTERPRISE.value},
            "custom_policy_engine": {PlanTier.ENTERPRISE.value},
            "dedicated_support": {PlanTier.PROFESSIONAL.value, PlanTier.ENTERPRISE.value},
        }

        allowed_plans = feature_matrix.get(feature_name, {PlanTier.ENTERPRISE.value})
        return plan in allowed_plans

    def _require_paid(self, user_id: Optional[str], feature: str) -> Tuple[bool, str]:
        if self.is_subscription_active(user_id):
            return True, f"{feature} permitted."
        return False, "Subscription Required. Choose a paid AgentStock AI plan to access this workspace."

    def can_create_decision(self, user_id: Optional[str]) -> Tuple[bool, str]:
        return self._require_paid(user_id, "Decision analysis")

    def can_run_what_if(self, user_id: Optional[str]) -> Tuple[bool, str]:
        return self._require_paid(user_id, "What-If simulation")

    def can_use_copilot(self, user_id: Optional[str]) -> Tuple[bool, str]:
        return self._require_paid(user_id, "Gemini Copilot")

    def can_use_voice_inventory(self, user_id: Optional[str]) -> Tuple[bool, str]:
        return self._require_paid(user_id, "Voice inventory")

    def can_use_image_scan(self, user_id: Optional[str]) -> Tuple[bool, str]:
        return self._require_paid(user_id, "Visual scanner")

    def can_use_reconciliation(self, user_id: Optional[str]) -> Tuple[bool, str]:
        plan = self.get_user_plan(user_id)
        if plan in {PlanTier.STARTER.value, PlanTier.PROFESSIONAL.value, PlanTier.ENTERPRISE.value}:
            return True, f"Inventory reconciliation active for {plan} tier."
        return False, "Subscription Required. Choose a paid AgentStock AI plan to use inventory reconciliation."

    def can_use_advanced_features(self, user_id: Optional[str]) -> Tuple[bool, str]:
        plan = self.get_user_plan(user_id)
        if plan in {PlanTier.PROFESSIONAL.value, PlanTier.ENTERPRISE.value}:
            return True, f"Full {plan} access active."
        return False, "This feature requires a Professional or Enterprise plan."

    def get_voice_limits(self, user_id: Optional[str]) -> dict:
        """Get monthly voice command allowances for user tier."""
        plan = self.get_user_plan(user_id)
        limits = {
            PlanTier.FREE.value: {"monthly_commands": 25, "tier": "Free Tier"},
            PlanTier.STARTER.value: {"monthly_commands": 250, "tier": "Starter Plan"},
            PlanTier.PROFESSIONAL.value: {"monthly_commands": 1500, "tier": "Pro Plan"},
            PlanTier.ENTERPRISE.value: {"monthly_commands": 99999, "tier": "Enterprise Plan (Unlimited)"},
        }
        return limits.get(plan, limits[PlanTier.FREE.value])

    def get_vision_limits(self, user_id: Optional[str]) -> dict:
        """Get monthly vision image scan allowances for user tier."""
        plan = self.get_user_plan(user_id)
        limits = {
            PlanTier.FREE.value: {"monthly_scans": 10, "tier": "Free Tier"},
            PlanTier.STARTER.value: {"monthly_scans": 100, "tier": "Starter Plan"},
            PlanTier.PROFESSIONAL.value: {"monthly_scans": 1000, "tier": "Pro Plan"},
            PlanTier.ENTERPRISE.value: {"monthly_scans": 99999, "tier": "Enterprise Plan (Unlimited)"},
        }
        return limits.get(plan, limits[PlanTier.FREE.value])

    def get_usage(self, user_id: Optional[str]) -> UsageRecord:
        """Retrieve or initialize current month's usage record."""
        current_month = datetime.now(timezone.utc).strftime("%Y-%m")
        uid = user_id or "anonymous"
        usage = self.database.get_usage_record(uid, current_month)
        if usage:
            return usage

        new_rec = UsageRecord(
            id=f"usg_{uid[:8]}_{current_month.replace('-', '')}",
            user_id=uid,
            period_month=current_month,
        )
        self.database.save_usage_record(new_rec)
        return new_rec

    def check_and_increment_usage(
        self, user_id: Optional[str], metric: str
    ) -> Tuple[bool, str, int, int]:
        """Check if user has remaining allowance for a metered operation and increment count."""
        if not user_id:
            return False, "Please sign in and subscribe to use this feature.", 0, 0

        plan = self.get_user_plan(user_id)
        pricing = get_plan_pricing(plan)
        limits_map = {
            "camera_scans": pricing.get("camera_scans", 100),
            "voice_queries": pricing.get("voice_queries", 250),
            "ai_decisions": pricing.get("ai_decisions", 500),
            "documents_analyzed": pricing.get("documents_analyzed", 50),
        }
        limit = limits_map.get(metric, 100)

        usage = self.get_usage(user_id)
        current_used = getattr(usage, metric, 0)

        if current_used >= limit:
            return (
                False,
                f"You have reached your {plan} plan limit of {limit} {metric.replace('_', ' ')} this month.",
                current_used,
                limit,
            )

        setattr(usage, metric, current_used + 1)
        usage.updated_at = datetime.now(timezone.utc).isoformat()
        self.database.save_usage_record(usage)
        return True, "Operation permitted.", current_used + 1, limit

    def can_access_dashboard(self, user_id: Optional[str]) -> Tuple[bool, str]:
        if not user_id:
            return False, "Authentication required to access workspace dashboard."
        return self._require_paid(user_id, "Workspace access")
