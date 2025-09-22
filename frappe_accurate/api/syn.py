import frappe
import requests
import hmac
import hashlib
import base64
from datetime import datetime
from frappe_accurate.api.auth import get_headers,get_settings,host_token

ACCURATE_BASE_URL = "https://api.accurate.id"   # ganti dengan URL API Accurate
ACCURATE_TOKEN = "your_token_here"              # simpan di doctype/setting jika perlu

@frappe.whitelist()
def sync_to_accurate(docname):
    """
    Sinkronisasi Item & Customer antara ERPNext <-> Accurate
    berdasarkan child table dari dokumen `Sync Log`
    """
    doc = frappe.get_doc("Sync Log", docname)

    # --- 1. Ambil data list dari Accurate ---
    headers = {"Authorization": f"Bearer {ACCURATE_TOKEN}"}
    items_acc = requests.get(f"{ACCURATE_BASE_URL}/items", headers=headers).json()
    customers_acc = requests.get(f"{ACCURATE_BASE_URL}/customers", headers=headers).json()

    items_acc_map = {i["code"]: i for i in items_acc.get("data", [])}
    customers_acc_map = {c["code"]: c for c in customers_acc.get("data", [])}

    results = []

    # --- 2. Loop data child table ---
    for row in doc.items:   # child table berisi Item/Customer
        if row.doctype_name == "Item":
            erp_item = frappe.get_doc("Item", row.record_id)
            code = erp_item.item_code

            if code not in items_acc_map:  # ada di ERPNext, belum ada di Accurate
                resp = requests.post(f"{ACCURATE_BASE_URL}/items", headers=headers, json={
                    "code": erp_item.item_code,
                    "name": erp_item.item_name,
                    "uom": erp_item.stock_uom
                })
                acc_id = resp.json().get("id")
                erp_item.db_set("accurate_id", acc_id)
                results.append(f"Item {code} dibuat di Accurate")

        elif row.doctype_name == "Customer":
            erp_customer = frappe.get_doc("Customer", row.record_id)
            code = erp_customer.customer_name

            if code not in customers_acc_map:  # ada di ERPNext, belum ada di Accurate
                resp = requests.post(f"{ACCURATE_BASE_URL}/customers", headers=headers, json={
                    "code": erp_customer.customer_name,
                    "name": erp_customer.customer_name,
                    "email": erp_customer.email_id
                })
                acc_id = resp.json().get("id")
                erp_customer.db_set("accurate_id", acc_id)
                results.append(f"Customer {code} dibuat di Accurate")

    # --- 3. Cari data yang ada di Accurate tapi belum ada di ERPNext ---
    for code, acc_item in items_acc_map.items():
        if not frappe.db.exists("Item", {"item_code": code}):
            new_item = frappe.get_doc({
                "doctype": "Item",
                "item_code": code,
                "item_name": acc_item.get("name"),
                "stock_uom": "Nos",  # default atau mapping
                "accurate_id": acc_item.get("id")
            })
            new_item.insert(ignore_permissions=True)
            results.append(f"Item {code} dibuat di ERPNext")

    for code, acc_customer in customers_acc_map.items():
        if not frappe.db.exists("Customer", {"customer_name": code}):
            new_customer = frappe.get_doc({
                "doctype": "Customer",
                "customer_name": code,
                "customer_type": "Company",
                "email_id": acc_customer.get("email"),
                "accurate_id": acc_customer.get("id")
            })
            new_customer.insert(ignore_permissions=True)
            results.append(f"Customer {code} dibuat di ERPNext")

    return {"status": "success", "log": results}
