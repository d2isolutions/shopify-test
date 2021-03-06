from odoo import models, fields, api

# mapping invoice type to journal type
TYPE2JOURNAL = {
    'out_invoice': 'sale',
    'in_invoice': 'purchase',
    'out_refund': 'sale_refund',
    'in_refund': 'purchase_refund',
}


class SaleWorkflowProcess(models.Model):
    _name = "sale.workflow.process.ept"
    _description = "sale workflow process"



    name = fields.Char(string='Name', size=64)
    validate_order = fields.Boolean("Validate Order", default=False)
    create_invoice = fields.Boolean('Create & Validate Invoice', default=False)
    register_payment = fields.Boolean(string='Register Payment', default=False)
    invoice_date_is_order_date = fields.Boolean('Force Accounting Date',
                                                help="If it's check the Accounting Date will be the "
                                                     "same as the order date")
    journal_id = fields.Many2one('account.journal', string='Payment Journal',
                                 domain=[('type', 'in', ['cash', 'bank'])])
    sale_journal_id = fields.Many2one('account.journal', string='Sales Journal',
                                      domain=[('type', '=', 'sale')])


    picking_policy = fields.Selection(
        [('direct', 'Deliver each product when available'),
         ('one', 'Deliver all products at once')], string='Shipping Policy',default="one")

    inbound_payment_method_id = fields.Many2one('account.payment.method', string="Debit Method",
                                                domain=[('payment_type', '=', 'inbound')],
                                                help="Means of payment for collecting money. "
                                                     "Odoo modules offer various payments "
                                                     "handling facilities, "
                                                     "but you can always use the 'Manual' payment "
                                                     "method in "
                                                     "order to manage payments outside of the "
                                                     "software.")

    @api.onchange("validate_order")
    def onchange_validate_order(self):
        for record in self:
            if not record.validate_order:
                record.create_invoice = False

    @api.onchange("create_invoice")
    def onchange_create_invoice(self):
        for record in self:
            if not record.create_invoice:
                record.register_payment = False
                record.invoice_date_is_order_date = False

    @api.model
    def auto_workflow_process(self, auto_workflow_process_id=False, ids=[]):
        """
        Added comment by Udit
        This method will find draft sale orders which are not having invoices yet,
        confirmed it and done the payment according to the auto invoice workflow
        configured in sale order.
        :param auto_workflow_process_id: auto workflow process id
        :param ids: ids of sale orders
        """
        sale_order_obj = self.env['sale.order']
        workflow_process_obj = self.env['sale.workflow.process.ept']
        if not auto_workflow_process_id:
            work_flow_process_records = workflow_process_obj.search([])
        else:
            work_flow_process_records = workflow_process_obj.browse(auto_workflow_process_id)

        for work_flow_process_record in work_flow_process_records:
            if not ids:
                orders = \
                    sale_order_obj. \
                        search([('auto_workflow_process_id', '=', work_flow_process_record.id),
                                ('state', 'not in', ('done', 'cancel', 'sale')),
                                ('invoice_status', '!=', 'invoiced')])
            else:
                orders = sale_order_obj.search(
                    [('auto_workflow_process_id', '=', work_flow_process_record.id),
                     ('id', 'in', ids)])
            if not orders:
                continue
            orders.process_orders_and_invoices_ept()

        return True

    def shipped_order_workflow(self, orders, customers_location):
        """
        This method is the auto workflow for shipped orders.
        :param work_flow_process_record: Workflow id
        :param orders: list of orders objects
        :param customers_location: customer location object
        :param log_book: log_book object
        :return: True
        """
        self.ensure_one()
        module_obj = self.env['ir.module.module']
        mrp_module = module_obj.sudo().search([('name', '=', 'mrp'), ('state', '=', 'installed')])
        for order in orders:
            if order.order_line:
                order.state = 'sale'
                order.mapped('order_line').write({'state': 'sale'})
                order.auto_shipped_order_ept(customers_location, mrp_module)
                order.validate_and_paid_invoices_ept(self)
        return True
