#!/usr/bin/env python

from google.appengine.ext import webapp
from google.appengine.ext.webapp.util import run_wsgi_app
import time, logging

import fw
import fw.core

class Handler(webapp.RequestHandler):
	def post(self, rest):
		start = time.clock()
		fw.core.run_widget(self, rest)
		t = time.clock() - start
		logging.info('Request handled in %d ms', int(t * 1000))
		
	get = post

application = webapp.WSGIApplication(
		[('/(.*)', Handler),],
		debug=True)

def main():
	run_wsgi_app(application)

def profile_main():
    # This is the main function for profiling
    # We've renamed our original main() above to real_main()
    import cProfile, pstats
    prof = cProfile.Profile()
    prof = prof.runctx("real_main()", globals(), locals())
    print "<pre>"
    stats = pstats.Stats(prof)
    stats.sort_stats("time")  # Or cumulative
    stats.print_stats(80)  # 80 = how many to print
    # The rest is optional.
    # stats.print_callees()
    # stats.print_callers()
    print "</pre>"

#real_main = main
#main = profile_main

if __name__ == "__main__":
	main()