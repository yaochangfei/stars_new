var chart_map = {};
var chart_options = {};
var condition_map = {}; // key: chart_id, value: condition

function init_chart(url_path, show_percent, option_setting) {
    $(".chart").each(function () {
        var tmp_chart_id = $(this).attr('id');
        chart_map[tmp_chart_id] = echarts.init(document.getElementById(tmp_chart_id));
        chart_options[tmp_chart_id] = Array();

        chart_map[tmp_chart_id].showLoading({color: '#A0D368'});
        update_chart(tmp_chart_id, null, null, url_path, show_percent, null, option_setting);
    });

}

function init_single_chart(url_path, chart_id, config, show_percent, option_setting) {
    chart_map[chart_id] = echarts.init(document.getElementById(chart_id));
    chart_options[chart_id] = Array();

    chart_map[chart_id].showLoading({color: '#A0D368'});
    drill_bar_chart(chart_id, config, show_percent, null, false, option_setting);
}

function update_chart(chart_id, condition_value, condition_name, url_path, show_percent, edit_index, option_setting) {
    var myChart = chart_map[chart_id];
    var chart_obj = $("#" + chart_id);
    var opt = myChart.getOption();
    var param = {
        'category': chart_obj.attr('data-category'),
        'condition_value': condition_value,
    };
    if (opt !== undefined) {
        param.xAxis = JSON.stringify(opt.xAxis[0].data);
    }
    var x_name = chart_obj.attr('data-x');

    if (condition_name === null || condition_name === '' || condition_name === undefined) {
        condition_name = '全部'
    }

    if (condition_map[chart_id] === undefined) {
        condition_map[chart_id] = {};
    }
    condition_map[chart_id][condition_name] = param;

    ajaxPost(url_path, param, function (ret) {
        if (ret.code === 0) {
            tip_msg('服务器错误。', 2000);
            myChart.hideLoading();
        } else if (ret.code === 1) {
            if (ret.pie) {
                for (var i=0; i < ret.pie['legendData'].length; i++) {
                    ret.pie['legendData'][i] = {'name': ret.pie['legendData'][i], 'textStyle': {'color': '#c5c5c5'}}
                }

                option = {
                    color: chart_color_list,
                    tooltip: {
                        trigger: 'item',
                        formatter: "{a} <br/>{b} : {c} ({d}%)"
                    },
                    legend: {
                        type: 'scroll',
                        orient: 'vertical',
                        right: 10,
                        top: 20,
                        bottom: 20,
                        data: ret.pie['legendData'],
                    },
                    series: [
                        {
                            name: '行为',
                            type: 'pie',
                            radius: '55%',
                            center: ['40%', '50%'],
                            data: ret.pie['seriesData'],
                            itemStyle: {
                                emphasis: {
                                    shadowBlur: 10,
                                    shadowOffsetX: 0,
                                    shadowColor: 'rgba(0, 0, 0, 0.5)'
                                }
                            }
                        }
                    ]
                };

            } else if (ret.line) {
                var old_option = myChart.getOption();
                var series = {
                    'name': condition_name,
                    'type': 'line',
                    'data': ret.line['seriesData']
                };
                var xAixs_data = ret.line.xAxisData;
                for (var i=0; i < xAixs_data.length; i++) {
                    xAixs_data[i] = {value: xAixs_data[i], textStyle: {color: '#c5c5c5'}}
                }

                if (!Boolean(old_option)) {
                    option = {
                        color: ["#7cb5ec", "#a0d368", "#f7a35b", "#8085e9", "#f15c80"],
                        tooltip: {
                            trigger: 'axis',
                            formatter: function (datas) {
                                var res = datas[0].name + '</br>';
                                for (var i = 0; i < datas.length; i++) {
                                    if (show_percent) {
                                        res += datas[i].marker + datas[i].seriesName + ': ' + auto_to_fixed(datas[i].data) + '%</br>';
                                    } else {
                                        res += datas[i].marker + datas[i].seriesName + ': ' + datas[i].data + '</br>';
                                    }
                                }
                                return res
                            }
                        },
                        legend: {
                            show: false,
                            left: 10,
                            data: [condition_name],
                        },
                        grid: {
                            left: '3%',
                            right: '4%',
                            bottom: '11%',
                            containLabel: true
                        },
                        xAxis: {
                            name: x_name,
                            nameGap: 5,
                            type: 'category',
                            boundaryGap: true,
                            data: ret.line['xAxisData']
                        },
                        yAxis: {
                            type: 'value',
                            axisLabel: {
                                color: '#c5c5c5',
                                formatter: function (value) {
                                    if (show_percent) {
                                        return auto_to_fixed(value) + '%'
                                    } else {
                                        return value
                                    }
                                }
                            },
                            splitLine:{show:false},
                        },
                        series: [series],
                    };
                    option.dataZoom = dataZoom

                } else {
                    if (edit_index || edit_index === 0) {
                        old_option.legend[0].data[edit_index + 1] = condition_name;
                        old_option.series[edit_index + 1] = series;
                        option = old_option;
                    } else {
                        if ($.inArray(condition_name, old_option.legend[0].data) === -1) {
                            old_option.legend[0].data.push(condition_name);
                            if (xAixs_data.length >= old_option.xAxis[0].data.length) {
                                old_option.xAxis.data = xAixs_data;
                            }
                            old_option.series.push(series);
                            option = old_option
                        }
                    }
                }
            }else if(ret.bar){
                var old_option = myChart.getOption();
                var series = {
                    'name': condition_name,
                    'type': 'bar',
                    'data': ret.bar['seriesData'],
                    'barMaxWidth': 35
                    //'barWidth': 35
                };
                var xAixs_data = ret.bar.xAxisData;
                if (!Boolean(old_option)) {
                    option = {
                        color: ["#7cb5ec", "#a0d368", "#f7a35b", "#8085e9", "#f15c80"],
                        tooltip: {
                            trigger: 'axis',
                            formatter: function (datas) {
                                var res = datas[0].name + '</br>';
                                for (var i = 0; i < datas.length; i++) {
                                    if (show_percent) {
                                        res += datas[i].marker + datas[i].seriesName + ': ' + auto_to_fixed(datas[i].data) + '</br>';
                                    } else {
                                        res += datas[i].marker + datas[i].seriesName + ': ' + datas[i].data + '</br>';
                                    }
                                }
                                return res
                            }
                        },
                        legend: {
                            show: false,
                            left: 10,
                            data: [condition_name],
                        },
                        grid: {
                            left: '3%',
                            right: '4%',
                            bottom: '11%',
                            containLabel: true
                        },
                        xAxis: {
                            name: x_name,
                            nameGap: 4,
                            type: 'category',
                            boundaryGap: true,
                            data: ret.bar['xAxisData'],
                            axisLabel: {
                                interval:'auto', //横轴信息全部显示
                                //rotate:-15 //-30度角倾斜显示
                            }
                        },
                        yAxis: {
                            type: 'value',
                            axisLabel: {
                                formatter: function (value) {
                                    if (show_percent) {
                                        return auto_to_fixed(value) + '人'
                                    } else {
                                        return value
                                    }
                                }
                            }
                        },
                        series: [series],
                    };
                    option.dataZoom = dataZoom;

                } else {
                    if (edit_index || edit_index === 0) {
                        old_option.legend[0].data[edit_index + 1] = condition_name;
                        old_option.series[edit_index + 1] = series;
                        option = old_option;
                    } else {
                        if ($.inArray(condition_name, old_option.legend[0].data) === -1) {
                            old_option.legend[0].data.push(condition_name);
                            if (xAixs_data.length >= old_option.xAxis[0].data.length) {
                                old_option.xAxis.data = xAixs_data;
                            }
                            old_option.series.push(series);
                            option = old_option
                        }
                    }
                }
            }
            if (option && typeof option === "object") {
                myChart.hideLoading();


                if (option_setting) {
                    if (!option_setting['dataZoom']) {
                        delete option.dataZoom
                    }
                    if (option_setting['xAxis_axisLabel_interval'] !== undefined) {
                        option['xAxis']['axisLabel']['interval'] = option_setting['xAxis_axisLabel_interval']
                    }
                }
                myChart.setOption(option, true);
            }
        }
    });
}

function export_chart(url, chart_id, x_axis_y_axis_name, show_percent) {
    var option = chart_map[chart_id].getOption();
    var series = {};
    for (var i = 0; i < option.series.length; i++) {
        var key = option.series[i].name;
        series[key] = option.series[i].data;
        if (show_percent) {
            series[key] = series[key].map(function (item, index) {
                return item + '%'
            });
        }
    }
    for (var i = 0; i < option.xAxis[0].data.length; i++){
        delete option.xAxis[0].data[i]['textStyle']
    }
    data = {
        'series': series,
        'xAxis': option.xAxis[0].data,
    };
    var param = {
        'x_axis_y_axis_name': x_axis_y_axis_name,
        'chart_name': $("#" + chart_id).attr('data-excel'),
        'data': JSON.stringify(data),
    };

    window.location.href = url + "?" + dict_2_url_params(param);

}

function auto_to_fixed(num) {
    /* for example:

    auto_to_fixed(1.131) ==>  1.1
    auto_to_fixed(0.131) ==>  0.13
    auto_to_fixed(0.01221) ==>   0.012
    auto_to_fixed(0.0011031)  ==>   0.0011
    auto_to_fixed(0.0000510121231)  ==>  0.000051
    */
    var digit = 1;
    var origin_num = num;
    while (num < 1 && num !== 0) {
        num *= 10;
        digit += 1;
    }
    return origin_num.toFixed(digit)
}

function delete_chart(chart_id, index) {
    var myChart = chart_map[chart_id];
    var old_option = myChart.getOption();
    old_option.legend[0].data.splice(index + 1, 1);
    old_option.series.splice(index + 1, 1);
    myChart.setOption(old_option, true)
}

function toggle_legend(chart_id, name) {
    var myChart = chart_map[chart_id];
    myChart.dispatchAction({
        type: 'legendToggleSelect',
        name: name
    });
}


function drill_bar_chart(chart_id, config, show_percent, edit_index, drop_chart, option_setting) {
    var myChart = chart_map[chart_id];
    var chart_obj = $("#" + chart_id);
    var opt = myChart.getOption();
    var param = {
        'category': chart_obj.attr('data-category'),
        'condition_value': config.data_str,
        'group_type': config.group_type
    };
    if (config.pre_data) {
        param.pre_data = JSON.stringify(config.pre_data)
    }

    var condition_name = config.condition_name;
    var url_path = config.url;

    if (opt !== undefined) {
        param.xAxis = JSON.stringify(opt.xAxis[0].data);
    }
    var x_name = chart_obj.attr('data-x');

    if (condition_name === null || condition_name === '' || condition_name === undefined) {
        condition_name = '全部'
    }

    if (condition_map[chart_id] === undefined) {
        condition_map[chart_id] = {};
    }
    condition_map[chart_id][condition_name] = param;

    ajaxPost(url_path, param, function (ret) {
        if (ret.code === 0) {
            tip_msg('服务器错误。', 2000);
            myChart.hideLoading();
        } else if (ret.code === 1) {
            var old_option = myChart.getOption();
            var series = {
                'name': condition_name,
                'type': 'bar',
                'data': ret.bar['seriesData'],
                'barMaxWidth': 35
                //'barWidth': 35
            };
            var xAixs_data = ret.bar.xAxisData;
            if (!Boolean(old_option) || drop_chart) {
                option = {
                    color: ["#7cb5ec", "#a0d368", "#f7a35b", "#8085e9", "#f15c80"],
                    tooltip: {
                        trigger: 'axis',
                        formatter: function (datas) {
                            var res = datas[0].name + '</br>';
                            for (var i = 0; i < datas.length; i++) {
                                if (show_percent) {
                                    res += datas[i].marker + datas[i].seriesName + ': ' + auto_to_fixed(datas[i].data) + '</br>';
                                } else {
                                    res += datas[i].marker + datas[i].seriesName + ': ' + datas[i].data + '</br>';
                                }
                            }
                            return res
                        }
                    },
                    legend: {
                        show: false,
                        left: 10,
                        data: [condition_name],
                    },
                    grid: {
                        left: '3%',
                        right: '4%',
                        bottom: '11%',
                        containLabel: true
                    },
                    xAxis: {
                        name: x_name,
                        nameGap: 4,
                        type: 'category',
                        boundaryGap: true,
                        data: ret.bar['xAxisData'],
                        axisLabel: {
                            interval:'auto', //横轴信息全部显示
                            rotate:-15 //-30度角倾斜显示
                        },
                        axisTick: {
                            alignWithLabel: true
                        }
                    },
                    yAxis: {
                        type: 'value',
                        axisLabel: {
                            formatter: function (value) {
                                if (show_percent) {
                                    return auto_to_fixed(value) + '人'
                                } else {
                                    return value
                                }
                            }
                        }
                    },
                    series: [series],
                };
                option.dataZoom = dataZoom

            } else {
                if (edit_index || edit_index === 0) {
                    old_option.legend[0].data[edit_index + 1] = condition_name;
                    old_option.series[edit_index + 1] = series;
                    option = old_option;
                } else {
                    if ($.inArray(condition_name, old_option.legend[0].data) === -1) {
                        old_option.legend[0].data.push(condition_name);
                        if (xAixs_data.length >= old_option.xAxis[0].data.length) {
                            old_option.xAxis.data = xAixs_data;
                        }
                        old_option.series.push(series);
                        option = old_option
                    }
                }
            }
            if (option && typeof option === "object") {
                myChart.hideLoading();

                if (option_setting) {
                    if (!option_setting['dataZoom']) {
                        delete option.dataZoom
                    }
                    if (option_setting['xAxis_axisLabel_interval'] !== undefined) {
                        option['xAxis']['axisLabel']['interval'] = option_setting['xAxis_axisLabel_interval']
                    }
                }
                console.log(option)
                myChart.setOption(option, true);
            }
        }
    });
}