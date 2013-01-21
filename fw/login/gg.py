import logging
import yaml
import urllib

import fw.login
import fw.login.ggapi as ggapi
import fw.login.social as social
import fw.core
import fw.util
import fw.db
import fw.widgets

GG_URL = 'http://gg.pl/#apps/%(app)s%(path)s'
RETURN_URL = 'http://%(host)s/gate/login.gg/%(path)s'
AUTH_URL = 'https://www.gg.pl/authorize'

if fw.util.IS_DEVELOPMENT:
	API = dict(key='720583283a23d16b2efa99691f7ebdef', secret='27adbe2722c48ac4547400c782a30384',
			   host='localhost:8010', appname='cgametest')
else:
	API = yaml.load(open('ggapi.yaml'))

gg_tokens = fw.db.DBDict('login.gg.tokens')

def get_return_url(path=''):
	if path.startswith('/'): path = path[1:]
	return RETURN_URL % dict(host=API['host'], path=path)

def get_authorize_url(path):
	return AUTH_URL + '?' + urllib.urlencode(dict(
		response_type='code',
		client_id=API['key'],
		scope='pubdir users life',
		redirect_uri=get_return_url(path)
	))

class GGProvider(fw.login.LoginProvider):
	@classmethod
	def login(cls, top, redirect_url):
		url = get_authorize_url(redirect_url)
		top.redirect(url)
	
	@classmethod
	def verify_login(cls, top):
		if 'gg.uin' not in top._session:
			raise LoginError
		return 'gg:' + top._session['gg.uin']
	
	@classmethod
	def logout(cls, top):
		fw.login.logout_do(top)
	
	@classmethod
	def get_user(cls, id):
		return GGUser(id)

fw.login.providers['gg'] = GGProvider

@fw.widgets.Gate.add('login.gg')
def login(top, path, args):
	if 'code' not in args:
		top.redirect('/') # todo: login
	code = args['code']
	client = ggapi.GG(API['key'], API['secret'], get_return_url(path), code=code)
	profile = client.get_user()['users'][0]
	uin = profile['id']
	top._session['gg.uin'] = uin
	gg_tokens[uin] = (client.access_token, client.refresh_token)
	top.redirect(fw.login.get_login_url(top, provider='gg', url=path))

class GGUser(object):
	def __init__(self, id):
		uin = id.split(':',1)[1]
		token = gg_tokens[uin]
		self.id = id
		self.client = ggapi.GG(API['key'], API['secret'], get_return_url(),
								   access_token=token[0], refresh_token=token[1])
	
	def client_call(self, func, args, part=None, default=None):
		funcobj = getattr(self.client, func)
		try:
			if part:
				return funcobj(*args)[part]
			else:
				return funcobj(*args)
		except:
			logging.exception('when quering GGAPI')
			return default
	
	def get_friends(self):
		resp = self.client_call('get_friends', (), part='friends', default=[])
		return [
			social.Friend(self.id, id='gg:' + friend['id'], name=friend['label'], desc=friend['id'])
			for friend in resp ]
	
	def get_profile(self):
		info_list = self.client_call('get_user', (), 'users', None)
		if not info_list:
			return social.Profile()
		logging.info(info_list)
		info = info_list[0]
		return social.Profile(name=info['label'], city=info['city'], gender=info['gender'],
							  birth=info['birth'])

	def notify_friend(self, to, message):
		user = to.split(':',1)[1]
		link = message.link
		if message.link and message.link.startswith('/'):
			link = GG_URL % dict(app=API['appname'], path=link)
		self.client_call('send_notification', (int(user), message.text.encode('utf8'), link))
	

