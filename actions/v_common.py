# !/usr/bin/python
# -*- coding:utf-8 -*-
import os
import json
import traceback

from tornado import escape
from tornado.web import url

import settings
from caches.redis_utils import RedisCache
from commons import sms_utils
from commons.common_utils import get_random_str, md5, get_increase_code, datetime2str, base64decode
from commons.upload_utils import save_upload_file
from db import STATUS_USER_ACTIVE, CATEGORY_UPLOAD_FILE_IMG_TXT, CATEGORY_CERTIFICATE_UE
from db.models import AdministrativeDivision, VehicleAttribute, User, UploadFiles
from enums import KEY_CATEGORY_VEHICLE_ATTRIBUTE_CACHE, KEY_INCREASE_UPLOAD_FILE
from logger import log_utils
from web import BaseHandler, decorators, pickle, NonXsrfBaseHandler, datetime
from pymongo import ReadPreference

logger = log_utils.get_logging()


class CommonAdminDivisionViewHandler(BaseHandler):
    @decorators.render_json
    async def post(self):
        r_dict = {'code': 0}
        post_code = self.get_argument('post_code', None)
        try:
            admin_division_list = await AdministrativeDivision.find(dict(parent_code=post_code)).to_list(None)
            r_dict['division_list'] = admin_division_list
            r_dict['code'] = 1
        except RuntimeError:
            logger.error(traceback.format_exc())

        return r_dict


class CommonAttributeViewHandler(BaseHandler):
    @decorators.render_json
    async def post(self):
        r_dict = {'code': 0}
        try:
            category = self.get_argument('category', None)
            if category:
                attribute_list = RedisCache.hmget(KEY_CATEGORY_VEHICLE_ATTRIBUTE_CACHE, (category,))[0]
                if attribute_list:
                    attribute_list = pickle.loads(attribute_list)
                else:
                    category = int(category)
                    parent_code = self.get_argument('parent_code')
                    if parent_code and parent_code.strip() == '':
                        parent_code = None
                    attribute_list = await VehicleAttribute.find(
                        dict(category=category, parent_code=parent_code)).to_list(length=None)
                    for attribute in attribute_list:
                        child_attribute_list = await self.get_child_attribute(attribute.code)
                        if child_attribute_list:
                            attribute.child_attr_list = child_attribute_list
                    # 缓存结果
                    RedisCache.hmset(KEY_CATEGORY_VEHICLE_ATTRIBUTE_CACHE,
                                      {category: pickle.dumps(attribute_list, pickle.HIGHEST_PROTOCOL)})
                r_dict['attribute_list'] = attribute_list
                r_dict['code'] = 1
            else:
                r_dict['code'] = -1
                r_dict['msg'] = u'Please specify a category.'
        except RuntimeError:
            logger.error(traceback.format_exc())

        return r_dict

    async def get_child_attribute(self, attr_code):
        attribute_list = await VehicleAttribute.find(dict(parent_code=attr_code)).to_list(length=None)
        for attribute in attribute_list:
            if attribute:
                attr_code = attribute.code
                if attr_code:
                    child_attr_list = await self.get_child_attribute(attr_code)
                    if child_attr_list:
                        attribute.child_attr_list = child_attr_list
        return attribute_list


class CommonAccessTokenGetViewHandler(NonXsrfBaseHandler):
    """
    获取Access Token
    """

    @decorators.render_json
    async def post(self):
        r_dict = {'code': 0}
        try:
            args = json.loads(self.request.body.decode('utf-8'))
            access_id = self.get_argument('access_key_id')
            if not access_id:
                access_id = args.get('access_key_id')
            access_secret = self.get_argument('access_key_secret')
            if not access_secret:
                access_secret = args.get('access_key_secret')
            if access_id and access_id:
                token = await self.generate_new_token(access_id, access_secret)
                if token:
                    r_dict['code'] = 1
                    r_dict['token'] = token
                else:
                    r_dict['code'] = -2  # access_key_id、access_key_secret 无效
            else:
                r_dict['code'] = -1  # access_key_id、access_key_secret 为空
        except RuntimeError:
            logger.error(traceback.format_exc())

        return r_dict

    async def generate_new_token(self, access_id, access_secret):
        """
        生成新的TOKEN
        :param access_id: ACCESS KEY ID
        :param access_secret: ACCESS KEY SECRET
        :return:
        """
        if access_id and access_secret:
            count = await User.count(dict(access_secret_id=access_id, access_secret_key=access_secret,
                                          status=STATUS_USER_ACTIVE))
            if count > 0:
                token = get_random_str(32)
                key = md5(token)
                RedisCache.set(key, token, 60 * 60 * 2)
                return token
        return None


class CommonXsrfGetViewHandler(NonXsrfBaseHandler):
    @decorators.render_json
    async def post(self):
        r_dict = {'code': 0}
        try:
            xsrf = escape.xhtml_escape(self.xsrf_token)
            if xsrf:
                r_dict['code'] = 1
                r_dict['_xsrf'] = xsrf
        except RuntimeError:
            logger.error(traceback.format_exc())
        return r_dict


class CommonMobileValidateViewHandler(NonXsrfBaseHandler):
    """
    手机验证码、支持人机校验
    """

    @decorators.render_json
    async def post(self):
        res = {'code': 0}
        mobile = self.get_argument('mobile')
        if mobile:
            _, verify_code = sms_utils.send_digit_verify_code(mobile, valid_sec=60)
            if verify_code:
                res['code'] = 1
                res['verify_code'] = verify_code
        return res


class CommonImgUploadViewHandler(BaseHandler):
    def check_xsrf_cookie(self):
        pass

    @decorators.render_json
    async def post(self):

        res = dict(errno=0)

        data = []
        image_cid_list = await save_upload_file(self, 'upload_img', category=CATEGORY_UPLOAD_FILE_IMG_TXT)
        if image_cid_list:
            file_name_list = await UploadFiles.distinct('title', dict(cid={"$in": image_cid_list}))
            for file_name in file_name_list:
                img_url = '%s://%s%s%s%s' % (settings.SERVER_PROTOCOL, settings.SERVER_HOST,
                                             settings.STATIC_URL_PREFIX, 'files/',
                                             file_name)
                data.append(img_url)
        else:
            res['errno'] = None

        res['data'] = data
        return res

class CommonUEditUploadViewHandler(NonXsrfBaseHandler):
    ue_config = {
        # 上传图片配置项
        "imageActionName": "uploadimage",
        "imageFieldName": "upfile",
        "imageMaxSize": 2048000,
        "imageAllowFiles": [".png", ".jpg", ".jpeg", ".gif", ".bmp"],
        "imageCompressEnable": True,
        "imageCompressBorder": 1600,
        "imageInsertAlign": "none",
        "imageUrlPrefix": "/static/files/",
        #"imagePathFormat": "/static/files/{filename}",

        # 涂鸦图片上传配置项
        "scrawlActionName": "uploadscrawl",
        "scrawlFieldName": "upfile",
        "scrawlMaxSize": 2048000,
        "scrawlUrlPrefix": "/static/files/",
        "scrawlInsertAlign": "none",

        # 截图工具上传
        "snapscreenActionName": "uploadimage",
        "snapscreenUrlPrefix": "/static/files/",
        "snapscreenInsertAlign": "none",

        # 抓取远程图片配置
        "catcherLocalDomain": ["127.0.0.1", "localhost", "img.baidu.com"],
        "catcherActionName": "catchimage",
        "catcherFieldName": "source",
        "catcherUrlPrefix": "/static/files/",
        "catcherMaxSize": 2048000,
        "catcherAllowFiles": [".png", ".jpg", ".jpeg", ".gif", ".bmp"],

        # 上传视频配置
        "videoActionName": "uploadvideo",
        "videoFieldName": "upfile",
        "videoUrlPrefix": "",
        "videoMaxSize": 102400000,
        "videoAllowFiles": [
            ".flv", ".swf", ".mkv", ".avi", ".rm", ".rmvb", ".mpeg", ".mpg",
            ".ogg", ".ogv", ".mov", ".wmv", ".mp4", ".webm", ".mp3", ".wav", ".mid"],

        # 上传视频配置
        "fileActionName": "uploadfile",
        "fileFieldName": "upfile",
        "fileUrlPrefix": "",
        "fileMaxSize": 51200000,
        "fileAllowFiles": [
            ".png", ".jpg", ".jpeg", ".gif", ".bmp",
            ".flv", ".swf", ".mkv", ".avi", ".rm", ".rmvb", ".mpeg", ".mpg",
            ".ogg", ".ogv", ".mov", ".wmv", ".mp4", ".webm", ".mp3", ".wav", ".mid",
            ".rar", ".zip", ".tar", ".gz", ".7z", ".bz2", ".cab", ".iso",
            ".doc", ".docx", ".xls", ".xlsx", ".ppt", ".pptx", ".pdf", ".txt", ".md", ".xml"
        ],

        # 列出指定目录下的图片
        "imageManagerActionName": "listimage",
        "imageManagerListPath": "/ueditor/php/upload/image/",
        "imageManagerListSize": 20,
        "imageManagerUrlPrefix": "",
        "imageManagerInsertAlign": "none",
        "imageManagerAllowFiles": [".png", ".jpg", ".jpeg", ".gif", ".bmp"],

        # 列出指定目录下的文件
        "fileManagerActionName": "listfile",
        "fileManagerListPath": "/ueditor/php/upload/file/",
        "fileManagerUrlPrefix": "",
        "fileManagerListSize": 20,
        "fileManagerAllowFiles": [
            ".png", ".jpg", ".jpeg", ".gif", ".bmp",
            ".flv", ".swf", ".mkv", ".avi", ".rm", ".rmvb", ".mpeg", ".mpg",
            ".ogg", ".ogv", ".mov", ".wmv", ".mp4", ".webm", ".mp3", ".wav", ".mid",
            ".rar", ".zip", ".tar", ".gz", ".7z", ".bz2", ".cab", ".iso",
            ".doc", ".docx", ".xls", ".xlsx", ".ppt", ".pptx", ".pdf", ".txt", ".md", ".xml"
        ]

    }

    @decorators.render_json
    async def get(self):
        """
        获取UEditor配置信息
        :return: dict
        """
        return self.ue_config

    @decorators.render_json
    async def post(self):
        try:
            action_name = self.get_argument('action')
            if action_name in self.ue_config.get('imageActionName'):
                # 图片上传
                img_name, o_img_name = await self.upload_image()
                if img_name and o_img_name:
                    return {'url': img_name, 'title': img_name, 'original': o_img_name, 'state': 'SUCCESS'}
            elif action_name in self.ue_config.get('scrawlActionName'):
                # 涂鸦上传
                scrawl_name = await self.upload_scrawl()
                if scrawl_name:
                    return {'url': scrawl_name, 'title': scrawl_name, 'original': scrawl_name, 'state': 'SUCCESS'}

        except RuntimeError:
            logger.error(traceback.format_exc())
        return {"state": "SUCCESS", "error": "Upload failed", "title": "Upload failed"}

    async def upload_image(self):
        """
        上传图片
        :return: 新文件名，原始文件名
        """
        img_name, o_img_name = '', ''
        file_id_list = await save_upload_file(self, 'upfile', category=CATEGORY_CERTIFICATE_UE)
        if file_id_list:
            file_id = file_id_list[0]
            if file_id:
                uf = await UploadFiles.get_by_cid(file_id, read_preference=ReadPreference.PRIMARY)
                if uf:
                    img_name = uf.title
                    o_img_name = uf.source_title
        return img_name, o_img_name

    async def upload_scrawl(self):
        """
        上传涂鸦
        :return: 新文件名，原始文件名
        """
        scrawl_name = ''
        base64_img_data = self.get_argument(self.ue_config.get('scrawlFieldName'))
        if base64_img_data:
            img_data = base64decode(base64_img_data)
            if img_data:
                try:
                    scrawl_name = '%s.png' % md5(datetime2str(datetime.datetime.now(), '%Y%m%d%H%M%S%f'))
                    img_path = os.path.join(settings.STATIC_PATH, 'files', scrawl_name)
                    with open(img_path, 'wb') as img:
                        img.write(img_data)
                except Exception:
                    logger.error(traceback.format_exc())
                finally:
                    if img:
                        img.close()
                if scrawl_name:
                    file_code = get_increase_code(KEY_INCREASE_UPLOAD_FILE)
                    uf = UploadFiles(
                        code=file_code, title=scrawl_name, source_title=scrawl_name, category=CATEGORY_CERTIFICATE_UE,
                        content_type='image/png')
                    uf.size = os.path.getsize(os.path.join(settings.STATIC_PATH, 'files', scrawl_name))
                    await uf.save()
        return scrawl_name


URL_MAPPING_LIST = [
    url(r'/common/division/', CommonAdminDivisionViewHandler, name='common_admin_division'),
    url(r'/common/attribute/', CommonAttributeViewHandler, name='common_attribute'),
    url(r'/common/get_token/', CommonAccessTokenGetViewHandler, name='common_gettoken'),
    url(r'/common/get_xsrf/', CommonXsrfGetViewHandler, name='common_get_xsrf'),
    url(r'/common/mobile_validate/', CommonMobileValidateViewHandler, name='common_mobile_validate'),
    url(r'/common/img_upload/', CommonImgUploadViewHandler, name='common_img_upload'),
    url(r'/common/uedit/upload/', CommonUEditUploadViewHandler, name="common_uedit_upload"),
]
