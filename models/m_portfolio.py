# -*- coding: utf-8 -*-
from odoo import models, fields, api

class StudentPortfolioProject(models.Model):
    _name = 'student.portfolio.project'
    _description = 'Karya/Proyek Portofolio Siswa'
    _order = 'create_date desc'

    siswa_id = fields.Many2one('m.siswa', string='Siswa', required=True, ondelete='cascade')
    name = fields.Char(string='Judul Proyek', required=True)
    description = fields.Text(string='Deskripsi Proyek')
    
    category = fields.Selection([
        ('scratch', 'Scratch'),
        ('pictoblox', 'PictoBlox'),
        ('arduino', 'Arduino'),
        ('python', 'Python'),
        ('roblox', 'Roblox'),
        ('minecraft', 'Minecraft'),
        ('web', 'Web Development'),
        ('other', 'Lainnya')
    ], string='Kategori', required=True, default='scratch')
    
    project_url = fields.Char(string='URL Karya / Download Link', help='Link ke live project, Scratch MIT, atau Google Drive download.')
    
    category_name_mapped = fields.Char(string='Kategori Text', compute='_compute_category_name')
    
    media_ids = fields.One2many(
        'student.portfolio.project.media',
        'project_id',
        string='Media (Foto/Video)',
        help='Maksimal 5 media per karya.'
    )

    @api.depends('category')
    def _compute_category_name(self):
        for rec in self:
            rec.category_name_mapped = dict(rec._fields['category'].selection).get(rec.category)
            

class StudentPortfolioProjectMedia(models.Model):
    _name = 'student.portfolio.project.media'
    _description = 'Media Karya Siswa'
    _order = 'sequence asc, id asc'

    project_id = fields.Many2one('student.portfolio.project', string='Karya', required=True, ondelete='cascade')
    sequence = fields.Integer(string='Urutan', default=10)
    
    media_type = fields.Selection([
        ('image', 'Foto/Gambar'),
        ('video', 'Video / File Lokal')
    ], string='Jenis Media', required=True, default='image')
    
    file_data = fields.Binary(string='File (Image/Video)', attachment=True, required=True)
    file_name = fields.Char(string='Nama File')
