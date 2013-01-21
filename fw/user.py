from google.appengine.api import users

def is_admin():
	return users.is_current_user_admin()

def create_login_url(dest):
	return users.create_login_url(dest)