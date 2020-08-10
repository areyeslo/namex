"""Events keep an audit trail of all changes submitted to the datastore

"""
from sqlalchemy import and_, func, case

from . import db
from namex.exceptions import BusinessException
from marshmallow import Schema, fields, post_load
from datetime import datetime
from .request import Request
from sqlalchemy.orm import backref
from sqlalchemy.dialects.postgresql import JSONB

from ..constants import EventAction, EventState


class Event(db.Model):
    __tablename__ = 'events'

    id = db.Column(db.Integer, primary_key=True)
    eventDate = db.Column('event_dt', db.DateTime(timezone=True), default=datetime.utcnow)
    action = db.Column(db.String(1000))
    jsonZip = db.Column('json_zip', db.Text)
    eventJson = db.Column('event_json', JSONB)

    # relationships
    stateCd = db.Column('state_cd', db.String(20), db.ForeignKey('states.cd'))
    state = db.relationship('State', backref=backref('state_events', uselist=False), foreign_keys=[stateCd])
    nrId = db.Column('nr_id', db.Integer, db.ForeignKey('requests.id'))
    request = db.relationship('Request', backref=backref('request_events', uselist=False), foreign_keys=[nrId])
    userId = db.Column('user_id', db.Integer, db.ForeignKey('users.id'))
    user = db.relationship('User', backref=backref('user_events', uselist=False), foreign_keys=[userId])

    GET = 'get'
    PUT = 'put'
    PATCH = 'patch'
    POST = 'post'
    DELETE = 'DELETE'
    UPDATE_FROM_NRO = 'update_from_nro'
    NRO_UPDATE = 'nro_update'
    MARKED_ON_HOLD = 'marked_on_hold'

    VALID_ACTIONS = [GET, PUT, PATCH, POST, DELETE]

    def json(self):
        return {"id": self.id, "eventDate": self.eventDate, "action": self.action, "stateCd": self.stateCd,
                "jsonData": self.eventJson,
                "requestId": self.nrId, "userId": self.userId}

    def save_to_db(self):
        db.session.add(self)
        db.session.commit()

    def save_to_session(self):
        db.session.add(self)

    def delete_from_db(self):
        raise BusinessException()

    @classmethod
    def get_put_records(cls, priority):
        put_records = db.session.query(Event.nrId.label('nrId'), func.max(cls.eventDate).label('eventDateFinal')).join(
            Request, and_(Event.nrId == Request.id)).filter(
            cls.action == EventAction.PUT.value,
            Request.priorityCd == priority.value,
            cls.stateCd.in_([EventState.APPROVED.value, EventState.REJECTED.value, EventState.CONDITIONAL.value]),
            cls.eventDate < func.now()
        ).group_by(Event.nrId).subquery()

        return put_records

    @classmethod
    def get_update_put_records(cls, put_records):
        update_from_put_records = db.session.query(Event.nrId,
                                                   func.max(put_records.c.eventDateFinal).label('eventDateFinal'),
                                                   func.min(Event.eventDate).label('eventDateStart')).join(
            put_records,
            Event.nrId == put_records.c.nrId).filter(
            Event.action == EventAction.UPDATE.value,
            ~Event.stateCd.in_([EventState.CANCELLED.value])).group_by(
            Event.nrId).subquery()

        return update_from_put_records

    @classmethod
    def get_examination_rate(cls, update_from_put_records):
        examination_rate = db.session.query(func.round(
            func.avg(
                case([
                    (update_from_put_records.c.eventDateFinal > update_from_put_records.c.eventDateStart,
                     func.round((func.extract('epoch', update_from_put_records.c.eventDateFinal) -
                                 func.extract('epoch', update_from_put_records.c.eventDateStart)) / 60))
                ])
            )
        ).label('Minutes'),
                                            func.round(
                                                func.avg(
                                                    case([
                                                        (update_from_put_records.c.eventDateFinal >
                                                         update_from_put_records.c.eventDateStart,
                                                         func.round((func.extract('epoch',
                                                                                  update_from_put_records.c.eventDateFinal) -
                                                                     func.extract('epoch',
                                                                                  update_from_put_records.c.eventDateStart)) / 3600))
                                                    ])
                                                )
                                            ).label('Hours'),
                                            func.round(
                                                func.avg(
                                                    case([
                                                        (update_from_put_records.c.eventDateFinal >
                                                         update_from_put_records.c.eventDateStart,
                                                         func.round((func.extract('epoch',
                                                                                  update_from_put_records.c.eventDateFinal) -
                                                                     func.extract('epoch',
                                                                                  update_from_put_records.c.eventDateStart)) / 86400))
                                                    ])
                                                )
                                            ).label('Days'),
                                            ).all()
        response= Event().get_examination_rate_response(examination_rate)
        return response

    def get_examination_rate_response(cls, examination_rate):
        examination_rate_dict = {'minutes':int(examination_rate[0][0]), 'hours':int(examination_rate[0][1]), 'days': int(examination_rate[0][2])}

        return examination_rate_dict
