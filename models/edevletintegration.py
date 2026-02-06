from odoo import models, fields, api

class EdevletIntegration(models.Model):
    _name = 'edevlet.integration'
    _description = 'E-Invoice Integration Configuration'
    
    type = fields.Selection([
        ('1', 'EFATURA'),
        ('2', 'EARSIV'),
        ('3', 'EIRSALIYE')
    ], string='Type', required=True)
    company_code = fields.Integer(string='Company Code', required=True)
    api_user_name = fields.Char(string='API User Name', size=100, required=True)
    api_password = fields.Char(string='API Password', size=100, required=True)
    prefix = fields.Char(string='Prefix', size=5)
    ubl_version = fields.Char(string='UBL Version', size=5)
    customization_id = fields.Char(string='Customization ID', size=10)
    template_file_name = fields.Char(string='Template File Name', size=50)
    sirket_kodu = fields.Char(string='Şirket Kodu', size=10)