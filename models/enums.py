from enum import Enum

class StatusType(str, Enum):
    OUTSTANDING = "outstanding"
    STARTED = "started"
    IN_PROGRESS = "in progress"
    FINISHED = "finished"
    CLOSED = "closed"
    ABORTED = "aborted"
    CANCELLED = "cancelled"
    
class PriorityType(str, Enum):
    LOW = 'low'
    MEDIUM = 'medium'
    HIGH = 'high'


class JourneyThemeId(str, Enum):
    MOUNTAIN = 'mountain'
    WORLD_TREE = 'world-tree'
    COSMIC = 'cosmic'
    VOLCANO = 'volcano'
    OCEAN = 'ocean'
    CASTLE = 'castle'


class JourneyCharacterId(str, Enum):
    BAT = 'bat'
    BAT_V2 = 'bat-v2'
    EAGLE = 'eagle'
    SNOW_LEOPARD = 'snow-leopard'
    OWL = 'owl'
    MOUNTAIN_GOAT = 'mountain-goat'
    FOX = 'fox'
    SALAMANDER = 'salamander'
    BABY_DRAGON = 'baby-dragon'
    MANTA_RAY = 'manta-ray'
    SEA_TURTLE = 'sea-turtle'
