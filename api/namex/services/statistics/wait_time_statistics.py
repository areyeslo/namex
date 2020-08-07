from enum import Enum
from namex.models import Event


# This enum has no value outside of the context of this file so it's defined here instead of in constants
class PriorityCode(Enum):
    YES = 'Y'
    NO = 'N'


class WaitTimeStatsService:
    def __init__(self):
        pass

    @classmethod
    def calculate_examination_rate(cls, is_priority):
        priority = PriorityCode.YES if is_priority else PriorityCode.NO

        put_records = Event.get_put_records(priority)
        update_from_put_records = Event.get_update_put_records(put_records)
        examination_rate = Event.get_examination_rate(update_from_put_records)

        return examination_rate
