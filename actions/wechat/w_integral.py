# !/usr/bin/python
# -*- coding:utf-8 -*-
import traceback

from datetime import datetime

from tornado.web import url

from commons.common_utils import get_increase_code
from db import STATUS_PRESENT_ACTIVE, STATUS_EXCHANGE_ORDER_CLOSED, CATEGORY_PRESENT_DISCOUNT_COUPON, \
    CATEGORY_PRESENT_REAL_GIFT, STATUS_EXCHANGE_ORDER_UNSHIPPED
from db.models import Member, Present, DiscountCoupon, ExchangeOrder, AdministrativeDivision
from enums import KEY_INCREASE_EXCHANGE_ORDER_CODE
from logger import log_utils
from motorengine import ASC, DESC
from motorengine.stages import MatchStage, LookupStage, SortStage, SkipStage
from motorengine.stages.limit_stage import LimitStage
from web import decorators, WechatBaseHandler

logger = log_utils.get_logging()


class WechatIntegralCenterViewHandler(WechatBaseHandler):
    """
    礼品中心
    """

    @decorators.render_template('wechat/integral/integral_center.html')
    async def get(self):
        member = await Member.get_by_id(self.current_user.oid)
        return locals()

    @decorators.render_json
    async def post(self):
        res = {'code': 1}

        pageNum = int(self.get_argument('pageNum', 1))
        size = int(self.get_argument('size', 9))
        filter_dict = {
            'status': STATUS_PRESENT_ACTIVE,
            'record_flag': 1,
        }
        skip = (pageNum - 1) * size if (pageNum - 1) * size > 0 else 0
        present_list = await Present.find(dict(status=STATUS_PRESENT_ACTIVE, record_flag=1), skip=skip, limit=int(size),
                                          sort=[('sort', ASC)]).to_list(int(size))
        if present_list:
            html = self.render_string('wechat/integral/integral_center_data_list.html', present_list=present_list)
        else:
            html = ''

        res['html'] = html
        res['current_length'] = len(present_list)
        res['totalSize'] = await Present.count(filter_dict)

        return res


class WechatIntegralPresentDetailViewHandler(WechatBaseHandler):
    """
    兑换礼品详情
    """

    @decorators.render_template('wechat/integral/present_detail.html')
    async def get(self):
        present_id = self.get_argument('present_id')
        present_cid = self.get_argument('present_cid')

        present = await Present.get_by_id(present_id)
        if not present:
            present = await Present.get_by_cid(present_cid)
        member = await Member.get_by_id(self.current_user.oid)

        return locals()


class WechatIntegralPresentCouponsViewHandler(WechatBaseHandler):
    """
    优惠券兑换记录
    """

    @decorators.render_template('wechat/integral/coupon_list.html')
    async def get(self):
        return locals()

    @decorators.render_json
    async def post(self):
        res = {'code': 1}

        pageNum = int(self.get_argument('pageNum', 1))
        size = int(self.get_argument('size', 10))
        skip = (pageNum - 1) * size if (pageNum - 1) * size > 0 else 0
        filter_dict = {
            'member_cid': self.current_user.cid,
            'record_flag': 1
        }

        match = MatchStage(filter_dict)
        lookup = LookupStage(Present, local_field='present_cid', foreign_field='cid', as_list_name='present')
        skip = SkipStage(skip)
        sort = SortStage([('updated_dt', DESC)])
        limit = LimitStage(int(size))

        coupon_list = await DiscountCoupon.aggregate([match, lookup, skip, sort, limit]).to_list(None)
        if coupon_list:
            html = self.render_string('wechat/integral/coupon_data_list.html', coupon_list=coupon_list)
        else:
            html = ''

        res['html'] = html
        res['current_length'] = len(coupon_list)
        res['totalSize'] = await DiscountCoupon.count(filter_dict)

        return res


class WechatIntegralPresentOrdersViewHandler(WechatBaseHandler):
    """
    实物礼品兑换记录
    """

    @decorators.render_template('wechat/integral/order_list.html')
    async def get(self):
        return locals()

    @decorators.render_json
    async def post(self):
        res = {'code': 1}

        pageNum = int(self.get_argument('pageNum', 1))
        size = int(self.get_argument('size', 10))
        filter_dict = {
            'member_cid': self.current_user.cid,
            'record_flag': 1
        }
        skip = (pageNum - 1) * size if (pageNum - 1) * size > 0 else 0

        match = MatchStage(filter_dict)
        lookup = LookupStage(Present, local_field='present_cid', foreign_field='cid', as_list_name='present')
        skip = SkipStage(skip)
        sort = SortStage([('updated_dt', DESC)])
        limit = LimitStage(int(size))
        order_list = await ExchangeOrder.aggregate([match, lookup, skip, sort, limit]).to_list(int(size))
        if order_list:
            html = self.render_string('wechat/integral/order_data_list.html', order_list=order_list)
        else:
            html = ''

        res['html'] = html
        res['current_length'] = len(order_list)
        res['totalSize'] = await ExchangeOrder.count(filter_dict)

        return res


class WechatIntegralPresentOrderDeleteViewHandler(WechatBaseHandler):
    """
    删除订单
    """

    @decorators.render_json
    async def post(self):
        res = {'code': 0}

        order_id = self.get_argument('order_id')
        try:
            exchange_order = await ExchangeOrder.get_by_id(order_id)
            # 订单已关闭
            if exchange_order.status == STATUS_EXCHANGE_ORDER_CLOSED:
                exchange_order.update_dt = datetime.now()
                exchange_order.update_id = self.current_user.oid
                exchange_order.record_flag = 0
                exchange_order.save()

                res['code'] = 1
        except Exception:
            logger.error(traceback.format_exc())

        return res


class WechatIntegralCouponExchangeViewHandler(WechatBaseHandler):
    """
    兑换优惠券
    """

    @decorators.render_json
    async def post(self):
        res = {'code': 1}

        present_id = self.get_argument('present_id')
        member_id = self.current_user.oid
        if present_id and member_id:
            try:
                present = await Present.get_by_id(present_id)
                member = await Member.get_by_id(member_id)
                if present and member and present.category == CATEGORY_PRESENT_DISCOUNT_COUPON:
                    # 校验积分
                    if present.ex_integral > member.integral:
                        res['code'] = -1
                    # 校验库存
                    elif present.inventory < 1:
                        res['code'] = -2
                    else:
                        # 优惠券校验每人可领限制
                        limit = present.limit
                        # 查询已领优惠券
                        exchange_count = await DiscountCoupon.count(
                            dict(present_cid=present.cid, member_cid=member.cid))
                        if (limit and exchange_count < limit) or not limit:
                            # 领取优惠券
                            # discount_coupon 添加member_code
                            discount_coupon = await DiscountCoupon.find_one(
                                dict(member_cid=None, present_cid=present.cid))
                            discount_coupon.updated_dt = datetime.now()
                            discount_coupon.updated_id = self.current_user.oid
                            discount_coupon.member_cid = member.cid
                            await discount_coupon.save()
                            # present 库存减少
                            present.updated_dt = datetime.now()
                            present.updated_id = self.current_user.oid
                            present.inventory = present.inventory - 1
                            await present.save()
                            # 用户积分减少
                            member.updated_dt = datetime.now()
                            member.updated_id = self.current_user.oid
                            member.integral = member.integral - present.ex_integral
                            await member.save()
                        else:
                            res['code'] = -3
                else:
                    res['code'] = 0
            except Exception:
                logger.error(traceback.format_exc())
                res['code'] = 0
        else:
            res['code'] = 0

        return res


class WechatIntegralGiftExchangeViewHandler(WechatBaseHandler):
    """
    填写地址及确认
    """

    @decorators.render_json
    async def post(self):
        res = {'code': 1}

        present_id = self.get_argument('present_id')
        receiver_name = self.get_argument('receiver_name')
        receive_address = self.get_argument('receiver_address')
        receiver_mobile = self.get_argument('receiver_mobile')
        receiver_area_codes = self.get_argument('receiver_area_codes')
        member_id = self.current_user.oid

        if present_id and member_id:
            try:
                present = await Present.get_by_id(present_id)
                member = await Member.get_by_id(member_id)
                if present and member and present.category == CATEGORY_PRESENT_REAL_GIFT:
                    # 校验积分
                    if present.ex_integral > member.integral:
                        res['code'] = -1
                    # 校验库存
                    elif present.inventory < 1:
                        res['code'] = -2
                    else:
                        # 新建订单
                        order = ExchangeOrder(present_cid=present.code, member_cid=member.cid,
                                              code=get_increase_code(KEY_INCREASE_EXCHANGE_ORDER_CODE),
                                              order_datetime=datetime.now(), receiver_name=receiver_name,
                                              receiver_mobile=receiver_mobile)
                        if receiver_area_codes:
                            area_codes_list = receiver_area_codes.split(',')
                            # 省
                            try:
                                province_code = area_codes_list[0]
                                province = await AdministrativeDivision.find_one(dict(code=province_code))
                                order.needless['province'] = province.title
                                order.province_code = province.code
                            except IndexError:
                                pass

                            try:
                                city_code = area_codes_list[1]
                                city = await AdministrativeDivision.find_one(dict(code=city_code))
                                order.needless['city'] = city.title
                                order.city_code = city.code
                            except IndexError:
                                pass

                            try:
                                district_code = area_codes_list[2]
                                district = await AdministrativeDivision.find_one(dict(code=district_code))
                                order.needless['district'] = district.title
                                order.district_code = district.code
                            except IndexError:
                                pass

                        order.receive_address = receive_address
                        order.ex_integral = present.ex_integral
                        order.status = STATUS_EXCHANGE_ORDER_UNSHIPPED
                        order.updated_id = self.current_user.oid
                        order.created_id = self.current_user.oid

                        await order.save()

                        # present 库存减少
                        present.update_dt = datetime.now()
                        present.updated_id = self.current_user.oid
                        present.inventory = present.inventory - 1

                        await present.save()

                        # 用户积分减少
                        member.update_dt = datetime.now()
                        member.updated_id = self.current_user.oid
                        member.integral = member.integral - present.ex_integral
                        await member.save()
                else:
                    res['code'] = 0
            except Exception:
                logger.error(traceback.format_exc())
                res['code'] = 0
        else:
            res['code'] = 0

        return res


URL_MAPPING_LIST = [
    url(r'/wechat/integral/center/', WechatIntegralCenterViewHandler, name='wechat_integral_center'),
    url(r'/wechat/integral/present/detail/', WechatIntegralPresentDetailViewHandler,
        name='wechat_integral_present_detail'),
    url(r'/wechat/integral/present/coupons/', WechatIntegralPresentCouponsViewHandler,
        name='wechat_integral_present_coupons'),
    url(r'/wechat/integral/present/orders/', WechatIntegralPresentOrdersViewHandler,
        name='wechat_integral_present_orders'),
    url(r'/wechat/integral/present/order/delete/', WechatIntegralPresentOrderDeleteViewHandler,
        name='wechat_integral_present_order_delete'),
    url(r'/wechat/integral/present/exchange/coupon/', WechatIntegralCouponExchangeViewHandler,
        name='wechat_integral_present_exchange_coupon'),
    url(r'/wechat/integral/present/exchange/gift/', WechatIntegralGiftExchangeViewHandler,
        name='wechat_integral_present_exchange_gift'),
]
