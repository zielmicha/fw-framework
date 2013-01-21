import logging
import random

import fw.db

import game

sectors = fw.db.DBDict('gamemap.sectors')
cities_of_user = fw.db.DBDict('gamemap.cities_of_user')
travelling_armies = fw.db.DBDict('gamemap.travelling_armies')
battle_logs = fw.db.DBDict('gamemap.battle_logs')

SECTOR_SIZE = 80
MAP_SIZE = 5 # in sectors

CITY = 'CITY'

class MapRetriever(object):
	def __init__(self):
		self.sector_cache = {}
	
	def get(self, x, y):
		sx = x // SECTOR_SIZE
		sy = y // SECTOR_SIZE
		rx = x % SECTOR_SIZE
		ry = y % SECTOR_SIZE
		
		sector = self.get_sector(sx, sy)
		
		#logging.info('%r x=%s sx=%s rx=%s -> %s', sector, (x,y), (sx,sy), (rx,ry), sector.get((rx, ry), None))
		
		return sector.get((rx, ry), None)
	
	def get_sector(self, sx, sy):
		pos = (sx % MAP_SIZE, sy % MAP_SIZE)
		if pos not in self.sector_cache:
			sector = sectors.get('%d,%d' % pos, {})
			self.sector_cache[pos] = sector
		return self.sector_cache[pos]
	
	def put(self, x, y, val):
		sx = (x // SECTOR_SIZE) % MAP_SIZE
		sy = (y // SECTOR_SIZE) % MAP_SIZE
		rx = x % SECTOR_SIZE
		ry = y % SECTOR_SIZE
		
		sector = self.get_sector(sx, sy)
		sector[(rx, ry)] = val
		
		self.sector_cache = {}
		sectors['%d,%d' % (sx, sy)] = sector

	def pick_empty(self):
		while True:
			x = random.randrange(MAP_SIZE * SECTOR_SIZE)
			y = random.randrange(MAP_SIZE * SECTOR_SIZE)
			
			if not self.get(x, y):
				return x,y

def get_cities_of_user(userid):
	return cities_of_user.get(userid, [])

def add_user_city(userid, cityid):
	cities = cities_of_user.get(userid, [])
	cities.append(cityid)
	cities_of_user[userid] = cities

def prepare(userid, cityname):
	map = MapRetriever()
	x, y = map.pick_empty()
	name = '%d,%d' % (x, y)
	
	game.City.Create(location=name, title=cityname, user=userid)
	add_user_city(userid, name)
	map.put(x, y, (CITY, name, userid, cityname))
	
def set_title(city, new_title):
	map = MapRetriever()
	x,y = city.get_pos()
	tuple = map.get(x, y)
	assert tuple[0] == 'CITY'
	map.put(x, y, tuple[:-1] + (new_title,))
	
	city.title = new_title
	city.put()

def add_travelling_army(id, owner, *args):
	armies = travelling_armies.get(owner, {})
	armies[id] = args
	travelling_armies[owner] = armies

def remove_travelling_army(id, owner):
	armies = travelling_armies.get(owner, {})
	del armies[id]
	travelling_armies[owner] = armies

def get_travelling_armies(owner):
	return [
		dict(id=k, units=units, src=src, dst=dst, left=left, arrives=arrives, mission=mission, battle_time=battle_time)
		for k, (mission, units, src, dst, left, arrives, battle_time)
			in travelling_armies.get(owner, {}).items()
	]