# -*- coding: utf-8 -*-
from odoo import models, fields, api
import base64
import time
from ..lib.firebase_service import upload_file_to_firebase

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
    
    file_data = fields.Binary(string='File (Image/Video)', attachment=True)
    file_name = fields.Char(string='Nama File')
    file_url = fields.Char(string='URL File (Cloud Bucket)', help='URL eksternal jika file disimpan di Cloud Storage')

    @api.model
    def create(self, vals):
        res = super(StudentPortfolioProjectMedia, self).create(vals)
        if vals.get('file_data'):
            res._upload_to_bucket()
        return res

    def write(self, vals):
        res = super(StudentPortfolioProjectMedia, self).write(vals)
        if vals.get('file_data'):
            self._upload_to_bucket()
        return res

    def _upload_to_bucket(self):
        for rec in self:
            if not rec.file_data:
                continue
            try:
                file_content = base64.b64decode(rec.file_data)
                f_name = rec.file_name or f"media_{int(time.time())}.png"
                dest_path = f"students/projects/{rec.project_id.siswa_id.id}/project_{rec.project_id.id}/{f_name}"
                
                # Tentukan mimetype
                c_type = 'image/png' if rec.media_type == 'image' else 'video/mp4'
                
                url = upload_file_to_firebase(self.env, file_content, f_name, dest_path, c_type)
                
                super(StudentPortfolioProjectMedia, rec).write({
                    'file_url': url,
                    'file_data': False
                })
            except Exception as e:
                pass
