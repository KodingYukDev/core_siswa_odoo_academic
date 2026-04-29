# -*- coding: utf-8 -*-
import logging
import json
from odoo import _
from odoo.exceptions import UserError

_logger = logging.getLogger(__name__)

try:
    import firebase_admin
    from firebase_admin import credentials, storage
except ImportError:
    _logger.warning("Firebase Admin SDK not installed. Please run: pip install firebase-admin")
    firebase_admin = None
    credentials = None
    storage = None

# Parameter kunci untuk menyimpan konfigurasi Firebase di ir.config_parameter
FIREBASE_CREDENTIALS_PARAM = 'firebase.service.account.key'
FIREBASE_BUCKET_NAME_PARAM = 'firebase.storage.bucket.name'

_firebase_app = None

def get_firebase_app(env):
    """
    Menginisialisasi dan mengembalikan instance Firebase Admin SDK.
    Menangani otentikasi menggunakan service account key.
    """
    global _firebase_app
    if _firebase_app:
        return _firebase_app

    if firebase_admin is None:
         raise UserError(_("""
            Firebase Admin SDK tidak ditemukan.
            Silakan install library berikut di server Odoo Anda:
            pip install firebase-admin
        """))

    config_params = env['ir.config_parameter'].sudo()
    
    service_account_key_str = config_params.get_param(FIREBASE_CREDENTIALS_PARAM)
    if not service_account_key_str:
        raise UserError(_("""
            Kunci akun layanan Firebase belum diatur di Pengaturan Sistem.
            Parameter: %s
        """) % FIREBASE_CREDENTIALS_PARAM)

    try:
        service_account_info = json.loads(service_account_key_str)
    except (json.JSONDecodeError, TypeError):
        raise UserError(_("Format kunci akun layanan Firebase tidak valid."))

    try:
        cred = credentials.Certificate(service_account_info)
        bucket_name = config_params.get_param(FIREBASE_BUCKET_NAME_PARAM)
        
        # Cek jika app sudah ada
        try:
            _firebase_app = firebase_admin.get_app()
            _logger.info("Firebase App sudah ada, menggunakan app yang ada dengan bucket: %s", bucket_name)
        except ValueError:
            # App belum ada, inisialisasi baru
            _firebase_app = firebase_admin.initialize_app(cred, {
                'storageBucket': bucket_name
            })
            _logger.info("Firebase Berhasil Diinisialisasi dengan bucket: %s", bucket_name)
        return _firebase_app
    except Exception as e:
        _logger.error("Terjadi error saat menginisialisasi Firebase Admin SDK: %s", e)
        raise UserError(_("Gagal menginisialisasi Firebase Admin SDK. Detail: %s") % str(e))

def upload_file_to_firebase(env, file_content, file_name, destination_path, content_type=None):
    """
    Mengupload file ke Firebase Storage.
    :param env: Odoo environment object
    :param file_content: Konten file dalam bentuk bytes.
    :param file_name: Nama file asli.
    :param destination_path: Path lengkap di bucket Firebase Storage (misal: 'live-report/siswa1/2023-01-01/file.pdf').
    :param content_type: Tipe MIME dari file (misal: 'image/png', 'video/mp4'). Jika None, akan dicoba ditebak.
    :return: URL publik file yang diupload.
    """
    app = get_firebase_app(env)
    bucket = storage.bucket(app=app)
    
    blob = bucket.blob(destination_path)
    
    try:
        # Set metadata untuk Content-Disposition: inline
        blob.metadata = {'Content-Disposition': 'inline'}
        
        blob.upload_from_string(file_content, content_type=content_type)
        blob.make_public()
        _logger.info("File '%s' berhasil diupload ke Firebase Storage: %s", file_name, destination_path)
        return blob.public_url
    except Exception as e:
        _logger.error("Gagal mengupload file '%s' ke Firebase Storage '%s': %s", file_name, destination_path, e)
        raise UserError(_("Gagal mengupload file ke Firebase Storage. Detail: %s") % str(e))

def delete_file_from_firebase(env, file_path):
    """
    Menghapus file dari Firebase Storage.
    :param env: Odoo environment object
    :param file_path: Path lengkap file di bucket Firebase Storage (misal: 'live-report/siswa1/2023-01-01/file.pdf').
    :return: True jika berhasil dihapus, False jika tidak.
    """
    app = get_firebase_app(env)
    bucket = storage.bucket(app=app)
    
    blob = bucket.blob(file_path)
    
    if blob.exists():
        try:
            blob.delete()
            _logger.info("File '%s' berhasil dihapus dari Firebase Storage.", file_path)
            return True
        except Exception as e:
            _logger.error("Gagal menghapus file '%s' dari Firebase Storage: %s", file_path, e)
            raise UserError(_("Gagal menghapus file dari Firebase Storage. Detail: %s") % str(e))
    else:
        _logger.warning("File '%s' tidak ditemukan di Firebase Storage untuk dihapus.", file_path)
        return False
