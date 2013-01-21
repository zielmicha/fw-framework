import logging

import fw.core
import fw.db
import fw.login.social

users = fw.db.DBDict('login.users')
aliases = fw.db.DBDict('login.aliases')

providers = {}

class UserSession(dict):
	def __init__(self, userid):
		self.userid = userid
	
	@property
	def provider(self):
		return provider[self.userid.split(':',1)[0]]
	
	@property
	def user(self):
		return fw.login.social.get_user(self.userid)

fw.core.possible_widget_config_values.append('requires_login')

class AccountHook(fw.core.Hook):
	def init(self):
		self.logged_user = self.top._session.get('logged_user')
		if not self.logged_user:
			if self.top.widget.get_config('requires_login'):
				self.top.redirect('login.form', url=self.top.get_old_url())
			return
		
		storage = users.get(self.logged_user, {})
		self.original_storage = storage.copy()
		self.storage = UserSession(self.logged_user)
		self.storage.update(storage)
		self.top.session = self.storage
	
	def destroy(self):
		if not self.logged_user:
			return
		if self.original_storage != self.storage:
			users[self.logged_user] = self.storage

fw.core.hook(AccountHook)

class Account(object):
	def __init__(self, widget):
		self.widget = widget
		self.top = widget.top
		self.logged_user = self.top.session.userid
		provider, rest = self.logged_user.split(':', 1)
		self.provider = providers[provider]
	
	def logout(self):
		self.provider.logout(self.top)
		self.top.redirect('start')

class AdminLogin(fw.core.Widget):
	view = 'fw/login/login.fwml:admin'
	
	@fw.core.action()
	def login(self, userid):
		self.top._session['logged_user'] = userid
	
	@fw.core.action()
	def set_sess(self, key, val):
		logging.info(self.top.session)
		self.top.session[key] = val
	
	@fw.core.action()
	def add_testuser(self, name):
		import fw.login.testuser
		fw.login.testuser.add(name)
	
	def get_view_attrs(self):
		return dict(logged=self.top._session.get('logged_user'))

fw.core.widget(name='admin.login', admin=True, public=True)(AdminLogin)

class LoginForm(fw.core.Widget):
	view = 'fw/login/login.fwml:form'
	
	url = fw.core.Attr()
	fail = fw.core.Attr(default=None)
	
	def get_view_attrs(self):
		if self.top._session.get('logged_user'):
			self.top.redirect(self.url)
		else:
			return dict(url=self.url, fail=self.fail)
	
	@fw.core.action()
	def login(self, provider, url):
		providers[provider].login(self.top, url)
	
fw.core.widget(name='login.form', public=True)(LoginForm)

@fw.core.global_action()
def login_do(self, provider, url):
	try:
		id = providers[provider].verify_login(self)
		if not id:
			raise LoginError
		if ':' not in id:
			raise ValueError('bad user id %r' % id)
		self.top._session['logged_user'] = id
	except LoginError:
		self.redirect('login.form', url=url, fail='login')
	else:
		if not url.startswith('/'):
			url = '/' + url
		self.redirect(url)

def get_login_url(top, provider, url):
	return login_do.get_action_url(top, dict(provider=provider, url=url))

@fw.core.global_action()
def logout_do(self):
	self.top._session['logged_user'] = None
	self.redirect('/')

def get_logout_url(top):
	return logout_do.get_action_url(top)

class LoginProvider(object):
	pass

class LoginError(Exception):
	pass
