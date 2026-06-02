"""Reset django-axes lockouts and user failed-login counters."""

from django.core.management.base import BaseCommand

from accounts.models import User


class Command(BaseCommand):
    help = "Clear login lockouts (django-axes) and reset failed_login_attempts on users."

    def add_arguments(self, parser):
        parser.add_argument(
            "--email",
            type=str,
            help="Unlock a specific user email only.",
        )
        parser.add_argument(
            "--all",
            action="store_true",
            help="Clear all axes lockout records.",
        )
        parser.add_argument(
            "--ip",
            type=str,
            help="Clear lockouts for a specific IP address.",
        )

    def handle(self, *args, **options):
        from axes.models import AccessAttempt
        from axes.utils import reset

        email = options.get("email")
        ip = options.get("ip")
        clear_all = options.get("all")

        if email:
            reset(username=email)
            updated = User.objects.filter(email__iexact=email).update(failed_login_attempts=0)
            self.stdout.write(
                self.style.SUCCESS(f"Unlocked {email} (axes + {updated} user record(s)).")
            )
            return

        if ip:
            reset(ip=ip)
            self.stdout.write(self.style.SUCCESS(f"Cleared axes lockouts for IP {ip}."))
            return

        if clear_all or not (email or ip):
            count = AccessAttempt.objects.count()
            AccessAttempt.objects.all().delete()
            User.objects.update(failed_login_attempts=0)
            self.stdout.write(
                self.style.SUCCESS(
                    f"Cleared {count} axes attempt(s) and reset all user failed_login counters."
                )
            )
            return

        self.stdout.write(self.style.WARNING("Use --email, --ip, or --all."))
