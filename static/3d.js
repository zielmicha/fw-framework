(function(){
	var ctx = $('#c')[0].getContext('2d')
	var hc = $('#hc')[0]
	var hctx = hc.getContext('2d')
	ctx.fillStyle = "rgba(0, 0, 200, 1)";
	hctx.fillStyle = "rgba(200, 200, 200, 1)";
	
	
	function drawPos(a, b, c, d, e, f, g, h) {
		var ps = translatePos(a, b, c, d, e, f, g, h)
		ctx.fillRect(1, ps.y-2, 800, 2)
		ctx.fillRect(ps.x-2, 2, 1, 800)
	}
	
	function drawPerspectiveImage(i, x, y, rot, scaleY, scaleY2) {
		for(var j=0; j<=i.height*scaleY - 1; j++)
			drawSlice(i, x, y+j, j/scaleY - j*j*scaleY2, (j/scaleY+y)*rot+1)
	}
	
	function translatePos(x, y, rot, scaleY, scaleY2, sx, sy, width) {
		var s = 1/scaleY
		var p = scaleY2
		var j = (s-Math.sqrt(s*s-4*p*sy)) / (2*p) // thanks to wolframalfa.com
		var scale = (j/scaleY)*rot+1
		return {
			y: (y + j),
			x: (x + scale*sx - width*scale/2),
			zoom: scale
		}
	}
	
	function drawSlice(i, x, y, srcY, scale) {
		var outWidth = i.width*scale
					/*	sx, sy,   sw,     sh, dx,            dy, dw,       dh*/
		ctx.drawImage(i, 0, srcY, i.width, 1, x - outWidth/2, y, outWidth, 1)
	}
	
	window.Map3d = {
		render: function() {
			hctx.fillStyle = "#738A47"; // like grass
			hctx.fillRect(0,0,4000,4000)
			hctx.fillStyle = "rgba(200, 200, 200, 1)";
			
			hctx.translate(-Map3d.x, -Map3d.y)
			Map3d.renderContent(hctx)
			hctx.translate(Map3d.x, Map3d.y)
			
			ctx.fillRect(0,0,1000,1000)
			drawPerspectiveImage(hc, Map3d.options.x, Map3d.options.y,
								 Map3d.options.rot, Map3d.options.scaleY,
								 Map3d.options.scaleY2)
			
			for(var i in Map3d.elementsToWatch) {
				var elem = Map3d.elementsToWatch[i]
				var x3d = parseFloat(elem.getAttribute('x3d'))
				var y3d = parseFloat(elem.getAttribute('y3d'))
				var pos = Map3d.translate(x3d, y3d)
				elem.style.top = (pos.y * Map3d.globalZoom) + 'px'
				elem.style.left = (pos.x * Map3d.globalZoom) + 'px' // - $(elem).width()/2
				elem.style.position = 'absolute'
				elem.style.fontSize = (pos.zoom * Map3d.globalZoom) + 'em'
			}
			
		}, options: {
			x: 100, y: 0, rot: 0.001, scaleY: 0.5, scaleY2: 0.001
		},
		x: -250, y:0,
		loop: function(interval, call) {
			function startLoop() {
				if(!Map3d.isLoopRunning)
					var loopIt = setInterval(function(){
						if(!Map3d.isLoopRunning)
							clearInterval(loopIt)
						Map3d.render()
					}, 50)
				Map3d.isLoopRunning++
			}
			startLoop()
			var it = setInterval(function(){
				var stop = call()
				if(stop == true) {
					clearInterval(it)
					Map3d.isLoopRunning--
				}
			}, interval || 50)
		},
		isLoopRunning: 0,
		elementsToWatch: [],
		watch: function(elem) {
			$(elem).addClass('watched').each(function(){
				Map3d.elementsToWatch.push(this)
			})
		},
		translate: function(x, y) {
			return translatePos(Map3d.options.x, Map3d.options.y,
								 Map3d.options.rot, Map3d.options.scaleY,
								 Map3d.options.scaleY2, x - Map3d.x, y - Map3d.y,
								 hc.width)
		}
	}
})()