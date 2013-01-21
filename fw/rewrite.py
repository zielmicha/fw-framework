import re
import yaml
import collections
import logging
import urllib

handlers = []
handlers_by_name = collections.defaultdict(list)

def create_url(name, args):
	handlers = handlers_by_name[name]
	
	for template, required_args in handlers:
		if all( (required_arg in args) for required_arg in required_args  ):
			# maybe simply check if parse_url(<new_url>) == name, args
			if any( ('/' in args[arg]) for arg in required_args ):
				continue
			template_args = {}
			args = args.copy()
			for arg in required_args:
				template_args[arg] = args[arg]
				del args[arg]
			url = template % template_args
			return url, args
	
	return '/' + name, args

def parse_url(path, args):
	if not path.startswith('/'):
		path = '/' + path
	path = urllib.unquote(path)
	result = _get_handler(path)
	if not result:
		return path[1:], args
	handler, argnames, match = result
	assert len(match.groups()) == len(argnames), \
		'len %r!=len %r' % (match.groups(), argnames)
	values = match.groups()
	new_args = dict(zip(argnames, values))
	new_args.update(args)
	return handler, new_args

def _get_handler(path):
	for (pattern, argnames), template, handler  in handlers:
		match = pattern.match(path)
		if match:
			return handler, argnames, match

TEXT, GROUP = 0, 1
class ConfigParser:
	config_pattern = re.compile(r""" # from stdlib's string.py
		(?:%(delim)s(?:				
		  (?P<escaped>%(delim)s) |   # Escape sequence of two delimiters
		  (?P<named>%(id)s)      |   # delimiter and a Python identifier
		  {(?P<braced>[^}]+)}   |   # delimiter and a braced identifier
		  (?P<invalid>)              # Other ill-formed delimiter exprs
		)|(?P<text>[^$]))
		""" % dict(delim=r'\$', id=r'[_a-z][_a-z0-9]*'), re.IGNORECASE | re.VERBOSE)
	
	def convert(self, mo):
		named = mo.group('named') or mo.group('braced')
		if named is not None:
			return (GROUP, named)
		if mo.group('escaped') is not None:
			return (TEXT, '$')
		if mo.group('invalid') is not None:
			raise ValueError('Invalid expression', mo.group('invalid'))
		if mo.group('text') is not None:
			return (TEXT, mo.group('text'))
		raise ValueError('Unrecognized named group in pattern')
	
	def parse_expr(self, text):
		text = text.strip()
		if not text.startswith('/'):
			raise ValueError('Path should start with / (%r)' % text)
		matches = self.config_pattern.finditer(text)
		self.matches = map(self.convert, matches)
	
	def create_template(self):
		return ''.join(
			(
				match[1]
				if match[0] == TEXT
				else '%(' + match[1] + ')s'
			)
			for match in self.matches )
	
	def create_regex(self):
		regex = '^%s$' % ''.join(
			(
				re.escape(match[1])
				if match[0] == TEXT
				else '(.*?)'
			)
			for match in self.matches )
		groups = [ match[1] for match in self.matches if match[0] == GROUP ]
		return (re.compile(regex), groups)

def load_config():
	global handlers
	
	file = yaml.load(open('rewrite.yaml'))
	for handler, defs in file.items():
		for definition in defs:
			parser = ConfigParser()
			parser.parse_expr(definition)
			pattern, groups = parser.create_regex()
			template = parser.create_template()
			handlers.append(((pattern, groups), template, handler))
			handlers_by_name[handler].append((template, groups))

load_config()



try:
	import fw.util
	fw.util.rewrite_callback = create_url
	fw.util.translate_url_callback = parse_url
except:
	logging.exception('failed to import fw.util')


if __name__ == '__main__':
	for (p, a), t, h in  handlers:
		print p.pattern, a, t, h
	print parse_url('/city/someid', dict(h='9'))
	print parse_url('/ne', dict(h='9'))
	print parse_url('/city/someid', dict(id='otherid'))
	print create_url('city', dict(id='ident'))
	print create_url('city', {})
	print create_url('city', dict(id='ident', param='123'))