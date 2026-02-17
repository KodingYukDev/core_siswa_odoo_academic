# -*- coding: utf-8 -*-
from odoo import models, fields, api

class StudentProfile(models.Model):
    _name = 'm.siswa'
    _description = 'Profil Siswa'
    # Tambahkan chatter di bawah (log histori)
    _inherit = ['mail.thread', 'mail.activity.mixin']

    # --- Relasi dan Tipe Siswa ---
    tipe_siswa = fields.Selection(
        [
            ('privat', 'Privat'),
            ('online', 'Online'),
            ('reguler', 'Reguler'),
            ('ekskul', 'Ekstrakurikuler'),
        ],
        string='Tipe Siswa',
        default='privat',
        required=True,
        tracking=True
    )
    sekolah_id = fields.Many2one('m.sekolah', string='Asal Sekolah', tracking=True)

    # --- Data Siswa ---
    name = fields.Char(string='Nama Siswa', required=True, tracking=True) # New direct name field

    class_name = fields.Char(string='Kelas', help="Contoh: 2 SD, TK B")
    
    # Relasi ke Master Tingkat
    level_id = fields.Many2one(
        'm.level.siswa', 
        string='Level',
        tracking=True
    )
    
    join_date = fields.Date(
        string='Tanggal Pertama Masuk',
        default=fields.Date.context_today,
        tracking=True
    )
    
    # Relasi ke Master Jenis Kelas
    class_type_id = fields.Many2one(
        'm.class.type', 
        string='Jenis Kelas',
        tracking=True
    )

    jadwal_hari = fields.Selection(
        [
            ('senin', 'Senin'),
            ('selasa', 'Selasa'),
            ('rabu', 'Rabu'),
            ('kamis', 'Kamis'),
            ('jumat', 'Jumat'),
            ('sabtu', 'Sabtu'),
            ('minggu', 'Minggu'),
        ],
        string='Jadwal Hari',
        tracking=True
    )

    jadwal_jam = fields.Float(string='Jadwal Jam', tracking=True)

    # --- Data untuk Penagihan Otomatis ---
    skema_pembayaran = fields.Selection(
        [
            ('monthly', 'Bulanan (per 4 pertemuan)'),
            ('semester', 'Semester (per 12 pertemuan)')
        ],
        string='Skema Pembayaran',
        default='monthly',
        required=True,
        tracking=True
    )

    product_id = fields.Many2one(
        'product.product',
        string='Produk untuk Penagihan',
        help="Pilih produk yang akan digunakan saat membuat invoice untuk siswa ini."
    )

    jumlah_pertemuan_hadir = fields.Integer(
        string='Total Pertemuan Dihadiri',
        default=0,
        readonly=True,
        copy=False # Tidak ikut dicopy saat record diduplikasi
    )

    jumlah_pertemuan_ditagih = fields.Integer(
        string='Total Pertemuan Ditagih',
        default=0,
        readonly=True,
        copy=False # Tidak ikut dicopy saat record diduplikasi
    )
    
    # Relasi ke Orang Tua (res.partner) - now exclusively for parent
    parent_id = fields.Many2one(
        'res.partner', 
        string='Penanggung Jawab / Institusi',
        help="Pilih kontak Penanggung Jawab (Orang Tua atau Institusi/Sekolah) yang ada di modul Kontak."
    )
    
    # Ambil nomor telepon dari Orang Tua secara otomatis
    parent_contact = fields.Char(
        string='Contact Person (HP)',
        related='parent_id.phone', # Bisa diganti ke 'mobile'
        readonly=True
    )
    
    status = fields.Selection(
        [
            ('active', 'Siswa Aktif'),
            ('leave', 'Cuti'),
            ('graduated', 'Lulus'),
            ('inactive', 'Tidak Aktif'),
        ],
        string='Status',
        default='active',
        tracking=True
    )
    
    notes = fields.Text(string='Keterangan')

    enrollment_ids = fields.One2many(
        'siswa.kursus.enrollment',
        'siswa_id',
        string='Riwayat Kursus'
    )

    current_enrollment_id = fields.Many2one(
        'siswa.kursus.enrollment',
        string='Kursus Aktif Saat Ini',
        compute='_compute_current_enrollment',
        store=True
    )

    @api.depends('enrollment_ids.status')
    def _compute_current_enrollment(self):
        for student in self:
            active_enrollments = student.enrollment_ids.filtered(lambda e: e.status == 'aktif')
            if active_enrollments:
                student.current_enrollment_id = active_enrollments[0]
            else:
                student.current_enrollment_id = False

    # --- SQL Constraints ---
    # No partner_id_uniq constraint as partner_id is now for parent and not unique per student profile
    _sql_constraints = [
        ('name_unique', 'unique(name, parent_id)', 'Nama siswa dengan orang tua yang sama harus unik!')
    ]

    # --- Helper ---
    # Removed @api.onchange('partner_id') as partner_id is no longer for the student
