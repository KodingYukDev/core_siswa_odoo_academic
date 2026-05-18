# -*- coding: utf-8 -*-
import json
import logging
from datetime import datetime, timedelta
from odoo import http, fields
from odoo.http import request

_logger = logging.getLogger(__name__)


class StudentExamAPIController(http.Controller):

    def _validate_access_code(self, access_code):
        """
        Validate access code.
        New approach: access_code is on m.siswa (prefix ST-).
        Legacy: access_code on siswa.kursus.enrollment (prefix EXM- or ST- on enrollment).
        Returns (student, enrollment) tuple or (False, False).
        """
        if not access_code:
            return False, False

        # New: try student-level access code first (ST- prefix)
        student = request.env['m.siswa'].sudo().search([
            ('access_code', '=', access_code),
            ('access_code_active', '=', True),
        ], limit=1)
        if student:
            # Find active enrollment for this student
            enrollment = request.env['siswa.kursus.enrollment'].sudo().search([
                ('siswa_id', '=', student.id),
                ('status', '=', 'aktif'),
            ], order='tanggal_mulai desc', limit=1)
            return student, enrollment

        # Legacy: try enrollment-level access code (EXM- or old ST- on enrollment)
        enrollment = request.env['siswa.kursus.enrollment'].sudo().search([
            ('access_code', '=', access_code),
            ('access_code_active', '=', True),
        ], limit=1)
        if enrollment:
            return enrollment.siswa_id, enrollment

        return False, False

    # ----------------------------------------------------------------
    # LOGIN: Validate access code, return enrollment + student + exams
    # ----------------------------------------------------------------
    @http.route(['/api/v1/student/login', '/api/v1/student/login/'], type='json', auth='public', methods=['POST'], csrf=False, cors='*')
    def student_login(self, **kwargs):
        try:
            # For type='json', Odoo automatically parses params into kwargs
            access_code = kwargs.get('access_code', '').strip().upper()

            student, enrollment = self._validate_access_code(access_code)
            if not student:
                return {'success': False, 'error': 'Kode akses tidak valid atau sudah tidak aktif.'}

            if not enrollment:
                return {'success': False, 'error': 'Siswa belum memiliki kursus aktif.'}

            modul = enrollment.modul_id

            # Get exams for this enrollment
            exams = []
            for exam in enrollment.exam_ids:
                remaining_seconds = 0
                if exam.start_time and exam.time_limit_minutes and exam.state == 'in_progress':
                    elapsed = (fields.Datetime.now() - exam.start_time).total_seconds()
                    total_limit = exam.time_limit_minutes * 60
                    if elapsed >= total_limit:
                        exam.action_done(status='timeout')
                        remaining_seconds = 0
                    else:
                        remaining_seconds = max(0, total_limit - elapsed)
                elif exam.state == 'done':
                    remaining_seconds = 0
                elif exam.state == 'draft':
                    # Remaining seconds is full time for draft
                    remaining_seconds = exam.time_limit_minutes * 60
                    if not remaining_seconds:
                        # Find default duration if not set
                        time_config = request.env['exam.time.config'].sudo().search([('exam_type', '=', exam.exam_type)], limit=1)
                        remaining_seconds = (time_config.duration_minutes if time_config else 30) * 60

                exams.append({
                    'id': exam.id,
                    'display_name': exam.display_name,
                    'exam_type': exam.exam_type,
                    'tanggal_ujian': str(exam.tanggal_ujian) if exam.tanggal_ujian else '',
                    'total_score': exam.total_score,
                    'state': exam.state,
                    'start_time': str(exam.start_time) if exam.start_time else '',
                    'time_limit_minutes': exam.time_limit_minutes,
                    'remaining_seconds': int(remaining_seconds),
                })

            res = {
                'success': True,
                'enrollment': {
                    'id': enrollment.id,
                    'name': enrollment.name,
                    'modul_name': modul.name if modul else '',
                    'modul_id': modul.id if modul else 0,
                    'status': enrollment.status,
                },
                'student': {
                    'id': student.id,
                    'name': student.name,
                },
                'exams': exams,
            }
            return res

        except Exception as e:
            _logger.error(f"Student Login Error: {e}")
            return {'success': False, 'error': str(e)}

    # ----------------------------------------------------------------
    # DASHBOARD DATA: Full data for the student dashboard
    # ----------------------------------------------------------------
    @http.route(['/api/v1/student/dashboard_data', '/api/v1/student/dashboard_data/'], type='json', auth='public', methods=['POST'], csrf=False, cors='*')
    def student_dashboard_data(self, **kwargs):
        try:
            access_code = kwargs.get('access_code', '').strip().upper()

            student, enrollment = self._validate_access_code(access_code)
            if not student:
                return {'success': False, 'error': 'Kode akses tidak valid.'}

            if not enrollment:
                return {'success': False, 'error': 'Siswa belum memiliki kursus aktif.'}

            modul = enrollment.modul_id

            # 1. Profile Data
            profile = {
                'id': student.id,
                'name': student.name,
                'nis': student.nis or '',
                'class_name': student.class_name or '',
                'level_name': student.level_id.name if student.level_id else '',
                'tipe_siswa': student.tipe_siswa,
                'join_date': str(student.join_date) if student.join_date else '',
                'status': student.status,
                'bio': student.bio_singkat or '',
            }

            # 2. Attendance Data
            absensi_rec = request.env['absensi.siswa.absensi'].sudo().search([('enrollment_id', '=', enrollment.id)], limit=1)
            attendance_summary = {
                'total_hadir': 0,
                'total_izin': 0,
                'total_absen': 0,
                'total_pertemuan': 0,
                'pertemuan_ke_berapa': 0,
            }
            attendance_history = []
            
            if absensi_rec:
                attendance_summary['total_pertemuan'] = absensi_rec.pertemuan_count
                for line in absensi_rec.attendance_line_ids:
                    if line.status == 'hadir': attendance_summary['total_hadir'] += 1
                    elif line.status == 'izin': attendance_summary['total_izin'] += 1
                    elif line.status == 'absen': attendance_summary['total_absen'] += 1
                    
                    if line.status:
                        attendance_summary['pertemuan_ke_berapa'] += 1
                    
                    attendance_history.append({
                        'id': line.id,
                        'pertemuan_ke': line.pertemuan_ke,
                        'display_name': line.display_name,
                        'status': line.status or 'belum',
                        'tanggal_waktu': str(line.tanggal_waktu) if line.tanggal_waktu else '',
                        'notes': line.notes or '',
                    })

            # 3. Certification / Performance
            penilaian_rec = request.env['siswa.kursus.penilaian.sertifikat'].sudo().search([('enrollment_id', '=', enrollment.id)], limit=1)
            performance = {
                'total_score': penilaian_rec.total_score if penilaian_rec else 0,
                'average_score': penilaian_rec.average_score if penilaian_rec else 0,
                'state': penilaian_rec.state if penilaian_rec else 'draft',
                'lines': []
            }
            if penilaian_rec:
                for line in penilaian_rec.assessment_line_ids:
                    performance['lines'].append({
                        'name': line.name,
                        'score': line.score,
                    })

            # 4. Exam List (Reuse logic from login)
            exams = []
            for exam in enrollment.exam_ids:
                remaining_seconds = 0
                if exam.start_time and exam.time_limit_minutes and exam.state == 'in_progress':
                    elapsed = (fields.Datetime.now() - exam.start_time).total_seconds()
                    total_limit = exam.time_limit_minutes * 60
                    if elapsed >= total_limit:
                        exam.action_done(status='timeout')
                        remaining_seconds = 0
                    else:
                        remaining_seconds = max(0, total_limit - elapsed)
                elif exam.state == 'done':
                    remaining_seconds = 0
                elif exam.state == 'draft':
                    time_config = request.env['exam.time.config'].sudo().search([('exam_type', '=', exam.exam_type)], limit=1)
                    remaining_seconds = (exam.time_limit_minutes if exam.time_limit_minutes else (time_config.duration_minutes if time_config else 30)) * 60

                exams.append({
                    'id': exam.id,
                    'display_name': exam.display_name,
                    'exam_type': exam.exam_type,
                    'state': exam.state,
                    'total_score': exam.total_score,
                    'remaining_seconds': int(remaining_seconds),
                })

            res = {
                'success': True,
                'profile': profile,
                'attendance_summary': attendance_summary,
                'attendance_history': attendance_history,
                'performance': performance,
                'exams': exams,
                'enrollment': {
                    'id': enrollment.id,
                    'name': enrollment.name,
                    'modul_name': modul.name if modul else '',
                    'status': enrollment.status,
                }
            }
            return res

        except Exception as e:
            _logger.error(f"Dashboard Data Error: {e}")
            return {'success': False, 'error': str(e)}

    # ----------------------------------------------------------------
    # EXAM DETAIL: Get exam questions/lines
    # ----------------------------------------------------------------
    @http.route(['/api/v1/student/exam/detail', '/api/v1/student/exam/detail/'], type='json', auth='public', methods=['POST'], csrf=False, cors='*')
    def exam_detail(self, **kwargs):
        try:
            access_code = kwargs.get('access_code', '').strip().upper()
            exam_id = kwargs.get('exam_id')

            student, enrollment = self._validate_access_code(access_code)
            if not enrollment:
                return {'success': False, 'error': 'Kode akses tidak valid.'}

            exam = request.env['siswa.kursus.exam'].sudo().search([
                ('id', '=', int(exam_id)),
                ('enrollment_id', '=', enrollment.id),
            ], limit=1)

            if not exam:
                return {'success': False, 'error': 'Ujian tidak ditemukan.'}

            remaining_seconds = 0
            if exam.start_time and exam.time_limit_minutes and exam.state == 'in_progress':
                elapsed = (fields.Datetime.now() - exam.start_time).total_seconds()
                total_limit = exam.time_limit_minutes * 60
                if elapsed >= total_limit:
                    exam.action_done()
                    remaining_seconds = 0
                else:
                    remaining_seconds = max(0, total_limit - elapsed)

            lines = []
            for line in exam.line_ids:
                line_data = {
                    'id': line.id,
                    'sequence': line.sequence,
                    'question': line.question or '',
                    'category_name': line.category_name or '',
                    'option_a': line.option_a or '',
                    'option_b': line.option_b or '',
                    'option_c': line.option_c or '',
                    'option_d': line.option_d or '',
                    'option_a_url': line.option_a_url or '',
                    'option_b_url': line.option_b_url or '',
                    'option_c_url': line.option_c_url or '',
                    'option_d_url': line.option_d_url or '',
                    'practice': line.practice or '',
                    'description': line.description or '',
                    'media_url': line.media_url or '',
                    'media_type': line.media_type or '',
                    'student_answer_selection': line.student_answer_selection or '',
                    'student_answer_text': line.student_answer_text or '',
                    'trainer_status': line.trainer_status or '',
                    'trainer_note': line.trainer_note or '',
                    'score': line.score,
                    'is_correct': line.is_correct,
                }
                lines.append(line_data)

            res = {
                'success': True,
                'exam': {
                    'id': exam.id,
                    'display_name': exam.display_name,
                    'exam_type': exam.exam_type,
                    'state': exam.state,
                    'total_score': exam.total_score,
                    'start_time': str(exam.start_time) if exam.start_time else '',
                    'time_limit_minutes': exam.time_limit_minutes,
                    'remaining_seconds': int(remaining_seconds),
                },
                'lines': lines,
            }
            return res

        except Exception as e:
            _logger.error(f"Exam Detail Error: {e}")
            return {'success': False, 'error': str(e)}

    # ----------------------------------------------------------------
    # START EXAM: Set state to in_progress, record start_time
    # ----------------------------------------------------------------
    @http.route(['/api/v1/student/exam/start', '/api/v1/student/exam/start/'], type='json', auth='public', methods=['POST'], csrf=False, cors='*')
    def exam_start(self, **kwargs):
        try:
            access_code = kwargs.get('access_code', '').strip().upper()
            exam_id = kwargs.get('exam_id')

            student, enrollment = self._validate_access_code(access_code)
            if not enrollment:
                return {'success': False, 'error': 'Kode akses tidak valid.'}

            exam = request.env['siswa.kursus.exam'].sudo().search([
                ('id', '=', int(exam_id)),
                ('enrollment_id', '=', enrollment.id),
            ], limit=1)

            if not exam:
                return {'success': False, 'error': 'Ujian tidak ditemukan.'}

            if exam.state == 'done':
                return request.make_json_response({'success': False, 'error': 'Ujian sudah selesai.'})

            if exam.state == 'draft':
                exam.action_start()

            remaining_seconds = 0
            if exam.start_time and exam.time_limit_minutes:
                if exam.state == 'in_progress':
                    elapsed = (fields.Datetime.now() - exam.start_time).total_seconds()
                    total_limit = exam.time_limit_minutes * 60
                    if elapsed >= total_limit:
                        exam.action_done(status='timeout')
                        remaining_seconds = 0
                    else:
                        remaining_seconds = max(0, total_limit - elapsed)
                elif exam.state == 'done':
                    remaining_seconds = 0
                else:
                    # Should not happen as we just called action_start() for draft
                    remaining_seconds = exam.time_limit_minutes * 60

            res = {
                'success': True,
                'start_time': str(exam.start_time),
                'time_limit_minutes': exam.time_limit_minutes,
                'remaining_seconds': int(remaining_seconds),
            }
            return res

        except Exception as e:
            _logger.error(f"Exam Start Error: {e}")
            return {'success': False, 'error': str(e)}

    @http.route(['/api/v1/student/exam/submit', '/api/v1/student/exam/submit/'], type='json', auth='public', methods=['POST'], csrf=False, cors='*')
    def exam_submit(self, **kwargs):
        try:
            access_code = kwargs.get('access_code', '').strip().upper()
            exam_id = kwargs.get('exam_id')
            answers = kwargs.get('answers', [])

            student, enrollment = self._validate_access_code(access_code)
            if not enrollment:
                return {'success': False, 'error': 'Kode akses tidak valid.'}

            exam = request.env['siswa.kursus.exam'].sudo().search([
                ('id', '=', int(exam_id)),
                ('enrollment_id', '=', enrollment.id),
            ], limit=1)

            if not exam:
                return {'success': False, 'error': 'Ujian tidak ditemukan.'}

            if exam.state == 'done':
                return {'success': False, 'error': 'Ujian sudah selesai, tidak bisa submit lagi.'}

            ExamLine = request.env['siswa.kursus.exam.line'].sudo()
            for ans in answers:
                line_id = ans.get('line_id')
                line = ExamLine.search([('id', '=', int(line_id)), ('exam_id', '=', exam.id)], limit=1)
                if not line:
                    continue
                update_vals = {}
                if exam.exam_type == 'pilihan_ganda':
                    selection = ans.get('answer', '')
                    if selection in ('A', 'B', 'C', 'D'):
                        update_vals['student_answer_selection'] = selection
                elif exam.exam_type == 'essai':
                    text = ans.get('answer', '')
                    update_vals['student_answer_text'] = text
                if update_vals:
                    line.write(update_vals)

            exam.action_done(status='done')
            return {'success': True, 'total_score': exam.total_score}

        except Exception as e:
            _logger.error(f"Exam Submit Error: {e}")
            return {'success': False, 'error': str(e)}

    @http.route(['/api/v1/student/exam/done', '/api/v1/student/exam/done/'], type='json', auth='public', methods=['POST'], csrf=False, cors='*')
    def exam_done(self, **kwargs):
        try:
            access_code = kwargs.get('access_code', '').strip().upper()
            exam_id = kwargs.get('exam_id')
            student, enrollment = self._validate_access_code(access_code)
            if not enrollment:
                return {'success': False, 'error': 'Kode akses tidak valid.'}
            exam = request.env['siswa.kursus.exam'].sudo().search([
                ('id', '=', int(exam_id)),
                ('enrollment_id', '=', enrollment.id),
            ], limit=1)
            if not exam:
                return {'success': False, 'error': 'Ujian tidak ditemukan.'}
            if exam.state != 'done':
                exam.action_done(status='timeout')
            return {'success': True}
        except Exception as e:
            _logger.error(f"Exam Done Error: {e}")
            return {'success': False, 'error': str(e)}

    @http.route(['/api/v1/student/time-config', '/api/v1/student/time-config/'], type='json', auth='public', methods=['POST'], csrf=False, cors='*')
    def time_config(self, **kwargs):
        try:
            configs = request.env['exam.time.config'].sudo().search([])
            result = []
            for cfg in configs:
                result.append({'exam_type': cfg.exam_type, 'duration_minutes': cfg.duration_minutes})
            return {'success': True, 'configs': result}
        except Exception as e:
            _logger.error(f"Time Config Error: {e}")
            return {'success': False, 'error': str(e)}
