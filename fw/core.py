#!/usr/bin/env python

import yaml
import urllib
import datetime
import json
import logging
import cgi
import sys

import fw.session
import fw.util
import fw.fwml
import fw.user
from fw import cgitb

options = yaml.load(open('fw.yaml'))
widgets = {}

possible_widget_config_values = ['public', 'admin']

class InternalError(Exception): pass

def run_widget(self, path):
	try:
		data = dict( (arg, self.request.get(arg)) for arg in self.request.arguments() )
		widget_name, args = fw.util.parse_url(path, data)
		widget = widgets[widget_name or 'start']
		return widget.run_this_widget(self, args)
	except:
		logging.exception('during handling request')
		html = cgitb.html(sys.exc_info())
		show_error(self, html)

error_key = 'fhnOJwgZo0XTS5Nv'

def show_error(self, html):
	self.response.set_status(500)
	if fw.user.is_admin():
		self.response.out.write(html)
	else:
		from Crypto.Cipher import AES
		key = AES.new(error_key)
		size = int((len(html) // 16 + 1) * 16)
		self.response.out.write('''<h1>Internal Server Error</h1>
			<form action=/api/send_error method=post>
				<input type=submit value=Powiadom class=fw-button>
				<br>
				<textarea name=data onfocus="return false" onkeydown="return false"
				cols=1 rows=1 style="opacity: 0.1;">
%s</textarea>'''
			% key.encrypt(html.rjust(size)).encode('base64'))

@fw.util.decorator
def widget(clazz, name=None, **conf):
	clazz._widget_name = name
	assert all(map(possible_widget_config_values.__contains__, conf.keys()))
	clazz.config = conf
	if name:
		widgets[name] = clazz
	clazz._init_class()
	return clazz

@fw.util.decorator
def action(method):
	return Action(method)

class Action(fw.util.ClassProperty):
	def __init__(self, method):
		self.method = method
		self.name = self.method.__name__
	
	def __call__(self, widget, *args, **kwargs):
		return self.method(widget, *args, **kwargs)
	
	def get_action_url(self, widget, args={}, varargs={}):
		return widget.get_action_url(self.name, args, varargs)

NO_DEFAULT = object()
class Attr(object):
	def __init__(self, name=None, type=None, default=NO_DEFAULT, public=True):
		self.name = name
		self.type = type or (lambda x:x)
		self.default = default
		self.public = public
	
	def serialize(self, val):
		if val == self.default:
			return None
		else:
			return self._serialize(val)
	
	def unserialize(self, val):
		if val is None:
			if self.default is NO_DEFAULT:
				raise KeyError(self.name)
			else:
				return self.default
		else:	
			return self._unserialize(val)
	
	def _serialize(self, val):
		return unicode(val)
	
	def _unserialize(self, val):
		return self.type(val)

class BoolAttr(Attr):
	def _serialize(self, val):
		return 'true' if val else 'false'
	
	def _unserialize(self, val):
		if val.lower() == 'false':
			return False
		else:
			return bool(val)

class ActionOwner(object):
	@classmethod
	def _init_class(cls):
		cls.actions = getattr(cls.__base__, 'actions', {}).copy()
		cls.attrs = getattr(cls.__base__, 'attrs', {}).copy()
		for key in cls.__dict__.keys():
			val = getattr(cls, key)
			if isinstance(val, Action):
				cls.actions[key] = val
			elif isinstance(val, Attr):
				delattr(cls, key)
				if not val.name:
					val.name = key
				val.owner = cls
				cls.attrs[key] = val
	
	def get_action_url(self, name, args={}, varargs={}):
		return self.top.get_action_url_with_target(name, self.get_path(), args, varargs)
	
	def call_action(self, name, args):
		self.updated = True
		action = self.actions[name]
		val = action(self, **dict([ (str(k), v) for k, v in args.items() ]))
		if self.updated:
			self.was_updated()
	
	def was_updated(self):
		pass

PAGE_TEMPLATE = open('page-template.html').read()

class Redirect(Exception):
	def __init__(self, dest):
		self.dest = dest

class Global(ActionOwner):
	actions = {}
		
	on_create = fw.util.Event()
	
	@classmethod
	def run_render(cls, env):
		if not cls.get_config('public', False):
			raise InternalError('widget not public')
		self = cls()
		self._env = env
		return self._run_render_widget()
	
	@classmethod
	def run_widget(cls, widget_cls, env, args):
		self = cls()
		self._env = env
		self._data = args
		self.widget_cls = widget_cls
		return self._run_render_widget()
	
	def __init__(self):
		self.top = self
		self.on_destory = fw.util.Event()

	def _run_render_widget(self):
		try:
			self._prepare()
			self._check_widget()
			kind, param = self._get_kind()
			self.widget.unserialize(self._data)
			if not self.widget.is_public():
				self.verify_my_url()
			self._render_or_action(kind, param)
		except Redirect, redirect:
			# what about __rpc=true requests?
			self._render_redirect(redirect.dest)
		finally:
			self._destroy()
	
	def _prepare(self):
		self._req = self._env.request
		self._resp = self._env.response
		self._create_or_get_sessid()
		self.widget = self.widget_cls(self)
		self.on_create.call(self)
	
	def _destroy(self):
		self.on_destory.call_reversed()
		if hasattr(self, '_session'):
			self._session.flush()
	
	def _set_cookie(self, key, val, weeks=2):
		expires = datetime.datetime.now() + datetime.timedelta(weeks=2)
		expires_rfc822 = expires.strftime('%a, %d %b %Y %H:%M:%S GMT')
		cookie = "%s=%s;expires=%s;path=/" % (key, val, expires_rfc822)
		self._resp.headers['set-cookie'] = cookie
	
	def _create_or_get_sessid(self):
		fw.session.create_or_get_session(self)
	
	def _check_widget(self):
		if not self.widget.is_public():
			self.verify_my_url()
		
		if self.widget.get_config('admin'):
			if not fw.user.is_admin():
				my_url = self.widget._widget_name + '?' + fw.util.urlencode(self._data)
				login_url = fw.user.create_login_url(my_url)
				self._env.redirect(login_url)
	
	def _get_kind(self):
		if '__action' in self._data:
			action = self._prepare_action()
			return ('action', action)
		else:
			return ('render', None)
	
	def _prepare_action(self):
		action_name = self._data['__action']
		action_target = self._data['__action_target']
		action_args = {}
		if self._data.get('__action_varargs'):
			varargs = dict([ item.split(',', 1)
			for item in self._data['__action_varargs'].split(';') ])
			for key, field_name in varargs.items():
				action_args[key] = self._data.get('_field_' + field_name)
		
		if self._data['__action_args']:
			for key in self._data['__action_args'].split(','):
				action_args[key] = self._data['__action_args_' + key]
		if '__blob' in action_args:
			del action_args['__blob']
			is_blob = True
		else:
			is_blob = False
		self.verify_my_url()
		return (is_blob, action_target, action_name, action_args)
	
	def _render_or_action(self, kind, params):
		if kind == 'action':
			self._do_action(*params)
		else:	
			self.render_custom()
	
	def _render_redirect(self, url):
		if '__rpc' in self._data:
			self._resp.headers['content-type'] = 'text/plain'
			if '__action' in self._data:
				json.dump({'redirect': url}, self._resp.out)
				return
			elif url.startswith('/') and not url.startswith('/_ah/'):
				if '?' in url: url += '&__rpc=true'
				else: url += '?__rpc=true'
			else:
				#raise Exception('cannot handle outside redirects in rpc requests (%r)', url)
				js = '<script>location.replace(unescape("%s"))</script>' % urllib.quote(url)
				self._resp.out.write(js)
				return
		self._env.redirect(url)
	
	def render_custom(self):
		if '__rpc' in self._data:
			self._resp.headers['content-type'] = 'text/plain'
			widget = self.get_child_with_path(self._data.get('__rpc_render', ''))
			content = widget.render()
		else:
			rendered = self.widget.render()
			title = self.widget.get_title()
			content = PAGE_TEMPLATE.replace('[content]', rendered)\
				.replace('[title]', cgi.escape(title) or '')
		self._resp.out.write(content)
	
	def verify_my_url(self):
		self._session.verify_url(self.widget._widget_name, self._data)
	
	def sign_url(self, params, name=None):
		if name is None:
			name = self.widget._widget_name
		return self._session.sign_url(name, params)
	
	def	_do_action(self, is_blob, target_path, name, params):
		target = self.get_child_with_path(target_path)
		result = target.call_action(name, params)
		if is_blob:
			self._render_blob(result)
		else:
			self._render_after_action()
	
	def _render_blob(self, result):
		if not isinstance(result, BlobValue):
			result = BlobValue(result)
		result.render(self)
		
	def _render_after_action(self):
		if '__rpc' in self._data:
			self._render_updates()
		else:
			self._redirect_to_view()
	
	def _render_updates(self):
		response = {}
		response['updates'] = self.widget.render_updated()
		response['url'] = self.get_new_url()
		json.dump(response, self._resp.out)
	
	def _redirect_to_view(self):
		self._env.redirect(self.get_new_url())
	
	def get_new_url(self):
		query = self.widget.serialize()
		if self.widget.is_public():
			return fw.util.url(self.widget._widget_name, query)
		else:
			return self.sign_url(query)
	
	def get_old_url(self, update={}):
		data = dict( (k, v) for k, v in self._data.items() if not k.startswith('__rpc') )
		data.update(update)
		if self.widget.is_public():
			return fw.util.url(self.widget._widget_name, data)
		else:
			return self.sign_url(query)

	def get_action_url_with_target(self, name, target, args, varargs):
		params = {}
		params['__action_args'] = ','.join(args.keys())
		for key, val in args.items():
			params['__action_args_' + key] = val
		if target == '_global':
			params.update(
					__action=name,
					__action_target='_global'
				)
			return self.sign_url(params, name='_global')
		else:
			params.update(self.widget.serialize())
			params['__action'] = name
			params['__action_target'] = target
			params['__action_varargs'] = ';'.join( '%s,%s' % (key, val)
												  for key, val in varargs.items() )
			return self.sign_url(params)
	
	def get_path_of_child(self, child):
		assert child is self.widget, '%s != %s' % (child, self.widget)
		return ''
	
	def get_path(self):
		return '_global'
	
	def get_child_with_path(self, path):
		if path == '_global':
			return self
		
		if path.startswith(','):
			path = path[1:]
		
		if not path:
			return self.widget
		else:
			return self.widget.get_child_with_path(path)
	
	def redirect(self, obj=None, **args):
		if not args and isinstance(obj, basestring) and '/' in obj:
			url = obj
		else:
			name = obj or self.widget._widget_name
			url = fw.util.url(name, args)
		raise Redirect(url)

class BaseWidget(ActionOwner):
	def __init__(self, parent):
		self.top = parent.top
		self.parent = parent
		self.only_public_attrs = True
		self.dont_serialize_attrs = {}
		self.init()
	
	@property
	def session(self):
		return self.top.session
	
	@classmethod
	def run_this_widget(cls, env, args):
		return Global.run_widget(cls, env, args)
	
	def was_updated(self):
		pass

	def init(self):
		pass
	
	def init_with_data(self, params):
		attrs = type(self).attrs
		for key, val in params.items():
			attr = attrs[key]
			val = attr.unserialize(val)
			self.dont_serialize_attrs[key] = val
			setattr(self, key, val)

	def serialize(self):
		self.only_public_attrs = True
		data = {}
		for name, attr in type(self).attrs.items():
			val = getattr(self, name)
			if name in self.dont_serialize_attrs:
				if self.dont_serialize_attrs[name] == val:
					continue
			serialized = attr.serialize(val)
			if serialized != None:
				if not attr.public:
					self.only_public_attrs = False
				data[attr.name] = serialized
		return data
	
	def unserialize(self, data):
		for name, attr in type(self).attrs.items():
			if not attr.public and data.get(name, None):
				self.only_public_attrs = False
			if not hasattr(self, name) or data.get(name, None):
				setattr(self, name, attr.unserialize(data.get(attr.name, None)))
	
	def get_title(self):
		return getattr(self, 'title', self._widget_name)
	
	def render_updated(self):
		if self.updated:
			return { self.get_path(): self.render() }
	
	def is_public(self):
		return type(self).get_config('public') and self.only_public_attrs
	
	@classmethod
	def get_config(cls, val, default=None):
		return cls.config.get(val, default)
		
	def get_path(self):
		return self.parent.get_path_of_child(self)
	


class Container(BaseWidget):
	def __init__(self, parent):
		self.children = {}
		self._children_only_name = {}
		self._reverse_children = {}
		
		BaseWidget.__init__(self, parent)
	
	def unserialize(self, data):
		self.unserialize_widget(data)
		self.after_unserialize()
		self.create_children()
		self.unserialize_children(data)
	
	def after_unserialize(self):
		pass
	
	def unserialize_children(self, data):
		self._unserialized_from = data
		for symbolic_name, child in self.iter_children():
			params = Container._get_params_for_child(data, symbolic_name)
			child.unserialize(params)
	
	def recreate_children(self):
		self.children = {}
		self._children_only_name = {}
		self._reverse_children = {}
		self.create_children()
		self.unserialize_children(self._unserialized_from)
	
	def unserialize_widget(self, data):
		BaseWidget.unserialize(self, data)
	
	def serialize(self):
		data = self.serialize_widget()
		data.update(self.serialize_children())
		return data
	
	def serialize_children(self):
		data = {}
		for symbolic_name, child in self.iter_children():
			data_of_child = child.serialize()
			for key, val in data_of_child.items():
				data[symbolic_name + key] = val
		return data
	
	def serialize_widget(self):
		return BaseWidget.serialize(self)

	def iter_children(self):
		for (name, second_hash), child in self.children.items():
			startswith = self._create_child_name(second_hash, name) + ','
			yield startswith, child
	
	def _create_child_name(self, hash, name):
		if hash:
			return hash + '-' + name
		else:
			return name
	
	@staticmethod
	def _get_params_for_child(data, symbolic_name):
		params = {}
		for key, val in data.items():
			if key.startswith(','):
				key = key[1:]
			if key.startswith(symbolic_name):
				params[key[len(symbolic_name):]] = val
		
		return params
	
	def add_child(self, name, second_name, widget):
		second_hash = Container._hash_second_name(second_name)
		if '-' in name or '-' in second_hash:
			raise ValueError('%r or %r contains "-"' % (name, second_hash))
		if (name, second_hash) in self.children:
			raise ValueError('Child with same attributes aleardy exists')
		self.children[(name, second_hash)] = widget
		self._children_only_name[name] = widget
		self._reverse_children[widget] = (name, second_hash)
	
	def get_child(self, name, second_hash=None):
		if (name, second_hash) in self.children:
			return self.children[(name, second_hash)]
		if name in self._children_only_name:
			return self._children_only_name[name]
		raise KeyError((name, second_hash))
	
	@staticmethod
	def _hash_second_name(second_name):
		if second_name == None:
			return ''
		else:
			return fw.util.short_hashsum(repr(second_name))
	
	def get_path_of_child(self, child):
		my_path = self.get_path()
		if my_path:
			return my_path + ',' + self.get_child_name(child)
		else:
			return self.get_child_name(child)
	
	def get_child_name(self, child):
		name, second_hash = self._reverse_children[child]
		return self._create_child_name(second_hash, name)

	def get_child_with_path(self, path):
		if ',' not in path:
			if '-' in path:
				second_hash, name = path.split('-', 1)
				return self.get_child(name, second_hash)
			else:
				return self.get_child(path)
		else:
			child, rest = path.split(',', 1)
			return self.get_child_with_path(child).get_child_with_path(rest)
	
	def is_public(self):
		return BaseWidget.is_public(self) and all([
				ch.is_public for ch in self.children.values() ])
	
	def render_updated(self):
		if self.updated:
			return BaseWidget.render_updated(self)
		else:
			widgets = {}
			for widget in self.children.values():
				update = widget.render_updated()
				if update:
					widgets.update(update)
			return widgets

class Widget(Container):
	def __init__(self, parent):
		Container.__init__(self, parent)
		self.updated = False
		self._fwml = None
		self._view_attrs = None
	
	@property
	def fwml(self):
		if not self._fwml:
			self._fwml = fw.fwml.FWML(self, self._get_fwml_text())
		return self._fwml
	
	def create_children(self):
		return self.fwml.create_children()
	
	def was_updated(self):
		# action may have changed something
		self._view_attrs = None
		# and children may also have changed
		self.recreate_children()

	def get_view_attr(self, name):
		return self.view_attrs[name]
		
	@property
	def view_attrs(self):
		if self._view_attrs == None:
			self._view_attrs = self.get_view_attrs()
		return self._view_attrs

	def render(self):
		return self.fwml.render()
	
	def _get_fwml_text(self):
		if self.view:
			return fw.util.get_file_content_maybe_parted(self.view)
		else:
			return ''
	
	def create_widget_from_children(self, vars):
		all_vars = self.view_attrs.copy()
		all_vars.update(vars)
		return AnonymousFWML(self, self.contains_fwml, all_vars)
	
	def wrap_html(self, html):
		path = fw.util.to_str(cgi.escape(self.get_path()))
		return '<span fw_widget_path="%s">%s</span>' % (path, fw.util.to_str(html))
	
	def translate(self, text):
		return fw.util.translate(self.session.get('lang', 'pl'), text)

class InsideWidget(object): pass

class AnonymousFWML(Widget, InsideWidget):
	def __init__(self, parent, fwml, vars):
		Widget.__init__(self, parent)
		self.fwml_text = fwml
		self.vars = vars
	
	def get_view_attrs(self):
		return self.vars
	
	def _get_fwml_text(self):
		return self.fwml_text
	
	def call_action(self, name, args):
		return self.parent.call_action(name, args)


AnonymousFWML._init_class()

api_methods = {}

@fw.util.decorator
def api(method):
	name = method.__name__
	api_methods[name] = method

@fw.util.decorator
def blob(method):
	return Blob(method)

@fw.util.decorator
def global_blob(method):
	blob = Blob(method)
	Global.actions[method.__name__] = blob
	return blob

@fw.util.decorator
def global_action(method):
	action = Action(method)
	Global.actions[method.__name__] = action
	return action

class BlobValue(object):
	def __init__(self, data, mimetype=None, cache=False):
		if not mimetype:
			mimetype = fw.util.get_mimetype(data)
		self.mimetype = mimetype
		self.cache = cache
		self.data = data
	
	def render(self, glob):
		if self.cache:
			glob._resp.headers['Expires'] = 'Mon, 01 Jan 2300 00:00:00 GM'
			glob._resp.headers['Cache-Control'] = 'public'
		glob._resp.headers['Content-Type'] = self.mimetype
		glob._resp.out.write(self.data)

class Blob(Action):
	def __init__(self, method):
		self.method = method
		self.name = self.method.__name__
	
	def get_blob_url(self, widget, args={}):
		args = args.copy()
		args['__blob'] = 'true'
		return self.get_action_url(widget, args)

class Hook(object):
	@classmethod
	def _init(cls, top):
		self = cls(top)
		top.on_destory.add(self.destroy)
	
	def __init__(self, top):
		self.top = top
		self.init()
	
	def destroy(self):
		pass

def hook(cls):
	Global.on_create.add(cls._init)
	return hook

def init():
	for module in options['modules']:
		__import__(module)
