# !/usr/bin/python
# -*- coding:utf-8 -*-


from commons.exception import AdministrationNotMatchError
from db.models import AdministrativeDivision


async def get_matched_division_2_dict(province_name: str = None, city_name: str = None,
                                      district_name: str = None) -> dict:
    """
    匹配除完整的行政区划信息，字典形式
    :param province_name: 省份名字（中或英）
    :param city_name: 城市名字（中或英）
    :param district_name: 区域名字（中或英）
    :return:
    """
    match_list = ['北京', '北京市', 'beijing', 'beijing city', '天津', '天津市', 'tianjin', 'tianjin city', '上海', '上海市',
                  'shanghai', 'shanghai city', '重庆', '重庆市', 'chongqing', 'chongqing city']
    if not province_name and city_name and city_name.lower() in match_list:
        province_name = city_name
    if province_name and not city_name and province_name.lower() in match_list:
        city_name = province_name
    division_dict = {}
    division_list = await get_matched_division(province_name, city_name, district_name)
    if division_list:
        for division in division_list:
            if division:
                level = division.get('level')
                if level:
                    division_dict[level] = {}
                    division_dict[level]['code'] = division.get('code')
                    division_dict[level]['title'] = division.get('title')
                    division_dict[level]['en_title'] = division.get('en_title')
    return division_dict


async def get_matched_division(province_name: str = None, city_name: str = None, district_name: str = None) -> list:
    """
    匹配除完整的行政区划信息
    :param province_name: 省份名字（中或英）
    :param city_name: 城市名字（中或英）
    :param district_name: 区域名字（中或英）
    :return:
    """
    if not province_name or not city_name:
        raise ValueError('"province_name", "city_name", must not be None')

    ad_list = []
    prov = await AdministrativeDivision.find_one(_do_create_division_match('P', province_name))
    city_match = _do_create_division_match('C', city_name)
    if prov:
        ad_list.append(prov)
        city_match.update({'parent_code': prov.code})

    city = await AdministrativeDivision.find_one(city_match)

    district_match = _do_create_division_match('D', district_name)
    if city:
        ad_list.append(city)
        district_match.update({'parent_code': city.code})

    district = await AdministrativeDivision.find_one(district_match)
    if district:
        ad_list.append(district)

    return [
        dict(
            code=division.code,
            title=division.title,
            en_title=division.en_title,
            level=division.level
        ) for division in ad_list
    ]


async def perfect_division_list(division: AdministrativeDivision) -> list:
    """
    完善行政信息
    :param division:
    :return:
    """
    division_list = []
    if division:
        division_list.append(dict(
            code=division.code,
            title=division.title,
            en_title=division.en_title,
            level=division.level
        ))
        parent = await division.parent
        if parent:
            parent_division_list = await perfect_division_list(parent)
            if parent_division_list:
                division_list.extend(parent_division_list)
    return division_list


def _do_create_division_match(division_level, division_name, parent_code=None):
    """
    构建查询条件
    :param division_level: 行政区划级别
    :param division_name: 行政区划名称
    :param parent_code: 父级code，可选
    :return:
    """
    match = {
        'level': division_level,
        '$or': [
            {
                'title': {'$regex': '^%s' % division_name, '$options': '$i'}
            },
            {
                'en_title': {'$regex': '^%s' % division_name, '$options': '$i'}
            }
        ]
    }
    if parent_code:
        match['parent_code'] = parent_code
    return match
