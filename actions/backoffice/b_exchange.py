# !/usr/bin/python
# -*- coding:utf-8 -*-
import traceback
import uuid

from bson import ObjectId
from datetime import datetime

from pymongo import UpdateOne
from tornado import gen
from tornado.web import url

from commons.common_utils import md5
from commons.page_utils import Paging
from commons.upload_utils import save_upload_file, drop_disk_file_by_cid
from db.models import Present, UploadFiles, DiscountCoupon
from db import CATEGORY_PRESENT_DISCOUNT_COUPON, STATUS_PRESENT_ACTIVE, \
    STATUS_PRESENT_INACTIVE, CATEGORY_PRESENT_WECHAT_LUCKY_MONEY, STATUS_DISCOUNT_COUPON_UNUSED, \
    CATEGORY_UPLOAD_FILE_IMG_PRESENT
from enums import PERMISSION_TYPE_INTEGRAL_EXCHANGE_MANAGEMENT
from logger import log_utils
from web import decorators
from web.base import BaseHandler

exchange_logger = log_utils.get_logging()


class PresentListViewHandler(BaseHandler):
    """
    兑换商城礼品列表
    """

    @decorators.permission_required(PERMISSION_TYPE_INTEGRAL_EXCHANGE_MANAGEMENT)
    @decorators.render_template('backoffice/exchange/list_view.html')
    async def get(self):

        # 上下架礼品数量
        active_amount = await Present.count(filtered={'record_flag': 1, 'status': STATUS_PRESENT_ACTIVE})
        inactive_amount = await Present.count(filtered={'record_flag': 1, 'status': STATUS_PRESENT_INACTIVE})
        all_amount = await Present.count(filtered={'record_flag': 1})

        search_title = self.get_argument('search_title', '')
        search_category = self.get_argument('search_category', '')
        search_status = self.get_argument('search_status', '')

        query_param = {}
        and_query_param = [{'record_flag': 1}]
        if search_title:
            and_query_param.append({'title': {'$regex': search_title}})
        if search_category:
            and_query_param.append({'category': int(search_category)})
        if search_status:
            and_query_param.append({'status': int(search_status)})

        if and_query_param:
            query_param['$and'] = and_query_param

        per_page_quantity = int(self.get_argument('per_page_quantity', 10))
        to_page_num = int(self.get_argument('page', 1))
        page_url = '%s?page=$page&per_page_quantity=%s&search_source=%s&search_datetime=%s' % \
                   (self.reverse_url("backoffice_present_list"), per_page_quantity, search_title, search_category)
        paging = Paging(page_url, Present, current_page=to_page_num, items_per_page=per_page_quantity,
                        sort=['-sort', '-updated_dt'], **query_param)

        await paging.pager()

        return locals()


class PresentAddViewHandler(BaseHandler):
    """
    新增兑换商城礼品
    """

    @decorators.permission_required(PERMISSION_TYPE_INTEGRAL_EXCHANGE_MANAGEMENT)
    @decorators.render_template('backoffice/exchange/add_view.html')
    async def get(self):
        return locals()

    @decorators.permission_required(PERMISSION_TYPE_INTEGRAL_EXCHANGE_MANAGEMENT)
    @decorators.render_json
    async def post(self):
        res = dict(code=0)

        code = self.get_argument('code', '')
        title = self.get_argument('title', '')
        category = self.get_argument('category', '')
        end_date = self.get_argument('end_date', '')
        start_date = self.get_argument('start_date', '')
        ex_integral = self.get_argument('ex_integral', '')
        sort = self.get_argument('sort', 0)
        inventory = self.get_argument('inventory', '')
        limit = self.get_argument('limit', 0)
        status = self.get_argument('status', '')
        placard_metas = self.request.files.get('placard')
        details = self.get_argument('details', '')
        lucky_price = self.get_argument('lucky_price', 0)

        if title and code and category and ex_integral and sort and inventory and status and placard_metas and details:

            if category == str(CATEGORY_PRESENT_DISCOUNT_COUPON) and not (end_date and start_date):
                res['code'] = -2
            elif category == str(CATEGORY_PRESENT_WECHAT_LUCKY_MONEY) and not lucky_price:
                res['code'] = -4
            else:
                exist_present = await Present.find_one(filtered={'code': code})
                if exist_present:
                    res['code'] = -3
                else:
                    try:
                        # 保存文件
                        save_res = await save_upload_file(self, 'placard', category=CATEGORY_UPLOAD_FILE_IMG_PRESENT)
                        if save_res:
                            present = Present()
                            present.code = code
                            present.title = title
                            present.category = int(category)
                            if present.category == CATEGORY_PRESENT_DISCOUNT_COUPON:
                                if end_date:
                                    present.end_date = datetime.strptime(end_date, '%Y-%m-%d %H:%M:%S')
                                if start_date:
                                    present.start_date = datetime.strptime(start_date, '%Y-%m-%d %H:%M:%S')

                            present.placard = save_res[0]

                            placard = await UploadFiles.find_one(filtered={'cid': save_res[0]})

                            present.needless = {'placard_title': 'files/%s' % placard.title}

                            present.ex_integral = int(ex_integral)
                            present.sort = int(sort) if sort else 0
                            present.inventory = int(inventory)
                            present.limit = int(limit) if limit else 0
                            present.status = int(status)
                            present.details = details
                            if present.category == CATEGORY_PRESENT_WECHAT_LUCKY_MONEY and lucky_price:
                                present.lucky_price = lucky_price

                            present.created_id = self.current_user.oid
                            present.updated_id = self.current_user.oid

                            push_id = await present.save()

                            res['code'] = 1
                            res['push_id'] = str(push_id)

                            # 新增同等数量优惠券
                            if present.category == CATEGORY_PRESENT_DISCOUNT_COUPON:
                                discount_coupon_list = []
                                for i in range(present.inventory):
                                    d = DiscountCoupon()
                                    d.created_dt = datetime.now()
                                    d.created_id = self.current_user.oid
                                    d.updated_dt = datetime.now()
                                    d.updated_id = self.current_user.oid
                                    d.record_flag = 1
                                    d.present_cid = present.cid
                                    d.status = STATUS_DISCOUNT_COUPON_UNUSED
                                    d.serial_num = str(uuid.uuid1()).upper()
                                    d.needless = {
                                        'present_title': present.title,
                                    }
                                    discount_coupon_list.append(d)
                                await DiscountCoupon.insert_many(discount_coupon_list)
                    except RuntimeError:
                        exchange_logger.error(traceback.format_exc())
        else:
            res['code'] = -1

        return res


class PresentEditViewHandler(BaseHandler):
    """
    编辑兑换商城礼品
    """

    @decorators.permission_required(PERMISSION_TYPE_INTEGRAL_EXCHANGE_MANAGEMENT)
    @decorators.render_template('backoffice/exchange/edit_view.html')
    async def get(self):

        present_id = self.get_argument('present_id', '')

        present = await Present.get_by_id(present_id)

        return locals()

    @decorators.permission_required(PERMISSION_TYPE_INTEGRAL_EXCHANGE_MANAGEMENT)
    @decorators.render_json
    async def post(self):
        res = dict(code=0)

        present_id = self.get_argument('present_id', '')
        code = self.get_argument('code', '')
        title = self.get_argument('title', '')
        category = self.get_argument('category', '')
        end_date = self.get_argument('end_date', '')
        start_date = self.get_argument('start_date', '')
        ex_integral = self.get_argument('ex_integral', '')
        sort = self.get_argument('sort', 0)
        inventory = self.get_argument('inventory', '')
        limit = self.get_argument('limit', 0)
        status = self.get_argument('status', '')
        placard_metas = self.request.files.get('placard')
        placard_cid = self.get_argument('placard_cid', '')
        details = self.get_argument('details', '')
        lucky_price = self.get_argument('lucky_price', 0)

        if present_id and title and code and category and ex_integral and sort and inventory and status and \
                (placard_metas or placard_cid) and details:

            if category == str(CATEGORY_PRESENT_DISCOUNT_COUPON) and not (end_date and start_date):
                res['code'] = -2
            elif category == str(CATEGORY_PRESENT_WECHAT_LUCKY_MONEY) and not lucky_price:
                res['code'] = -4
            else:
                exist_present = await Present.find_one(filtered={'code': code, '_id': {'$ne': ObjectId(present_id)}})
                if exist_present:
                    res['code'] = -3
                else:
                    try:

                        save_res = await save_upload_file(self, 'placard', category=CATEGORY_UPLOAD_FILE_IMG_PRESENT,
                                                          file_cid=placard_cid)

                        if save_res or placard_cid:

                            present = await Present.get_by_id(present_id)
                            pre_inventory = present.inventory
                            current_inventory = int(inventory)

                            present.code = code
                            present.title = title
                            present.category = int(category)
                            if present.category == CATEGORY_PRESENT_DISCOUNT_COUPON:
                                if end_date:
                                    present.end_date = datetime.strptime(end_date, '%Y-%m-%d %H:%M:%S')
                                if start_date:
                                    present.start_date = datetime.strptime(start_date, '%Y-%m-%d %H:%M:%S')

                            present.placard = save_res[0] if save_res else placard_cid
                            placard = await UploadFiles.find_one(filtered={'cid': present.placard})

                            present.needless = {'placard_title': 'files/%s' % placard.title}

                            present.ex_integral = int(ex_integral)
                            present.sort = int(sort) if sort else 0
                            present.inventory = current_inventory
                            present.limit = int(limit) if limit else 0
                            present.status = int(status)
                            present.details = details
                            if present.category == CATEGORY_PRESENT_WECHAT_LUCKY_MONEY and lucky_price:
                                present.lucky_price = lucky_price

                            present.updated_id = self.current_user.oid

                            # 编辑同等数量优惠券
                            if present.category == CATEGORY_PRESENT_DISCOUNT_COUPON:
                                if pre_inventory < current_inventory:

                                    discount_coupon_list = []
                                    for i in range(current_inventory - pre_inventory):
                                        d = DiscountCoupon()
                                        d.created_dt = datetime.now()
                                        d.created_id = self.current_user.oid
                                        d.updated_dt = datetime.now()
                                        d.updated_id = self.current_user.oid
                                        d.record_flag = 1
                                        d.present_cid = present.cid
                                        d.status = STATUS_DISCOUNT_COUPON_UNUSED
                                        d.serial_num = str(uuid.uuid1()).upper()
                                        d.needless = {
                                            'present_title': present.title,
                                        }
                                        discount_coupon_list.append(d)
                                    await DiscountCoupon.insert_many(discount_coupon_list)

                                if pre_inventory > current_inventory:
                                    filter_d = {
                                        'status': STATUS_DISCOUNT_COUPON_UNUSED,
                                        'record_flag': 1,
                                        'present_cid': present.cid,
                                        'member_cid': None
                                    }
                                    discount_list = await DiscountCoupon.find(filter_d).to_list(
                                        length=pre_inventory - current_inventory)
                                    discount_id_list = [d.get('_id') for d in discount_list]
                                    await DiscountCoupon.delete_by_ids(discount_id_list)
                            present_id = await present.save()

                            res['code'] = 1
                            res['present_id'] = str(present_id)
                    except RuntimeError:
                        exchange_logger.error(traceback.format_exc())
        else:
            res['code'] = -1

        return res


class PresentStatusViewHandler(BaseHandler):
    """
    上架下架兑换商城礼品
    """

    @decorators.permission_required(PERMISSION_TYPE_INTEGRAL_EXCHANGE_MANAGEMENT)
    @decorators.render_json
    async def post(self):
        res = dict(code=0)
        present_ids = self.get_arguments('present_ids[]')
        target_status = self.get_argument('target_status', '')

        if present_ids and target_status:
            try:

                update_requests = []
                for present_id in present_ids:
                    update_requests.append(UpdateOne({'_id': ObjectId(present_id)},
                                                     {'$set': {'status': int(target_status),
                                                               'updated_dt': datetime.now(),
                                                               'updated_id': self.current_user.oid}}))
                await Present.update_many(update_requests)

                res['code'] = 1

            except RuntimeError:
                exchange_logger.error(traceback.format_exc())

        return res


class PresentDeleteViewHandler(BaseHandler):
    """
    删除礼品
    """

    @decorators.permission_required(PERMISSION_TYPE_INTEGRAL_EXCHANGE_MANAGEMENT)
    @decorators.render_json
    async def post(self):
        res = dict(code=0)
        present_ids = self.get_arguments('present_ids[]')

        if present_ids:
            try:
                present_id_list = [ObjectId(present_id) for present_id in present_ids]

                present_cid_list = await Present.distinct('cid', {'_id': {'$in': present_id_list}})
                placard_list = await Present.distinct('placard',
                                                      {'_id': {'$in': present_id_list}, 'placard': {'$ne': None}})
                field_dict = {'present_cid': {'$in': present_cid_list}}
                exist_discount_coupon = await DiscountCoupon.find_one(field_dict)
                if exist_discount_coupon:
                    await DiscountCoupon.delete_many(field_dict)
                await Present.delete_by_ids(present_ids)
                if placard_list:
                    await drop_disk_file_by_cid(placard_list)
                res['code'] = 1
            except RuntimeError:
                exchange_logger.error(traceback.format_exc())

        return res


class PresentInventoryViewHandler(BaseHandler):
    """
    修改礼品库存
    """

    @decorators.permission_required(PERMISSION_TYPE_INTEGRAL_EXCHANGE_MANAGEMENT)
    @decorators.render_json
    async def post(self):
        res = dict(code=0)
        present_id = self.get_argument('present_id', '')
        inventory = self.get_argument('inventory', '')

        if present_id and inventory:
            try:
                present = await Present.get_by_id(present_id)
                pre_inventory = int(present.inventory)
                current_inventory = int(inventory)

                if present.category == CATEGORY_PRESENT_DISCOUNT_COUPON:
                    if pre_inventory < current_inventory:

                        discount_coupon_list = []
                        for i in range(current_inventory - pre_inventory):
                            d = DiscountCoupon()
                            d.created_dt = datetime.now()
                            d.created_id = self.current_user.oid
                            d.updated_dt = datetime.now()
                            d.updated_id = self.current_user.oid
                            d.record_flag = 1
                            d.present_cid = present.cid
                            d.status = STATUS_DISCOUNT_COUPON_UNUSED
                            d.serial_num = str(uuid.uuid1()).upper()
                            d.needless = {
                                'present_title': present.title,
                            }
                            discount_coupon_list.append(d)
                        await DiscountCoupon.insert_many(discount_coupon_list)

                    if pre_inventory > current_inventory:
                        filter_d = {
                            'status': STATUS_DISCOUNT_COUPON_UNUSED,
                            'record_flag': 1,
                            'present_cid': present.cid,
                            'member_cid': None
                        }
                        discount_list = await DiscountCoupon.find(filter_d).to_list(
                            length=pre_inventory - current_inventory)

                        discount_id_list = [d.oid for d in discount_list]

                        await DiscountCoupon.delete_by_ids(discount_id_list)

                present.inventory = current_inventory
                present.updated_dt = datetime.now()
                present.update_id = self.current_user.oid
                await present.save()

                res['code'] = 1

            except RuntimeError:
                exchange_logger.error(traceback.format_exc())

        return res


URL_MAPPING_LIST = [
    url(r'/backoffice/present/list/', PresentListViewHandler, name='backoffice_present_list'),
    url(r'/backoffice/present/add/', PresentAddViewHandler, name='backoffice_present_add'),
    url(r'/backoffice/present/edit/', PresentEditViewHandler, name='backoffice_present_edit'),
    url(r'/backoffice/present/status/', PresentStatusViewHandler, name='backoffice_present_status'),
    url(r'/backoffice/present/delete/', PresentDeleteViewHandler, name='backoffice_present_delete'),
    url(r'/backoffice/present/inventory/', PresentInventoryViewHandler, name='backoffice_present_inventory'),
]
