# ======================================================
# HARD CODED MAPPING (1 file, clean, simple)
# ======================================================

TABLE_MAPPINGS = {

    "item": {
        "erp_table": "Item IGH",
        "acc_table": "item",
        "key_erp": "acc_id",
        "key_acc": "id",
        "fields_import": {
            "itemName": "item_name",
            "itemType": "item_type",
            "itemCategory.id": "category_id",
            "unit.name": "unit",
            "barcode": "barcode",
            "description": "description",
        },
        "fields_export": {
            "item_name": "itemName",
            "item_type": "itemType",
            "category_id": "itemCategory",
            "unit": "unit",
            "barcode": "barcode",
            "description": "description",
        }
    },

    "item-category": {
        "erp_table": "Item Category IGH",
        "acc_table": "item-category",
        "key_erp": "acc_id",
        "key_acc": "id",
        "fields_import": {
            "name": "category_name",
        },
        "fields_export": {
            "category_name": "name",
        }
    },

    "unit": {
        "erp_table": "Unit IGH",
        "acc_table": "unit",
        "key_erp": "acc_id",
        "key_acc": "id",
        "fields_import": {"name": "unit_name"},
        "fields_export": {"unit_name": "name"},
    },

    "vendor": {
        "erp_table": "Vendor IGH",
        "acc_table": "vendor",
        "key_erp": "acc_id",
        "key_acc": "id",
        "fields_import": {
            "name": "supplier_name",
            "email": "email",
            "mobilePhone": "mobile",
            "address": "address",
            "status": "status",
        },
        "fields_export": {
            "supplier_name": "name",
            "email": "email",
            "mobile": "mobilePhone",
            "address": "address",
            "status": "status",
        }
    },

    "customer": {
        "erp_table": "Customer IGH",
        "acc_table": "customer",
        "key_erp": "acc_id",
        "key_acc": "id",
        "fields_import": {
            "name": "customer_name",
            "email": "email",
            "mobilePhone": "phone",
            "address": "address",
            "status": "status",
        },
        "fields_export": {
            "customer_name": "name",
            "email": "email",
            "phone": "mobilePhone",
            "address": "address",
            "status": "status",
        }
    },
}
