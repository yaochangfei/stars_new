# !/usr/bin/python
# -*- coding:utf-8 -*-
import uuid

import os
from tornado.web import RequestHandler

import settings
from commons.common_utils import md5, get_file_extension_name, drop_disk_file, get_increase_code
from db import CATEGORY_UPLOAD_FILE_OTHER
from db.models import UploadFiles
from enums import KEY_INCREASE_UPLOAD_FILE


async def save_upload_file(request_handler, field_name, category=CATEGORY_UPLOAD_FILE_OTHER, file_cid=None):
    """
    保存上传的文件
    :param request_handler: 请求句柄
    :param field_name: 请求表单中文件域名称
    :param category: 文件类别
    :param file_code: 文件编码， 不为空时则更新文件
    :return:
    """
    if not isinstance(request_handler, RequestHandler):
        raise ValueError('Parameter request_handler must be a instance of RequestHandler.')
    if not isinstance(field_name, (bytes, str, list)):
        raise ValueError('Parameter request_field_name must be a type of str or unicode or list.')
    field_list = []
    if isinstance(field_name, (bytes, str)):
        field_list.append(field_name)
    else:
        field_list.extend(field_name)
    files_request = request_handler.request.files
    if files_request:
        file_cid_list = []
        for field_name in field_list:
            if field_name:
                f_metas = files_request.get(field_name)
                if f_metas:
                    title = md5(uuid.uuid1().hex)
                    source_title = None
                    content_type = None
                    f_buffers = []
                    for f_meta in f_metas:
                        f_buffers.append(f_meta['body'])
                        source_title = f_meta['filename']
                        content_type = f_meta['content_type']
                    if f_buffers:
                        e_name = get_file_extension_name(source_title)
                        title = u'%s%s' % (title, e_name)
                        final_name = os.path.join(settings.UPLOAD_FILES_PATH, title)
                        upload_file = None
                        uf = None
                        if file_cid:
                            uf = await UploadFiles.find_one(dict(cid=file_cid))
                            if uf:
                                await drop_disk_file(os.path.join(settings.UPLOAD_FILES_PATH, uf.title))
                        try:
                            upload_file = open(final_name, 'wb')
                            with upload_file:
                                upload_file.write((''.encode('utf-8')).join(f_buffers))
                        finally:
                            if upload_file:
                                upload_file.close()
                        if not uf:
                            uf = UploadFiles()
                            file_code = get_increase_code(KEY_INCREASE_UPLOAD_FILE)
                            uf.code = file_code
                        uf.title = title
                        uf.source_title = source_title
                        uf.size = os.path.getsize(final_name)
                        uf.category = category
                        if request_handler.current_user:
                            uf.updated_id = request_handler.current_user.oid
                            uf.created_id = request_handler.current_user.oid
                        uf.content_type = content_type

                        await uf.save()
                        file_cid_list.append(uf.cid)
        return file_cid_list
    return []


async def get_upload_file_by_cid(cid):
    """
    使用文件cid获取已上传的文件信息
    :param code:
    :return:
    """
    if cid:
        upload_file = await UploadFiles.find_one(dict(cid=cid))
        if upload_file:
            return upload_file
    return None


async def drop_disk_file_by_cid(cid_list=[]):
    """
    根据cid删除文件和上传的记录
    :param cid_list:需要要删除的cid
    :return:
    """
    if cid_list:
        if isinstance(cid_list, str):
            cid_list = cid_list.split()
        file_name_list = await UploadFiles.distinct('title', {'cid': {'$in': cid_list}})
        if file_name_list:
            for file_name in file_name_list:
                if file_name:
                    await drop_disk_file(os.path.join(settings.UPLOAD_FILES_PATH, file_name))
        await UploadFiles.delete_many({'cid': {'$in': cid_list}})
