def deal_with_data_excel(date_list, top_five_data_list):
    data, province_and_city_dict = {}, {}

    for index, date in enumerate(date_list):
        for ti, data_list in enumerate(top_five_data_list):
            name = data_list[index].get('name')
            value = data_list[index].get('value')
            if name:
                name_list = name.split(' ')
                if name_list:
                    province, city = name_list[0], name_list[1]
                    data['%s%s' % (city + ' ', date)] = value

                    if not province_and_city_dict.get(province):
                        province_and_city_dict[province] = {}
                    if not province_and_city_dict[province].get(city):
                        province_and_city_dict[province][city] = {}
                    province_and_city_dict[province][city][date] = (list(province_and_city_dict[province].keys()).index(city), index, value)

    return data, province_and_city_dict
