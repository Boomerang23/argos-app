# app/services.py
from __future__ import annotations

from datetime import datetime, timezone
from sqlalchemy.orm import Session
from thefuzz import process, fuzz

from . import models


class ScreeningService:
    def check_name(
        self,
        db: Session,
        name: str,
        organization_id: int,
        threshold: int = 80,
        limit: int = 3,
    ):
        """
        Compare 'name' aux sanctions du tenant (organization_id).
        token_set_ratio gère les prénoms inversés / composés.
        Retourne les matchs >= threshold.
        """
        sanctions = (
            db.query(models.Sanction)
            .filter(models.Sanction.organization_id == organization_id)
            .all()
        )

        if not sanctions:
            return []

        # mapping nom -> source
        sanctions_dict = {
            s.name: (s.list_source or "MANUAL") for s in sanctions
        }
        db_names = list(sanctions_dict.keys())

        matches = process.extract(
            name,
            db_names,
            scorer=fuzz.token_set_ratio,
            limit=limit,
        )

        results = []
        for match_name, score in matches:
            if score >= threshold:
                results.append(
                    {
                        "matched_name": match_name,
                        "score": round(float(score), 2),
                        "list_source": sanctions_dict[match_name],
                        "alert": True,
                    }
                )

        return results


def log_action(
    db: Session,
    user: models.User,
    action: str,
    target: str = "",
    details: str = "",
) -> None:
    """
    Audit log.
    - Tenant logs: organization_id=user.organization_id
    - Platform logs (SUPER_ADMIN global): organization_id=None autorisé

    IMPORTANT:  la colonne audit_logs.organization_id est nullable en DB
    si on veut logger les actions super admin.
    """
    db_log = models.AuditLog(
        organization_id=user.organization_id,  # None possible pour SUPER_ADMIN
        timestamp=datetime.now(timezone.utc).isoformat(),
        user_email=user.email,
        action=action,
        target=target,
        details=details,
    )
    db.add(db_log)
    db.commit()