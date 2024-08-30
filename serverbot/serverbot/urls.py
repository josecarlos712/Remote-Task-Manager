from django.contrib import admin
from django.urls import path, include

urlpatterns = [
    path("admin/", admin.site.urls),
    path('', include('bot.urls')),
    path('accounts/', include('django.contrib.auth.urls')),
    # path('api/', include('bot.api.urls'))
]
