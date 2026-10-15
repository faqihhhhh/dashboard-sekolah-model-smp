from django.contrib.auth.models import AbstractBaseUser, BaseUserManager, PermissionsMixin
from django.db import models
from django.utils import timezone


class Role(models.TextChoices):
    """Peran akun. Guest tidak punya akun (pengunjung tanpa login)."""

    VIEWER = "viewer", "Viewer"
    ADMIN = "admin", "Admin"
    SUPER_ADMIN = "super_admin", "Super Admin"


# Semakin besar angkanya, semakin luas hak aksesnya.
ROLE_RANK = {Role.VIEWER: 1, Role.ADMIN: 2, Role.SUPER_ADMIN: 3}


class UserManager(BaseUserManager):
    use_in_migrations = True

    def _create_user(self, email, password, **extra_fields):
        if not email:
            raise ValueError("Email wajib diisi.")
        user = self.model(email=self.normalize_email(email), **extra_fields)
        user.set_password(password)
        user.save(using=self._db)
        return user

    def create_user(self, email, password=None, **extra_fields):
        extra_fields.setdefault("role", Role.VIEWER)
        return self._create_user(email, password, **extra_fields)

    def create_superuser(self, email, password=None, **extra_fields):
        extra_fields["role"] = Role.SUPER_ADMIN
        return self._create_user(email, password, **extra_fields)


class User(AbstractBaseUser, PermissionsMixin):
    email = models.EmailField("email", unique=True)
    full_name = models.CharField("nama lengkap", max_length=150)
    role = models.CharField("peran", max_length=20, choices=Role.choices, default=Role.VIEWER)
    is_active = models.BooleanField("aktif", default=True)
    is_staff = models.BooleanField("akses admin Django", default=False, editable=False)
    date_joined = models.DateTimeField("tanggal bergabung", default=timezone.now)

    objects = UserManager()

    USERNAME_FIELD = "email"
    REQUIRED_FIELDS = ["full_name"]

    class Meta:
        verbose_name = "pengguna"
        verbose_name_plural = "pengguna"

    def __str__(self):
        return f"{self.full_name} <{self.email}>"

    def get_full_name(self):
        return self.full_name

    def get_short_name(self):
        return self.full_name.split(" ")[0] if self.full_name else self.email

    def save(self, *args, **kwargs):
        self.email = self.email.strip().lower()
        # Akses ke /admin (Django) hanya untuk Super Admin; selalu mengikuti peran.
        is_super = self.role == Role.SUPER_ADMIN
        self.is_staff = is_super
        self.is_superuser = is_super
        super().save(*args, **kwargs)


class LoginThrottle(models.Model):
    """Jendela percobaan login yang dibagi semua worker aplikasi."""

    key = models.CharField(max_length=64, unique=True)
    failures = models.PositiveSmallIntegerField(default=0)
    window_started = models.DateTimeField(default=timezone.now)
    blocked_until = models.DateTimeField(null=True, blank=True)
    updated_at = models.DateTimeField(auto_now=True, db_index=True)
