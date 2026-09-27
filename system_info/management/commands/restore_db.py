import gzip
import os
import subprocess

from decouple import config
from django.core.management.base import BaseCommand, CommandError
from django.db import connections

from .backup_db import BACKUP_DIR

MYSQL_BIN = config("MYSQL_PATH", default="mysql")


class Command(BaseCommand):
    help = (
        "Restores the default database from a backup produced by backup_db (a "
        ".sql.gz file under backups/). DESTRUCTIVE — replaces every table in the "
        "live database. CLI-only by design, never exposed as a web action: takes "
        "--yes to actually run, otherwise just prints what it would do."
    )

    def add_arguments(self, parser):
        parser.add_argument("filename", help="Backup filename as shown on the System Health page, not a full path.")
        parser.add_argument("--yes", action="store_true", help="Actually perform the restore (required).")

    def handle(self, *args, **options):
        filename = options["filename"]
        if "/" in filename or "\\" in filename or not filename.endswith(".sql.gz"):
            raise CommandError("Give just the backup's filename (as shown on the System Health page), not a path.")
        filepath = BACKUP_DIR / filename
        if not filepath.is_file():
            raise CommandError(f"No such backup: {filepath}")

        db = connections["default"].settings_dict
        if not options["yes"]:
            self.stdout.write(self.style.WARNING(
                f"This would REPLACE every table in database '{db['NAME']}' with the contents of {filename}.\n"
                f"Re-run with --yes to actually do it."
            ))
            return

        cmd = [
            MYSQL_BIN,
            f"--host={db['HOST'] or '127.0.0.1'}",
            f"--port={db['PORT'] or '3306'}",
            f"--user={db['USER']}",
            db["NAME"],
        ]
        env = {**os.environ, "MYSQL_PWD": db["PASSWORD"]} if db["PASSWORD"] else dict(os.environ)

        with gzip.open(filepath, "rb") as f:
            result = subprocess.run(cmd, input=f.read(), capture_output=True, env=env)

        if result.returncode != 0:
            raise CommandError(result.stderr.decode(errors="replace")[:4000])

        self.stdout.write(self.style.SUCCESS(f"Restored from {filename}."))
