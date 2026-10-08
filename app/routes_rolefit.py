"""Role fit for a stored CV: one role, or all 8 roles side by side. Results are saved on the CV, per role."""
import json
from concurrent.futures import ThreadPoolExecutor
from datetime import datetime, timezone

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel
from sqlalchemy.orm import Session

from .agents.role_fit import ROLES, check_role_fit
from .db import get_db
from .limits import budget_block_message, enforce_budget, enforce_rate_limit
from .models import Recommendation, User
from .security import get_current_user

router = APIRouter(prefix="/cv", tags=["role-fit"])


class FitIn(BaseModel):
    role: str  # one of ROLES, or "all"


@router.post("/recommendations/{rec_id}/role-fit")
def role_fit(rec_id: int, body: FitIn, user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    if body.role != "all" and body.role not in ROLES:
        raise HTTPException(422, f"role must be 'all' or one of: {', '.join(ROLES)}")
    rec = db.get(Recommendation, rec_id)
    if rec is None or (user.role != "admin" and rec.user_id != user.id):
        raise HTTPException(404, "Recommendation not found")
    cv_text = rec.cv_text or ""
    if not cv_text.strip():
        raise HTTPException(409, "This CV was classified before its text was stored. Upload it again to check role fit.")

    roles = ROLES if body.role == "all" else [body.role]
    enforce_budget(db, user)
    enforce_rate_limit(db, user, weight=len(roles))

    def one(role: str):
        blocked = budget_block_message(user)
        try:
            return role, ({"ok": False, "error": blocked} if blocked else check_role_fit(user, cv_text, role))
        except Exception as e:  # one role failing must not discard the others
            return role, {"ok": False, "error": f"{type(e).__name__}: {e}"}

    with ThreadPoolExecutor(max_workers=4) as pool:
        outcomes = dict(pool.map(one, roles))

    saved = json.loads(rec.role_fit_json) if rec.role_fit_json else {}
    errors = {}
    for role, out in outcomes.items():
        if out["ok"]:
            saved[role] = {**out["result"], "ts": datetime.now(timezone.utc).isoformat()}
        else:
            errors[role] = out["error"]
    if len(errors) == len(roles):
        raise HTTPException(502, f"Role fit failed: {next(iter(errors.values()))}")
    rec.role_fit_json = json.dumps(saved)
    db.commit()
    return {"recommendation_id": rec.id, "role_fit": saved, "errors": errors}
