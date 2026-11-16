"""
20261116_lock_screen_name_full_default — Live Activity kilit ekranı varsayılan olarak tam isim gösterir.

The Settings model default used to be "initials", so profile/online-booking saves and
settings inserts wrote an explicit "initials" into `settings.lock_screen_name_mode`.
No UI has ever let an org choose the mode, so every stored "initials" is a default
artifact. Unsetting it lets the "missing means full" rule (live_activity.content.name_mode)
apply. "full" and "hidden" are left alone.

Not reversible: the stored "initials" values carried no choice, so there is nothing to restore.
"""

REVERSIBLE = False
DESCRIPTION = "Live Activity: drop default-artifact lock_screen_name_mode='initials' (full name is the default)"


async def up(db):
    await db.settings.update_many(
        {"lock_screen_name_mode": "initials"},
        {"$unset": {"lock_screen_name_mode": ""}},
    )


async def down(db):
    """No-op: the removed "initials" values were model-default artifacts, not org choices."""
    return None
