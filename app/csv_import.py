import csv
import io
import re
from datetime import datetime
import phonenumbers

ALIASES = {
    "customer_name": [
        "customer_name", "customer name", "name", "full name", "customer",
        "subscriber name", "subscriber"
    ],
    "phone": [
        "phone", "phone number", "mobile", "mobile number", "cell", "cell phone",
        "customer phone", "primary phone", "telephone"
    ],
    "rep_name": [
        "rep_name", "rep name", "rep", "sales rep", "salesperson", "agent",
        "sales representative"
    ],
    "install_date": [
        "install_date", "install date", "installation date", "scheduled install",
        "scheduled install date", "appointment date", "install"
    ],
    "order_id": [
        "order_id", "order id", "account id", "account number", "sale id",
        "customer id", "lead id", "submission id", "id"
    ],
}

DATE_FORMATS = [
    "%m/%d/%Y", "%m/%d/%y", "%Y-%m-%d", "%m-%d-%Y", "%m-%d-%y",
    "%Y/%m/%d", "%b %d %Y", "%B %d %Y"
]

def norm_header(s: str) -> str:
    return re.sub(r"\s+", " ", (s or "").strip().lower().replace("_", " "))

def detect_columns(headers):
    normalized = {norm_header(h): h for h in headers}
    found = {}
    for target, aliases in ALIASES.items():
        for alias in aliases:
            if norm_header(alias) in normalized:
                found[target] = normalized[norm_header(alias)]
                break
    return found

def parse_date(value):
    if not value:
        return None
    value = value.strip()
    for fmt in DATE_FORMATS:
        try:
            return datetime.strptime(value, fmt).date()
        except ValueError:
            pass
    # Excel-ish date with time
    for fmt in ("%m/%d/%Y %H:%M", "%Y-%m-%d %H:%M:%S"):
        try:
            return datetime.strptime(value, fmt).date()
        except ValueError:
            pass
    return None

def normalize_phone(value, default_country="US"):
    if not value:
        return None
    try:
        p = phonenumbers.parse(value, default_country)
        if not phonenumbers.is_possible_number(p):
            return None
        return phonenumbers.format_number(p, phonenumbers.PhoneNumberFormat.E164)
    except Exception:
        return None

def read_csv_bytes(data: bytes):
    # Handle UTF-8 BOM commonly produced by exports.
    text = data.decode("utf-8-sig", errors="replace")
    sample = text[:4096]
    try:
        dialect = csv.Sniffer().sniff(sample, delimiters=",;\t")
    except csv.Error:
        dialect = csv.excel

    reader = csv.DictReader(io.StringIO(text), dialect=dialect)
    headers = reader.fieldnames or []
    mapping = detect_columns(headers)
    rows = list(reader)
    return headers, mapping, rows
