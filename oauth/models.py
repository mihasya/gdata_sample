from django.db import models
from django.contrib.auth.models import User

# Create your models here.
class GoogleAccount(models.Model):
    user = models.ForeignKey(User, verbose_name="For Which User")
    data = models.TextField()
    ctime = models.DateTimeField(auto_now_add=True)
