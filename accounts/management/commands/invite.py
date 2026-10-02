from pathlib import Path

from django.core.exceptions import ValidationError
from django.core.management.base import BaseCommand, CommandError
from django.core.validators import validate_email

from accounts.models import User


class Command(BaseCommand):
    help = "Invite participants by email so they can sign in with a one-time code."

    def add_arguments(self, parser):
        parser.add_argument("emails", nargs="*", help="Email addresses to invite")
        parser.add_argument("--file", type=Path, help="Text file with one email per line")

    def handle(self, *args, emails, file, **options):
        emails = list(emails)
        if file:
            emails += [line.strip() for line in file.read_text().splitlines()]
        emails = [e.lower() for e in emails if e and not e.startswith("#")]
        if not emails:
            raise CommandError("Give at least one email address or --file.")

        created = existing = 0
        for email in emails:
            try:
                validate_email(email)
            except ValidationError:
                self.stderr.write(f"Skipping invalid address: {email}")
                continue
            user = User.objects.filter(email=email).first()
            if user:
                if not user.is_active:
                    user.is_active = True
                    user.save(update_fields=["is_active"])
                existing += 1
            else:
                User.objects.create_user(email)
                created += 1
        self.stdout.write(self.style.SUCCESS(f"Invited {created} new, {existing} already invited."))
