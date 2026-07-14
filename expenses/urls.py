from django.urls import path

from . import views

app_name = "expenses"

urlpatterns = [
    path("", views.ExpenseListView.as_view(), name="list"),
    path("add/", views.ExpenseCreateView.as_view(), name="add"),
    path("<int:pk>/edit/", views.ExpenseUpdateView.as_view(), name="edit"),
    path("<int:pk>/delete/", views.ExpenseDeleteView.as_view(), name="delete"),
    path("categories/", views.ExpenseCategoryListView.as_view(), name="categories"),
    path("categories/add/", views.ExpenseCategoryCreateView.as_view(), name="category_add"),
]
