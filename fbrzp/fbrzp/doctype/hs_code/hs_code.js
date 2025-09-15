// Copyright (c) 2025, Tech Ventures and contributors
// For license information, please see license.txt

frappe.ui.form.on('HS Code', {
	refresh: function(frm) {
		frm.set_query("parent_hs_code", function() {
			return {
				filters: {
					"is_group": 1
				}
			}
		});
	}
});
