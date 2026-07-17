# -*- coding: utf-8 -*-
import base64
from odoo import models, fields, api, _
from odoo.exceptions import ValidationError
from odoo.tools import file_open


class RapotRenderMixin(models.AbstractModel):
    """Helper bersama untuk render PDF rapot (dipakai kedua model penilaian)."""
    _name = 'rapot.render.mixin'
    _description = 'Rapot Render Helper'

    def get_rapot_logo_base64(self):
        # Logo di-embed base64 karena path statis kadang gagal dirender wkhtmltopdf.
        with file_open('students/static/src/img/logo_kodingyuk.png', 'rb') as f:
            return base64.b64encode(f.read()).decode()


class RapotRubrikAspek(models.Model):
    """Master aspek penilaian umum untuk tabel kedua rapot
    (Pemahaman Konsep Dasar, Kemampuan Teknis, dst)."""
    _name = 'rapot.rubrik.aspek'
    _description = 'Master Aspek Rubrik Rapot'
    _order = 'sequence, name'

    name = fields.Char(string='Aspek Penilaian', required=True)
    max_score = fields.Float(string='Skor Maksimal', required=True, default=20.0)
    sequence = fields.Integer(string='Urutan', default=10)
    active = fields.Boolean(string='Aktif', default=True)

    _sql_constraints = [
        ('max_score_positive', 'check(max_score > 0)', 'Skor maksimal harus lebih dari 0!'),
    ]


class SiswaKursusPenilaianRubrikLine(models.Model):
    _name = 'siswa.kursus.penilaian.rubrik.line'
    _description = 'Baris Rubrik Rapot (Siswa Privat)'
    _order = 'sequence, id'

    assessment_id = fields.Many2one(
        'siswa.kursus.penilaian.sertifikat',
        string='Penilaian Sertifikat',
        required=True,
        ondelete='cascade',
    )
    aspek_id = fields.Many2one('rapot.rubrik.aspek', string='Aspek', ondelete='restrict')
    name = fields.Char(string='Aspek Penilaian', required=True)
    max_score = fields.Float(string='Skor Maksimal', default=20.0)
    sequence = fields.Integer(string='Urutan', default=10)
    score = fields.Float(string='Skor', default=0.0)

    @api.onchange('aspek_id')
    def _onchange_aspek_id(self):
        if self.aspek_id:
            self.name = self.aspek_id.name
            self.max_score = self.aspek_id.max_score
            self.sequence = self.aspek_id.sequence

    @api.constrains('score', 'max_score')
    def _check_score_range(self):
        for rec in self:
            if rec.score < 0 or (rec.max_score and rec.score > rec.max_score):
                raise ValidationError(
                    _("Skor '%s' harus antara 0 dan %s.") % (rec.name, rec.max_score))
