#!/usr/bin/env python
import os
import hashlib
import urllib
import logging
import string
import collections
import yaml

IS_DEVELOPMENT = 'Dev' in os.environ['SERVER_SOFTWARE']
IGNORE_BAD_SIGNS = False #IS_DEVELOPMENT

ident_letters = string.letters + string.digits + '_'

translations = collections.defaultdict(dict)

def translate(lang, text):
	#logging.info('%s: %r', lang, text)
	EN = translations.get('pl', {})
	return translations[lang].get(text, EN.get(text, text))

def add_translations(new):
	if isinstance(new, str):
		new = yaml.load(open(new))
	
	for lang, words in new.items():
		for original, translated in words.items():
			translations[lang][original] = translated

class ClassProperty(object):
	def __get__(self, instance, owner=None):
		if instance == None:
			return self
		else:
			return ClassPropertyInstance(self, instance)

class ClassPropertyInstance(object):
	def __init__(self, property, instance):
		self._property = property
		self._instance = instance
	
	def __call__(self, *args, **kwargs):
		return self._property(self._instance, *args, **kwargs)
	
	def __getattr__(self, name):
		attr = getattr(self._property, name)
		def wrapper(*args, **kwargs):
			return attr(self._instance, *args, **kwargs)
		return wrapper

def decorator(factory):
	def decorated(*args, **kwargs):
		def apply_to_obj(obj):
			return factory(obj, *args, **kwargs)
		return apply_to_obj
	decorated.__name__ = factory.__name__
	return decorated

def random_string(i=9):
	return urlsafe_b64(os.urandom(i))

def urlsafe_b64(s):
	return s.encode('base64').strip().replace('+','5').replace('/','A')\
		.replace('=', '4')

def hashsum(s):
	return urlsafe_b64(hashlib.sha256(s).digest())[:12]

def short_hashsum(s):
	return hashsum(s)[:4]

ignore_params_in_url = ('__rpc', '__rpc_render')

def sign_url(private, name, params):
	url = normal_url(name, params)
	nparams = params.copy()
	nparams['__sign'] = hashsum(private + '\0' + url)
	#logging.info(repr(private + '\0' + url))
	return normal_url(name, nparams)

def normal_url(name, params):
	sorted_params = [ (key, params[key]) for key in sorted(params)
					if key not in ignore_params_in_url and not key.startswith('_field_') ]
	return url(name, dict(sorted_params))

def urlencode(args):
	return urllib.urlencode(dict([
		(name, to_unicode(val).encode('utf8'))
		for name, val in args.items() ]))

rewrite_callback = None
translate_url_callback = None

def url(widget, args):
	args = dict([
		(name, to_unicode(val).encode('utf8'))
		for name, val in args.items() ])
	if rewrite_callback:
		widget, args = rewrite_callback(widget, args)
	else:
		widget = '/' + widget
	if args:
		return widget + '?' + urlencode(args).replace('%2C', ',')
	else:
		return widget

def parse_url(name, args):
	if translate_url_callback:
		return translate_url_callback(name, args)
	else:
		return name, args

class BadSignError(Exception): pass

def verify_url(private, name, params):
	params = params.copy()
	sign = params['__sign']
	del params['__sign']
	url = normal_url(name, params)
	good_sign = hashsum(private + '\0' + url)
	
	if good_sign != sign:
		if not IGNORE_BAD_SIGNS:
			raise BadSignError(sign, url)
		else:
			logging.info('Ignoring bad sign %r' % url)

file_cache = {}

def get_file_content(name):
	if name in file_cache and not IS_DEVELOPMENT:
		return file_cache[name]
	content = file_cache[name] = open(name).read()
	return content

def get_file_content_maybe_parted(name):
	if ':' in name:
		filename, part = name.split(':', 1)
		content = get_file_content(filename)
		parts = split_parted_file(content)
		return parts[part]
	else:
		return get_file_content(name)

def split_parted_file(content):
	parts = {}
	segments = ('\n' + content).split('\n[[PART ')
	if segments[0].strip():
		raise ValueError('Text before first part: %r' % segments[0])
	for segment in segments[1:]:
		name, rest = segment.split(']]', 1)
		name = name.strip()
		if name in parts:
			raise KeyError(name)
		parts[name] = rest
	
	return parts

def get_attr_or_item(obj, name):
	try:
		val = obj[name]
	except (KeyError, TypeError, AttributeError):
		try:
			val = obj[int(name)]
		except (ValueError, TypeError, AttributeError):
			val = getattr(obj, name)
	
	if callable(val):
		return val()
	else:
		return val

def to_str(obj):
	if isinstance(obj, str):
		return obj
	else:
		s = unicode(obj)
		return s.encode('utf8', 'replace')

def to_unicode(obj):
	if isinstance(obj, unicode):
		return obj
	else:
		return str(obj).encode('utf8', 'replace')

def reverse_dict(mapping):
	return dict( (v, k) for k, v in mapping.items() )

def get_mimetype(data):
	if 'JFIF' in data[:16]:
		return 'image/jpeg'
	elif data.startswith('\x89PNG'):
		return 'image/png'
	else:
		return 'text/plain'

def create_ident(obj):
	ident = str(obj)
	if all( ch in ident_letters for ch in ident):
		return ident
	else:
		return short_hashsum(ident)

class Event(object):
	def __init__(self):
		self.listeners = []
	
	def add(self, method):
		self.listeners.append(method)

	def call(self, *args, **kwargs):
		for listener in self.listeners:
			listener(*args, **kwargs)
	
	def call_reversed(self, *args, **kwargs):
		for listener in reversed(self.listeners):
			listener(*args, **kwargs)

def kwargs25(kwargs):
	# converts dictionary keys from str or unicode to str
	return dict([ (to_str(k),v) for k, v in kwargs.items() ])
