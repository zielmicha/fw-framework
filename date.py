import time
import sys
import datetime

sys.path.append('pytz.zip')

import pytz
default_tz = 'Europe/Warsaw'

seconds_in_hour = 3600

def now():
	return float(time.time()) / seconds_in_hour

def format_time(format, hours, timezone=None):
	return localize(hours, timezone).strftime(format)

def localize(hours, timezone=None):
	tz = pytz.timezone(timezone or default_tz)
	return date_from_hours(hours).astimezone(tz)

def date_from_hours(hours):
	dt = datetime.datetime.fromtimestamp(hours * seconds_in_hour, pytz.utc)
	
	return dt