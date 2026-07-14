from django.contrib.auth.base_user import AbstractBaseUser, BaseUserManager
from django.contrib.auth.models import PermissionsMixin
from django.db import models


class UserManager(BaseUserManager):
    def create_user(self, username, firstname, lastname, password=None, **extra_fields):
        if not username:
            raise ValueError("Username is required")
        user = self.model(username=username, firstname=firstname, lastname=lastname, **extra_fields)
        user.set_password(password)
        user.save(using=self._db)
        return user

    def create_superuser(self, username, firstname, lastname, password=None, **extra_fields):
        extra_fields.setdefault("is_staff", True)
        extra_fields.setdefault("is_superuser", True)
        extra_fields.setdefault("type", User.TYPE_ADMIN)
        return self.create_user(username, firstname, lastname, password, **extra_fields)


class User(AbstractBaseUser, PermissionsMixin):
    TYPE_ADMIN = 1
    TYPE_CUSTOMER_LEGACY = 2  # kept for row compatibility only; no active login path uses this
    TYPE_CHOICES = [(TYPE_ADMIN, "Admin"), (TYPE_CUSTOMER_LEGACY, "Customer (legacy)")]

    id = models.AutoField(primary_key=True)
    firstname = models.CharField(max_length=250)
    lastname = models.CharField(max_length=250)
    username = models.CharField(max_length=255, unique=True)
    avatar = models.CharField(max_length=255, null=True, blank=True)
    type = models.PositiveSmallIntegerField(choices=TYPE_CHOICES, default=TYPE_ADMIN)
    date_added = models.DateTimeField(auto_now_add=True)
    date_updated = models.DateTimeField(auto_now=True, null=True)

    must_change_password = models.BooleanField(default=False)
    is_active = models.BooleanField(default=True)
    is_staff = models.BooleanField(default=True)

    objects = UserManager()

    USERNAME_FIELD = "username"
    REQUIRED_FIELDS = ["firstname", "lastname"]

    class Meta:
        db_table = "users"
        managed = False

    def __str__(self):
        return self.username

    def get_full_name(self):
        return f"{self.firstname} {self.lastname}".strip()

    def get_short_name(self):
        return self.firstname
