from db.models import Member, Race, AdministrativeDivision


async def check_enter_race(member: Member, race_cid: str):
    """
    加固接口，防止不是本活动的用户加入到本活动中
    :param member:
    :param race_cid:
    :return:
    """
    r_dict = {'code': 0, 'enter_race': True}
    race = await Race.find_one({'cid': race_cid, 'record_flag': 1})
    #  省级活动
    if race.province_code and not race.city_code:
        prov = await AdministrativeDivision.find_one({'code': race.province_code, 'parent_code': None})
        #  如果用户的授权省份和活动的省份不一样，不让其进入活动
        if member.auth_address.get('province') != prov.title:
            r_dict['code'] = 1000
            r_dict['enter_race'] = False
    #  市级活动
    elif race.province_code and race.city_code:
        prov = await AdministrativeDivision.find_one({'code': race.province_code, 'parent_code': {'$eq': None}})
        city = await AdministrativeDivision.find_one({'code': race.city_code, 'parent_code': {'$ne': None}})
        if member.auth_address.get('province') != prov.title or member.auth_address.get('city') != city.title:
            r_dict['code'] = 1000
            r_dict['enter_race'] = False

    return r_dict

