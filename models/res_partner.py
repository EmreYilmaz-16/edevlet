from odoo import fields, models


class ResPartner(models.Model):
    _inherit = "res.partner"

    vergi_no = fields.Char(string="Vergi No")
    vergi_dairesi = fields.Char(string="Vergi Dairesi")
    bina_numarasi = fields.Char(string="Bina Numarası")
