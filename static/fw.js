function fw_wait_for_jquery(){
	if(!window['$'])
		setTimeout(fw_wait_for_jquery, 0)
	else
		fw_init();
}

function fw_outer_html_setup() {
	jQuery.fn.outerHTML = function(s) {
		if(s) {
			var new_elem = $(s)
			new_elem.insertBefore(this)
			$(this).remove()
			return new_elem
		} else
			return jQuery("<p>").append(this.eq(0).clone()).html();
	}
}

function fw_init(elem) {
	fw_set_browser_class()
	fw_outer_html_setup()
	fw_setup_ajax_indicator()
	$(function(){
		fw_process_elem(document.body)
	})
	fw_use_hash()
	window.onpopstate = fw_pop_state
	setTimeout(function(){
		fw_is_init = false
	}, 100)
	fw_initialized = true
}

function fw_set_browser_class() {
	var clazz = null
	if($.browser.mozilla) clazz = 'mozilla'
	if($.browser.webkit) clazz = 'webkit'
	if(clazz) $('body').addClass(clazz)
}

function fw_use_hash() {
	var hash = location.hash.slice(1)
	var path = location.pathname.slice(1)
	if(hash && hash != path) {
		fw_run_widget_link(hash)
	}
}

var fw_initialized = false
var fw_is_init = true
var fw_current_location = fw_get_location()

function fw_pop_state() {
	if(fw_is_init) return
	fw_run_widget_link(fw_get_location(), true)
}

function fw_get_location() {
	var hash = location.hash.slice(1)
	if(hash)
		return hash
	return location.pathname + location.search
}

function fw_setup_ajax_indicator() {
	var indicator = $('<div id=fw-ajax-indicator><img src=/static/loading.gif>').appendTo('body')
	indicator.hide()
	$(document).ajaxStart(function(){
		indicator.show()
	}).ajaxStop(function(){
		indicator.hide()
	})
}

function fw_process_elem(elem) {
	$(elem).find('[fw_action_url]').each(function(){
		var url = $(this).attr('fw_action_url')
		var replace = (typeof $(this).attr('fw_replace')) != 'undefined'
		$(this).click(function(){
			fw_run_action(url, replace)
			return false
		})
	})
	$(elem).find('.fw-widget-link').each(function(){
		var url = $(this).attr('fw_widget_link') || $(this).attr('href')
		var target = $(this).attr('fw_link_target')
		var display_url = $(this).attr('href')
		var replace = (typeof $(this).attr('fw_replace')) != 'undefined'
		$(this).click(function(){
			setTimeout(function(){
				fw_run_widget_link({url: url, target: target, display: display_url, replace: replace })
			}, 0)
			return false
		})
	})
	$(elem).find('.fw-submit').each(function(){
		var form = $(this).parents('form')[0]
		var base_url = $(form).attr('action')
		$(this).click(function(){
			if($(form).attr('fw_no_js'))
				return true
			var url = fw_url_with_param(base_url, $(form).serialize())
			fw_run_action(url)
			return false
		})
	})
	$(elem).find('fwscript').each(function(){
		var text = $(this).html()
		var parent = $(this).parent()
		var type = $(this).attr('type')
		$(this).remove()
		if(text.slice(0, 4) == '<!--')
			text = text.slice(4)
		fw_run_fw_script(type, '(function(fw_elem){' + text + '\n})(_param)', parent)
	})
	if(window['G_vmlCanvasManager'])
		$(elem).find('canvas').each(function(){
			G_vmlCanvasManager.initElement(this)
		})
}

function fw_run_fw_script(type, code, elem) {
	var run = function() { fw_eval(code, elem) }
	if(type == 'fw/resize')
		fw_on_resize(run)
	else if(type == 'fw/init' || !type)
		run()
	else
		console.error('Unknown script type', type)
}

function fw_on_resize(func) {
	$(window).resize(func)
	func()
}

function fw_run_widget_link(arg, dont_push, force, no_anim) {
	var url, target, display_url, replace, out_elem
	if(typeof arg == 'object') {
		url = arg.url
		target = arg.target || ''
		display_url = arg.display || url
		replace = arg.replace || false
		out_elem = arg.out_elem || '[fw_widget_path="' + target + '"]'
	} else {
		url = arg
		target = ''
		display_url = arg
		replace = false
		out_elem = '#fw-body'
	}
	if(fw_current_location == url && !force)
		return
	var rpc_url = fw_url_with_rpc(display_url)
	if(target)
		rpc_url += '&__rpc_render=' + encodeURIComponent(target)
	var lock
	var lock_elem
	if(!no_anim) {
		lock_elem = target ? $(out_elem) : $('#fw-body')
		lock = fw_lock_elem(lock_elem)
	}
	function set_result(data) {
		fw_replace_elem(out_elem, data, false, out_elem=='#fw-body')
		if(!dont_push)
			fw_push_history(display_url, replace)
		else if(!arg.no_push)
			fw_current_location = display_url
		/*
		 Did you know that you can write not only if(a=b) instead of if(a==b),
		 but also a==b instead of a=b?
		 
		 Today I've done it twice.
		*/
	}
	fw_ajax(rpc_url, function(data){
		if(!no_anim)
			lock.unlock(function(){
				var time = ANIM_TIME
				fw_animate_opacity(lock_elem, 0.5, 0.0, time)
				setTimeout(function(){
					fw_animate_opacity(lock_elem, 0.0, 1.0, time * 2)
					set_result(data)
				}, time)
			}, {no_anim: true})
		else
			set_result(data)
	})
}

function fw_animate_opacity(elem, start, end, time) {
	elem.find('.animate-separatly').each(function(){
		fw_animate_opacity($(this), start, end, time)
	})
	var iters = time / 50
	var step = (end - start) / iters
	var current = start
	var it = setInterval(function(){
		elem.css('opacity', current)
		current += step
		iters--;
		if(iters == 0) {
			elem.css('opacity', end)
			clearInterval(it)
		}
	}, 50)
}

var ANIM_TIME = 100 // a bit too fast?

function fw_lock_elem(elem) {
	var time = ANIM_TIME
	fw_animate_opacity(elem, 1.0, 0.5, time)
	
	function do_unlock(callback_before, opt) {
		if(!opt.no_anim)
			elem.animate({opacity: 1}, time)
		callback_before()
	}
	
	var lock = {unlock: function(callback_before, opt){
		if(lock.finished)
			do_unlock(callback_before, opt)
		else
			lock.on_finish = function(){ do_unlock(callback_before, opt) }
	}}
	lock.finished = false
	setTimeout(function(){
		lock.finished = true
		if(lock.on_finish)
			lock.on_finish()
	}, time)
	return lock
}

var fw_reloading_timer

function fw_run_reloading(each) {
	clearInterval(fw_reloading_timer)
	fw_reloading_timer = setInterval(function(){
		fw_reload()
	}, each)
}

function fw_reload() {
	fw_run_widget_link(fw_current_location, true, true, true)
}

function fw_run_action(url, replace) {
	var rpc_url = fw_url_with_rpc(url)
	fw_json_ajax(rpc_url, function(resp) {
		if(resp.redirect) {
			url = resp.redirect
			if(url.slice(0, 1) == '/' && url.slice(0, 5) != '/_ah/')
				fw_run_widget_link({
					url: resp.redirect
				})
			else
				location.href = url
			return
		}
		for(var key in resp.updates) {
			var content = resp.updates[key]
			var target = $('[fw_widget_path="' + key + '"]:first')
			if(target.length != 1)
				console.error('Need exactly one element', key, target)
			fw_replace_elem(target, content)
			//fw_process_elem(target)
		}
		fw_push_history(resp.url, replace)
	})
}

function fw_replace_elem(id, html, no_anim, no_replace) {
	var replace = !no_replace
	var elem = $(id)
	if(elem.length == 0)
		console.error('No elements with selector', id, '( ==', elem, ')')
	
	fw_set_elem_content(elem, html, replace)
}


function fw_set_elem_content(id, html, replace) {
	var parsed = $('<div eghr></div>')
	parsed.html(html)
	parsed.find('script').each(function(){
		var elem = $(this)
		if(elem.attr('type') && elem.attr('type') != 'text/javascript')
			return
		if(elem.attr('src')) {
			elem.attr('src', '')
			$.getScript(elem.attr('src'))
		} else {
			var text = elem.text()
			if(text.slice(0, 4) == '<!--')
				text = text.slice(4)
				
			fw_eval('(function(fw_elem){\n' + text + '\n})(_param)', elem)
		}
		elem.text('/* js */')//remove()
	})
	var out_elem = $(id)
	//console.log('parsed', parsed.html())
	if(replace)
		out_elem = out_elem.outerHTML(parsed.html())
	else
		out_elem.html(parsed.html())
	fw_process_elem(out_elem)
	return out_elem
}

function fw_eval(_script, _param) {
	try {
		eval(_script)
	} catch(e) {
		console.error(_script)
		throw e;
	}
}

if(!window['fw_animation'])
	window.fw_animation = false


function fw_url_with_rpc(url) {
	if(url.indexOf('?') == -1)
		return url + '?__rpc=true'
	else
		return url + '&__rpc=true'
}

function fw_url_with_param(url, param) {
	if(url.indexOf('?') == -1)
		return url + '?' + param
	else
		return url + '&' + param
}

function fw_run_action_custom(url, args) {
	for(var key in args) {
		url += '&' + key + '=' + encodeURIComponent(args[key])
	}
	fw_run_action(url)
}

function fw_push_history(url, replace) {
	var currentLocation = location.pathname + location.search
	if(url == currentLocation || url == currentLocation.slice(1))
		return
	var method = replace ? 'replaceState' : 'pushState'
	if(history[method]) {
		location.hash = location.hash.slice(0, 1)
		history[method](null, null, url)
	} else
		location.href = url //location.hash = '#' + url
	fw_current_location = url
}

function fw_json_ajax(url, func) {
	fw_ajax(url, function(json){
		var value = eval('(' + json + ')')
		func(value)
	})
}

function fw_ajax(url, func) {
	$.ajax({
		url: url,
		success: func,
		error: fw_ajax_error
	})
}

function fw_ajax_error(reason) {
	$('body').outerHTML(reason.responseText)
	alert('Error')
}

function fw_hover_anim(elems, over, out) {
	var newElem = null
	var currentElem = null
	var changeAfter = 0
	$(elems).mouseover(function(){
		newElem = $(this)
	}).mouseout(function(){
		newElem = null1
	})
	setInterval(function(){
		if(newElem != currentElem && (++changeAfter) >= 3) {
			if(currentElem)
				out(currentElem)
			if(newElem)
				over(newElem)
			currentElem = newElem
			changeAfter = 0
		}
	}, 200)
}

if(document.cookie.indexOf('disable_fw_js=true') == -1)
	fw_wait_for_jquery()
else
	fw_initialized = 'partially'
	