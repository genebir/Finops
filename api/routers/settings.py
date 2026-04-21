"""Settings endpoints — runtime threshold config in platform_settings.

GET    /api/settings          → all settings
GET    /api/settings/{key}    → single setting
POST   /api/settings          → create new setting
PUT    /api/settings/{key}    → update value
DELETE /api/settings/{key}    → delete setting
"""

from fastapi import APIRouter, HTTPException
from starlette.responses import Response

from ..deps import columns, db_read, db_write, tables
from ..models import SettingCreateRequest, SettingItem, SettingsResponse, SettingUpdateRequest

router = APIRouter(tags=["settings"])


def _select_expr(cols: set[str]) -> str:
    """Build the SELECT list based on which columns exist."""
    value_type = "value_type" if "value_type" in cols else "'str' AS value_type"
    description = "description" if "description" in cols else "NULL AS description"
    return f"key, value, {value_type}, {description}"


@router.get("/api/settings", response_model=SettingsResponse)
def get_settings() -> SettingsResponse:
    with db_read() as db:
        if "platform_settings" not in tables(db):
            return SettingsResponse(items=[])
        cur = db.cursor()
        cols = columns(db, "platform_settings")
        cur.execute(
            f"SELECT {_select_expr(cols)} FROM platform_settings ORDER BY key"
        )
        rows = cur.fetchall()
        cur.close()
        return SettingsResponse(
            items=[
                SettingItem(
                    key=r[0], value=str(r[1]),
                    value_type=r[2] or "str",
                    description=r[3],
                )
                for r in rows
            ]
        )


@router.get("/api/settings/{key}", response_model=SettingItem)
def get_setting(key: str) -> SettingItem:
    with db_read() as db:
        if "platform_settings" not in tables(db):
            raise HTTPException(status_code=404, detail="platform_settings table not found")
        cur = db.cursor()
        cols = columns(db, "platform_settings")
        cur.execute(
            f"SELECT {_select_expr(cols)} FROM platform_settings WHERE key = %s",
            [key],
        )
        row = cur.fetchone()
        cur.close()
        if not row:
            raise HTTPException(status_code=404, detail=f"Setting '{key}' not found")
        return SettingItem(
            key=row[0], value=str(row[1]),
            value_type=row[2] or "str",
            description=row[3],
        )


@router.post("/api/settings", response_model=SettingItem, status_code=201)
def create_setting(body: SettingCreateRequest) -> SettingItem:
    """Create a new setting. Returns 409 if the key already exists."""
    with db_write() as db:
        if "platform_settings" not in tables(db):
            raise HTTPException(status_code=404, detail="platform_settings table not found")
        cur = db.cursor()
        cur.execute("SELECT key FROM platform_settings WHERE key = %s", [body.key])
        if cur.fetchone():
            cur.close()
            raise HTTPException(status_code=409, detail=f"Setting '{body.key}' already exists")

        cur.execute(
            "INSERT INTO platform_settings (key, value, value_type, description) "
            "VALUES (%s, %s, %s, %s)",
            [body.key, body.value, body.value_type, body.description],
        )
        cur.close()
        return SettingItem(
            key=body.key, value=body.value,
            value_type=body.value_type,
            description=body.description,
        )


@router.put("/api/settings/{key}", response_model=SettingItem)
def update_setting(key: str, body: SettingUpdateRequest) -> SettingItem:
    """Update an existing setting's value."""
    with db_write() as db:
        if "platform_settings" not in tables(db):
            raise HTTPException(status_code=404, detail="platform_settings table not found")
        cur = db.cursor()
        cols = columns(db, "platform_settings")
        cur.execute(
            "SELECT key FROM platform_settings WHERE key = %s", [key]
        )
        if not cur.fetchone():
            cur.close()
            raise HTTPException(status_code=404, detail=f"Setting '{key}' not found")

        if "updated_at" in cols:
            cur.execute(
                "UPDATE platform_settings SET value = %s, updated_at = NOW() WHERE key = %s",
                [body.value, key],
            )
        else:
            cur.execute(
                "UPDATE platform_settings SET value = %s WHERE key = %s",
                [body.value, key],
            )

        cur.execute(
            f"SELECT {_select_expr(cols)} FROM platform_settings WHERE key = %s",
            [key],
        )
        row = cur.fetchone()
        cur.close()
        assert row is not None
        return SettingItem(
            key=row[0], value=str(row[1]),
            value_type=row[2] or "str",
            description=row[3],
        )


@router.delete("/api/settings/{key}", status_code=204)
def delete_setting(key: str) -> Response:
    """Delete a setting by key."""
    with db_write() as db:
        if "platform_settings" not in tables(db):
            raise HTTPException(status_code=404, detail="platform_settings table not found")
        cur = db.cursor()
        cur.execute("SELECT key FROM platform_settings WHERE key = %s", [key])
        if not cur.fetchone():
            cur.close()
            raise HTTPException(status_code=404, detail=f"Setting '{key}' not found")
        cur.execute("DELETE FROM platform_settings WHERE key = %s", [key])
        cur.close()
        return Response(status_code=204)
