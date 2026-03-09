# -*- coding: utf-8 -*-
from odoo import models, fields, api

class ExamTimeConfig(models.Model):
    _name = 'exam.time.config'
    _description = 'Master Waktu Ujian'
    _order = 'exam_type'

    name = fields.Char(string='Nama', compute='_compute_name', store=True)
    exam_type = fields.Selection([
        ('pilihan_ganda', 'Pilihan Ganda'),
        ('essai', 'Essai'),
        ('praktik', 'Praktik')
    ], string='Tipe Ujian', required=True)
    duration_minutes = fields.Integer(string='Durasi (Menit)', required=True, default=30)

    _sql_constraints = [
        ('exam_type_unique', 'unique(exam_type)', 'Setiap tipe ujian hanya boleh punya satu konfigurasi waktu!')
    ]

    @api.depends('exam_type', 'duration_minutes')
    def _compute_name(self):
        type_labels = dict(self._fields['exam_type'].selection)
        for rec in self:
            label = type_labels.get(rec.exam_type, '')
            rec.name = f"{label} - {rec.duration_minutes} Menit"
