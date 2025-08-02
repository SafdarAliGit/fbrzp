import frappe

def custom_on_update(doc, method):
    account = frappe.get_doc("Account", "GST - ZPL")
    rate = float(account.tax_rate) or frappe.throw("Tax rate undefined on GST - ZPL")

    for item in doc.items:
        item.tax_rate = rate
        item.tax_amount = round(item.amount * (rate / 100), 2)


