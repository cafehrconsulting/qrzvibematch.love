from datetime import datetime

from flask_sqlalchemy import SQLAlchemy


db = SQLAlchemy()


class TimestampMixin:
    created_at = db.Column(db.DateTime, nullable=False, default=datetime.utcnow)
    updated_at = db.Column(
        db.DateTime,
        nullable=False,
        default=datetime.utcnow,
        onupdate=datetime.utcnow,
    )


class User(db.Model, TimestampMixin):
    __tablename__ = "users"

    id = db.Column(db.Integer, primary_key=True)

    # Account
    email = db.Column(db.String(255), unique=True, nullable=True, index=True)
    password_hash = db.Column(db.String(255), nullable=True)

    # Public profile
    first_name = db.Column(db.String(100), nullable=False, default="QRZ")
    last_name = db.Column(db.String(100), nullable=False, default="Member")
    display_name = db.Column(db.String(120), nullable=False, default="QRZ Member")
    username = db.Column(db.String(80), unique=True, nullable=True, index=True)

    age = db.Column(db.Integer, nullable=False, default=30)
    gender = db.Column(db.String(50), nullable=True)
    interested_in = db.Column(db.String(120), nullable=True)

    city = db.Column(db.String(120), nullable=True)
    state = db.Column(db.String(120), nullable=True)
    country = db.Column(db.String(120), nullable=True)
    profession = db.Column(db.String(150), nullable=True)
    education = db.Column(db.String(150), nullable=True)

    headline = db.Column(db.String(255), nullable=True)
    bio = db.Column(db.Text, nullable=True)
    relationship_goal = db.Column(db.String(150), nullable=True)
    love_language = db.Column(db.String(120), nullable=True)
    lifestyle = db.Column(db.String(255), nullable=True)
    zodiac_sign = db.Column(db.String(50), nullable=True)

    profile_image = db.Column(db.String(500), nullable=True)
    cover_image = db.Column(db.String(500), nullable=True)

    # Status / subscription
    is_active = db.Column(db.Boolean, nullable=False, default=True)
    is_online = db.Column(db.Boolean, nullable=False, default=False)
    is_verified = db.Column(db.Boolean, nullable=False, default=False)
    is_premium = db.Column(db.Boolean, nullable=False, default=False)

    # Matching scores
    distance_miles = db.Column(db.Integer, nullable=False, default=0)
    compatibility_score = db.Column(db.Integer, nullable=False, default=0)
    career_score = db.Column(db.Integer, nullable=False, default=0)
    zodiac_score = db.Column(db.Integer, nullable=False, default=0)
    psychology_score = db.Column(db.Integer, nullable=False, default=0)
    location_score = db.Column(db.Integer, nullable=False, default=0)

    # Engagement / monetization
    gift_points = db.Column(db.Integer, nullable=False, default=0)
    likes_sent = db.Column(db.Integer, nullable=False, default=0)
    likes_received = db.Column(db.Integer, nullable=False, default=0)
    profile_views = db.Column(db.Integer, nullable=False, default=0)

    # Relationships
    matches_as_user_one = db.relationship(
        "Match",
        foreign_keys="Match.user_one_id",
        back_populates="user_one",
        lazy=True,
        cascade="all, delete-orphan",
    )
    matches_as_user_two = db.relationship(
        "Match",
        foreign_keys="Match.user_two_id",
        back_populates="user_two",
        lazy=True,
        cascade="all, delete-orphan",
    )

    messages_sent = db.relationship(
        "Message",
        foreign_keys="Message.sender_id",
        back_populates="sender",
        lazy=True,
        cascade="all, delete-orphan",
    )
    messages_received = db.relationship(
        "Message",
        foreign_keys="Message.recipient_id",
        back_populates="recipient",
        lazy=True,
        cascade="all, delete-orphan",
    )

    gift_transactions_sent = db.relationship(
        "GiftTransaction",
        foreign_keys="GiftTransaction.sender_id",
        back_populates="sender",
        lazy=True,
        cascade="all, delete-orphan",
    )
    gift_transactions_received = db.relationship(
        "GiftTransaction",
        foreign_keys="GiftTransaction.recipient_id",
        back_populates="recipient",
        lazy=True,
        cascade="all, delete-orphan",
    )

    profile_interests = db.relationship(
        "UserInterest",
        back_populates="user",
        lazy=True,
        cascade="all, delete-orphan",
        order_by="UserInterest.id.asc()",
    )

    photos = db.relationship(
        "UserPhoto",
        back_populates="user",
        lazy=True,
        cascade="all, delete-orphan",
        order_by="UserPhoto.display_order.asc(), UserPhoto.id.asc()",
    )

    def full_name(self) -> str:
        return f"{self.first_name} {self.last_name}".strip()

    def location_display(self) -> str:
        parts = [part for part in [self.city, self.state, self.country] if part]
        return ", ".join(parts)

    def to_dict(self) -> dict:
        return {
            "id": self.id,
            "email": self.email,
            "first_name": self.first_name,
            "last_name": self.last_name,
            "display_name": self.display_name,
            "username": self.username,
            "age": self.age,
            "gender": self.gender,
            "interested_in": self.interested_in,
            "city": self.city,
            "state": self.state,
            "country": self.country,
            "profession": self.profession,
            "education": self.education,
            "headline": self.headline,
            "bio": self.bio,
            "relationship_goal": self.relationship_goal,
            "love_language": self.love_language,
            "lifestyle": self.lifestyle,
            "zodiac_sign": self.zodiac_sign,
            "profile_image": self.profile_image,
            "cover_image": self.cover_image,
            "is_active": self.is_active,
            "is_online": self.is_online,
            "is_verified": self.is_verified,
            "is_premium": self.is_premium,
            "distance_miles": self.distance_miles,
            "compatibility_score": self.compatibility_score,
            "career_score": self.career_score,
            "zodiac_score": self.zodiac_score,
            "psychology_score": self.psychology_score,
            "location_score": self.location_score,
            "gift_points": self.gift_points,
            "likes_sent": self.likes_sent,
            "likes_received": self.likes_received,
            "profile_views": self.profile_views,
            "created_at": self.created_at.isoformat() if self.created_at else None,
            "updated_at": self.updated_at.isoformat() if self.updated_at else None,
        }

    def __repr__(self) -> str:
        return f"<User {self.id} {self.display_name}>"


class Match(db.Model, TimestampMixin):
    __tablename__ = "matches"

    id = db.Column(db.Integer, primary_key=True)

    user_one_id = db.Column(db.Integer, db.ForeignKey("users.id"), nullable=True, index=True)
    user_two_id = db.Column(db.Integer, db.ForeignKey("users.id"), nullable=True, index=True)

    status = db.Column(db.String(50), nullable=False, default="matched")
    compatibility_score = db.Column(db.Integer, nullable=False, default=0)
    career_score = db.Column(db.Integer, nullable=False, default=0)
    zodiac_score = db.Column(db.Integer, nullable=False, default=0)
    psychology_score = db.Column(db.Integer, nullable=False, default=0)
    location_score = db.Column(db.Integer, nullable=False, default=0)

    is_active = db.Column(db.Boolean, nullable=False, default=True)
    unread_count_user_one = db.Column(db.Integer, nullable=False, default=0)
    unread_count_user_two = db.Column(db.Integer, nullable=False, default=0)
    last_message_preview = db.Column(db.String(255), nullable=True)
    last_interaction_at = db.Column(db.DateTime, nullable=True)

    user_one = db.relationship(
        "User",
        foreign_keys=[user_one_id],
        back_populates="matches_as_user_one",
    )
    user_two = db.relationship(
        "User",
        foreign_keys=[user_two_id],
        back_populates="matches_as_user_two",
    )

    messages = db.relationship(
        "Message",
        back_populates="match",
        lazy=True,
        cascade="all, delete-orphan",
        order_by="Message.created_at.asc()",
    )

    gift_transactions = db.relationship(
        "GiftTransaction",
        back_populates="match",
        lazy=True,
        cascade="all, delete-orphan",
    )

    def to_dict(self) -> dict:
        return {
            "id": self.id,
            "user_one_id": self.user_one_id,
            "user_two_id": self.user_two_id,
            "status": self.status,
            "compatibility_score": self.compatibility_score,
            "career_score": self.career_score,
            "zodiac_score": self.zodiac_score,
            "psychology_score": self.psychology_score,
            "location_score": self.location_score,
            "is_active": self.is_active,
            "unread_count_user_one": self.unread_count_user_one,
            "unread_count_user_two": self.unread_count_user_two,
            "last_message_preview": self.last_message_preview,
            "last_interaction_at": self.last_interaction_at.isoformat() if self.last_interaction_at else None,
            "created_at": self.created_at.isoformat() if self.created_at else None,
            "updated_at": self.updated_at.isoformat() if self.updated_at else None,
        }

    def __repr__(self) -> str:
        return f"<Match {self.id} status={self.status}>"


class Message(db.Model, TimestampMixin):
    __tablename__ = "messages"

    id = db.Column(db.Integer, primary_key=True)

    match_id = db.Column(db.Integer, db.ForeignKey("matches.id"), nullable=True, index=True)
    sender_id = db.Column(db.Integer, db.ForeignKey("users.id"), nullable=True, index=True)
    recipient_id = db.Column(db.Integer, db.ForeignKey("users.id"), nullable=True, index=True)

    body = db.Column(db.Text, nullable=False, default="")
    message_type = db.Column(db.String(50), nullable=False, default="text")
    is_read = db.Column(db.Boolean, nullable=False, default=False)
    is_premium = db.Column(db.Boolean, nullable=False, default=False)
    delivered_at = db.Column(db.DateTime, nullable=True)
    read_at = db.Column(db.DateTime, nullable=True)

    match = db.relationship("Match", back_populates="messages")
    sender = db.relationship(
        "User",
        foreign_keys=[sender_id],
        back_populates="messages_sent",
    )
    recipient = db.relationship(
        "User",
        foreign_keys=[recipient_id],
        back_populates="messages_received",
    )

    def to_dict(self) -> dict:
        return {
            "id": self.id,
            "match_id": self.match_id,
            "sender_id": self.sender_id,
            "recipient_id": self.recipient_id,
            "body": self.body,
            "message_type": self.message_type,
            "is_read": self.is_read,
            "is_premium": self.is_premium,
            "delivered_at": self.delivered_at.isoformat() if self.delivered_at else None,
            "read_at": self.read_at.isoformat() if self.read_at else None,
            "created_at": self.created_at.isoformat() if self.created_at else None,
            "updated_at": self.updated_at.isoformat() if self.updated_at else None,
        }

    def __repr__(self) -> str:
        return f"<Message {self.id} type={self.message_type}>"


class GiftTransaction(db.Model, TimestampMixin):
    __tablename__ = "gift_transactions"

    id = db.Column(db.Integer, primary_key=True)

    match_id = db.Column(db.Integer, db.ForeignKey("matches.id"), nullable=True, index=True)
    sender_id = db.Column(db.Integer, db.ForeignKey("users.id"), nullable=True, index=True)
    recipient_id = db.Column(db.Integer, db.ForeignKey("users.id"), nullable=True, index=True)

    gift_name = db.Column(db.String(120), nullable=False, default="Rose")
    gift_type = db.Column(db.String(80), nullable=False, default="virtual")
    points_cost = db.Column(db.Integer, nullable=False, default=0)
    cash_value = db.Column(db.Float, nullable=False, default=0.0)
    note = db.Column(db.String(255), nullable=True)

    match = db.relationship("Match", back_populates="gift_transactions")
    sender = db.relationship(
        "User",
        foreign_keys=[sender_id],
        back_populates="gift_transactions_sent",
    )
    recipient = db.relationship(
        "User",
        foreign_keys=[recipient_id],
        back_populates="gift_transactions_received",
    )

    def to_dict(self) -> dict:
        return {
            "id": self.id,
            "match_id": self.match_id,
            "sender_id": self.sender_id,
            "recipient_id": self.recipient_id,
            "gift_name": self.gift_name,
            "gift_type": self.gift_type,
            "points_cost": self.points_cost,
            "cash_value": self.cash_value,
            "note": self.note,
            "created_at": self.created_at.isoformat() if self.created_at else None,
            "updated_at": self.updated_at.isoformat() if self.updated_at else None,
        }

    def __repr__(self) -> str:
        return f"<GiftTransaction {self.id} {self.gift_name}>"


class UserInterest(db.Model, TimestampMixin):
    __tablename__ = "user_interests"

    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey("users.id"), nullable=False, index=True)
    interest_name = db.Column(db.String(120), nullable=False)

    user = db.relationship("User", back_populates="profile_interests")

    def to_dict(self) -> dict:
        return {
            "id": self.id,
            "user_id": self.user_id,
            "interest_name": self.interest_name,
            "created_at": self.created_at.isoformat() if self.created_at else None,
            "updated_at": self.updated_at.isoformat() if self.updated_at else None,
        }

    def __repr__(self) -> str:
        return f"<UserInterest {self.id} {self.interest_name}>"


class UserPhoto(db.Model, TimestampMixin):
    __tablename__ = "user_photos"

    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey("users.id"), nullable=False, index=True)
    image_url = db.Column(db.String(500), nullable=False)
    caption = db.Column(db.String(255), nullable=True)
    is_primary = db.Column(db.Boolean, nullable=False, default=False)
    display_order = db.Column(db.Integer, nullable=False, default=0)

    user = db.relationship("User", back_populates="photos")

    def to_dict(self) -> dict:
        return {
            "id": self.id,
            "user_id": self.user_id,
            "image_url": self.image_url,
            "caption": self.caption,
            "is_primary": self.is_primary,
            "display_order": self.display_order,
            "created_at": self.created_at.isoformat() if self.created_at else None,
            "updated_at": self.updated_at.isoformat() if self.updated_at else None,
        }

    def __repr__(self) -> str:
        return f"<UserPhoto {self.id} user={self.user_id}>"