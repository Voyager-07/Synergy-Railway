from django.contrib.auth.models import AbstractUser, Group, Permission
from django.db import models

class CustomUser(AbstractUser):
    profile_image = models.ImageField(upload_to='profile_images/', blank=True, null=True)
    full_name = models.CharField(max_length=150, blank=True, null=False)
    cc_username = models.CharField(max_length=100, blank=True, null=True)
    cf_username = models.CharField(max_length=100, blank=True, null=True)
    lc_username = models.CharField(max_length=100, blank=True, null=True)

    # Add related_name to avoid conflicts
    groups = models.ManyToManyField(Group, related_name="customuser_groups", blank=True)
    user_permissions = models.ManyToManyField(Permission, related_name="customuser_permissions", blank=True)

    def __str__(self):
        return self.email
