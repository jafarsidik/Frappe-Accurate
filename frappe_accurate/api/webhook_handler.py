import frappe
import json

@frappe.whitelist(allow_guest=True)
def handler():
    """
    Webhook handler untuk Accurate
    Bisa menampung banyak tipe data: sales_invoice, sales_order, customer, item, purchase_order, purchase_invoice
    """
    try:
        # Ambil raw body
        raw_body = frappe.request.get_data(as_text=True)
        if not raw_body:
            frappe.throw("No data received")

        payload = json.loads(raw_body)
        frappe.logger().info(f"Accurate Webhook Payload: {frappe.as_json(payload)}")

        # Cek tipe event (harus dikirim Accurate di payload)
        event_type = payload.get("type")   # contoh: "sales_invoice", "customer", dll
        data = payload.get("data")

        if not event_type or not data:
            frappe.throw("Payload tidak lengkap (event_type & data wajib)")

        # Routing ke handler masing-masing
        if event_type == "SALES_INVOICE":
            process_sales_invoice(data)
        elif event_type == "SALES_ORDER":
            process_sales_order(data)
        elif event_type == "CUSTOMER":
            process_customer(data)
        elif event_type == "item":
            process_item(data)
        elif event_type == "PURCHASE_ORDER":
            process_purchase_order(data)
        elif event_type == "PURCHASE_INVOICE":
            process_purchase_invoice(data)
        else:
            frappe.throw(f"Event type {event_type} tidak dikenali")

        return {"status": "success", "event_type": event_type}

    except Exception as e:
        frappe.log_error(frappe.get_traceback(), "Accurate Webhook Error")
        return {"status": "error", "message": str(e)}


# -------------------------
# Handler khusus per event
# -------------------------

def process_sales_invoice(data):
    """Update Sales Invoice ke Sales Order ERPNext"""
    sales_invoice_id = data.get("invoiceId")
    sales_order_no = data.get("salesOrderNo")
    if not sales_invoice_id or not sales_order_no:
        return

    so = frappe.get_doc("Sales Order", sales_order_no)
    so.append("custom_sales_invoice_child", {
        "accurate_invoice_id": sales_invoice_id
    })
    so.save(ignore_permissions=True)
    frappe.db.commit()


def process_sales_order(data):
    """Sinkron Sales Order dari Accurate"""
    frappe.get_doc({
        "doctype": "Sales Order",
        "customer": data.get("customerNo"),
        "transaction_date": data.get("transDate"),
        "custom_accurate_id": data.get("id")
    }).insert(ignore_permissions=True)


def process_customer(data):
    """Sinkron Customer dari Accurate"""
    frappe.get_doc({
        "doctype": "Customer",
        "customer_name": data.get("name"),
        "custom_accurate_id": data.get("id"),
        "custom_customerno": data.get("customerNo")
    }).insert(ignore_permissions=True)


def process_item(data):
    """Sinkron Item/Produk dari Accurate"""
    frappe.get_doc({
        "doctype": "Item",
        "item_code": data.get("itemNo"),
        "item_name": data.get("name"),
        "custom_accurate_id": data.get("id")
    }).insert(ignore_permissions=True)


def process_purchase_order(data):
    """Sinkron Purchase Order dari Accurate"""
    frappe.get_doc({
        "doctype": "Purchase Order",
        "supplier": data.get("supplierNo"),
        "transaction_date": data.get("transDate"),
        "custom_accurate_id": data.get("id")
    }).insert(ignore_permissions=True)


def process_purchase_invoice(data):
    """Sinkron Purchase Invoice dari Accurate"""
    frappe.get_doc({
        "doctype": "Purchase Invoice",
        "supplier": data.get("supplierNo"),
        "posting_date": data.get("transDate"),
        "custom_accurate_id": data.get("id")
    }).insert(ignore_permissions=True)
