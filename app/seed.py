import csv
from decimal import Decimal, InvalidOperation
from pathlib import Path
from sqlalchemy.orm import Session
from app.models import Category, Item


def _clean_decimal(val):
    if not val:
        return Decimal("0")
    val = str(val).replace(",", "").strip()
    try:
        return Decimal(val)
    except InvalidOperation:
        return Decimal("0")


def _clean_int(val):
    if not val:
        return 0
    val = str(val).strip()
    try:
        return int(float(val))
    except (ValueError, TypeError):
        return 0


def seed_from_csv(db: Session, csv_path: Path):
    if db.query(Item).count() > 0:
        return False

    categories = []
    current_category = None
    done = False

    with open(csv_path, newline="", encoding="utf-8") as f:
        reader = csv.reader(f)
        for row in reader:
            if not row:
                continue
            first = row[0].strip()
            if done:
                continue

            if first.lower() == "civil defense ifak":
                done = True
                continue

            if first in ("Stop The Bleed", "OTC Meds", "Hygiene/Wound Care", "Boo Boo", "Misc"):
                current_category = Category(name=first, sort_order=len(categories))
                db.add(current_category)
                db.flush()
                categories.append(current_category)
                continue

            if current_category is None:
                continue
            if first == "Item":
                continue
            if first == "":
                continue

            lowered = first.lower()
            if lowered.startswith("total") or lowered.startswith("max full"):
                continue
            if "total / person" in lowered:
                continue
            if "cost / kit" in lowered:
                continue
            if lowered in ("w/ stb total / person", "no stb + coverage total / person"):
                continue
            if any(lowered.endswith(f" x{n}") for n in ["1", "2", "4", "6"]):
                continue

            if len(row) < 6:
                continue

            name = first
            needed_per_kit = _clean_int(row[1]) if len(row) > 1 else 1
            source = row[2] if len(row) > 2 else ""
            cost_per_package = _clean_decimal(row[3]) if len(row) > 3 else Decimal("0")
            units = _clean_int(row[4]) if len(row) > 4 else 1
            amount_per_unit = _clean_int(row[5]) if len(row) > 5 else 1
            qty_per_package = units * amount_per_unit if units and amount_per_unit else 1

            if qty_per_package > 0 and cost_per_package > 0:
                cost_per_unit = cost_per_package / Decimal(qty_per_package)
            else:
                cost_per_unit = Decimal("0")

            item = Item(
                category_id=current_category.id,
                name=name,
                needed_per_kit=needed_per_kit or 1,
                source=source,
                cost_per_package=cost_per_package,
                qty_per_package=qty_per_package,
                cost_per_unit=cost_per_unit,
                current_stock=0,
            )
            db.add(item)

    db.commit()
    return True
