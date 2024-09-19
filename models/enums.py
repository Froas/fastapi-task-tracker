from enum import Enum

class StatusType(str, Enum):
    OUTSTANDING = "outstanding"
    STARTED = "started"
    IN_PROGRESS = "in progress"
    FINISHED = "finished"
    CLOSED = "closed"
    ABORTED = "aborted"
    
class PriorityType(str, Enum):
    LOW = 'low'
    MEDIUM = 'medium'
    HIGH = 'high'