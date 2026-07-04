import logging
from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession

logger = logging.getLogger(__name__)

async def verify_user_streak_columns(session: AsyncSession) -> None:
    """Check if the login streak columns exist in the users table, and add them if not."""
    try:
        # Test if columns exist
        await session.execute(text("SELECT last_login_date, current_streak, longest_streak FROM users LIMIT 1"))
    except Exception:
        await session.rollback()
        logger.info("Database streak columns missing. Performing auto-migration...")
        
        # Add columns one by one to support dialects cleanly
        statements = [
            "ALTER TABLE users ADD COLUMN last_login_date DATE",
            "ALTER TABLE users ADD COLUMN current_streak INTEGER DEFAULT 0",
            "ALTER TABLE users ADD COLUMN longest_streak INTEGER DEFAULT 0"
        ]
        
        for stmt in statements:
            try:
                await session.execute(text(stmt))
                await session.commit()
                logger.info(f"Executed: {stmt}")
            except Exception as e:
                await session.rollback()
                # Ignore if column already exists (e.g. if one existed but not others)
                if "already exists" in str(e).lower() or "duplicate column" in str(e).lower():
                    logger.debug(f"Column already exists: {stmt}")
                else:
                    logger.error(f"Failed to execute: {stmt}. Error: {e}")
