import datetime
import traceback

from actions.backoffice.race.lottery_draw.utils import get_red_status_count
from actions.backoffice.race.redpkt_rule.utils import generate_awards_by_item_settings
from actions.backoffice.race.utils import get_menu
from commons.page_utils import Paging
from db.models import RedPacketEntry, Member, RedPacketLotteryHistory, AdministrativeDivision, \
    RedPacketBasicSetting, RedPacketBox
from db.models import RedPacketItemSetting
from enums import PERMISSION_TYPE_MINIAPP_LOTTERY_DRAW_MANAGEMENT
from logger import log_utils
from motorengine import DESC
from motorengine.stages import MatchStage, SortStage, LookupStage, ProjectStage
from pymongo import ReadPreference
from tornado.web import url
from web import BaseHandler, decorators

logger = log_utils.get_logging()


class LotteryDrawSettingViewHandler(BaseHandler):
    """
    抽奖红包首页
    """

    def string_display(self, value, default='-'):
        if isinstance(value, (bytes, str, int, float)):
            if value:
                return value
        return default

    @decorators.render_template('backoffice/race/lottery_draw/lottery_manage.html')
    @decorators.permission_required(PERMISSION_TYPE_MINIAPP_LOTTERY_DRAW_MANAGEMENT)
    async def get(self):

        race_cid = self.get_argument('race_cid', '')
        menu_list = await get_menu(self, 'config', race_cid)
        rule_cid = self.get_argument('rule_cid', '')

        # 已经设置好的红包基础设置
        basic_setting_match = MatchStage({'record_flag': 1, 'race_cid': race_cid, 'rule_cid': rule_cid})
        basic_setting_sort = SortStage([('updated_dt', DESC)])
        basic_set_list = await RedPacketBasicSetting.aggregate(
            stage_list=[basic_setting_match, basic_setting_sort]).to_list(None)
        if basic_set_list:
            basic_set = basic_set_list[0]
        if not basic_set_list:
            basic_set = RedPacketBasicSetting()

        #  已经设置好的奖项设置
        red_packet_item_list = await RedPacketItemSetting.find(
            {'record_flag': 1, 'race_cid': race_cid, 'rule_cid': rule_cid}).sort('-amount').to_list(None)
        return locals()


class LotteryBasicSettingSubmitHandler(BaseHandler):
    """
    保存基础设置
    """

    @decorators.render_json
    @decorators.permission_required(PERMISSION_TYPE_MINIAPP_LOTTERY_DRAW_MANAGEMENT)
    async def post(self):
        r_dict = {'code': 0}
        race_cid = self.get_argument('race_cid')
        rule_cid = self.get_argument('rule_cid')
        expect_num = self.get_argument('expect_num')
        top_limit = self.get_argument('top_limit')
        fail_msg = self.get_argument('fail_msg')
        over_limit = self.get_argument('over_limit')
        content = self.get_argument('content')

        if not (race_cid and rule_cid):
            r_dict['code'] = -1
            return r_dict

        try:
            count = await RedPacketBox.count({'rule_cid': rule_cid, 'member_cid': {'$ne': None}})
            expect_num = int(expect_num)
            if expect_num <= count:
                r_dict['code'] = -2
                return r_dict

            settings = await RedPacketItemSetting.find({'rule_cid': rule_cid, 'record_flag': 1},
                                                       ReadPreference.PRIMARY).to_list(None)
            if not settings:
                r_dict['code'] = -3
                return r_dict

            # 更新抽奖基础信息设置
            basic_set = await RedPacketBasicSetting.find_one(
                {'race_cid': race_cid, 'rule_cid': rule_cid, 'record_flag': 1}, read_preference=ReadPreference.PRIMARY)
            if not basic_set:
                basic_set = RedPacketBasicSetting(race_cid=race_cid, rule_cid=rule_cid)

            basic_set.expect_num = expect_num
            basic_set.top_limit = int(top_limit)
            basic_set.fail_msg = fail_msg
            basic_set.over_msg = over_limit
            basic_set.guide = content
            basic_set.updated_dt = datetime.datetime.now()
            basic_set.updated_id = self.current_user.cid
            await basic_set.save()

            await generate_awards_by_item_settings(basic_set, settings)
            r_dict['code'] = 1
        except Exception:
            logger.error(traceback.format_exc())

        return r_dict


class LotteryPrizeItemSubmit(BaseHandler):
    """
    保存奖项
    """

    @decorators.render_json
    @decorators.permission_required(PERMISSION_TYPE_MINIAPP_LOTTERY_DRAW_MANAGEMENT)
    async def post(self):
        r_dict = {'code': 0}
        race_cid = self.get_argument('race_cid')
        rule_cid = self.get_argument('rule_cid')

        if not (race_cid and rule_cid):
            r_dict['code'] = -1
            return r_dict

        award_name_list = self.get_arguments('award_name_list[]')
        award_amount_list = self.get_arguments('award_amount_list[]')
        award_quantity_list = self.get_arguments('award_quantity_list[]')
        award_msg_list = self.get_arguments('award_msg_list[]')

        try:
            for name, amount, quantity, msg in zip(award_name_list, award_amount_list, award_quantity_list,
                                                   award_msg_list):
                item = RedPacketItemSetting(race_cid=race_cid, rule_cid=rule_cid)
                item.title = name
                item.amount = float(amount)
                item.quantity = int(quantity)
                item.message = msg

                await item.save()
            r_dict['code'] = 1
        except Exception:
            logger.error(traceback.format_exc())

        return r_dict


class LotteryResultListViewHandler(BaseHandler):
    """
    查看抽奖结果
    """

    @decorators.render_template('backoffice/race/lottery_draw/lottery_result.html')
    @decorators.permission_required(PERMISSION_TYPE_MINIAPP_LOTTERY_DRAW_MANAGEMENT)
    async def get(self):
        race_cid = self.get_argument('race_cid', '')
        if race_cid:

            # 抽奖总览
            match_stage = MatchStage({'race_cid': race_cid, 'record_flag': 1})
            old_match_stage = MatchStage({'race_cid': race_cid, 'record_flag': 0})
            a_sort = SortStage([('amount', DESC)])
            #  关闭活动之前设置好的奖项配置
            old_red_item_list = await RedPacketItemSetting.aggregate(stage_list=[old_match_stage, a_sort]).to_list(None)
            red_packet_item_list = await RedPacketItemSetting.aggregate(stage_list=[match_stage, a_sort]).to_list(None)
            #  中奖各个奖项的个数的列表
            old_win_prize_quantity_list = []
            win_prize_quantity_list = []
            #  剩下的奖项的个数
            remain_prize_quantity_list = []
            #  已经中奖的各个奖项的数量
            if red_packet_item_list:
                win_prize_quantity_list, remain_prize_quantity_list = await get_red_status_count(race_cid,
                                                                                                 red_packet_item_list)
            if old_red_item_list:

                old_win_prize_quantity_list, _ = await get_red_status_count(race_cid, old_red_item_list)
            else:
                red_packet_item_list = []
            #  抽奖详情
            kw_word = self.get_argument('kw_word', '')
            #  奖项标题
            item_title = self.get_argument('item_title', '')
            memebr_lookup = LookupStage(Member, 'open_id', 'open_id', 'member_list')
            attr_project = ProjectStage(**{
                'member_cid': {'$arrayElemAt': ['$member_list.cid', 0]},
                'nick_name': {'$arrayElemAt': ['$member_list.nick_name', 0]},
                'province_code': {'$arrayElemAt': ['$member_list.province_code', 0]},
                'city_code': {'$arrayElemAt': ['$member_list.city_code', 0]},
                'lottery_dt': '$lottery_dt',
                'award_cid': '$award_cid'
            })
            p_lookup = LookupStage(AdministrativeDivision, 'province_code', 'code', 'p_list')
            c_lookup = LookupStage(AdministrativeDivision, 'city_code', 'code', 'c_list')
            award_lookup = LookupStage(RedPacketEntry, 'award_cid', 'cid', 'entry_list')
            info_project = ProjectStage(**{
                'member_cid': '$member_cid',
                'nick_name': '$nick_name',
                'p_list': '$p_list',
                'c_list': '$c_list',
                'province': {'$arrayElemAt': ['$p_list.title', 0]},
                'city': {'$arrayElemAt': ['$c_list.title', 0]},
                'lottery_dt': '$lottery_dt',
                'award_cid': {'$arrayElemAt': ['$entry_list.award_cid', 0]}
            })
            item_lookup = LookupStage(RedPacketItemSetting, 'award_cid', 'cid', 'item_list')
            final_project = ProjectStage(**{
                'member_cid': '$member_cid',
                'nick_name': '$nick_name',
                'province': '$province',
                'city': '$city',
                'p_list': '$p_list',
                'c_list': '$c_list',
                'lottery_dt': '$lottery_dt',
                'award_title': {'$arrayElemAt': ['$item_list.title', 0]},
                'item_list': '$item_list'
            })
            query_dict = {}
            if kw_word:
                query_dict['$or'] = [
                    {'province': {'$regex': kw_word, '$options': 'i'}},
                    {'city': {'$regex': kw_word, '$options': 'i'}},
                    {'nick_name': {'$regex': kw_word, '$options': 'i'}},
                    {'member_cid': {'$regex': kw_word, '$options': 'i'}},
                ]
            if item_title:
                query_dict['award_title'] = {'$regex': item_title, '$options': 'i'}
            query = MatchStage(query_dict)
            query_match_dict = {'race_cid': race_cid}
            per_page_quantity = int(self.get_argument('per_page_quantity', 10))
            to_page_num = int(self.get_argument('page', 1))
            page_url = '%s?page=$page&per_page_quantity=%s&race_cid=%s&kw_name=%s&item_title=%s' % (
                self.reverse_url("backoffice_race_lottery_result_list"), per_page_quantity, race_cid, kw_word,
                item_title)
            paging = Paging(page_url, RedPacketLotteryHistory, current_page=to_page_num,
                            pipeline_stages=[memebr_lookup, attr_project, p_lookup, c_lookup, award_lookup,
                                             info_project, item_lookup, final_project, query],
                            items_per_page=per_page_quantity, **query_match_dict)
            await paging.pager()
        return locals()


URL_MAPPING_LIST = [
    url(r'/backoffice/race/lottery/draw/setting/', LotteryDrawSettingViewHandler,
        name='backoffice_race_lottery_setting'),
    url(r'/backoffice/race/lottery/draw/result/list/', LotteryResultListViewHandler,
        name='backoffice_race_lottery_result_list'),
    url(r'/backoffice/race/lottery/basic/submit/', LotteryBasicSettingSubmitHandler,
        name='backoffice_race_lottery_basic_submit'),
    url(r'/backoffice/race/lottery/award/submit/', LotteryPrizeItemSubmit, name='backoffice_race_lottery_award_submit')
]
