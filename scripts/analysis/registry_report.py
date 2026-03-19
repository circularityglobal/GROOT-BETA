#!/usr/bin/env python3
"""
Contract registry report.
Shows public vs private contracts, SDK counts, chain distribution, and most-starred projects.

Usage:
    python scripts/analysis/registry_report.py
"""

import json
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))))

SCRIPT_META = {
    "name": "registry_report",
    "description": "Contract registry: public/private counts, SDKs, chain distribution, top starred",
    "category": "analysis",
    "requires_admin": False,
}


def main():
    from api.database import init_databases, create_public_session
    from sqlalchemy import func as sqlfunc

    init_databases()
    db = create_public_session()

    try:
        print("=== Contract Registry Report ===\n")

        # ── Registry Projects ────────────────────────────────────────
        try:
            from api.models.registry import RegistryProject, RegistryABI, RegistrySDK, ExecutionLogic

            total = db.query(RegistryProject).count()
            active = db.query(RegistryProject).filter(RegistryProject.is_active == True).count()  # noqa
            public = db.query(RegistryProject).filter(RegistryProject.visibility == "public").count()
            private = db.query(RegistryProject).filter(RegistryProject.visibility == "private").count()

            print(f"--- Registry Projects ---")
            print(f"  Total: {total} ({active} active)")
            print(f"  Public: {public}")
            print(f"  Private: {private}")

            # ABIs and SDKs
            abi_count = db.query(RegistryABI).count()
            sdk_count = db.query(RegistrySDK).count()
            logic_count = db.query(ExecutionLogic).count()
            print(f"  ABIs: {abi_count}")
            print(f"  SDKs: {sdk_count}")
            print(f"  Execution logic entries: {logic_count}")

            # Chain distribution
            print(f"\n--- By Chain ---")
            chains = db.query(
                RegistryProject.chain,
                sqlfunc.count().label("count"),
            ).group_by(RegistryProject.chain).order_by(sqlfunc.count().desc()).all()

            for ch in chains:
                print(f"  {ch.chain:<20} {ch.count:>6}")

            # Category distribution
            print(f"\n--- By Category ---")
            cats = db.query(
                RegistryProject.category,
                sqlfunc.count().label("count"),
            ).group_by(RegistryProject.category).order_by(sqlfunc.count().desc()).all()

            for cat in cats:
                print(f"  {cat.category:<20} {cat.count:>6}")

            # Top starred
            top = db.query(RegistryProject).filter(
                RegistryProject.stars_count > 0,
            ).order_by(RegistryProject.stars_count.desc()).limit(10).all()

            if top:
                print(f"\n--- Most Starred ---")
                for p in top:
                    print(f"  {p.slug:<40} {p.stars_count:>4} stars")

        except ImportError:
            print("  Registry models not available")

        # ── GROOT Brain (User Contract Repos) ────────────────────────
        try:
            from api.models.brain import UserRepository, ContractRepo, SDKDefinition

            repos = db.query(UserRepository).count()
            contracts = db.query(ContractRepo).filter(ContractRepo.is_active == True).count()  # noqa
            public_contracts = db.query(ContractRepo).filter(
                ContractRepo.is_public == True,  # noqa
                ContractRepo.is_active == True,  # noqa
            ).count()
            sdks = db.query(SDKDefinition).count()
            public_sdks = db.query(SDKDefinition).filter(SDKDefinition.is_public == True).count()  # noqa

            print(f"\n--- GROOT Brain (User Contracts) ---")
            print(f"  User repositories: {repos}")
            print(f"  Contracts: {contracts} ({public_contracts} public)")
            print(f"  SDKs generated: {sdks} ({public_sdks} public)")

            # Chain distribution for user contracts
            user_chains = db.query(
                ContractRepo.chain,
                sqlfunc.count().label("count"),
            ).filter(
                ContractRepo.is_active == True,  # noqa
            ).group_by(ContractRepo.chain).order_by(sqlfunc.count().desc()).all()

            if user_chains:
                print(f"\n  User contracts by chain:")
                for ch in user_chains:
                    print(f"    {ch.chain:<20} {ch.count:>6}")

            # Language distribution
            langs = db.query(
                ContractRepo.language,
                sqlfunc.count().label("count"),
            ).filter(
                ContractRepo.is_active == True,  # noqa
            ).group_by(ContractRepo.language).order_by(sqlfunc.count().desc()).all()

            if langs:
                print(f"\n  User contracts by language:")
                for lang in langs:
                    print(f"    {lang.language:<20} {lang.count:>6}")

        except ImportError:
            print("  Brain models not available")

    except Exception as e:
        print(f"ERROR: {e}")
        sys.exit(1)
    finally:
        db.close()


if __name__ == "__main__":
    main()
