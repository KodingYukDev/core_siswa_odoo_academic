# -*- coding: utf-8 -*-
from odoo import models, fields


class ResCompany(models.Model):
    _inherit = 'res.company'

    rapot_koordinator_name = fields.Char(string='Nama Koordinator Ekskul')
    rapot_koordinator_signature = fields.Image(
        string='Tanda Tangan Koordinator Ekskul',
        max_width=800,
        max_height=400,
    )
