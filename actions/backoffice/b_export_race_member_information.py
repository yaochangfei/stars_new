# !/usr/bin/python
# -*- coding:utf-8 -*-
import traceback

from io import BytesIO
from urllib.parse import quote

from tornado.web import url
from xlsxwriter import Workbook

from db import TYPE_EDUCATION_DICT, CATEGORY_MEMBER_DICT, TYPE_AGE_GROUP_DICT, SEX_DICT
from db.models import Race, Member, Company, RaceMapping
from enums import PERMISSION_TYPE_REPORT_EXECUTIVE_DIRECT_MANAGEMENT
from logger import log_utils
from motorengine.stages import MatchStage, LookupStage
from web import BaseHandler, decorators

logger = log_utils.get_logging()


class RaceMemberInformationHandler(BaseHandler):
    """
    活动参与人员信息导出模块
    """

    @decorators.permission_required(PERMISSION_TYPE_REPORT_EXECUTIVE_DIRECT_MANAGEMENT)
    @decorators.render_json
    async def get(self):
        race_cid = self.get_argument('race_cid', '')
        if not race_cid:
            return dict(code=-1)
        race = await Race.find_one(dict(cid=race_cid))
        if not race:
            return dict(code=-2)
        self.__export_race_member_information(race_cid, race.title)

    def __export_race_member_information(self, race_cid: str, race_title: str):
        try:
            filename = '%s会员信息' % race_title
            output = BytesIO()
            self.__generate_workbook(output, race_cid, race_title)
            self.set_header('Content-Type', 'application/vnd.openxmlformats-officedocument.spreadsheetml.sheet')
            self.set_header('Content-Disposition',
                            "attachment;filename*=utf-8''{}.xlsx".format(quote(filename.encode('utf-8'))))
            self.write(output.getvalue())
            self.finish()
        except Exception:
            logger.error(traceback.format_exc())

    def __generate_workbook(self, output, race_cid: str, race_title: str):
        """
        生成活动会员信息excel，
        包含微信昵称、性别、手机号、教育程度、群体、年龄段、授权的地理信息、公司
        :param race_cid:竞赛ID
        :return: excel
        """
        # 根据竞赛ID查询竞赛与会员的映射记录
        match_stage = MatchStage({'race_cid': race_cid, 'record_flag': 1})
        # 关联会员表
        lookup_stage_member = LookupStage(Member, 'member_cid', 'cid', 'member_list')
        # 关联公司表
        lookup_stage_company = LookupStage(Company, 'company_cid', 'cid', 'company_list')
        # 竞赛会员映射结果
        race_mapping_cursor = RaceMapping.sync_aggregate([match_stage, lookup_stage_member, lookup_stage_company])

        # excel格式
        workbook = Workbook(output, {'in_memory': True})
        sheet = workbook.add_worksheet('%s会员信息' % race_title)
        data_center_format = workbook.add_format(
            {'valign': 'vcenter', 'align': 'center', 'font_name': 'Microsoft YaHei', 'border': 1})
        excel_header_fields = ['昵称', '性别', '手机号', '教育程度', '群体', '年龄段', '授权的地理信息', '公司']
        for index, field in enumerate(excel_header_fields):
            sheet.write_string(0, index, field)
        col = 1
        while True:
            try:
                race_mapping = race_mapping_cursor.next()
                if race_mapping:
                    if race_mapping.member_list:
                        member = race_mapping.member_list[0]
                        sheet.write_string(col, 0, member.nick_name, data_center_format)
                        sheet.write_string(col, 1, SEX_DICT[member.sex], data_center_format)
                        sheet.write_string(col, 2, race_mapping.mobile if race_mapping.mobile else '',
                                           data_center_format)
                        sheet.write_string(col, 3, TYPE_EDUCATION_DICT[getattr(member, 'education', 4)],
                                           data_center_format)
                        sheet.write_string(col, 4, CATEGORY_MEMBER_DICT[getattr(member, 'category', 5)],
                                           data_center_format)
                        sheet.write_string(col, 5, TYPE_AGE_GROUP_DICT[getattr(member, 'age_group', 1)],
                                           data_center_format)
                        sheet.write_string(col, 6, ''.join(list(race_mapping.auth_address.values())),
                                           data_center_format)
                        if len(race_mapping.company_list):
                            sheet.write_string(col, 7, getattr(race_mapping.company_list[0], 'title', ''),
                                               data_center_format)
                        col += 1
                else:
                    continue
            except StopIteration:
                break
        workbook.close()


URL_MAPPING_LIST = [
    url(r'/backoffice/reports/race/member/export/excel/', RaceMemberInformationHandler,
        name='backoffice_race_member_export_excel')
]
