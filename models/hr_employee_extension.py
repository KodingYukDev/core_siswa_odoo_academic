# -*- coding: utf-8 -*-
from odoo import models, fields


class HrEmployee(models.Model):
    _inherit = 'hr.employee'

    signature_image = fields.Image(
        string='Tanda Tangan',
        max_width=800,
        max_height=400,
        help='Gambar tanda tangan untuk dicetak di rapot/sertifikat.'
    )
