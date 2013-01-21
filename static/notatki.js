on_init(function(){
	var mouseOver = null
	var lastMouseOver = null
	var defaultHideNow = 2
	var hideNow = defaultHideNow
	
	setInterval(function(){
		if(mouseOver == null)
			if(--hideNow != 0)
				return
		if(mouseOver != lastMouseOver) {
			if(mouseOver == null) {
				$('#big-thumb').fadeOut()
			} else {
				$('#big-thumb').fadeIn()
				$('#big-thumb').animate({ top: mouseOver.position().top })
				$('#big-thumb').attr('src', mouseOver.attr('src'))
			}
			lastMouseOver = mouseOver
		}
	}, 400)
	$(IMG_SELECTOR).mouseover(function(){
		mouseOver = $(this).find('img')
		hideNow = defaultHideNow
	}).mouseout(function(){
		mouseOver = null
	})
})
