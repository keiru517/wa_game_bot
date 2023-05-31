from django.urls import path
from django.conf.urls.static import static
from django.conf import settings
from . import views

app_name='whatsapp'
urlpatterns = [
    path('', views.index, name="index"),
    path('games', views.games, name="games"),
    path('players', views.players, name="players"),
    # path('login', views.login_view, name="login_view"),
    # path('register', views.register_view, name="register_view"),
    # path('register_user', views.register, name="register"),
    # path('clients', views.clients, name="clients"),
    # path('library', views.library, name="library"),
    # path('upload', views.upload_view, name="upload_view"),
    # path('upload_file', views.upload, name="upload"),
    # path('prompts', views.prompts, name="prompts"),
    path('settings', views.settings, name="settings"),
    path('help', views.help, name="help"),
    path('contact', views.contact, name="contact"),
    # path('signout', views.sign_out, name="sign_out"),
    # path('get_percentage', views.get_percentage, name="get_percentage"),

    path('incoming_message', views.incoming_message, name='incoming_message'),
    
] + static(settings.MEDIA_URL, document_root=settings.MEDIA_ROOT)