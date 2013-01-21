#!/usr/bin/env python
import logging
import urllib
import __builtin__
import operator

import fw.util
import fw.sgml

from fw.sgml import tag
from fw.util import kwargs25

@fw.util.decorator
def visits(method, names):
	for name in names.split():
		visitors[name] = method
	return method

visitors = {}

def parse_call_ex(action):
	action = action.strip()
	if '(' not in action:
		return action, [], {}
	elif not action.endswith(')'):
		raise ValueError('invalid call syntax %r' % action)
	else:
		split_symbol = ';' if ';' in action else ','
		name, args_str = action[:-1].split('(', 1)
		kwargs = {}
		args = []
		if args_str:
			for arg in args_str.split(split_symbol):
				arg = arg.strip()
				if ':' not in arg:
					args.append(arg)
				else:
					key, val = arg.split(':', 1)
					kwargs[key.strip()] = val.strip()
		return name, args, kwargs

def parse_call(action):
	name, args, kwargs = parse_call_ex(action)
	if args:
		raise ValueError('Only keywords arguments expected (got %s)' % args)
	return name, kwargs

class Visitor(object):
	def __init__(self, fwml, widget):
		self.widget = widget
		self.fwml = fwml
	
	@visits('child')
	def visit_child(self, elem):
		return fw.sgml.PlainSGML(
			self.widget.get_child(elem.attrs['name']).render() )
	
	@visits('include')
	def visit_include(self, elem):
		content = fw.util.get_file_content_maybe_parted(elem.attrs['src'])
		return self.parse(content)

	@visits('a button')
	def visit_links(self, elem):
		clazz = 'fw-link' if elem.name == 'a' else 'fw-button'
		nattrs = elem.attrs.copy()
		if 'class' in elem.attrs:
			clazz += ' ' + elem.attrs['class']
		if 'action' in elem.attrs:
			return self._generate_action_form(elem.attrs['action'], self.visit(elem.children), clazz, nattrs)
		elif 'href' in elem.attrs:
			href = elem.attrs['href']
			if '://' in href:
				return elem
			return self._generate_href_form(href, self.visit(elem.children), clazz, elem.attrs.get('target'), nattrs)
		elif 'submit' in elem.attrs:
			return tag(elem.name, self.visit(elem.children), type='submit', clazz=clazz + ' fw-submit')
		else:
			return tag(elem.name, self.visit(elem.children), self.process_attrs(elem.attrs))

	@visits('if')
	def visit_if(self, elem):
		val = self.fwml.get_if_val(elem)
		if val:
			return fw.sgml.Tags(self.visit(elem.children))
		return fw.sgml.PlainSGML('')
	
	@visits('script')
	def visit_script(self, elem):
		# Google Chrome sometimes behaves strangely when using script elements
		if elem.attrs.get('type', '').startswith('fw/'):
			return tag('fwscript', self.visit(elem.children), elem.attrs)
		else:
			return elem

	def _generate_action_form(self, action, content, clazz, attrs):
		action_name, action_args = self._parse_call(action)
		widget_url = self.widget.get_action_url(action_name, action_args)
		return tag('form', style='display:inline', action=widget_url, method='post',
			children=[
				tag('button', type='submit', children=self.visit(content), clazz=clazz,
					fw_action_url=widget_url, attrs=attrs)
		])
	
	def _generate_href_form(self, action, content, clazz, target, attrs):
		url = self._parse_href(action)
		if target == '$this':
			del attrs['target']
			if not isinstance(url, tuple):
				raise ValueError('link with target==$this not a tuple')
			top_name = self.fwml.widget.top.widget._widget_name
			widget, args = url
			str_url = fw.util.url(widget, args)
			if widget != self.fwml.widget._widget_name:
				raise ValueError('link with target==$this has to have same widget')
			href = fw.util.url(top_name, self._get_href_target_args(args))
			return tag('a', href=href,
					   children=content, clazz=clazz + ' fw-widget-link',
					   #fw_widget_link=str_url,
					   fw_link_target=self.fwml.widget.get_path(), attrs=attrs)
		else:
			if isinstance(url, tuple):
				url = fw.util.url(*url)
			return tag('a', href=url, children=content, clazz=clazz + ' fw-widget-link', attrs=attrs)
	
	def _get_href_target_args(self, url_args):
		path = self.fwml.widget.get_path() + ','
		if path == ',': path = ''
		args = dict([ (k,v) for k,v in self.fwml.widget.top._data.items()
				if not k.startswith(path) and k not in fw.util.ignore_params_in_url ])
		args.update( (path+k, v) for k,v in url_args.items() )
		return args

	def _parse_href(self, href):
		if href.startswith('$'):
			result = self.fwml._process_value(href)
			if isinstance(result, basestring):
				return result
			else:
				if isinstance(result, tuple):
					widget, args = result
				elif isinstance(result, dict):
					args = result
					widget = self.fwml.widget._widget_name
				return (widget, args)
		else:
			widget, args = self._parse_call(href)
			return (widget, args)
	
	def _create_href_url(self, name, args):
		if name not in fw.core.widgets:
			logging.warn('link to non existing widget %s', name)
			return ''
		if not fw.core.widgets[name].get_config('public'):
			return self.widget.session.sign_url(name, args)	
		else:
			return fw.util.url(name, args)

	def _parse_call(self, action):
		name, args = parse_call(action)
		return name, dict([ (key, self.fwml._process_value(val)) for key, val in args.items() ])

	@visits('form')
	def visit_form(self, elem):
		if 'action' in elem.attrs and '(' in elem.attrs['action']:
			action = elem.attrs['action']
			name, args = parse_call(action)
			
			std_args = {}
			form_args = {}
			
			for key, val in args.items():
				try:
					std_args[key] = self.fwml._process_value(val)
				except (AttributeError, KeyError):
					form_args[key] = val[1:]
			
			url = self.widget.get_action_url(name, std_args, form_args)
			
			attrs = self.process_attrs(elem.attrs)
			if 'file' in elem.attrs:
				attrs.update(enctype="multipart/form-data", fw_no_js="true")
			attrs.update(action=url, method='post')
				
			return tag('form', self.visit(elem.children), attrs=attrs)
		
		return tag('form', children=self.visit(elem.children), attrs=self.process_attrs(elem.attrs))
	
	@visits('input select textarea')
	def visit_input(self, elem):
		attrs = self.process_attrs(elem.attrs)
		if 'name' in attrs:
			attrs['name'] = '_field_' + attrs['name']
		return tag(elem.name, self.visit(elem.children), attrs=attrs)
	
	def process_attrs(self, attrs):
		return dict([ (key, self.fwml._process_value(val)) for key, val in attrs.items() ])

	#def _generate_fields_action_form(self, action_name, action_args, content, clazz):
	#	
	#	params = dict(
	#		name=action_name,
	#		args=std_args,
	#		form_args=form_args
	#	)
	#	url = self.widget.top.sign_url(params, name='')
	#	return tag('button', type='submit', children=content, clazz=clazz,
	#			   value='0', name='__form_' + urllib.quote(url))

	@visits('display')
	def visit_display(self, elem):
		return fw.util.to_str(self.fwml._process_value(elem.attrs['e']))
	
	@visits('text')
	def visit_text(self, elem):
		val = fw.util.to_str(self.fwml._process_value(elem.attrs['e']))
		return self.fwml.translate(val)
	
	@visits('t')
	def visit_t(self, elem):
		val = ''.join(map(str, self.visit(elem.children)))
		return self.fwml.translate(val)

	@visits('display-html')
	def visit_display_html(self, elem):
		return fw.sgml.PlainSGML(
			fw.util.to_str(self.fwml._process_value(elem.attrs['e']))
		)

	@visits('[root]')
	def visit_root(self, elem):
		return tag('span', fw_widget_path=self.widget.get_path(),
				   children=self.visit(elem.children))
	
	@visits('fast-foreach')
	def visit_fast_foreach(self, elem):
		list = self.fwml._process_value(elem.attrs['list'])
		dest = elem.attrs['var']
		out = []
		for item in list:
			self.fwml.widget.view_attrs[dest] = item
			out.extend( self.visit(elem.children) )
		return fw.sgml.Tags(out)

	def visit_default(self, elem):
		if elem in self.fwml.widgets:
			return fw.sgml.PlainSGML(self.fwml.widgets[elem].render())
		
		attrs = dict([ (key, self.fwml._process_value(val))
						for key, val in elem.attrs.items() ])
		return fw.sgml.Tag(elem.name, attrs, self.visit(elem.children))

	def visit(self, elem):
		if elem is None:
			return elem
		if isinstance(elem, basestring):
			return elem
		if isinstance(elem, list):
			return map(self.visit, elem)
		
		try:
			return visitors.get(elem.name, Visitor.visit_default)(self, elem)
		except Exception, err:
			if not hasattr(err, '_fwml_was_warned'):
				if not elem or elem.warn(err):
					err._fwml_was_warned = True
			raise
	
	def parse(self, text):
		return self.visit(create_tree(text))

class FWML(object):
	def __init__(self, widget, text):
		self.widget = widget
		self.widgets = {}
		self.children_created = False
		if isinstance(text, fw.sgml.TagBase):
			self.tag = text
		elif isinstance(text, list):
			self.tag = fw.sgml.tag('[root]', children=text)
		else:
			self.tag = create_tree(text)
	
	def create_children(self):
		def visit(tag):
			if tag.name == 'if':
				return not self.get_if_val(tag)
			if tag.name in fw.core.widgets:
				self._add_child(tag)
				return True
			else:
				return False
		
		self.tag.visit(visit)
		self.children_created = True
	
	def _add_child(self, tag):
		if 'name' in tag.attrs:
			name = tag.attrs['name']
		else:
			name = fw.util.hashsum(repr(tag) + repr(getattr(tag, 'pos', '')))
		
		widget = self.create_widget_from_tag(tag)
		self.widgets[tag] = widget
		self.widget.add_child(name, None, widget)
		
	def create_widget_from_tag(self, tag):
		widget_cls = fw.core.widgets[tag.name]
		widget = widget_cls(self.widget)
		
		attrs = dict([ (key, self._process_value(val))
						for key, val in tag.attrs.items()
						if key not in reserved_tag_attrs ])
		
		widget.init_with_data(attrs)
		widget.contains_fwml = tag.children
		return widget
	
	def get_if_val(self, elem):
		try:
			cond = elem.attrs['true']
			reverse = False
		except KeyError:
			cond = elem.attrs['false']
			reverse = True
		val = self._process_value(cond)
		if reverse:
			val = not val
		return val

	def _process_value(self, value):
		def get_widget_parents():
			current = self.widget
			list = [current]
			while isinstance(current, fw.core.InsideWidget):
				current = current.parent
				list.append(current)
			return list
		
		if not value:
			return value
		if value.startswith('$'):
			if '(' in value:
				name, args, kwargs = parse_call_ex(value[1:])
				kwargs = dict([ (key, self._process_value(val)) for key, val in kwargs.items() ])
				args = map(self._process_value, args)
				val = None
				lookup = get_widget_parents() + [__builtin__, operator, FwmlFunctions]
				for obj in lookup:
					try:
						val = getattr(obj, name)
					except AttributeError:
						continue
					else:
						break
				if not val:
					raise AttributeError('No such function %r' % name)
				return val(*args, **kwargs25(kwargs))
			else:
				var = value[1:]
				segments = var.split('.')
				value = self.widget.get_view_attr(segments[0])
				for attr in segments[1:]:
					value = fw.util.get_attr_or_item(value, attr)
				return value
		else:
			return value

	def render(self):
		assert self.children_created, 'rendering objects without created children'
		visitor = Visitor(self, self.widget)
		return str(visitor.visit(self.tag))
	
	def translate(self, text):
		return fw.util.translate(self.widget.session.get('lang', 'pl'), text)
	
reserved_tag_attrs = ('name', )

cache = {}

def create_tree(text):
	if text not in cache:
		cache[text] = fw.sgml.create_tree(text)
	return cache[text]

import math
import json

class FwmlFunctions:
	@staticmethod
	def ceil(x):
		return int(math.ceil(float(x)))
		
	@staticmethod
	def json(obj):
		return json.dumps(obj)

