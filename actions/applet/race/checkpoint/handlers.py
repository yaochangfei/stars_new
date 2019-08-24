import traceback

from actions.applet import find_member_by_open_id
from actions.applet.race.checkpoint.utils import check_enter_race
from actions.applet.race.utils import do_get_suite_subject_list, deal_subject_list, has_redpkt
from actions.applet.utils import is_redpacket_enabled, async_add_notice
from db import STATUS_GAME_CHECK_POINT_ACTIVE, STATUS_RESULT_CHECK_POINT_WIN, TYPE_MSG_LOTTERY, \
    CATEGORY_REDPACKET_RULE_LOTTERY
from db import STATUS_USER_ACTIVE
from db.models import Member, RaceMapping, RaceGameCheckPoint, AdministrativeDivision, Race, RedPacketRule, \
    RedPacketBox
from db.models import MemberCheckPointHistory
from logger import log_utils
from motorengine import DESC, datetime
from motorengine.stages import MatchStage, SortStage, LookupStage
from motorengine.stages.group_stage import GroupStage
from pymongo import ReadPreference
from tasks.instances.task_lottery_queuing import start_lottery_queuing
from tornado.web import url
from web import WechatAppletHandler, decorators
from wechat import wechat_utils

logger = log_utils.get_logging()


class AppletRaceCheckpointsGetHandler(WechatAppletHandler):
    """获取竞赛所有关卡信息&会员当前关卡信息"""

    @decorators.render_json
    @decorators.wechat_applet_authenticated
    async def post(self):
        r_dict = {'code': 0}
        open_id = self.get_i_argument('open_id', '')
        race_cid = self.get_i_argument('race_cid', '')
        if not open_id:
            r_dict['code'] = 1001
            return r_dict

        try:
            member = await find_member_by_open_id(open_id)
            if not member or not member.auth_address:
                r_dict['code'] = 1002
                return r_dict
            #  判断用户的授权地理位置信息和活动位置是否相符
            r_dict = await check_enter_race(member, race_cid)
            if not r_dict['enter_race']:
                r_dict['code'] = 0
                return r_dict
            mapping = await RaceMapping.find_one({'race_cid': race_cid, 'member_cid': member.cid, 'record_flag': 1},
                                                 read_preference=ReadPreference.PRIMARY)
            if not mapping:
                mapping = RaceMapping(race_cid=race_cid, member_cid=member.cid)
                mapping.province_code = member.province_code
                mapping.city_code = member.city_code
                mapping.district_code = member.district_code
                mapping.age_group = member.age_group
                mapping.sex = member.sex
                mapping.category = member.category
                mapping.education = member.education

            if not mapping.auth_address:
                mapping.auth_address = member.auth_address

            await mapping.save()

            race_checkpoints = await RaceGameCheckPoint.aggregate(stage_list=[
                MatchStage({'status': STATUS_GAME_CHECK_POINT_ACTIVE, 'race_cid': race_cid}),
                LookupStage(RedPacketRule, 'redpkt_rule_cid', 'cid', 'rule_list'),
                SortStage([('index', DESC)])
            ]).to_list(None)
            if race_checkpoints:
                is_end = False
                checkpoint_history = await MemberCheckPointHistory.find_one(
                    filtered={'member_cid': member.cid, 'check_point_cid': race_checkpoints[0].cid,
                              'status': STATUS_RESULT_CHECK_POINT_WIN, 'record_flag': 1})
                if checkpoint_history:
                    is_end = True
                race_checkpoint_cids = [c.cid for c in race_checkpoints]
                if not mapping.race_check_point_cid or mapping.race_check_point_cid not in race_checkpoint_cids:
                    mapping.race_check_point_cid = race_checkpoint_cids[-1]
                    await member.save()
                    cur_game_checkpoint_cid = race_checkpoint_cids[-1]
                elif is_end:
                    cur_game_checkpoint_cid = race_checkpoint_cids[0]
                else:
                    index = race_checkpoint_cids.index(mapping.race_check_point_cid)
                    cur_game_checkpoint_cid = race_checkpoint_cids[index]
                game_checkpoint_list = [{'cid': checkpoint.cid,
                                         'index': checkpoint.index,
                                         'alias': checkpoint.alias,
                                         'unlock_quantity': checkpoint.unlock_quantity,
                                         'has_redpkt': await has_redpkt(race_cid, checkpoint, member.cid)}
                                        for checkpoint in race_checkpoints]

                r_dict = {
                    'race_cid': race_cid,
                    'code': 1000,
                    'is_end': is_end,
                    'avatar': member.avatar,
                    'nick_name': member.nick_name,
                    'cur_game_checkpoint_cid': cur_game_checkpoint_cid,
                    'game_checkpoint_list': game_checkpoint_list
                }
            else:
                r_dict['code'] = 1000
                r_dict['game_checkpoint_list'] = []
        except Exception:
            logger.error(traceback.format_exc())
        return r_dict


class AppletRaceAreaRankingListHandler(WechatAppletHandler):
    """
    竞赛地区排行
    """

    @decorators.render_json
    @decorators.wechat_applet_authenticated
    async def post(self):
        r_dict = {'code': 0}
        open_id = self.get_i_argument('open_id', '')
        race_cid = self.get_i_argument('race_cid', '')

        if not race_cid:
            r_dict['code'] = 1001
            return r_dict

        try:
            member = await find_member_by_open_id(open_id)
            if not member.auth_address:
                r_dict['code'] = 1002
                return r_dict

            race = await Race.find_one({'cid': race_cid})

            rankings = []
            province = member.auth_address.get('province')
            city = member.auth_address.get('city')

            if not race.city_code:
                # 省级活动, 城市排序
                match_stage = MatchStage({'auth_address.province': province, 'race_cid': race_cid})
                group_stage = GroupStage('auth_address.city', sum={'$sum': 1})

            else:
                # 市级活动, 区域排序
                c = await AdministrativeDivision.find_one({'title': city, 'parent_code': {"$ne": None}})
                match_stage = MatchStage({'auth_address.city': city, 'race_cid': race_cid})
                group_stage = GroupStage('auth_address.district', sum={'$sum': 1})

            area_list = await RaceMapping.aggregate(stage_list=[
                match_stage,
                group_stage,
                SortStage([('sum', DESC)])
            ]).to_list(None)

            for area in area_list:
                rank = {
                    'title': area.id if area.id else '其他地区',
                    'people_count': area.sum
                }
                rankings.append(rank)
            r_dict = {
                'code': 1000,
                'rankings': rankings
            }
        except Exception:
            logger.error(traceback.format_exc())

        return r_dict


class AppletRaceCheckpointQuestionsGetViewHandler(WechatAppletHandler):
    """
   获取关卡题目，包括对手答案、给出答案的时间
    """

    @decorators.render_json
    @decorators.wechat_applet_authenticated
    async def post(self):
        r_dict = {'code': 0}
        open_id = self.get_i_argument('open_id', '')
        race_cid = self.get_i_argument('race_cid', '')
        checkpoint_cid = self.get_i_argument('checkpoint_cid', '')
        if not (open_id and race_cid):
            r_dict['code'] = 1001
            return r_dict
        try:
            if checkpoint_cid:
                member = await find_member_by_open_id(open_id)
                race_mapping = await RaceMapping.find_one(
                    {'record_flag': 1, 'race_cid': race_cid, 'member_cid': member.cid})
                if race_mapping:
                    race_checkpoint = await RaceGameCheckPoint.find_one({'cid': checkpoint_cid})
                    checkpoint_rule_cid = race_checkpoint.rule_cid if race_checkpoint else None
                    subject_list = await do_get_suite_subject_list(race_cid, checkpoint_rule_cid, member=member)
                    question_list, answer_list = await deal_subject_list(race_cid, subject_list)
                    r_dict['question_list'] = question_list
                    r_dict['answers'] = answer_list
                    r_dict['code'] = 1000
                else:
                    r_dict['code'] = 1002
            else:
                r_dict['code'] = 1003
        except Exception:
            logger.error(traceback.format_exc())
        return r_dict


class MiniappSubmitGameCheckpointAnswerViewHandler(WechatAppletHandler):
    """
    提交竞赛关卡题目答案
    """

    @decorators.render_json
    @decorators.wechat_applet_authenticated
    async def post(self):
        r_dict = {'code': 0, 'mobile_enabled': False}
        open_id = self.get_i_argument('open_id', '')
        own = self.get_i_argument('data', {})
        checkpoint_cid = own.get('checkpoint_cid', '')
        min_datetime = datetime.datetime.now().replace(hour=0, minute=0, second=0, microsecond=0)
        max_datetime = datetime.datetime.now().replace(hour=23, minute=59, second=59, microsecond=999)
        try:
            r_dict['show_resolving'] = False
            #  判断是否不让用户答题
            r_dict['answer_forbidden'] = False
            if open_id:
                member = await find_member_by_open_id(open_id)
                if member:
                    if own:
                        check_point = await RaceGameCheckPoint.find_one({'cid': checkpoint_cid, 'record_flag': 1})
                        if check_point:
                            race = await Race.find_one({'cid': check_point.race_cid, 'record_flag': 1})
                            if race.resolving_enabled:
                                r_dict['show_resolving'] = True
                        has_answer_count = await MemberCheckPointHistory.count({'member_cid': member.cid,
                                                                                'check_point_cid': checkpoint_cid,
                                                                                'updated_dt': {
                                                                                    '$gt': min_datetime,
                                                                                    '$lt': max_datetime}})
                        # 处理答案数据，增加答题历史
                        unlock, is_end, is_challenge_success, correct_list = \
                            await wechat_utils.deal_checkpoint_own_answer(check_point.race_cid, member, own,
                                                                          checkpoint_cid)
                        is_pass = bool(await MemberCheckPointHistory.find_one(
                            {'member_cid': member.cid, 'status': STATUS_RESULT_CHECK_POINT_WIN,
                             'check_point_cid': checkpoint_cid}))

                        answer_count = has_answer_count + 1
                        #  如果有答题限制, 则判断答题次数和答题限制数量的关系
                        if check_point.answer_limit_quantity:
                            if check_point.answer_limit_quantity <= answer_count and not is_pass:
                                r_dict['answer_forbidden'] = True
                            if not is_pass and answer_count < check_point.answer_limit_quantity:
                                remainder_answer_count = check_point.answer_limit_quantity - answer_count
                                r_dict['remainder_answer_count'] = remainder_answer_count
                        if is_challenge_success:
                            checkpoint = await RaceGameCheckPoint.get_by_cid(checkpoint_cid)

                            # 只能发起一次领奖请求
                            rp_box = await RedPacketBox.count(
                                {'checkpoint_cid': checkpoint_cid, 'member_cid': member.cid, 'record_flag': 1})
                            if rp_box or not await is_redpacket_enabled(checkpoint):
                                r_dict['redpkt_enabled'] = False
                            else:
                                r_dict['redpkt_enabled'] = True
                                redpkt_rule = await RedPacketRule.get_by_cid(checkpoint.redpkt_rule_cid)
                                r_dict['redpkt_category'] = redpkt_rule.category
                                r_dict['checkpoint_cid'] = checkpoint.cid

                                if redpkt_rule.category == CATEGORY_REDPACKET_RULE_LOTTERY:
                                    await async_add_notice(member.cid, check_point.race_cid, checkpoint_cid,
                                                           msg_type=TYPE_MSG_LOTTERY)
                                else:
                                    start_lottery_queuing.delay(member.cid, checkpoint.race_cid,
                                                                redpkt_rule, checkpoint_cid)

                                    # time_begin = time.time()
                                    # while time.time() - time_begin <= 2:
                                    #     ret = RedisCache.hget(KEY_RACE_LOTTERY_RESULT.format(checkpoint_cid),
                                    #                           member.cid)
                                    #     if ret is not None:
                                    #         break
                                    #
                                    #     await asyncio.sleep(1)

                        if is_end:
                            race = await Race.get_by_cid(check_point.race_cid)
                            race_map = await RaceMapping.find_one(
                                {'member_cid': member.cid, 'race_cid': check_point.race_cid, 'record_flag': 1})
                            if race.mobile_enabled:
                                if race_map and not race_map.mobile:
                                    r_dict['mobile_enabled'] = True

                        r_dict['question_accuracy'] = correct_list
                        r_dict['unlock'] = unlock
                        r_dict['is_end'] = is_end
                        r_dict['is_challenge_success'] = is_challenge_success
                        r_dict['answer_count'] = answer_count
                        r_dict['code'] = 1000
                    else:
                        r_dict['code'] = 1003
                else:
                    r_dict['code'] = 1001
            else:
                r_dict['code'] = 1002
        except Exception:
            logger.error(traceback.format_exc())
        return r_dict


class AppletRaceIsAnswerHandler(WechatAppletHandler):
    """
    判断该关卡是否可以答题的
    """

    @decorators.render_json
    @decorators.wechat_applet_authenticated
    async def post(self):
        r_dict = {'code': 0}
        open_id = self.get_i_argument('open_id', '')
        checkpoint_cid = self.get_i_argument('checkpoint_cid', '')
        min_datetime = datetime.datetime.now().replace(hour=0, minute=0, second=0, microsecond=0)
        max_datetime = datetime.datetime.now().replace(hour=23, minute=59, second=59, microsecond=999)
        try:
            #  判断是否不让用户答题
            r_dict['answer_forbidden'] = False
            if open_id:
                member = await find_member_by_open_id(open_id)
                if member:
                    if not checkpoint_cid:
                        r_dict['code'] = 1004
                        return r_dict
                    checkpoint = await RaceGameCheckPoint.find_one({'cid': checkpoint_cid, 'record_flag': 1})
                    checkpoint_history_list = await MemberCheckPointHistory.find(
                        {'member_cid': member.cid, 'check_point_cid': checkpoint_cid,
                         'updated_dt': {'$gt': min_datetime,
                                        '$lt': max_datetime}}).to_list(None)

                    status_list = []
                    if checkpoint_history_list:
                        status_list = [checkpoint_history.status for checkpoint_history in checkpoint_history_list]
                    if checkpoint.answer_limit_quantity and checkpoint.answer_limit_quantity != 0 and status_list and \
                            STATUS_RESULT_CHECK_POINT_WIN not in status_list and len(
                        checkpoint_history_list) >= checkpoint.answer_limit_quantity:
                        r_dict['answer_forbidden'] = True
                    r_dict['code'] = 1000
                else:
                    r_dict['code'] = 1003
            else:
                r_dict['code'] = 1001
        except Exception:
            logger.error(traceback.format_exc())
        return r_dict


URL_MAPPING_LIST = [
    url(r'/wechat/applet/race/checkpoint/questions/get/', AppletRaceCheckpointQuestionsGetViewHandler,
        name='wechat_applet_race_checkpoint_questions_get'),
    url(r'/wechat/applet/race/checkpoint/questions/save/', MiniappSubmitGameCheckpointAnswerViewHandler,
        name='wechat_applet_race_checkpoint_questions_save'),
    url(r'/wechat/applet/race/ranking/list/', AppletRaceAreaRankingListHandler,
        name='wechat_applet_race_ranking_list'),
    url(r'/wechat/applet/race/checkpoint/list/', AppletRaceCheckpointsGetHandler,
        name='wechat_applet_race_checkpoint_list'),
    url(r'/wechat/applet/race/checkpoint/judge/answer/forbidden/', AppletRaceIsAnswerHandler,
        name='wechat_applet_race_checkpoint_judge_answer_forbidden'),
]
