import frappe
from erpnext.accounts.doctype.sales_invoice.sales_invoice import SalesInvoice as SalesInvoiceController
from fbrzp.api import FBRDigitalInvoicingAPI  
from frappe.utils import cint
import pyqrcode
from frappe.utils import strip_html_tags



class SalesInvoice(SalesInvoiceController):
    def on_submit(self):
        super().on_submit()
        if not self.custom_post_to_fdi:
            return
        
        if self.goods_sold_at_reduced_rate:
            if self.taxes[0].rate > 5:
                frappe.throw("Goods at reduced rate is not applicable for this invoice at rate " + str(self.taxes[0].rate))

        data = self.get_mapped_data()
        api_log = frappe.new_doc("FDI Request Log")
        api_log.request_data = frappe.as_json(data, indent=4)
        try:

            api = FBRDigitalInvoicingAPI()
            response = api.make_request("POST", "di_data/v1/di/postinvoicedata", self.get_mapped_data())
            resdata = response.get("validationResponse")
            
            if resdata.get("status") == "Valid": 
                self.db_set("custom_fbr_invoice_no",response.get("invoiceNumber"), commit=True)
                url = pyqrcode.create(self.custom_fbr_invoice_no)
                url.svg(frappe.get_site_path()+'/public/files/'+self.name+'_online_qrcode.svg', scale=8)
                self.custom_qr_code = '/files/'+self.name+'_online_qrcode.svg'
                self.db_set("custom_qr_code", self.custom_qr_code, commit=True)
                api_log.response_data = frappe.as_json(response, indent=4)
                api_log.save()
                frappe.msgprint("Invoice successfully submitted to FBR Digital Invoicing.")
            else:
                api_log.response_data = frappe.as_json(response, indent=4)
                api_log.save()
                frappe.log_error(
                title="FBR Digital Invoicing API Error",
                message=frappe.as_json(resdata, indent=4)
                )
                frappe.throw(
                    "Error in FBR Digital Invoicing" 
                )
                  
                
        except Exception as e:
            api_log.error = frappe.as_json(e, indent=4)
            api_log.save()
                
            frappe.log_error(
                title="FBR Digital Invoicing API Error",
                message=frappe.get_traceback()
            )
            
            frappe.throw(f"Error while submitting invoice to FBR: {str(e)}")

        api_log.save()
    def get_mapped_data(self):
        
        data = {}
        data["invoiceType"] = "Sale Invoice"
        data["invoiceDate"] = self.posting_date
        
        data["sellerNTNCNIC"] = self.company_tax_id
        data["sellerBusinessName"] = self.company
        data["sellerProvince"] = frappe.db.get_value("Company", self.company, "province")  # Default to Sindh if not set
        # Uncomment the next line if you have a seller address field
        #data["sellerAddress"] = self.seller.get("address")
        
        
        data["buyerNTNCNIC"] = (self.fbr_tax_id(self.customer) if self.fbr_tax_id(self.customer) else self.tax_id) if self.tax_id else ""    
        data["buyerBusinessName"] = self.customer_name
        data["buyerProvince"] = self.territory
        data["buyerAddress"] = self.customer_address
        data["buyerRegistrationType"] = "Unregistered" if not self.tax_id else "Registered"
        data["scenarioId"] = "SN002" if not self.tax_id else "SN001"  # Adjust based on your logic

        if self.goods_sold_at_reduced_rate:
            data["scenarioId"]=self.goods_at_reduced_rate().get('scenarioId',"")
       
        data["items"] = self.get_items()
        # frappe.log_error(
        #     title="SENDING DATA",
        #     message=frappe.as_json(data, indent=4)
        # )
        # frappe.throw("Stoped")
        return data
    
    def get_items(self):
        items = []
        for item in self.fbr_sales_invoice_item:
            escaped_descrip = ""
            # uom = self.get_and_set_uom(item.hs_code)
            tax_amount = round(item.amount * (self.taxes[0].rate /100), 2)
            # escaped_descrip = strip_html_tags(item.description)
            total_values = item.amount + tax_amount
            item_data = {
                "hsCode": item.hs_code,  # Default HS Code if not set
                "productDescription": f"{item.item_code}-{item.idx}",
                "rate": f"{cint(self.taxes[0].rate)}%",
                "uoM": item.fbr_uom if item.fbr_uom else "KG",
                "quantity": item.weight if item.weight > 0 else item.qty,
                "totalValues": f"{total_values:.2f}",  # Placeholder, adjust as needed
                "valueSalesExcludingST": round(item.amount, 2),
                "fixedNotifiedValueOrRetailPrice": 0,  # Placeholder, adjust as needed
                "salesTaxApplicable": tax_amount if tax_amount > 0 else 0,  # Assuming first tax is sales tax
                "salesTaxWithheldAtSource": 0,  # Placeholder, adjust as needed
                "extraTax": "",  # Placeholder, adjust as needed
                "furtherTax": 0,  # Assuming first tax is further tax
                "sroScheduleNo": "",  # Placeholder, adjust as needed
                "fedPayable": 0,  # Placeholder, adjust as needed
                "discount": 0,
                "saleType": "Goods at standard rate (default)",  # Adjust based on your logic
                "sroItemSerialNo": ""  # Placeholder, adjust as needed
            }
            
            if self.efs_invoice:
                item_data["quantity"] = item.efs_weight
            if self.goods_sold_at_reduced_rate:
                item_data["sroScheduleNo"]=self.goods_at_reduced_rate().get('sroScheduleNo',"")
                item_data["saleType"]=self.goods_at_reduced_rate().get('saleType',"")
                item_data["sroItemSerialNo"]=self.goods_at_reduced_rate().get('sroItemSerialNo',"")

            items.append(item_data)
        return items
        
    # def get_and_set_uom(self, hs_code):
    #     hs_code_doc = frappe.new_doc("HS Code")
    #     if frappe.db.exists("HS Code", hs_code):
    #         hs_code_doc = frappe.get_doc("HS Code", hs_code)
        
    #     api = FBRDigitalInvoicingAPI() 
    #     response = api.make_request("GET", f"pdi/v2/HS_UOM?hs_code={hs_code}&annexure_id=3")
    #     if response:
    #         #res = response.json()
    #         uom = response[0].get("description")
    #         hs_code_doc.hs_code = hs_code
    #         hs_code_doc.uom = uom
    #         hs_code_doc.save()
    #         return uom

    def goods_at_reduced_rate(self):
        mapping = {
        "sroScheduleNo":    "EIGHTH SCHEDULE Table 1",
        "saleType":         "Goods at Reduced Rate",
        "sroItemSerialNo":  "19",
        "scenarioId":       "SN005",
        }
        return mapping
    def fbr_tax_id(self,customer):
        fbr_tax_id = frappe.db.get_value("Customer", customer, "fbr_tax_id")
        if fbr_tax_id:  
            return fbr_tax_id
        else:
            return None
       
       

def update_fbr_sales_invoice_items(doc, method):
    """Custom update function for Sales Invoice to fill fbr_sales_invoice_item child table"""

    # Fetch items grouped by item_code and rate
    items = frappe.db.sql(
        """
        SELECT
            hs_code,
            description,
            fbr_uom,
            delivery_note,
            item_name,
            item_code,
            rate,
            SUM(qty) AS qty,
            SUM(efs_weight) AS efs_weight,
            SUM(weight) AS weight,
            SUM(amount) AS amount
        FROM `tabSales Invoice Item`
        WHERE parent = %s
        GROUP BY item_code, rate
        """,
        (doc.name,),
        as_dict=True
    )

    # Clear existing child table entries
    doc.set('fbr_sales_invoice_item', [])

    # Populate child table with new grouped items
    for item in items:
        row = doc.append('fbr_sales_invoice_item', {})
        row.hs_code = item.hs_code
        row.description = item.description
        row.fbr_uom = item.fbr_uom
        row.delivery_note = item.delivery_note
        row.item_name = item.item_name
        row.item_code = item.item_code
        row.rate = item.rate
        row.qty = item.qty
        row.efs_weight = item.efs_weight
        row.weight = item.weight
        row.amount = item.amount


     
    
            

