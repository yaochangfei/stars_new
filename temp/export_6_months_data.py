from datetime import datetime

from commons.common_utils import datetime2str
from db import SEX_DICT, TYPE_AGE_GROUP_DICT, TYPE_EDUCATION_DICT
from db.models import MemberGameHistory, Member, AdministrativeDivision
from pymongo import ReadPreference
from xlsxwriter import Workbook

six_month_ago = datetime.now().replace(year=2018, month=10, day=1, hour=0, minute=0, second=0, microsecond=0)
cursor = MemberGameHistory.sync_find({'created_dt': {'$gte': six_month_ago}}, read_preference=ReadPreference.PRIMARY)

workbook = Workbook('近6个月的游戏数据.xlsx')
worksheet = workbook.add_worksheet()
menu = ['序号', '昵称', '性别', '年龄段', '受教育程度', '省份', '城市', '总题数', '答对题目数量', '答题时间']
for index, m in enumerate(menu):
    worksheet.write_string(0, index, m)

post_code_map = {}
row = 0
while True:
    row += 1
    try:
        history = cursor.next()
        worksheet.write_number(row, 0, row)

        member = Member.sync_get_by_cid(history.member_cid)
        if not member:
            continue
        worksheet.write_string(row, 1, member.nick_name if member else '-')
        worksheet.write_string(row, 2, SEX_DICT.get(member.sex) if member else '-')
        worksheet.write_string(row, 3, TYPE_AGE_GROUP_DICT.get(member.age_group) if member else '-')
        worksheet.write_string(row, 4, TYPE_EDUCATION_DICT.get(member.education) if member else '-')

        prov = city = '-'
        if member.province_code and member.city_code:
            if member.province_code in post_code_map:
                prov = post_code_map[member.province_code]
            else:
                prov = AdministrativeDivision.sync_find_one({'code': member.province_code}).title

            if member.city_code in post_code_map:
                city = post_code_map[member.city_code]
            else:
                city = AdministrativeDivision.sync_find_one({'code': member.city_code}).title

            post_code_map[member.province_code] = prov
            post_code_map[member.city_code] = city

        worksheet.write_string(row, 5, prov)
        worksheet.write_string(row, 6, city)
        worksheet.write_number(row, 7, len(history.result))

        correct_count = 0
        for r in history.result:
            if r.get('true_answer'):
                correct_count += 1
        worksheet.write_number(row, 8, correct_count)
        worksheet.write_string(row, 9, datetime2str(history.created_dt))

    except StopIteration:
        break

workbook.close()
