# -*- coding: utf-8 -*-
from datetime import timedelta

from odoo import api, fields, models, _
from odoo.exceptions import ValidationError


class StudentLifecycleReason(models.Model):
    _name = 'student.lifecycle.reason'
    _description = 'Alasan Siklus Hidup Siswa'
    _order = 'reason_type, sequence, name'

    name = fields.Char(required=True)
    reason_type = fields.Selection([
        ('stop', 'Tidak Lanjut / Berhenti'),
        ('pause', 'Cuti'),
        ('renew', 'Perpanjangan'),
        ('reschedule', 'Reschedule'),
        ('intervention', 'Intervensi'),
        ('transition', 'Perpindahan Program'),
    ], required=True, index=True)
    sequence = fields.Integer(default=10)
    active = fields.Boolean(default=True)


class StudentCourseEnrollmentLifecycle(models.Model):
    _inherit = 'siswa.kursus.enrollment'

    expected_end_date = fields.Date(string='Perkiraan Selesai', index=True, tracking=True)
    quit_date = fields.Date(string='Tanggal Berhenti', index=True, tracking=True)
    quit_reason_id = fields.Many2one('student.lifecycle.reason', string='Alasan Tidak Lanjut',
        domain=[('reason_type', '=', 'stop')], tracking=True)
    quit_reason_note = fields.Text(string='Catatan Tidak Lanjut', tracking=True)
    renewal_status = fields.Selection([
        ('not_due', 'Belum Waktunya'), ('pending', 'Perlu Ditanyakan'),
        ('offered', 'Sudah Ditawarkan'), ('renewed', 'Lanjut'),
        ('declined', 'Tidak Lanjut'),
    ], string='Status Perpanjangan', default='not_due', required=True, index=True, tracking=True)
    renewal_decision_date = fields.Date(string='Tanggal Keputusan Perpanjangan', tracking=True)
    renewal_reason_id = fields.Many2one('student.lifecycle.reason', string='Alasan Perpanjangan',
        domain=[('reason_type', '=', 'renew')], tracking=True)
    next_program_id = fields.Many2one('modul.pembelajaran', string='Rekomendasi Program Berikutnya', tracking=True)
    next_program_note = fields.Text(string='Alasan Rekomendasi', tracking=True)
    session_cadence_days = fields.Integer(string='Target Jarak Sesi (Hari)', default=7)
    intervention_ids = fields.One2many('student.intervention', 'enrollment_id', string='Intervensi')
    reschedule_event_ids = fields.One2many('student.reschedule.event', 'enrollment_id', string='Riwayat Reschedule')
    transition_ids = fields.One2many('student.program.transition', 'enrollment_id', string='Perpindahan Program')
    attention_level = fields.Selection([
        ('green', 'Normal'), ('yellow', 'Perlu Perhatian'), ('red', 'Prioritas'),
    ], compute='_compute_attention', store=True, index=True)
    attention_score = fields.Integer(compute='_compute_attention', store=True)
    attention_reason = fields.Char(compute='_compute_attention', store=True)
    days_since_last_session = fields.Integer(compute='_compute_attention', store=True)

    @api.depends('status', 'tanggal_mulai', 'expected_end_date', 'renewal_status',
                 'jumlah_pertemuan_wajib', 'jumlah_pertemuan_diikuti')
    def _compute_attention(self):
        today = fields.Date.context_today(self)
        attendance_model = (
            self.env['absensi.siswa.absensi.line']
            if 'absensi.siswa.absensi.line' in self.env else None
        )
        for enrollment in self:
            score = 0
            reasons = []
            last_date = False
            if attendance_model is not None:
                line = attendance_model.search([
                    ('absensi_id.enrollment_id', '=', enrollment.id),
                    ('tanggal_waktu', '<=', fields.Datetime.now()),
                ], order='tanggal_waktu desc', limit=1)
                last_date = line.tanggal_waktu.date() if line.tanggal_waktu else False
            days = (today - last_date).days if last_date else 0
            enrollment.days_since_last_session = days
            if enrollment.status == 'aktif' and last_date and days >= 21:
                score += 60
                reasons.append(_('Tidak ada sesi %s hari') % days)
            elif enrollment.status == 'aktif' and last_date and days >= 14:
                score += 35
                reasons.append(_('Tidak ada sesi %s hari') % days)
            required = enrollment.jumlah_pertemuan_wajib or 0
            followed = enrollment.jumlah_pertemuan_diikuti or 0
            if enrollment.status == 'aktif' and required and followed < required:
                elapsed = max((today - enrollment.tanggal_mulai).days, 0) if enrollment.tanggal_mulai else 0
                expected = min(required, elapsed // max(enrollment.session_cadence_days, 1) + 1)
                gap = expected - followed
                if gap >= 3:
                    score += 35
                    reasons.append(_('Pace tertinggal %s sesi') % gap)
                elif gap >= 1:
                    score += 15
                    reasons.append(_('Pace tertinggal %s sesi') % gap)
            if enrollment.expected_end_date and enrollment.status == 'aktif':
                remaining = (enrollment.expected_end_date - today).days
                if remaining <= 30 and enrollment.renewal_status in ('not_due', 'pending'):
                    score += 20
                    reasons.append(_('Perpanjangan perlu ditindaklanjuti'))
            score = min(score, 100)
            enrollment.attention_score = score
            enrollment.attention_level = 'red' if score >= 60 else ('yellow' if score >= 25 else 'green')
            enrollment.attention_reason = '; '.join(reasons) or _('Tidak ada indikator perhatian')

    @api.constrains('status', 'quit_date', 'quit_reason_id')
    def _check_stop_fields(self):
        for record in self:
            if record.status == 'berhenti' and (not record.quit_date or not record.quit_reason_id):
                raise ValidationError(_('Tanggal berhenti dan alasan tidak lanjut wajib diisi.'))
            if record.quit_date and record.tanggal_mulai and record.quit_date < record.tanggal_mulai:
                raise ValidationError(_('Tanggal berhenti tidak boleh sebelum tanggal mulai.'))

    @api.constrains('renewal_status', 'renewal_decision_date', 'renewal_reason_id')
    def _check_renewal_decision(self):
        for record in self:
            if record.renewal_status in ('renewed', 'declined') and not record.renewal_decision_date:
                raise ValidationError(_('Tanggal keputusan perpanjangan wajib diisi.'))
            if record.renewal_status == 'declined' and not record.renewal_reason_id:
                raise ValidationError(_('Alasan tidak lanjut wajib diisi untuk keputusan tidak lanjut.'))

    @api.model
    def _cron_refresh_attention(self):
        self.search([('status', '=', 'aktif')])._compute_attention()


class StudentRescheduleEvent(models.Model):
    _name = 'student.reschedule.event'
    _description = 'Riwayat Reschedule Siswa'
    _order = 'requested_at desc, id desc'

    enrollment_id = fields.Many2one('siswa.kursus.enrollment', required=True, ondelete='cascade', index=True)
    student_id = fields.Many2one(related='enrollment_id.siswa_id', store=True, index=True)
    requested_at = fields.Datetime(default=fields.Datetime.now, required=True, index=True)
    old_datetime = fields.Datetime(required=True)
    new_datetime = fields.Datetime(required=True)
    initiator = fields.Selection([('parent', 'Orang Tua'), ('trainer', 'Trainer'), ('admin', 'Admin')], required=True)
    reason_id = fields.Many2one('student.lifecycle.reason', domain=[('reason_type', '=', 'reschedule')], required=True)
    notice_hours = fields.Float(compute='_compute_notice_hours', store=True)
    state = fields.Selection([('requested', 'Diajukan'), ('approved', 'Disetujui'), ('rejected', 'Ditolak'), ('done', 'Selesai')], default='requested', required=True, index=True)
    note = fields.Text()

    @api.depends('requested_at', 'old_datetime')
    def _compute_notice_hours(self):
        for record in self:
            record.notice_hours = max((record.old_datetime - record.requested_at).total_seconds() / 3600, 0) if record.old_datetime and record.requested_at else 0

    @api.constrains('old_datetime', 'new_datetime')
    def _check_dates(self):
        for record in self:
            if record.old_datetime == record.new_datetime:
                raise ValidationError(_('Jadwal lama dan jadwal baru harus berbeda.'))


class StudentIntervention(models.Model):
    _name = 'student.intervention'
    _description = 'Intervensi Siswa'
    _inherit = ['mail.thread', 'mail.activity.mixin']
    _order = 'alert_date desc, id desc'

    enrollment_id = fields.Many2one('siswa.kursus.enrollment', required=True, ondelete='cascade', index=True, tracking=True)
    student_id = fields.Many2one(related='enrollment_id.siswa_id', store=True, index=True)
    alert_date = fields.Date(default=fields.Date.context_today, required=True, index=True)
    attention_level = fields.Selection(related='enrollment_id.attention_level', store=True)
    trigger_reason = fields.Char(required=True, tracking=True)
    owner_id = fields.Many2one('res.users', default=lambda self: self.env.user, required=True, index=True, tracking=True)
    action_type = fields.Selection([('call_parent', 'Hubungi Orang Tua'), ('schedule', 'Perbaiki Jadwal'), ('academic_review', 'Review Akademik'), ('program_change', 'Ubah Program'), ('payment_review', 'Review Pembayaran'), ('other', 'Lainnya')], required=True, tracking=True)
    due_date = fields.Date(required=True, default=lambda self: fields.Date.context_today(self) + timedelta(days=2), index=True)
    state = fields.Selection([('open', 'Terbuka'), ('done', 'Selesai'), ('cancelled', 'Dibatalkan')], default='open', required=True, index=True, tracking=True)
    outcome = fields.Selection([('returned', 'Kembali Belajar'), ('rescheduled', 'Jadwal Diperbaiki'), ('renewed', 'Lanjut Program'), ('paused', 'Cuti'), ('stopped', 'Berhenti'), ('unreachable', 'Tidak Dapat Dihubungi'), ('other', 'Lainnya')], tracking=True)
    outcome_date = fields.Date(tracking=True)
    note = fields.Text(tracking=True)

    @api.constrains('state', 'outcome', 'outcome_date')
    def _check_done(self):
        for record in self:
            if record.state == 'done' and (not record.outcome or not record.outcome_date):
                raise ValidationError(_('Outcome dan tanggal outcome wajib untuk intervensi selesai.'))


class StudentProgramTransition(models.Model):
    _name = 'student.program.transition'
    _description = 'Perpindahan Program Siswa'
    _order = 'transition_date desc, id desc'

    enrollment_id = fields.Many2one('siswa.kursus.enrollment', required=True, ondelete='cascade', index=True)
    student_id = fields.Many2one(related='enrollment_id.siswa_id', store=True, index=True)
    transition_date = fields.Date(default=fields.Date.context_today, required=True, index=True)
    from_program_id = fields.Many2one('modul.pembelajaran', required=True)
    to_program_id = fields.Many2one('modul.pembelajaran', required=True)
    reason_id = fields.Many2one('student.lifecycle.reason', domain=[('reason_type', '=', 'transition')], required=True)
    recommended_by = fields.Many2one('res.users', default=lambda self: self.env.user)
    accepted = fields.Boolean(default=True)
    note = fields.Text()

    @api.constrains('from_program_id', 'to_program_id')
    def _check_programs(self):
        for record in self:
            if record.from_program_id == record.to_program_id:
                raise ValidationError(_('Program asal dan tujuan harus berbeda.'))
