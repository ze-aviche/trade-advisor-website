"""
Stripe subscription management for SaaS billing.

Required environment variables:
  STRIPE_SECRET_KEY       - sk_test_... or sk_live_...
  STRIPE_WEBHOOK_SECRET   - whsec_... (from Stripe dashboard webhook config)
  STRIPE_PRICE_BEGINNER   - price_... for $5/mo Beginner plan
  STRIPE_PRICE_ADVANCED   - price_... for $10/mo Advanced plan
  STRIPE_PRICE_YOGI       - price_... for $25/mo Yogi plan
"""
import os
import stripe
import logging
from typing import Optional

logger = logging.getLogger(__name__)

# Tier → Stripe Price ID
TIER_PRICE_IDS: dict[str, Optional[str]] = {
    'beginner': os.getenv('STRIPE_PRICE_BEGINNER'),
    'advanced': os.getenv('STRIPE_PRICE_ADVANCED'),
    'yogi':     os.getenv('STRIPE_PRICE_YOGI'),
}

# Reverse map built at import time (re-built in init so env vars are resolved)
_PRICE_TIER_MAP: dict[str, str] = {}


class StripeManager:
    def __init__(self):
        self.secret_key = os.getenv('STRIPE_SECRET_KEY')
        if not self.secret_key:
            raise ValueError("STRIPE_SECRET_KEY environment variable is required")

        stripe.api_key = self.secret_key
        self.webhook_secret = os.getenv('STRIPE_WEBHOOK_SECRET', '')

        # Rebuild reverse map now that env vars are confirmed loaded
        global _PRICE_TIER_MAP
        _PRICE_TIER_MAP = {v: k for k, v in TIER_PRICE_IDS.items() if v}

        logger.info("Stripe manager initialized (mode: %s)",
                    "LIVE" if self.secret_key.startswith("sk_live") else "TEST")

    # ── Customer ────────────────────────────────────────────────────────────

    def get_or_create_customer(self, user_id: int, email: str, username: str,
                                existing_id: Optional[str] = None) -> dict:
        if existing_id:
            try:
                customer = stripe.Customer.retrieve(existing_id)
                if not getattr(customer, 'deleted', False):
                    return customer
            except stripe.error.InvalidRequestError:
                pass
        customer = stripe.Customer.create(
            email=email,
            name=username,
            metadata={'user_id': str(user_id)}
        )
        logger.info("Created Stripe customer %s for user %s", customer['id'], user_id)
        return customer

    # ── Checkout ────────────────────────────────────────────────────────────

    def create_checkout_session(self, user_id: int, email: str, username: str,
                                 tier: str, success_url: str, cancel_url: str,
                                 existing_customer_id: Optional[str] = None) -> dict:
        price_id = TIER_PRICE_IDS.get(tier)
        if not price_id:
            raise ValueError(
                f"No Stripe price configured for tier '{tier}'. "
                f"Set STRIPE_PRICE_{tier.upper()} in your environment."
            )
        customer = self.get_or_create_customer(user_id, email, username, existing_customer_id)
        session = stripe.checkout.Session.create(
            customer=customer['id'],
            mode='subscription',
            line_items=[{'price': price_id, 'quantity': 1}],
            success_url=success_url,
            cancel_url=cancel_url,
            allow_promotion_codes=True,
            metadata={'user_id': str(user_id), 'tier': tier},
            subscription_data={
                'metadata': {'user_id': str(user_id), 'tier': tier}
            },
        )
        return {'id': session['id'], 'url': session['url'], 'customer_id': customer['id']}

    # ── Customer Portal ─────────────────────────────────────────────────────

    def create_portal_session(self, customer_id: str, return_url: str) -> dict:
        session = stripe.billing_portal.Session.create(
            customer=customer_id,
            return_url=return_url,
        )
        return {'url': session['url']}

    # ── Webhooks ────────────────────────────────────────────────────────────

    def construct_webhook_event(self, payload: bytes, sig_header: str):
        return stripe.Webhook.construct_event(payload, sig_header, self.webhook_secret)

    # ── Helpers ─────────────────────────────────────────────────────────────

    def tier_from_subscription(self, subscription) -> Optional[str]:
        """Map a subscription's price back to an internal tier name."""
        for item in subscription.get('items', {}).get('data', []):
            tier = _PRICE_TIER_MAP.get(item['price']['id'])
            if tier:
                return tier
        # Fall back to metadata set at checkout
        return subscription.get('metadata', {}).get('tier')
