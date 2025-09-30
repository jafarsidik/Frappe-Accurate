import frappe
import json
from frappe.utils import now,nowdate
from frappe import _
import requests
from frappe_accurate.api.auth import get_headers,get_settings,host_token

@frappe.whitelist(allow_guest=True)
def testing():
    """Update Sales Order dari Accurate Invoice"""
    try:
        host = host_token()  # ambil host terbaru via /api-token.do
        url = f"{host}/accurate/api/sales-invoice/detail.do?id=700"
        headers = get_headers()
        res = requests.get(url, headers=headers, timeout=30).json()
        records = res['d']

        for r in records['detailItem']:
            # cari Sales Order berdasarkan custom id
            so_name = frappe.db.get_value(
                "Sales Order",
                {"custom_sales_order_id_accurate": r["salesOrder"]['id']},
                "name"
            )

            if not so_name:
                frappe.log_error(f"Tidak ditemukan Sales Order dengan Accurate ID {r['salesOrder']['id']}", "Sales Order Update Error")
                continue

            so = frappe.get_doc("Sales Order", so_name)

            # tambahkan child row ke custom child table
            so.append('custom_sales_invoice_accurate', {
                'transaction_date': records['transDate'],
                'sales_invoice_number': records["number"],
                'sales_invoice_status': records['statusName'],
                'sales_invoice_id': records['id'],
                'sales_invoice_amount': records['totalAmount'],
            })

            # simpan update
            so.save(ignore_permissions=True)

        frappe.db.commit()
        return {"status": "success", "message": "Invoice linked to Sales Order", "invoice_id": "700"}

    except Exception as e:
        frappe.log_error(frappe.get_traceback(), "Accurate Invoice Webhook Error")
        return {"status": "error", "message": str(e)}

@frappe.whitelist(allow_guest=True)
def handler():
	"""Menerima webhook dari Accurate Online (Sales Order, Sales Invoice, dsb)"""
	
	try:
		# Default data
		data = frappe.local.form_dict

		# Coba parse JSON body kalau ada
		if frappe.request and frappe.request.data:
			try:
				data = json.loads(frappe.request.data)
			except Exception:
				frappe.log_error(frappe.request.data, "Accurate Webhook - Invalid JSON")
				data = {}

		# Simpan log dulu
		frappe.get_doc({
			"doctype": "Webhook Request Log",
			"user": "Guest",
			"url": frappe.request.url,
			"headers": json.dumps(dict(frappe.request.headers), indent=2),
			"data": json.dumps(data, indent=2),
			"status": "Success",
			"error": None,
			"response": json.dumps({"message": "Webhook received"}, indent=2),
		}).insert(ignore_permissions=True)

		# --- Handler sesuai bentuk payload ---
		if isinstance(data, list):
			# Bentuk normal -> ada type + data[]
			for payload in data:
				payload_type = payload.get("type")
				rows = payload.get("data", [])

				for row in rows:
					if payload_type == "SALES_INVOICE":
						save_sales_invoice(row)

		elif isinstance(data, dict):
			# Kalau cuma cmd = "frappe_accurate.api.accurate_webhook.handler"
			if "cmd" in data and len(data) == 1:
				frappe.log_error("Webhook trigger only (no data)", "Accurate Webhook - Empty Trigger")
				# tidak usah buat Sales Order/Invoice
			else:
				# Bisa tambahin handler tipe lain di sini kalau ada
				pass

		frappe.db.commit()
		return {"status": "success", "message": "Webhook received"}

	except Exception as e:
		frappe.log_error(frappe.get_traceback(), "Accurate Webhook Error")
		return {"status": "error", "message": str(e)}

def save_sales_invoice(row):
    """Update Sales Order dari Accurate Invoice"""
    try:
        host = host_token()  # ambil host terbaru via /api-token.do
        url = f"{host}/accurate/api/sales-invoice/detail.do?id={row['salesInvoiceId']}"
        headers = get_headers()
        res = requests.get(url, headers=headers, timeout=30).json()
        records = res['d']

        for r in records['detailItem']:
            # cari Sales Order berdasarkan custom id
            so_name = frappe.db.get_value(
                "Sales Order",
                {"custom_sales_order_id_accurate": r["salesOrder"]['id']},
                "name"
            )

            if not so_name:
                frappe.log_error(f"Tidak ditemukan Sales Order dengan Accurate ID {r['salesOrder']['id']}", "Sales Order Update Error")
                continue

            so = frappe.get_doc("Sales Order", so_name)

            # tambahkan child row ke custom child table
            so.append('custom_sales_invoice_accurate', {
                'transaction_date': records['transDate'],
                'sales_invoice_number': records["number"],
                'sales_invoice_status': records['statusName'],
                'sales_invoice_id': records['id'],
                'sales_invoice_amount': records['totalAmount'],
            })

            # simpan update
            so.save(ignore_permissions=True)

        frappe.db.commit()
        return {"status": "success", "message": "Invoice linked to Sales Order", "invoice_id": "700"}

    except Exception as e:
        frappe.log_error(frappe.get_traceback(), "Accurate Invoice Webhook Error")
        return {"status": "error", "message": str(e)}
    
