
(function($) {

	var myData = {};
	var type;

	$.showAlert = function(options) {
		showPopWindws(options, "alert");
	};

	$.showConfirm = function(options) {
		showPopWindws(options, "confirm");
	};

	$.openDialog = function(options) {
		showPopWindws(options, "dialog");
	};

	var showPopWindws = function(options, flag) {
		var defaults = {
			title: "",
			content: "",
			showClose: true,
			width : 270,
			btn: ["取消","确认"]
		};
		myData = $.extend(defaults, {}, options);
		
		//建立容器
		var box = $("<div class='tui_popWinBox'></div>");
		$("body").append(box);

		//建立遮罩
		var mask;
		mask=$("<div class='tui_winMask'></div>");
		box.append(mask);
		
		var win;
		//弹框类型
		switch(flag) {
			case "alert":
				win = $('<div class="tui_popWin"><div class="dialog_cnt"><div class="dialog_hd"><h3></h3></div><div class="dialog_bd"><div></div></div><div class="dialog_ft"><button type="button" class="sureBtn">确认</button></div></div></div>');
				break;
			case "confirm":
				win = $('<div class="tui_popWin"><div class="dialog_cnt"><div class="dialog_hd"><h3></h3></div><div class="dialog_bd"><div></div></div><div class="dialog_ft"><button type="button" class="cancelBtn cancel_confirm"></button><button type="button" class="sureBtn sure_confirm"></button></div></div></div>');
				break;
			case "dialog":
				win = $('<div class="tui_popWin dialog"><div class="dialog_cnt"><div class="dialog_hd"><h3></h3></div><div class="dialog_bd"></div><div class="dialog_ft"><button type="button" class="sureBtn">关闭</button></div></div></div>');
				break;
		}
		box.append(win);
		//标题
		win.find("h3").append(myData.title);
		//内容
		win.find(".dialog_bd div").append(myData.content);

		// confirm按钮：
		win.find(".cancel_confirm").append(myData.btn[0]);
		win.find(".sure_confirm").append(myData.btn[1]);
		//根据弹框类型添加确定/取消事件
		switch(flag) {
			case "alert":
				addSureEvent(win.find(".sureBtn"), myData);
				break;
			case "confirm":
				addSureEvent(win.find(".sureBtn"), myData);
				addCancelEvent(win.find(".cancelBtn"), myData);
				break;
		}
		if(options.title == undefined || options.title == "") {
			win.find(".dialog_hd").hide();
		}
		//自定义弹框
		if(flag == 'dialog') {
			//显示隐藏关闭按钮
			if(myData.showClose) {
				addSureEvent(win.find(".sureBtn"), myData);
			} else {
				win.find(".dialog_ft").hide();
			}
			resizePercentWin(myData.width, myData.height, win.find(".dialog_cnt"));
			var boxCotent = win.find(".dialog_bd");
			setTimeout(function() {
				if(myData.url){
					boxCotent.append($("<iframe width='100%' height='100%' frameBorder=0  allowTransparency='false' src='" + myData.url + "'></iframe>"));
					$("iframe").width(boxCotent.width())
				}
			}, 100);
		}
		setTimeout(function() {
			$(".tui_popWinBox").addClass("show");
		}, 100);
		tui_touchEnable = 0;
	};

	$.closePopWin = function() {
		$(".tui_popWinBox").remove();
		tui_touchEnable = 1;
	};

	function addSureEvent(btn, myData) {
		btn.bind('click', function(e) {
			$.closePopWin();
			if(myData.sure)
				myData.sure(myData.data)
		});
	}

	function addCancelEvent(btn, myData) {
		btn.bind('click', function(e) {
			$.closePopWin();
			if(myData.cancel)
				myData.cancel(myData.data);
		});
	}

	function resizePercentWin(wid, hei, myPopBox) {
		var boxCotent = myPopBox.find(".dialog_bd");
		var title = myPopBox.find(".dialog_hd");
		var foot = myPopBox.find(".dialog_ft");
		wid = wid.toString();
		hei = hei.toString();
		//console.log(wid)
		//console.log(hei)
		var index = wid.indexOf("%");
		if(index != -1) {
			wid = wid.substring(0, index);
			wid = document.documentElement.clientWidth * Number(wid) * 0.01;
		}
		index = hei.indexOf("%");
		if(index != -1) {
			hei = hei.substring(0, index);
			hei = document.documentElement.clientHeight * Number(hei) * 0.01;
		}
		myPopBox.css({
			"width": wid
		});
		boxCotent.css({
			"height": hei - title.height() - foot.height()
		});
	}

})(jQuery);