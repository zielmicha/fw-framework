from gamedef import *

set_config(
	resources=('food', 'wood', 'gold', 'uranium'),
	default_resources=res(700, 700, 700, 100),
	default_income=res(20, 20, 10, 0),
	queues=('_buildings', ),
	unit_queues=('barracks', 'factory'),
	resource_buildings=dict(food=['farm'], wood=['forest'], gold=['goldmine'], uranium=['uraniummine']),
	walk_speed=Time(seconds=0.001), # seconds/field
	fight_round=Time(seconds=10),
)

add_building(
	'forest',
	costs=Std(0, 100, 50, 0),
	income=Std(food=20),
	time=TimeStd(seconds=30)
)

add_building(
	'farm',
	costs=Std(0, 100, 50, 0),
	income=Std(wood=20),
	time=TimeStd(seconds=30)
)

add_building(
	'goldmine',
	costs=Std(0, 100, 100, 0),
	income=Std(gold=20),
	time=TimeStd(seconds=50)
)

add_building(
	'uraniummine',
	costs=Std(0, 10, 10, 0),
	income=Std(uranium=20),
	time=TimeStd(seconds=160)
)

add_building(
	'barracks',
	costs=Std(0, 100, 100, 30),
	time=TimeStd(100),
	qspeed=dict(barracks=SingleStd(1.3))
)

add_building(
	'factory',
	costs=Std(0, 100, 100, 30),
	time=TimeStd(100),
	qspeed=dict(barracks=SingleStd(1.3))
)

add_unit(
	'gunner',
	costs=res(10, 10, 5, 0),
	upkeep=res(food=1),
	travel_upkeep=res(food=2),
	battle_upkeep=res(food=2, gold=1),
	time=Time(seconds=15),
	qname='barracks',
	
	attack=20,
	hp=40,
)

add_unit(
	'automatic',
	costs=res(10, 10, 10, 0),
	upkeep=res(food=2),
	travel_upkeep=res(food=3),
	battle_upkeep=res(food=3, gold=1),
	time=Time(seconds=30),
	qname='barracks',
	
	attack=35,
	hp=45,
)

add_unit(
	'rocketlauncher',
	costs=res(10, 10, 10, 0),
	upkeep=res(food=2),
	travel_upkeep=res(food=3),
	battle_upkeep=res(food=3, gold=1),
	time=Time(seconds=150),
	qname='factory',
	
	attack=150,
	hp=200,
)

add_unit(
	'tank',
	costs=res(10, 10, 10, 0),
	upkeep=res(food=2),
	travel_upkeep=res(food=3),
	battle_upkeep=res(food=3, gold=1),
	time=Time(seconds=150),
	qname='factory',
	
	attack=150,
	hp=200,
)