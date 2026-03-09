# -*- coding: utf-8 -*-
{
    'name': "Database Siswa",
    'summary': """
        Modul kustom untuk mengelola database siswa KodingYuk!,
        termasuk level, jenis kelas, dan data akademik.
    """,
    'author': "PT Koding Yuk Academy", # Anda bisa ganti dengan nama Anda
    'website': "https://kodingyuk.id", # Ganti jika perlu
    'category': 'Education',
    'version': '17.0.1.0.2',
    'depends': [
        'base',
        'mail',     # Untuk chatter (log & histori)
        'contacts', # Karena kita berelasi ke res.partner
    ],
    'data': [
        # Security
        'security/ir.model.access.csv',

        # Data
        'data/exam_time_config_data.xml',

        # Views
        'views/m_level_siswa_views.xml',
        'views/m_class_type_views.xml',
        'views/m_enrollment_views.xml',
        'views/m_penilaian_sertifikat_views.xml',
        'views/m_exam_siswa_views.xml',
        'views/m_exam_time_config_views.xml',
        'views/m_siswa_views.xml',
        'views/automation_cron.xml',

        # Menus
        'views/student_menus.xml',
    ],
    'installable': True,
    'application': True, # Jadikan ini sebagai aplikasi (muncul di menu utama)
    'auto_install': False,
    'license': 'LGPL-3',
}