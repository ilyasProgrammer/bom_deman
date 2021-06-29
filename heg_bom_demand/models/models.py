# -*- coding: utf-8 -*-

from odoo import models, fields, api


class BomDemand(models.Model):
    _name = "bom.demand"
    _description = "BOM Demand"

    name = fields.Char("Name", default="Draft")
    bom_id = fields.Many2one('mrp.bom', required=True)
    bom_qty = fields.Integer("BOMs Quantity", default=1)
    purchase_count = fields.Integer("Purchase Count", compute="compute_purchase_count", readonly=True)
    line_ids = fields.One2many('bom.demand.line', 'bom_demand_id')
    purchase_ids = fields.Many2many('purchase.order')
    state = fields.Selection([('draft', 'Draft'), ('done', 'Done')], default='draft')
    comment = fields.Text("Comment")
    # TODO report summ lines

    def compute_purchase_count(self):
        for r in self:
            r.purchase_count = len(r.purchase_ids)

    @api.onchange('bom_qty')
    def onchange_bom_qty(self):
        self.write({'line_ids': [(5, 0, 0)]})
        self.make_bom_structure(self.bom_id)

    @api.onchange('bom_id')
    def onchange_bom_id(self):
        self.write({'line_ids': [(5, 0, 0)]})
        self.make_bom_structure(self.bom_id)

    def make_bom_structure(self, bom_id, cnt=None, level=0):
        cnt = cnt or 0
        for line in bom_id.bom_line_ids:
            line_quantity = (self.bom_qty / (bom_id.product_qty or 1.0)) * line.product_qty
            vals = {"bom_demand_id": self.id,
                    "product_id": line.product_id.id,
                    "qty": line_quantity,
                    "stock_qty": line.product_id.qty_available,  # TODO check this
                    "type": 'component' if line.child_bom_id else 'part',
                    "level": level,
                    "sequence": cnt,
                    }
            self.env['bom.demand.line'].create(vals)
            cnt += 1
            if line.child_bom_id:
                cnt = self.make_bom_structure(line.child_bom_id, cnt, level=level+1)
        return cnt

    def action_open_bom_demand_purchases(self):
        return {
            "type": "ir.actions.act_window",
            "res_model": "purchase.order",
            "view_mode": "tree",
            "views": [[False, "tree"], [False, "form"]],
            "domain": [("id", "in", self.purchase_ids.ids)],
            "context": dict(self._context, create=False),
            "name": "BOM Demand Purchase",
        }

    def button_generate_purchase(self):
        purchase_ids = self.env['purchase.order']
        prod_model = self.env['product.product']
        suppliers = self.line_ids.filtered(lambda x: x.type == 'part' and x.demand_qty > 0).mapped('product_id').mapped('seller_ids').mapped('name').sorted(lambda x: x.id)
        grouped_bom_demand_lines = self.env['bom.demand.line'].read_group([('bom_demand_id', '=', self.id),
                                                                           ('demand_qty', '>', 0),
                                                                           ('type', '=', 'part')],
                                                                          ['ids:array_agg(id)', 'qty:sum', 'stock_qty:sum', 'demand_qty:sum'],
                                                                          ['product_id'])
        for r in grouped_bom_demand_lines:
            r['in_purchase'] = False
        # demand_lines = self.line_ids.filtered(lambda x: x.demand_qty > 0)
        # lines_with_sup = grouped_bom_demand_lines.filtered(lambda x: len(x.product_id.seller_ids) > 0)
        lines_with_sup = list(filter(lambda x: len(prod_model.browse(x['product_id'][0]).seller_ids) > 0, grouped_bom_demand_lines))
        lines_without_sup = list(filter(lambda x: len(prod_model.browse(x['product_id'][0]).seller_ids) == 0, grouped_bom_demand_lines))
        for sup in suppliers:
            po_vals = {"partner_id": sup.id, "partner_ref": "BOM Demand for: %s" % self.name}
            po = self.env['purchase.order'].create(po_vals)
            purchase_ids += po
            for l in lines_with_sup:
                if l['in_purchase']:
                    continue
                product_id = prod_model.browse(l['product_id'][0])
                for sup_line in product_id.seller_ids:
                    if sup_line.name.id == sup.id:
                        pol_vals = {"order_id": po.id,
                                    "product_id": product_id.id,
                                    "product_qty": l['demand_qty'],
                                    "name": sup_line.display_name,
                                    "price_unit": sup_line.price,
                                    "product_uom": product_id.uom_id.id,
                                    "date_planned": self.create_date,
                                    }
                        pol = self.env['purchase.order.line'].create(pol_vals)
                        l['in_purchase'] = True
                        break
        #  Without Supplier
        po_no_sup = self.env['purchase.order'].create({"partner_id": 1, "partner_ref": "BOM Demand for: %s" % self.name})
        purchase_ids += po_no_sup
        for lws in lines_without_sup:
            product_id = prod_model.browse(lws['product_id'][0])
            pol_vals = {"order_id": po_no_sup.id,
                        "product_id": product_id.id,
                        "product_qty": lws['demand_qty'],
                        "name": product_id.display_name,
                        "price_unit": product_id.price,
                        "product_uom": product_id.uom_id.id,
                        "date_planned": self.create_date,
                        }
            pol = self.env['purchase.order.line'].create(pol_vals)
            l['in_purchase'] = True
        final_pos = self.env['purchase.order']
        for po in purchase_ids:
            if len(po.order_line) == 0:
                po.button_cancel()
            else:
                final_pos += po
        self.purchase_ids = final_pos
        for po in purchase_ids:
            if po.state == 'cancel':
                po.unlink()
        self.state = 'done'

    def button_delete_all_purchase(self):
        for po in self.purchase_ids:
            po.button_cancel()
            po.unlink()

    def button_reset_to_draft(self):
        self.state = 'draft'

    def write(self, values):
        if not values.get('name'):
            if values.get('bom_id'):
                values['name'] = self.env['mrp.bom'].browse(values['bom_id']).display_name
            else:
                values['name'] = self.bom_id.display_name
        res = super(BomDemand, self).write(values)
        return res


class BomDemandLine(models.Model):
    _name = "bom.demand.line"
    _description = "BOM Demand Line"

    bom_demand_id = fields.Many2one('bom.demand', readonly=True)
    product_id = fields.Many2one('product.product', readonly=True)
    sequence = fields.Integer("#", default=0, readonly=True)
    level = fields.Integer(default=0, readonly=True)
    qty = fields.Float("Quantity", help="Quantity required by BOM x BOMs Quantity")
    stock_qty = fields.Float("In Stock", readonly=True)
    demand_qty = fields.Float("Demand", readonly=True, compute="compute_demand", store=True, help="How many to order")
    type = fields.Selection([('component', 'component'), ('part', 'part')], default='component', readonly=True)

    @api.depends('qty')
    def compute_demand(self):
        for r in self:
            r.demand_qty = r.qty - r.stock_qty
            if r.demand_qty < 0:
                r.demand_qty = 0


class BomDemandOnlyPartsGrouped(models.AbstractModel):
    _name = 'report.heg_bom_demand.report_bom_demand_only_parts_grouped'
    _description = 'BOM demand only parts grouped report model'

    def _get_report_values(self, doc_ids, data):
        grouped_bom_demand_lines = self.env['bom.demand.line'].read_group([('bom_demand_id', 'in', doc_ids),
                                                                           ('demand_qty', '>', 0),
                                                                           ('type', '=', 'part')],
                                                                          ['ids:array_agg(id)', 'qty:sum', 'stock_qty:sum', 'demand_qty:sum'],
                                                                          ['product_id'])

        docs = self.env['bom.demand'].browse(doc_ids)
        return {
            'docs': docs,
            'data': data,
            'lines_data': grouped_bom_demand_lines,
        }
