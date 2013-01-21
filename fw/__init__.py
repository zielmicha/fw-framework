from fw.core import BaseWidget, widget, action, Attr
import fw.core

try:
	fw.core.init()
except AttributeError:
	import logging
	logging.exception('fw.core.init()')
	fw.core = __import__('fw.core')

#except:
#	import logging
#	logging.exception('cannot import core')