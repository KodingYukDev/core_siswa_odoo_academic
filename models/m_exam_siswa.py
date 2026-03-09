# -*- coding: utf-8 -*-
import mimetypes
import uuid
from odoo import models, fields, api, _
from odoo.exceptions import UserError

class SiswaKursusExam(models.Model):
    _name = 'siswa.kursus.exam'
    _description = 'Ujian Siswa'
    _inherit = ['mail.thread', 'mail.activity.mixin']
    _rec_name = 'display_name'

    enrollment_id = fields.Many2one(
        'siswa.kursus.enrollment',
        string='Pendaftaran Kursus',
        required=True,
        ondelete='cascade'
    )
    
    siswa_id = fields.Many2one('m.siswa', string='Siswa', related='enrollment_id.siswa_id', store=True, readonly=True)
    modul_id = fields.Many2one('modul.pembelajaran', string='Modul', related='enrollment_id.modul_id', store=True, readonly=True)
    
    tanggal_ujian = fields.Date(string='Tanggal Ujian', default=fields.Date.context_today)
    
    exam_type = fields.Selection([
        ('pilihan_ganda', 'Pilihan Ganda'),
        ('essai', 'Essai'),
        ('praktik', 'Praktik')
    ], string='Tipe Ujian', required=True)
    
    line_ids = fields.One2many('siswa.kursus.exam.line', 'exam_id', string='Detail Pertanyaan')
    
    total_score = fields.Float(string='Skor Akhir', compute='_compute_total_score', store=True, digits=(16, 2))
    start_time = fields.Datetime(string='Waktu Mulai Ujian', copy=False)
    time_limit_minutes = fields.Integer(string='Batas Waktu (Menit)', default=0)

    state = fields.Selection([
        ('draft', 'Draft'),
        ('in_progress', 'Sedang Dikerjakan'),
        ('done', 'Selesai')
    ], string='Status', default='draft', tracking=True)

    display_name = fields.Char(string='Nama Ujian', compute='_compute_display_name', store=True)

    @api.depends('enrollment_id.name', 'exam_type')
    def _compute_display_name(self):
        for rec in self:
            type_label = dict(self._fields['exam_type'].selection).get(rec.exam_type)
            rec.display_name = f"Ujian {type_label} - {rec.enrollment_id.name}"

    @api.depends('line_ids.score')
    def _compute_total_score(self):
        for rec in self:
            if rec.exam_type == 'pilihan_ganda':
                # For PG, simple average or sum? Let's use average based on correct/total
                total_lines = len(rec.line_ids)
                correct_lines = len(rec.line_ids.filtered(lambda l: l.is_correct))
                rec.total_score = (correct_lines / total_lines * 100) if total_lines > 0 else 0.0
            else:
                # For Essai and Praktik, we use the score field on lines
                total_score = sum(line.score for line in rec.line_ids)
                count = len(rec.line_ids)
                rec.total_score = total_score / count if count > 0 else 0.0

    def action_start(self):
        self.ensure_one()
        if self.state != 'draft':
            return
        time_config = self.env['exam.time.config'].search([('exam_type', '=', self.exam_type)], limit=1)
        duration = time_config.duration_minutes if time_config else 30
        self.write({
            'state': 'in_progress',
            'start_time': fields.Datetime.now(),
            'time_limit_minutes': duration,
        })

    def action_done(self):
        self.ensure_one()
        self.state = 'done'

class SiswaKursusExamLine(models.Model):
    _name = 'siswa.kursus.exam.line'
    _description = 'Detail Jawaban Ujian Siswa'
    _order = 'sequence'

    exam_id = fields.Many2one('siswa.kursus.exam', string='Ujian', ondelete='cascade')
    exam_type = fields.Selection(related='exam_id.exam_type', readonly=True)
    sequence = fields.Integer("No")
    
    # Data yang DI-COPY dari modul pembelajaran (History)
    question = fields.Text("Pertanyaan (Snapshot)")
    category_name = fields.Char("Kategori (Snapshot)")
    
    # Pilihan Ganda Snapshot
    option_a = fields.Char("Opsi A")
    option_b = fields.Char("Opsi B")
    option_c = fields.Char("Opsi C")
    option_d = fields.Char("Opsi D")
    correct_option = fields.Selection([
        ('A', 'A'), ('B', 'B'), ('C', 'C'), ('D', 'D')
    ], string="Opsi Benar (Snapshot)")
    
    # Praktik Snapshot
    practice = fields.Char("Praktik (Snapshot)")
    description = fields.Text("Deskripsi (Snapshot)")
    
    # Media Snapshot
    media_url = fields.Char("Media URL (Snapshot)")
    media_type = fields.Selection([
        ('image', 'Image'), ('video', 'Video'), ('other', 'Other')
    ], string="Media Type (Snapshot)")
    
    # Input dari Siswa / Trainer
    student_answer_selection = fields.Selection([
        ('A', 'A'), ('B', 'B'), ('C', 'C'), ('D', 'D')
    ], string='Jawaban Siswa (PG)')
    
    student_answer_text = fields.Text(string='Jawaban Siswa (Essai)')
    
    trainer_status = fields.Selection([
        ('berhasil', 'Berhasil'),
        ('gagal', 'Gagal')
    ], string='Status Praktik')
    
    trainer_note = fields.Text(string='Catatan Mentor')
    
    score = fields.Float(string='Skor', digits=(16, 2))
    is_correct = fields.Boolean(string='Benar?', compute='_compute_is_correct', store=True)

    @api.depends('student_answer_selection', 'correct_option')
    def _compute_is_correct(self):
        for rec in self:
            if rec.exam_type == 'pilihan_ganda':
                rec.is_correct = (rec.student_answer_selection == rec.correct_option) if rec.student_answer_selection else False
            else:
                rec.is_correct = False

    media_preview = fields.Html("Preview Media", compute="_compute_media_preview", sanitize=False)

    @api.depends('media_url', 'media_type')
    def _compute_media_preview(self):
        for rec in self:
            if rec.media_url:
                if rec.media_type == 'image':
                    rec.media_preview = f'<img src="{rec.media_url}" style="max-height: 100px;"/>'
                elif rec.media_type == 'video':
                    rec.media_preview = f'<video width="200" height="120" controls><source src="{rec.media_url}">Your browser does not support the video tag.</video>'
                else:
                    rec.media_preview = f'<a href="{rec.media_url}" target="_blank">View Media</a>'
            else:
                rec.media_preview = False

    def action_open_media(self):
        self.ensure_one()
        if self.media_url:
            return {
                'type': 'ir.actions.act_url',
                'url': self.media_url,
                'target': 'new',
            }
        else:
            raise UserError(_("Media tidak tersedia."))
