from db import STATUS_ACTIVE, CATEGORY_REDPACKET_RULE_LOTTERY
from db.models import Race, RedPacketRule, RedPacketEntry, RedPacketBox, RedPacketBasicSetting, RedPacketItemSetting, \
    Member, RedPacketAwardHistory, RedPacketLotteryHistory, RaceGameCheckPoint
from motorengine import ASC
from motorengine.stages import MatchStage, SortStage

STATUS_REDPACKET_AWARDED = 0  # 已被领取
STATUS_REDPACKET_NOT_AWARDED = 1  # 还没有被领取
STATUS_REDPACKET_AWARDING = 2  # 奖励发放
STATUS_REDPACKET_AWARD_FAILED = 5  # 领取失败

# 活动
race_title = '2019扬州市迎新春科学素质大擂台'
race = Race.sync_find_one({'title': race_title})

# 关卡
checkpoint_list = RaceGameCheckPoint.sync_aggregate([
    MatchStage({'race_cid': race.cid}),
    SortStage([('index', ASC)])
]).to_list(None)

last_ck = checkpoint_list[-1]

# 红包规则
rule = RedPacketRule.sync_find_one({'race_cid': race.cid})
if not rule:
    rule = RedPacketRule()
rule.code = 'rule01'
rule.title = 'rule01'
rule.status = STATUS_ACTIVE
rule.race_cid = race.cid
rule.category = CATEGORY_REDPACKET_RULE_LOTTERY
rule_oid = rule.sync_save()

# 红包基础设置
basic = RedPacketBasicSetting.sync_find_one({'race_cid': race.cid})
basic.rule_cid = rule.cid
basic.sync_save()
# db.TBL_RED_PACKET_BASIC_SETTING.update({}, {$rename : {"expect_people_num" : "expect_num", "top_limit_each_day": "top_limit"}}, false, true)
settings = RedPacketItemSetting.sync_find({'race_cid': race.cid})
setting_map = {}
for s in settings:
    s.rule_cid = rule.cid
    setting_map[s.cid] = s
    s.sync_save()
# db.TBL_RED_PACKET_ITEM_SETTING.update({}, {$rename : {"count" : "quantity"}}, false, true)

# 奖池
for entry in RedPacketEntry.sync_find({'race_cid': race.cid}):
    item = setting_map[entry.award_cid]
    box = RedPacketBox()
    box.race_cid = race.cid
    box.rule_cid = rule.cid
    box.award_cid = entry.award_cid
    box.award_msg = item.message
    box.award_amount = item.amount

    if entry.open_id:
        member = Member.sync_find_one({'open_id': entry.open_id})
        box.member_cid = member.cid

    hist = RedPacketAwardHistory.sync_find_one({'race_cid': race.cid, 'award_cid': entry.cid, 'issue_status': {'$ne': 1}})
    if hist:
        box.draw_status = STATUS_REDPACKET_AWARDED
        box.draw_dt = hist.request_dt
        box.error_msg = hist.error_msg
        box.request_dt = hist.request_dt
        box.checkpoint_cid = last_ck.cid
    else:
        box.draw_status = STATUS_REDPACKET_AWARD_FAILED

    box.sync_save()

# 抽奖记录
for history in RedPacketLotteryHistory.sync_find({'race_cid': race.cid}):
    history.rule_cid = rule.cid
    history.checkpoint_cid = last_ck.cid
    history.sync_save()

