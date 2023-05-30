from django.contrib import admin
from .models import AdminUser, Game, Player
# Register your models here.
admin.site.register(AdminUser)
admin.site.register(Game)
admin.site.register(Player)