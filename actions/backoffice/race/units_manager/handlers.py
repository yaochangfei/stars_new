import re
import traceback
from io import BytesIO

import xlrd
from actions.backoffice.race.utils import get_menu
from pymongo import UpdateOne
from tornado.web import url
from xlsxwriter import Workbook

from commons.page_utils import Paging
from db import STATUS_UNIT_MANAGER_ACTIVE, STATUS_UNIT_MANAGER_INACTIVE
from db.models import Company
from enums import PERMISSION_TYPE_MINIAPP_UNIT_MANAGER_MANAGEMENT
from logger import log_utils
from web import BaseHandler, decorators, datetime

logger = log_utils.get_logging()


class UnitManagerListViewHandler(BaseHandler):
    """
    单位管理的列表页
    """

    @decorators.render_template('backoffice/race/units_manager/list_view.html')
    @decorators.permission_required(PERMISSION_TYPE_MINIAPP_UNIT_MANAGER_MANAGEMENT)
    async def get(self):
        race_cid = self.get_argument('race_cid', '')
        menu_list = await get_menu(self, 'config', race_cid)
        query_params = {'record_flag': 1, 'race_cid': race_cid}
        title = self.get_argument('title', '')
        if title:
            query_params['title'] = {'$regex': title, '$options': 'i'}
        code = self.get_argument('code', '')
        if code:
            query_params['code'] = {'$regex': code, '$options': 'i'}

        per_page_quantity = int(self.get_argument('per_page_quantity', 10))
        to_page_num = int(self.get_argument('page', 1))
        page_url = '%s?race_cid=%s&page=$page&per_page_quantity=%s&title=%s&code=%s' % (
            self.reverse_url("backoffice_race_unit_manager_list"), race_cid, per_page_quantity, title, code)
        paging = Paging(page_url, Company, current_page=to_page_num,
                        items_per_page=per_page_quantity,
                        sort=['created_dt'], **query_params)
        await paging.pager()
        return locals()


class UnitManagerAddViewHandler(BaseHandler):
    """
    新增单位
    """

    @decorators.render_template('backoffice/race/units_manager/add_view.html')
    @decorators.permission_required(PERMISSION_TYPE_MINIAPP_UNIT_MANAGER_MANAGEMENT)
    async def get(self):
        race_cid = self.get_argument('race_cid', '')
        menu_list = await get_menu(self, 'config', race_cid)
        return locals()

    @decorators.render_json
    @decorators.permission_required(PERMISSION_TYPE_MINIAPP_UNIT_MANAGER_MANAGEMENT)
    async def post(self):
        r_dict = {'code': 0}
        race_cid = self.get_argument('race_cid', '')
        unit_id = None
        try:
            title = self.get_argument('title', None)
            status = self.get_argument('status', None)  # 状态
            code = self.get_argument('code', None)
            if title and code:
                unit_count = await Company.count(dict(record_flag=1, code=code, race_cid=race_cid))
                if unit_count > 0:
                    r_dict['code'] = -3
                else:
                    if status == 'on':
                        status = STATUS_UNIT_MANAGER_ACTIVE
                    else:
                        status = STATUS_UNIT_MANAGER_INACTIVE
                    unit = Company(title=title, code=code)
                    unit.race_cid = race_cid
                    unit.status = status
                    unit.created_dt = datetime.datetime.now()
                    unit.updated_id = self.current_user.oid
                    unit_id = await unit.save()
                    r_dict['code'] = 1
            else:
                if not title:
                    r_dict['code'] = -1
                if not code:
                    r_dict['code'] = -2
        except Exception:
            #  如果因为网络问题等其他问题导致前端展示添加不正确但是数据已经保存到数据库了,应该删除掉
            if unit_id:
                await Company.delete_by_ids([unit_id])
            logger.error(traceback.format_exc())
        return r_dict


class UnitManagerEditViewHandler(BaseHandler):
    """
    单位编辑
    """

    @decorators.render_template('backoffice/race/units_manager/edit_view.html')
    @decorators.permission_required(PERMISSION_TYPE_MINIAPP_UNIT_MANAGER_MANAGEMENT)
    async def get(self, unit_cid):
        race_cid = self.get_argument('race_cid', '')
        menu_list = await get_menu(self, 'config', race_cid)
        if race_cid and unit_cid:
            unit = await Company.find_one(
                filtered={'cid': unit_cid, 'record_flag': 1})
        return locals()

    @decorators.render_json
    @decorators.permission_required(PERMISSION_TYPE_MINIAPP_UNIT_MANAGER_MANAGEMENT)
    async def post(self, unit_cid):
        race_cid = self.get_argument('race_cid', '')
        r_dict = {'code': 0}
        try:
            if race_cid and unit_cid:
                unit = await Company.find_one(filtered={'cid': unit_cid, 'record_flag': 1})
                title = self.get_argument('title', None)
                status = self.get_argument('status', None)  # 状态
                code = self.get_argument('code', None)
                if unit and title and code:
                    unit_count = await Company.count(dict(code=code, race_cid=race_cid, cid={'$ne': unit_cid}))
                    if unit_count > 0:
                        r_dict['code'] = -3
                    else:
                        if status == 'on':
                            status = STATUS_UNIT_MANAGER_ACTIVE
                        else:
                            status = STATUS_UNIT_MANAGER_INACTIVE
                        unit.title = title
                        unit.code = code
                        unit.status = status
                        unit.updated_dt = datetime.datetime.now()
                        unit.updated_id = self.current_user.oid
                        await unit.save()
                        r_dict['code'] = 1
                else:
                    if not title:
                        r_dict['code'] = -1
                    if not code:
                        r_dict['code'] = -2
        except Exception:
            logger.error(traceback.format_exc())
        return r_dict


class UnitManagerStatusSwitchViewHandler(BaseHandler):
    """
    改变单位状态
    """

    @decorators.render_json
    @decorators.permission_required(PERMISSION_TYPE_MINIAPP_UNIT_MANAGER_MANAGEMENT)
    async def post(self, unit_cid):
        race_cid = self.get_argument('race_cid', '')
        r_dict = {'code': 0}
        try:
            if race_cid and unit_cid:
                status = self.get_argument('status', False)
                if status == 'true':
                    status = STATUS_UNIT_MANAGER_ACTIVE
                else:
                    status = STATUS_UNIT_MANAGER_INACTIVE
                unit = await Company.find_one(
                    filtered={'cid': unit_cid, 'record_flag': 1})
                if unit:
                    unit.status = status
                    unit.updated_dt = datetime.datetime.now()
                    unit.updated_id = self.current_user.oid
                    await unit.save()
                r_dict['code'] = 1
        except Exception:
            logger.error(traceback.format_exc())
        return r_dict


class UnitManagerBatchOperateViewHandler(BaseHandler):
    """
    批量改变单位状态
    """

    @decorators.render_json
    @decorators.permission_required(PERMISSION_TYPE_MINIAPP_UNIT_MANAGER_MANAGEMENT)
    async def post(self):
        race_cid = self.get_argument('race_cid', '')
        r_dict = {'code': 0}
        try:
            unit_cid_list = self.get_body_arguments('unit_cid_list[]', [])
            if race_cid and unit_cid_list:
                operate = self.get_argument('operate', None)
                if operate is not None:
                    if int(operate) == 1:
                        update_requests = []
                        for unit_cid in unit_cid_list:
                            update_requests.append(UpdateOne({'cid': unit_cid},
                                                             {'$set': {'status': STATUS_UNIT_MANAGER_ACTIVE,
                                                                       'updated_dt': datetime.datetime.now(),
                                                                       'updated_id': self.current_user.oid}}))
                        await Company.update_many(update_requests)
                    elif int(operate) == 0:
                        update_requests = []
                        for unit_cid in unit_cid_list:
                            update_requests.append(UpdateOne({'cid': unit_cid},
                                                             {'$set': {
                                                                 'status': STATUS_UNIT_MANAGER_INACTIVE,
                                                                 'updated_dt': datetime.datetime.now(),
                                                                 'updated_id': self.current_user.oid}}))
                        await Company.update_many(update_requests)
                    elif int(operate) == -1:
                        await Company.delete_many({'cid': {'$in': unit_cid_list}})
                    r_dict['code'] = 1
        except Exception:
            logger.error(traceback.format_exc())
        return r_dict


class UnitManagerDeleteViewHandler(BaseHandler):
    """
    删除单位
    """

    @decorators.render_json
    @decorators.permission_required(PERMISSION_TYPE_MINIAPP_UNIT_MANAGER_MANAGEMENT)
    async def post(self, unit_cid):
        race_cid = self.get_argument('race_cid', '')
        r_dict = {'code': 0}
        try:
            if race_cid and unit_cid:
                unit = await Company.find_one(
                    filtered={'cid': unit_cid, 'record_flag': 1})
                await unit.delete()
                r_dict['code'] = 1
        except Exception:
            logger.error(traceback.format_exc())
        return r_dict


class UnitImportViewHandler(BaseHandler):
    """
    单位导入
    """

    @decorators.permission_required(PERMISSION_TYPE_MINIAPP_UNIT_MANAGER_MANAGEMENT)
    @decorators.render_template('backoffice/race/units_manager/upload_view.html')
    async def get(self):
        race_cid = self.get_argument('race_cid', '')
        menu_list = await get_menu(self, 'config', race_cid)
        return locals()

    @decorators.permission_required(PERMISSION_TYPE_MINIAPP_UNIT_MANAGER_MANAGEMENT)
    @decorators.render_json
    async def post(self):
        r_dict = {'code': 0}
        race_cid = self.get_argument('race_cid', '')
        try:
            if race_cid and self.request.files:
                import_files_meta = self.request.files['file']
                if import_files_meta:
                    code = await self.__subject_import_excel(race_cid, import_files_meta[0]['body'])
                    r_dict['code'] = code
        except RuntimeError:
            logger.error(traceback.format_exc())
        return r_dict

    async def __subject_import_excel(self, race_cid, excel_file_content):
        result_code = 1
        #  所有单位的编号
        unit_code_list = await Company.distinct('code', {'race_cid': race_cid, 'record_flag': 1})
        book = xlrd.open_workbook(file_contents=excel_file_content)
        #  获得第一个表的信息
        sheet = book.sheet_by_index(0)
        unit_list = []
        row_list = []

        title_list = []
        for ind, col in enumerate(sheet.row_values(0)):
            if col:
                title_list.append(col)
        # 判断表头是否正确
        if len(title_list) != 2:
            result_code = 2
            return result_code
        # 拿到所有的行数据
        for rownum in range(1, sheet.nrows):
            row_list.append([col for col in sheet.row_values(rownum)])
        #  上传文件中有一些已经存在过的，需要删除，重新覆盖
        delete_unit_oid_list = []
        if row_list:
            for i, row_data in enumerate(row_list):
                code_repeat = False
                # 单位编码
                unit_code = str(self.__get_replace_data(row_data[0], 2))
                #  单位编码不能超过16位
                if not unit_code or len(unit_code) > 16:
                    continue
                else:
                    reg = re.compile(r'^[a-zA-Z0-9]*$')
                    if not bool(reg.match(unit_code)):
                        continue
                    if unit_code in unit_code_list:
                        unit = await Company.find_one(dict(code=unit_code))
                        #  上传文件中有编码重复的行，只添加一个
                        if unit:
                            delete_unit_oid_list.append(unit.oid)
                            await unit.delete()
                        else:
                            code_repeat = True
                    unit = Company()
                    unit.race_cid = race_cid
                    unit.code = unit_code
                    unit.title = str(row_data[1])[:-2] if not isinstance(row_data[1], str) else row_data[1]
                    unit.status = STATUS_UNIT_MANAGER_ACTIVE
                    unit_code_list.append(unit_code)
                if not code_repeat:
                    unit_list.append(unit)
                    if len(unit_list) == 500:
                        await  Company.insert_many(unit_list)
                        unit_list = []
            if unit_list:
                await Company.insert_many(unit_list)
                await Company.delete_by_ids(delete_unit_oid_list)
        return result_code

    def __get_replace_data(self, data, data_type, data_dict=None):
        if not data:
            return None
        if isinstance(data, float):
            data = int(data)
            data = str(data)
        if isinstance(data, str):
            data = data.replace('\n', '').replace(' ', '')
        if data_type == 1:
            if not data_dict.get(data):
                return None
            else:
                return data_dict.get(data)
        else:
            return data


class UnitDownloadTemplatetViewHandler(BaseHandler):
    @decorators.permission_required(PERMISSION_TYPE_MINIAPP_UNIT_MANAGER_MANAGEMENT)
    async def get(self):
        try:
            # 根据需求生成excel模板
            filename = 'unit_template_%s.xlsx' % datetime.datetime.now().strftime('%Y%m%d%H%M')
            sheet_name1 = '单位导入模板'
            options = {'sheet_name1': sheet_name1}
            first_column_list = self.__get_column_list()
            work_book = self.__create_common_excel(first_column_list, options=options)

            self.set_header('Content-Type', 'application/vnd.openxmlformats-officedocument.spreadsheetml.sheet')
            self.set_header('Content-Disposition', 'attachment; filename=' + filename)
            self.write(work_book)
            self.finish()
        except Exception as e:
            logger.error(str(e))

    def __get_column_list(self):
        """
        拼接列名
        :return:
        """
        column_list_start = [u'单位编号', u'单位名称']
        return column_list_start

    def __create_common_excel(self, first_column_list, options={}):
        """
        生成excel 模板
        :param first_column_list: 单位列名
        :param options:
        :return:
        """
        output = BytesIO()
        workbook = Workbook(output, {'in_memory': True})
        # sheet 1名称
        worksheet_subject = workbook.add_worksheet(options['sheet_name1'] if 'sheet_name1' in options else None)
        line_index = 0  # 起始line
        first_column_num = len(first_column_list)  # 列总数
        worksheet_subject.set_column(0, first_column_num - 1, 14)
        column_format = workbook.add_format({'bold': '1', 'valign': 'vcenter', 'align': 'center',
                                             'font_name': 'Microsoft YaHei'})
        worksheet_subject.set_row(line_index, 20, column_format)
        for index, column in enumerate(first_column_list):
            worksheet_subject.write_string(line_index, index, column, column_format)
        workbook.close()
        return output.getvalue()


URL_MAPPING_LIST = [
    url(r'/backoffice/race/unit/manager/list/', UnitManagerListViewHandler,
        name='backoffice_race_unit_manager_list'),
    url(r'/backoffice/race/unit/manager/add/', UnitManagerAddViewHandler,
        name='backoffice_race_unit_manager_add'),
    url(r'/backoffice/race/unit/manager/edit/([0-9a-zA-Z_]+)/', UnitManagerEditViewHandler,
        name='backoffice_race_unit_manager_edit'),
    url(r'/backoffice/race/unit/manager/status/switch/([0-9a-zA-Z_]+)/', UnitManagerStatusSwitchViewHandler,
        name='backoffice_race_unit_manager_status_switch'),
    url(r'/backoffice/race/unit/manager/batch_operate/', UnitManagerBatchOperateViewHandler,
        name='backoffice_race_unit_manager_batch_operate'),
    url(r'/backoffice/race/unit/manager/delete/([0-9a-zA-Z_]+)/', UnitManagerDeleteViewHandler,
        name='backoffice_race_unit_manager_delete'),
    url(r'/backoffice/race/unit/manager/import/', UnitImportViewHandler,
        name='backoffice_race_unit_manager_import'),
    url(r'/backoffice/race/unit/manager/download/', UnitDownloadTemplatetViewHandler,
        name='backoffice_race_unit_manager_download'),
]
