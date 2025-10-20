import frappe
import json
from frappe.utils import now,nowdate
from frappe import _
import requests
from frappe_accurate.api.auth import get_headers,get_settings,host_token

@frappe.whitelist(allow_guest=True)
def test_call():
	
	purchaseOrderId = 50 #idx['purchaseOrderId']
	purchaseOrderNo = "PI.2025.10.00001" #idx['purchaseOrderNo']
	host = host_token()  # ambil host terbaru via /api-token.do
	url = f"{host}/accurate/api/purchase-invoice/detail.do?id={purchaseOrderId}"
	headers = get_headers()
	res = requests.get(url, headers=headers, timeout=30).json()
	records = res['d']
	for idx_po in records['detailItem']:
		po_id = idx_po['purchaseOrderId']
	return res

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
					if payload_type == "SALES_ORDER":
						save_sales_order(row)
					if payload_type == "SALES_INVOICE":
						save_sales_invoice(row)
					if payload_type == "PURCHASE_ORDER":
						update_purchase_order(row)
					if payload_type == "PURCHASE_INVOICE":
						update_purchase_invoice(row)

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

def save_sales_order(row):
	"""Update Sales Order dari Accurate Invoice"""
	try:
		# pastikan row berbentuk list of dict
		if isinstance(row, dict):
			row = [row]
		for idx in row:
			salesOrderId = idx.get('salesOrderId')
			salesOrderNo = idx.get('salesOrderNo')
			host = host_token()  # ambil host terbaru via /api-token.do
			url = f"{host}/accurate/api/sales-order/detail.do?id={salesOrderId}"
			headers = get_headers()
			res = requests.get(url, headers=headers, timeout=30).json()
			records = res['d']

			for r in records['detailItem']:
				# cari Sales Order berdasarkan custom id
				so_name = frappe.db.get_value(
					"Sales Order",
					{"custom_sales_order_id_accurate": salesOrderId},
					"name"
				)

				if not so_name:
					frappe.log_error(f"Tidak ditemukan Sales Order dengan Accurate ID {salesOrderNo}", "Sales Order Update Error")
					continue

				so = frappe.get_doc("Sales Order", so_name)
				so.custom_statusname = records['statusName']
				
				# simpan update 
				so.save(ignore_permissions=True)

			frappe.db.commit()
		return {"status": "success", "message": "Invoice linked to Sales Order", "invoice_id": "700"}

	except Exception as e:
		frappe.log_error(frappe.get_traceback(), "Accurate Invoice Webhook Error")
		return {"status": "error", "message": str(e)}

def save_sales_invoice(row):
	"""Update Sales Order dari Accurate Invoice"""
	try:
		# pastikan row berbentuk list of dict
		if isinstance(row, dict):
			row = [row]
		for idx in row:
			salesInvoiceId = idx.get('salesInvoiceId')
			salesOrderNo = idx.get('salesOrderNo')
			host = host_token()  # ambil host terbaru via /api-token.do
			url = f"{host}/accurate/api/sales-invoice/detail.do?id={salesInvoiceId}"
			headers = get_headers()
			res = requests.get(url, headers=headers, timeout=30).json()
			records = res['d']

			# cari Purchase Order berdasarkan custom custom_purchase_order_id_accurate
			for idx_po in records['detailItem']:
				so_id = idx_po['salesOrderId']
				totalPrice = idx_po['totalPrice']
    
				so_name = frappe.db.get_value(
					"Sales Order",
					{"custom_sales_order_id_accurate": so_id},
					"name"
				)

				if not so_name:
					frappe.log_error(f"Tidak ditemukan Sales Order dengan Accurate ID {so_id}", "Sales Order Update Error")
					continue

				so = frappe.get_doc("Sales Order", so_name)
				#so.custom_statusname = records['statusName']
				# tambahkan child row ke custom child table
				so.custom_sales_invoice_accurate = []
				so.append('custom_sales_invoice_accurate', {
				 	'transaction_date': records['transDate'],
				 	'sales_invoice_number': records["number"],
				 	'sales_invoice_status': records['statusName'],
				 	'sales_invoice_id': records['id'],
				 	'sales_invoice_amount': totalPrice,
				})

				# simpan update
				so.save(ignore_permissions=True)

			frappe.db.commit()
		return {"status": "success", "message": "Invoice linked to Sales Order", "invoice_id": so_id}

	except Exception as e:
		frappe.log_error(frappe.get_traceback(), "Accurate Invoice Webhook Error")
		return {"status": "error", "message": str(e)}


def update_purchase_order(row):
	"""Update Purchase Order dari Accurate Invoice"""
	try:
		# pastikan row berbentuk list of dict
		if isinstance(row, dict):
			row = [row]
		for idx in row:
			purchaseOrderId = idx.get('purchaseOrderId')
			purchaseOrderNo = idx.get('purchaseOrderNo')
   
			host = host_token()  # ambil host terbaru via /api-token.do
			url = f"{host}/accurate/api/purchase-order/detail.do?id={purchaseOrderId}"
			headers = get_headers()
			res = requests.get(url, headers=headers, timeout=30).json()
			records = res['d']
			
			# cari Purchase Order berdasarkan custom custom_purchase_order_id_accurate
			po_name = frappe.db.get_value(
				"Purchase Order",
				{"custom_purchase_order_id_accurate": purchaseOrderId},
				"name"
			)

			if not po_name:
				frappe.log_error(f"Tidak ditemukan Purchase Order dengan Accurate ID {purchaseOrderId}", "Purchase Order Update Error")
				continue

			po = frappe.get_doc("Purchase Order", po_name)
			po.custom_purchase_order_status_accurate = records['statusName']
			po.save(ignore_permissions=True)

			frappe.db.commit()
		return {"status": "success", "message": "Invoice linked to Purchase Order", "invoice_id":purchaseOrderId }

	except Exception as e:
		frappe.log_error(frappe.get_traceback(), "Accurate Invoice Webhook Error")
		return {"status": "error", "message": str(e)}

def update_purchase_invoice(row):
	"""Update Purchase Order dari Accurate Invoice"""
	try:
		# pastikan row berbentuk list of dict
		if isinstance(row, dict):
			row = [row]
		for idx in row:
			purchaseInvoiceId = idx.get('purchaseInvoiceId')
			purchaseInvoiceNo = idx.get('purchaseInvoiceNo')
   
			host = host_token()  # ambil host terbaru via /api-token.do
			url = f"{host}/accurate/api/purchase-invoice/detail.do?id={purchaseInvoiceId}"
			headers = get_headers()
			res = requests.get(url, headers=headers, timeout=30).json()
			records = res['d']
			
			# cari Purchase Order berdasarkan custom custom_purchase_order_id_accurate
			for idx_po in records['detailItem']:
				po_id = idx_po['purchaseOrderId']
				totalPrice = idx_po['totalPrice']
				po_name = frappe.db.get_value(
					"Purchase Order",
					{"custom_purchase_order_id_accurate": po_id},
					"name"
				)

				if not po_name:
					frappe.log_error(f"Tidak ditemukan Purchase Order dengan Accurate ID {po_id}", "Purchase Order Update Error")
					continue

				po = frappe.get_doc("Purchase Order", po_name)
				#Update Data Purchase Invocie di Data Purchase Order
				po.custom_purchase_invoice_child = []
				po.append('custom_purchase_invoice_child', {
					'transaction_date': records['transDate'],
					'purchase_invoice_number': records["number"],
					'purchase_invoice_status': records['statusName'],
					'purchase_invoice_id': records['id'],
					'purchase_invoice_amount': totalPrice,
				})
				po.save(ignore_permissions=True)

			frappe.db.commit()
		return {"status": "success", "message": "Invoice linked to Purchase Order", "invoice_id":po_id }

	except Exception as e:
		frappe.log_error(frappe.get_traceback(), "Accurate Invoice Webhook Error")
		return {"status": "error", "message": str(e)}