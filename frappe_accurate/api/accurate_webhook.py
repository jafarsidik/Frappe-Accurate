import frappe
import json
from frappe.utils import now
from frappe import _

@frappe.whitelist(allow_guest=True)
def handler():
    """Menerima webhook dari Accurate Online untuk Invoice"""

    try:
        # Ambil raw data dari request
        data = frappe.local.form_dict

        # Jika request berupa JSON
        if frappe.request and frappe.request.data:
            try:
                data = json.loads(frappe.request.data)
            except Exception:
                frappe.log_error(frappe.request.data, "Accurate Webhook - Invalid JSON")

        # Simpan log webhook agar bisa dicek nanti
        frappe.get_doc({
            "doctype": "Webhook Request Log",
            "user": "Guest",
            "url": frappe.request.url,
            "headers": json.dumps(dict(frappe.request.headers), indent=2),
            "data": json.dumps(data, indent=2),
            "status": "Success",
            "error":None,
            "response":json.dumps({"message": "Webhook received"}, indent=2),
            #"trigger": "Accurate Invoice",
            #"output": "Received at {}".format(now())
        }).insert(ignore_permissions=True)
        
        frappe.db.commit()

        return {"status": "success", "message": "Webhook received"}

    except Exception as e:
        frappe.log_error(frappe.get_traceback(), "Accurate Webhook Error")
        return {"status": "error", "message": str(e)}
    
@frappe.whitelist(allow_guest=True)
def sales_invoice_webhook():
    """Menerima webhook dari Accurate Online untuk Invoice"""

    try:
        # Ambil raw data dari request
        data = frappe.local.form_dict

        # Jika request berupa JSON
        if frappe.request and frappe.request.data:
            try:
                data = json.loads(frappe.request.data)
            except Exception:
                frappe.log_error(frappe.request.data, "Accurate Invoice Webhook - Invalid JSON")

        # Simpan log webhook agar bisa dicek nanti
        frappe.get_doc({
            "doctype": "Webhook Log",
            "webhook_type": "Accurate Invoice",
            "payload": json.dumps(data, indent=2),
            "received_at": now()
        }).insert(ignore_permissions=True)

        # Contoh mapping data Invoice Accurate ke Doctype Frappe
        # invoice = frappe.get_doc({
        #     "doctype": "Sales Invoice",
        #     "customer": data.get("customer_name"),
        #     "posting_date": data.get("transDate"),
        #     "due_date": data.get("dueDate"),
        #     "custom_accurate_invoice_id": data.get("id"),
        #     "custom_invoice_number": data.get("number"),
        #     "items": []
        # })

        # Tambahkan item jika ada
        # for item in data.get("detailItem", []):
        #     invoice.append("items", {
        #         "item_code": item.get("itemName"),
        #         "qty": item.get("quantity"),
        #         "rate": item.get("unitPrice")
        #     })

        # invoice.insert(ignore_permissions=True)
        # sales_order = frappe.get_doc({
        #     "doctype": "Sales Order",
        #     "customer": data.get("customer_name"),
        #     "posting_date": data.get("transDate"),
        #     "due_date": data.get("dueDate"),
        #     "custom_accurate_invoice_id": data.get("id"),
        #     "custom_invoice_number": data.get("number"),
        #     "items": []
        # })
        # sales_order.append("items", {
        #         "item_code": item.get("itemName"),
        #         "qty": item.get("quantity"),
        #         "rate": item.get("unitPrice")
        #     })
        frappe.db.commit()

        return {"status": "success", "message": "Invoice received", "invoice_id": invoice.name}

    except Exception as e:
        frappe.log_error(frappe.get_traceback(), "Accurate Invoice Webhook Error")
        return {"status": "error", "message": str(e)}
