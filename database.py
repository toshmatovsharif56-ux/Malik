import aiosqlite
from config import DB_PATH


async def init_db():
    async with aiosqlite.connect(DB_PATH) as db:
        await db.execute("""
            CREATE TABLE IF NOT EXISTS users (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                user_id INTEGER UNIQUE NOT NULL,
                username TEXT,
                first_name TEXT,
                last_name TEXT,
                phone TEXT,
                imei_file_id TEXT,
                circle_file_id TEXT,
                passport_front_file_id TEXT,
                passport_back_file_id TEXT,
                agreed_rules INTEGER DEFAULT 0,
                access_granted INTEGER DEFAULT 0,
                status TEXT DEFAULT 'pending',
                reject_reason TEXT,
                registered_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                verified_at TIMESTAMP
            )
        """)
        await db.commit()


async def upsert_user(user_id, username, first_name, last_name):
    async with aiosqlite.connect(DB_PATH) as db:
        await db.execute("""
            INSERT INTO users (user_id, username, first_name, last_name)
            VALUES (?, ?, ?, ?)
            ON CONFLICT(user_id) DO UPDATE SET
                username=excluded.username,
                first_name=excluded.first_name,
                last_name=excluded.last_name
        """, (user_id, username or "", first_name or "", last_name or ""))
        await db.commit()


async def set_agreed(user_id):
    async with aiosqlite.connect(DB_PATH) as db:
        await db.execute("UPDATE users SET agreed_rules=1 WHERE user_id=?", (user_id,))
        await db.commit()


async def set_phone(user_id, phone):
    async with aiosqlite.connect(DB_PATH) as db:
        await db.execute("UPDATE users SET phone=? WHERE user_id=?", (phone, user_id))
        await db.commit()


async def set_circle(user_id, file_id):
    async with aiosqlite.connect(DB_PATH) as db:
        await db.execute("UPDATE users SET circle_file_id=? WHERE user_id=?", (file_id, user_id))
        await db.commit()


async def set_imei(user_id, file_id):
    async with aiosqlite.connect(DB_PATH) as db:
        await db.execute("UPDATE users SET imei_file_id=? WHERE user_id=?", (file_id, user_id))
        await db.commit()


async def set_passport_front(user_id, file_id):
    async with aiosqlite.connect(DB_PATH) as db:
        await db.execute("UPDATE users SET passport_front_file_id=? WHERE user_id=?", (file_id, user_id))
        await db.commit()


async def set_passport_back(user_id, file_id):
    async with aiosqlite.connect(DB_PATH) as db:
        await db.execute("UPDATE users SET passport_back_file_id=? WHERE user_id=?", (file_id, user_id))
        await db.commit()


async def set_access_granted(user_id):
    async with aiosqlite.connect(DB_PATH) as db:
        await db.execute(
            "UPDATE users SET access_granted=1, status='approved', verified_at=CURRENT_TIMESTAMP WHERE user_id=?",
            (user_id,)
        )
        await db.commit()


async def set_rejected(user_id, reason):
    async with aiosqlite.connect(DB_PATH) as db:
        await db.execute(
            "UPDATE users SET status='rejected', reject_reason=? WHERE user_id=?",
            (reason, user_id)
        )
        await db.commit()


async def get_user(user_id):
    async with aiosqlite.connect(DB_PATH) as db:
        db.row_factory = aiosqlite.Row
        async with db.execute("SELECT * FROM users WHERE user_id=?", (user_id,)) as c:
            row = await c.fetchone()
            return dict(row) if row else None


async def search_users(query: str) -> list:
    async with aiosqlite.connect(DB_PATH) as db:
        db.row_factory = aiosqlite.Row
        q = f"%{query}%"
        async with db.execute("""
            SELECT * FROM users
            WHERE username LIKE ? OR first_name LIKE ? OR last_name LIKE ?
               OR CAST(user_id AS TEXT) LIKE ? OR phone LIKE ?
               OR (first_name || ' ' || last_name) LIKE ?
            ORDER BY registered_at DESC LIMIT 20
        """, (q, q, q, q, q, q)) as c:
            return [dict(r) for r in await c.fetchall()]


async def search_users_prefix(query: str) -> list:
    """Живой поиск по префиксу для автодополнения."""
    async with aiosqlite.connect(DB_PATH) as db:
        db.row_factory = aiosqlite.Row
        q = f"{query}%"
        async with db.execute("""
            SELECT user_id, username, first_name, last_name, phone, status
            FROM users
            WHERE username LIKE ? OR first_name LIKE ? OR CAST(user_id AS TEXT) LIKE ?
            ORDER BY registered_at DESC LIMIT 10
        """, (q, q, q)) as c:
            return [dict(r) for r in await c.fetchall()]


async def get_all_users(limit=10, offset=0) -> list:
    async with aiosqlite.connect(DB_PATH) as db:
        db.row_factory = aiosqlite.Row
        async with db.execute(
            "SELECT * FROM users ORDER BY registered_at DESC LIMIT ? OFFSET ?",
            (limit, offset)
        ) as c:
            return [dict(r) for r in await c.fetchall()]


async def get_stats() -> dict:
    async with aiosqlite.connect(DB_PATH) as db:
        async with db.execute("SELECT COUNT(*) FROM users") as c:
            total = (await c.fetchone())[0]
        async with db.execute("SELECT COUNT(*) FROM users WHERE agreed_rules=1") as c:
            agreed = (await c.fetchone())[0]
        async with db.execute("SELECT COUNT(*) FROM users WHERE access_granted=1") as c:
            granted = (await c.fetchone())[0]
        async with db.execute("SELECT COUNT(*) FROM users WHERE status='pending' AND phone IS NOT NULL") as c:
            pending = (await c.fetchone())[0]
        async with db.execute("SELECT COUNT(*) FROM users WHERE status='rejected'") as c:
            rejected = (await c.fetchone())[0]
        return {
            "total": total, "agreed": agreed,
            "granted": granted, "pending": pending, "rejected": rejected
        }


async def get_user_by_username(username: str):
    async with aiosqlite.connect(DB_PATH) as db:
        db.row_factory = aiosqlite.Row
        async with db.execute(
            "SELECT * FROM users WHERE LOWER(username) = LOWER(?)", (username,)
        ) as c:
            row = await c.fetchone()
            return dict(row) if row else None
