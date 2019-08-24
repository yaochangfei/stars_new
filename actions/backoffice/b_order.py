# !/usr/bin/python
# -*- coding:utf-8 -*-
import traceback

from bson import ObjectId
from datetime import datetime

from pymongo import UpdateOne
from tornado import gen
from tornado.web import url

from commons.page_utils import Paging
from db.models import ExchangeOrder
from enums import PERMISSION_TYPE_INTEGRAL_ORDER_MANAGEMENT
from db import STATUS_EXCHANGE_ORDER_CLOSED, STATUS_EXCHANGE_ORDER_SHIPPED
from logger import log_utils
from web import decorators
from web.base import BaseHandler

order_logger = log_utils.get_logging()


class OrderListViewHandler(BaseHandler):
    """
    订单列表
    """
    @decorators.permission_required(PERMISSION_TYPE_INTEGRAL_ORDER_MANAGEMENT)
    @decorators.render_template('backoffice/order/list_view.html')
    async def get(self):
        search_code = self.get_argument('search_code', '')
        search_member = self.get_argument('search_member', '')
        search_datetime = self.get_argument('search_datetime', '')

        query_param = {}
        and_query_param = [{'record_flag': 1}]
        if search_code:
            and_query_param.append({'code': {'$regex': search_code}})
        if search_datetime:
            start = datetime.strptime(search_datetime, '%Y-%m-%d').replace(hour=0, minute=0, second=0)
            end = datetime.strptime(search_datetime, '%Y-%m-%d').replace(hour=23, minute=59, second=59)
            query_param['order_datetime'] = {
                '$lt': end,
                '$gt': start,
            }
        if search_member:
            and_query_param.append({'$or': [
                {'receiver_name': {'$regex': search_member}},
                {'receiver_mobile': {'$regex': search_member}}
            ]})

        if and_query_param:
            query_param['$and'] = and_query_param

        per_page_quantity = int(self.get_argument('per_page_quantity', 10))
        to_page_num = int(self.get_argument('page', 1))
        page_url = '%s?page=$page&per_page_quantity=%s&search_source=%s&search_datetime=%s&search_datetime=%s' % \
                   (self.reverse_url("backoffice_order_list"), per_page_quantity, search_code, search_member,
                    search_datetime)
        paging = Paging(page_url, ExchangeOrder, current_page=to_page_num, items_per_page=per_page_quantity,
                        sort=['-updated_dt'], **query_param)

        await paging.pager()

        return locals()


class OrderDeleteViewHandler(BaseHandler):
    """
    删除订单
    """
    @decorators.permission_required(PERMISSION_TYPE_INTEGRAL_ORDER_MANAGEMENT)
    @decorators.render_json
    async def post(self):
        res = dict(code=0)
        order_ids = self.get_arguments('order_ids[]')

        if order_ids:
            try:

                await ExchangeOrder.delete_by_ids(order_ids)
                res['code'] = 1

            except RuntimeError:
                order_logger.error(traceback.format_exc())

        return res


class OrderCloseViewHandler(BaseHandler):
    """
    关闭订单
    """
    @decorators.permission_required(PERMISSION_TYPE_INTEGRAL_ORDER_MANAGEMENT)
    @decorators.render_json
    async def post(self):
        res = dict(code=0)
        order_ids = self.get_arguments('order_ids[]')
        target_status = self.get_argument('target_status', STATUS_EXCHANGE_ORDER_CLOSED)

        if order_ids and target_status:
            try:

                update_requests = []
                for order_id in order_ids:
                    update_requests.append(UpdateOne({'_id': ObjectId(order_id)},
                                                     {'$set': {'status': int(target_status),
                                                               'updated_dt': datetime.now(),
                                                               'updated_id': self.current_user.oid}}))
                await ExchangeOrder.update_many(update_requests)

                res['code'] = 1

            except RuntimeError:
                order_logger.error(traceback.format_exc())

        return res


class OrderDeliveryViewHandler(BaseHandler):
    """
    订单发货
    """
    @decorators.permission_required(PERMISSION_TYPE_INTEGRAL_ORDER_MANAGEMENT)
    @decorators.render_template('backoffice/order/delivery_view.html')
    async def get(self):
        order_id = self.get_argument('order_id', '')
        order = await ExchangeOrder.get_by_id(order_id)

        return {'order': order}

    @decorators.permission_required(PERMISSION_TYPE_INTEGRAL_ORDER_MANAGEMENT)
    @decorators.render_json
    async def post(self):
        res = dict(code=0)

        order_id = self.get_argument('order_id', '')
        carrier_code = self.get_argument('carrier_code', '')
        shipped_code = self.get_argument('shipped_code', '')

        if order_id and carrier_code and shipped_code:
            try:

                exchange_order = await ExchangeOrder.get_by_id(order_id)
                exchange_order.carrier_code = int(carrier_code)
                exchange_order.shipped_code = shipped_code
                exchange_order.status = STATUS_EXCHANGE_ORDER_SHIPPED
                exchange_order.updated_dt = datetime.now()
                exchange_order.updated_id = self.current_user.oid

                await exchange_order.save()

                res['code'] = 1

            except RuntimeError:
                order_logger.error(traceback.format_exc())
        else:
            res['code'] = -1

        return res


URL_MAPPING_LIST = [
    url(r'/backoffice/order/list/', OrderListViewHandler, name='backoffice_order_list'),
    url(r'/backoffice/order/delete/', OrderDeleteViewHandler, name='backoffice_order_delete'),
    url(r'/backoffice/order/close/', OrderCloseViewHandler, name='backoffice_order_close'),
    url(r'/backoffice/order/delivery/', OrderDeliveryViewHandler, name='backoffice_order_delivery'),
]
