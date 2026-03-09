# -*- coding: utf-8 -*-
import json
import logging
from datetime import datetime, timedelta
from odoo import http, fields
from odoo.http import request

_logger = logging.getLogger(__name__)


class StudentExamAPIController(http.Controller):

    def _validate_access_code(self, access_code):
        """Validate access code and return enrollment record or False."""
        if not access_code:
            return False
        enrollment = request.env['siswa.kursus.enrollment'].sudo().search([
            ('access_code', '=', access_code),
            ('access_code_active', '=', True),
        ], limit=1)
        return enrollment if enrollment else False

    # ----------------------------------------------------------------
    # LOGIN: Validate access code, return enrollment + student + exams
    # ----------------------------------------------------------------
    @http.route(['/api/v1/student/login', '/api/v1/student/login/'], type='http', auth='none', methods=['POST', 'OPTIONS'], csrf=False, cors='*')
    def student_login(self, **kwargs):
        if request.httprequest.method == 'OPTIONS':
            return http.Response(status=200)
        try:
            # Handle both JSON-RPC and plain JSON
            body = request.httprequest.data.decode('utf-8')
            data = json.loads(body)
            params = data.get('params', data)
            access_code = params.get('access_code', '').strip().upper()

            enrollment = self._validate_access_code(access_code)
            if not enrollment:
                res = {'success': False, 'error': 'Kode akses tidak valid atau sudah tidak aktif.'}
                return request.make_json_response(res)

            student = enrollment.siswa_id
            modul = enrollment.modul_id

            # Get exams for this enrollment
            exams = []
            for exam in enrollment.exam_ids:
                # Auto-start exam if it's still in draft when student logs in
                if exam.state == 'draft':
                    exam.sudo().action_start()
                
                remaining_seconds = 0
                if exam.start_time and exam.time_limit_minutes and exam.state == 'in_progress':
                    elapsed = (fields.Datetime.now() - exam.start_time).total_seconds()
                    remaining_seconds = max(0, (exam.time_limit_minutes * 60) - elapsed)

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
            return request.make_json_response(res)

        except Exception as e:
            _logger.error(f"Student Login Error: {e}")
            return request.make_json_response({'success': False, 'error': str(e)})

    # ----------------------------------------------------------------
    # START EXAM: Start a specific exam for enrollment
    # ----------------------------------------------------------------
    @http.route(['/api/v1/student/exam/start', '/api/v1/student/exam/start/'], type='http', auth='none', methods=['POST', 'OPTIONS'], csrf=False, cors='*')
    def exam_start(self, **kwargs):
        if request.httprequest.method == 'OPTIONS':
            return http.Response(status=200)
        try:
            body = request.httprequest.data.decode('utf-8')
            data = json.loads(body)
            params = data.get('params', data)
            exam_id = params.get('exam_id')

            exam = request.env['siswa.kursus.exam'].sudo().browse(int(exam_id))
            if not exam.exists():
                return request.make_json_response({'success': False, 'error': 'Exam tidak ditemukan.'})

            # Start only this specific exam
            exam.action_start()

            return request.make_json_response({'success': True})

        except Exception as e:
            _logger.error(f"Start Exam Error: {e}")
            return request.make_json_response({'success': False, 'error': str(e)})

    # ----------------------------------------------------------------
    # EXAM DETAIL: Get exam questions/lines
    # ----------------------------------------------------------------
    @http.route(['/api/v1/student/exam/detail', '/api/v1/student/exam/detail/'], type='http', auth='none', methods=['POST', 'OPTIONS'], csrf=False, cors='*')
    def exam_detail(self, **kwargs):
        if request.httprequest.method == 'OPTIONS':
            return http.Response(status=200)
        try:
            body = request.httprequest.data.decode('utf-8')
            data = json.loads(body)
            params = data.get('params', data)
            access_code = params.get('access_code', '').strip().upper()
            exam_id = params.get('exam_id')

            enrollment = self._validate_access_code(access_code)
            if not enrollment:
                return request.make_json_response({'success': False, 'error': 'Kode akses tidak valid.'})

            exam = request.env['siswa.kursus.exam'].sudo().search([
                ('id', '=', int(exam_id)),
                ('enrollment_id', '=', enrollment.id),
            ], limit=1)

            if not exam:
                return request.make_json_response({'success': False, 'error': 'Ujian tidak ditemukan.'})

            remaining_seconds = 0
            if exam.start_time and exam.time_limit_minutes and exam.state == 'in_progress':
                elapsed = (fields.Datetime.now() - exam.start_time).total_seconds()
                remaining_seconds = max(0, (exam.time_limit_minutes * 60) - elapsed)

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
            return request.make_json_response(res)

        except Exception as e:
            _logger.error(f"Exam Detail Error: {e}")
            return request.make_json_response({'success': False, 'error': str(e)})

    # ----------------------------------------------------------------
    # START EXAM: Set state to in_progress, record start_time
    # ----------------------------------------------------------------
    @http.route(['/api/v1/student/exam/start', '/api/v1/student/exam/start/'], type='http', auth='none', methods=['POST', 'OPTIONS'], csrf=False, cors='*')
    def exam_start(self, **kwargs):
        if request.httprequest.method == 'OPTIONS':
            return http.Response(status=200)
        try:
            body = request.httprequest.data.decode('utf-8')
            data = json.loads(body)
            params = data.get('params', data)
            access_code = params.get('access_code', '').strip().upper()
            exam_id = params.get('exam_id')

            enrollment = self._validate_access_code(access_code)
            if not enrollment:
                return request.make_json_response({'success': False, 'error': 'Kode akses tidak valid.'})

            exam = request.env['siswa.kursus.exam'].sudo().search([
                ('id', '=', int(exam_id)),
                ('enrollment_id', '=', enrollment.id),
            ], limit=1)

            if not exam:
                return request.make_json_response({'success': False, 'error': 'Ujian tidak ditemukan.'})

            if exam.state == 'done':
                return request.make_json_response({'success': False, 'error': 'Ujian sudah selesai.'})

            if exam.state == 'draft':
                exam.action_start()

            remaining_seconds = 0
            if exam.start_time and exam.time_limit_minutes:
                elapsed = (fields.Datetime.now() - exam.start_time).total_seconds()
                remaining_seconds = max(0, (exam.time_limit_minutes * 60) - elapsed)

            res = {
                'success': True,
                'start_time': str(exam.start_time),
                'time_limit_minutes': exam.time_limit_minutes,
                'remaining_seconds': int(remaining_seconds),
            }
            return request.make_json_response(res)

        except Exception as e:
            _logger.error(f"Exam Start Error: {e}")
            return request.make_json_response({'success': False, 'error': str(e)})

    # ----------------------------------------------------------------
    # SUBMIT ANSWERS: Save student answers per line
    # ----------------------------------------------------------------
    @http.route(['/api/v1/student/exam/submit', '/api/v1/student/exam/submit/'], type='http', auth='none', methods=['POST', 'OPTIONS'], csrf=False, cors='*')
    def exam_submit(self, **kwargs):
        if request.httprequest.method == 'OPTIONS':
            return http.Response(status=200)
        try:
            body = request.httprequest.data.decode('utf-8')
            data = json.loads(body)
            params = data.get('params', data)
            access_code = params.get('access_code', '').strip().upper()
            exam_id = params.get('exam_id')
            answers = params.get('answers', [])

            enrollment = self._validate_access_code(access_code)
            if not enrollment:
                return request.make_json_response({'success': False, 'error': 'Kode akses tidak valid.'})

            exam = request.env['siswa.kursus.exam'].sudo().search([
                ('id', '=', int(exam_id)),
                ('enrollment_id', '=', enrollment.id),
            ], limit=1)

            if not exam:
                return request.make_json_response({'success': False, 'error': 'Ujian tidak ditemukan.'})

            if exam.state == 'done':
                return request.make_json_response({'success': False, 'error': 'Ujian sudah selesai, tidak bisa submit lagi.'})

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

            # Mark exam as done after submission
            exam.action_done()

            res = {
                'success': True,
                'total_score': exam.total_score,
            }
            return request.make_json_response(res)

        except Exception as e:
            _logger.error(f"Exam Submit Error: {e}")
            return request.make_json_response({'success': False, 'error': str(e)})

    # ----------------------------------------------------------------
    # MARK DONE: Mark exam as done (e.g. timer expired)
    # ----------------------------------------------------------------
    @http.route(['/api/v1/student/exam/done', '/api/v1/student/exam/done/'], type='http', auth='none', methods=['POST', 'OPTIONS'], csrf=False, cors='*')
    def exam_done(self, **kwargs):
        if request.httprequest.method == 'OPTIONS':
            return http.Response(status=200)
        try:
            body = request.httprequest.data.decode('utf-8')
            data = json.loads(body)
            params = data.get('params', data)
            access_code = params.get('access_code', '').strip().upper()
            exam_id = params.get('exam_id')

            enrollment = self._validate_access_code(access_code)
            if not enrollment:
                return request.make_json_response({'success': False, 'error': 'Kode akses tidak valid.'})

            exam = request.env['siswa.kursus.exam'].sudo().search([
                ('id', '=', int(exam_id)),
                ('enrollment_id', '=', enrollment.id),
            ], limit=1)

            if not exam:
                return request.make_json_response({'success': False, 'error': 'Ujian tidak ditemukan.'})

            if exam.state != 'done':
                exam.action_done()

            return request.make_json_response({'success': True})

        except Exception as e:
            _logger.error(f"Exam Done Error: {e}")
            return request.make_json_response({'success': False, 'error': str(e)})

    # ----------------------------------------------------------------
    # TIME CONFIG: Get master time configuration
    # ----------------------------------------------------------------
    @http.route(['/api/v1/student/time-config', '/api/v1/student/time-config/'], type='http', auth='none', methods=['POST', 'OPTIONS'], csrf=False, cors='*')
    def time_config(self, **kwargs):
        if request.httprequest.method == 'OPTIONS':
            return http.Response(status=200)
        try:
            configs = request.env['exam.time.config'].sudo().search([])
            result = []
            for cfg in configs:
                result.append({
                    'exam_type': cfg.exam_type,
                    'duration_minutes': cfg.duration_minutes,
                })
            return request.make_json_response({'success': True, 'configs': result})

        except Exception as e:
            _logger.error(f"Time Config Error: {e}")
            return request.make_json_response({'success': False, 'error': str(e)})
