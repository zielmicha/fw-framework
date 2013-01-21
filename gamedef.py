
import collections

class Config(object):pass

config = Config()

def set_config(**kwargs):
	config.__dict__.update(kwargs)

INF = 1e9999 # float('inf') - does not work on python 2.5

class Res(tuple):
	def mul(self, a):
		return map(lambda i: i * a, self)
	def add(self, res2):
		assert len(res2) == len(self), (res2, self)
		return Res(tuple( a+b for a, b in zip(res2, self) ))
	def sub(self, res2):
		assert len(res2) == len(self)
		return Res(tuple( a-b for a, b in zip(self, res2) ))
	def is_enough(self, other):
		i_am_smaller = any( mine < other for mine, other in zip(self, other) )
		return not i_am_smaller
	def div_max(self, res2):
		assert len(res2) == len(self), (res2, self)
		return int(min( (a / b if b != 0 else INF) for a, b in zip(self, res2) ))
	def items(self):
		return zip(config.resources, self)

def Time(seconds=0, minutes=0, hours=0, days=0):
	return (seconds + 60*(minutes + 60*(hours + 24*days))) / 3600.

#def res(*args, **kwargs):
#	if not kwargs:
#		return Res(args)
#	else:
#		res = config.resources
#		val = [0] * len(res)
#		for k, v in kwargs.items():
#			val[res.index(k)] = v
#		return Res(val)

def res(food=0, wood=0, gold=0, uranium=0):
	return Res((food, wood, gold, uranium))

def empty_res():
	return Res([0] * len(config.resources))

def leveling(method):
	def decorator(*args, **kwargs):
		if len(args) != 1:
			a = res(*args, **kwargs)
		else:
			assert not kwargs
			a = args
		return Leveler(method, a)
	return decorator

import json

class Leveler(object):
	def __init__(self, method, start):
		self._convert_to_js = ('CreateLeveler(function(level, start)'
			'{return %s}, %s)' % (method.__doc__, json.dumps(start)))
		self.method = method
		self.start = start
	def __call__(self, level):
		return map(lambda i: self.method(level, i), self.start)
	def __repr__(self):
		return 'Leveler(%s)' % self.method.__doc__

def TimeLeveling(mode, *args, **kwargs):
	return SingleLeveler(mode, Time(*args, **kwargs))

def SingleLeveling(mode, n):
	return SingleLeveler(mode, n)

class SingleLeveler(object):
	def __init__(self, method, start):
		self._convert_to_js = ('CreateSingleLeveler(function(level, start)'
			'{return %s}, %s)' % (method.__doc__, json.dumps(start)))
		self.method = method
		self.start = start
	def __call__(self, level):
		return self.method(self.start)(level)[0]
	def __repr__(self):
		return 'Leveler(%s)' % self.method.__doc__

def TimeStd(*args, **kwargs):
	return TimeLeveling(Std, *args, **kwargs)

def SingleStd(n):
	return SingleLeveling(Std, n)

@leveling
def Linear(level, start):
	'start * level'
	return start * level

@leveling
def Double(level, start):
	'start * Math.pow(2, level - 1)'
	return start * (2 ** (level - 1))

@leveling
def Std(level, start):
	'start * Math.pow(1.3, level - 1)'
	return start * (1.3 ** (level - 1))

@leveling
def Empty(level, start):
	' 0 '
	return 0

class Building():
	def __init__(self, costs, time, income=Empty(), qspeed={}):
		self.income = income
		self.costs = costs
		self.time = time
		self.qspeed = qspeed
	def run(self, env, level):
		for k, v in self.qspeed.items():
			env.speed_queue(k, v(level))
		env.incr_resource_income(self.income(level))
	def get_costs(self, level):
		return self.costs(level)
	def get_time(self, level):
		return self.time(level)

class Unit:
	def __init__(self, ident, costs, time, upkeep, qname, attack, hp,
				 travel_upkeep, battle_upkeep):
		self.queue_name = qname
		self.time = time
		self.costs = costs
		self.upkeep = upkeep
		self.queue = qname
		
		self.attack = attack
		self.hp = hp
		self.travel_upkeep = travel_upkeep
		self.battle_upkeep = battle_upkeep
		
		self.ident = ident
		units_by_queue[qname].append(self)
	
	for n in 'costs time queue_name upkeep queue'.split():
		exec '''def get_%s(self): return self.%s''' % (n, n)

buildings = {}
units = {}
units_by_queue = collections.defaultdict(list)

def add_building(ident, *args, **kwargs):
	buildings[ident] = Building(*args, **kwargs)

def add_unit(ident, *args, **kwargs):
	units[ident] = Unit(ident, *args, **kwargs)

def get_building_object(ident):
	return buildings[ident]

def get_unit_object(ident):
	return units[ident]

import gameconfig