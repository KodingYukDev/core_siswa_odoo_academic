# -*- coding: utf-8 -*-
from odoo import models, fields, api, _
from odoo.exceptions import ValidationError

class StudentCourseEnrollment(models.Model):
    _name = 'siswa.kursus.enrollment'
    _description = 'Pendaftaran Kursus Siswa'
    _order = 'tanggal_mulai desc'

    name = fields.Char(string="Pendaftaran", compute='_compute_name', store=True)
    
    siswa_id = fields.Many2one(
        'm.siswa', 
        string='Siswa', 
        required=True, 
        ondelete='cascade',
        index=True
    )
    modul_id = fields.Many2one(
        'modul.pembelajaran', 
        string='Kursus/Modul', 
        required=True
    )
    tanggal_mulai = fields.Date(
        string='Tanggal Mulai', 
        default=fields.Date.context_today,
        required=True
    )
    tanggal_selesai = fields.Date(string='Tanggal Selesai')
    
    status = fields.Selection([
        ('aktif', 'Aktif'),
        ('lulus', 'Lulus'),
        ('berhenti', 'Berhenti')
    ], string='Status', default='aktif', required=True)

    jumlah_pertemuan_wajib = fields.Integer(
        string="Sesi Wajib",
        compute='_compute_jumlah_pertemuan_wajib',
        store=True
    )

    # Field ini akan diisi oleh modul absensi_siswa
    _sql_constraints = [
        ('enrollment_unique', 'unique(siswa_id, modul_id)', 'Siswa sudah terdaftar di kursus ini!')
    ]

    penilaian_ids = fields.One2many(
        'siswa.kursus.penilaian.sertifikat',
        'enrollment_id',
        string='Penilaian Sertifikat'
    )

    average_score = fields.Float(
        string='Rata-rata Nilai',
        related='penilaian_ids.average_score',
        store=True,
        readonly=True
    )

    assessment_line_ids = fields.One2many(
        string='Detail Penilaian',
        related='penilaian_ids.assessment_line_ids',
        readonly=True
    )
    
    exam_ids = fields.One2many(
        'siswa.kursus.exam',
        'enrollment_id',
        string='Ujian Siswa'
    )

    # Dihitung dari absensi_siswa (sudah ada di enrollment_extension, tapi kita pastikan di sini)
    jumlah_pertemuan_diikuti = fields.Integer(
        string="Pertemuan Diikuti",
        compute='_compute_jumlah_pertemuan_diikuti',
        store=True
    )

    @api.depends('modul_id') # In actual use, this will depend on absensi records
    def _compute_jumlah_pertemuan_diikuti(self):
        # This will be handled by absensi_siswa module extension
        # But we ensure it's here for the logic
        pass

    def action_start_exam(self):
        self.ensure_one()
        if self.jumlah_pertemuan_diikuti < self.jumlah_pertemuan_wajib:
            raise UserError(_("Siswa belum menyelesaikan semua pertemuan wajib (%s/%s).") % (self.jumlah_pertemuan_diikuti, self.jumlah_pertemuan_wajib))
        
        if not self.modul_id:
            raise UserError(_("Modul pembelajaran belum ditentukan."))
        
        if not self.modul_id.exam_ids:
            raise UserError(_("Tidak ada soal ujian di modul %s.") % self.modul_id.name)

        # Generate snapshot ujian
        for exam_template in self.modul_id.exam_ids:
            # Cek jika sudah ada ujian tipe ini yang belum selesai
            existing = self.exam_ids.filtered(lambda e: e.exam_type == exam_template.exam_type)
            if existing:
                continue
            
            new_exam = self.env['siswa.kursus.exam'].create({
                'enrollment_id': self.id,
                'exam_type': exam_template.exam_type,
            })
            
            for line in exam_template.line_ids:
                self.env['siswa.kursus.exam.line'].create({
                    'exam_id': new_exam.id,
                    'sequence': line.sequence,
                    'question': line.question,
                    'category_name': line.category_id.name,
                    'option_a': line.option_a,
                    'option_b': line.option_b,
                    'option_c': line.option_c,
                    'option_d': line.option_d,
                    'correct_option': line.correct_option,
                    'practice': line.practice,
                    'description': line.description,
                    'media_url': line.media_url,
                    'media_type': line.media_type,
                })
        
        return self.action_view_student_exams()

    def action_view_student_exams(self):
        self.ensure_one()
        action = self.env['ir.actions.act_window']._for_xml_id('students.action_siswa_kursus_exam')
        action['domain'] = [('enrollment_id', '=', self.id)]
        action['context'] = {'default_enrollment_id': self.id}
        return action
    
    # Fields and methods moved from enrollment_extension for direct availability
    has_certificate_assessment = fields.Boolean(
        string="Ada Penilaian Sertifikat",
        compute="_compute_has_certificate_assessment",
        store=False # No need to store, computed on-the-fly
    )

    @api.depends('status') 
    def _compute_has_certificate_assessment(self):
        for rec in self:
            rec.has_certificate_assessment = bool(self.env['siswa.kursus.penilaian.sertifikat'].search([('enrollment_id', '=', rec.id)], limit=1))

    def action_create_or_view_certificate_assessment(self):
        self.ensure_one()
        
        # Search for existing assessment
        existing_assessment = self.env['siswa.kursus.penilaian.sertifikat'].search([('enrollment_id', '=', self.id)], limit=1)
        
        action = self.env['ir.actions.act_window']._for_xml_id('students.action_siswa_kursus_penilaian_sertifikat')
        
        if existing_assessment:
            action['res_id'] = existing_assessment.id
            action['views'] = [(False, 'form')] 
            return action

        # Create new assessment
        new_assessment = self.env['siswa.kursus.penilaian.sertifikat'].create({
            'enrollment_id': self.id,
        })

        # Pre-fill assessment lines from modul.pembelajaran.penilaian.item
        if self.modul_id and self.modul_id.penilaian_item_ids:
            for item in self.modul_id.penilaian_item_ids:
                self.env['siswa.kursus.penilaian.sertifikat.line'].create({
                    'assessment_id': new_assessment.id,
                    'penilaian_item_id': item.id,
                    'sequence': item.sequence,
                    'score': 0.0,
                })
        
        action['res_id'] = new_assessment.id
        action['views'] = [(False, 'form')]
        return action


    @api.depends('siswa_id.name', 'modul_id.name')
    def _compute_name(self):
        for rec in self:
            if rec.siswa_id and rec.modul_id:
                rec.name = f"{rec.siswa_id.name} - {rec.modul_id.name}"
            else:
                rec.name = "Pendaftaran Baru"

    @api.depends('modul_id.materi_ids')
    def _compute_jumlah_pertemuan_wajib(self):
        for rec in self:
            if rec.modul_id:
                rec.jumlah_pertemuan_wajib = len(rec.modul_id.materi_ids)
            else:
                rec.jumlah_pertemuan_wajib = 0
