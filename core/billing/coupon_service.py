"""Coupon and Promotional Code Verification Service for AgentStock AI."""
from datetime import datetime, timezone
from typing import Optional, Tuple, Dict, Any
from models.security import Coupon, CouponRedemption
from models.subscription import PlanTier


class CouponService:
    """Server-side coupon validation and discount calculation engine."""

    DEFAULT_COUPONS = {
        "LAUNCH50": {
            "id": "cpn_launch50",
            "code": "LAUNCH50",
            "discount_type": "PERCENTAGE",
            "discount_value": 50.0,
            "plan_tier": None,
            "max_redemptions": 500,
            "is_active": True,
            "campaign": "Public Commercial Launch",
        },
        "SAVE20": {
            "id": "cpn_save20",
            "code": "SAVE20",
            "discount_type": "PERCENTAGE",
            "discount_value": 20.0,
            "plan_tier": None,
            "max_redemptions": 1000,
            "is_active": True,
            "campaign": "General Promotion",
        },
        "STARTER100": {
            "id": "cpn_starter100",
            "code": "STARTER100",
            "discount_type": "FIXED",
            "discount_value": 5.0,
            "plan_tier": PlanTier.STARTER.value,
            "max_redemptions": 200,
            "is_active": True,
            "campaign": "Starter Plan Kickoff",
        },
    }

    @classmethod
    def get_coupon(cls, code: str) -> Optional[Dict[str, Any]]:
        """Return a copy of a configured coupon without exposing mutable state."""
        coupon = cls.DEFAULT_COUPONS.get((code or "").strip().upper())
        return dict(coupon) if coupon else None

    @classmethod
    def validate_coupon(
        cls,
        code: str,
        plan_name: str,
        user_id: Optional[str] = None,
        already_redeemed: bool = False,
    ) -> Tuple[bool, str, float]:
        """
        Validate coupon eligibility server-side.
        Returns:
            (is_valid: bool, message: str, discount_amount: float)
        """
        clean_code = (code or "").strip().upper()
        if not clean_code:
            return False, "Please enter a coupon code.", 0.0

        coupon_data = cls.get_coupon(clean_code)
        if not coupon_data:
            return False, f"Coupon code '{clean_code}' is invalid or has expired.", 0.0

        if not coupon_data["is_active"]:
            return False, "This coupon code is no longer active.", 0.0

        # Plan Tier restriction check
        target_tier = coupon_data.get("plan_tier")
        if target_tier and target_tier.upper() != plan_name.upper():
            return False, f"Coupon '{clean_code}' is only valid for {target_tier} plan.", 0.0

        # Per-user redemption check
        if already_redeemed:
            return False, "You have already redeemed this promotional code.", 0.0

        return True, f"Coupon '{clean_code}' applied successfully!", coupon_data["discount_value"]

    @classmethod
    def calculate_discounted_price(
        cls,
        base_price: float,
        discount_type: str,
        discount_value: float,
    ) -> float:
        """Calculate final price after coupon discount."""
        if discount_type == "PERCENTAGE":
            discount = base_price * (discount_value / 100.0)
        else:
            discount = discount_value

        return max(0.0, round(base_price - discount, 2))
