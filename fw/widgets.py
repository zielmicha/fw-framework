#!/usr/bin/env python
import logging
import random

import fw.core
import fw.util
import fw.fwml
import fw.mail

class WrapperWidget(fw.core.Widget, fw.core.InsideWidget):
	def get_view_attrs(self):
		return self.parent.view_attrs
	
	def call_action(self, name, args):
		if name in self.actions:
			return fw.core.Widget.call_action(self, name, args)
		else:
			return self.parent.call_action(name, args)

_ = fw.core.widget(name='foreach')
class ForEach(WrapperWidget):
	list = fw.core.Attr()
	var = fw.core.Attr(type=str)
	key = fw.core.Attr(type=str, default=None)
	
	def init(self):
		self.widgets = []
	
	def create_children(self):
		for i, item in enumerate(self.list):
			vars = {self.var: item}
			child = self.create_widget_from_children(vars)
			ident = fw.util.create_ident(self.get_key(item))
			self.widgets.append(child)
			self.add_child(ident, i, child)
	
	def get_key(self, obj):
		if not self.key:
			return obj
		else:
			return fw.util.get_attr_or_item(obj, self.key)
	
	def get_path_of_child(self, child):
		r = fw.core.Widget.get_path_of_child(self, child)
		return r
	
	def render(self):
		result = []
		for widget in self.widgets:
			result.append(widget.render())
		return self.wrap_html(''.join(result))

_(ForEach)

_ = fw.core.widget(name='spoiler')
class Spoiler(WrapperWidget):
	open = fw.core.BoolAttr(default=False)
	tag = fw.core.Attr()
	
	def create_children(self):
		self.child = self.create_widget_from_children({})
		self.add_child('child', None, self.child)
		name, args = fw.fwml.parse_call(self.tag)
		self.tag_inst = fw.fwml.tag(name, attrs=args)
	
	def render(self):
		toggle_url = self.toggle.get_action_url()
		opener = fw.sgml.tag('a', clazz='fw-spoiler-button',
								href=toggle_url,
								fw_action_url=toggle_url,
								fw_replace=None,
								children=[self.tag_inst])
		if self.open:
			body = fw.sgml.PlainSGML(self.child.render())
			val = fw.sgml.tag('span', clazz='fw-spoiler', children=[opener, body]).repr()
		else:
			val = opener.repr()
		return self.wrap_html(val)
	
	@fw.core.action()
	def toggle(self):
		self.open = not self.open

_(Spoiler)

_ = fw.core.widget(name='api')
class API(object):
	@classmethod
	def run_this_widget(cls, env, args):
		name, args = cls.get_request(env, args)
		method = fw.core.api_methods[name]
		try:
			result = method(**dict([ (str(k), v) for k, v in args.items() ]))
		except fw.core.Redirect, r:
			env.redirect(r.dest)
		else:
			env.response.headers['content-type'] = 'text/plain'
			env.response.out.write(result)
	
	@classmethod
	def get_request(cls, env, args):
		name = args['name']
		del args['name']
		return name, args
	
	@classmethod
	def _init_class(cls):
		pass
_(API)

_ = fw.core.widget(name='_global')
class GlobalWidget(fw.core.Widget):
	def unserialize(self, data): pass
	def serialize(self):
		raise RuntimeError('No redirect in global action.')
	def render(self): pass
_(GlobalWidget)

lorem_ipsum = fw.util.get_file_content('fw/lorem-ipsum.txt').split('. ')

_ = fw.core.widget(name='loremipsum', public=True)
class LoremIpsum(fw.core.Widget):
	view = None
	count = fw.core.Attr(type=int, default=10)
	para_count = fw.core.Attr(type=int, default=1)
	
	def render(self):
		return '<p>'.join([
			'. '.join([
				random.choice(lorem_ipsum)
				for i in xrange(self.count)
			]) + '.'
			for j in xrange(self.para_count)
		])
_(LoremIpsum)

class Gate(fw.core.Widget):
	name = fw.core.Attr()
	path = fw.core.Attr()
	
	gates = {}
	
	@staticmethod
	@fw.util.decorator
	def add(method, name):
		Gate.gates[name] = method
	
	def render(self):
		self.gates[self.name](self.top, self.path, self.top._data)
	
	def create_children(self):
		pass

fw.core.widget(name='gate', public=True)(Gate)

@fw.core.api()
def send_error(data):
	from Crypto.Cipher import AES
	key = AES.new(fw.core.error_key)
	err = key.decrypt(data.decode('base64'))
	
	fw.mail.send_to_admin(html=err, subject='Error reported in your application', text=data)
	
	raise fw.core.Redirect('/')
	
