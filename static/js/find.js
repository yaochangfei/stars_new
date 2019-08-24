$(function(){
    /*瀑布流初始化设置*/
	var $grid = $('.grid').masonry({
		itemSelector : '.grid-item',
		gutter:10
    });
    // layout Masonry after each image loads
	$grid.imagesLoaded().done( function() {
	  $grid.masonry('layout');
	});
	   var dataFall = [];
	   $(window).scroll(function(){
	   	$grid.masonry('layout');
                var scrollTop = $(this).scrollTop();var scrollHeight = $(document).height();var windowHeight = $(this).height();  
                if(scrollTop + windowHeight == scrollHeight){
                        $.ajax({
	               		dataType:"json",
				        type:'get',
				        url:'./article.json',
			            success:function(result){
			            	dataFall = result.result.article;
			            	appendFall();
			            },
			            error:function(e){
			            	console.log('请求失败')
			            }
	                   })
                }

         });
        function appendFall(){
          $.each(dataFall, function(index ,value) {
          	$grid.imagesLoaded().done( function() {
	        $grid.masonry('layout');
	           });
      	  var $griDiv = $('<div class="grid-item item '+ 'bg_'+value.theme+'">');
		  var $griItem = "<div class='comment_header'> <img src=" +value.pic +"> <span>"+ value.name+"</span> </div> <div class='comment_text'>"+ value.comment+"</div> <div class='comment_agree clear'> <i class='agree_i fl " +"agree_"+ value.theme + "'></i> <span class='" + "col_"+ value.theme+ " fl'>"+value.access_num+"</span> </div>";
      	  $griDiv.append($griItem);
      	  var $items = $griDiv;
		  $items.imagesLoaded().done(function(){
				 $grid.masonry('layout');
	             $grid.append( $items ).masonry('appended', $items);
			})
           });
        }
});
