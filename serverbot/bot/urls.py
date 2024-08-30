from django.urls import path
from . import views


urlpatterns = [
    path('', views.homePage, name="home"),
    path('activity/<str:pk>/', views.activityPage, name="activity"),
    path('room/<str:pk>/', views.roomPage, name="room"),
    path('accounts/login/', views.login_view, name="login"),
    path('accounts/logout/', views.logout_view, name="logout"),
    path('programs/', views.component_programs_view, name="component_programs"),
    path('programs/<str:pk>/', views.load_program, name="program"),
    path('error', views.error_page, name="error"),
    path('cooking/', views.cooking, name="cooking"),
]
