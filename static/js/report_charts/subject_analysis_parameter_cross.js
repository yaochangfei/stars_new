function showSubjectAnalysisParameterCross(result_data, difficulty_name_list,dom_id) {
    var data_list = init_result_data(result_data);
    var source_list = data_list[0];
    var series_list = data_list[1];
    var myChart = echarts.getInstanceByDom(document.getElementById(dom_id));
    if (myChart === undefined || myChart === null || myChart === "") {
        myChart = echarts.init(document.getElementById(dom_id));
    }
    var option = {
        color:['#E0F0FB','#C1E1F7','#A0D4F5','#81C5F1','#62B6ED'],
        title: {
            text: '难度+知识维度',
            left: 'center',
            y: 20,
            textStyle: {
                fontSize: 16,
                fontWeight: 'normal',
                color: '#373737'
            },
            show: false
        },
        dataset: {
            source: source_list
        },
        legend: {difficulty_name_list, textStyle: {color: dimension_text_color}},
        tooltip: {
            trigger: 'item'
            // trigger: 'axis',
            // axisPointer: {
            //     type: 'shadow'
            // }
        },
        grid: {
            left: '3%',
            right: '4%',
            bottom: '3%',
            containLabel: true
        },
        xAxis: {
            type: 'category',
            axisTick: {
                show: false
            },
            axisLabel: {
                interval: 0,
                textStyle: {
                    color: '#989898'
                }
            },
            axisLine: {
                lineStyle: {
                    color: '#989898',
                    width: 1
                }
            },
            splitLine: {show: false}
        },
        yAxis: {
            type: 'value',
            axisLabel: {
                formatter: '{value} %',
                textStyle: {
                    color: '#989898'
                }
            },
            axisTick: {
                show: false
            },
            axisLine: {
                lineStyle: {
                    color: '#989898',
                    width: 1
                }
            },
            splitLine: {show: false}
        },
        series: series_list
    };
    myChart.clear();
    myChart.setOption(option);

    function init_result_data(result_data) {
        var source_list = [];
        var series_list = [];
        var series_len = result_data[0].sub.length;
        for (var i = 0; i < result_data.length; i++) {
            var dimension_dict = {};
            var data = result_data[i];
            dimension_dict['dimension'] = data.title;
            var sub_list = data.sub;
            for (var j = 0; j < sub_list.length; j++) {
                var sub_data = sub_list[j];
                if (sub_data.total) {
                    dimension_dict[sub_data.title] = (sub_data.correct / sub_data.total * 100).toFixed(2);
                } else {
                    dimension_dict[sub_data.title] = 0;
                }
            }
            source_list.push(dimension_dict);

        }
        var avg = 1 / series_len;
        for (var s = 0; s < series_len; s++) {
            var opacity = avg + avg * s;
            series_list.push({
                type: 'bar',
                label: {
                    show: true,
                    position: 'top',
                    textStyle: {
                        color: dimension_text_x_color
                    }
                },
                itemStyle: {
                    opacity: 1
                }
            })
        }

        return [source_list, series_list]
    }
}