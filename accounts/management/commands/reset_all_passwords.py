import secrets

from django.core.management.base import BaseCommand

from accounts.models import User


class Command(BaseCommand):
    help = (
        "One-time cutover command: sets every user's password to a fresh random "
        "Django-hashed temporary password and flags must_change_password=True. "
        "Never touches the legacy MD5 value. Run once against staging to rehearse, "
        "then once for real against production during the Phase 9 maintenance window."
    )

    def add_arguments(self, parser):
        parser.add_argument(
            "--length", type=int, default=10, help="Length of the generated temporary password."
        )

    def handle(self, *args, **options):
        length = options["length"]
        users = User.objects.all()
        if not users.exists():
            self.stdout.write(self.style.WARNING("No users found."))
            return

        for user in users:
            temp_password = secrets.token_urlsafe(length)[:length]
            user.set_password(temp_password)
            user.must_change_password = True
            user.save(update_fields=["password", "must_change_password"])
            self.stdout.write(f"{user.username}: {temp_password}")

        self.stdout.write(
            self.style.SUCCESS(
                f"Reset passwords for {users.count()} user(s). "
                "Communicate the temporary passwords above securely and have each "
                "user change theirs on first login."
            )
        )
