from django.urls import path, get_resolver, URLPattern, URLResolver
from . import views, views_api
from .utils.APIResponse import SuccessResponse, BadMethodErrorResponse
from .views_api import logger


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
        cleaned_pattern = str(pattern).strip('/')

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


def api_get_tree(request):
    _method = 'GET'
    # If the request is None, the function returns if the function is 'GET' or 'POST'
    if not request:
        return _method

    if request.method == 'GET':
        # This functions gets the api tree from the urls.py variable 'urlpatterns', and gets the method calling the function with the parameter None.
        # It returns a dictionary with the api tree.
        api_tree = {}
        # Get the URL resolver for the root URLconf
        # Get the URL resolver for the root URLconf (settings.ROOT_URLCONF)
        resolver = get_resolver(None)  # None gets the root URLconf

        logger.debug("Starting to build simple API tree.")

        # Iterate through the URL patterns in the root URLconf
        # resolver.url_patterns contains a list of URLPattern and URLResolver instances
        def traverse_patterns(patterns, base_pattern=""):
            for url_pattern in patterns:
                # --- DEBUGGING: Log each pattern being considered ---
                logger.debug(f"Considering pattern: {url_pattern} (Base: {base_pattern})")
                # --- END DEBUGGING ---

                if isinstance(url_pattern, URLPattern):
                    # This is a direct URL pattern pointing to a view
                    # Get the string representation of the URL pattern
                    pattern_string = str(url_pattern.pattern)
                    full_url_pattern = base_pattern + pattern_string  # Combine with base pattern from inclusion

                    # Check if the full pattern starts with 'api/' to identify API endpoints
                    if full_url_pattern.startswith('api/'):
                        # Ensure the pattern has a name and a callback function (the view)
                        if hasattr(url_pattern, 'name') and url_pattern.name and hasattr(url_pattern,
                                                                                         'callback') and url_pattern.callback:
                            # --- DEBUGGING: Log pattern matching criteria ---
                            logger.debug(f"Pattern '{full_url_pattern}' matches 'api/' prefix and has name/callback.")
                            # --- END DEBUGGING ---
                            try:
                                # Get the supported methods from the custom 'supported_methods' attribute
                                # Use getattr with a default value ('N/A') if the attribute is not found
                                supported_methods = getattr(url_pattern.callback, 'supported_methods', 'N/A')

                                # Get the description from the view function's docstring
                                # Use getattr with a default value if the docstring is missing
                                description = getattr(url_pattern.callback, '__doc__', 'No description available.')
                                description = description.strip()  # Remove leading/trailing whitespace from docstring

                                # Use the URL pattern's name as the key in the tree
                                # Ensure the name is unique if you have duplicate names across includes
                                # For simplicity, using the name directly, but consider prefixing with base_pattern if names clash
                                api_tree[url_pattern.name] = {
                                    'url': full_url_pattern,  # Store the full URL pattern
                                    'methods': supported_methods,
                                    'description': description,
                                }
                                logger.debug(f"Added API endpoint to tree: {url_pattern.name} ({full_url_pattern})")

                            except Exception as e:
                                # Catch any unexpected errors during processing a specific pattern
                                logger.error(f"Error processing URL pattern '{full_url_pattern}' for API tree: {e}",
                                             exc_info=True)
                                # Add an entry indicating an error for this pattern
                                api_tree[url_pattern.name] = {
                                    'url': full_url_pattern,
                                    'methods': 'N/A',
                                    'description': f"Error retrieving details: {e}",
                                }
                                logger.debug(f"Error occurred for pattern '{full_url_pattern}'. Added error entry.")


                        else:
                            # Log patterns that start with 'api/' but lack name/callback
                            logger.debug(
                                f"Pattern '{full_url_pattern}' starts with 'api/' but lacks a name or callback. Skipping.")
                    else:
                        # Log patterns that do not start with 'api/'
                        logger.debug(f"Pattern '{full_url_pattern}' does not start with 'api/'. Skipping.")

                elif isinstance(url_pattern, URLResolver):
                    # This is an included URL configuration, traverse recursively
                    # Get the base pattern for the included URLs
                    included_base_pattern = base_pattern + str(url_pattern.pattern)
                    logger.debug(f"Traversing included URL patterns at base: {included_base_pattern}")
                    # Recursively call traverse_patterns with the included patterns and the new base pattern
                    traverse_patterns(url_pattern.url_patterns, included_base_pattern)

        # Start the traversal from the root URLconf's patterns
        traverse_patterns(resolver.url_patterns)
        # Return a JsonResponse instance with the data and status code
        api_response_data = SuccessResponse("Árbol de endpoints API", api_tree)
        return api_response_data.to_response()  # Return JsonResponse

    else:
        # Handle methods other than GET
        logger.warning(f"Received unsupported method '{request.method}' for API tree endpoint.")
        # Return a JsonResponse instance for the error response
        api_response_data = BadMethodErrorResponse(request.method, _method)
        return api_response_data.to_response()  # Return JsonResponse


urlpatterns = [
    path('', views.homePage, name="home"),
    path('activity/<str:pk>/', views.activity_page, name="activity"),
    path('room/<str:pk>/', views.room_page, name="room"),
    path('accounts/login/', views.login_view, name="login"),
    # path('accounts/logout/', views.logout_view, name="logout"),
    path('accounts/register', views.register_view, name="register"),
    path('programs/', views.component_programs_view, name="component_programs"),
    path('programs/<str:pk>/', views.load_program, name="program"),
    path('error', views.error_page, name="error"),
    path('cooking/', views.cooking, name="cooking"),
    path('about', views.about_view, name="about"),

    # API URLs
    # path('api/data/<str:pk>', views_api.api_data, name='get_data'),
    path('api/data/tree', api_get_tree, name='get_tree'),
    path('api/command/list', views_api.api_update_commands_list, name='get_command_list'),
    path('api/command/execute', views_api.api_execute_command, name='execute_command'),
    path('api/accounts/register', views_api.api_register, name="api_register"),
    path('api/accounts/login', views_api.api_login, name="api_login"),
    path('api/accounts/logout', views_api.api_logout, name="api_logout"),
    path('api/refresh/processes_status/', views_api.refresh_processes_status, name="refresh_processes_status"),
]
