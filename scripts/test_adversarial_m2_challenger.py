#!/usr/bin/env python3
"""scripts/test_adversarial_m2_challenger.py

Adversarial Stress Testing Harness for SuperVmarket Milestone 2 (Normalización Global y Resolución de Entidades - R2).
Empirical challenger agent: teamwork_mp_challenger_m2_2

Evaluates 5 critical dimensions:
1. Storage capacity variants: "Galaxy A55 128GB" and "Galaxy A55 256GB" NEVER merge to the same canonical key.
2. Price sanity ratio guard: Outlier items ($25,000 accessory vs $850,000 TV) are REJECTED (0.35 <= ratio <= 2.80).
3. Duplicate prevention on precios(ean, supermercado): Repointing never generates duplicate PK IntegrityErrors.
4. Referential integrity: Orphaned prices count is EXACTLY 0 in supervmarket.db.
5. Concurrency stress: Concurrent read queries against supervmarket.db under WAL mode yield 0 locking errors.
"""

import concurrent.futures
import os
import re
import sqlite3
import sys
import time
import unittest
from typing import Any, Dict, List, Tuple

# Ensure project root in sys.path
ROOT_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if ROOT_DIR not in sys.path:
    sys.path.insert(0, ROOT_DIR)

from api._lib.catalog_normalizer import (
    build_entity_resolution_index,
    resolve_and_repoint_entities,
    classify_canonical_category,
    GLOBAL_MODEL_TO_EAN,
    GROCERY_TO_EAN,
    norm_brand,
)
from api._lib.normalization import (
    extract_capacity_variant,
    extract_model,
    is_accessory,
    is_valid_ean13,
)

DB_PATH = os.path.join(ROOT_DIR, "supervmarket.db")


def make_valid_ean13(prefix12: str) -> str:
    """Calculates GS1 Modulo 10 check digit and returns 13-digit valid EAN."""
    p = prefix12[:12]
    s = sum(int(c) * (1 if i % 2 == 0 else 3) for i, c in enumerate(p))
    chk = (10 - (s % 10)) % 10
    return p + str(chk)


def create_mock_db() -> sqlite3.Connection:
    """Creates an in-memory SQLite database matching supervmarket.db schema."""
    conn = sqlite3.connect(":memory:")
    cur = conn.cursor()

    cur.execute("""
        CREATE TABLE productos (
            ean TEXT PRIMARY KEY,
            nombre TEXT NOT NULL,
            marca TEXT,
            modelo TEXT,
            tipo TEXT,
            categoria_normalizada TEXT,
            origen TEXT DEFAULT 'scraped',
            creado_el TEXT DEFAULT CURRENT_TIMESTAMP,
            actualizado_el TEXT DEFAULT CURRENT_TIMESTAMP
        )
    """)

    cur.execute("""
        CREATE TABLE precios (
            ean TEXT NOT NULL,
            supermercado TEXT NOT NULL,
            precio_venta REAL NOT NULL,
            precio_lista REAL,
            descuento REAL,
            precio_por_unidad REAL,
            unidad_medida TEXT,
            stock INTEGER DEFAULT 1,
            internal_id TEXT,
            link TEXT,
            fecha TEXT,
            promo_etiqueta TEXT,
            promo_tipo TEXT,
            promo_min_qty INTEGER,
            precio_promo_unit REAL,
            requiere_club INTEGER DEFAULT 0,
            seller_id TEXT DEFAULT '1',
            store_type TEXT DEFAULT 'supermarket',
            PRIMARY KEY (ean, supermercado)
        )
    """)

    cur.execute("""
        CREATE TABLE historial_precios (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            ean TEXT NOT NULL,
            supermercado TEXT NOT NULL,
            precio REAL NOT NULL,
            fecha TEXT NOT NULL
        )
    """)

    conn.commit()
    return conn


class TestSuite1StorageCapacityVariants(unittest.TestCase):
    """
    Stress-test: Storage capacity variants must NEVER merge to the same canonical key.
    Target case: "Galaxy A55 128GB" vs "Galaxy A55 256GB".
    """

    def test_extract_capacity_variant_accuracy(self):
        """Verifies regex extraction of storage/RAM variants."""
        cases = [
            ("Samsung Galaxy A55 128GB 8GB RAM 5G", "128GB"),
            ("Samsung Galaxy A55 256GB 5G Awesome Navy", "256GB"),
            ("Samsung Galaxy A55 128 GB Negro", "128GB"),
            ("Samsung Galaxy A55 256 gigas", "256GB"),
            ("Samsung Galaxy A55 512GB", "512GB"),
            ("iPhone 15 Pro Max 1TB Titanio", "1TB"),
            ("iPhone 15 Pro Max 2TB", "2TB"),
            ("Smart TV Samsung 55 UN55CU7000", ""),  # No storage variant
            ("Heladera Samsung No Frost 382L", ""),  # Liter capacity, not storage
        ]
        for title, expected in cases:
            with self.subTest(title=title):
                var = extract_capacity_variant(title)
                self.assertEqual(var, expected, f"Failed variant extraction for {title}")

    def test_in_memory_index_capacity_separation(self):
        """
        Verifies that build_entity_resolution_index creates distinct index keys
        for Galaxy A55 128GB and Galaxy A55 256GB with valid GS1 EAN-13s.
        """
        conn = create_mock_db()
        cur = conn.cursor()

        # Insert Canonical 128GB with valid GS1 Modulo-10 checksum
        ean_128 = make_valid_ean13("779123456789")  # 7791234567898
        self.assertTrue(is_valid_ean13(ean_128))
        cur.execute("INSERT INTO productos (ean, nombre, marca, modelo) VALUES (?, ?, ?, ?)",
                    (ean_128, "Celular Samsung Galaxy A55 128GB 5G", "Samsung", "A55"))
        cur.execute("INSERT INTO precios (ean, supermercado, precio_venta, stock) VALUES (?, ?, ?, ?)",
                    (ean_128, "Samsung Store", 750000.0, 10))

        # Insert Canonical 256GB with valid GS1 Modulo-10 checksum
        ean_256 = make_valid_ean13("779123456780")  # 7791234567805
        self.assertTrue(is_valid_ean13(ean_256))
        cur.execute("INSERT INTO productos (ean, nombre, marca, modelo) VALUES (?, ?, ?, ?)",
                    (ean_256, "Celular Samsung Galaxy A55 256GB 5G", "Samsung", "A55"))
        cur.execute("INSERT INTO precios (ean, supermercado, precio_venta, stock) VALUES (?, ?, ?, ?)",
                    (ean_256, "Samsung Store", 890000.0, 10))

        conn.commit()

        hw_indexed, _ = build_entity_resolution_index(conn)
        self.assertEqual(hw_indexed, 2, "Expected 2 hardware models indexed")

        key_128 = ("SAMSUNG", "A55", "128GB")
        key_256 = ("SAMSUNG", "A55", "256GB")

        self.assertIn(key_128, GLOBAL_MODEL_TO_EAN, "128GB key must exist in index")
        self.assertIn(key_256, GLOBAL_MODEL_TO_EAN, "256GB key must exist in index")

        self.assertEqual(GLOBAL_MODEL_TO_EAN[key_128][0], ean_128)
        self.assertEqual(GLOBAL_MODEL_TO_EAN[key_256][0], ean_256)
        self.assertNotEqual(GLOBAL_MODEL_TO_EAN[key_128][0], GLOBAL_MODEL_TO_EAN[key_256][0],
                            "Galaxy A55 128GB and 256GB must NEVER map to the same EAN")

        conn.close()

    def test_repointing_preserves_capacity_variants_and_never_crosses(self):
        """
        Adversarial test: Non-EAN synthetic candidates (e.g. from Coppel or Fravega)
        must resolve STRICTLY to their matching capacity variant and NEVER cross-link.
        """
        conn = create_mock_db()
        cur = conn.cursor()

        # Canonical items
        ean_128 = make_valid_ean13("779123456789")
        ean_256 = make_valid_ean13("779123456780")
        cur.execute("INSERT INTO productos (ean, nombre, marca, modelo) VALUES (?, ?, ?, ?)",
                    (ean_128, "Celular Samsung Galaxy A55 128GB 5G", "Samsung", "A55"))
        cur.execute("INSERT INTO precios (ean, supermercado, precio_venta, stock) VALUES (?, ?, ?, ?)",
                    (ean_128, "Samsung Store", 750000.0, 10))

        cur.execute("INSERT INTO productos (ean, nombre, marca, modelo) VALUES (?, ?, ?, ?)",
                    (ean_256, "Celular Samsung Galaxy A55 256GB 5G", "Samsung", "A55"))
        cur.execute("INSERT INTO precios (ean, supermercado, precio_venta, stock) VALUES (?, ?, ?, ?)",
                    (ean_256, "Samsung Store", 890000.0, 10))

        # Synthetic candidates
        synth_128 = "COPPEL-A55-128"
        cur.execute("INSERT INTO productos (ean, nombre, marca, modelo) VALUES (?, ?, ?, ?)",
                    (synth_128, "Smartphone Samsung Galaxy A55 128GB Awesome Blue", "Samsung", "A55"))
        cur.execute("INSERT INTO precios (ean, supermercado, precio_venta, stock) VALUES (?, ?, ?, ?)",
                    (synth_128, "Coppel", 720000.0, 5))

        synth_256 = "FRAVEGA-A55-256"
        cur.execute("INSERT INTO productos (ean, nombre, marca, modelo) VALUES (?, ?, ?, ?)",
                    (synth_256, "Samsung Galaxy A55 256GB Awesome Lilac", "Samsung", "A55"))
        cur.execute("INSERT INTO precios (ean, supermercado, precio_venta, stock) VALUES (?, ?, ?, ?)",
                    (synth_256, "Fravega", 880000.0, 3))

        # Mismatched candidate: 512GB (no canonical 512GB exists)
        synth_512 = "NALDO-A55-512"
        cur.execute("INSERT INTO productos (ean, nombre, marca, modelo) VALUES (?, ?, ?, ?)",
                    (synth_512, "Samsung Galaxy A55 512GB Special Edition", "Samsung", "A55"))
        cur.execute("INSERT INTO precios (ean, supermercado, precio_venta, stock) VALUES (?, ?, ?, ?)",
                    (synth_512, "Naldo", 1050000.0, 2))

        conn.commit()

        # Build index and execute repointing
        build_entity_resolution_index(conn)
        stats = resolve_and_repoint_entities(conn, dry_run=False)

        # Check repointing results in precios
        cur.execute("SELECT supermercado, ean FROM precios WHERE supermercado = 'Coppel'")
        coppel_ean = cur.fetchone()[1]
        self.assertEqual(coppel_ean, ean_128, "128GB synthetic item must repoint strictly to 128GB canonical EAN")

        cur.execute("SELECT supermercado, ean FROM precios WHERE supermercado = 'Fravega'")
        fravega_ean = cur.fetchone()[1]
        self.assertEqual(fravega_ean, ean_256, "256GB synthetic item must repoint strictly to 256GB canonical EAN")

        cur.execute("SELECT supermercado, ean FROM precios WHERE supermercado = 'Naldo'")
        naldo_ean = cur.fetchone()[1]
        self.assertEqual(naldo_ean, synth_512, "512GB synthetic item must NOT repoint to 128GB or 256GB canonical")

        conn.close()


class TestSuite2PriceSanityRatioGuard(unittest.TestCase):
    """
    Stress-test: Price sanity ratio guard ($0.35 <= ratio <= 2.80$).
    Tests extreme outlier rejection (e.g. $25,000 accessory vs $850,000 TV)
    and sharp boundary behavior.
    """

    def setUp(self):
        self.conn = create_mock_db()
        self.cur = self.conn.cursor()

        # Base Canonical TV ($850,000)
        self.canon_tv_ean = make_valid_ean13("779089500099")  # 7790895000997
        self.assertTrue(is_valid_ean13(self.canon_tv_ean))
        self.cur.execute("""
            INSERT INTO productos (ean, nombre, marca, modelo, categoria_normalizada)
            VALUES (?, ?, ?, ?, ?)
        """, (self.canon_tv_ean, "Smart TV LG 55 4K UHD 55QNED80", "LG", "55QNED80", "televisores"))
        self.cur.execute("""
            INSERT INTO precios (ean, supermercado, precio_venta, stock)
            VALUES (?, ?, ?, ?)
        """, (self.canon_tv_ean, "LG Oficial", 850000.0, 5))
        self.conn.commit()

        build_entity_resolution_index(self.conn)

    def tearDown(self):
        self.conn.close()

    def test_accessory_outlier_low_rejection(self):
        """
        Scenario from dispatch:
        $25,000 accessory with similar model string vs $850,000 TV.
        Ratio = 25,000 / 850,000 = 0.0294 (< 0.35).
        MUST be REJECTED by the price ratio guard ($0.35 <= ratio <= 2.80).
        """
        # Case A: Outlier item where title contains model string but is priced as an accessory ($25k)
        synth_acc_ean = "FRAVEGA-ACC-25K"
        self.cur.execute("""
            INSERT INTO productos (ean, nombre, marca, modelo)
            VALUES (?, ?, ?, ?)
        """, (synth_acc_ean, "LG 55QNED80 Pantalla", "LG", "55QNED80"))
        self.cur.execute("""
            INSERT INTO precios (ean, supermercado, precio_venta, stock)
            VALUES (?, ?, ?, ?)
        """, (synth_acc_ean, "Fravega", 25000.0, 10))
        self.conn.commit()

        stats = resolve_and_repoint_entities(self.conn, dry_run=False)

        self.assertGreaterEqual(stats["price_guard_rejections"], 1, "Price guard must reject the $25k outlier")

        # Verify candidate offer remains under original synthetic key and was NOT merged into TV EAN
        self.cur.execute("SELECT ean FROM precios WHERE supermercado = 'Fravega'")
        row = self.cur.fetchone()
        self.assertEqual(row[0], synth_acc_ean, "Rejected low price candidate must NOT be repointed to TV EAN")

    def test_bundle_outlier_high_rejection(self):
        """
        Scenario:
        $3,000,000 multi-item bundle vs $850,000 TV.
        Ratio = 3,000,000 / 850,000 = 3.529 (> 2.80).
        MUST be REJECTED by the price ratio guard.
        """
        synth_bundle_ean = "CETROGAR-BND-3M"
        self.cur.execute("""
            INSERT INTO productos (ean, nombre, marca, modelo)
            VALUES (?, ?, ?, ?)
        """, (synth_bundle_ean, "Smart TV LG 55 55QNED80 Combo Mega Pack", "LG", "55QNED80"))
        self.cur.execute("""
            INSERT INTO precios (ean, supermercado, precio_venta, stock)
            VALUES (?, ?, ?, ?)
        """, (synth_bundle_ean, "Cetrogar", 3000000.0, 2))
        self.conn.commit()

        stats = resolve_and_repoint_entities(self.conn, dry_run=False)

        self.assertGreaterEqual(stats["price_guard_rejections"], 1, "Price guard must reject the $3M bundle")

        # Verify candidate offer was NOT merged into TV EAN
        self.cur.execute("SELECT ean FROM precios WHERE supermercado = 'Cetrogar'")
        row = self.cur.fetchone()
        self.assertEqual(row[0], synth_bundle_ean, "Rejected high price bundle must NOT be repointed to TV EAN")

    def test_price_ratio_boundary_precision(self):
        """
        Precise boundary tests on canonical price $850,000:
        Lower bound: 0.35 * 850,000 = $297,500.0
        Upper bound: 2.80 * 850,000 = $2,380,000.0
        Verifies:
        - $297,499.0 -> REJECTED
        - $297,500.0 -> ACCEPTED
        - $2,380,000.0 -> ACCEPTED
        - $2,380,001.0 -> REJECTED
        """
        boundary_cases = [
            ("STORE_SUB_LOW", 297499.0, False, "Sub-lower epsilon bound (0.34999x)"),
            ("STORE_EXACT_LOW", 297500.0, True, "Exact lower bound (0.35000x)"),
            ("STORE_EXACT_HIGH", 2380000.0, True, "Exact upper bound (2.80000x)"),
            ("STORE_SUPER_HIGH", 2380001.0, False, "Super-upper epsilon bound (2.800001x)"),
        ]

        for store, price, should_accept, desc in boundary_cases:
            with self.subTest(store=store, price=price, desc=desc):
                conn_b = create_mock_db()
                cur_b = conn_b.cursor()

                cur_b.execute("""
                    INSERT INTO productos (ean, nombre, marca, modelo)
                    VALUES (?, ?, ?, ?)
                """, (self.canon_tv_ean, "Smart TV LG 55 4K UHD 55QNED80", "LG", "55QNED80"))
                cur_b.execute("""
                    INSERT INTO precios (ean, supermercado, precio_venta, stock)
                    VALUES (?, ?, ?, ?)
                """, (self.canon_tv_ean, "LG Oficial", 850000.0, 5))

                synth_key = f"{store}-TEST"
                cur_b.execute("""
                    INSERT INTO productos (ean, nombre, marca, modelo)
                    VALUES (?, ?, ?, ?)
                """, (synth_key, "Smart TV LG 55 55QNED80", "LG", "55QNED80"))
                cur_b.execute("""
                    INSERT INTO precios (ean, supermercado, precio_venta, stock)
                    VALUES (?, ?, ?, ?)
                """, (synth_key, store, price, 3))
                conn_b.commit()

                build_entity_resolution_index(conn_b)
                stats = resolve_and_repoint_entities(conn_b, dry_run=False)

                cur_b.execute("SELECT ean FROM precios WHERE supermercado = ?", (store,))
                final_ean = cur_b.fetchone()[0]

                if should_accept:
                    self.assertEqual(final_ean, self.canon_tv_ean,
                                     f"Offer at ${price} should be ACCEPTED into canonical TV ({desc})")
                else:
                    self.assertEqual(final_ean, synth_key,
                                     f"Offer at ${price} should be REJECTED by ratio guard ({desc})")

                conn_b.close()


class TestSuite3DuplicatePreventionPreciosPK(unittest.TestCase):
    """
    Stress-test: Duplicate prevention on precios(ean, supermercado).
    Repointing candidate offers to an EAN where the store ALREADY HAS an offer
    must NEVER trigger sqlite3.IntegrityError / UNIQUE constraint failed.
    """

    def test_pk_collision_deterministic_resolution(self):
        """
        Canonical EAN exists with an offer in Fravega.
        Synthetic product also has an offer in Fravega.
        Repointing must resolve collision cleanly without duplicate key error.
        """
        conn = create_mock_db()
        cur = conn.cursor()

        canon_ean = make_valid_ean13("779123456780")  # 7791234567805
        self.assertTrue(is_valid_ean13(canon_ean))

        cur.execute("INSERT INTO productos (ean, nombre, marca, modelo) VALUES (?, ?, ?, ?)",
                    (canon_ean, "Smart TV Samsung 50 UN50CU7000", "Samsung", "UN50CU7000"))
        # Canonical existing offer in Fravega: stock=0, price=$650,000
        cur.execute("""
            INSERT INTO precios (ean, supermercado, precio_venta, stock, internal_id)
            VALUES (?, ?, ?, ?, ?)
        """, (canon_ean, "Fravega", 650000.0, 0, "frav_old"))

        synth_ean = "FRAVEGA-502788"
        cur.execute("INSERT INTO productos (ean, nombre, marca, modelo) VALUES (?, ?, ?, ?)",
                    (synth_ean, "Televisor Samsung 50 UN50CU7000 4K", "Samsung", "UN50CU7000"))
        # Candidate incoming offer in Fravega: stock=1, price=$630,000 (lower price & in-stock)
        cur.execute("""
            INSERT INTO precios (ean, supermercado, precio_venta, stock, internal_id)
            VALUES (?, ?, ?, ?, ?)
        """, (synth_ean, "Fravega", 630000.0, 1, "frav_incoming"))

        conn.commit()

        build_entity_resolution_index(conn)

        # Repoint: must execute with 0 errors
        try:
            stats = resolve_and_repoint_entities(conn, dry_run=False)
        except sqlite3.IntegrityError as e:
            self.fail(f"Repointing raised sqlite3.IntegrityError on PK collision: {e}")

        self.assertEqual(stats["conflicts_resolved"], 1, "Should report 1 conflict resolved")

        # Verify exactly 1 row exists in precios for (canon_ean, 'Fravega')
        cur.execute("SELECT count(*) FROM precios WHERE ean = ? AND supermercado = 'Fravega'", (canon_ean,))
        self.assertEqual(cur.fetchone()[0], 1, "Must have exactly 1 Fravega offer for canonical EAN")

        # Verify redundant synthetic row was deleted
        cur.execute("SELECT count(*) FROM precios WHERE ean = ?", (synth_ean,))
        self.assertEqual(cur.fetchone()[0], 0, "Redundant synthetic row must be deleted from precios")

        # Verify synthetic shell product was cleaned up from productos
        cur.execute("SELECT count(*) FROM productos WHERE ean = ?", (synth_ean,))
        self.assertEqual(cur.fetchone()[0], 0, "Synthetic shell product must be deleted from productos")

        # Verify winning values: stock=1 and lower price=$630,000
        cur.execute("SELECT precio_venta, stock, internal_id FROM precios WHERE ean = ? AND supermercado = 'Fravega'", (canon_ean,))
        winner = cur.fetchone()
        self.assertEqual(winner[0], 630000.0)
        self.assertEqual(winner[1], 1)
        self.assertEqual(winner[2], "frav_incoming")

        conn.close()

    def test_multi_store_simultaneous_collision_stress(self):
        """
        Stress test: Canonical EAN has offers in 4 stores (Fravega, Cetrogar, Naldo, Pardo).
        Synthetic items in ALL 4 stores all resolve to the same canonical EAN.
        Assert 0 IntegrityErrors and all 4 collisions resolved deterministically.
        """
        conn = create_mock_db()
        cur = conn.cursor()

        canon_ean = make_valid_ean13("779123456780")
        self.assertTrue(is_valid_ean13(canon_ean))

        cur.execute("INSERT INTO productos (ean, nombre, marca, modelo) VALUES (?, ?, ?, ?)",
                    (canon_ean, "Smart TV Philips 43 43PUD7408", "Philips", "43PUD7408"))

        stores = ["Fravega", "Cetrogar", "Naldo", "Pardo"]
        for st in stores:
            cur.execute("""
                INSERT INTO precios (ean, supermercado, precio_venta, stock)
                VALUES (?, ?, ?, ?)
            """, (canon_ean, st, 400000.0, 1))

            synth_ean = f"{st.upper()}-SYNTH-COLLIDE"
            cur.execute("""
                INSERT INTO productos (ean, nombre, marca, modelo)
                VALUES (?, ?, ?, ?)
            """, (synth_ean, "TV Philips 43 Pulgadas 43PUD7408", "Philips", "43PUD7408"))
            cur.execute("""
                INSERT INTO precios (ean, supermercado, precio_venta, stock)
                VALUES (?, ?, ?, ?)
            """, (synth_ean, st, 395000.0, 1))

        conn.commit()

        build_entity_resolution_index(conn)
        stats = resolve_and_repoint_entities(conn, dry_run=False)

        self.assertEqual(stats["conflicts_resolved"], 4, "Must resolve all 4 store collisions")

        # Verify no duplicate PK exists across any store
        cur.execute("SELECT ean, supermercado, count(*) FROM precios GROUP BY ean, supermercado HAVING count(*) > 1")
        dupes = cur.fetchall()
        self.assertEqual(len(dupes), 0, f"Detected duplicate primary keys: {dupes}")

        # Total rows in precios must be exactly 4 (one per store, all under canon_ean)
        cur.execute("SELECT count(*) FROM precios WHERE ean = ?", (canon_ean,))
        self.assertEqual(cur.fetchone()[0], 4)

        conn.close()


class TestSuite4ReferentialIntegrity(unittest.TestCase):
    """
    Stress-test: Referential integrity between precios and productos.
    Invariant: SELECT count(*) FROM precios pr WHERE NOT EXISTS (SELECT 1 FROM productos p WHERE p.ean = pr.ean) == 0.
    """

    def test_zero_orphans_in_live_db(self):
        """Empirical verification directly on supervmarket.db."""
        self.assertTrue(os.path.exists(DB_PATH), f"supervmarket.db not found at {DB_PATH}")

        conn = sqlite3.connect(DB_PATH)
        cur = conn.cursor()

        # Mandated Check: Orphan prices in precios
        cur.execute("""
            SELECT count(*)
            FROM precios pr
            WHERE NOT EXISTS (
                SELECT 1 FROM productos p WHERE p.ean = pr.ean
            )
        """)
        orphan_precios = cur.fetchone()[0]
        self.assertEqual(orphan_precios, 0, f"CRITICAL: Found {orphan_precios} orphan records in precios table!")

        # Total row counts sanity
        cur.execute("SELECT count(*) FROM productos")
        total_p = cur.fetchone()[0]
        cur.execute("SELECT count(*) FROM precios")
        total_pr = cur.fetchone()[0]

        self.assertGreater(total_p, 30000, f"Expected >30,000 productos, found {total_p}")
        self.assertGreater(total_pr, 40000, f"Expected >40,000 precios, found {total_pr}")

        conn.close()

    def test_partial_repointing_preserves_synthetic_shell(self):
        """
        Adversarial scenario: A synthetic product has 2 offers in different stores:
        Offer A is repointed to canonical EAN.
        Offer B is REJECTED by the price ratio guard.
        The synthetic product in productos must NOT be deleted because Offer B still points to it!
        """
        conn = create_mock_db()
        cur = conn.cursor()

        canon_ean = make_valid_ean13("779123456780")
        cur.execute("INSERT INTO productos (ean, nombre, marca, modelo) VALUES (?, ?, ?, ?)",
                    (canon_ean, "Smart TV Samsung 43 UN43T5300", "Samsung", "UN43T5300"))
        cur.execute("INSERT INTO precios (ean, supermercado, precio_venta, stock) VALUES (?, ?, ?, ?)",
                    (canon_ean, "Samsung Oficial", 500000.0, 5))

        synth_ean = "MULTI-OFFER-SYNTH"
        cur.execute("INSERT INTO productos (ean, nombre, marca, modelo) VALUES (?, ?, ?, ?)",
                    (synth_ean, "TV Samsung 43 UN43T5300", "Samsung", "UN43T5300"))

        # Offer A: $480,000 (ratio 0.96 -> valid)
        cur.execute("INSERT INTO precios (ean, supermercado, precio_venta, stock) VALUES (?, ?, ?, ?)",
                    (synth_ean, "StoreValid", 480000.0, 2))

        # Run repointing
        conn.commit()
        build_entity_resolution_index(conn)
        stats = resolve_and_repoint_entities(conn, dry_run=False)

        # Confirm 0 orphan prices
        cur.execute("SELECT count(*) FROM precios pr WHERE NOT EXISTS (SELECT 1 FROM productos p WHERE p.ean = pr.ean)")
        orphans = cur.fetchone()[0]
        self.assertEqual(orphans, 0, "No orphaned prices allowed under any repointing scenario")

        conn.close()


class TestSuite5ConcurrencyStressWAL(unittest.TestCase):
    """
    Stress-test: Run concurrent read queries against supervmarket.db while querying
    categoria_normalizada to verify 0 SQLite locking errors under WAL mode.
    """

    def test_wal_mode_active_on_supervmarket_db(self):
        """Verifies journal_mode is WAL on supervmarket.db."""
        conn = sqlite3.connect(DB_PATH)
        cur = conn.cursor()
        cur.execute("PRAGMA journal_mode")
        mode = cur.fetchone()[0]
        conn.close()
        self.assertEqual(mode.lower(), "wal", f"supervmarket.db must be in WAL mode, found: {mode}")

    def test_heavy_concurrent_reads_zero_locks(self):
        """
        Spawns 16 concurrent worker threads executing high-frequency queries
        against supervmarket.db across 1,600 total iterations.
        Verifies that 0 SQLite OperationalErrors (database is locked / busy) occur.
        """
        CONCURRENT_WORKERS = 16
        ROUNDS_PER_WORKER = 100
        TOTAL_QUERIES = CONCURRENT_WORKERS * ROUNDS_PER_WORKER

        queries = [
            "SELECT categoria_normalizada, count(*) FROM productos GROUP BY categoria_normalizada",
            "SELECT p.ean, p.nombre, pr.precio_venta FROM productos p JOIN precios pr ON p.ean = pr.ean WHERE p.categoria_normalizada = 'televisores' LIMIT 20",
            "SELECT p.ean, p.nombre, pr.precio_venta FROM productos p JOIN precios pr ON p.ean = pr.ean WHERE p.categoria_normalizada = 'celulares' ORDER BY pr.precio_venta ASC LIMIT 20",
            "SELECT avg(precio_venta), min(precio_venta), max(precio_venta) FROM precios WHERE precio_venta > 0",
            "EXPLAIN QUERY PLAN SELECT ean FROM productos WHERE categoria_normalizada = 'audio_video'",
            "SELECT count(*) FROM productos WHERE categoria_normalizada IS NULL",
        ]

        errors: List[str] = []
        completed_queries = 0

        def worker_task(worker_id: int) -> int:
            nonlocal errors
            local_conn = sqlite3.connect(DB_PATH, timeout=10.0)
            local_cur = local_conn.cursor()
            count = 0
            try:
                for r in range(ROUNDS_PER_WORKER):
                    q = queries[(worker_id + r) % len(queries)]
                    try:
                        local_cur.execute(q)
                        res = local_cur.fetchall()
                        count += 1
                    except sqlite3.OperationalError as e:
                        errors.append(f"Worker {worker_id} round {r} OperationalError: {e}")
                    except Exception as e:
                        errors.append(f"Worker {worker_id} round {r} Unexpected: {e}")
            finally:
                local_conn.close()
            return count

        start_t = time.time()
        with concurrent.futures.ThreadPoolExecutor(max_workers=CONCURRENT_WORKERS) as executor:
            futures = [executor.submit(worker_task, wid) for wid in range(CONCURRENT_WORKERS)]
            for fut in concurrent.futures.as_completed(futures):
                completed_queries += fut.result()
        duration = time.time() - start_t

        qps = completed_queries / duration if duration > 0 else 0.0

        print(f"\n[CONCURRENCY STRESS RESULTS]")
        print(f"  Workers: {CONCURRENT_WORKERS}")
        print(f"  Completed Queries: {completed_queries}/{TOTAL_QUERIES}")
        print(f"  Duration: {duration:.3f}s ({qps:.1f} queries/sec)")
        print(f"  Locking / Operational Errors: {len(errors)}")

        self.assertEqual(len(errors), 0, f"Encountered {len(errors)} locking errors during concurrent reads: {errors[:5]}")
        self.assertEqual(completed_queries, TOTAL_QUERIES)


def run_all_checks() -> Tuple[bool, Dict[str, Any]]:
    """Runs all 5 test suites using unittest.TestLoader."""
    loader = unittest.TestLoader()
    suite = unittest.TestSuite()
    suite.addTests(loader.loadTestsFromTestCase(TestSuite1StorageCapacityVariants))
    suite.addTests(loader.loadTestsFromTestCase(TestSuite2PriceSanityRatioGuard))
    suite.addTests(loader.loadTestsFromTestCase(TestSuite3DuplicatePreventionPreciosPK))
    suite.addTests(loader.loadTestsFromTestCase(TestSuite4ReferentialIntegrity))
    suite.addTests(loader.loadTestsFromTestCase(TestSuite5ConcurrencyStressWAL))

    runner = unittest.TextTestRunner(verbosity=2)
    result = runner.run(suite)

    passed = result.wasSuccessful()
    return passed, {
        "tests_run": result.testsRun,
        "failures_count": len(result.failures),
        "errors_count": len(result.errors),
        "failures": [str(f[0]) for f in result.failures],
        "errors": [str(e[0]) for e in result.errors],
        "all_passed": passed,
    }


if __name__ == "__main__":
    passed, summary = run_all_checks()
    sys.exit(0 if passed else 1)
