#! /usr/bin/python
# -*- coding: utf-8 -*-
"""
将excel中行政区划信息转为json文件
民政部行政区划信息：http://www.mca.gov.cn/article/sj/xzqh//1980/


"""
import copy
import json
import time

from pypinyin import lazy_pinyin

import requests
import xlrd
from logger import log_utils

logger = log_utils.get_logging('gene_ad.log')


def gene_json():
    workbook = xlrd.open_workbook(filename='./ad.xlsx')
    sheet = workbook.sheet_by_index(0)

    ad_list = []
    location_list = []
    for _row in range(sheet.nrows):
        if _row < 1:
            continue
        code = str(int(sheet.cell_value(_row, 0)))
        name = sheet.cell_value(_row, 1)
        lng, lat, lev, auth_address = parse_location(name)
        if not (lng and lat and lev and auth_address):
            continue

        _ad_dict = {
            'code': code,
            'name': name,
            'cell': [],
            'en_name': ''.join(lazy_pinyin(name))
        }
        # if lev == 1:
        #     # 城市
        #     parent_name = auth_address.get('province')
        #     for _ad in ad_list:
        #         if _ad.get('name') == parent_name:
        #
        #     ad_list.append(_ad_dict)
        if lev == 2:
            # 区县
            parent_name = auth_address.get('city')
            location_list.append([name, lng, lat, parent_name])

    print(location_list)


def parse_location(address: str):
    """

    :param address:
    :return:
    """
    url = "https://apis.map.qq.com/ws/geocoder/v1/"
    res = requests.get(url, {'address': address, 'output': 'json', 'key': "DH2BZ-ZXC66-A2JS2-EGAPA-OZLWE-VPFCD"})

    try:
        res_json = res.json()
        lng = res_json.get('result').get('location').get('lng')
        lat = res_json.get('result').get('location').get('lat')
        level = res_json.get('result').get('level')
        auth_address = res_json.get('result').get('address_components')
    except AttributeError:
        print("not find. address: %s, res: %s" % (address, res_json))
        return None, None, None, None
    return lng, lat, level, auth_address


class struct_ad(object):
    code = None
    name = None
    en_name = None
    lng = None
    lat = None
    level = None
    cell = []

    def get_struct(self):
        return


def get_provinces():
    url = 'https://apis.map.qq.com/ws/district/v1/list?key=DH2BZ-ZXC66-A2JS2-EGAPA-OZLWE-VPFCD'
    res = requests.get(url).json()
    with open('./origin.json', 'w') as f:
        f.write(json.dumps(res))

    return res.get('result', [])


def get_citys(code):
    city_list = []
    url = 'https://apis.map.qq.com/ws/district/v1/getchildren?id=%s&key=DH2BZ-ZXC66-A2JS2-EGAPA-OZLWE-VPFCD' % code
    res = requests.get(url).json()
    res = res.get('result', [])[0]
    for city in res:
        city = format_ad(city)
        city['level'] = 'C'

        sub = False
        if city['code'] == '341500':
            sub = True
        city['cell'] = get_dists(city['code'], sub)
        city_list.append(city)

    time.sleep(0.2)
    return city_list


def get_dists(code, sub=False):
    dists_list = []
    url = 'https://apis.map.qq.com/ws/district/v1/getchildren?id=%s&key=DH2BZ-ZXC66-A2JS2-EGAPA-OZLWE-VPFCD' % code
    res = requests.get(url).json()
    res = res.get('result', [])[0]
    for dists in res:
        dists = format_ad(dists)
        dists['level'] = 'D'
        if sub:
            dists['cell'] = get_towns(dists['code'])
        dists_list.append(dists)
    time.sleep(0.2)
    return dists_list


def get_towns(code):
    towns_list = []
    url = 'https://apis.map.qq.com/ws/district/v1/getchildren?id=%s&key=DH2BZ-ZXC66-A2JS2-EGAPA-OZLWE-VPFCD' % code
    res = requests.get(url).json()
    res = res.get('result', [])[0]
    for dists in res:
        dists = format_ad(dists)
        dists['level'] = 'T'
        if 'cell' in dists:
            del dists['cell']
        towns_list.append(dists)
    time.sleep(0.2)
    return towns_list


def format_ad(prov):
    prov['code'] = prov['id']
    prov['name'] = prov['fullname']
    prov['en_name'] = ''.join(prov.get('pinyin', lazy_pinyin(prov['name'])))
    del prov['id']
    del prov['fullname']
    if 'pinyin' in prov:
        del prov['pinyin']

    if 'cidx' in prov:
        del prov['cidx']

    return prov


def init():
    ad_list = []
    ret = get_provinces()
    prov_list = ret[0]

    with open('./city.json', 'w', encoding='utf-8') as f:
        city_json = json.dumps(ret[1], ensure_ascii=False)
        f.write(city_json)

    with open('./dist.json', 'w', encoding='utf-8') as f:
        dist_list = json.dumps(ret[2], ensure_ascii=False)
        f.write(dist_list)

    try:
        for index, prov in enumerate(prov_list):
            print('has generate', index)
            prov = format_ad(prov)
            prov['level'] = 'P'
            if prov['code'] in ['110000', '120000', '310000', '500000', '810000', '820000']:
                temp_prov = copy.deepcopy(prov)
                temp_prov['cell'] = get_dists(prov['code'])
                temp_prov['level'] = 'C'
                _code = list(temp_prov['code'])
                _code[3] = '1'
                temp_prov['code'] = ''.join(_code)
                prov['cell'] = [temp_prov]
            else:
                prov['cell'] = get_citys(prov['code'])
            ad_list.append(prov)
    except Exception as e:
        print(str(e))

    print(ad_list)
    info = {'division': ad_list}
    ad_json = json.dumps(info, ensure_ascii=False)
    with open('./ad.json', 'w', encoding='utf-8') as f:
        f.write(ad_json)


init()
