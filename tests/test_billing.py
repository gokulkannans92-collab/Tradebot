import pytest
import sys
import os

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from api.models.saas_models import (
    get_default_plans, SubscriptionTier
)
from api.middleware.tenant import (
    get_tier_limits, check_feature_flag
)


class TestBillingPlans:
    def test_get_default_plans(self):
        plans = get_default_plans()
        assert len(plans) == 3
        assert plans[0]["tier"] == SubscriptionTier.FREE
        assert plans[1]["tier"] == SubscriptionTier.PRO
        assert plans[2]["tier"] == SubscriptionTier.ELITE

    def test_free_planPricing(self):
        plans = get_default_plans()
        free_plan = next(p for p in plans if p["tier"] == SubscriptionTier.FREE)
        assert free_plan["price_monthly_inr"] == 0
        assert free_plan["max_trades_per_day"] == 2

    def test_pro_planPricing(self):
        plans = get_default_plans()
        pro_plan = next(p for p in plans if p["tier"] == SubscriptionTier.PRO)
        assert pro_plan["price_monthly_inr"] == 3999
        assert pro_plan["max_trades_per_day"] == 10
        assert pro_plan["live_trading"] is True

    def test_elite_planPricing(self):
        plans = get_default_plans()
        elite_plan = next(p for p in plans if p["tier"] == SubscriptionTier.ELITE)
        assert elite_plan["price_monthly_inr"] == 11999
        assert elite_plan["api_access"] is True
        assert elite_plan["priority_support"] is True

    def test_plan_features(self):
        plans = get_default_plans()
        for plan in plans:
            assert "features" in plan
            assert "name" in plan
            assert "description" in plan


class TestTierLimits:
    def test_free_tier_limits(self):
        limits = get_tier_limits(SubscriptionTier.FREE)
        assert limits["max_trades_per_day"] == 2
        assert limits["max_api_calls_per_day"] == 0
        assert "paper_trading" in limits["features"]

    def test_pro_tier_limits(self):
        limits = get_tier_limits(SubscriptionTier.PRO)
        assert limits["max_trades_per_day"] == 10
        assert limits["max_api_calls_per_day"] == 100
        assert "live_trading" in limits["features"]

    def test_elite_tier_limits(self):
        limits = get_tier_limits(SubscriptionTier.ELITE)
        assert limits["max_trades_per_day"] == 999
        assert limits["max_api_calls_per_day"] == 999999
        assert "api_access" in limits["features"]


class TestFeatureFlags:
    def test_paper_trading_all_tiers(self):
        assert check_feature_flag(SubscriptionTier.FREE, "paper_trading") is True
        assert check_feature_flag(SubscriptionTier.PRO, "paper_trading") is True
        assert check_feature_flag(SubscriptionTier.ELITE, "paper_trading") is True

    def test_live_trading_pro_and_above(self):
        assert check_feature_flag(SubscriptionTier.FREE, "live_trading") is False
        assert check_feature_flag(SubscriptionTier.PRO, "live_trading") is True
        assert check_feature_flag(SubscriptionTier.ELITE, "live_trading") is True

    def test_api_access_elite_only(self):
        assert check_feature_flag(SubscriptionTier.FREE, "api_access") is False
        assert check_feature_flag(SubscriptionTier.PRO, "api_access") is False
        assert check_feature_flag(SubscriptionTier.ELITE, "api_access") is True

    def test_unknown_feature(self):
        assert check_feature_flag(SubscriptionTier.FREE, "unknown_feature") is False


class TestSubscriptionTiers:
    def test_tier_enum_values(self):
        assert SubscriptionTier.FREE.value == "free"
        assert SubscriptionTier.PRO.value == "pro"
        assert SubscriptionTier.ELITE.value == "elite"
