from getpass import getpass

from pydantic import EmailStr, TypeAdapter
from sqlalchemy import func, select

from app.core.security import hash_password
from app.db.session import SessionLocal
from app.models import AuditLog, Role, User
from app.schemas import validate_strong_password


def main() -> None:
    email = TypeAdapter(EmailStr).validate_python(input("Initial Admin email: ").strip()).lower()
    full_name = input("Admin full name: ").strip()
    password = getpass("Initial Admin password (12+ chars, upper/lower/number/symbol): ")
    validate_strong_password(password)
    if not email or not full_name:
        raise SystemExit("Email and full name are required")

    with SessionLocal() as db:
        if (db.scalar(select(func.count()).select_from(User)) or 0) > 0:
            raise SystemExit("Bootstrap refused: users already exist. Use the Admin user-management API.")
        user = User(
            email=email,
            full_name=full_name,
            role=Role.ADMIN.value,
            password_hash=hash_password(password),
            is_active=True,
            must_change_password=False,
        )
        db.add(user)
        db.flush()
        db.add(AuditLog(
            actor_id=user.id,
            action="user.bootstrap_admin_created",
            target_type="user",
            target_id=str(user.id),
            details={},
        ))
        db.commit()
        print(f"Initial Admin account created: {email}")


if __name__ == "__main__":
    main()
