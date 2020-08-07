from namex.models import Request
from namex.models import Event


class WaitTimeStatsService:
    def __init__(self):
        pass

    def calculate_examination_rate(self, priority):
        put_records = Event.get_update_put_records(priority)
        update_from_put_records = Event.get_update_put_records(put_records)
        examination_rate = Event.get_examination_rate(update_from_put_records)

        return examination_rate
