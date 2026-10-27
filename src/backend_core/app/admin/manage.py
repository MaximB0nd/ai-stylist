"""Grant or revoke admin access for an existing account, using local CLI only."""
import argparse
import asyncio
from sqlalchemy import select
from app.db.session import AsyncSessionLocal, engine
from app.models.user import User


async def change_role(email, revoke=False):
    try:
        async with AsyncSessionLocal() as session:
            user = await session.scalar(select(User).where(User.email == email.strip().lower()))
            if user is None: raise ValueError("Account not found; register it first")
            if not user.is_active and not revoke: raise ValueError("Account is inactive")
            user.is_admin = not revoke
            await session.commit()
    finally:
        await engine.dispose()


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--email", required=True)
    parser.add_argument("--revoke", action="store_true")
    args = parser.parse_args()
    try:
        asyncio.run(change_role(args.email, args.revoke))
    except ValueError as exc:
        parser.exit(2, str(exc) + "\n")
    print("Administrator role updated")
