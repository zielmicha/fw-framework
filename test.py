#!/usr/bin/env python
import fw
import fw.fwml
import fw.core

import logging

_ = fw.widget(name='incrementor', public=True)
class Incrementor(fw.BaseWidget):
	def serialize(self):
		return dict(i=self.i)
	
	def unserialize(self, data):
		self.i = int(data.get('i', 0))
	
	@fw.action()
	def increment(self):
		self.i += 1
	
	def render(self):
		url = self.increment.get_action_url()
		return 'Value of this incrementor is: %d ' % self.i + ACTION % url
_(Incrementor)

ACTION = '<a href=%s>inc</a>'

_ = fw.widget(name='incrementor2', public=True)
class Incrementor2(fw.core.Container):
	i = fw.Attr('i', type=int, default=13)
	
	@fw.action()
	def increment(self):
		self.i += 1
	
	def create_children(self):
		incr = Incrementor(self)
		incr.i = 5
		#self.add_child('foo', None, incr)
	
	def render(self):
		#v = fw.fwml.Visitor(self)
		#t = v.parse('Value is %d, <button action=increment>increment</button>' % self.i)
		#t += self.get_child('foo').render()
		return ''
_(Incrementor2)

_ = fw.widget(name='incrementor3', public=True)
class Incrementor3(fw.core.Widget):
	i = fw.Attr('i', type=int, default=12)
	secret_attr = fw.Attr('secret_attr', default='ok', public=False)
	
	@fw.action()
	def increment(self, i=1):
		self.i += int(i)
	
	@fw.action()
	def set_secret(self):
		self.secret_attr = 'no'
	
	@fw.action()
	def longaction(self):
		import time
		time.sleep(5)
	
	def get_view_attrs(self):
		return dict(i=self.i, secret=self.secret_attr!='ok')
	
	def _get_fwml_text(self):
		return '''<span style="border:1px solid black; display: inline-block">
				<incrementor2 name=bar /></span><br>
			<display e=$i /> <button action=increment>+</button>
			<button action=increment(i:2)>+2</button>
			<button href=incrementor3(i:150)>To 150</button>
			<button action=increment(i:-1)>-1</button>
			<a href=secretwidget>Secret!</a>
			<a action=set_secret>Tell me secret!</a>
			<if true=$secret>
				<br>
				SECRET IS REVEALED!
			</if>
			<button action=longaction>long action</button>
			<br>
			<form action=increment(i:$hello)>
				<input name=hello type=text>
				<button submit>ok</button>
			</form>
		'''
_(Incrementor3)

_ = fw.widget(name='secretwidget')
class SecretWidget(fw.core.Widget):
	def get_view_attrs(self):
		return dict()
	
	def _get_fwml_text(self):
		return 'SECRET!'
_(SecretWidget)

_ = fw.widget(name='loginscreen', public=True)
class LoginScreen(fw.core.Widget):
	logged = fw.Attr('logged', default='', public=False)
	
	def get_view_attrs(self):
		return dict(logged=self.logged)
	
	@fw.action()
	def login(self, passwd):
		assert passwd == 'secret'
		self.logged = 'yes'
		self.top.session.put('login', True)
	
	@fw.action()
	def logout(self):
		self.logged = ''
		self.top.session.put('login', False)
	
	def _get_fwml_text(self):
		return '''
		<form action=login(passwd:$passwd)>
			Password: <input name=passwd>
			<button submit>Login</button>
		</form>
		
		<if true=logged>
			<h3>Hello, you are logged.</h3>
			<button action=logout>Logout</button>
		</if>
		<button href=requires_login>Requires login
		'''
_(LoginScreen)

_ = fw.widget(name='requires_login', public=True)
class RequiresLogin(fw.core.Widget):
	
	def init(self):
		self.is_logged = self.top.session.get('login')
		if not self.is_logged:
			self.replace_with(LoginScreen(self))
	
	def get_view_attrs(self):
		return dict(is_logged=self.is_logged)
	
	def _get_fwml_text(self):
		return '''
		<display e=is_logged />
		'''
_(RequiresLogin)