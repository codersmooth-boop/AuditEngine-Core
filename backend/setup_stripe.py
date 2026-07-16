"""Idempotent Stripe catalog setup for AuditEngine.

Creates two prices under the AuditEngine Professional product:
- professional_monthly · €49/mo
- annual_yearly       · €490/yr
"""
import os
import stripe
from dotenv import load_dotenv
from pathlib import Path

load_dotenv(Path(__file__).parent / ".env")
stripe.api_key = os.environ["STRIPE_SECRET_KEY"]

CATALOG = [
    {
        "emergent_product_id": "auditengine_professional",
        "name": "AuditEngine Professional",
        "description": "Unlimited ESG compliance audits, Merkle-Root snapshots, Board Brief PDFs, Trust Anchor microsite, Regulator Sandbox access.",
        "tax_code": "txcd_10103001",  # SaaS
        "prices": [
            {"lookup_key": "professional_monthly", "amount": 4900, "currency": "eur", "interval": "month"},
            {"lookup_key": "annual_yearly",        "amount": 49000, "currency": "eur", "interval": "year"},
        ],
    },
]


def ensure_tax_settings():
    s = stripe.tax.Settings.retrieve()
    if s.head_office and getattr(s.head_office, "address", None):
        return
    stripe.tax.Settings.modify(
        head_office={"address": {
            "country": "FI", "line1": "Aleksanterinkatu 1", "city": "Helsinki",
            "postal_code": "00100",
        }},
        defaults={"tax_behavior": "exclusive"},
    )


def get_or_create_product(entry):
    for p in stripe.Product.list(active=True).auto_paging_iter():
        if p.to_dict().get("metadata", {}).get("emergent_product_id") == entry["emergent_product_id"]:
            return p
    return stripe.Product.create(
        name=entry["name"],
        description=entry.get("description"),
        tax_code=entry.get("tax_code"),
        metadata={"managed_by": "emergent", "emergent_product_id": entry["emergent_product_id"]},
    )


def upsert_price(product, spec):
    existing = stripe.Price.list(lookup_keys=[spec["lookup_key"]], active=True, limit=1).data
    if existing:
        px = existing[0]
        if px.unit_amount == spec["amount"] and px.currency == spec["currency"]:
            print(f"  · price {spec['lookup_key']} already correct → {px.id}")
            return px
        stripe.Price.modify(px.id, active=False)
        print(f"  · deactivated stale price {px.id}")
    kwargs = dict(
        product=product.id,
        unit_amount=spec["amount"],
        currency=spec["currency"],
        lookup_key=spec["lookup_key"],
        transfer_lookup_key=True,
    )
    if spec.get("interval"):
        kwargs["recurring"] = {"interval": spec["interval"]}
    px = stripe.Price.create(**kwargs)
    print(f"  · created price {spec['lookup_key']} → {px.id}")
    return px


def main():
    print("→ ensuring tax settings")
    try:
        ensure_tax_settings()
    except Exception as e:
        print(f"  (tax settings skipped: {e})")
    for entry in CATALOG:
        print(f"→ product: {entry['name']}")
        product = get_or_create_product(entry)
        print(f"  product_id = {product.id}")
        for spec in entry["prices"]:
            upsert_price(product, spec)
    print("done.")


if __name__ == "__main__":
    main()
