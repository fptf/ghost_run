"""Назначение роли: `python -m app.scripts.set_role <email> <runner|moderator|admin>`."""

import sys

from app.infra.db import open_session
from app.infra.models import Role
from app.infra.users_repo import set_role_by_email


def main(argv: list[str], database_url: str | None = None) -> int:
    if len(argv) != 2 or argv[1] not in Role.__members__:
        print(__doc__, file=sys.stderr)
        return 2
    email, role = argv[0], Role(argv[1])
    with open_session(database_url) as session:
        try:
            user = set_role_by_email(session, email, role)
        except LookupError:
            print(f"Пользователь {email} не найден", file=sys.stderr)
            return 1
        print(f"{user.email}: {user.role}")
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
