from sqlalchemy import select, update, text
from urllib.parse import quote_plus
from sqlalchemy.ext.asyncio import create_async_engine, async_sessionmaker
from datetime import datetime, timezone

from .orm_models import Base, Key, User, Role
import asyncio

class NebuloidORM:
    def __init__(self, manifest):
        self.manifest = manifest
    
    def mount(self):
        # Placeholder for ORM mounting logic
        self.engine = self.connect_db(self.manifest.data['db']['cred'])
        self.Session = async_sessionmaker(bind=self.engine)
        self.session = self.Session()
        print("Database connected:", self.engine)
    
    def connect_db(self, cred):
        # db_type="mysql", username="", password="", host="localhost", port=None, database=""
        db_type  = cred.get("db_type", "")
        username = quote_plus(cred.get("username", ""))
        password = quote_plus(cred.get("password", ""))
        host     = cred.get("host", "")
        port     = cred.get("port","3306")
        database = cred.get("database", "")

        # todo:sqllite in-memory feature
        if db_type == "mysql":
            url = f"mysql+aiomysql://{username}:{password}@{host}:{port}/{database}"
            return create_async_engine(url)

        elif db_type == "postgresql":
            url = f"postgresql+psycopg2://{username}:{password}@{host}:{port}/{database}"
            return create_async_engine(url)

        elif db_type == "sqlite":
            url = f"sqlite:///{database}"  # * use ':memory:' for in-memory
            return create_async_engine(url)

        elif db_type == "mssql":  # Microsoft SQL Server
            # Requires: pip install pyodbc
            url = f"mssql+pyodbc://{username}:{password}@{host},{port}/{database}?driver=ODBC+Driver+17+for+SQL+Server"
            return create_async_engine(url)

        elif db_type == "oracle":
            # Requires: pip install cx_Oracle
            url = f"oracle+cx_oracle://{username}:{password}@{host}:{port}/?service_name={database}"
            return create_async_engine(url)

        else:
            raise ValueError(f"Unsupported DB type: {db_type}")

        
        return create_async_engine(url, echo=True)  # echo=True shows SQL logs
    
    async def execute(self, query, data=None):
        try:
            async with self.engine.connect() as conn:
                result = await conn.execute(text(query), data or {})
             # commit if not a SELECT
                if result.returns_rows:  # SELECT queries
                    rows = [dict(row._mapping) for row in result.fetchall()]
                    return {"status": "success", "data": rows}
                else:  # INSERT/UPDATE/DELETE
                    await conn.commit()
                    return {"status": "success", "rows_affected": result.rowcount}
                
        except Exception as e:
            return {"status": "error", "message": str(e)}
    
    async def add_key(self, session_id, key_bytes):
        async with self.Session() as session:
            new_key = Key(session=session_id, key=key_bytes)
            session.add(new_key)
            await session.commit()
            return new_key

    async def get_key(self, session_id: str):
        async with self.Session() as session:
            result = await session.execute(
                select(Key).where(Key.session == session_id)
            )
            key_obj = result.scalar_one_or_none()  # returns Key instance or None
            return key_obj

    # Update existing key for a session
    async def update_key(self, session_id: str, key_bytes: bytes):
        async with self.Session() as session:
            key_obj = await self.get_key(session_id)
            if key_obj:
                key_obj.key = key_bytes
                key_obj.last_used = datetime.now()
                session.add(key_obj)  # add is safe for updates in ORM
                await session.commit()
                return key_obj
            else:
                return None  # optionally handle missing session differently
    
    # * Background loop for cleaning up old sessions.
    async def maintenance_task(self):
        while True:
            try:
                async with self.Session() as db:
                    await db.execute(text("CALL maintenance()"))
                    await db.commit()

            except Exception as e:
                print("Maintenance error:", e)

            await asyncio.sleep(60)  # run every 60s
    # Add a new user
    async def add_user(self, username: str, password_hash: str, role: int = 0):
        async with self.Session() as session:
            new_user = User(
                identifier=username,
                password_hash=password_hash
            )
            session.add(new_user)
            await session.commit()
            await session.refresh(new_user)  # ensures new_user.id is available
            return new_user

    # Fetch user by username
    async def get_user_by_username(self, username: str):
        async with self.Session() as session:
            result = await session.execute(
                select(User).where(User.identifier == username)
            )
            user_obj = result.scalar_one_or_none()
            return user_obj    


    async def get_user_access_data(self, session_id: str):
      #Check auth_keys row by session_id.
       #If logged_in=1, then fetch role from users table.
        #Return JSON (dict) with user_id, role, logged_in.
        
        if not session_id:
            return None, {"status": "error", "logged_in": False, "message": "No session id"}

        async with self.Session() as session:
            # Step 1: Find row in auth_keys
            result = await session.execute(
                select(Key.user_id, Key.logged_in).where(Key.session == session_id)
            )
            row = result.one_or_none()

            if not row:
                return None, {"status": "error", "logged_in": False, "message": "Session not found"}

            user_id, logged_in = row

            # Step 2: Check if logged_in == 1
            if logged_in != 1:
                return None, {"status": "error", "logged_in": False, "message": "User not logged in"}

            # Step 3: Get role from users table
            user_result = await session.execute(
                select(User.role).where(User.id == user_id)
            )
            user_row = user_result.one_or_none()

            if not user_row:
                return None, {"status": "error", "logged_in": False, "message": "User not found"}

            role, = user_row  # unpack single column

            role_result = await session.execute(
                select(Role.name).where(Role.id == role)
            )
            role_row = role_result.one_or_none()

            role, = role_row

            # Step 4: Return as JSON
            return user_id, {
                "status": "success",
                "role": role,
                "logged_in": True,
            }

    async def get_role(self, user_id: int):
        """Fetch role name for a given user_id."""
        async with self.Session() as session:
            result = await session.execute(
                select(User.role).where(User.id == user_id)
            )
            row = result.one_or_none()
            if not row:
                return None

            role_id, = row

            role_result = await session.execute(
                select(Role.name).where(Role.id == role_id)
            )
            role_row = role_result.one_or_none()
            if not role_row:
                return None

            role_name, = role_row
            return role_name
        
    async def update_user_login_status(self, session_id: str, user_id: int, logged_in: bool):
        """Update or insert login status for a session in auth_keys."""
        if not session_id:
            return False

        async with self.Session() as session:
            # Try to update existing row
            result = await session.execute(
                update(Key)
                .where(Key.session == session_id)
                .values(
                    user_id=user_id,
                    logged_in=1 if logged_in else 0,
                    last_used=datetime.now()
                )
            )

            if result.rowcount == 0:
                return False  # No rows updated, session_id not found

            await session.commit()
            return True
        
    async def get_user_profile(self, user_id=None, session_id=None):
        
        if user_id is None and session_id is not None:
            async with self.Session() as session:
                result = await session.execute(
                    select(Key.user_id).where(Key.session == session_id)
                )
                row = result.one_or_none()
                if row:
                    user_id, = row
                else:
                    return {"status": "error", "message": "Session not found"}

        query = """
            SELECT *
            FROM profile
            WHERE user_id = :user_id
        """
        return await self.execute(query, {"user_id": user_id})
