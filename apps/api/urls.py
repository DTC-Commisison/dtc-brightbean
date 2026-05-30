from django.urls import path

from . import views

urlpatterns = [
    path("openapi/", views.openapi_spec, name="openapi_spec"),
    path("webhooks/asset-received", views.asset_received, name="asset_received"),
]

