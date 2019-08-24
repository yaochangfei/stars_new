from db.models import ReportRacePeopleStatistics, RaceMapping, Race
from motorengine.stages import MatchStage, LookupStage, ProjectStage
from motorengine.stages.group_stage import GroupStage


async def get_report_data(race: Race, sort_stage, time_match_stage, category, belong_city_district_title_list = []):
    """
    获得活动报表数据
    :param race:
    :param sort_stage:
    :param category:
    :param time_match_stage
    :param belong_city_district_title_list
    :return:
    """
    title_list = []
    accuracy_series_data_list = []
    member_count_dict = {}
    member_quantity_dict = {}
    member_accuracy_dict = {}
    if race:
        #  参与人次
        match_stage = MatchStage({'race_cid': race.cid, 'record_flag': 1})
        stage_list = [match_stage, time_match_stage]
        if belong_city_district_title_list:
            stage_list.append(MatchStage({'district': {'$in': belong_city_district_title_list}}))
        group_stage = GroupStage(category, sum={'$sum': "$total_num"})
        stage_list += [group_stage, sort_stage]
        stats = await ReportRacePeopleStatistics.aggregate(stage_list).to_list(None)
        series_data_list = [s.sum for s in stats]
        title_list = [s.id for s in stats if s]
        #  {'苏州': 200, '扬州': 300}
        if title_list and series_data_list:
            member_count_dict = {title: data for title, data in zip(title_list, series_data_list)}
            member_count_dict = delete_other(member_count_dict)
            title_list = list(member_count_dict.keys())
        #  参加人数
        group_stage = GroupStage('auth_address.%s' % category, sum={'$sum': 1})
        if belong_city_district_title_list:
            participants_stats = await RaceMapping.aggregate(
                stage_list=[match_stage, time_match_stage, MatchStage({'auth_address.district': {'$in': belong_city_district_title_list}}),group_stage]).to_list(None)
        else:
            participants_stats = await RaceMapping.aggregate(
                stage_list=[match_stage, time_match_stage, group_stage]).to_list(None)
        quantity_title_list = [s.id for s in participants_stats]
        quantity_data_list = [s.sum for s in participants_stats]
        if quantity_title_list and quantity_data_list:
            member_quantity_dict = {title: data for title, data in zip(quantity_title_list, quantity_data_list)}
            member_quantity_dict = delete_other(member_quantity_dict)
        #  正确率
        participants_accuracy = GroupStage('auth_address.%s' % category,
                                           total_correct={'$sum': '$total_correct'},
                                           total_count={'$sum': '$total_count'})
        if belong_city_district_title_list:
            accuracy_stats = await RaceMapping.aggregate(
                stage_list=[match_stage, time_match_stage,
                            MatchStage({'auth_address.district': {'$in': belong_city_district_title_list}}),
                            participants_accuracy]).to_list(None)
        else:
            accuracy_stats = await RaceMapping.aggregate(
                stage_list=[match_stage, time_match_stage, participants_accuracy]).to_list(None)
        for s in accuracy_stats:
            if s and s.total_count == 0:
                accuracy_series_data_list.append(0)
            elif s and s.total_count != 0:
                accuracy_series_data_list.append(round((s.total_correct / s.total_count) * 100, 2))
        accuracy_title_list = [s.id for s in accuracy_stats if s]
        member_accuracy_dict = {title: data for title, data in zip(accuracy_title_list, accuracy_series_data_list)}
        member_accuracy_dict = delete_other(member_accuracy_dict)
    return title_list, member_count_dict, member_quantity_dict, member_accuracy_dict


def delete_other(title_dict):
    """
    把None给删除
    :param title_dict:
    :return:
    """
    if None in title_dict:
        del title_dict[None]
    return title_dict