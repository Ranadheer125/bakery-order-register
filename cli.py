"""Bakery Order Register - interactive terminal app.   Run:  python cli.py"""
import os, sys
from datetime import date
import core

C = {"b": "\033[1m", "r": "\033[31m", "g": "\033[32m", "y": "\033[33m", "m": "\033[35m", "c": "\033[36m", "d": "\033[2m", "x": "\033[0m"}
if not sys.stdout.isatty() and not os.environ.get("FORCE_COLOR"): C = dict.fromkeys(C, "")
col = lambda k, s: f"{C[k]}{s}{C['x']}"
money = lambda n: f"Rs {n:,.2f}"
PAGE = 10

def banner():
    print(col("m", r"""
  ____        _                   ___          _             ____            _     _
 | __ )  __ _| | _____ _ __ _   _/ _ \ _ __ __| | ___ _ __  |  _ \ ___  __ _(_)___| |_ ___ _ __
 |  _ \ / _` | |/ / _ \ '__| | | | | | '__/ _` |/ _ \ '__| | |_) / _ \/ _` | / __| __/ _ \ '__|
 | |_) | (_| |   <  __/ |  | |_| | |_| | | (_| |  __/ |    |  _ <  __/ (_| | \__ \ ||  __/ |
 |____/ \__,_|_|\_\___|_|   \__, |\___/|_|  \__,_|\___|_|    |_| \_\___|\__, |_|___/\__\___|_|
                            |___/                                       |___/""".rstrip()))
    print(col("d", "  Cake & bakery orders, pickup dates and payments - data saved in data/orders.json\n"))

# ---------- centralised input wrappers: loop until valid ----------
def ask(label, field=None, raw=None, default=None, allow_blank=False):
    while True:
        hint = f" [{default}]" if default not in (None, "") else ""
        try: v = input(f"  {label}{hint}: ").strip()
        except EOFError: raise SystemExit
        if v == "" and default is not None: v = str(default)
        if v == "" and allow_blank: return v
        err = core.field_error(raw or {}, field, v) if field else (None if v else "This can't be blank.")
        if err: print(col("r", f"    x {err}")); continue
        return v

def choose(label, options):
    for i, o in enumerate(options, 1): print(f"    {i}. {o}")
    while True:
        v = input(f"  {label} (number or name): ").strip()
        if v.isdigit() and 1 <= int(v) <= len(options): return options[int(v) - 1]
        m = [o for o in options if o.lower() == v.lower()]
        if m: return m[0]
        print(col("r", f"    x Choose 1-{len(options)}."))

def confirm(q): return input(f"  {q} (y/n): ").strip().lower() in ("y", "yes")
def pause(): input(col("d", "\n  Press Enter to continue..."))

def pick_id(orders):
    ids = {o["id"] for o in orders}
    while True:
        v = input("  Order # (blank to cancel): ").strip()
        if v == "": return None
        if v.isdigit() and int(v) in ids: return int(v)
        print(col("r", "    x No order with that number."))

# ---------- display ----------
def table(rows, page_size=PAGE):
    if not rows: print(col("y", "  No orders found.")); return
    head = f"  {'#':>3} {'Customer':<16} {'Item':<26} {'Qty':>3} {'Pickup':<10} {'Total':>10} {'Payment':<8} Status"
    pages = (len(rows) + page_size - 1) // page_size; p = 0
    while True:
        print(col("b", head)); print("  " + "-" * (len(head) - 2))
        for o in rows[p * page_size:(p + 1) * page_size]:
            st = ("Picked up" if o["picked_up"] else {"overdue": col("r", "OVERDUE"), "due-today": col("y", "DUE TODAY"), "due-soon": col("y", "due soon")}.get(o["flag"], "waiting"))
            pc = {"Paid": "g", "Partial": "y", "Unpaid": "r"}[o["payment_status"]]
            flag = col("r", " !") if o["warnings"] else ""
            pay = col(pc, o["payment_status"].ljust(8))
            print(f"  {o['id']:>3} {o['customer'][:16]:<16} {o['item'][:26]:<26} {o['quantity']:>3} {o['pickup_date']:<10} {o['total']:>10,.2f} {pay} {st}{flag}")
        print(col("d", f"  Page {p + 1}/{pages} - {len(rows)} orders"))
        if pages == 1: return
        k = input("  [n]ext  [p]revious  [q]uit list: ").strip().lower()
        if k == "n" and p < pages - 1: p += 1
        elif k == "p" and p > 0: p -= 1
        elif k == "q": return

def bar(v, mx, w=30): return "#" * int(w * v / mx) if mx else ""

def show_summary(orders):
    s = core.summary(orders)
    print(col("b", "\n  EXECUTIVE SUMMARY"))
    for k, v in [("Orders", s["orders"]), ("Order value", money(s["revenue"])), ("Collected", money(s["collected"])),
                 ("Still owed", money(s["outstanding"])), ("Average order", money(s["average_order"])),
                 ("Paid / Partial / Unpaid", f"{s['paid']} / {s['partial']} / {s['unpaid']}"),
                 ("Awaiting pickup", s["awaiting_pickup"]), ("Overdue", s["overdue"]), ("Due today", s["due_today"])]:
        print(f"  {k:<26}{v}")
    print(col("b", "\n  Revenue by category"))
    mx = max((v["revenue"] for v in s["by_category"].values()), default=0)
    for c, v in sorted(s["by_category"].items(), key=lambda x: -x[1]["revenue"]):
        print(f"  {c:<10}{v['orders']:>3} orders {v['revenue']:>11,.2f}  {col('m', bar(v['revenue'], mx))}")
    print(col("b", "\n  Upcoming pickups (next 7 days with orders)"))
    for d, n in s["upcoming"]: print(f"  {d}  {n} order(s)")
    print(col("b", "\n  Top customers"))
    for n, v in s["top_customers"]: print(f"  {n:<20}{money(v)}")

def show_warnings(orders):
    fo = core.with_flags(orders); hit = False
    print(col("b", "\n  WARNINGS"))
    for o in fo:
        msgs = ([{"overdue": "OVERDUE - pickup date has passed", "due-today": "Due for pickup today"}[o["flag"]]] if o["flag"] in ("overdue", "due-today") else []) + o["warnings"]
        if o["payment_status"] == "Unpaid" and not o["picked_up"]: msgs.append("No payment received")
        for m in msgs: hit = True; print(f"  {col('r', '!')} #{o['id']:<3} {o['customer'][:18]:<18} {m}")
    if not hit: print(col("g", "  Nothing needs attention."))

# ---------- actions ----------
def add_order(orders):
    print(col("b", "\n  NEW ORDER") + col("d", "  (invalid answers are rejected and asked again)"))
    raw = {}
    raw["customer"] = ask("Customer name", "customer", raw)
    raw["phone"] = ask("Mobile number (10 digits)", "phone", raw)
    raw["item"] = ask("Item (e.g. Black Forest Cake 1kg)", "item", raw)
    raw["category"] = choose("Category", core.CATEGORIES)
    raw["quantity"] = ask("Quantity (1-100)", "quantity", raw, default=1)
    raw["unit_price"] = ask("Price each", "unit_price", raw)
    raw["order_date"] = ask("Order date YYYY-MM-DD", "order_date", raw, default=date.today().isoformat())
    raw["pickup_date"] = ask("Pickup date YYYY-MM-DD", "pickup_date", raw)
    total = int(raw["quantity"]) * float(raw["unit_price"])
    raw["amount_paid"] = ask(f"Amount paid now (total {total:,.2f})", "amount_paid", raw, default=0)
    raw["notes"] = ask("Notes (optional)", raw=raw, allow_blank=True)
    o = core.validate(raw); o["id"] = max((x["id"] for x in orders), default=0) + 1
    orders.append(o); core.save(orders)
    print(col("g", f"\n  Saved order #{o['id']} for {o['customer']} - total {money(o['total'])}, {o['payment_status']}."))

def list_orders(orders): table(core.search(orders))

def search_orders(orders):
    print(col("b", "\n  SEARCH & FILTER") + col("d", "  (leave a filter blank to skip it)"))
    q = input("  Keyword (name, phone, item, notes): ").strip()
    cat = input(f"  Category {core.CATEGORIES}: ").strip().title()
    st = input("  Payment (Paid/Partial/Unpaid): ").strip().title()
    pk = input("  Pickup (open/overdue/done): ").strip().lower()
    table(core.search(orders, q, st if st in ("Paid", "Partial", "Unpaid") else "", cat if cat in core.CATEGORIES else "", pk))

def update_payment(orders):
    i = pick_id(orders)
    if i is None: return
    o = next(x for x in orders if x["id"] == i)
    print(f"  {o['customer']} owes {money(o['total'] - o['amount_paid'])} of {money(o['total'])}.")
    raw = dict(o); raw["amount_paid"] = ask("New total amount paid", "amount_paid", raw, default=o["total"])
    o.update(core.validate(raw)); core.save(orders); print(col("g", f"  Payment status: {o['payment_status']}."))

def mark_picked(orders):
    i = pick_id(orders)
    if i is None: return
    o = next(x for x in orders if x["id"] == i); o["picked_up"] = True; core.save(orders)
    print(col("g", f"  Order #{i} marked as picked up.") + (col("y", " Note: it is not fully paid.") if o["payment_status"] != "Paid" else ""))

def delete_order(orders):
    i = pick_id(orders)
    if i is None: return
    if confirm(f"Delete order #{i}?"): orders[:] = [o for o in orders if o["id"] != i]; core.save(orders); print(col("g", "  Deleted."))

def export_reports(orders):
    for p in core.write_exports(orders): print(col("g", f"  Wrote {os.path.relpath(p)}"))

def make_chart(orders):
    p = core.chart_png(orders)
    print(col("g", f"  Chart saved to {os.path.relpath(p)}") if p else col("y", "  Chart needs matplotlib:  pip install matplotlib  (the text chart in Summary works without it)."))

def import_csv(orders):
    path = input("  Path to CSV file (try sample_data/legacy_import_sample.csv): ").strip().strip('"')
    try:
        with open(path, encoding="utf-8-sig") as f: text = f.read()
    except OSError as e: print(col("r", f"  x Can't read file: {e.strerror}")); return
    added, log = core.bulk_import(orders, text); core.save(orders)
    print(col("g", f"  Imported {added} row(s).") + col("r", f"  Rejected {len(log)}.") if log else col("g", f"  Imported {added} row(s)."))
    for line in log: print(col("r", "   " + line))
    if log:
        lp = os.path.join(core.BASE, "exports", "import_errors.log"); os.makedirs(os.path.dirname(lp), exist_ok=True)
        open(lp, "w", encoding="utf-8").write("\n".join(log)); print(col("d", f"  Error log: {os.path.relpath(lp)}"))

MENU = [("Add new order", add_order), ("View all orders", list_orders), ("Search / filter orders", search_orders),
        ("Update payment", update_payment), ("Mark order picked up", mark_picked), ("Delete order", delete_order),
        ("Summary dashboard", lambda o: show_summary(o)), ("Warnings (overdue, unpaid, anomalies)", show_warnings),
        ("Export reports (CSV, Markdown, audit log)", export_reports), ("Import legacy CSV", import_csv), ("Save chart image", make_chart)]

def main():
    orders = core.load(); banner(); core_warn = core.summary(orders)
    if core_warn["overdue"] or core_warn["due_today"]:
        print(col("y", f"  ! {core_warn['overdue']} overdue and {core_warn['due_today']} due-today order(s). Choose 8 to see them.\n"))
    while True:
        print(col("b", "  MAIN MENU"))
        for i, (n, _) in enumerate(MENU, 1): print(f"  {i:>2}. {n}")
        print("   0. Exit")
        c = input(col("c", "\n  Choose an option: ")).strip()
        if c == "0": print(col("m", "  Goodbye! Your orders are saved.")); return
        if c.isdigit() and 1 <= int(c) <= len(MENU):
            try: MENU[int(c) - 1][1](orders)
            except KeyboardInterrupt: print(col("y", "\n  Cancelled."))
            pause()
        else: print(col("r", f"  x Enter a number from 0 to {len(MENU)}.\n"))

if __name__ == "__main__":
    try: main()
    except (KeyboardInterrupt, EOFError): print("\n  Bye.")
