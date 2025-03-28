from django.contrib import admin
from django.conf.urls.static import static
from django.urls import path, include
from django.views.generic import TemplateView
from allauth.account.views import (
    PasswordResetFromKeyView,
    PasswordResetFromKeyDoneView,
    PasswordResetDoneView
)

from core import settings

urlpatterns = [
    path('admin/', admin.site.urls),
    path('accounts/', include('allauth.urls')),  # Django-Allauth authentication
    path(
        "accounts/password/reset/key/<uidb36>-<key>/",
        PasswordResetFromKeyView.as_view(),
        name="account_reset_password_from_key",
    ),
    path(
        "accounts/password/reset/key/done/",
        PasswordResetFromKeyDoneView.as_view(),
        name="account_reset_password_from_key_done",
    ),
    path('', include('app.urls')),
]

if settings.DEBUG:
    urlpatterns += static(settings.MEDIA_URL, document_root=settings.MEDIA_ROOT)