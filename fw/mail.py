import logging
import re
import fw.util
from google.appengine.api import mail

ADMIN = 'zielmicha@gmail.com'
DEFAULT_SENDER = 'Fw Framework <error@lin.appspotmail.com>'

def send(sender, to, subject, html, text):
	message = mail.EmailMessage(sender=sender, subject=subject)
	message.to = to
	message.body = fw.util.to_str(text)
	message.html = """
	<html><head>
	<meta http-equiv="Content-Type" content="text/html; charset=utf-8">
	</head><body>%s</body></html>
	""" % fw.util.to_str(html)
	
	message.send()
	
	if fw.util.IS_DEVELOPMENT:
		logging.info('[Mail content]\n' + html[:200])

def send_to_admin(subject, html, text):
	send(DEFAULT_SENDER, ADMIN, subject, html, text)