// function menu_action() {
//     $(".left_menu").each(function () {
//         if($(this).find("li").hasClass("active")){
//             $(this).addClass("active");
//         }
//     })
// }
$(function () {
    // 只能输入数字：
    $(document).on("input propertychange", ".only_num", function () {
        $(this).val($(this).val().replace(/[^\d]/g, ''));
    });
    // 只能输入数字和小数点
    $(document).on("input propertychange", ".only_decials", function () {
        $(this).val($(this).val().replace(/[^\d.]/g, ''));
    });
    // tips:
    $("body .tips").mouseenter(function () {
        var txt = $(this).attr("data-name");
        var that = this;
        if (txt) {
            layer.tips(txt, that, {
                time: 0,
                tips: 1
            })
        }
    }).mouseleave(function () {
        layer.closeAll('tips');
    });

//内容自适应窗口调整
    window.onresize = function () {
        autoReset();
    };
    autoReset();
    checked();
//  user_info：
    $(".user_info").mouseover(function () {
        $(this).find(".outer_login").show()
    }).mouseout(function () {
        $(this).find(".outer_login").hide();
    });
//  left_menu:
//     menu_action();
    $(".first_menu").click(function () {
        $(this).parent().toggleClass("active");
    });
    $(document).on("click", ".table_role .checkbox_i", function () {
        $(this).toggleClass("checked");
    });
    $(".table_list .checkbox_i").click(function () {
        $(this).toggleClass("checked");
        checked();
    });
    $(".table_control .checkbox_i").click(function () {
        if ($(this).hasClass("checked")) {
            $(".data_list").find(".checkbox_i").removeClass("checked");
            $(this).parents(".manage_table").find(".checkbox_i").removeClass("checked");
            $(this).removeClass("checked");
        }
        else {
            $(".data_list").find(".checkbox_i").addClass("checked");
            $(this).parents(".manage_table").find(".checkbox_i").addClass("checked");
            $(this).removeClass("checked_part").addClass("checked");
        }
    });
});

// 自动调节大小
function autoReset() {
    var rightArea = $(".right_area");
    var leftArea = $(".left_area");
    var clientHeight = document.documentElement.clientHeight - 60;
    leftArea.height(clientHeight);
    rightArea.height(clientHeight);
}

function checked() {
    var tableList = $(".table_list");
    tableList.each(function () {
        var checkboxNum = $(this).find(".checkbox_i").length;
        if ($(this).find(".checkbox_i.checked").length === 0) {
            $(this).siblings(".table_control").find(".checkbox_i").removeClass("checked_part checked");
        }
        else if ($(this).find(".checkbox_i.checked").length === checkboxNum) {
            $(this).siblings(".table_control").find(".checkbox_i").removeClass("checked_part").addClass("checked");
        }
        else {
            $(this).siblings(".table_control").find(".checkbox_i").removeClass("checked").addClass("checked_part");
        }
    });

}

// 删除数组指定项：
Array.prototype.indexOf = function (val) {
    for (var i = 0; i < this.length; i++) {
        if (this[i] == val) return i;
    }
    return -1;
};
// 删除数组中某字符串：
Array.prototype.remove = function (val) {
    var index = this.indexOf(val);
    if (index > -1) {
        this.splice(index, 1);
    }
};
// 删除数组中某对象：
Array.prototype.removeObj = function (val) {
    for (var l = 0; l < this.length; l++) {
        for (var m = 0; m < this[l].sub.length; m++) {
            if (this[l].sub[m].c_name == val) {
                this[l].sub.splice(m, 1);
                break;
            }
        }
    }
};
// 删除数组中空sub的项：
Array.prototype.deleteObj = function () {
    for (var i = 0; i < this.length; i++) {
        if (this[i].sub.length == 0) {
            this.splice(i, 1);
            break;
        }
    }
};
// 数组去重：
Array.prototype.removeRepeat = function () {
    var n = [];
    for (var i = 0; i < this.length; i++) {
        if (n.indexOf(this[i]) == -1) {
            n.push(this[i]);
        }
    }
    return n;
};
Array.prototype.removeByIndex = function (dx) {
    if (isNaN(dx) || dx > this.length) {
        return false;
    }
    for (var i = 0, n = 0; i < this.length; i++) {
        if (this[i] != this[dx]) {
            this[n++] = this[i]
        }
    }
    this.length -= 1
}

function format_data(data) {
    var temp_dict = {}
    for (var key in data) {
        var value = data[key];
        if (Array.isArray(value)) {
            temp_dict[key] = value
        } else {
            value = parseInt(value);
            temp_dict[key] = [value]
        }
    }
    return temp_dict
}

// 初始化省份个数：
function initNum(arr) {
    var p_box = $(".province_box");
    for (var i = 0; i < arr.length; i++) {
        var obj = p_box.find("li[data-code='" + arr[i].substring(0, 2) + "0000']").find(".city_num");
        obj.removeClass("dis_none");
        obj.html(parseInt(obj.html() == "" ? 0 : obj.html()) + 1);
    }
}


function get_cachekey_data() {
    /* 获取服务器cachekey数据，用于图表模块
    *
    * 使用可变参数arguments， 参数格式为
    * arguments[0]: cache_key
    * arguments[1]: callback 填充图表数据的回调函数
    * arguments[other]: args of callback 回调函数的参数
    * */

    var [cache_key, fill_charts, ...args] = arguments;
    ajaxPost("/backoffice/reports/cache_key/get/", {'cache_key': cache_key}, function (res) {
        if (res.code === 0) {
            tip_msg('正在准备数据，请稍等~', 1000);
        } else if (res.code === 2) {
            setTimeout(get_cachekey_data, 2000, cache_key, fill_charts, ...args)
        } else if (res.code === 1) {
            // 填充图表数据
            fill_charts(res.data, ...args)
        }
    })
}

function sort_xAixs_desc(array_xa, array_xb) {
    /*
    对报表模块的x轴数据排序
     */
    return array_xb.data.length - array_xa.data.length
}