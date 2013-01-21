#!/usr/bin/env python
import re
import warnings
import traceback
import logging
import cgi

token_re = re.compile(r'(<!--(.*?)-->)|(<!\[CDATA\[(.*?)\]\]>)|(<\s*(/?)\s*\S+?(\s+\S+?(=\s*(".*?"|\S*?))?)*\s*(/?)\s*>)|([^<]+)', re.DOTALL)

def get_error_offset(text, start):
	text_to_start = text[:start]
	text_to_start_lines = text_to_start.splitlines() or ['']
	lineno = len(text_to_start_lines)
	offset = len(text_to_start_lines[-1]) + 1
	all_lines = text.splitlines() or ['']
	line = all_lines[len(text_to_start_lines) - 1]
	return lineno, offset, line

def warn_syntax(msg, text, start, err='Syntax Error'):
	lineno, offset, line = get_error_offset(text, start)
	logging.error('%s: %s; line %d, offset %d; %s' % (err, msg, lineno, offset, line.strip()))

def tokenize(input):
	if isinstance(input, str):
		input = input.decode('utf-8')
	
	last_end = 0
	for match in re.finditer(token_re, input):
		if match.start(0) != last_end:
			warn_syntax('Invalid syntax', input, last_end)
		last_end = match.end(0)
		yield (input, match.start(0), match.group(0))
	
	if last_end != len(input):
		warn_syntax('Invalid syntax', input, last_end)

def parse_token(text, start, token):
	def assert_ends(s):
		if not token.endswith(s):
			warn_syntax('Token %r does not end with %r' % (token, s), text, start)
	
	if token.startswith('<!--'):
		assert_ends('>')
		return None
	
	if token.startswith('<![CDATA['):
		assert_ends(']]>')
		return token[len('<![CDATA['): -len(']]>')]
	
	if token.startswith('<'):
		assert_ends('>')
		return parse_tag(text, start, token[1:-1])
	
	return token

OPEN, CLOSE, SELFCLOSE = range(3)

def parse_tag(text, start, tag):
	type = OPEN
	tag = tag.strip()
	tag_split = tag.split(None, 1)
	if len(tag_split) == 1:
		tagname = tag_split[0]
		rest = ''
	else:
		tagname, rest = tag_split
	tagname = tagname.strip()
	if tagname.startswith('/'):
		type = CLOSE
		tagname = tagname[1:].strip()
	rest = rest.strip()
	
	if rest.endswith('/'):
		type = SELFCLOSE
		rest = rest[:-1].strip()
	
	if (rest.count('"') % 2) != 0: 
		warn_syntax('Odd number of "', text, start)
	tokens = tokenize_attributes(rest)
	
	attrs = []
	while tokens:
		token = tokens.pop()
		if token.endswith('='):
			token = token[:-1]
		if tokens and tokens[-1].endswith('='):
			key = tokens.pop()[:-1]
			attrs.append((key, token))
		else:
			attrs.append((token, None))
	return (type, tagname, attrs, text, start)
	
def tokenize_attributes(attrs):
	tokens = []
	token = []
	quoted_mode = False
	for ch in attrs:
		if quoted_mode:
			if ch == '"':
				tokens.append(''.join(token))
				token = []
				quoted_mode = False
			else:
				token.append(ch)
		elif ch in ' \n\t\r':
			tokens.append(''.join(token))
			token = []
		elif ch == '=':
			token.append('=')
			tokens.append(''.join(token))
			token = []
		elif ch == '"':
			tokens.append(''.join(token))
			token = []
			quoted_mode = True
		else:
			token.append(ch)
	if token:
		tokens.append(''.join(token))
	return filter(lambda x: x, tokens) # only nonempty tokens

def get_parsed_tokens(input):
	return [ parse_token(text, start, token) for (text, start, token) in tokenize(input) ]

class TagBase(object): pass

SCRIPT_ELEMENTS = ('script', 'fwscript', )
NEEDCLOSE_ELEMENTS = SCRIPT_ELEMENTS + ('textarea', 'iframe', 'canvas')

class Tag(TagBase):
	def __init__(self, name, attrs, children=None):
		self.name = name
		self.children = [] if children is None else children
		self.attrs = dict(attrs)
	
	def repr(self):
		def q(k, s):
			if s == None or s == True:
				return ''
			if type(s) not in (str, unicode):
				raise TypeError('Argument value has bad type (key=%r, val=%r)' % (k, s))
			if len(s.split()) > 1 or cgi.escape(s) != s or s == '':
				return u'="%s"' % to_unicode(cgi.escape(s))
			return u'='+s
		
		children = self.children_to_string()
		attrs = u' '.join( u'%s%s' % (k,q(k,v)) for k, v in self.attrs.items() if v != False)
		if attrs: attrs = ' ' + attrs
		if not children and self.name not in NEEDCLOSE_ELEMENTS:
			val = u'<%s%s />' % (self.name, attrs)
		else:
			val = u'<%s%s>%s</%s>' % (self.name, attrs, children, self.name)
		return unicode(val)
	
	def __repr__(self):
		return self.repr().encode('utf8')

	def children_to_string(self):
		if self.name in SCRIPT_ELEMENTS:
			childstr = [ to_unicode(ch) for ch in self.children ]
			return u'<!--\n %s \n//-->' % u''.join(childstr)
		
		def str_child(child):
			if child is None:
				return ''
			elif isinstance(child, basestring):
				return to_unicode(cgi.escape(child))
			else:
				return child.repr()
		
		return u''.join(map(str_child, self.children))
	
	def visit(self, func):
		stop_visiting = func(self)
		if not stop_visiting:
			for child in self.children:
				if isinstance(child, Tag):
					child.visit(func)
	
	def warn(self, msg, err='Error'):
		if not hasattr(self, 'pos') or not self.pos:
			return False
		else:
			apply(warn_syntax, [msg] + list(self.pos), dict(err=err)) # for python2.5
			return True

def to_str(obj):
	str = unicode(obj)
	return str.encode('utf8', 'replace')

def to_unicode(obj):
	if isinstance(obj, unicode):
		return obj
	else:
		return str(obj).decode('utf8')

class PlainSGML(TagBase):
	def __init__(self, sgml):
		self.sgml = to_unicode(sgml)
	
	def repr(self):
		return self.sgml

class Tags(TagBase):
	def __init__(self, tags):
		self._tag = Tag(None, (), tags)
	
	def repr(self):
		return self._tag.children_to_string()

def tag(name_, children=[], attrs={}, clazz=None, *children_extra, **attrs_extra):
	attrs = attrs.copy()
	attrs.update(attrs_extra)
	if clazz is not None:
		if 'class' in attrs:
			attrs['class'] += ' ' + clazz
		else:
			attrs['class'] = clazz
	return Tag(name_, attrs, children + list(children_extra))

SELF_CLOSING = frozenset('img br input link meta'.split())

def create_tree(tokens, self_closing=SELF_CLOSING):
	root = Tag('[root]', [])
	current = root
	stack = []
	for token in get_parsed_tokens(tokens):
		if isinstance(token, tuple):
			type, name, attr, text, start = token
			if name in SELF_CLOSING:
				type = SELFCLOSE
			if type == OPEN:
				newtag = Tag(name, attr)
				newtag.pos = (text, start)
				current.children.append(newtag)
				stack.append(current)
				current = newtag
			elif type == SELFCLOSE:
				newtag = Tag(name, attr)
				newtag.pos = (text, start)
				current.children.append(newtag)
			elif type == CLOSE:
				if name != current.name:
					warn_syntax("Invalid closing tag, expected %r, found %r" % (current.name, name), text, start)
					while stack and name != current.name:
						current = stack.pop()
				if stack:
					current = stack.pop()
				else:
					warn_syntax("Invalid closing tag, expected [eof], found %r" % name, text, start)
		else:
			current.children.append(token)
	return root

if __name__ == '__main__':
	T = '<img title="prettyimage is here" nouserselect src=./hello.png><b>a</p>'
	print create_tree(T)