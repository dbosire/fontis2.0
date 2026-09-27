import gzip
import os
import subprocess
from datetime import datetime
from zoneinfo import ZoneInfo

from decouple import config
from django.conf import settings
from django.core.management.base import BaseCommand, CommandError
from django.db import connections

from system_info.models import ScheduledTaskRun

BACKUP_DIR = settings.BASE_DIR / "backups"
KEEP_LAST = 30
MYSQLDUMP_BIN = config("MYSQLDUMP_PATH", default="mysqldump")


class Command(BaseCommand):
    help = (
        "Dumps the default database to a gzipped .sql file under backups/, prunes "
        "anything past the most recent KEEP_LAST, and logs a ScheduledTaskRun row "
        "the System Health page reads. Meant to be invoked by cron twice a day "
        "(see README) — pass --source manual for an on-demand run triggered from "
        "the System Health page's 'Back up now' button."
    )

    def add_arguments(self, parser):
        parser.add_argument(
            "--source", choices=[ScheduledTaskRun.CRON, ScheduledTaskRun.MANUAL],
            default=ScheduledTaskRun.CRON,
        )

    def handle(self, *args, **options):
        source = options["source"]
        BACKUP_DIR.mkdir(parents=True, exist_ok=True)
        db = connections["default"].settings_dict
        timestamp = datetime.now(ZoneInfo("Africa/Nairobi")).strftime("%Y%m%d-%H%M%S")
        filename = f"fontis-{timestamp}.sql.gz"
        filepath = BACKUP_DIR / filename

        cmd = [
            MYSQLDUMP_BIN,
            f"--host={db['HOST'] or '127.0.0.1'}",
            f"--port={db['PORT'] or '3306'}",
            f"--user={db['USER']}",
            "--single-transaction", "--quick", "--routines",
            db["NAME"],
        ]
        # Passed via env, never argv, so the DB password never shows up in `ps`.
        env = {**os.environ, "MYSQL_PWD": db["PASSWORD"]} if db["PASSWORD"] else dict(os.environ)

        try:
            result = subprocess.run(cmd, capture_output=True, timeout=300, env=env)
        except (OSError, subprocess.TimeoutExpired) as exc:
            self._log_failure(source, f"Could not run mysqldump: {exc}")
            raise CommandError(str(exc))

        if result.returncode != 0:
            detail = result.stderr.decode(errors="replace")[:4000]
            self._log_failure(source, detail)
            raise CommandError(detail)

        with gzip.open(filepath, "wb") as f:
            f.write(result.stdout)

        removed = self._prune()

        ScheduledTaskRun.objects.create(
            task="backup", source=source, status=ScheduledTaskRun.OK,
            output=f"Wrote {filename} ({filepath.stat().st_size:,} bytes)."
                   + (f" Pruned {removed} old backup(s)." if removed else ""),
        )
        self.stdout.write(self.style.SUCCESS(f"Backup written: {filename}"))

    def _log_failure(self, source, detail):
        ScheduledTaskRun.objects.create(task="backup", source=source, status=ScheduledTaskRun.FAILED, output=detail)

    def _prune(self):
        backups = sorted(BACKUP_DIR.glob("fontis-*.sql.gz"), key=lambda p: p.name, reverse=True)
        stale = backups[KEEP_LAST:]
        for path in stale:
            path.unlink(missing_ok=True)
        return len(stale)
