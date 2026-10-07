from django.urls import path

from . import views

app_name = "compliance"

urlpatterns = [
    path("", views.ComplianceDashboardView.as_view(), name="dashboard"),
    path("premises/<int:pk>/", views.PremisesRequirementUpdateView.as_view(), name="premises_update"),
    path("files/<str:kind>/<int:pk>/", views.ComplianceFileView.as_view(), name="file"),

    path("documents/", views.DocumentListView.as_view(), name="document_list"),
    path("documents/add/", views.DocumentCreateView.as_view(), name="document_add"),
    path("documents/<int:pk>/edit/", views.DocumentUpdateView.as_view(), name="document_edit"),
    path("documents/<int:pk>/delete/", views.DocumentDeleteView.as_view(), name="document_delete"),

    path("equipment/", views.EquipmentListView.as_view(), name="equipment_list"),
    path("equipment/add/", views.EquipmentCreateView.as_view(), name="equipment_add"),
    path("equipment/<int:pk>/", views.EquipmentDetailView.as_view(), name="equipment_detail"),
    path("equipment/<int:pk>/edit/", views.EquipmentUpdateView.as_view(), name="equipment_edit"),
    path("equipment/<int:pk>/delete/", views.EquipmentDeleteView.as_view(), name="equipment_delete"),
    path("equipment/<int:equipment_pk>/calibrations/add/", views.CalibrationCreateView.as_view(), name="calibration_add"),
    path("calibrations/<int:pk>/edit/", views.CalibrationUpdateView.as_view(), name="calibration_edit"),
    path("calibrations/<int:pk>/delete/", views.CalibrationDeleteView.as_view(), name="calibration_delete"),

    path("medical/", views.MedicalListView.as_view(), name="medical_list"),
    path("medical/add/", views.MedicalCreateView.as_view(), name="medical_add"),
    path("medical/<int:pk>/edit/", views.MedicalUpdateView.as_view(), name="medical_edit"),
    path("medical/<int:pk>/delete/", views.MedicalDeleteView.as_view(), name="medical_delete"),

    path("personnel/", views.PersonnelListView.as_view(), name="personnel_list"),
    path("personnel/add/", views.PersonnelCreateView.as_view(), name="personnel_add"),
    path("personnel/<int:pk>/edit/", views.PersonnelUpdateView.as_view(), name="personnel_edit"),
    path("personnel/<int:pk>/delete/", views.PersonnelDeleteView.as_view(), name="personnel_delete"),

    path("procedures/", views.ProcedureListView.as_view(), name="procedure_list"),
    path("procedures/add/", views.ProcedureCreateView.as_view(), name="procedure_add"),
    path("procedures/<int:pk>/", views.ProcedureDetailView.as_view(), name="procedure_detail"),
    path("procedures/<int:pk>/edit/", views.ProcedureUpdateView.as_view(), name="procedure_edit"),
    path("procedures/<int:pk>/delete/", views.ProcedureDeleteView.as_view(), name="procedure_delete"),
    path("procedures/<int:pk>/approve/", views.ProcedureApproveView.as_view(), name="procedure_approve"),
]
