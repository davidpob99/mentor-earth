import hashlib
import secrets
from datetime import timedelta

from django.conf import settings
from django.contrib.auth.models import AbstractBaseUser, BaseUserManager, PermissionsMixin
from django.db import models
from django.utils import timezone


class UserManager(BaseUserManager):
    use_in_migrations = True

    def create_user(self, email, password=None, **extra):
        if not email:
            raise ValueError("An email address is required.")
        user = self.model(email=self.normalize_email(email).lower(), **extra)
        if password:
            user.set_password(password)
        else:
            user.set_unusable_password()
        user.save(using=self._db)
        return user

    def create_superuser(self, email, password=None, **extra):
        extra.setdefault("is_staff", True)
        extra.setdefault("is_superuser", True)
        return self.create_user(email, password, **extra)


class CareerStage(models.TextChoices):
    PHD = "phd", "PhD student"
    POSTDOC = "postdoc", "Postdoc"
    SCIENTIST = "scientist", "Research scientist"
    FACULTY = "faculty", "Faculty"
    STAFF = "staff", "Staff"
    OTHER = "other", "Other"


class User(AbstractBaseUser, PermissionsMixin):
    """A participant. Inviting someone means creating a User with their email."""

    email = models.EmailField(unique=True)
    full_name = models.CharField(max_length=120, blank=True)
    research_topic = models.CharField(
        max_length=120, blank=True, help_text="e.g. Computational neuroscience"
    )
    career_stage = models.CharField(max_length=20, choices=CareerStage.choices, blank=True)
    photo = models.ImageField(upload_to="photos/", blank=True)
    is_active = models.BooleanField(default=True)
    is_staff = models.BooleanField(default=False)
    date_joined = models.DateTimeField(default=timezone.now)

    objects = UserManager()

    USERNAME_FIELD = "email"
    EMAIL_FIELD = "email"
    REQUIRED_FIELDS = []

    class Meta:
        ordering = ["full_name", "email"]

    def __str__(self):
        return self.full_name or self.email

    @property
    def profile_completed(self):
        return bool(self.full_name and self.research_topic and self.career_stage)

    @property
    def first_name(self):
        return (self.full_name or self.email).split()[0]

    @property
    def initials(self):
        parts = (self.full_name or self.email).split()
        return "".join(p[0] for p in parts[:2]).upper()

    @property
    def avatar_hue(self):
        return int(hashlib.md5(self.email.encode()).hexdigest()[:4], 16) % 360


def _hash_code(code):
    return hashlib.sha256(code.encode()).hexdigest()


class LoginCode(models.Model):
    user = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name="login_codes")
    code_hash = models.CharField(max_length=64)
    created_at = models.DateTimeField(auto_now_add=True)
    expires_at = models.DateTimeField()
    attempts = models.PositiveSmallIntegerField(default=0)
    used_at = models.DateTimeField(null=True, blank=True)

    class Meta:
        ordering = ["-created_at"]

    @classmethod
    def issue(cls, user):
        """Invalidate previous codes and return (LoginCode, plaintext code)."""
        cls.objects.filter(user=user, used_at__isnull=True).update(used_at=timezone.now())
        code = f"{secrets.randbelow(1_000_000):06d}"
        obj = cls.objects.create(
            user=user,
            code_hash=_hash_code(code),
            expires_at=timezone.now() + timedelta(minutes=settings.LOGIN_CODE_TTL_MINUTES),
        )
        return obj, code

    @property
    def is_usable(self):
        return (
            self.used_at is None
            and self.expires_at > timezone.now()
            and self.attempts < settings.LOGIN_CODE_MAX_ATTEMPTS
        )

    def check_code(self, code):
        """Count the attempt; on success mark the code as used."""
        if not self.is_usable:
            return False
        if secrets.compare_digest(self.code_hash, _hash_code(code.strip())):
            self.used_at = timezone.now()
            self.save(update_fields=["used_at"])
            return True
        self.attempts += 1
        self.save(update_fields=["attempts"])
        return False
