//公民科学素质答题人次趋势
function showTendencyMemberTimesChart(result_data, series_name, chart_color, not_checked_name_list, category) {
    var deal_data = deal_result_data(result_data, series_name, chart_color);
    var xAxis_list = deal_data[0];
    var series_dict = deal_data[1];
    var lately_date = new Date();
    lately_date.setDate(lately_date.getDate() - 30);

    var myChart = echarts.getInstanceByDom(document.getElementById('tendency_member_times_chart'));
    if (myChart === undefined || myChart === null || myChart === "") {
        myChart = echarts.init(document.getElementById('tendency_member_times_chart'));
    }
    var option = myChart.getOption();
    if(category === undefined){
        category = "次数"
    }
    if (option) {
        var o_xAxis_list = option.xAxis[0].data;
        series_dict = deal_result_data_by_xAxis(result_data, series_name, o_xAxis_list, chart_color);
        var series_list = option.series;
        var legend_data_list = option.legend[0].data;
        if (legend_data_list.indexOf(series_name) < 0) {
            series_list.push(series_dict);
            legend_data_list.push(series_name);
            option.series = series_list;
            option.legend[0].data = legend_data_list
        }


    } else {
        option = {
            color: ["#7cb5ec"],
            title: {
                text: '公民科学素质答题人次趋势',
                show: false
            },
            toolbox: {
                show: false,
                feature: {
                    saveAsImage: {}
                },
                right: 20
            },
            legend: {
                data: [series_name],
                show: false
            },
            tooltip: {
                trigger: 'axis',
                axisPointer: {
                    type: 'cross',
                    crossStyle: {
                        color: '#989898',
                        type: 'dotted'
                    },
                    lineStyle: {
                        type: 'dotted'
                    },
                    label: {
                        precision: 0
                    }
                },
                borderRadius: 0,
                position: ['40%', 10],
                borderWidth: 0,
                borderRadius: 2,
                textStyle: {
                    color: '#fff',
                    lineHeight: 12,
                    fontSize: 12
                },
                padding: 10
            },
            xAxis: {
                data: xAxis_list,
                axisLine: {
                    lineStyle: {
                        color: '#989898',
                        width: 1
                    }
                },
                axisTick: {
                    show: false
                },
                axisLabel: {
                    textStyle: {
                        color: '#989898'
                    }
                }
            },
            yAxis: {
                splitLine: {
                    show: false
                },
                axisLine: {
                    lineStyle: {
                        color: '#989898',
                        width: 1
                    }
                },
                axisLabel: {
                    textStyle: {
                        color: '#989898'
                    }
                },
                axisTick: {
                    show: false
                }
            },

            series: [series_dict]
        };
        option.dataZoom = dataZoom
    }
    myChart.clear();
    myChart.setOption(option, {'notMerge': true});
    if (not_checked_name_list) {
        for (let i in not_checked_name_list) {
            myChart.dispatchAction({
                type: 'legendUnSelect',
                name: not_checked_name_list[i]
            });
        }
    }
    if(category === "次数"){
       myChart.dispatchAction({type: 'legendUnSelect', name: '总体答题' + '人数'})
       myChart.dispatchAction({type: 'legendSelect', name: '总体答题' + '次数'})
    }else{
        myChart.dispatchAction({type: 'legendUnSelect', name: '总体答题' + '次数'})
        myChart.dispatchAction({type: 'legendSelect', name: '总体答题' + '人数'})
    }

    myChart.on('click', function (param) {
        if (param.seriesName === '全国答题人数' || param.seriesName === '全国答题次数') {
            var select_date = param.name;
            var data = {
                'date': select_date
            };
            ajaxPost('/backoffice/reports/learning/situation/member/increase/', data, function (result) {
                if (result.code == 0) {
                    tip_msg("获取数据失败！", 2000);
                } else {
                    var result_data = result.data;
                    $("#tendency_member_times_bar_chart").show();
                    $("#tendency_member_times_chart").hide();
                    $("#control_head").hide();
                    $("#control_back").show();
                    $("#tendency_member_times_bar_chart").siblings(".set_time_box").css('visibility', 'hidden');
                    $("#tendency_member_times_bar_chart").siblings(".screen_box").css('visibility', 'hidden');
                    $("#tendency_member_times_bar_chart").siblings(".more_screen_box").css('visibility', 'hidden');
                    if (result_data.length === 0) {
                        $(".no_data").removeClass("dis_none");
                        return
                    }
                    var myChartBar = echarts.getInstanceByDom(document.getElementById('tendency_member_times_bar_chart'));
                    if (myChartBar === undefined || myChart === null || myChart === "") {
                        myChartBar = echarts.init(document.getElementById('tendency_member_times_bar_chart'));
                    }

                    option = {
                        title: {
                            text: '每日新增TOP5',
                            textStyle: {
                                color: '#797979',
                                fontSize: 14,
                                align: 'center',
                            },
                            left: '60',
                            show: true
                        },
                        color: ["#7cb5ec", "#a0d368", "#f7a35b", "#8085e9", "#f15c80"],
                        tooltip: {
                            trigger: 'axis',
                            axisPointer: {
                                type: 'cross',
                                crossStyle: {
                                    color: '#989898',
                                    type: 'dotted'
                                },
                                lineStyle: {
                                    type: 'dotted'
                                },
                                label: {
                                    precision: 0
                                }
                            },
                            borderRadius: 0,
                            position: ['40%', 10],
                            borderWidth: 0,
                            borderRadius: 2,
                            textStyle: {
                                color: '#fff',
                                lineHeight: 12,
                                fontSize: 12
                            },
                            padding: 10,
                            formatter: function (datas) {
                                var res = datas[0].name + '<br/>';
                                for (var i = 0, length = datas.length; i < length; i++) {
                                    if (datas[i].data.name !== "" && datas[i].data.name !== null) {
                                        var index = datas[i].dataIndex + 1
                                        res += datas[i].marker + 'Top' + index + '：' + datas[i].value + '<br/>';
                                    }
                                }
                                return res
                            }
                        },
                        yAxis: {
                            minInterval: 1,
                            splitLine: {
                                show: false
                            },
                            axisLine: {
                                lineStyle: {
                                    color: '#989898',
                                    width: 1
                                }
                            },
                            axisLabel: {
                                textStyle: {
                                    color: '#989898'
                                }
                            },
                            axisTick: {
                                show: false
                            }
                        },
                        xAxis: {
                            data: get_member_increase_xAxis_data(result_data),
                            axisLine: {
                                lineStyle: {
                                    color: '#989898',
                                    width: 1
                                }
                            },
                            axisTick: {
                                show: false
                            },
                            axisLabel: {
                                textStyle: {
                                    color: '#989898'
                                }
                            }
                        },
                        series: get_member_increase_series(result_data)
                    };
                    myChartBar.clear();
                    myChartBar.setOption(option);
                    $('.member_times_back').show();
                }
            });
        }

    });

    function get_member_increase_xAxis_data(result_list) {
        var xAxis_data = [];
        for (var i = 0; i < result_list.length; i++) {
            var result = result_list[i];
            xAxis_data.push(result.title);
        }
        return xAxis_data;
    }

    function get_member_increase_series(result_list) {
        var color_list = ["#7cb5ec", "#a0d368", "#f7a35b", "#8085e9", "#f15c80"];
        var quantity_list = [];
        var series_list = [];
        var color_len = color_list.length;
        for (var i = 0; i < result_list.length; i++) {
            var result = result_list[i];
            if (i <= color_len - 1) {
                var color = color_list[i];
            } else {
                var color = "#7cb5ec";
            }
            var temp_dict = {
                name: result.province_title + ' ' + result.title,
                value: result.quantity,
                itemStyle: {
                    color: color
                }
            };
            quantity_list.push(temp_dict);
        }
        var temp_dict = {
            name: 'Top5',
            type: 'bar',
            data: quantity_list,
            symbol: 'emptyCircle',
            symbolSize: 2,
            lineStyle: {
                normal: {
                    width: 2,
                }
            },
            barWidth: 40


        };
        series_list.push(temp_dict);
        return series_list

    }
}

function deal_result_data(result_data, series_name, chart_color) {
    var xAxis_list = [];
    var series_data = [];
    if (result_data) {
        for (var i = 0; i < result_data.length; i++) {
            var daily_data = result_data[i];
            if (daily_data) {
                for (var key in daily_data) {
                    var value = daily_data[key];
                    xAxis_list.push(key);
                    series_data.push(value);
                }
            }
        }
    }

    var series_dict = {
        name: series_name,
        type: 'line',
        data: series_data,
        symbol: 'emptyCircle',
        symbolSize: 2,
        itemStyle: {
            color: chart_color
        },
        lineStyle: {
            color: chart_color,
            width: 2,
        }

    };
    return [xAxis_list, series_dict]
}

function deal_result_data_by_xAxis(result_data, series_name, xAxis_list, chart_color) {
    var series_data = [];
    var result_dict = {};
    if (result_data) {
        for (var i = 0; i < result_data.length; i++) {
            var daily_data = result_data[i];
            if (daily_data) {
                for (var key in daily_data) {
                    var value = daily_data[key];
                    result_dict[key] = value;
                }
            }
        }
    }
    if (xAxis_list) {
        for (var j = 0; j < xAxis_list.length; j++) {
            var k = xAxis_list[j];
            var v = result_dict[k];
            if (v && v != undefined && v != 'undefined') {
            } else {
                v = 0;
            }
            series_data.push(v);
        }
    }

    var series_dict = {
        name: series_name,
        type: 'line',
        data: series_data,
        symbol: 'emptyCircle',
        symbolSize: 2,
        itemStyle: {
            color: chart_color
        },
        lineStyle: {
            width: 2,
            color: chart_color
        }

    };
    return series_dict
}

function formatDate(dateobj) {
    var year = dateobj.getFullYear();
    var month = dateobj.getMonth() + 1;
    var day = dateobj.getDate();
    var datestr = year + '/' + month + '/' + day;
    return datestr;
}
