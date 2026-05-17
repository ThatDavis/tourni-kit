import csv
from decimal import Decimal
from pathlib import Path
from sqlalchemy.orm import Session
from app.models import Category, Item


def seed_from_csv(db: Session, csv_path: Path):
    if db.query(Item).count() > 0:
        return False

    category_map = {}

    with open(csv_path, newline="", encoding="utf-8") as f:
        reader = csv.DictReader(f)
        for row in reader:
            cat_name = row.get("category", "").strip()
            item_name = row.get("name", "").strip()
            if not cat_name or not item_name:
                continue

            if cat_name not in category_map:
                cat = Category(name=cat_name, sort_order=len(category_map))
                db.add(cat)
                db.flush()
                category_map[cat_name] = cat
            else:
                cat = category_map[cat_name]

            needed = int(row.get("needed_per_kit", 1) or 1)
            cost_pp = Decimal(row.get("cost_per_package", "0") or "0")
            qpp = int(row.get("qty_per_package", 1) or 1)
            cpu = cost_pp / Decimal(qpp) if qpp > 0 and cost_pp > 0 else Decimal("0")

            item = Item(
                category_id=cat.id,
                name=item_name,
                needed_per_kit=needed,
                source=row.get("source", "").strip(),
                cost_per_package=cost_pp,
                qty_per_package=qpp,
                cost_per_unit=cpu,
                current_stock=0,
            )
            db.add(item)

    db.commit()
    return True
