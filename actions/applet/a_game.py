# !/usr/bin/python

import datetime
import random
import time
import traceback

from tornado.web import url

from actions.applet import find_member_by_open_id
from actions.applet.utils import do_get_suite_subject_list, deal_subject_list, pk_award, \
    get_member_ranking_list, deal_with_own_answers, update_member_pk_info
from db import STATUS_USER_ACTIVE, TYPE_DAN_GRADE_ONE, SOURCE_MEMBER_DIAMOND_PK_ENTRANCE_FEE, TYPE_DAN_GRADE_ELEVEN, \
    STATUS_RESULT_GAME_PK_WIN, \
    STATUS_RESULT_GAME_PK_FAILED, STATUS_RESULT_GAME_PK_TIE_BREAK, STATUS_RESULT_GAME_PK_GIVE_UP, \
    TYPE_STAR_GRADE_FIVE, ANSWER_LIMIT_NUMBER, CATEGORY_NOTICE_FRIENDS_PLAY, \
    STATUS_GAME_DAN_GRADE_ACTIVE, DAN_STAR_GRADE_MAPPING, TYPE_STAR_GRADE_ZERO, CATEGORY_EXAM_CERTIFICATE_DICT, \
    SOURCE_MEMBER_DIAMOND_DAILY_SHARE_TIMES_LIMIT, SOURCE_MEMBER_DIAMOND_DAILY_SHARE, SOURCE_MEMBER_DIAMOND_DICT, \
    KNOWLEDGE_FIRST_LEVEL_DICT, KNOWLEDGE_SECOND_LEVEL_DICT
from db.model_utils import update_diamond_reward, get_cache_answer_limit, set_cache_answer_limit, get_cache_share_times, \
    set_cache_share_times, do_diamond_reward
from db.models import Member, MemberGameHistory, GameDiamondConsume, GameDiamondReward, MemberFriend, MemberNotice, \
    GameDanGrade, AdministrativeDivision, MemberStarsAwardHistory, \
    MemberExamCertificate, SubjectResolvingViewedStatistics, Subject, SubjectOption, UploadFiles
from logger import log_utils
from motorengine import DESC, ASC
from motorengine.stages import MatchStage, SortStage, LookupStage, LimitStage
from settings import SERVER_PROTOCOL, SERVER_HOST, STATIC_URL_PREFIX
from web import decorators, WechatAppletHandler
from wechat import wechat_utils
from wechat.enums import MINI_APP_STATIC_URL_PREFIX
from .utils import get_dan_grade_by_index, convert_subject_dimension_dict

logger = log_utils.get_logging('a_game', 'a_game.log')


class AppletGameFightQuestionsGetViewHandler(WechatAppletHandler):
    """
   获取排位赛题目，包括对手答案、给出答案的时间
    """

    @decorators.render_json
    @decorators.wechat_applet_authenticated
    async def post(self):
        r_dict = {'code': 0}
        try:
            open_id = self.get_i_argument('open_id', None)
            if open_id:
                member = await find_member_by_open_id(open_id)
                if member:
                    dan_grade_index = member.dan_grade if member.dan_grade else 1
                    game_dan_grade_list = await GameDanGrade.find(dict(status=STATUS_GAME_DAN_GRADE_ACTIVE)).sort(
                        [('index', ASC)]).to_list(None)
                    game_dan_grade = game_dan_grade_list[dan_grade_index - 1] if len(
                        game_dan_grade_list) >= dan_grade_index else None
                    rule_cid = game_dan_grade.rule_cid if game_dan_grade else None
                    subject_list = await  do_get_suite_subject_list(rule_cid=rule_cid, member=member)
                    question_list, answer_list = await deal_subject_list(subject_list)
                    r_dict['question_list'] = question_list
                    r_dict['answers'] = answer_list
                    # r_dict['init_own_answers'] = [{'questionid': subject.cid} for subject in subject_list]
                    r_dict['code'] = 1000
                else:
                    r_dict['code'] = 1002
            else:
                r_dict['code'] = 1001
        except Exception:
            logger.error(traceback.format_exc())
        return r_dict


class MiniappSubmitAnswersViewHandler(WechatAppletHandler):
    """保存排位赛结果"""

    @decorators.render_json
    @decorators.wechat_applet_authenticated
    async def post(self):
        r_dict = {'code': 0}
        try:
            open_id = self.get_i_argument('open_id', None)
            own = self.get_i_argument('data', {})
            if open_id:
                member = await find_member_by_open_id(open_id)
                if member:
                    if own:
                        # 处理答案数据，增加答题历史
                        pk_status, unlock, continuous_win_times, question_accuracy, member_game_history = await deal_with_own_answers(
                            member, own)
                        if own.get('dan_grade_index'):
                            if pk_status == STATUS_RESULT_GAME_PK_WIN:
                                member_stars_award_history = MemberStarsAwardHistory()
                                member_stars_award_history.dan_grade = member_game_history.dan_grade
                                member_stars_award_history.member_cid = member.cid
                                member_stars_award_history.quantity = 1
                                member_stars_award_history.award_dt = datetime.datetime.now()
                                await member_stars_award_history.save()

                            end_datetime = datetime.datetime.now().replace(hour=23, minute=59, second=59,
                                                                           microsecond=999)
                            current_datetime = datetime.datetime.now()
                            timeout = (end_datetime - current_datetime).seconds
                            set_cache_answer_limit(member.cid, timeout)
                            # 根据pk结果处理信息
                            # level_list, level_list_new = await wechat_utils.get_level_list_info(
                            #     member, pk_status=pk_status, unlock=unlock,
                            #     pk_grade=own.get('grade', TYPE_DAN_GRADE_ONE))
                            # level_list, level_list_new = await wechat_utils.get_level_list_info2(
                            #     member, pk_status=pk_status, unlock=unlock,
                            #     pk_grade=own.get('grade', TYPE_DAN_GRADE_ONE))

                            # 更新用户pk信息
                            # 存在钻石加减
                            diamond_changes = await update_member_pk_info(
                                member, pk_status, unlock, own.get('dan_grade_index', TYPE_DAN_GRADE_ONE))
                            # 判断钻石奖励（首次PK，首次获胜，连胜奖励）, 积分奖励，首次pk，每日首次pk
                            # 放在更新用户pk信息之后
                            diamond_reward_amount, first_fight_amount, first_fight_win_amount, continuous_win_amount = await pk_award(
                                member, pk_status, continuous_win_times)

                            # 判断当前等级是否全部解锁
                            member = await find_member_by_open_id(open_id)
                            all_unlock = False
                            if member.dan_grade == TYPE_DAN_GRADE_ELEVEN and member.star_grade >= TYPE_STAR_GRADE_FIVE:
                                all_unlock = True
                            r_dict['code'] = 1000
                            r_dict['all_unlock'] = all_unlock
                            # r_dict['level_list'] = level_list
                            # r_dict['level_list_new'] = level_list_new
                            r_dict['unlock'] = unlock
                            r_dict['diamond_changes'] = diamond_changes
                            r_dict['diamond_reward_amount'] = diamond_reward_amount

                            r_dict['first_fight_amount'] = first_fight_amount
                            r_dict['first_fight_win_amount'] = first_fight_win_amount
                            r_dict['continuous_win_amount'] = continuous_win_amount
                            r_dict['streak_times'] = continuous_win_times

                            r_dict['question_accuracy'] = question_accuracy
                        else:
                            source_open_id = self.get_i_argument('source_open_id', None)
                            if source_open_id:
                                pk_status = int(own.get('pk_status', STATUS_RESULT_GAME_PK_GIVE_UP))  # pk结果
                                source_member = await find_member_by_open_id(source_open_id)
                                if source_member:
                                    nick_name = member.nick_name if member.nick_name else '游客'
                                    content = None
                                    if pk_status == STATUS_RESULT_GAME_PK_WIN:
                                        content = '很遗憾，你的好友 %s 在对战中击败了您！' % nick_name
                                    elif pk_status == STATUS_RESULT_GAME_PK_FAILED:
                                        content = '恭喜你，在对战中击败了好友 %s! ' % nick_name
                                    elif pk_status == STATUS_RESULT_GAME_PK_TIE_BREAK:
                                        content = '您的好友 %s 在对战中和你战成了平局! ' % nick_name
                                    if content:
                                        await MemberNotice(
                                            member_cid=source_member.cid,
                                            category=CATEGORY_NOTICE_FRIENDS_PLAY,
                                            content=content).save()
                            game_history_count = await MemberGameHistory.count(
                                filtered={'member_cid': member.cid, 'runaway_index': None})
                            r_dict['can_friend_share'] = False
                            if game_history_count > 0:
                                r_dict['can_friend_share'] = True
                            r_dict['question_accuracy'] = question_accuracy
                            r_dict['code'] = 1010
                else:
                    r_dict['code'] = 1002
            else:
                r_dict['code'] = 1001
        except Exception:
            logger.error(traceback.format_exc())
        return r_dict


class AppletFightFriendQuestionsGetViewHandler(WechatAppletHandler):
    """
   获取好友对战时分享人的题目信息
    """

    @decorators.render_json
    @decorators.wechat_applet_authenticated
    async def post(self):
        r_dict = {'code': 0}
        try:
            open_id = self.get_i_argument('open_id', None)
            if open_id:
                member = await find_member_by_open_id(open_id)
                if member:
                    opponent, question_list, init_own_answer_list = await wechat_utils.generate_opponent_answers(member)
                    r_dict['opponent'] = opponent
                    r_dict['question_list'] = question_list
                    r_dict['init_own_answers'] = init_own_answer_list
                    r_dict['code'] = 1000
                else:
                    r_dict['code'] = 1002
            else:
                r_dict['code'] = 1001
        except Exception:
            logger.error(traceback.format_exc())
        return r_dict


class AppletFightMemberGetHandler(WechatAppletHandler):
    """
    获取排位赛对手信息（虚拟）
    """

    @decorators.render_json
    @decorators.wechat_applet_authenticated
    async def post(self):
        """

        :return:
        """
        r_dict = {'code': 0}
        open_id = self.get_i_argument('open_id', None)
        grade_index = self.get_i_argument('dan_grade_index', TYPE_DAN_GRADE_ONE)
        try:
            if not open_id:
                r_dict['code'] = 1001
                return r_dict

            t1 = time.time()
            member = await find_member_by_open_id(open_id)
            r_dict['own_base'] = {
                'open_id': open_id,
                'dan_grade_index': member.dan_grade if member.dan_grade else 0,
                'dan_grade_title': await get_dan_grade_by_index(member.dan_grade),
                'nick_name': member.nick_name,
                'avatar_url': member.avatar,
            }
            t2 = time.time()
            logger.info('[%s] get_own: %s' % (open_id, t2 - t1))

            city = await AdministrativeDivision.find_one({'code': member.city_code})
            r_dict['own_base']['city'] = city.title if city else u"未知"

            history_list = await MemberGameHistory.find({'cid': member.cid}).sort('-fight_datetime').limit(1).to_list(1)
            continuous_win_times = history_list[0].continuous_win_times if history_list else 0
            r_dict['own_base']['continuous_win_times'] = continuous_win_times
            t3 = time.time()
            logger.info('[%s] get_own_win_times: %s' % (open_id, t3 - t2))

            pk_member_list = await Member.find(
                {'open_id': {'$ne': open_id, '$exists': True}, 'status': STATUS_USER_ACTIVE,
                 'province_code': {'$ne': None}}).skip(random.randint(0, 20000)).limit(1).to_list(1)

            pk_member = pk_member_list[0]
            pk_member_city = await AdministrativeDivision.find_one({'code': pk_member.city_code})
            r_dict['opponent_base'] = {
                'open_id': pk_member.open_id,
                'dan_grade_index': pk_member.dan_grade if pk_member.dan_grade else 0,
                'dan_grade_title': await get_dan_grade_by_index(pk_member.dan_grade),
                'city': pk_member if pk_member_city else u'未知',
                'nick_name': pk_member.nick_name,
                'avatar_url': pk_member.avatar,
                'continuous_win_times': random.randint(0, 5)
            }

            t4 = time.time()
            logger.info('[%s] get_opp: %s' % (open_id, t4 - t3))
            # 入场费
            diamond_consume = await GameDiamondConsume.find_one(dict(source=int(grade_index) if grade_index else 0))
            diamond_consume_quantity = diamond_consume.quantity if diamond_consume.quantity else 0
            member_diamond = member.diamond if member.diamond else 0
            member.diamond = member_diamond - diamond_consume_quantity
            member.updated_dt = datetime.datetime.now()
            # 入场费记录
            await update_diamond_reward(member.cid, SOURCE_MEMBER_DIAMOND_PK_ENTRANCE_FEE,
                                        -diamond_consume_quantity)
            t5 = time.time()
            logger.info('[%s] deal_record: %s' % (open_id, t5 - t4))
            await member.save()
            r_dict['code'] = 1000

        except Exception:
            logger.error(traceback.format_exc())
        return r_dict


class AppletFightDanGradeListHandler(WechatAppletHandler):
    """获取排位赛所有段位"""

    @decorators.render_json
    @decorators.wechat_applet_authenticated
    async def post(self):
        """{
              "code": [整型]返回码,
              "current_dan_index": [整型]会员当前段位(旧current_level)
              "dan_grade_list": [(旧level_list)
                     {
                            "dan_grade_index": [整型]段位下标,
                            "dan_grade_title": [字符串]段位名称(旧title),
                            "dan_grade_title_url": [字符串]段位名称图地址(旧name),
                            "logo_url": [字符串]段位LOGO地址(旧logo),
                            "unlocked": [布尔值]是否解锁(旧if_lock),
                            "stars": [
                                 {"status" : ""},
                                 {"status" : "pass"},
                                 {"status" : "through"},
                            ],
                            "diamond_consume": [布尔值]钻石消耗量(旧cost)
                     },
                     ...
              ]
       }"""
        r_dict = {'code': 0}
        open_id = self.get_i_argument('open_id')
        if not open_id:
            r_dict['code'] = 1001
            return r_dict
        try:
            def get_stars(current_level, current_star, grade_index):
                stars = []
                if grade_index > current_level:
                    stars = [{'status': ''} for _ in range(DAN_STAR_GRADE_MAPPING.get(grade_index))]
                elif grade_index < current_level:
                    stars = [{'status': 'pass'} for _ in range(DAN_STAR_GRADE_MAPPING.get(grade_index))]
                elif grade_index == current_level:
                    # 判断最后一级全部解锁
                    if grade_index == TYPE_DAN_GRADE_ELEVEN and current_star == DAN_STAR_GRADE_MAPPING.get(grade_index):
                        stars = [{'status': 'pass'} for _ in range(DAN_STAR_GRADE_MAPPING.get(grade_index))]
                    else:
                        for _ in range(DAN_STAR_GRADE_MAPPING.get(grade_index) - current_star):
                            stars.append({'status': ''})
                        for _ in range(current_star):
                            stars.append({'status': 'through'})

                return stars

            member = await find_member_by_open_id(open_id)
            if not member:
                r_dict['code'] = 1002
                return r_dict

            dan_grade = member.dan_grade if member.dan_grade else TYPE_DAN_GRADE_ONE
            star_grade = member.star_grade if member.star_grade else TYPE_STAR_GRADE_ZERO

            diamond_consume_list = await GameDiamondConsume.find().sort([('source', ASC)]).to_list(None)

            diamond_consume_dict = {diamond_consume.source: diamond_consume.quantity for diamond_consume in
                                    diamond_consume_list}
            dan_grades = await GameDanGrade.find({'status': STATUS_GAME_DAN_GRADE_ACTIVE}).sort(
                [('index', ASC)]).to_list(None)
            for dan in dan_grades:
                if 'dan_grade_list' not in r_dict:
                    r_dict['dan_grade_list'] = []
                if dan.index > member.dan_grade:
                    if member.star_grade == DAN_STAR_GRADE_MAPPING.get(member.dan_grade):
                        if_lock = False
                    else:
                        if_lock = True
                else:
                    if_lock = False

                r_dict['dan_grade_list'].append({
                    'dan_grade_index': dan.index,
                    'dan_grade_title': dan.title,
                    'dan_grade_title_url': '{protocol}://{host}{static_url}level{index}.png'.format(
                        protocol=SERVER_PROTOCOL, host=SERVER_HOST, static_url=MINI_APP_STATIC_URL_PREFIX,
                        index=dan.index),
                    'logo_url': '{protocol}://{host}{static_url}sign{index}.png'.format(
                        protocol=SERVER_PROTOCOL, host=SERVER_HOST, static_url=MINI_APP_STATIC_URL_PREFIX,
                        index=dan.index),
                    'if_lock': if_lock,
                    'stars': get_stars(dan_grade, star_grade, dan.index),
                    'diamond_consume': diamond_consume_dict.get(dan.index, 0)
                })

            if dan_grade >= len(r_dict['dan_grade_list']):
                dan_grade = len(r_dict['dan_grade_list'])
            elif dan_grade - 2 <= 0:
                dan_grade = 1
            else:
                dan_grade -= 2

            r_dict['current_dan_index'] = dan_grade
            r_dict['code'] = 1000
        except Exception:
            logger.error(traceback.format_exc())
        return r_dict


# class AppletVaultBankAwardHandler(WechatAppletHandler):
#     """领取金库奖励"""
#
#     @decorators.render_json
#     @decorators.wechat_applet_authenticated
#     async def post(self):
#         r_dict = {'code': 0}
#         open_id = self.get_i_argument('open_id')
#         if not open_id:
#             return r_dict
#
#         try:
#             member = await Member.find_one({'open_id': open_id, 'status': STATUS_USER_ACTIVE})
#             if not member:
#                 return r_dict
#
#             vault_bank = await VaultDiamondBank.find_one({"quantity": {'$ne': None}})
#             if vault_bank:
#                 r_dict['code'] = 1001
#                 return r_dict
#
#             start_datetime = datetime.datetime.now().replace(hour=0, minute=0, second=0, microsecond=0)
#             end_datetime = datetime.datetime.now().replace(hour=23, minute=59, second=59, microsecond=999)
#             details = await MemberDiamondDetail.find(
#                 {
#                     '$and': [
#                         {"member_cid": member.cid},
#                         {"source": SOURCE_MEMBER_DIAMOND_VAULT_REWARD},
#                         {"reward_datetime": {'$gte': start_datetime}},
#                         {"reward_datetime": {'$lte': end_datetime}}
#                     ]
#                 }
#             ).sort(['reward_datetime', DESC]).to_list(None)
#
#             if details:
#                 count = len(details)
#                 if count != 0 and count > vault_bank.times:
#                     return r_dict
#
#                 latest_diamond_detail = details[0]
#                 # 距上次奖励的时间间隔
#                 spacing_time = datetime.datetime.now() - latest_diamond_detail.reward_datetime
#                 if spacing_time.minute >= vault_bank.minutes:
#                     award_member_diamond = int(vault_bank.quantity)
#                 else:
#                     need_quantity = (vault_bank.quantity / vault_bank.minutes) * spacing_time.minute
#                     award_member_diamond = int(need_quantity)
#             else:
#                 award_member_diamond = int(vault_bank.quantity)
#
#             await update_diamond_reward(member.cid, SOURCE_MEMBER_DIAMOND_VAULT_REWARD, award_member_diamond)
#             member_diamond = member.diamond
#             member.diamond = member_diamond + award_member_diamond  # +金库奖励的钻石
#             member.updated_dt = datetime.datetime.now()
#             await member.save()
#
#             r_dict['remain_seconds'] = int(vault_bank.minutes) * 60  # 剩余奖励时间(初始化)
#             r_dict['total_seconds'] = int(vault_bank.minutes) * 60  # 总时间限制
#             r_dict['can_get_diamond'] = 0  # 可领取钻石（每次点击领取后初始化）
#             r_dict['total_diamond'] = vault_bank.quantity  # 总奖励数量
#             r_dict['member_diamond'] = member_diamond + award_member_diamond  # 用户所有的钻石数
#
#             r_dict['code'] = 1000
#         except Exception:
#             logger.error(traceback.format_exc())
#
#         return r_dict


class AppletFightRankingsGetHandler(WechatAppletHandler):
    """获取对战排行榜"""

    @decorators.render_json
    @decorators.wechat_applet_authenticated
    async def post(self):
        r_dict = {'code': 0}
        open_id = self.get_i_argument('open_id', None)
        try:
            if open_id:
                member = await find_member_by_open_id(open_id)
                if member:
                    rankings, my_ranking = await get_member_ranking_list(member)
                    r_dict['rankings'] = rankings
                    r_dict['my_ranking'] = my_ranking
                    r_dict['code'] = 1000
                else:
                    r_dict['code'] = 1002
            else:
                r_dict['code'] = 1001
        except Exception:
            logger.error(traceback.format_exc())

        return r_dict


class AppletFightFriendRankingsGetViewHandler(WechatAppletHandler):
    """
    获取好友排行榜
    """

    @decorators.render_json
    @decorators.wechat_applet_authenticated
    async def post(self):
        r_dict = {'code': 0}
        open_id = self.get_i_argument('open_id', None)
        try:
            if open_id:
                member = await find_member_by_open_id(open_id)
                if member:
                    member_friend_list = await MemberFriend.find(dict(member_cid=member.cid)).to_list(None)
                    member_friend_cid_list = [member_friend.friend_cid for member_friend in member_friend_list]
                    member_friend_cid_list.append(member.cid)
                    rankings, my_ranking = await get_member_ranking_list(member,
                                                                         q_member_cid_list=member_friend_cid_list)

                    r_dict['rankings'] = rankings
                    r_dict['my_ranking'] = my_ranking

                    r_dict['code'] = 1000
                else:
                    r_dict['code'] = 1002
            else:
                r_dict['code'] = 1001
        except Exception:
            logger.error(traceback.format_exc())
        return r_dict


class AppletFightAreaRankingsGet(WechatAppletHandler):
    """获取地区排行榜（市一级）"""

    @decorators.render_json
    @decorators.wechat_applet_authenticated
    async def post(self):
        r_dict = {'code': 0}
        open_id = self.get_i_argument('open_id', None)
        try:
            if open_id:
                member = await find_member_by_open_id(open_id)
                if not member:
                    r_dict['code'] = 1002
                    return r_dict

                rankings, my_ranking = await get_member_ranking_list(member, find_area=True)
                r_dict['rankings'] = rankings
                r_dict['my_ranking'] = my_ranking
                r_dict['code'] = 1000
            else:
                r_dict['code'] = 1001
        except Exception:
            logger.error(traceback.format_exc())

        return r_dict


class AppletFightPeriodRankingsGet(WechatAppletHandler):
    """获取周排行榜"""

    @decorators.render_json
    @decorators.wechat_applet_authenticated
    async def post(self):
        r_dict = {'code': 0}
        open_id = self.get_i_argument('open_id', None)
        period = int(self.get_i_argument('period', 0))
        try:
            if open_id:
                member = await find_member_by_open_id(open_id)
                if member:
                    rankings, my_ranking = await get_member_ranking_list(member, period, find_time=True)
                    r_dict['rankings'] = rankings
                    r_dict['my_ranking'] = my_ranking
                    r_dict['code'] = 1000
                else:
                    r_dict['code'] = 1002
            else:
                r_dict['code'] = 1001
        except Exception:
            logger.error(traceback.format_exc())

        return r_dict


class AppletFightLimitCheckHandler(WechatAppletHandler):
    """检查参与排位赛次数"""

    @decorators.render_json
    @decorators.wechat_applet_authenticated
    async def post(self):
        r_dict = {'code': 0}
        open_id = self.get_i_argument('open_id')
        if not open_id:
            return r_dict
        try:
            member = await find_member_by_open_id(open_id)
            value = get_cache_answer_limit(member.cid)
            r_dict['code'] = 1001 if ANSWER_LIMIT_NUMBER and value >= ANSWER_LIMIT_NUMBER else 1000
        except Exception:
            logger.error(traceback.format_exc())

        return r_dict


class AppletCertificateGetHandler(WechatAppletHandler):
    """获取毕业证书类型"""

    @decorators.render_json
    @decorators.wechat_applet_authenticated
    async def post(self):
        r_dict = {'code': 0}
        open_id = self.get_i_argument('open_id')
        if not open_id:
            r_dict['code'] = 1001
            return r_dict
        try:
            member = await find_member_by_open_id(open_id)
            if not member:
                r_dict['code'] = 1002
                return r_dict
            cert = await MemberExamCertificate.find_one({'member_cid': member.cid})
            if not cert:
                r_dict['code'] = 1005
            else:
                r_dict = {'code': 1000, 'category': cert.category,
                          'title': CATEGORY_EXAM_CERTIFICATE_DICT.get(cert.category),
                          'award_dt': cert.award_dt.strftime(u"%Y年%m月%d日")}
        except Exception:
            logger.error(traceback.format_exc())
        return r_dict


class AppletSubjectResolvingReviewHandler(WechatAppletHandler):
    """
    记录查看答案解析的次数
    """

    @decorators.render_json
    @decorators.wechat_applet_authenticated
    async def post(self):
        r_dict = {'code': 0}
        open_id = self.get_i_argument('open_id')
        wrong_count = self.get_i_argument('wrong_count')

        if not open_id:
            r_dict['code'] = 1001
            return r_dict

        try:
            member = await find_member_by_open_id(open_id)
            if not member:
                r_dict['code'] = 1002
                return r_dict

            # 保存查看答案解析历史
            if wrong_count is not None and int(wrong_count) >= 0:
                sr = SubjectResolvingViewedStatistics(member_cid=member.cid, wrong_count=int(wrong_count))
                sr.sex = member.sex
                sr.age_group = member.age_group
                sr.province_code = member.province_code
                sr.city_code = member.city_code
                sr.education = member.education
                await sr.save()
            r_dict['code'] = 1000
        except Exception:
            logger.error(traceback.format_exc())
        return r_dict


class AppletShareAwardHandler(WechatAppletHandler):
    """
    发放每日分享好友奖励
    """

    @decorators.render_json
    @decorators.wechat_applet_authenticated
    async def post(self):
        """

        :return:
        {
            "code": [整型]返回码,
            "diamonds_num": [整型]会员总钻石数量
            "award_title": [字符串]奖励名称(旧title)
            "award_diamonds": [整型]本次奖励钻石数
        }
        """
        r_dict = {'code': 0}
        open_id = self.get_i_argument('open_id', None)
        try:
            if not open_id:
                r_dict['code'] = 1001
                return r_dict

            member = await find_member_by_open_id(open_id)
            if not member:
                r_dict['code'] = 1002
                return r_dict

            reward_info = []
            share_times_limit = (await GameDiamondReward.find_one(
                {'source': SOURCE_MEMBER_DIAMOND_DAILY_SHARE_TIMES_LIMIT})).quantity
            value = get_cache_share_times(member.cid)
            if value < share_times_limit:
                end_datetime = datetime.datetime.now().replace(hour=23, minute=59, second=59, microsecond=999)
                current_datetime = datetime.datetime.now()
                timeout = (end_datetime - current_datetime).seconds
                # 分享奖励
                _, m_diamond = await do_diamond_reward(member, SOURCE_MEMBER_DIAMOND_DAILY_SHARE)
                # 设置更新已奖励次数
                set_cache_share_times(member.cid, timeout)
                if member.diamond is None:
                    member.diamond = m_diamond
                else:
                    member.diamond = member.diamond + m_diamond
                await member.save()
                reward_info = [{
                    'title': SOURCE_MEMBER_DIAMOND_DICT.get(SOURCE_MEMBER_DIAMOND_DAILY_SHARE),
                    'diamond_num': m_diamond
                }]
            # 用户的钻石
            r_dict['diamonds_num'] = member.diamond
            r_dict['reward_info'] = reward_info
            r_dict['code'] = 1000
        except Exception:
            logger.error(traceback.format_exc())
        return r_dict


class AppletFightFriendQuestionGetHandler(WechatAppletHandler):
    """
    获取对战好友题目信息
    """

    @decorators.render_json
    @decorators.wechat_applet_authenticated
    async def post(self):
        r_dict = {'code': 0}
        try:
            open_id = self.get_i_argument('open_id', None)
            opponent_open_id = self.get_i_argument('opponent_open_id', None)

            member = await find_member_by_open_id(open_id)
            opponent = await find_member_by_open_id(opponent_open_id)
            if not open_id or not opponent_open_id or not member or not opponent:
                r_dict['code'] = 1001
                return r_dict

            game_history = await MemberGameHistory.aggregate([
                MatchStage({'member_cid': opponent.cid, 'runaway_index': None}),
                SortStage([('dan_grade', DESC), ('created_dt', DESC)]),
                LimitStage(1)
            ]).to_list(1)

            if not game_history:
                # 还未进行过排位赛
                r_dict['code'] = 1005
                return r_dict

            game_history = game_history[0]
            history_subject_cid_dict = {result.get('subject_cid'): result for result in game_history.result}
            result_map = {
                result.get('subject_cid'): {
                    'remain_time': 20 - result.get('consume_time', 0),
                    'question_id': result.get('subject_cid'),
                    'option_id': result.get('selected_option_cid'),
                    'true_answer': result.get('true_answer'),
                    'score': result.get('score', 0)
                } for result in game_history.result
            }

            subject_list = await Subject.aggregate(stage_list=[
                MatchStage({'cid': {'$in': list(history_subject_cid_dict.keys())}}),
                LookupStage(SubjectOption, let={'cid': '$cid'},
                            pipeline=[{'$match': {'$expr': {'$and': [{'$eq': ['$subject_cid', '$$cid']}]}}},
                                      {'$sort': {'code': ASC}}], as_list_name='option_list'),
                LookupStage(UploadFiles, 'image_cid', 'cid', 'file_list')]).to_list(None)

            answers = []
            question_list = []
            for subject in subject_list:
                title_picture_url = ''
                if subject.file_list:
                    title_picture_url = '%s://%s%s%s%s' % (
                        SERVER_PROTOCOL, SERVER_HOST, STATIC_URL_PREFIX, 'files/', subject.file_list[0].title)

                dimension_dict = await convert_subject_dimension_dict(subject.dimension_dict)
                question = {
                    'id': subject.cid,
                    'title': subject.title,
                    'picture_url': title_picture_url,
                    'category_name': dimension_dict.get('学科部类').title,
                    'timeout': 20,
                    'difficulty_degree': '%s/5' % dimension_dict.get('题目难度').ordered,
                    'knowledge_first': KNOWLEDGE_FIRST_LEVEL_DICT.get(subject.knowledge_first),
                    'knowledge_second': KNOWLEDGE_SECOND_LEVEL_DICT.get(subject.knowledge_second),
                    'resolving': subject.resolving,
                    'option_list': [{
                        'id': opt.cid, 'title': opt.title, 'true_answer': opt.correct
                    } for opt in subject.option_list]
                }
                question_list.append(question)
                answers.append(result_map.get(subject.cid))

            r_dict = {
                'code': 1000,
                'question_list': question_list,
                'answers': answers
            }
        except Exception:
            logger.error(traceback.format_exc())

        return r_dict


URL_MAPPING_LIST = [
    url(r'/wechat/applet/fight/member/get/', AppletFightMemberGetHandler, name='wechat_applet_fight_member_get'),
    url(r'/wechat/applet/fight/questions/get/', AppletGameFightQuestionsGetViewHandler,
        name='wechat_applet_fight_questions_get'),
    url(r'/wechat/applet/fight/answers/save/', MiniappSubmitAnswersViewHandler,
        name='wechat_applet_fight_answers_save'),
    url(r'/wechat/applet/fight/limit/check/', AppletFightLimitCheckHandler, name='wechat_applet_fight_limit_check'),
    url(r'/wechat/applet/fight/dan_grade/list/', AppletFightDanGradeListHandler,
        name='wechat_applet_fight_dan_grade_list'),
    url(r'/wechat/applet/fight/rankings/get/', AppletFightRankingsGetHandler, name='wechat_applet_fight_rankings_get'),
    url(r'/wechat/applet/fight/friend/rankings/get/', AppletFightFriendRankingsGetViewHandler,
        name='wechat_applet_fight_friend_rankings_get'),
    url(r'/wechat/applet/fight/area/rankings/get/', AppletFightAreaRankingsGet,
        name='wechat_applet_fight_area_rankings_get'),
    url(r'/wechat/applet/fight/period/rankings/get/', AppletFightPeriodRankingsGet,
        name='wechat_applet_fight_period_rankings_get'),
    # url(r'/wechat/applet/vault_bank/award/', AppletVaultBankAwardHandler, name='wechat_applet_vault_bank_award'),
    url(r'/wechat/applet/certificate/get/', AppletCertificateGetHandler, name='wechat_applet_certificate_get'),
    url(r'/wechat/applet/subject_resolving/review/', AppletSubjectResolvingReviewHandler,
        name='wechat_applet_subject_resolving_review'),
    url(r'/wechat/applet/share/award/', AppletShareAwardHandler, name='wechat_applet_share_award'),
    url(r'/wechat/applet/fight/friend/questions/get/', AppletFightFriendQuestionGetHandler,
        name='wechat_applet_fight_friend_questions_get')
]
