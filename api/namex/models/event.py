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
        return {"id": self.id, "eventDate": self.eventDate, "action": self.action, "stateCd": self.stateCd, "jsonData": self.eventJson,
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
        put_records = db.ession.query(Event.nr_id, func.max(Event.event_dt).label('event_dt_final')).join(
            Request, and_(Event.nr_id == Request.id)).filter(
            Event.action == EventAction.PUT.value,
            Request.priority_cd == priority,
            Event.state_cd.in_([EventState.APPROVED.value, EventState.REJECTED.value, EventState.CONDITIONAL.value]),
            Event.event_dt < func.now()
        ).group_by(Event.nr_id).subquery()

        return put_records

    @classmethod
    def get_update_put_records(cls, put_records):
        update_from_put_records = db.session.query(Event.nr_id,
                                                   func.max(put_records.c.event_dt_final).label('event_dt_final'),
                                                   func.min(Event.event_dt).label('event_dt_start')).join(
            put_records,
            Event.nr_id == put_records.c.nr_id).filter(
            Event.action == EventAction.UPDATE.value,
            ~Event.state_cd.in_([EventState.CANCELLED.value])).group_by(
            Event.nr_id).subquery()

        return update_from_put_records

    @classmethod
    def get_examination_rate(cls, update_from_put_records):
        examination_rate = db.session.query(func.round(
            func.avg(
                case([
                    (update_from_put_records.c.event_dt_final >
                     update_from_put_records.c.event_dt_start,
                     func.round((func.extract('epoch',
                                              update_from_put_records.c.event_dt_final) -
                                 func.extract('epoch',
                                              update_from_put_records.c.event_dt_start)) / 60))
                ])
            )
        ).label('Minutes'),
                                            func.round(
                                                func.avg(
                                                    case([
                                                        (update_from_put_records.c.event_dt_final >
                                                         update_from_put_records.c.event_dt_start,
                                                         func.round((func.extract('epoch',
                                                                                  update_from_put_records.c.event_dt_final) -
                                                                     func.extract('epoch',
                                                                                  update_from_put_records.c.event_dt_start)) / 3600))
                                                    ])
                                                )
                                            ).label('Hours'),
                                            func.round(
                                                func.avg(
                                                    case([
                                                        (update_from_put_records.c.event_dt_final >
                                                         update_from_put_records.c.event_dt_start,
                                                         func.round((func.extract('epoch',
                                                                                  update_from_put_records.c.event_dt_final) -
                                                                     func.extract('epoch',
                                                                                  update_from_put_records.c.event_dt_start)) / 86400))
                                                    ])
                                                )
                                            ).label('Days'),
                                            ).all()
        return examination_rate

