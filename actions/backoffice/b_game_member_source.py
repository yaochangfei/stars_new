#! /usr/bin/python

import os
import traceback
from bson import ObjectId
from web import decorators
from web.base import BaseHandler
from enums.permission import PERMISSION_TYPE_SOURCE_MANAGEMENT
from tornado.web import url
from commons.page_utils import Paging
from db.models import GameMemberSource, UploadFiles
from logger import log_utils
from commons.common_utils import download_qr_image, md5, drop_disk_file
from db import CATEGORY_UPLOAD_FILE_IMG_GAME_MEMBER_SOURCE_QR
from settings import STATIC_PATH, SERVER_HOST, SERVER_PROTOCOL

logger = log_utils.get_logging()


class GameMemberSourceListViewHandler(BaseHandler):
    @decorators.render_template('backoffice/game_member_source/list_view.html')
    @decorators.permission_required(PERMISSION_TYPE_SOURCE_MANAGEMENT)
    async def get(self):
        per_page_quantity = int(self.get_argument('per_page_quantity', 10))
        to_page_num = int(self.get_argument('page', 1))
        page_url = '%s?page=$page$per_page_quantity=%s' % (
            self.reverse_url('backoffice_source_list'), per_page_quantity)
        paging = Paging(page_url, GameMemberSource, current_page=to_page_num, items_per_page=per_page_quantity,
                        sort=['-updated_dt'])
        await paging.pager()
        return locals()


class GameMemberSourceAddViewHandler(BaseHandler):
    @decorators.render_template('backoffice/game_member_source/add_view.html')
    @decorators.permission_required(PERMISSION_TYPE_SOURCE_MANAGEMENT)
    async def get(self):
        return locals()

    @decorators.render_json
    @decorators.permission_required(PERMISSION_TYPE_SOURCE_MANAGEMENT)
    async def post(self):
        ret = {'code': 0}
        name = self.get_argument('name')
        code = self.get_argument('code')
        comment = self.get_argument('comment')
        source_status = self.get_argument('source_status')
        qr_status = self.get_argument('qr_status')

        if not name or not code:
            ret['code'] = -1
            return ret

        qr_status = True if qr_status == 'true' else False
        try:
            if await GameMemberSource.count({'$or': [{'code': code}, {'title': name}]}) > 0:
                ret['code'] = -2
                return ret

            source = GameMemberSource(code=code, title=name)
            source.comment = comment
            source.need_qr_code = qr_status
            source.status = int(source_status)

            await source.save()
            ret['code'] = 1
        except Exception:
            logger.error(traceback.format_exc())

        return ret


class GameMemberSourceEditViewHandler(BaseHandler):
    @decorators.render_template('backoffice/game_member_source/edit_view.html')
    @decorators.permission_required(PERMISSION_TYPE_SOURCE_MANAGEMENT)
    async def get(self, source_oid):
        try:
            source = await GameMemberSource.find_one({'_id': ObjectId(source_oid)})
        except Exception:
            logger.error(traceback.format_exc())
        return locals()

    @decorators.render_json
    @decorators.permission_required(PERMISSION_TYPE_SOURCE_MANAGEMENT)
    async def post(self, source_oid):
        ret = {'code': 0}
        name = self.get_argument('name')
        code = self.get_argument('code')
        comment = self.get_argument('comment')
        source_status = self.get_argument('source_status')
        qr_status = self.get_argument('qr_status')

        if not name or not code:
            ret['code'] = -1
            return ret

        qr_status = True if qr_status == 'true' else False
        try:
            if await GameMemberSource.count({'$or': [{'code': code}, {'title': name}]}) != 1:
                ret['code'] = -2
                return ret

            source = await GameMemberSource.find_one({'_id': ObjectId(source_oid)})
            source.code = code
            source.title = name
            source.comment = comment
            source.need_qr_code = qr_status
            source.status = int(source_status)

            await source.save()
            ret['code'] = 1
        except Exception:
            logger.error(traceback.format_exc())

        return ret


class GameMemberSourceDeleteHandler(BaseHandler):
    @decorators.render_json
    @decorators.permission_required(PERMISSION_TYPE_SOURCE_MANAGEMENT)
    async def post(self, source_id):
        ret = {'code': 0}
        try:
            source = await GameMemberSource.get_by_id(source_id)
            if source:
                qr = await UploadFiles.get_by_id(source.qr_code_cid)
                if qr:
                    await qr.delete()
                    await drop_disk_file(STATIC_PATH + '/files/' + qr.title)
                await source.delete()
                ret['code'] = 1
        except Exception:
            logger.error(traceback.format_exc())

        return ret


class GameMemberSourceStatusChangeHandler(BaseHandler):
    @decorators.render_json
    @decorators.permission_required(PERMISSION_TYPE_SOURCE_MANAGEMENT)
    async def post(self):
        ret = {'code': 0}
        source_oid = self.get_argument('source_oid')
        target_status = self.get_argument('target_status')
        try:
            source = await GameMemberSource.get_by_id(source_oid)
            if source:
                source.status = int(target_status)
                await source.save()
                ret['code'] = 1
        except Exception:
            logger.error(traceback.format_exc())

        return ret


class GameMemberSourceQRDownloadHandler(BaseHandler):
    @decorators.permission_required(PERMISSION_TYPE_SOURCE_MANAGEMENT)
    async def get(self, source_oid):
        try:
            source = await GameMemberSource.get_by_id(source_oid)
            name = md5(source.code) + '.png'

            qr_path = STATIC_PATH + '/files/' + name

            if not os.path.exists(qr_path):
                await download_qr_image(name, scene=source.code)

            qr_code = 'qr_' + source.code
            qr_file = await UploadFiles.find_one({'code': qr_code})
            if not qr_file:
                qr_file = UploadFiles(code=qr_code)
                qr_file.title = name
                qr_file.source_title = source.title
                qr_file.category = CATEGORY_UPLOAD_FILE_IMG_GAME_MEMBER_SOURCE_QR
                qr_file.size = os.path.getsize(qr_path)
                await qr_file.save()

            source.qr_code_cid = qr_file.oid
            await source.save()

            self.set_header('Content-Type', 'image/png')
            self.set_header('Content-Disposition', 'attachment; filename=' + name)
            with open(qr_path, 'rb') as qr:
                self.write(qr.read())

            self.finish()

        except Exception:
            logger.error(traceback.format_exc())


URL_MAPPING_LIST = [
    url(r'/backoffice/game_member_source/list/', GameMemberSourceListViewHandler, name='backoffice_source_list'),
    url(r'/backoffice/game_member_source/add/', GameMemberSourceAddViewHandler, name='backoffice_source_add'),
    url(r'/backoffice/game_member_source/edit/([0-9a-zA-Z_]+)/', GameMemberSourceEditViewHandler,
        name='backoffice_source_edit'),
    url(r'/backoffice/game_member_source/delete/([0-9a-zA-Z_]+)/', GameMemberSourceDeleteHandler,
        name='backoffice_source_delete'),
    url(r'/backoffice/game_member_source/status/change/', GameMemberSourceStatusChangeHandler,
        name='backoffice_source_status_change'),
    url(r'/backoffice/game_member_source/qr/download/([0-9a-zA-Z_]+)/', GameMemberSourceQRDownloadHandler,
        name='backoffice_source_qr_download')
]
