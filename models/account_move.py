import base64

from odoo import api, fields, models, _
from odoo.exceptions import ValidationError
from odoo.modules.module import get_module_resource

PROFILE_TYPES = [
    ('TICARIFATURA', 'TICARIFATURA'),
    ('IHRACAT', 'IHRACAT'),
    ('TEMELFATURA', 'TEMELFATURA'),
    ('YOLCUBERABERFATURA', 'YOLCUBERABERFATURA'),
    ('BEDELSIZIHRACAT', 'BEDELSIZIHRACAT'),
    ('KAMU', 'KAMU'),
    ('ENERJI', 'ENERJI'),
    ('ILAC_TIBBICIHAZ', 'ILAC_TIBBICIHAZ'),
    ('MIKROIHRACAT', 'MIKROIHRACAT'),
]

INVOICE_TYPE_CODES = [
    ('SATIS', 'SATIS'),
    ('IADE', 'IADE'),
    ('IHRACKAYITLI', 'IHRACKAYITLI'),
    ('KONAKLAMAVERGISI', 'KONAKLAMAVERGISI'),
    ('SGK', 'SGK'),
    ('TEVKIFATIADE', 'TEVKIFATIADE'),
    ('SARJ', 'SARJ'),
    ('SARJANLIK', 'SARJANLIK'),
    ('TEKNOLOJIDESTEK', 'TEKNOLOJIDESTEK'),
]


class AccountMove(models.Model):
    _inherit = 'account.move'

    profile_type = fields.Selection(
        PROFILE_TYPES,
        string='Profile Type',
        default='TICARIFATURA',
    )
    invoice_type_code = fields.Selection(
        INVOICE_TYPE_CODES,
        string='Invoice Type Code',
        default='SATIS',
    )

    @api.constrains('profile_type', 'move_type')
    def _check_profile_type_required(self):
        for move in self:
            if move.move_type in ('out_invoice', 'out_refund') and not move.profile_type:
                raise ValidationError(_('Profile Type is required for customer invoices.'))

    @api.constrains('invoice_type_code', 'move_type')
    def _check_invoice_type_code_required(self):
        for move in self:
            if move.move_type in ('out_invoice', 'out_refund') and not move.invoice_type_code:
                raise ValidationError(_('Invoice Type Code is required for customer invoices.'))

    def action_download_invoice_xml(self):
        self.ensure_one()
        module_name = __package__.split('.')[0]
        xml_path = get_module_resource(module_name, 'ornek_xml.xml')
        if not xml_path:
            raise ValidationError(_('Sample XML file could not be found.'))
        with open(xml_path, 'rb') as xml_file:
            xml_content = xml_file.read()
        attachment = self.env['ir.attachment'].create({
            'name': f"{self.name or 'invoice'}.xml",
            'type': 'binary',
            'datas': base64.b64encode(xml_content),
            'mimetype': 'application/xml',
            'res_model': self._name,
            'res_id': self.id,
        })
        return {
            'type': 'ir.actions.act_url',
            'url': f"/web/content/{attachment.id}?download=true",
            'target': 'self',
        }
