# Bakery Order Register  (Project #87, Everyday Innovators)

Record cake and bakery orders, pickup dates and payment status.
**Python backend** (standard library only) with **two front ends** that share one logic module:

| Front end | Start it | Open |
|---|---|---|
| Terminal app (menu driven, ANSI colours) | `python cli.py` | the terminal |
| Website (HTML + JS served by Python) | `python server.py` | http://localhost:8000 |

Both read and write the same file, `data/orders.json`, so an order added in one appears in the other.
Requires Python 3.10+. No installs needed. Optional: `pip install matplotlib` for the chart image.

## Project structure
    core.py          validation, persistence, search, summary, exports, CSV import (shared)
    cli.py           interactive terminal interface
    server.py        web server + JSON API (python standard library http.server)
    static/          index.html + app.js  (website front end)
    sample_data/     sample_orders.csv, sample_orders.json (40 records), legacy_import_sample.csv (bad rows on purpose)
    tests/           python -m unittest discover -s tests      (13 tests)
    data/            orders.json is created on first run (40 sample orders are seeded)
    exports/         reports written by the app

## Requirement checklist
| Brief requirement | Where |
|---|---|
| Interactive terminal interface, menu, guided steps, branded welcome | `cli.py` (12-option menu, banner) |
| Defensive input validation | `core.validate` (name, 10-digit mobile, qty 1-100, price, dates, overpayment); `cli.ask` loops until valid; same rules enforced by the web API |
| Core logic: orders, pickup dates, payment status | payment status derived from amount paid (Unpaid / Partial / Paid); pickup status (waiting, due soon, due today, overdue, picked up) |
| Local persistence (JSON/CSV) | `data/orders.json`, atomic write; missing or corrupt file is recreated (bad copy kept as `orders.json.corrupt`) |
| Query and search | keyword + category + payment + pickup filters (terminal option 3, website toolbar) |
| Executive summary | totals, average order, collected vs owed, status counts, revenue by category (text bar chart), upcoming pickups, top customers |
| Export: Markdown, audit log, CSV | terminal option 9 writes to `exports/`; website export buttons |
| Threshold warnings | overdue, due today, unpaid, plus anomalies (quantity >= 50, total >= 20,000, pickup > 90 days out, collected but unpaid) |
| GUI enhancement | the website (Tkinter/Textual not needed) |
| Bulk CSV import with row-by-row error log | terminal option 10 (also saves `exports/import_errors.log`), website Import CSV |
| 30-50 sample entries, CSV + JSON, edge cases | `sample_data/` (40 entries incl. same-day pickup, max quantity, 120-day pickup, collected-but-unpaid) |
| Chart (Matplotlib) | terminal option 11 (optional) |
| Pagination for large tables | 10 rows per page in the terminal list |

## 5-minute demo script
1. `python cli.py`: show the banner and the startup warning about overdue orders.
2. Option 1, add an order. Type bad answers on purpose (name "A", phone "123", quantity 0, pickup before order date, overpayment) and show each being rejected and re-asked.
3. Option 3, search "cake" in category Cake.  Option 7, the summary dashboard.  Option 8, warnings.
4. Option 10, import `sample_data/legacy_import_sample.csv` and show the row-by-row error log.
5. Option 9, export. Open `exports/bakery_report.md`.
6. Exit, run `python cli.py` again, and show the new order is still there (persistence).
7. `python server.py`, open the website, show the same data, add an order with a form error, mark paid, filter by Unpaid.
8. Optional: option 11 for the chart image. Run `python -m unittest discover -s tests` to show the tests passing.

## Web API
GET /api/orders?q=&category=&status=&pickup= | POST /api/orders | PUT /api/orders/<id> | DELETE /api/orders/<id>
GET /api/summary | GET /api/export?fmt=csv|md|txt | POST /api/import (CSV body) | POST /api/reset
