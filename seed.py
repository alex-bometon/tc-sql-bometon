#!/usr/bin/env python3
"""CLI para regenerar los datos sintéticos de SkeletIA en Google BigQuery.

Ejemplo solicitado por el enunciado:

    python seed.py --project mi-proyecto --dataset skeletia \
        --customers 500 --orders 2000

El script reutiliza las reglas de negocio del proyecto:
- 70 productos por defecto;
- 2-3 líneas por pedido (2.25 de media por defecto);
- un pago por pedido;
- reviews para ~35 % de las líneas de pedidos entregados;
- validación previa a la carga;
- vaciado de tablas en orden inverso de dependencias;
- carga desde DataFrames de pandas;
- comprobación final de recuentos en BigQuery.

Importante:
    El dataset y las 11 tablas deben existir previamente. El esquema se crea
    con `parte_2_modelo_bigquery/notebooks/01_setup_bigquery.ipynb`.
"""

from __future__ import annotations

import argparse
import os
import random
import re
import sys
from collections import defaultdict
from datetime import datetime, timedelta
from decimal import Decimal, ROUND_HALF_UP
from pathlib import Path
from typing import Any

import pandas as pd
from dotenv import load_dotenv
from faker import Faker
from faker.config import AVAILABLE_LOCALES
from google.cloud import bigquery
from google.api_core.exceptions import NotFound


# ============================================================
# 1. CONFIGURACIÓN GENERAL
# ============================================================

DEFAULT_CUSTOMERS = 500
DEFAULT_PRODUCTS = 70
DEFAULT_ORDERS = 2_000
DEFAULT_ITEMS_PER_ORDER = 2.25
DEFAULT_REVIEW_PROBABILITY = 0.35
DEFAULT_SEED = 42

TABLE_LOAD_ORDER = [
    "countries",
    "cities",
    "acquisition_channels",
    "categories",
    "brands",
    "customers",
    "products",
    "orders",
    "order_items",
    "payments",
    "reviews",
]

TABLE_TRUNCATE_ORDER = list(reversed(TABLE_LOAD_ORDER))

VALID_ORDER_STATUSES = {
    "pending",
    "confirmed",
    "shipped",
    "delivered",
    "cancelled",
    "returned",
}

VALID_PAYMENT_STATUSES = {
    "pending",
    "completed",
    "failed",
    "refunded",
}

VALID_PAYMENT_METHODS = {
    "apple_pay",
    "bank_transfer",
    "card",
    "cash_on_delivery",
    "google_pay",
    "paypal",
    "samsung_pay",
}


# ============================================================
# 2. DATOS MAESTROS
# ============================================================

COUNTRIES_DATA = [
    {"country_id": 1, "country_code": "ES", "country_name": "Spain", "faker_locale": "es_ES"},
    {"country_id": 2, "country_code": "FR", "country_name": "France", "faker_locale": "fr_FR"},
    {"country_id": 3, "country_code": "DE", "country_name": "Germany", "faker_locale": "de_DE"},
    {"country_id": 4, "country_code": "IT", "country_name": "Italy", "faker_locale": "it_IT"},
    {"country_id": 5, "country_code": "PT", "country_name": "Portugal", "faker_locale": "pt_PT"},
    {"country_id": 6, "country_code": "NL", "country_name": "Netherlands", "faker_locale": "nl_NL"},
    {"country_id": 7, "country_code": "BE", "country_name": "Belgium", "faker_locale": "fr_BE"},
    {"country_id": 8, "country_code": "AT", "country_name": "Austria", "faker_locale": "de_AT"},
]

CITIES_DATA = [
    {"city_id": 1, "country_id": 1, "city_name": "Madrid"},
    {"city_id": 2, "country_id": 1, "city_name": "Barcelona"},
    {"city_id": 3, "country_id": 1, "city_name": "Valencia"},
    {"city_id": 4, "country_id": 2, "city_name": "Paris"},
    {"city_id": 5, "country_id": 2, "city_name": "Lyon"},
    {"city_id": 6, "country_id": 2, "city_name": "Toulouse"},
    {"city_id": 7, "country_id": 3, "city_name": "Berlin"},
    {"city_id": 8, "country_id": 3, "city_name": "Hamburg"},
    {"city_id": 9, "country_id": 3, "city_name": "Munich"},
    {"city_id": 10, "country_id": 4, "city_name": "Rome"},
    {"city_id": 11, "country_id": 4, "city_name": "Milan"},
    {"city_id": 12, "country_id": 4, "city_name": "Turin"},
    {"city_id": 13, "country_id": 5, "city_name": "Lisbon"},
    {"city_id": 14, "country_id": 5, "city_name": "Porto"},
    {"city_id": 15, "country_id": 5, "city_name": "Braga"},
    {"city_id": 16, "country_id": 6, "city_name": "Amsterdam"},
    {"city_id": 17, "country_id": 6, "city_name": "Rotterdam"},
    {"city_id": 18, "country_id": 6, "city_name": "Utrecht"},
    {"city_id": 19, "country_id": 7, "city_name": "Brussels"},
    {"city_id": 20, "country_id": 7, "city_name": "Antwerp"},
    {"city_id": 21, "country_id": 7, "city_name": "Ghent"},
    {"city_id": 22, "country_id": 8, "city_name": "Vienna"},
    {"city_id": 23, "country_id": 8, "city_name": "Graz"},
    {"city_id": 24, "country_id": 8, "city_name": "Salzburg"},
]

ACQUISITION_CHANNELS_DATA = [
    {"channel_id": 1, "channel_code": "organic", "channel_name": "Organic search"},
    {"channel_id": 2, "channel_code": "paid_ads", "channel_name": "Paid ads"},
    {"channel_id": 3, "channel_code": "social_media", "channel_name": "Social media"},
    {"channel_id": 4, "channel_code": "referral", "channel_name": "Referral"},
    {"channel_id": 5, "channel_code": "affiliate", "channel_name": "Affiliate"},
]

CATEGORIES_DATA = [
    {"category_id": 1, "category_name": "Smartphones", "description": "Smartphones and mobile devices"},
    {"category_id": 2, "category_name": "Laptops", "description": "Portable computers and ultrabooks"},
    {"category_id": 3, "category_name": "Tablets", "description": "Tablets and related devices"},
    {"category_id": 4, "category_name": "Audio", "description": "Headphones, speakers and audio accessories"},
    {"category_id": 5, "category_name": "Peripherals", "description": "Keyboards, mice, webcams and peripherals"},
    {"category_id": 6, "category_name": "Wearables", "description": "Smartwatches and fitness wearables"},
    {"category_id": 7, "category_name": "Smart Home", "description": "Connected home and IoT devices"},
    {"category_id": 8, "category_name": "Storage & Components", "description": "Storage devices and computer components"},
]

BRANDS_DATA = [
    {"brand_id": 1, "brand_name": "SkeletIA"},
    {"brand_id": 2, "brand_name": "Neurobyte"},
    {"brand_id": 3, "brand_name": "HexaTech"},
    {"brand_id": 4, "brand_name": "Quantumix"},
    {"brand_id": 5, "brand_name": "NovaCore"},
    {"brand_id": 6, "brand_name": "PixelForge"},
    {"brand_id": 7, "brand_name": "VoltEdge"},
    {"brand_id": 8, "brand_name": "Synapse"},
    {"brand_id": 9, "brand_name": "Aether Labs"},
    {"brand_id": 10, "brand_name": "Carbon Devices"},
]

COUNTRY_BY_ID = {row["country_id"]: row for row in COUNTRIES_DATA}
CITY_BY_ID = {row["city_id"]: row for row in CITIES_DATA}

PHONE_PREFIXES = {
    "ES": "+34",
    "FR": "+33",
    "DE": "+49",
    "IT": "+39",
    "PT": "+351",
    "NL": "+31",
    "BE": "+32",
    "AT": "+43",
}

PRODUCT_CONFIG = {
    1: {"base_name": "NeuroPhone", "min_price": 249, "max_price": 1399},
    2: {"base_name": "BoneBook", "min_price": 499, "max_price": 2499},
    3: {"base_name": "OsteoTab", "min_price": 199, "max_price": 1299},
    4: {"base_name": "EchoCore", "min_price": 29, "max_price": 599},
    5: {"base_name": "PhantomGear", "min_price": 15, "max_price": 349},
    6: {"base_name": "PulseBand", "min_price": 49, "max_price": 699},
    7: {"base_name": "CryptHome", "min_price": 19, "max_price": 499},
    8: {"base_name": "SpineDrive", "min_price": 39, "max_price": 999},
}

REVIEW_TEXTS = {
    1: [
        "The product did not meet my expectations.",
        "I would not buy this model again.",
        "The overall experience was disappointing.",
    ],
    2: [
        "It works, but the overall experience could be better.",
        "Usable, although there are several points to improve.",
        "The product is acceptable but below my expectations.",
    ],
    3: [
        "Correct product and acceptable value for money.",
        "It does the job and the experience was reasonable.",
        "A balanced product without major surprises.",
    ],
    4: [
        "Very good product. I would buy it again.",
        "Good performance and a positive overall experience.",
        "The product met my expectations very well.",
    ],
    5: [
        "Excellent product and very good experience.",
        "Very satisfied with the purchase and the performance.",
        "Excellent value and a product I would recommend.",
    ],
}


# ============================================================
# 3. HELPERS
# ============================================================

def money(value: float | Decimal) -> Decimal:
    return Decimal(str(value)).quantize(
        Decimal("0.01"),
        rounding=ROUND_HALF_UP,
    )


def random_datetime(start: datetime, end: datetime) -> datetime:
    if end <= start:
        return start

    seconds = int((end - start).total_seconds())
    return start + timedelta(seconds=random.randint(0, seconds))


def weighted_choice(values: list[Any], weights: list[float]) -> Any:
    return random.choices(values, weights=weights, k=1)[0]


def safe_faker(locale: str) -> Faker:
    return Faker(locale if locale in AVAILABLE_LOCALES else "en_US")


def build_fakers() -> dict[int, Faker]:
    return {
        country["country_id"]: safe_faker(country["faker_locale"])
        for country in COUNTRIES_DATA
    }


def expected_order_items(orders: int) -> int:
    """Mantiene 2.25 líneas por pedido; con 2000 pedidos produce 4500."""
    return round(orders * DEFAULT_ITEMS_PER_ORDER)


# ============================================================
# 4. GENERACIÓN DE DATOS
# ============================================================

def generate_customers(
    count: int,
    *,
    now: datetime,
    fakers_by_country: dict[int, Faker],
) -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []

    email_domains = [
        "gmail.com",
        "outlook.com",
        "proton.me",
        "icloud.com",
        "mail.com",
    ]

    for customer_id in range(1, count + 1):
        city = random.choice(CITIES_DATA)
        country = COUNTRY_BY_ID[city["country_id"]]
        fake = fakers_by_country[country["country_id"]]

        first_name = fake.first_name()
        last_name = fake.last_name()

        email_user = re.sub(
            r"[^a-zA-Z0-9._-]",
            "",
            fake.user_name(),
        ).lower()

        email = (
            f"{email_user}.{customer_id:04d}"
            f"@{random.choice(email_domains)}"
        )

        raw_phone = re.sub(r"[^0-9]", "", fake.phone_number())
        phone = f"{PHONE_PREFIXES[country['country_code']]} {raw_phone[-12:]}"

        channel_id = weighted_choice(
            [1, 2, 3, 4, 5],
            [35, 25, 20, 12, 8],
        )

        registered_at = random_datetime(
            now - timedelta(days=900),
            now - timedelta(days=30),
        )

        rows.append(
            {
                "customer_id": customer_id,
                "first_name": first_name[:80],
                "last_name": last_name[:120],
                "email": email[:180],
                "phone": phone[:30],
                "city_id": city["city_id"],
                "channel_id": channel_id,
                "registered_at": registered_at,
                "is_active": random.random() < 0.97,
            }
        )

    return rows


def generate_products(count: int, *, now: datetime) -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []

    for product_id in range(1, count + 1):
        category_id = random.randint(1, 8)
        brand_id = random.randint(1, 10)
        config = PRODUCT_CONFIG[category_id]

        current_sale_price = money(
            random.uniform(config["min_price"], config["max_price"])
        )

        current_cost = money(
            current_sale_price
            * Decimal(str(random.uniform(0.55, 0.78)))
        )

        letter = chr(65 + ((product_id - 1) % 26))
        model_number = random.randint(100, 999)

        rows.append(
            {
                "product_id": product_id,
                "sku": f"SKL-{category_id:02d}-{product_id:04d}",
                "category_id": category_id,
                "brand_id": brand_id,
                "product_name": f"{config['base_name']} {letter}{model_number}",
                "current_sale_price": current_sale_price,
                "current_cost": current_cost,
                "stock": random.randint(0, 250),
                "is_active": random.random() < 0.94,
                "created_at": random_datetime(
                    now - timedelta(days=1000),
                    now,
                ),
            }
        )

    return rows


def generate_orders(
    customers_rows: list[dict[str, Any]],
    count: int,
    *,
    now: datetime,
    fakers_by_country: dict[int, Faker],
) -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    end_date = now - timedelta(days=10)

    for order_id in range(1, count + 1):
        customer = random.choice(customers_rows)

        order_start = max(
            customer["registered_at"],
            now - timedelta(days=548),
        )

        order_date = random_datetime(order_start, end_date)

        status = weighted_choice(
            [
                "pending",
                "confirmed",
                "shipped",
                "delivered",
                "cancelled",
                "returned",
            ],
            [5, 8, 10, 65, 7, 5],
        )

        shipped_at = None
        delivered_at = None

        if status in {"shipped", "delivered", "returned"}:
            shipped_at = order_date + timedelta(days=random.randint(1, 3))

        if status in {"delivered", "returned"}:
            delivered_at = shipped_at + timedelta(days=random.randint(1, 5))

        if random.random() < 0.90:
            shipping_city_id = customer["city_id"]
        else:
            shipping_city_id = random.choice(CITIES_DATA)["city_id"]

        shipping_city = CITY_BY_ID[shipping_city_id]
        shipping_fake = fakers_by_country[shipping_city["country_id"]]

        shipping_cost = weighted_choice(
            [
                Decimal("0.00"),
                Decimal("4.99"),
                Decimal("7.99"),
                Decimal("9.99"),
            ],
            [35, 30, 23, 12],
        )

        rows.append(
            {
                "order_id": order_id,
                "customer_id": customer["customer_id"],
                "status": status,
                "order_date": order_date,
                "shipped_at": shipped_at,
                "delivered_at": delivered_at,
                "shipping_recipient": (
                    f"{customer['first_name']} {customer['last_name']}"
                )[:200],
                "shipping_address_line1": shipping_fake.street_address()[:200],
                "shipping_postal_code": shipping_fake.postcode()[:20],
                "shipping_city_id": shipping_city_id,
                "shipping_cost": shipping_cost,
                "currency_code": "EUR",
            }
        )

    return rows


def generate_order_items(
    orders_rows: list[dict[str, Any]],
    products_rows: list[dict[str, Any]],
    target_items: int,
) -> list[dict[str, Any]]:
    order_count = len(orders_rows)
    minimum = order_count * 2
    maximum = order_count * 3

    if not minimum <= target_items <= maximum:
        raise ValueError(
            "--order-items debe quedar entre 2 y 3 líneas por pedido "
            f"({minimum} y {maximum} para {order_count} pedidos)."
        )

    if len(products_rows) < 3:
        raise ValueError("Se necesitan al menos 3 productos para generar pedidos.")

    number_of_three_line_orders = target_items - minimum

    three_line_order_ids = set(
        random.sample(
            [row["order_id"] for row in orders_rows],
            k=number_of_three_line_orders,
        )
    )

    rows: list[dict[str, Any]] = []
    order_item_id = 1

    for order in orders_rows:
        line_count = 3 if order["order_id"] in three_line_order_ids else 2
        selected_products = random.sample(products_rows, k=line_count)

        for product in selected_products:
            price_factor = Decimal(str(random.uniform(0.85, 1.05)))
            unit_price = money(product["current_sale_price"] * price_factor)

            historical_cost_factor = Decimal(str(random.uniform(0.90, 1.00)))
            historical_cost = product["current_cost"] * historical_cost_factor

            unit_cost = money(
                min(
                    historical_cost,
                    unit_price * Decimal("0.90"),
                )
            )

            quantity = weighted_choice([1, 2, 3], [80, 16, 4])
            discount_percent = weighted_choice(
                [
                    Decimal("0.00"),
                    Decimal("5.00"),
                    Decimal("10.00"),
                    Decimal("15.00"),
                ],
                [70, 15, 10, 5],
            )

            rows.append(
                {
                    "order_item_id": order_item_id,
                    "order_id": order["order_id"],
                    "product_id": product["product_id"],
                    "quantity": quantity,
                    "unit_price": unit_price,
                    "unit_cost": unit_cost,
                    "discount_percent": discount_percent,
                }
            )
            order_item_id += 1

    if len(rows) != target_items:
        raise RuntimeError(
            f"Se esperaban {target_items} líneas y se generaron {len(rows)}."
        )

    return rows


def generate_payments(
    orders_rows: list[dict[str, Any]],
    order_items_rows: list[dict[str, Any]],
    *,
    now: datetime,
) -> list[dict[str, Any]]:
    items_by_order: dict[int, list[dict[str, Any]]] = defaultdict(list)

    for item in order_items_rows:
        items_by_order[item["order_id"]].append(item)

    rows: list[dict[str, Any]] = []

    for payment_id, order in enumerate(orders_rows, start=1):
        order_total = Decimal("0.00")

        for item in items_by_order[order["order_id"]]:
            discount_factor = Decimal("1.00") - (
                item["discount_percent"] / Decimal("100")
            )

            line_total = (
                Decimal(item["quantity"])
                * item["unit_price"]
                * discount_factor
            )
            order_total += line_total

        order_total = money(order_total + order["shipping_cost"])

        # Distribución definida para la versión actual de SkeletIA.
        payment_method = weighted_choice(
            [
                "apple_pay",
                "bank_transfer",
                "card",
                "cash_on_delivery",
                "google_pay",
                "paypal",
                "samsung_pay",
            ],
            [12, 4, 50, 3, 8, 22, 1],
        )

        if order["status"] == "pending":
            payment_status = "pending"
        elif order["status"] == "returned":
            payment_status = "refunded"
        elif order["status"] == "cancelled":
            payment_status = weighted_choice(
                ["failed", "refunded"],
                [40, 60],
            )
        else:
            payment_status = "completed"

        payment_date = order["order_date"] + timedelta(days=random.randint(0, 1))

        if order["status"] == "returned":
            status_updated_at = min(
                now,
                order["delivered_at"] + timedelta(days=random.randint(1, 10)),
            )
        elif order["status"] == "cancelled":
            status_updated_at = order["order_date"] + timedelta(days=1)
        else:
            status_updated_at = payment_date

        status_updated_at = max(status_updated_at, payment_date)

        rows.append(
            {
                "payment_id": payment_id,
                "order_id": order["order_id"],
                "payment_method": payment_method,
                "status": payment_status,
                "amount": order_total,
                "payment_date": payment_date,
                "status_updated_at": status_updated_at,
                "external_reference": f"PAY-{order['order_id']:08d}",
            }
        )

    return rows


def generate_reviews(
    orders_rows: list[dict[str, Any]],
    order_items_rows: list[dict[str, Any]],
    probability: float,
    *,
    now: datetime,
) -> list[dict[str, Any]]:
    order_by_id = {row["order_id"]: row for row in orders_rows}
    rows: list[dict[str, Any]] = []
    review_id = 1

    for item in order_items_rows:
        order = order_by_id[item["order_id"]]

        if order["status"] != "delivered":
            continue

        if random.random() >= probability:
            continue

        rating = weighted_choice(
            [1, 2, 3, 4, 5],
            [4, 6, 15, 35, 40],
        )

        review_date = min(
            now,
            order["delivered_at"] + timedelta(days=random.randint(1, 30)),
        )

        rows.append(
            {
                "review_id": review_id,
                "order_item_id": item["order_item_id"],
                "rating": rating,
                "comment": random.choice(REVIEW_TEXTS[rating]),
                "review_date": review_date,
            }
        )
        review_id += 1

    return rows


def build_dataframes(
    *,
    customers: int,
    products: int,
    orders: int,
    order_items: int,
    review_probability: float,
    seed: int,
) -> dict[str, pd.DataFrame]:
    random.seed(seed)
    Faker.seed(seed)

    now = datetime.now().replace(microsecond=0)
    fakers_by_country = build_fakers()

    customers_rows = generate_customers(
        customers,
        now=now,
        fakers_by_country=fakers_by_country,
    )
    products_rows = generate_products(products, now=now)
    orders_rows = generate_orders(
        customers_rows,
        orders,
        now=now,
        fakers_by_country=fakers_by_country,
    )
    order_items_rows = generate_order_items(
        orders_rows,
        products_rows,
        order_items,
    )
    payments_rows = generate_payments(
        orders_rows,
        order_items_rows,
        now=now,
    )
    reviews_rows = generate_reviews(
        orders_rows,
        order_items_rows,
        review_probability,
        now=now,
    )

    countries_public = [
        {
            "country_id": row["country_id"],
            "country_code": row["country_code"],
            "country_name": row["country_name"],
        }
        for row in COUNTRIES_DATA
    ]

    return {
        "countries": pd.DataFrame(countries_public),
        "cities": pd.DataFrame(CITIES_DATA),
        "acquisition_channels": pd.DataFrame(ACQUISITION_CHANNELS_DATA),
        "categories": pd.DataFrame(CATEGORIES_DATA),
        "brands": pd.DataFrame(BRANDS_DATA),
        "customers": pd.DataFrame(customers_rows),
        "products": pd.DataFrame(products_rows),
        "orders": pd.DataFrame(orders_rows),
        "order_items": pd.DataFrame(order_items_rows),
        "payments": pd.DataFrame(payments_rows),
        "reviews": pd.DataFrame(reviews_rows),
    }


# ============================================================
# 5. VALIDACIONES
# ============================================================

def require(condition: bool, message: str) -> None:
    if not condition:
        raise ValueError(message)


def validate_dataframes(
    dfs: dict[str, pd.DataFrame],
    *,
    expected_customers: int,
    expected_products: int,
    expected_orders: int,
    expected_order_items_count: int,
    review_probability: float,
) -> None:
    require(len(dfs["customers"]) == expected_customers, "Número de customers incorrecto.")
    require(len(dfs["products"]) == expected_products, "Número de products incorrecto.")
    require(len(dfs["orders"]) == expected_orders, "Número de orders incorrecto.")
    require(
        len(dfs["order_items"]) == expected_order_items_count,
        "Número de order_items incorrecto.",
    )
    require(len(dfs["payments"]) == expected_orders, "Debe existir un pago por pedido.")

    # PK / unicidad.
    primary_keys = {
        "countries": "country_id",
        "cities": "city_id",
        "acquisition_channels": "channel_id",
        "categories": "category_id",
        "brands": "brand_id",
        "customers": "customer_id",
        "products": "product_id",
        "orders": "order_id",
        "order_items": "order_item_id",
        "payments": "payment_id",
        "reviews": "review_id",
    }

    for table_name, pk in primary_keys.items():
        df = dfs[table_name]
        require(df[pk].notna().all(), f"{table_name}.{pk} contiene NULL.")
        require(df[pk].is_unique, f"{table_name}.{pk} contiene duplicados.")

    require(dfs["customers"]["email"].is_unique, "customers.email debe ser único.")
    require(dfs["products"]["sku"].is_unique, "products.sku debe ser único.")
    require(
        dfs["payments"]["external_reference"].is_unique,
        "payments.external_reference debe ser único.",
    )
    require(dfs["payments"]["order_id"].is_unique, "Debe existir un pago por pedido.")
    require(dfs["reviews"]["order_item_id"].is_unique, "Máximo una review por línea.")

    duplicated_order_products = dfs["order_items"].duplicated(
        subset=["order_id", "product_id"]
    )
    require(
        not duplicated_order_products.any(),
        "No puede repetirse el mismo producto dentro de un pedido.",
    )

    # FKs.
    require(
        set(dfs["cities"]["country_id"]).issubset(set(dfs["countries"]["country_id"])),
        "FK cities.country_id inválida.",
    )
    require(
        set(dfs["customers"]["city_id"]).issubset(set(dfs["cities"]["city_id"])),
        "FK customers.city_id inválida.",
    )
    require(
        set(dfs["customers"]["channel_id"]).issubset(
            set(dfs["acquisition_channels"]["channel_id"])
        ),
        "FK customers.channel_id inválida.",
    )
    require(
        set(dfs["products"]["category_id"]).issubset(set(dfs["categories"]["category_id"])),
        "FK products.category_id inválida.",
    )
    require(
        set(dfs["products"]["brand_id"]).issubset(set(dfs["brands"]["brand_id"])),
        "FK products.brand_id inválida.",
    )
    require(
        set(dfs["orders"]["customer_id"]).issubset(set(dfs["customers"]["customer_id"])),
        "FK orders.customer_id inválida.",
    )
    require(
        set(dfs["orders"]["shipping_city_id"]).issubset(set(dfs["cities"]["city_id"])),
        "FK orders.shipping_city_id inválida.",
    )
    require(
        set(dfs["order_items"]["order_id"]).issubset(set(dfs["orders"]["order_id"])),
        "FK order_items.order_id inválida.",
    )
    require(
        set(dfs["order_items"]["product_id"]).issubset(set(dfs["products"]["product_id"])),
        "FK order_items.product_id inválida.",
    )
    require(
        set(dfs["payments"]["order_id"]).issubset(set(dfs["orders"]["order_id"])),
        "FK payments.order_id inválida.",
    )
    require(
        set(dfs["reviews"]["order_item_id"]).issubset(set(dfs["order_items"]["order_item_id"])),
        "FK reviews.order_item_id inválida.",
    )

    # Dominios.
    require(
        set(dfs["orders"]["status"]).issubset(VALID_ORDER_STATUSES),
        "orders.status contiene valores no permitidos.",
    )
    require(
        set(dfs["payments"]["status"]).issubset(VALID_PAYMENT_STATUSES),
        "payments.status contiene valores no permitidos.",
    )
    require(
        set(dfs["payments"]["payment_method"]).issubset(VALID_PAYMENT_METHODS),
        "payments.payment_method contiene valores no permitidos.",
    )

    # Rangos.
    require((dfs["products"]["current_sale_price"] >= 0).all(), "Precio actual negativo.")
    require((dfs["products"]["current_cost"] >= 0).all(), "Coste actual negativo.")
    require((dfs["products"]["stock"] >= 0).all(), "Stock negativo.")
    require((dfs["order_items"]["quantity"] >= 1).all(), "Cantidad inválida.")
    require((dfs["order_items"]["unit_price"] >= 0).all(), "unit_price negativo.")
    require((dfs["order_items"]["unit_cost"] >= 0).all(), "unit_cost negativo.")
    require(
        dfs["order_items"]["discount_percent"].map(
            lambda value: Decimal("0") <= value <= Decimal("100")
        ).all(),
        "discount_percent fuera de 0-100.",
    )
    require((dfs["orders"]["shipping_cost"] >= 0).all(), "shipping_cost negativo.")
    require((dfs["payments"]["amount"] >= 0).all(), "payment.amount negativo.")

    if not dfs["reviews"].empty:
        require(dfs["reviews"]["rating"].between(1, 5).all(), "rating fuera de 1-5.")

    # Cada pedido debe tener 2 o 3 líneas.
    lines_per_order = dfs["order_items"].groupby("order_id").size()
    require(len(lines_per_order) == expected_orders, "Hay pedidos sin líneas.")
    require(lines_per_order.between(2, 3).all(), "Cada pedido debe tener 2 o 3 líneas.")

    # Coherencia temporal de pedidos.
    customers_registration = dfs["customers"].set_index("customer_id")["registered_at"]

    for row in dfs["orders"].itertuples(index=False):
        require(
            row.order_date >= customers_registration.loc[row.customer_id],
            f"Pedido {row.order_id}: order_date anterior al registro del cliente.",
        )

        if row.status in {"shipped", "delivered", "returned"}:
            require(row.shipped_at is not None, f"Pedido {row.order_id}: falta shipped_at.")
            require(row.shipped_at >= row.order_date, f"Pedido {row.order_id}: shipped_at inválida.")
        else:
            require(pd.isna(row.shipped_at), f"Pedido {row.order_id}: shipped_at debería ser NULL.")

        if row.status in {"delivered", "returned"}:
            require(row.delivered_at is not None, f"Pedido {row.order_id}: falta delivered_at.")
            require(row.delivered_at >= row.shipped_at, f"Pedido {row.order_id}: delivered_at inválida.")
        else:
            require(pd.isna(row.delivered_at), f"Pedido {row.order_id}: delivered_at debería ser NULL.")

    # Reviews solo sobre líneas de pedidos entregados y posteriores a la entrega.
    order_status_by_id = dfs["orders"].set_index("order_id")["status"].to_dict()
    delivered_at_by_id = dfs["orders"].set_index("order_id")["delivered_at"].to_dict()
    item_order_by_id = dfs["order_items"].set_index("order_item_id")["order_id"].to_dict()

    for row in dfs["reviews"].itertuples(index=False):
        order_id = item_order_by_id[row.order_item_id]
        require(order_status_by_id[order_id] == "delivered", "Review asociada a pedido no entregado.")
        require(
            row.review_date >= delivered_at_by_id[order_id],
            "Review anterior a la entrega.",
        )

    # El importe de cada pago debe coincidir con líneas + envío.
    items_by_order: dict[int, list[Any]] = defaultdict(list)
    for row in dfs["order_items"].itertuples(index=False):
        items_by_order[row.order_id].append(row)

    shipping_by_order = dfs["orders"].set_index("order_id")["shipping_cost"].to_dict()

    for payment in dfs["payments"].itertuples(index=False):
        calculated = Decimal("0.00")
        for item in items_by_order[payment.order_id]:
            calculated += (
                Decimal(item.quantity)
                * item.unit_price
                * (Decimal("1.00") - item.discount_percent / Decimal("100"))
            )
        calculated = money(calculated + shipping_by_order[payment.order_id])
        require(
            calculated == payment.amount,
            f"Pago {payment.payment_id}: amount no coincide con el pedido.",
        )

    delivered_order_ids = set(
        dfs["orders"].loc[dfs["orders"]["status"] == "delivered", "order_id"]
    )
    delivered_item_count = int(
        dfs["order_items"]["order_id"].isin(delivered_order_ids).sum()
    )

    actual_review_rate = (
        len(dfs["reviews"]) / delivered_item_count
        if delivered_item_count
        else 0.0
    )

    # No exigimos exactamente 35 % porque se genera probabilísticamente.
    if delivered_item_count >= 100:
        tolerance = 0.08
        require(
            abs(actual_review_rate - review_probability) <= tolerance,
            "La tasa de reviews se aleja demasiado de la probabilidad configurada."
        )


# ============================================================
# 6. BIGQUERY
# ============================================================

def configure_credentials(root_dir: Path, credentials_arg: str | None) -> None:
    credentials_value = credentials_arg or os.getenv("GOOGLE_APPLICATION_CREDENTIALS")

    if not credentials_value:
        return

    credentials_path = Path(credentials_value).expanduser()

    if not credentials_path.is_absolute():
        credentials_path = (root_dir / credentials_path).resolve()

    if not credentials_path.exists():
        raise FileNotFoundError(
            "No se encuentra el fichero de credenciales: "
            f"{credentials_path}"
        )

    os.environ["GOOGLE_APPLICATION_CREDENTIALS"] = str(credentials_path)


def validate_bigquery_structure(
    client: bigquery.Client,
    *,
    project_id: str,
    dataset_id: str,
) -> bigquery.Dataset:
    dataset_ref = f"{project_id}.{dataset_id}"

    try:
        dataset = client.get_dataset(dataset_ref)
    except NotFound as exc:
        raise RuntimeError(
            f"No existe el dataset {dataset_ref}. "
            "Ejecuta primero 01_setup_bigquery.ipynb."
        ) from exc

    missing_tables: list[str] = []

    for table_name in TABLE_LOAD_ORDER:
        try:
            client.get_table(f"{dataset_ref}.{table_name}")
        except NotFound:
            missing_tables.append(table_name)

    if missing_tables:
        raise RuntimeError(
            "Faltan tablas en BigQuery: "
            + ", ".join(missing_tables)
            + ". Ejecuta primero 01_setup_bigquery.ipynb."
        )

    return dataset


def truncate_tables(
    client: bigquery.Client,
    *,
    project_id: str,
    dataset_id: str,
    location: str | None,
) -> None:
    print("\nVaciando tablas existentes...")

    for table_name in TABLE_TRUNCATE_ORDER:
        table_id = f"{project_id}.{dataset_id}.{table_name}"
        client.query(
            f"TRUNCATE TABLE `{table_id}`",
            location=location,
        ).result()
        print(f"  OK  {table_name}")


def load_dataframe(
    client: bigquery.Client,
    *,
    dataframe: pd.DataFrame,
    table_id: str,
    location: str | None,
) -> None:
    table = client.get_table(table_id)

    job_config = bigquery.LoadJobConfig(
        schema=table.schema,
        write_disposition=bigquery.WriteDisposition.WRITE_APPEND,
    )

    job = client.load_table_from_dataframe(
        dataframe,
        table_id,
        job_config=job_config,
        location=location,
    )
    job.result()


def load_all_dataframes(
    client: bigquery.Client,
    dfs: dict[str, pd.DataFrame],
    *,
    project_id: str,
    dataset_id: str,
    location: str | None,
) -> None:
    print("\nCargando DataFrames en BigQuery...")

    for table_name in TABLE_LOAD_ORDER:
        table_id = f"{project_id}.{dataset_id}.{table_name}"
        load_dataframe(
            client,
            dataframe=dfs[table_name],
            table_id=table_id,
            location=location,
        )
        print(f"  OK  {table_name}: {len(dfs[table_name]):,} filas")


def verify_bigquery_counts(
    client: bigquery.Client,
    dfs: dict[str, pd.DataFrame],
    *,
    project_id: str,
    dataset_id: str,
    location: str | None,
) -> None:
    print("\nVerificando recuentos en BigQuery...")

    for table_name in TABLE_LOAD_ORDER:
        table_id = f"{project_id}.{dataset_id}.{table_name}"
        query = f"SELECT COUNT(*) AS row_count FROM `{table_id}`"
        row = next(client.query(query, location=location).result())
        bigquery_count = int(row.row_count)
        dataframe_count = len(dfs[table_name])

        if bigquery_count != dataframe_count:
            raise RuntimeError(
                f"{table_name}: DataFrame={dataframe_count}, "
                f"BigQuery={bigquery_count}."
            )

        print(f"  OK  {table_name}: {bigquery_count:,}")


# ============================================================
# 7. CLI
# ============================================================

def positive_int(value: str) -> int:
    number = int(value)
    if number <= 0:
        raise argparse.ArgumentTypeError("Debe ser un entero positivo.")
    return number


def probability(value: str) -> float:
    number = float(value)
    if not 0 <= number <= 1:
        raise argparse.ArgumentTypeError("Debe estar entre 0 y 1.")
    return number


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description=(
            "Regenera los datos sintéticos de SkeletIA y los carga "
            "en las tablas existentes de BigQuery."
        )
    )

    parser.add_argument(
        "--project",
        help="ID del proyecto GCP. Si se omite, usa GCP_PROJECT_ID de .env.",
    )
    parser.add_argument(
        "--dataset",
        help="ID del dataset. Si se omite, usa BQ_DATASET_ID de .env.",
    )
    parser.add_argument(
        "--customers",
        type=positive_int,
        default=DEFAULT_CUSTOMERS,
        help=f"Número de clientes. Por defecto: {DEFAULT_CUSTOMERS}.",
    )
    parser.add_argument(
        "--products",
        type=positive_int,
        default=DEFAULT_PRODUCTS,
        help=f"Número de productos. Por defecto: {DEFAULT_PRODUCTS}.",
    )
    parser.add_argument(
        "--orders",
        type=positive_int,
        default=DEFAULT_ORDERS,
        help=f"Número de pedidos. Por defecto: {DEFAULT_ORDERS}.",
    )
    parser.add_argument(
        "--order-items",
        type=positive_int,
        default=None,
        help=(
            "Número exacto de líneas de pedido. Debe estar entre 2 y 3 "
            "por pedido. Si se omite, usa 2.25 líneas por pedido."
        ),
    )
    parser.add_argument(
        "--review-probability",
        type=probability,
        default=DEFAULT_REVIEW_PROBABILITY,
        help=(
            "Probabilidad de review por línea de pedido entregado. "
            f"Por defecto: {DEFAULT_REVIEW_PROBABILITY}."
        ),
    )
    parser.add_argument(
        "--seed",
        type=int,
        default=DEFAULT_SEED,
        help=f"Semilla aleatoria. Por defecto: {DEFAULT_SEED}.",
    )
    parser.add_argument(
        "--credentials",
        help=(
            "Ruta opcional al JSON del Service Account. Si se omite, "
            "usa GOOGLE_APPLICATION_CREDENTIALS de .env."
        ),
    )
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="Genera y valida los datos, pero no modifica BigQuery.",
    )

    return parser.parse_args()


def print_generation_summary(dfs: dict[str, pd.DataFrame]) -> None:
    delivered_order_ids = set(
        dfs["orders"].loc[dfs["orders"]["status"] == "delivered", "order_id"]
    )
    delivered_items = int(
        dfs["order_items"]["order_id"].isin(delivered_order_ids).sum()
    )
    review_rate = (
        100 * len(dfs["reviews"]) / delivered_items
        if delivered_items
        else 0.0
    )
    avg_items = len(dfs["order_items"]) / len(dfs["orders"])

    print("\nResumen generado")
    print("----------------")
    for table_name in TABLE_LOAD_ORDER:
        print(f"{table_name:22s} {len(dfs[table_name]):>7,}")

    print(f"\nMedia líneas/pedido: {avg_items:.2f}")
    print(f"Reviews sobre líneas entregadas: {review_rate:.2f} %")

    methods = (
        dfs["payments"]["payment_method"]
        .value_counts(normalize=True)
        .mul(100)
        .sort_values(ascending=False)
    )

    print("\nMétodos de pago")
    print("---------------")
    for method, pct in methods.items():
        print(f"{method:22s} {pct:6.2f} %")


def main() -> int:
    args = parse_args()

    root_dir = Path(__file__).resolve().parent
    load_dotenv(root_dir / ".env")

    project_id = args.project or os.getenv("GCP_PROJECT_ID")
    dataset_id = args.dataset or os.getenv("BQ_DATASET_ID")

    if not project_id:
        print(
            "ERROR: falta --project o GCP_PROJECT_ID en .env.",
            file=sys.stderr,
        )
        return 2

    if not dataset_id:
        print(
            "ERROR: falta --dataset o BQ_DATASET_ID en .env.",
            file=sys.stderr,
        )
        return 2

    order_items = args.order_items or expected_order_items(args.orders)

    minimum_items = args.orders * 2
    maximum_items = args.orders * 3

    if not minimum_items <= order_items <= maximum_items:
        print(
            "ERROR: --order-items debe estar entre "
            f"{minimum_items} y {maximum_items} para {args.orders} pedidos.",
            file=sys.stderr,
        )
        return 2

    if args.products < 3:
        print("ERROR: --products debe ser al menos 3.", file=sys.stderr)
        return 2

    # Los valores por defecto cumplen exactamente los mínimos del enunciado.
    if args.customers < 500:
        print("AVISO: el enunciado exige al menos 500 clientes.")
    if args.products < 70:
        print("AVISO: el enunciado exige al menos 70 productos.")
    if args.orders < 2_000:
        print("AVISO: el enunciado exige al menos 2.000 pedidos.")

    print("SkeletIA seed")
    print("=============")
    print(f"Proyecto:           {project_id}")
    print(f"Dataset:            {dataset_id}")
    print(f"Clientes:           {args.customers:,}")
    print(f"Productos:          {args.products:,}")
    print(f"Pedidos:            {args.orders:,}")
    print(f"Líneas de pedido:   {order_items:,}")
    print(f"Prob. reviews:      {args.review_probability:.0%}")
    print(f"Semilla:            {args.seed}")

    try:
        dfs = build_dataframes(
            customers=args.customers,
            products=args.products,
            orders=args.orders,
            order_items=order_items,
            review_probability=args.review_probability,
            seed=args.seed,
        )

        validate_dataframes(
            dfs,
            expected_customers=args.customers,
            expected_products=args.products,
            expected_orders=args.orders,
            expected_order_items_count=order_items,
            review_probability=args.review_probability,
        )

        print("\nValidaciones locales: OK")
        print_generation_summary(dfs)

        if args.dry_run:
            print("\nDry-run finalizado: BigQuery no se ha modificado.")
            return 0

        configure_credentials(root_dir, args.credentials)

        client = bigquery.Client(project=project_id)
        dataset = validate_bigquery_structure(
            client,
            project_id=project_id,
            dataset_id=dataset_id,
        )

        truncate_tables(
            client,
            project_id=project_id,
            dataset_id=dataset_id,
            location=dataset.location,
        )

        load_all_dataframes(
            client,
            dfs,
            project_id=project_id,
            dataset_id=dataset_id,
            location=dataset.location,
        )

        verify_bigquery_counts(
            client,
            dfs,
            project_id=project_id,
            dataset_id=dataset_id,
            location=dataset.location,
        )

    except Exception as exc:
        print(f"\nERROR: {exc}", file=sys.stderr)
        return 1

    print("\nSeed completado correctamente.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
