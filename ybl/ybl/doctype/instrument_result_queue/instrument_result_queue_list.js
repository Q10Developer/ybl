frappe.listview_settings['Instrument Result Queue'] = {

    onload: function(listview) {

        listview.page.add_inner_button(__('Test HL7'), function() {

            frappe.call({
                method: 'ybl.ybl.HL7_listener.test_hl7',

                callback: function(r) {

                    if (r.message) {

                        console.log(r.message);

                        frappe.msgprint({
                            title: __('Success'),
                            message: __('HL7 Message Processed Successfully'),
                            indicator: 'green'
                        });

                        listview.refresh();
                    }
                }
            });

        });

    }
};