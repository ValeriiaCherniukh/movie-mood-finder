from django.urls import path
from . import views

urlpatterns = [
    path("lists/", views.my_lists, name="my_lists"),
    path("lists/add/", views.add_to_list, name="add_to_list"),
    path("lists/update/<int:pk>/", views.update_status, name="update_status"),
    path("lists/remove/<int:pk>/", views.remove_from_list, name="remove_from_list"),
    path("lists/add-tmdb/", views.add_tmdb_to_list, name="add_tmdb_to_list"),

]
