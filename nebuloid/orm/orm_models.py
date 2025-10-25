from sqlalchemy import BigInteger, String, LargeBinary, DateTime,  ForeignKey , JSON, Integer, func
from sqlalchemy.orm import declarative_base, Mapped, mapped_column
from datetime import datetime, timezone, timedelta
Base = declarative_base()
# IST = timezone(timedelta(hours=5, minutes=30))
class Key(Base):
    __tablename__ = "auth_keys"

    # Composite Primary Key (id + session)
    id: Mapped[int] = mapped_column(BigInteger, primary_key=True, autoincrement=True)
    session: Mapped[str] = mapped_column(String(100), primary_key=True)

    user_id: Mapped[int] = mapped_column(Integer, nullable=False)
    logged_in: Mapped[int] = mapped_column(Integer, default=0, nullable=False)

    key: Mapped[bytes] = mapped_column(LargeBinary(32), nullable=False)

    created_at: Mapped[datetime] = mapped_column(DateTime, default=func.now())
    last_used: Mapped[datetime] = mapped_column(DateTime, default=func.now(), onupdate=func.now())

    def __repr__(self):
        return (
            f"<Key(id={self.id}, session={self.session}, user_id={self.user_id}, "
            f"logged_in={self.logged_in}, key={self.key.hex()[:8]}...)>"
        )

class User(Base):
    __tablename__ = "users"

    id: Mapped[int] = mapped_column(BigInteger, primary_key=True, autoincrement=True)
    identifier: Mapped[str] = mapped_column(String(255), unique=True, nullable=False)
    password_hash: Mapped[str] = mapped_column(String(255), nullable=True)
    role: Mapped[int] = mapped_column(Integer, default=0)
    preferences: Mapped[dict] = mapped_column(JSON, default=dict)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=func.now())
    updated_at: Mapped[datetime] = mapped_column(DateTime, default=func.now(), onupdate=func.now())

    def __repr__(self):
        return f"<User(id={self.id}, identifier={self.identifier})>"

class Role(Base):
    __tablename__ = "roles"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    name: Mapped[str] = mapped_column(String(100))
    description: Mapped[str] = mapped_column(String(255) )

    def __repr__(self):
        return f"<role(id={self.id}, name={self.name})>"

class Profile(Base):
    __tablename__ = "profiles"

    # Composite PK: id + user_id
    id: Mapped[int] = mapped_column(BigInteger, primary_key=True, autoincrement=True)
    user_id: Mapped[int] = mapped_column(BigInteger, ForeignKey("users.id"), primary_key=True)

    name: Mapped[str] = mapped_column(String(100), nullable=False)
    display_name: Mapped[str] = mapped_column(String(45), nullable=True)
    gender: Mapped[int] = mapped_column(Integer, nullable=True)
    ph_number: Mapped[str] = mapped_column(String(15), nullable=True)
    email: Mapped[str] = mapped_column(String(255), nullable=True)

    created_at: Mapped[datetime] = mapped_column(DateTime, default=func.now())
    updated_at: Mapped[datetime] = mapped_column(DateTime, default=func.now(), onupdate=func.now())

   

    def __repr__(self):
        return f"<Profile(id={self.id}, user_id={self.user_id}, name={self.name})>"
