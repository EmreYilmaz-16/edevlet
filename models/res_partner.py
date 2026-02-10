from odoo import _, fields, models
from odoo.exceptions import UserError


class ResPartner(models.Model):
    _inherit = "res.partner"

    vergi_no = fields.Char(string="Vergi No")
    vergi_dairesi = fields.Char(string="Vergi Dairesi")
    bina_numarasi = fields.Char(string="Bina Numarası")
    taxpayer_check_result = fields.Text(
        string='Mükelleflik Kontrol Sonucu',
        readonly=True,
    )
    taxpayer_status = fields.Selection(
        selection=[
            ('mukellef', 'Mükellef'),
            ('non_mukellef', 'Mükellef Değil'),
        ],
        string='Mükellef Durumu',
        readonly=True,
        copy=False,
    )

    def action_check_customer_tax_id(self):
        self.ensure_one()

        tax_id_or_personal_id = (self.vergi_no or self.vat or '').strip()
        if not tax_id_or_personal_id:
            raise UserError(_('Müşteri kartında Vergi No/VAT bilgisi bulunamadı.'))

        integration = self.env['edevlet.integration'].search([('type', '=', '1')], limit=1)
        if not integration:
            raise UserError(_('Mükelleflik kontrolü için EFATURA tipinde entegrasyon tanımı bulunamadı.'))

        ticket = integration._get_forms_authentication_ticket()
        result = integration._check_customer_tax_id(
            ticket=ticket,
            tax_id_or_personal_id=tax_id_or_personal_id,
        )
        self.taxpayer_check_result = result.get('summary')
        self.taxpayer_status = result.get('status')

        return {
            'type': 'ir.actions.client',
            'tag': 'display_notification',
            'params': {
                'title': _('Mükelleflik Kontrolü'),
                'message': result.get('summary'),
                'type': 'success',
                'sticky': False,
            },
        }
