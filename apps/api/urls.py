from django.urls import path

from . import views

urlpatterns = [path("openapi/", views.openapi_spec, name="openapi_spec")]
