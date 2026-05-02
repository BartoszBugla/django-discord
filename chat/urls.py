from django.urls import path
from . import views

app_name = "chat"

urlpatterns = [
    path('', views.home, name='home'),
    path('register/', views.register_view, name='register'),
    path('login/', views.login_view, name='login'),
    path('logout/', views.logout_view, name='logout'),
    path('presence/<int:user_id>/', views.presence_status, name='presence_status'),
    path('profil/<int:user_id>/', views.profile_view, name='profile'),
    path('profil/edytuj/', views.edit_profile, name='edit_profile'),
    path('kanal/nowy/', views.create_channel, name='create_channel'),
    path('kanal/<int:channel_id>/', views.channel_view, name='channel'),
    path('kanal/<int:channel_id>/dolacz/', views.join_channel, name='join_channel'),
    path('kanal/<int:channel_id>/dodaj-czlonka/', views.add_channel_member, name='add_channel_member'),
    path('kanal/<int:channel_id>/usun/', views.delete_channel, name='delete_channel'),
    path('kanal/<int:channel_id>/opusc/', views.leave_channel, name='leave_channel'),
    path('dm/', views.dm_list, name='dm_list'),
    path('dm/<int:user_id>/', views.dm_view, name='dm'),
    path('wiadomosc/<int:message_id>/usun/', views.delete_message, name='delete_message'),
    path('wiadomosc/<int:message_id>/reakcja/', views.add_reaction, name='add_reaction'),
    path('uzytkownik/<int:user_id>/rola/', views.change_role, name='change_role'),
    path(
        'powiadomienia/odczytaj/<int:pk>/',
        views.notification_mark_read,
        name='notification_mark_read',
    ),
    path('powiadomienia/', views.notifications_settings, name='notifications_settings'),
    path('szukaj/', views.search_view, name='search'),
    path('api/szukaj/', views.search_api, name='search_api'),
    path('panel/', views.admin_users, name='admin_users'),
    path(
        'panel/uzytkownik/<int:user_id>/konto/',
        views.admin_toggle_user_active,
        name='admin_toggle_user_active',
    ),
]
