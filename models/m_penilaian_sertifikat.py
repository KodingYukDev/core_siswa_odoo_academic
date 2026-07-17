# -*- coding: utf-8 -*-
import base64
from odoo import models, fields, api, _
from odoo.exceptions import ValidationError

class SiswaKursusPenilaianSertifikat(models.Model):
    _name = 'siswa.kursus.penilaian.sertifikat'
    _description = 'Penilaian Sertifikat Kursus Siswa'
    _inherit = ['mail.thread', 'mail.activity.mixin']
    _rec_name = 'display_name'

    enrollment_id = fields.Many2one(
        'siswa.kursus.enrollment',
        string='Pendaftaran Kursus',
        required=True,
        ondelete='cascade',
        index=True
    )
    
    siswa_id = fields.Many2one(
        'm.siswa',
        string='Siswa',
        related='enrollment_id.siswa_id',
        store=True,
        readonly=True
    )
    modul_id = fields.Many2one(
        'modul.pembelajaran',
        string='Kursus/Modul',
        related='enrollment_id.modul_id',
        store=True,
        readonly=True
    )

    assessment_line_ids = fields.One2many(
        'siswa.kursus.penilaian.sertifikat.line',
        'assessment_id',
        string='Detail Penilaian'
    )

    state = fields.Selection([
        ('draft', 'Draft'),
        ('done', 'Selesai'),
    ], string='Status', default='draft', tracking=True)

    total_score = fields.Float(string='Jumlah Skor', compute='_compute_scores', store=True, digits=(16, 2))
    average_score = fields.Float(string='Rata-rata Skor', compute='_compute_scores', store=True, digits=(16, 2))
    display_name = fields.Char(string='Penilaian', compute='_compute_display_name', store=True)

    catatan = fields.Text(string='Catatan Untuk Peserta Didik')
    pelatih_id = fields.Many2one('hr.employee', string='Pelatih/Pembina')
    nilai_huruf = fields.Char(string='Nilai Akhir (Huruf)', compute='_compute_nilai_huruf', store=True)
    company_id = fields.Many2one('res.company', string='Perusahaan', default=lambda self: self.env.company)

    rapot_nama_siswa = fields.Char(string='Nama (Rapot)', compute='_compute_rapot_identity')
    rapot_kelas = fields.Char(string='Kelas (Rapot)', compute='_compute_rapot_identity')
    rapot_level = fields.Char(string='Level (Rapot)', compute='_compute_rapot_identity')
    rapot_sekolah_nama = fields.Char(string='Sekolah (Rapot)', compute='_compute_rapot_identity')

    @api.depends('siswa_id.name', 'siswa_id.class_name', 'siswa_id.level_id.name')
    def _compute_rapot_identity(self):
        for rec in self:
            rec.rapot_nama_siswa = rec.siswa_id.name
            rec.rapot_kelas = rec.siswa_id.class_name
            rec.rapot_level = rec.siswa_id.level_id.name if rec.siswa_id.level_id else False
            rec.rapot_sekolah_nama = False

    @api.depends('average_score')
    def _compute_nilai_huruf(self):
        for rec in self:
            score = rec.average_score
            if score >= 90:
                rec.nilai_huruf = 'Sangat Baik (A)'
            elif score >= 80:
                rec.nilai_huruf = 'Baik (B)'
            elif score >= 70:
                rec.nilai_huruf = 'Cukup (C)'
            else:
                rec.nilai_huruf = 'Perlu Bimbingan (D)'

    def get_rapot_pdf_base64(self):
        report = self.env.ref('students.action_report_rapot_siswa')
        pdf_content, _ = report._render_qweb_pdf(report.report_name, self.ids)
        return base64.b64encode(pdf_content).decode('utf-8')

    @api.depends('enrollment_id.display_name')
    def _compute_display_name(self):
        for rec in self:
            if rec.enrollment_id:
                rec.display_name = f"Penilaian - {rec.enrollment_id.display_name}"
            else:
                rec.display_name = "Penilaian Baru"

    @api.depends('assessment_line_ids.score')
    def _compute_scores(self):
        for rec in self:
            total = sum(line.score for line in rec.assessment_line_ids if line.score is not False)
            count = len(rec.assessment_line_ids)
            rec.total_score = total
            rec.average_score = total / count if count > 0 else 0.0

    def action_set_done(self):
        self.ensure_one()
        if self.state != 'draft':
            raise ValidationError(_("Penilaian sudah diselesaikan atau bukan dalam status draft."))
        if not self.assessment_line_ids:
            raise ValidationError(_("Tidak ada poin penilaian yang diisi."))
        for line in self.assessment_line_ids:
            if line.score is False:
                raise ValidationError(_("Mohon isi semua skor penilaian sebelum menyelesaikan."))
        self.state = 'done'
        # Set enrollment status to 'lulus' after assessment is done
        if self.enrollment_id and self.enrollment_id.status != 'lulus':
            self.enrollment_id.status = 'lulus'


class SiswaKursusPenilaianSertifikatLine(models.Model):
    _name = 'siswa.kursus.penilaian.sertifikat.line'
    _description = 'Baris Penilaian Sertifikat Kursus Siswa'
    _order = 'sequence, name'

    assessment_id = fields.Many2one(
        'siswa.kursus.penilaian.sertifikat',
        string='Penilaian Sertifikat',
        required=True,
        ondelete='cascade'
    )
    
    penilaian_item_id = fields.Many2one(
        'modul.pembelajaran.penilaian.item',
        string='Poin Penilaian',
        required=True,
        ondelete='restrict' # Prevent deletion if used in assessment
    )

    name = fields.Char(string='Materi', compute='_compute_penilaian_item_details', store=True, readonly=True)
    description = fields.Text(string='Deskripsi Singkat', compute='_compute_penilaian_item_details', store=True, readonly=True)
    sequence = fields.Integer(string='Urutan', compute='_compute_penilaian_item_details', store=True, readonly=True)
    score = fields.Float(string='Score', required=True, digits=(16, 2))

    @api.depends('penilaian_item_id')
    def _compute_penilaian_item_details(self):
        for rec in self:
            if rec.penilaian_item_id:
                rec.name = rec.penilaian_item_id.name
                rec.description = rec.penilaian_item_id.description
                rec.sequence = rec.penilaian_item_id.sequence
            else:
                rec.name = False
                rec.description = False
                rec.sequence = 0

    @api.constrains('score')
    def _check_score_range(self):
        for rec in self:
            if not (0 <= rec.score <= 100):
                raise ValidationError(_("Skor harus berada dalam rentang 0 hingga 100."))
