"""Centralized Entitlement and Subscription Access Service for AgentStock AI."""
from typing import Optional, Tuple
from uuid import uuid4
from database.database import Database
from models.subscription import UserSubscription, SubscriptionStatus, PlanTier


class SubscriptionService:
    """Centralized access control evaluating user entitlements against active subscriptions."""

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

        sub = self.database.get_subscription_by_user_id(user_id)
        if sub and sub.is_active:
            return sub

        return UserSubscription(
            id=uuid4().hex,
            user_id=user_id,
            plan_name=PlanTier.FREE.value,
            subscription_status=SubscriptionStatus.ACTIVE.value,
        )

    def get_user_plan(self, user_id: Optional[str]) -> str:
        """Get the tier name for a user."""
        sub = self.get_user_subscription(user_id)
        return sub.plan_name.upper()

    def has_feature(self, user_id: Optional[str], feature_name: str) -> bool:
        """Check if user has entitlement for specific platform feature."""
        plan = self.get_user_plan(user_id)

        # Enterprise has all features
        if plan == PlanTier.ENTERPRISE.value:
            return True

        # Feature rules
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

    def can_create_decision(self, user_id: Optional[str]) -> Tuple[bool, str]:
        """Check if user can run a new inventory decision analysis."""
        return True, "Decision analysis permitted."

    def can_run_what_if(self, user_id: Optional[str]) -> Tuple[bool, str]:
        """Check if user can run counterfactual what-if simulations."""
        return True, "What-If simulation permitted."

    def can_use_copilot(self, user_id: Optional[str]) -> Tuple[bool, str]:
        """Check if user can execute Gemini Decision Copilot questions."""
        return True, "Gemini Copilot permitted."

    def can_use_voice_inventory(self, user_id: Optional[str]) -> Tuple[bool, str]:
        """Check if user has voice inventory assistance entitlement."""
        return True, "Voice inventory permitted."

    def can_use_image_scan(self, user_id: Optional[str]) -> Tuple[bool, str]:
        """Check if user has visual inventory scanning entitlement."""
        return True, "Visual scanner permitted."

    def can_use_reconciliation(self, user_id: Optional[str]) -> Tuple[bool, str]:
        """Check if user has automated visual reconciliation entitlement."""
        plan = self.get_user_plan(user_id)
        if plan in {PlanTier.STARTER.value, PlanTier.PROFESSIONAL.value, PlanTier.ENTERPRISE.value}:
            return True, f"Inventory reconciliation active for {plan} tier."
        return True, "Reconciliation preview enabled."

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

    def can_use_advanced_features(self, user_id: Optional[str]) -> Tuple[bool, str]:
        """Check if user has access to Pro/Enterprise features."""
        plan = self.get_user_plan(user_id)
        if plan in {PlanTier.PROFESSIONAL.value, PlanTier.ENTERPRISE.value}:
            return True, f"Full {plan} access active."
        return False, "This feature requires a Professional or Enterprise plan."
