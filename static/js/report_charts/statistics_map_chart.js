var myChart = null;

function showMap(result_data, geoCoordMap, mapName, label_type_name) {
    var data_list = do_deal_result_data(result_data);
    var dealed_data = data_list[0];
    var city_list = data_list[1];
    var times_sum_dict = data_list[2];
    var times_sum = times_sum_dict[mapName];
    // if (label_type_name === "正确率") {
    //     times_sum_dict = get_province_city_accuracy(result_data);
    //     times_sum = times_sum_dict[mapName];
    // }
    if (mapName === "" || mapName == null || mapName === undefined || mapName !== 'china') {
        city_list = dealed_data[mapName];
    }
    var option = {};
    if (label_type_name === "正确率") {
        times_sum_dict = get_province_city_accuracy(result_data);
        times_sum = times_sum_dict[mapName];
        option = correct_rate_option(result_data, times_sum, mapName)
    } else {
        option = {
            backgroundColor: backgroundColor,
            title: {
                text: '公民参与科学素质学习累计',
                show: false
            },
            toolbox: {
                show: false,
                feature: {
                    saveAsImage: {}
                },
                right: 20
            },
            tooltip: {
                trigger: 'item',
                formatter: function (params) {
                    if (!params.value) {
                        return params.name;
                    }
                }
            },
            legend: {
                orient: 'horizontal',
                left: '30',
                bottom: '50',
                itemGap: -3,
                itemWidth: 8,
                itemHeight: 20,
                data: legend_data,
                textStyle: {
                    color: '#333'
                },
                formatter: function (name) {
                    return '';
                }
            },
            // visualMap: {
            //     min: 0,
            //     max: 200,
            //     calculable: true,
            //     inRange: {
            //         color: ['#50a3ba', '#eac736', '#d94e5d']
            //     },
            //     textStyle: {
            //         color: '#fff'
            //     }
            // },
            geo: {
                map: mapName,
                geoIndex: '222',
                // selectedMode: 'single',
                label: {
                    normal: {
                        show: false
                    },
                    emphasis: {
                        show: false
                    }
                },
                itemStyle: {
                    normal: {
                        areaColor: areaColor,
                        borderColor: '#AFD1FF'
                    },
                    emphasis: {
                        areaColor: '#a1c3f5'
                    }
                }
            },
            xAxis: {
                axisLabel: {show: false},
                axisLine: {show: false},
                splitLine: {show: false},
                axisTick: {show: false},
                min: -1,
                max: 1
            },
            yAxis: {
                axisLabel: {show: false},
                axisLine: {show: false},
                splitLine: {show: false},
                axisTick: {show: false},
                min: -1,
                max: 0
            },
            series: deal_series(city_list, times_sum, mapName, label_type_name)
        };
    }
    // 指定图表的配置项和数据
    // 使用刚指定的配置项和数据显示图表。
    if (myChart != null && myChart !== "" && myChart !== undefined) {
        myChart.dispose();
    }

    myChart = echarts.init(document.getElementById('map_statistics'));
    myChart.clear();
    myChart.setOption(option);
    myChart.on('click', function (param) {
        //下钻其实就是点击事件，切换脚本而已

        if (param.name) {
            if (param.name === "上海" || param.name === "北京" || param.name === "天津" || param.name === "重庆") {
                return
            }
            
            // if (label_type_name === "正确率") return;
            var is_province = null;
            for (var i = 0; i < result_data.length; i++) {
                if (result_data[i].title === param.name) {
                    is_province = true;
                    break;
                } else {
                    is_province = false;
                }
            }

            if (!is_province) {
                return
            }

            showMap(result_data, geoCoordMap, param.name, label_type_name);
            showProvinceChart(result_data, param.name, label_type_name);
            $('.map_back').removeClass('dis_none');
        }
    });
}

function do_deal_result_data(result_data) {
    var res = {};
    var province_list = [];
    var province_data_list = [];
    var all_city_list = [];
    var times_sum = 0;
    var times_sum_dict = [];
    if (result_data) {
        for (var i = 0; i < result_data.length; i++) {
            var city_list = result_data[i].city_list;
            var province = result_data[i].title;
            province = deal_special_province(province);
            result_data[i].title = province;

            times_sum += result_data[i].data;
            if (province) {
                province_list.push(province);
                province_data_list.push(result_data[i].data);
                times_sum_dict[province] = result_data[i].data;
            }
            if (city_list) {
                res[province] = [];
                for (var j = 0; j < city_list.length; j++) {
                    var geoCoord = geoCoordMap[city_list[j].title];
                    if (geoCoord) {
                        res[province].push({
                            name: city_list[j].title,
                            value: geoCoord.concat(city_list[j].data)
                        });
                        all_city_list.push({
                            name: city_list[j].title,
                            value: geoCoord.concat(city_list[j].data)
                        });
                    }
                }
            }
        }
        times_sum_dict['china'] = times_sum;
    }
    return [res, all_city_list, times_sum_dict];
}

function sliceArray(array, size) {
    if (size == 0) {
        return [array];
    }
    var result = [];
    for (var x = 0; x < Math.ceil(array.length / size); x++) {
        var start = x * size;
        var end = start + size;
        result.push(array.slice(start, end));
    }
    return result;
}

var convertData = function (data) {
    var res = [];
    for (var i = 0; i < data.length; i++) {
        var geoCoord = geoCoordMap[data[i].title];
        if (geoCoord) {
            res.push({
                name: data[i].title,
                value: geoCoord.concat(data[i].data)
            });
        }
    }
    return res;
};

function comdify(n) {
    if (n) {
        n = n.toString();
        var re = /\d{1,3}(?=(\d{3})+$)/g;
        var n1 = n.replace(/^(\d+)((\.\d+)?)$/, function (s, s1, s2) {
            return s1.replace(re, "$&,") + s2;
        });
        return n1;
    }
    return n
}

function deal_series(city_list, times_sum, mapName, label_type_name) {
    times_sum = comdify(times_sum);
    var min_len = Math.ceil(city_list.length / 5);
    city_list.sort(function (a, b) {
        return b.value[2] - a.value[2];
    });
    var level_city_list = sliceArray(city_list, min_len);
    var s_data = [];
    for (var i = 0; i < level_city_list.length; i++) {
        var data_list = {
            name: i + 1,
            type: 'scatter',
            coordinateSystem: 'geo',
            data: level_city_list[i],
            symbolSize: d_info[i].size,
            showEffectOn: 'emphasis',
            label: {
                normal: {
                    formatter: '{b}',
                    position: 'right',
                    color: '#fff',
                    backgroundColor: 'rgba(72,84,101,0.7)',
                    padding: [6, 8, 6, 8],
                    borderRadius: 2,
                    show: false
                },
                emphasis: {
                    show: true,
                    position: [25, 0],
                    formatter: function (params) {
                        return params.name + ': ' + params.value[2];
                    }
                }
            },
            itemStyle: {
                normal: {
                    color: d_info[i].color
                }
            }
        };
        s_data.push(data_list);
    }
    if (mapName === undefined || mapName === 'china') {
        mapName = "";
    }
    var lable_list = {
        type: 'scatter',
        data: [[0, 0]],
        symbolSize: 1,
        label: {
            show: true,
            position: 'top',
            formatter: function () {
                return ['{c|' + '}{a|已累计}{b|' + times_sum + '}{a|' + label_type_name + '}'].join('\n')
            },
            padding: [0, 30, 0, 30],
            color: '#000',
            rich: {
                a: {
                    padding: [0, 10, 0, 10],
                    color: '#ccc',
                    fontSize: 20
                },
                b: {
                    padding: [3, 10, 3, 10],
                    color: '#9D6AFF',
                    fontSize: 40,
                    backgroundColor: '#f2f2f2',
                    borderRadius: 3,
                    fontFamily: 'Arial'
                },
                c: {
                    color: '#ccc',
                    fontSize: 20
                },
            }
        }
    };
    s_data.push(lable_list);
    // var china_list = {
    //     name: '0',
    //     type: 'map',
    //     geoIndex: 0,
    //     data: [
    //         {name: '北京', value: ''},
    //         {name: '天津', value: ''},
    //         {name: '上海', value: ''},
    //         {name: '重庆', value: ''},
    //         {name: '河北', value: ''},
    //         {name: '河南', value: ''},
    //         {name: '云南', value: ''},
    //         {name: '辽宁', value: ''},
    //         {name: '黑龙江', value: ''},
    //         {name: '湖南', value: ''},
    //         {name: '安徽', value: ''},
    //         {name: '山东', value: ''},
    //         {name: '新疆', value: ''},
    //         {name: '江苏', value: ''},
    //         {name: '浙江', value: ''},
    //         {name: '江西', value: ''},
    //         {name: '湖北', value: ''},
    //         {name: '广西', value: ''},
    //         {name: '甘肃', value: ''},
    //         {name: '山西', value: ''},
    //         {name: '内蒙古', value: ''},
    //         {name: '陕西', value: ''},
    //         {name: '吉林', value: ''},
    //         {name: '福建', value: ''},
    //         {name: '贵州', value: ''},
    //         {name: '广东', value: ''},
    //         {name: '青海', value: ''},
    //         {name: '西藏', value: ''},
    //         {name: '四川', value: ''},
    //         {name: '宁夏', value: ''},
    //         {name: '海南', value: ''},
    //         {name: '台湾', value: ''},
    //         {name: '香港', value: ''},
    //         {name: '澳门', value: ''}
    //     ],
    //     label: {
    //         normal: {
    //             formatter: '{b}',
    //             position: 'right',
    //             color: '#fff',
    //             backgroundColor: 'rgba(72,84,101,0.7)',
    //             padding: [6, 8, 6, 8],
    //             borderRadius: 2,
    //             show: true
    //         },
    //         emphasis: {
    //             show: true
    //         }
    //     }
    // };
    // s_data.push(china_list);
    return s_data;
}

function get_bar_data(result_data) {
    var name_list = [];
    var times_list = [];
    var undefined_name = '';
    var undefined_data = '';
    if (result_data) {
        for (var i = 0; i < result_data.length; i++) {
            var name = result_data[i].title;
            var times = result_data[i].data;
            name = deal_special_province(name);
            if (name !== "undefined") {
                name_list.push(name);
                times_list.push(times);
            } else {
                undefined_name = '其他';
                undefined_data = times;
            }

        }
    }
    //其他（地图数据）
    // if (undefined_name !== '') {
    //     name_list.push(undefined_name);
    //     times_list.push(undefined_data);
    // }
    if (name_list) {
        name_list = name_list.reverse();
    }
    if (times_list) {
        times_list = times_list.reverse();
    }
    return [name_list, times_list]
}

function do_get_province_city_data(result_data) {
    var province_city_dict = {};
    if (result_data) {
        for (var i = 0; i < result_data.length; i++) {
            var name = result_data[i].title;
            var city_list = result_data[i].city_list;
            if (name) {
                name = deal_special_province(name);
                province_city_dict[name] = city_list
            }
        }
    }
    return province_city_dict
}

var echart_bar = null;

function showProvinceChart(result_data, province, label_type_name) {
    if (province === "" || province == null || province === undefined || province !== 'china') {
        var province_city_dict = do_get_province_city_data(result_data);
        result_data = province_city_dict[province];
    }

    var data_list = get_bar_data(result_data);
    var province_list = data_list[0];
    var province_data_list = data_list[1];

    var barMinWidth = $("#province_statistics").outerWidth() * 0.6;
    var option_bar = {
        title: {
            text: '全国各省份答题人数一览（人次）',
            show: false
        },
        toolbox: {
            show: false,
            feature: {
                saveAsImage: {}
            },
            right: 20
        },
        grid: {
            left: '8%',
            right: '13%',
            top: '0%',
            bottom: '2%',
            width: '64%',
            containLabel: true
        },
        tooltip: {
            show: true,
            trigger: "axis",
            axisPointer: {
                lineStyle: {
                    opacity: 0
                }
            },
            formatter: function (params) {
                return params[1].name;
            }
        },
        color: ['#8cc7fe'],
        xAxis: {
            type: 'value',
            boundaryGap: [0, 0],
            axisTick: {
                show: false
            },
            axisLabel: {
                show: false
            },
            axisLine: {
                show: false
            },
            splitLine: {show: false}
        },
        yAxis: {
            type: 'category',
            data: province_list,
            axisTick: {
                show: false
            },
            axisLabel: {
                textStyle: {
                    color: '#37487A',
                    align: 'right',
                    fontSize: 10
                },
                padding: [0, 0, 0, 0]
            },
            axisLine: {
                show: false
            },
            splitLine: {show: false}
        },
        series: [
            {
                name: '',
                type: 'bar',
                barWidth: '10',
                barMaxWidth: '100%',
                data: province_data_list,
                barGap: '-100%',
                barMinHeight: barMinWidth,
                label: {
                    normal: {
                        show: true,
                        position: 'right',
                        color: '#999',
                        formatter: function (params) {
                            return params.value;
                        }
                    }
                },
                itemStyle: {
                    normal: {
                        color: item_color,
                        barBorderRadius: [12, 12, 12, 12]
                    }
                },
                emphasis: {
                    label: {
                        show: true,
                        color: emphasis_colors[0]
                    },
                    itemStyle: {
                        color: emphasis_colors[1]
                    }
                }
            },
            {
                name: '',
                type: 'bar',
                barWidth: 10,
                barGap: '-100%',
                data: province_data_list,
                label: {
                    normal: {
                        show: false,
                        position: 'right',
                        color: '#999',
                        formatter: function (params) {
                            return params.value;
                        }
                    }
                },
                itemStyle: {
                    normal: {
                        color: new echarts.graphic.LinearGradient(0, 0, 1, 1, [{
                            offset: 0,
                            color: color_offset[0]
                        }, {
                            offset: 1,
                            color: color_offset[1]
                        }]),
                        shadowColor: 'rgba(0, 0, 0, 0.4)',
                        barBorderRadius: [12, 12, 12, 12]
                    }
                }
            }
        ]
    };
    if (echart_bar != null && echart_bar !== "" && echart_bar !== undefined) {
        echart_bar.dispose();
    }
    echart_bar = echarts.init(document.getElementById('province_statistics'));
    echart_bar.clear();
    echart_bar.setOption(option_bar);
    echart_bar.on('click', function (param) {
        //下钻其实就是点击事件，切换脚本而已
        if (param.name) {
            if (param.name === "上海" || param.name === "北京" || param.name === "天津" || param.name === "重庆") {
                return
            }
            // if (label_type_name === "正确率") return;
            showMap(result_data, geoCoordMap, param.name, label_type_name);
            showProvinceChart(result_data, param.name);
            city_name = param.name;
            $('.map_back').removeClass('dis_none');
        }
    });
}

function deal_special_province(title) {
    if (title === "内蒙古自治区") {
        title = "内蒙古";
    }
    if (title === "西藏自治区") {
        title = "西藏";
    }
    if (title === "新疆维吾尔自治区") {
        title = "新疆";
    }
    if (title === "广西壮族自治区") {
        title = "广西";
    }
    if (title === "宁夏回族自治区") {
        title = "宁夏";
    }
    return title
}

function get_province_city_accuracy(result_data) {
    var total_sum = 0;
    var correct_sum = 0;
    var times_sum_dict = [];
    if (result_data) {
        for (var i = 0; i < result_data.length; i++) {
            var province = result_data[i].title;
            province = deal_special_province(province);
            total_sum += result_data[i].total;
            correct_sum += result_data[i].correct;
            if (province) {
                times_sum_dict[province] = result_data[i].data;
            }
        }
        if (total_sum) {
            times_sum_dict['china'] = (correct_sum / total_sum * 100).toFixed(2);
        }
    }
    return times_sum_dict;
}

function correct_rate_option(result_data, times_sum, map_name) {
    var map_name_show = map_name;
    if (map_name === undefined || map_name === 'china') {
        map_name_show = "";
    }
    var option = {
        backgroundColor: backgroundColor,
        title: {
            text: '公民参与科学素质学习累计',
            show: false
        },
        toolbox: {
            show: false,
            feature: {
                saveAsImage: {}
            },
            right: 20
        },
        tooltip: {
            show: true,
            formatter: function (params) {
                if (typeof params.data !== 'undefined') {
                    return params.name + '：' + params.data['value'] + '%'
                }
            },
        },
        visualMap: {
            type: 'continuous',
            min: 50,
            max: 100,
            calculable: true,
            inRange: {
                // color: ['#FFD3D3', '#FFB8B8', '#FF7878', '#FF5858', '#e83232']
                color: ['#3EC2FF', '#5ABC0B', '#C6E202', '#F8E71C', '#FE9B03', '#F76B1C', '#CC0000', '#7D0000'],
                // colorSaturation: 1
            },
            textStyle: {
                color: '#000'
            },
            bottom: 30,
            left: 'left',
        },
        geo: {
            map: map_name,
            geoIndex: '222',
            // selectedMode: 'single',
            label: {
                normal: {
                    show: true,
                },
                emphasis: {
                    show: false
                }
            },
            itemStyle: {
                normal: {
                    areaColor: '#ffffcc',
                    borderColor: '#AFD1FF'
                },
                emphasis: {
                    areaColor: '#a1c3f5'
                }
            }
        },
        xAxis: {
            axisLabel: {show: false},
            axisLine: {show: false},
            splitLine: {show: false},
            axisTick: {show: false},
            min: -1,
            max: 1
        },
        yAxis: {
            axisLabel: {show: false},
            axisLine: {show: false},
            splitLine: {show: false},
            axisTick: {show: false},
            min: -1,
            max: 0
        },
        series: [
            {
                name: 'Correct Rate',
                type: 'map',
                roam: false,
                geoIndex: 0,
                data: correct_rate_data(result_data, map_name)
            },
            {
                type: 'scatter',
                data: [[0, 0]],
                symbolSize: 1,
                label: {
                    show: true,
                    position: 'top',
                    formatter: function () {
                        if (result_data.length !== 0){
                           return ['{c|' + '}{a|总体正确率}{b|' + times_sum + '}{a|%}'].join('\n')
                        }else{
                            return ['{c|' + '}{a|总体正确率}{b|' + 0 + '}{a|%}'].join('\n')
                        }

                    },
                    padding: [0, 30, 0, 30],
                    color: '#000',
                    rich: {
                        a: {
                            padding: [0, 10, 0, 10],
                            color: '#ccc',
                            fontSize: 20
                        },
                        b: {
                            padding: [3, 10, 3, 10],
                            color: '#9D6AFF',
                            fontSize: 40,
                            backgroundColor: '#f2f2f2',
                            borderRadius: 3,
                            fontFamily: 'Arial'
                        },
                        c: {
                            color: '#ccc',
                            fontSize: 20
                        },
                    }
                }
            }
        ]
    };
    return option
}

function correct_rate_data(result_data, map_name) {
    var province_data_list = [];
    var city_data_list = [];
    if (result_data) {
        for (var i = 0; i < result_data.length; i++) {
            var province = result_data[i].title;
            province = deal_special_province(province);
            if (province) {
                if (map_name && map_name === province) {
                    var city_list = result_data[i].city_list;
                    for (var j = 0; j < city_list.length; j++) {
                        var city_name = city_list[j].title;
                        var data = city_list[j].data;
                        city_data_list.push({'name': city_name, 'value': data});

                    }
                    if (city_data_list) return city_data_list
                } else {
                    province_data_list.push({'name': province, 'value': result_data[i].data});
                }
            }
        }
    }
    return province_data_list
}