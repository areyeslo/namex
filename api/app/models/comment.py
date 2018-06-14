from app import db, ma
from datetime import datetime
from sqlalchemy.orm import backref
from app.models.user import User


class Comment(db.Model):
    __tablename__ = 'comments'

    id = db.Column(db.Integer, primary_key=True)
    comment = db.Column(db.String(4096))
    timestamp = db.Column('timestamp', db.DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

    # parent keys
    nrId = db.Column('nr_id', db.Integer, db.ForeignKey('requests.id'))
    examinerId = db.Column('user_id', db.Integer, db.ForeignKey('users.id'))

    # Relationships - Users
    examiner = db.relationship("User", backref=backref("examiner_comments", uselist=False), foreign_keys=[examinerId])
    # NRComments = db.relationship('Request', backref=backref("comments", uselist=False), foreign_keys=[nrId])

    def as_dict(self):
        return {
            'examiner': self.examiner.username,
            'comment': self.comment,
            'timestamp': self.timestamp
        }

    def save_to_db(self):
        db.session.add(self)
        db.session.commit()

    def delete_from_db(self):
        pass