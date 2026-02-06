from odoo import api, fields, models, _
from odoo.exceptions import ValidationError

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


class AccountMove(models.Model):
    _inherit = 'account.move'

    profile_type = fields.Selection(PROFILE_TYPES, string='Profile Type')

    @api.constrains('profile_type', 'move_type')
    def _check_profile_type_required(self):
        for move in self:
            if move.move_type in ('out_invoice', 'out_refund') and not move.profile_type:
                raise ValidationError(_('Profile Type is required for customer invoices.'))
