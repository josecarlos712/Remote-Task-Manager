from django.urls import path
from . import views, views_api

urlpatterns = [
    path('', views.homePage, name="home"),
    path('activity/<str:pk>/', views.activity_page, name="activity"),
    path('room/<str:pk>/', views.room_page, name="room"),
    path('accounts/login/', views.login_view, name="login"),
    #path('accounts/logout/', views.logout_view, name="logout"),
    path('accounts/register', views.register_view, name="register"),
    path('programs/', views.component_programs_view, name="component_programs"),
    path('programs/<str:pk>/', views.load_program, name="program"),
    path('error', views.error_page, name="error"),
    path('cooking/', views.cooking, name="cooking"),
    path('about', views.about_view, name="about"),

    # API URLs
    #path('api/data/<str:pk>', views_api.api_data, name='get_data'),
    path('api/data/tree', views_api.api_get_tree, name='get_tree'),
    path('api/command/execute', views_api.api_command, name='execute_command'),
    path('api/accounts/register', views_api.api_register, name="api_register"),
    path('api/accounts/login', views_api.api_login, name="api_login"),
    path('api/accounts/logout', views_api.api_logout, name="api_logout"),
    path('api/refresh/processes_status/', views_api.refresh_processes_status, name="refresh_processes_status"),
]


def build_api_tree():
    """
    Builds a tree structure of API endpoints from a list of URL patterns.

    Args:
        url_patterns: A list of strings, where each string is a URL pattern.

    Returns:
        A dictionary representing the tree structure of API endpoints.
    """
    api_tree = {}

    for pattern in urlpatterns:
        # Clean up the pattern (remove leading/trailing slashes if necessary)
        cleaned_pattern = pattern.strip('/')

        if cleaned_pattern.startswith('api/'):
            # Remove the 'api/' prefix
            api_path = cleaned_pattern[len('api/'):]
            # Split the path into components
            components = api_path.split('/')

            current_level = api_tree
            for i, component in enumerate(components):
                if component not in current_level:
                    current_level[component] = {}
                # Move to the next level
                current_level = current_level[component]

    return api_tree
