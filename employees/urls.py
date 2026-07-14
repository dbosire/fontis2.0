from django.urls import path

from . import views

app_name = "employees"

urlpatterns = [
    path("", views.EmployeeListView.as_view(), name="list"),
    path("add/", views.EmployeeCreateView.as_view(), name="add"),
    path("<int:pk>/", views.EmployeeDetailView.as_view(), name="detail"),
    path("<int:pk>/edit/", views.EmployeeUpdateView.as_view(), name="edit"),
    path("<int:pk>/delete/", views.EmployeeDeleteView.as_view(), name="delete"),

    path("departments/", views.DepartmentListView.as_view(), name="departments"),
    path("departments/add/", views.DepartmentCreateView.as_view(), name="department_add"),
    path("departments/<int:pk>/delete/", views.DepartmentDeleteView.as_view(), name="department_delete"),

    path("roles/", views.RoleListView.as_view(), name="roles"),
    path("roles/add/", views.RoleFormView.as_view(), name="role_add"),
    path("roles/<int:pk>/edit/", views.RoleFormView.as_view(), name="role_edit"),
    path("roles/<int:pk>/delete/", views.RoleDeleteView.as_view(), name="role_delete"),

    path("store/", views.EmployeeAssetListView.as_view(), name="assets"),
    path("store/add/", views.EmployeeAssetCreateView.as_view(), name="asset_add"),
    path("store/<int:pk>/edit/", views.EmployeeAssetUpdateView.as_view(), name="asset_edit"),
    path("store/<int:pk>/delete/", views.EmployeeAssetDeleteView.as_view(), name="asset_delete"),

    path("attendance/", views.AttendanceListView.as_view(), name="attendance"),
    path("attendance/add/", views.AttendanceCreateView.as_view(), name="attendance_add"),
    path("attendance/<int:pk>/delete/", views.AttendanceDeleteView.as_view(), name="attendance_delete"),

    path("leave/", views.LeaveRequestListView.as_view(), name="leave"),
    path("leave/add/", views.LeaveRequestCreateView.as_view(), name="leave_add"),
    path("leave/<int:pk>/<str:decision>/", views.LeaveRequestDecisionView.as_view(), name="leave_decision"),
    path("leave/<int:pk>/delete/", views.LeaveRequestDeleteView.as_view(), name="leave_delete"),

    path("payroll/", views.PayrollListView.as_view(), name="payroll"),
    path("payroll/generate/", views.PayrollGenerateView.as_view(), name="payroll_generate"),
    path("payroll/<int:pk>/<str:status>/", views.PayrollStatusView.as_view(), name="payroll_status"),
    path("payroll/<int:pk>/delete/", views.PayrollDeleteView.as_view(), name="payroll_delete"),

    path("performance/", views.PerformanceReviewListView.as_view(), name="performance"),
    path("performance/add/", views.PerformanceReviewCreateView.as_view(), name="performance_add"),
    path("performance/<int:pk>/delete/", views.PerformanceReviewDeleteView.as_view(), name="performance_delete"),

    path("training/programs/", views.TrainingProgramListView.as_view(), name="training_programs"),
    path("training/programs/add/", views.TrainingProgramCreateView.as_view(), name="training_program_add"),
    path("training/programs/<int:pk>/delete/", views.TrainingProgramDeleteView.as_view(), name="training_program_delete"),

    path("training/records/", views.TrainingRecordListView.as_view(), name="training_records"),
    path("training/records/add/", views.TrainingRecordCreateView.as_view(), name="training_record_add"),
    path("training/records/<int:pk>/edit/", views.TrainingRecordUpdateView.as_view(), name="training_record_edit"),
    path("training/records/<int:pk>/delete/", views.TrainingRecordDeleteView.as_view(), name="training_record_delete"),
]
