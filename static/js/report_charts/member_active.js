//公民活跃度

function showMemberActiveChart(data, series_name, chart_color) {
    var result_data = data.data_list;
    var all_members = data.all_members;
    var deal_data = deal_result_data_member_active(result_data, all_members, series_name, chart_color);
    var xAxis_list = deal_data[0];
    var series_dict = deal_data[1];
    var lately_date = new Date();
    lately_date.setDate(lately_date.getDate() - 30);
    var start_date_str = formatDate(lately_date);

    var myChart = echarts.getInstanceByDom(document.getElementById('member_active_chart'));
    if (myChart === undefined || myChart === null || myChart === "") {
        myChart = echarts.init(document.getElementById('member_active_chart'));
    }
    var option = myChart.getOption();
    if (option) {
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
            color: ["#7cb5ec" ],
            title: {
                text: '公民活跃度',
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
                padding: 10,
                formatter: function (datas) {
                    var res = datas[0].axisValue + '<br/>';
                    for (var i = 0, length = datas.length; i < length; i++) {
                        if (datas[i].data.name !== "" && datas[i].data.name !== null) {
                            res += datas[i].marker + datas[i].seriesName + '：' + datas[i].value + '%' + '<br/>';
                        }
                    }
                    return res
                }
            },
            xAxis: {
                data: xAxis_list,
                name: "活跃\n天数",
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
                    formatter: '{value} %',
                    textStyle: {
                        color: '#989898'
                    }
                },
                axisTick: {
                    show: false
                },
            },
            series: [series_dict]
        };
        option.dataZoom = dataZoom
    }
    myChart.setOption(option, {'notMerge': true});
    myChart.on('click', function (param) {
        console.log(param);
    });

    function deal_result_data(result_data, series_name) {
        var xAxis_list = [];
        var series_data = [];
        if (result_data) {
            for (var i = 0; i < result_data.length; i++) {
                var daily_data = result_data[i];
                if (daily_data) {
                    xAxis_list.push(daily_data.days);
                    series_data.push(daily_data.quantity);
                }
            }
        }
        var series_dict = {
            name: series_name,
            type: 'bar',
            data: series_data,
            symbol: 'emptyCircle',
            symbolSize: 6,
            lineStyle: {
                normal: {
                    width: 2,
                    color: "#7CB5EC"
                }
            }

        };
        return [xAxis_list, series_dict]
    }
}

function deal_result_data_member_active(result_data, all_members, series_name, chart_color) {
    var xAxis_list = [];
    var series_data = [];
    if (result_data) {
        for (var i = 0; i < result_data.length; i++) {
            var daily_data = result_data[i];
            if (daily_data) {
                xAxis_list.push(daily_data.days);
                if (all_members) {
                    series_data.push((daily_data.quantity / all_members * 100).toFixed(2));
                }
                else {
                    series_data.push(0);
                }
            }
        }
    }
    var series_dict = {
        name: series_name,
        type: 'bar',
        data: series_data,
        symbol: 'emptyCircle',
        symbolSize: 6,
        itemStyle : {
            color : chart_color
        },
        'label': {
            'show': true,
            'position': 'top',
            'textStyle': {
                'color': '#989898'
            },
        },
    };
    return [xAxis_list, series_dict]
}

function formatDate(dateobj) {
    var year = dateobj.getFullYear();
    var month = dateobj.getMonth() + 1;
    var day = dateobj.getDate();
    var datestr = year + '/' + month + '/' + day;
    return datestr;
}
