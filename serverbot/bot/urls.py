from django.urls import path
from . import views, views_api

urlpatterns = [
    path('', views.homePage, name="home"),
    path('activity/<str:pk>/', views.activity_page, name="activity"),
    path('room/<str:pk>/', views.room_page, name="room"),
    path('accounts/login/', views.login_view, name="login"),
    path('accounts/logout/', views.logout_view, name="logout"),
    path('programs/', views.component_programs_view, name="component_programs"),
    path('programs/<str:pk>/', views.load_program, name="program"),
    path('error', views.error_page, name="error"),
    path('cooking/', views.cooking, name="cooking"),

    # API URLs
    path('api/data/', views_api.api_data, name='get_data'),
    path('api/command', views_api.execute_function, name='execute_function'),
    path('api/test_page/', views_api.test_page, name="test_page"),
    path('api/refresh/processes_status/', views_api.refresh_processes_status, name="refresh_processes_status"),
]
