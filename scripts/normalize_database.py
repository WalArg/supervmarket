#!/usr/bin/env python3
"""scripts/normalize_database.py

CLI Runner for SuperVmarket Global Normalization & Entity Resolution (Milestone 2 - R2).
Usage:
    python scripts/normalize_database.py [--db-path supervmarket.db] [--dry-run] [--verbose]
"""

import argparse
import json
import logging
import os
import sys
import time

# Ensure project root in sys.path
ROOT_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if ROOT_DIR not in sys.path:
    sys.path.insert(0, ROOT_DIR)

from api._lib.catalog_normalizer import normalize_catalog


def setup_logging(verbose: bool = False):
    level = logging.DEBUG if verbose else logging.INFO
    logging.basicConfig(
        level=level,
        format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
        datefmt="%Y-%m-%d %H:%M:%S",
    )


def main():
    parser = argparse.ArgumentParser(description="Normalize database categories and resolve entities.")
    parser.add_argument("--db-path", default="supervmarket.db", help="Path to SQLite database")
    parser.add_argument("--dry-run", action="store_true", help="Run without committing to SQLite")
    parser.add_argument("--verbose", action="store_true", help="Enable verbose log output")
    args = parser.parse_args()

    setup_logging(args.verbose)
    logger = logging.getLogger("supervmarket.cli.normalize")
    logger.info(f"Starting catalog normalization on database: {args.db_path} (dry_run={args.dry_run})")

    try:
        summary = normalize_catalog(db_path=args.db_path, dry_run=args.dry_run)

        logger.info(f"Normalization completed successfully in {summary['duration_seconds']}s")
        logger.info(f"Total Products: {summary['total_products']}")
        logger.info(f"Categories Updated: {summary['categories_updated']}")
        logger.info(f"NULL Categories Remaining: {summary['null_categories_remaining']}")
        logger.info(f"ER Hardware Models Indexed: {summary['entity_resolution']['hardware_models_indexed']}")
        logger.info(f"ER Hardware Links Repointed: {summary['entity_resolution']['hardware_links_repointed']}")
        logger.info(f"ER Grocery Keys Indexed: {summary['entity_resolution']['grocery_keys_indexed']}")
        logger.info(f"ER Grocery Links Repointed: {summary['entity_resolution']['grocery_links_repointed']}")
        logger.info(f"ER Total Offers Repointed: {summary['entity_resolution']['total_repointed']}")
        logger.info(f"ER Constraint Conflicts Resolved: {summary['entity_resolution']['conflicts_resolved']}")
        logger.info(f"ER Cleaned Product Shells: {summary['entity_resolution']['cleaned_shells']}")
        logger.info(f"ER Price Guard Rejections: {summary['entity_resolution']['price_guard_rejections']}")

        print("\n=======================================================")
        print("     SUPERVMARKET MILESTONE 2: CANONICAL TAXONOMY      ")
        print("=======================================================")
        for cat, count in sorted(summary["category_breakdown"].items(), key=lambda x: x[1], reverse=True):
            pct = (count / summary["total_products"]) * 100.0 if summary["total_products"] > 0 else 0.0
            print(f"  {cat:<26}: {count:>6}  ({pct:5.2f}%)")
        print("=======================================================\n")

        if summary["null_categories_remaining"] > 0:
            logger.error(f"FAILURE: {summary['null_categories_remaining']} NULL categories remain in productos!")
            sys.exit(1)

        sys.exit(0)
    except Exception as e:
        logger.exception(f"Fatal error during database normalization: {e}")
        sys.exit(1)


if __name__ == "__main__":
    main()
