from django.urls import path
from django.conf.urls.static import static
from django.conf import settings
from . import views

app_name='whatsapp'
urlpatterns = [
    path('', views.index, name="index"),
    # path('whatsapi', views.whatsapi, name='whatsapi'),
    path('incoming_message', views.incoming_message, name='incoming_message'),
] + static(settings.MEDIA_URL, document_root=settings.MEDIA_ROOT)