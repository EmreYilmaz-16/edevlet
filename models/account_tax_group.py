from odoo import fields, models


class AccountTaxGroup(models.Model):
    _inherit = 'account.tax.group'

    tax_code = fields.Char(string='Tax Code')
    tax_code_name = fields.Char(string='Tax Code Name')
