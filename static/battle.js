on_init(window.battle_fun = function(){

var log = {}
//window.enemy_garnison = {gunner: 10}

var canvas = $('#battle-canvas')[0]
var c = canvas.getContext('2d')

var unit_width=30, unit_height=50
var unit_widths = {
	gunner: 28,
	automatic: 28,
	rocketlauncher: 89,
}
var unit_heights = {
	gunner: 45,
	automatic: 45,
	rocketlauncher: 70
}
var army_width = 200
var type_space = 20

var units_pos = window.units_pos = {attack: {}, defense: {}}
var max_y = {attack: 300, defense: 300}

var round_time = 10 // <<<==
var microround_number = 20
var microround_time = round_time/microround_number
var current_microround = 0

var next_round = {}

var unit_scale = 0.5

for(var i in unit_heights)
	unit_heights[i] *= unit_scale
for(var i in unit_widths)
	unit_widths[i] *= unit_scale

function calc_army(army_name, units, x, y) {
	var old_army = get_old_army(army_name)
	for(var name in units) {
		var amount = Math.ceil(units[name])
		var add = amount - (old_army[name]||0) 
		if(add > 0)
			y = add_army(army_name, name, add, x, y)
		else
			y = remove_army(army_name, name, -add, x, y)
	}
}
window.calc_army = calc_army

function add_army(army_name, name, amount, x, y) { /* y is no more used */
	var positions = units_pos[army_name][name] || []
	var left = amount || 0
	for(var i in positions) {
		if(left <= 0) break
		var pos = positions[i]
		if(!pos[2]) { // not alive?
			left -= 1
			pos[2] = true // now alive
		}
	}
	return add_army_down(army_name, name, left, x, max_y[army_name] + unit_heights[name])
}

function remove_army(army_name, name, amount, x, y) {/* x, y is not used */
	var positions = units_pos[army_name][name] || []
	var left = amount || 0
	for(var i in positions) {
		if(left <= 0) break
		var pos = positions[i]
		if(pos[2]) { // alive?
			left -= 1
			pos[2] = false // now dead
		}
	}
}

function add_army_down(army_name, name, amount, x, y) {
	if(!units_pos[army_name][name]) units_pos[army_name][name] = []
	while(amount > 0) {
		var draw_count = Math.min(amount, Math.floor(army_width / unit_widths[name]))
		amount -= draw_count
		for(var i=0; i<draw_count; i++) {
			if(y > max_y[army_name]) max_y[army_name] = y
			units_pos[army_name][name].push([x+unit_widths[name]*i, y, true])
		}
		y += unit_heights[name]
	}
	return y
}

function get_old_army(name) {
	var units = {}
	for(var kind in units_pos[name]) {
		var list = units_pos[name][kind]
		units[kind] = 0
		for(var i in list)
			if(list[i][2] === true)
				units[kind] += 1
	}
	return units
}

window.get_old_army = get_old_army

function draw_army(army_name, units, x, y) {
	var this_army_pos = units_pos[army_name]
	for(var kind in this_army_pos) {
		var units_of_kind = this_army_pos[kind]
		var img_name = '/static/img/' + kind + '-btl-' + army_name + '.png'
		for(var i in units_of_kind) {
			var pos = units_of_kind[i]
			if(!pos[2]) c.globalAlpha = 0.5 //not alive?
			draw_img(img_name, pos[0], pos[1] - unit_heights[kind], unit_widths[kind], unit_heights[kind])
			c.globalAlpha = 1
		}
	}
}

function calc_log(defense, attack, even) {
	draw_log_funcs = []
	calc_log_side('defense', 'attack', log.defense, defense, attack, even)
	calc_log_side('attack', 'defense', log.attack, attack, defense, even)
}

function randomize(n) { return (n*n)^0xA123A }

var draw_log_funcs

function calc_log_side(army_name, enemy_army, log, units, victims, even) {
	var left_victims = $.extend({}, victims) //copy
	var left_units = $.extend({}, units)
	
	for(var i in log) {
		var e = log[i]
		var attacktype=e[0], victimtype=e[1], attacknum=e[2], victimnum=e[3]
		
		var last_attack_num = left_units[attacktype] - 1
		left_units[attacktype] -= attacknum
		var last_victim_num = left_victims[victimtype] - 1
		left_victims[victimtype] -= victimnum
		
		var shoot_to = [] // list index:src value: dst (indexes in list attackers and defenders)
		
		var attackers = find_alive(army_name, attacktype, attacknum)
		var defenders = find_alive(enemy_army, victimtype, victimnum)
		
		for(var j=0; j<attacknum; j++) {
			shoot_to.push(Math.round( ((victimnum-1)/(attacknum-1)) *j ))
		}
		//shoot_to = shuffle(shoot_to)
		for(var j in shoot_to) {
			var src = attackers[j]
			var dst = defenders[shoot_to[j]]
			draw_log_funcs.push(function() {
				if((randomize(shoot_to[j]) % microround_number) != (current_microround % microround_number)) return
				if(army_name == 'attack') {
					if(!even) c.strokeStyle = 'rgba(255, 50, 50, 0.9)'
					else c.strokeStyle = 'rgba(255, 50, 50, 0.5)'
				} else {
					if(!even) c.strokeStyle = 'rgba(50, 50, 255, 0.9)'
					else c.strokeStyle = 'rgba(50, 50, 255, 0.5)'
				}
				c.beginPath()
				c.moveTo(src[0] + unit_widths[attacktype]/2, src[1] + unit_heights[attacktype]/2)
				c.lineTo(dst[0] + unit_widths[victimtype]/2, dst[1] + unit_heights[victimtype]/2)
				c.closePath()
				c.stroke()
				dst[2] = false // not alive
			})
		}
	}
}

/** Returns array of length num containing alive units poitions */
function find_alive(army, kind, num) {
	num = Math.floor(num)
	var all_units = units_pos[army][kind]
	var alive = []
	for(var i in all_units) {
		if(alive.length >= num) break
		var unit = all_units[i]
		if(unit[2]) { // alive?
			alive.push(unit)
		}
	}
	if(alive.length != num) {
		console.warn('Not enough units of kind', kind, 'army', army)
		console.warn('needed', num, 'got', alive.length)
	}
	return alive
}

//+ Jonas Raoni Soares Silva
//@ http://jsfromhell.com/array/shuffle [v1.0]
shuffle = function(o){ //v1.0
	for(var j, x, i = o.length; i; j = parseInt(Math.random() * i), x = o[--i], o[i] = o[j], o[j] = x);
	return o;
};
// end

img_cache = {}

function draw_img(name, x, y, w, h) {
	var img = get_img(name)
	if(img) c.drawImage(img, x, y, w, h)
}

function draw_tiled_img(name, x, y, w, h, tileW, tileH) {
	var img = get_img(name)
	if(!img) return
	var numX = Math.ceil(w/tileW)
	var numY = Math.ceil(h/tileH)
	for(var nx=0; nx<numX; nx++)
		for(var ny=0; ny<numY; ny++) {
			c.drawImage(img, x + nx*tileW, y + ny*tileH, tileW, tileH)
		}
}

function get_img(name) {
	if(img_cache[name])
		return img_cache[name]
	if(img_cache[name] === null)
		return null
	img_cache[name] = null
	var new_img = new Image()
	new_img.src = name
	new_img.onload = function(){
		img_cache[name] = new_img
	}
}

var running = false
var fetched = false

function round () {
	if((microround_number-current_microround) == 2/microround_time)
		fetch() /* fetch next round, 2 seconds before end of it */
	if(current_microround == microround_number) {
		running = false
		current_microround = 0
	}
	
	if(!running) {
		if(fetched) {
			running = true
			fetched = false
		} else
			return 
	}
	if(current_microround == 0){
		//console.log('log', log)
		calc_army('defense',  window.garnison, 10, null)
		calc_army('attack', window.enemy_garnison, 370, null)
		calc_log(window.garnison, window.enemy_garnison, true)
	}
	current_microround += 1
}

function fetch() {
	$.get('/api/get_battle_state?cityname=' + encodeURIComponent(window.cityname),
		function(text){
			var json = eval('(' + text + ')')
			window.garnison = json[2]
			window.enemy_garnison = json[1]
			
			log = json[0]
			fetched = true
		})
}

function draw_city() {
	draw_tiled_img('/static/img/grass.png', 0, 0, 1000, 1000, 400, 400)
	draw_img('/static/img/all.png', 0, 0, 1000, 1000)
}

function make_city() {
	for(var name in window.buildings) {
		var level = window.buildings[name]
		if(!level) continue
		if(!buildings_def[name]) continue
		var pos = buildings_def[name]
		
		var elem = $('[buildingname=' + name + ']')
		elem.find('img.b').attr('src', '/static/img/' + name + '-city.png')
			.attr('width', pos[2]).attr('height', pos[3])
		elem.css({left: pos[0] + 'px', top: pos[1] + 'px'})
		$('.battle-body').append(elem)
		
		if(name == 'farm') {
			var i=0
			elem.find('img.b').click(function(){
				i++
				if(i==5) {
					elem.find('img.b').attr('src', '/static/img/farm-city-anim.gif')
						.remove().appendTo('body')
						.css({position: 'absolute', width: '100%',
							 height: '100%', left: 0, top: 0}).addClass('kiu')
					window.scrollTo(0,0)
					setTimeout(function(){
						$('body .kiu').fadeOut(2000)
					}, 6500)
				}
			})
		}
	}
}

function get_scale() {
	return $(canvas).width() / canvas.width
}

function draw(even) {
	c.fillStyle = 'white'
	//c.fillRect(0,0,1000,1000)
	draw_city()
	draw_army('defense',  window.garnison, null, null)
	draw_army('attack', window.enemy_garnison, null, null)
	for(var i in draw_log_funcs) draw_log_funcs[i]()
}

function loop() {
	var even = false
	setInterval(function(){
		if(even) round()
		draw(even)
		even = !even
	}, microround_time/2*1000)
}

loop()
fetch()

$(window).resize(adjustSize = function(){
	var wnd_width = $(window).width()
	var battle_width = $('.battle-body').width()
	$('.battle-body').css('zoom', wnd_width / battle_width)
})

var buildings_def = {
	forest: [700, 30, 200, 200],
	farm: [100, 750, 150, 150],
	goldmine: [300, 750, 150, 150],
	uraniummine: [500, 750, 150, 150]
}

make_city()
setTimeout(adjustSize, 100)

})