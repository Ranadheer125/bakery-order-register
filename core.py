"""Core logic shared by the terminal app (cli.py) and the web app (server.py).
Standard library only: validation, JSON persistence, search, summary, exports, import."""
import csv, io, json, os, re, random, threading
from datetime import date, timedelta

BASE = os.path.dirname(os.path.abspath(__file__))
DATA_FILE = os.path.join(BASE, "data", "orders.json")
LOCK = threading.Lock()
CATEGORIES = ["Cake", "Cupcakes", "Pastry", "Bread", "Cookies", "Custom"]
FIELDS = ["id", "customer", "phone", "item", "category", "quantity", "unit_price", "total",
          "order_date", "pickup_date", "amount_paid", "payment_status", "picked_up", "notes"]

# ---------- validation ----------
class ValidationError(Exception):
    def __init__(self, errors): self.errors = errors

def parse_date(s):
    try: return date.fromisoformat(str(s))
    except ValueError: return None

def validate(raw, existing=None):
    """Return a clean order dict or raise ValidationError({field: message})."""
    e, o = {}, {}
    o["customer"] = re.sub(r"\s+", " ", str(raw.get("customer", ""))).strip()
    if not 2 <= len(o["customer"]) <= 60: e["customer"] = "Enter a name of 2 to 60 characters."
    phone = re.sub(r"[\s\-]", "", str(raw.get("phone", "")))
    phone = re.sub(r"^(\+91|0)", "", phone)
    o["phone"] = phone
    if not re.fullmatch(r"[6-9]\d{9}", phone): e["phone"] = "Enter a 10-digit mobile number."
    o["item"] = str(raw.get("item", "")).strip()
    if not 2 <= len(o["item"]) <= 80: e["item"] = "Describe the item in 2 to 80 characters."
    o["category"] = str(raw.get("category", ""))
    if o["category"] not in CATEGORIES: e["category"] = "Choose a category from the list."
    try:
        o["quantity"] = int(raw.get("quantity"))
        if not 1 <= o["quantity"] <= 100: raise ValueError
    except (TypeError, ValueError): e["quantity"] = "Quantity must be a whole number from 1 to 100."
    try:
        o["unit_price"] = round(float(raw.get("unit_price")), 2)
        if not 0 < o["unit_price"] <= 50000: raise ValueError
    except (TypeError, ValueError): e["unit_price"] = "Price must be above 0 and at most 50,000."
    od, pd = parse_date(raw.get("order_date") or date.today().isoformat()), parse_date(raw.get("pickup_date"))
    if not od: e["order_date"] = "Use the format YYYY-MM-DD."
    if not pd: e["pickup_date"] = "Pick a pickup date."
    elif od and pd < od: e["pickup_date"] = "Pickup can't be before the order date."
    o["order_date"] = od.isoformat() if od else ""
    o["pickup_date"] = pd.isoformat() if pd else ""
    if "quantity" in o and "unit_price" in o:
        o["total"] = round(o["quantity"] * o["unit_price"], 2)
        try:
            paid = raw.get("amount_paid", 0)
            o["amount_paid"] = round(float(paid if paid not in ("", None) else 0), 2)
            if not 0 <= o["amount_paid"] <= o["total"]:
                e["amount_paid"] = f"Amount paid must be between 0 and {o['total']:.2f}."
        except (TypeError, ValueError): e["amount_paid"] = "Amount paid must be a number."
        if "amount_paid" in o:
            o["payment_status"] = ("Paid" if o["amount_paid"] >= o["total"] else
                                   "Partial" if o["amount_paid"] > 0 else "Unpaid")
    o["picked_up"] = str(raw.get("picked_up", False)).lower() in ("true", "1", "yes")
    o["notes"] = str(raw.get("notes", "")).strip()[:200]
    if e: raise ValidationError(e)
    return o

# ---------- storage ----------
def seed_orders():
    random.seed(87)
    names = ["Asha Reddy", "Ravi Kumar", "Priya Sharma", "Imran Khan", "Meera Nair", "Suresh Babu",
             "Lakshmi Devi", "Arjun Rao", "Fatima Begum", "Kiran Patel", "Divya Menon", "Anil Verma"]
    items = [("Black Forest Cake 1kg", "Cake", 850), ("Red Velvet Cake 500g", "Cake", 520),
             ("Chocolate Cupcakes (box of 6)", "Cupcakes", 360), ("Almond Croissant", "Pastry", 90),
             ("Whole Wheat Loaf", "Bread", 70), ("Butter Cookies 250g", "Cookies", 180),
             ("Custom Birthday Cake 2kg", "Custom", 1900), ("Pineapple Pastry", "Pastry", 60)]
    today, out = date.today(), []
    for i in range(1, 41):
        it = random.choice(items); qty = random.choice([1, 1, 2, 3, 6, 12])
        od = today - timedelta(days=random.randint(0, 20))
        pd = od + timedelta(days=random.randint(1, 12)); total = qty * it[2]
        picked = pd < today and random.random() < .85
        paid = total if picked and random.random() < .9 else random.choice([0, total, total, round(total / 2)])
        out.append(dict(id=i, customer=random.choice(names), phone="9" + "".join(random.choices("0123456789", k=9)),
            item=it[0], category=it[1], quantity=qty, unit_price=float(it[2]), total=float(total),
            order_date=od.isoformat(), pickup_date=pd.isoformat(), amount_paid=float(paid),
            payment_status="Paid" if paid >= total else "Partial" if paid else "Unpaid",
            picked_up=picked, notes=""))
    # edge cases for validation / warning demos
    out[2].update(picked_up=True, amount_paid=0.0, payment_status="Unpaid", notes="Anomaly: collected but unpaid")
    out[3].update(pickup_date=(today + timedelta(days=120)).isoformat(), notes="Anomaly: pickup 120 days away")
    out[0].update(pickup_date=out[0]["order_date"], notes="Same-day pickup")
    out[1].update(quantity=100, total=100 * out[1]["unit_price"], amount_paid=0.0, payment_status="Unpaid",
                  notes="Boundary: max quantity", picked_up=False)
    return out

def load():
    try:
        with open(DATA_FILE, encoding="utf-8") as f:
            data = json.load(f)
        if not isinstance(data, list): raise ValueError
        return data
    except (FileNotFoundError, json.JSONDecodeError, ValueError) as ex:
        if os.path.exists(DATA_FILE):  # keep corrupted file for inspection
            os.replace(DATA_FILE, DATA_FILE + ".corrupt")
        data = seed_orders(); save(data); return data

def save(orders):
    os.makedirs(os.path.dirname(DATA_FILE), exist_ok=True)
    tmp = DATA_FILE + ".tmp"
    with open(tmp, "w", encoding="utf-8") as f: json.dump(orders, f, indent=2)
    os.replace(tmp, DATA_FILE)

# ---------- business logic ----------
def flag(o, today=None):
    today = today or date.today()
    pd = parse_date(o["pickup_date"])
    if o["picked_up"]: return None
    if pd and pd < today: return "overdue"
    if pd and pd == today: return "due-today"
    if pd and pd <= today + timedelta(days=2): return "due-soon"
    return None

def anomalies(o):
    w = []
    if o["quantity"] >= 50: w.append("Unusually large quantity")
    if o["total"] >= 20000: w.append("High-value order")
    od, pd = parse_date(o["order_date"]), parse_date(o["pickup_date"])
    if od and pd and (pd - od).days > 90: w.append("Pickup more than 90 days after order")
    if o["picked_up"] and o["payment_status"] != "Paid": w.append("Collected but not fully paid")
    return w

def with_flags(orders):
    return [dict(o, flag=flag(o), warnings=anomalies(o), balance=round(o["total"] - o["amount_paid"], 2)) for o in orders]

def search(orders, q="", status="", category="", pickup=""):
    q = q.lower().strip(); res = []
    for o in with_flags(orders):
        if q and q not in " ".join(str(o[k]) for k in ("customer", "phone", "item", "notes")).lower(): continue
        if status and o["payment_status"] != status: continue
        if category and o["category"] != category: continue
        if pickup == "open" and o["picked_up"]: continue
        if pickup == "done" and not o["picked_up"]: continue
        if pickup == "overdue" and o["flag"] != "overdue": continue
        res.append(o)
    return sorted(res, key=lambda o: (o["picked_up"], o["pickup_date"]))

def summary(orders):
    fo = with_flags(orders); n = len(fo)
    revenue = sum(o["total"] for o in fo); collected = sum(o["amount_paid"] for o in fo)
    by_cat = {}
    for o in fo:
        c = by_cat.setdefault(o["category"], {"orders": 0, "revenue": 0.0}); c["orders"] += 1; c["revenue"] += o["total"]
    by_day = {}
    for o in fo: by_day[o["pickup_date"]] = by_day.get(o["pickup_date"], 0) + 1
    upcoming = sorted((d, c) for d, c in by_day.items() if d >= date.today().isoformat())[:7]
    cust = {}
    for o in fo: cust[o["customer"]] = cust.get(o["customer"], 0) + o["total"]
    top = sorted(cust.items(), key=lambda x: -x[1])[:3]
    return {"orders": n, "revenue": round(revenue, 2), "collected": round(collected, 2),
            "outstanding": round(revenue - collected, 2), "average_order": round(revenue / n, 2) if n else 0,
            "paid": sum(o["payment_status"] == "Paid" for o in fo), "partial": sum(o["payment_status"] == "Partial" for o in fo),
            "unpaid": sum(o["payment_status"] == "Unpaid" for o in fo),
            "overdue": sum(o["flag"] == "overdue" for o in fo), "due_today": sum(o["flag"] == "due-today" for o in fo),
            "awaiting_pickup": sum(not o["picked_up"] for o in fo), "anomalies": sum(bool(o["warnings"]) for o in fo),
            "by_category": {k: {"orders": v["orders"], "revenue": round(v["revenue"], 2)} for k, v in by_cat.items()},
            "upcoming": upcoming, "top_customers": top}

def export(orders, fmt):
    if fmt == "csv":
        buf = io.StringIO(); w = csv.DictWriter(buf, FIELDS); w.writeheader()
        for o in orders: w.writerow({k: o.get(k, "") for k in FIELDS})
        return buf.getvalue(), "text/csv", "bakery_orders.csv"
    s = summary(orders); today = date.today().isoformat()
    if fmt == "md":
        t = f"# Bakery Order Report ({today})\n\n| Metric | Value |\n|---|---|\n"
        for k in ("orders", "revenue", "collected", "outstanding", "average_order", "overdue", "awaiting_pickup"):
            t += f"| {k.replace('_', ' ').title()} | {s[k]} |\n"
        t += "\n## By category\n\n| Category | Orders | Revenue |\n|---|---|---|\n"
        for c, v in s["by_category"].items(): t += f"| {c} | {v['orders']} | {v['revenue']} |\n"
        t += "\n## Orders\n\n| ID | Customer | Item | Pickup | Total | Payment |\n|---|---|---|---|---|---|\n"
        for o in orders: t += f"| {o['id']} | {o['customer']} | {o['item']} | {o['pickup_date']} | {o['total']} | {o['payment_status']} |\n"
        return t, "text/markdown", "bakery_report.md"
    t = f"BAKERY ORDER AUDIT LOG - {today}\n" + "=" * 50 + "\n"
    for o in orders:
        t += f"#{o['id']:<4} {o['customer']:<18} {o['item'][:28]:<28} pickup {o['pickup_date']} {o['payment_status']:<8} {o['total']:>9.2f}\n"
    t += "=" * 50 + f"\nOrders: {s['orders']}  Revenue: {s['revenue']}  Outstanding: {s['outstanding']}\n"
    return t, "text/plain", "bakery_audit.txt"

def bulk_import(orders, text):
    """Import legacy CSV. Returns (added, row-by-row error log)."""
    added, log = 0, []
    reader = csv.DictReader(io.StringIO(text))
    need = {"customer", "phone", "item", "category", "quantity", "unit_price", "pickup_date"}
    if not reader.fieldnames or not need <= set(reader.fieldnames):
        return 0, [f"Missing columns: {', '.join(sorted(need - set(reader.fieldnames or [])))}"]
    nid = max((o["id"] for o in orders), default=0) + 1
    for i, row in enumerate(reader, start=2):
        try:
            o = validate(row); o["id"] = nid; nid += 1; orders.append(o); added += 1
        except ValidationError as ve:
            log.append(f"Row {i}: " + "; ".join(f"{k}: {m}" for k, m in ve.errors.items()))
    return added, log


# ---------- helpers used by the terminal app ----------
_DEFAULTS = dict(customer="Aa", phone="9999999999", item="Aa", category="Cake", quantity=1, unit_price=1,
                 pickup_date="2999-01-01", amount_paid=0)

def field_error(raw, name, value):
    """Validate one field in the context of what has been entered so far. Returns message or None."""
    ctx = {**_DEFAULTS, "order_date": date.today().isoformat(), **raw, name: value}
    try: validate(ctx); return None
    except ValidationError as ve: return ve.errors.get(name)

def write_exports(orders, folder=None):
    folder = folder or os.path.join(BASE, "exports"); os.makedirs(folder, exist_ok=True); paths = []
    for fmt in ("csv", "md", "txt"):
        text, _, name = export(orders, fmt); p = os.path.join(folder, name)
        with open(p, "w", encoding="utf-8", newline="") as f: f.write(text)
        paths.append(p)
    return paths

def write_sample_files(folder=None):
    folder = folder or os.path.join(BASE, "sample_data"); os.makedirs(folder, exist_ok=True)
    data = seed_orders()
    with open(os.path.join(folder, "sample_orders.json"), "w", encoding="utf-8") as f: json.dump(data, f, indent=2)
    with open(os.path.join(folder, "sample_orders.csv"), "w", encoding="utf-8", newline="") as f:
        w = csv.DictWriter(f, FIELDS); w.writeheader(); w.writerows(data)

def chart_png(orders, path=None):
    """Revenue-by-category bar chart. Needs matplotlib (optional); returns path or None."""
    try:
        import matplotlib; matplotlib.use("Agg"); import matplotlib.pyplot as plt
    except ImportError: return None
    s = summary(orders)["by_category"]; path = path or os.path.join(BASE, "exports", "revenue_by_category.png")
    os.makedirs(os.path.dirname(path), exist_ok=True)
    plt.figure(figsize=(7, 4)); plt.bar(list(s), [v["revenue"] for v in s.values()], color="#b3245b")
    plt.title("Revenue by category"); plt.ylabel("Rupees"); plt.tight_layout(); plt.savefig(path); plt.close()
    return path
