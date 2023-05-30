from django.db import models
from datetime import datetime
# Create your models here.

class Game(models.Model):
    phone_number = models.CharField(default="", max_length=20)
    username = models.CharField(default="", max_length=50)
    location = models.CharField(default="", max_length=100)
    start_date = models.CharField(default="", max_length=20)
    start_time = models.CharField(default=0, max_length=15)
    min_players = models.IntegerField(default=0)
    max_players = models.IntegerField(default=0)
    created_at = models.DateTimeField(default=datetime.now)
    

class AdminUser(models.Model):
    game = models.ForeignKey(Game, on_delete=models.CASCADE)
    username = models.CharField(default="", max_length=50)
    phone_number = models.CharField(default="", max_length=20)


class Player(models.Model):
    game = models.ForeignKey(Game, on_delete=models.CASCADE)
    username = models.CharField(default="", max_length=50)
    phone_number = models.CharField(default="", max_length=20)
    is_playerlist = models.BooleanField(default=False)
    is_waitlist = models.BooleanField(default=False)
    is_outlist = models.BooleanField(default=False)
    is_blocked = models.BooleanField(default=False)
    joined_at = models.DateTimeField(default=datetime.now)
