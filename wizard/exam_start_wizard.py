# -*- coding: utf-8 -*-
from odoo import models, fields, api, _
from odoo.exceptions import UserError
import random

class ExamStartWizard(models.TransientModel):
    _name = 'siswa.kursus.exam.start.wizard'
    _description = 'Wizard Mulai Ujian / Remedial'

    enrollment_id = fields.Many2one('siswa.kursus.enrollment', string='Pendaftaran', required=True)
    
    exam_type_pg = fields.Boolean(string='Pilihan Ganda')
    exam_type_essai = fields.Boolean(string='Essai')
    exam_type_praktik = fields.Boolean(string='Praktik')

    @api.model
    def default_get(self, fields_list):
        res = super(ExamStartWizard, self).default_get(fields_list)
        enrollment_id = self.env.context.get('active_id')
        if enrollment_id:
            res['enrollment_id'] = enrollment_id
            enrollment = self.env['siswa.kursus.enrollment'].browse(enrollment_id)
            
            # Pre-select based on existing exam templates in the module
            if enrollment.modul_id:
                templates = enrollment.modul_id.exam_ids
                res['exam_type_pg'] = any(t.exam_type == 'pilihan_ganda' for t in templates)
                res['exam_type_essai'] = any(t.exam_type == 'essai' for t in templates)
                res['exam_type_praktik'] = any(t.exam_type == 'praktik' for t in templates)
                
                # Logic: If they already have a PASSED exam of a certain type, maybe uncheck it?
                # User said: "jadi kalau yang udah lulus gitu ga perlu lagi di ulang"
                # Let's find latest attempts
                for exam_type in ['pilihan_ganda', 'essai', 'praktik']:
                    latest = self.env['siswa.kursus.exam'].search([
                        ('enrollment_id', '=', enrollment_id),
                        ('exam_type', '=', exam_type)
                    ], order='attempt_number desc', limit=1)
                    
                    if latest and latest.pass_fail_status == 'pass':
                        res[f'exam_type_{"pg" if exam_type == "pilihan_ganda" else exam_type}'] = False
        return res

    def action_confirm(self):
        self.ensure_one()
        enrollment = self.enrollment_id
        
        # Validation
        if not (self.exam_type_pg or self.exam_type_essai or self.exam_type_praktik):
            raise UserError(_("Pilih setidaknya satu tipe ujian untuk dimulai."))

        selected_types = []
        if self.exam_type_pg: selected_types.append('pilihan_ganda')
        if self.exam_type_essai: selected_types.append('essai')
        if self.exam_type_praktik: selected_types.append('praktik')

        # Check attendance
        attended = enrollment.jumlah_pertemuan_diikuti or 0
        required = enrollment.jumlah_pertemuan_wajib or 0
        if attended < required:
            raise UserError(_(f"Siswa belum menyelesaikan semua pertemuan wajib ({attended}/{required})."))

        # Create access code if needed
        if not enrollment.access_code or not enrollment.access_code_active:
            enrollment.action_generate_access_code()

        created_count = 0
        for exam_template in enrollment.modul_id.exam_ids:
            if exam_template.exam_type not in selected_types:
                continue

            existing_attempts = self.env['siswa.kursus.exam'].search_count([
                ('enrollment_id', '=', enrollment.id),
                ('exam_type', '=', exam_template.exam_type)
            ])
            attempt_number = existing_attempts + 1

            new_exam = self.env['siswa.kursus.exam'].create({
                'enrollment_id': enrollment.id,
                'exam_type': exam_template.exam_type,
                'time_limit_minutes': exam_template.time_limit_minutes,
                'attempt_number': attempt_number,
            })
            
            # Shuffle questions
            lines_to_copy = list(exam_template.line_ids)
            random.shuffle(lines_to_copy)
            
            for idx, line in enumerate(lines_to_copy, 1):
                self.env['siswa.kursus.exam.line'].create({
                    'exam_id': new_exam.id,
                    'sequence': idx,
                    'question': line.question,
                    'category_name': line.category_id.name,
                    'option_a': line.option_a,
                    'option_b': line.option_b,
                    'option_c': line.option_c,
                    'option_d': line.option_d,
                    'option_a_url': line.option_a_url,
                    'option_b_url': line.option_b_url,
                    'option_c_url': line.option_c_url,
                    'option_d_url': line.option_d_url,
                    'correct_option': line.correct_option,
                    'practice': line.practice,
                    'description': line.description,
                    'project_url': line.project_url,
                    'media_url': line.media_url,
                    'media_type': line.media_type,
                })
            created_count += 1

        return enrollment.action_view_student_exams()
