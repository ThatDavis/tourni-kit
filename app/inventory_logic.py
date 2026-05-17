from decimal import Decimal
from sqlalchemy.orm import Session
from app.models import Category, Item, InventoryTransaction


def get_kit_math(db: Session):
    """
    current_stock is stored as TOTAL INDIVIDUAL UNITS on hand.
    needed_per_kit is also in individual units.
    """
    categories = db.query(Category).order_by(Category.sort_order).all()
    per_category = []
    category_maxes = []
    total_cost_no_stb = Decimal("0")
    total_cost_with_stb = Decimal("0")

    for cat in categories:
        cat_entries = []
        cat_max = None
        cat_cost = Decimal("0")
        for item in cat.item_list:
            needed = item.needed_per_kit or 1
            stock = item.current_stock or 0
            kits_possible = stock // needed if needed > 0 else 0
            if cat_max is None:
                cat_max = kits_possible
            else:
                cat_max = min(cat_max, kits_possible)
            cat_cost += (item.cost_per_unit or Decimal("0")) * needed
            cat_entries.append({
                "item": item,
                "kits_possible": kits_possible,
            })
        if cat_max is None:
            cat_max = 0
        category_maxes.append(cat_max)
        per_category.append({
            "category": cat,
            "entries": cat_entries,
            "max_kits": cat_max,
            "cost": cat_cost,
        })
        if cat.name.lower() == "stop the bleed":
            total_cost_with_stb += cat_cost
        else:
            total_cost_no_stb += cat_cost
            total_cost_with_stb += cat_cost

    global_max = min(category_maxes) if category_maxes else 0

    # Compute max kits excluding Stop The Bleed
    non_stb_maxes = []
    for cat_data in per_category:
        if cat_data["category"].name.lower() != "stop the bleed":
            non_stb_maxes.append(cat_data["max_kits"])
    global_max_no_stb = min(non_stb_maxes) if non_stb_maxes else 0

    return {
        "per_category": per_category,
        "global_max_kits": global_max,
        "global_max_kits_no_stb": global_max_no_stb,
        "cost_no_stb": total_cost_no_stb,
        "cost_with_stb": total_cost_with_stb,
    }


def consume_kit_stock(db: Session, user_id: int, note: str = "kit build"):
    """
    Consumes one kit's worth of inventory. current_stock = total individual units.
    Returns True if successful, False if insufficient stock.
    """
    math = get_kit_math(db)
    if math["global_max_kits"] < 1:
        return False

    for cat_data in math["per_category"]:
        for item_data in cat_data["entries"]:
            item = item_data["item"]
            needed = item.needed_per_kit or 1
            if item.current_stock < needed:
                return False

    for cat_data in math["per_category"]:
        for item_data in cat_data["entries"]:
            item = item_data["item"]
            needed = item.needed_per_kit or 1
            item.current_stock -= needed
            db.add(item)
            tx = InventoryTransaction(
                item_id=item.id,
                user_id=user_id,
                delta=-needed,
                new_stock=item.current_stock,
                reason="build_consumption",
                note=note,
            )
            db.add(tx)
    db.commit()
    return True


def add_inventory(db: Session, item_id: int, user_id: int, packages: int, reason: str = "purchase", note: str = ""):
    """
    Adds inventory by package count. Computes total units from packages * qty_per_package.
    """
    item = db.query(Item).filter(Item.id == item_id).first()
    if not item:
        return None
    total_units = packages * (item.qty_per_package or 1)
    item.current_stock = (item.current_stock or 0) + total_units
    db.add(item)
    tx = InventoryTransaction(
        item_id=item.id,
        user_id=user_id,
        delta=total_units,
        new_stock=item.current_stock,
        reason=reason,
        note=note,
    )
    db.add(tx)
    db.commit()
    return item
