"""CLI helper: mint a fresh regulator API key.

Usage:
    python3 -m backend.issue_regulator_key --name "Dr. Jane Smith" --organization "EFRAG" --ttl-days 90
"""
import asyncio
import os
import argparse
from motor.motor_asyncio import AsyncIOMotorClient
from dotenv import load_dotenv
from pathlib import Path
from regulator_sandbox import issue_key

load_dotenv(Path(__file__).parent / ".env")


async def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--name", required=True, help="Contact name (auditor/analyst)")
    ap.add_argument("--organization", required=True, help="Regulator entity — e.g. EFRAG, ESMA, SEC")
    ap.add_argument("--ttl-days", type=int, default=30)
    args = ap.parse_args()

    client = AsyncIOMotorClient(os.environ["MONGO_URL"])
    db = client[os.environ["DB_NAME"]]
    raw = await issue_key(db, name=args.name, organization=args.organization, ttl_days=args.ttl_days)
    print("=" * 78)
    print("REGULATOR KEY ISSUED — DISPLAY ONCE, STORE SECURELY")
    print(f"  organization : {args.organization}")
    print(f"  contact      : {args.name}")
    print(f"  ttl_days     : {args.ttl_days}")
    print(f"  key          : {raw}")
    print("=" * 78)
    print("Usage: curl -H 'X-Regulator-Key: <key>' <backend_url>/api/regulator/sandbox/<endpoint>")


if __name__ == "__main__":
    asyncio.run(main())
