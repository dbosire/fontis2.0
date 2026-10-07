import mimetypes
import os
from datetime import timedelta

from django.contrib import messages
from django.http import FileResponse, Http404
from django.shortcuts import get_object_or_404, redirect
from django.urls import reverse, reverse_lazy
from django.views import View
from django.views.generic import CreateView, DeleteView, DetailView, ListView, TemplateView, UpdateView

from core.mixins import ModulePermissionRequiredMixin

from . import services
from .forms import (
    CalibrationForm, ComplianceDocumentForm, EquipmentForm, MedicalCertificateForm, PersonnelDocumentForm,
    PremisesRequirementForm, ProcedureForm,
)
from .models import (
    Calibration, ComplianceDocument, Equipment, MedicalCertificate, PersonnelDocument, PremisesRequirement,
    Procedure, ProcedureRevision,
)


class ViewComplianceMixin(ModulePermissionRequiredMixin):
    module_name = "compliance"
    permission_level = "view"


class EditComplianceMixin(ModulePermissionRequiredMixin):
    module_name = "compliance"
    permission_level = "edit"


def _delete_stored_file(file_field):
    """Best-effort removal of an upload. A failure to unlink (file already gone, or
    still held open by a download in progress) must not turn a successful database
    change into a 500 — worst case an orphaned file is left behind."""
    if file_field:
        try:
            file_field.storage.delete(file_field.name)
        except OSError:
            pass


class FormPageMixin:
    """Shared add/edit page: one generic template, a title and a cancel link."""

    template_name = "compliance/form.html"
    form_title = ""
    success_message = "Saved."
    cancel_url = None
    file_kind = None  # compliance:file kind, so the form can link to the current upload

    def get_cancel_url(self):
        if self.cancel_url:
            return self.cancel_url
        # A plain success_url is used as-is: ModelFormMixin.get_success_url() formats it
        # against self.object, which is still None while a CreateView is rendering.
        if getattr(self, "success_url", None):
            return str(self.success_url)
        return self.get_success_url()

    def get_context_data(self, **kwargs):
        ctx = super().get_context_data(**kwargs)
        ctx["form_title"] = self.form_title
        ctx["cancel_url"] = self.get_cancel_url()
        ctx["file_kind"] = self.file_kind
        return ctx

    def form_valid(self, form):
        response = super().form_valid(form)
        messages.success(self.request, self.success_message)
        return response


class FileReplacingUpdateMixin:
    """Removes the previous upload from disk when an edit replaces it, so superseded
    certificates don't pile up orphaned in the private store."""

    def get_object(self, queryset=None):
        obj = super().get_object(queryset)
        self._old_file_name = obj.file.name if getattr(obj, "file", None) else ""
        return obj

    def form_valid(self, form):
        response = super().form_valid(form)
        new_name = form.instance.file.name if form.instance.file else ""
        if self._old_file_name and self._old_file_name != new_name:
            try:
                form.instance.file.storage.delete(self._old_file_name)
            except OSError:
                pass
        return response


class ConfirmDeleteMixin:
    template_name = "core/components/confirm_delete.html"
    success_message = "Deleted."
    cancel_url = None

    def get_context_data(self, **kwargs):
        ctx = super().get_context_data(**kwargs)
        ctx["cancel_url"] = self.cancel_url or self.get_success_url()
        return ctx

    def form_valid(self, form):
        _delete_stored_file(getattr(self.object, "file", None))
        messages.success(self.request, self.success_message)
        return super().form_valid(form)


# ---------------------------------------------------------------- Overview

class ComplianceDashboardView(ViewComplianceMixin, TemplateView):
    template_name = "compliance/dashboard.html"

    def get_context_data(self, **kwargs):
        ctx = super().get_context_data(**kwargs)
        checklist = services.readiness_checklist()
        scored = [item for item in checklist if item["ok"] is not None]
        requirements, met = services.premises_progress()
        ctx.update(
            checklist=checklist,
            passed=sum(1 for item in scored if item["ok"]),
            total=len(scored),
            premises=[(r, PremisesRequirementForm(instance=r, prefix=f"r{r.pk}")) for r in requirements],
            premises_met=met,
            premises_total=len(requirements),
            alerts=services.compliance_alert_items(),
        )
        return ctx


class PremisesRequirementUpdateView(EditComplianceMixin, View):
    def post(self, request, pk):
        requirement = get_object_or_404(PremisesRequirement, pk=pk)
        was_met = requirement.is_met
        form = PremisesRequirementForm(request.POST, instance=requirement, prefix=f"r{pk}")
        if form.is_valid():
            requirement = form.save(commit=False)
            if requirement.is_met and not was_met:
                requirement.confirmed_on = services.today()
                requirement.confirmed_by = request.user
            elif not requirement.is_met:
                requirement.confirmed_on = None
                requirement.confirmed_by = None
            requirement.save()
            messages.success(request, "Premises requirement updated.")
        return redirect("compliance:dashboard")


# ---------------------------------------------------------------- Licences & permits

class DocumentListView(ViewComplianceMixin, ListView):
    model = ComplianceDocument
    template_name = "compliance/document_list.html"
    context_object_name = "documents"

    def get_queryset(self):
        qs = ComplianceDocument.objects.all()
        category = self.request.GET.get("category", "")
        if category:
            qs = qs.filter(category=category)
        return qs

    def get_context_data(self, **kwargs):
        ctx = super().get_context_data(**kwargs)
        today = services.today()
        for doc in ctx["documents"]:
            doc.status = services.expiry_status(doc.expiry_date, today)
        ctx["category_choices"] = ComplianceDocument.CATEGORY_CHOICES
        ctx["selected_category"] = self.request.GET.get("category", "")
        return ctx


class DocumentCreateView(EditComplianceMixin, FormPageMixin, CreateView):
    file_kind = "document"
    model = ComplianceDocument
    form_class = ComplianceDocumentForm
    form_title = "Add licence / document"
    success_url = reverse_lazy("compliance:document_list")
    success_message = "Document added."

    def get_initial(self):
        initial = super().get_initial()
        category = self.request.GET.get("category")
        if category in dict(ComplianceDocument.CATEGORY_CHOICES):
            initial["category"] = category
        return initial

    def form_valid(self, form):
        form.instance.uploaded_by = self.request.user
        return super().form_valid(form)


class DocumentUpdateView(EditComplianceMixin, FileReplacingUpdateMixin, FormPageMixin, UpdateView):
    file_kind = "document"
    model = ComplianceDocument
    form_class = ComplianceDocumentForm
    form_title = "Edit document"
    success_url = reverse_lazy("compliance:document_list")
    success_message = "Document updated."


class DocumentDeleteView(EditComplianceMixin, ConfirmDeleteMixin, DeleteView):
    model = ComplianceDocument
    success_url = reverse_lazy("compliance:document_list")
    success_message = "Document deleted."


# ---------------------------------------------------------------- Equipment & calibration

class EquipmentListView(ViewComplianceMixin, TemplateView):
    template_name = "compliance/equipment_list.html"

    def get_context_data(self, **kwargs):
        ctx = super().get_context_data(**kwargs)
        ctx["rows"] = services.equipment_rows()
        ctx["retired"] = Equipment.objects.filter(is_active=False)
        return ctx


class EquipmentCreateView(EditComplianceMixin, FormPageMixin, CreateView):
    model = Equipment
    form_class = EquipmentForm
    form_title = "Add equipment"
    success_url = reverse_lazy("compliance:equipment_list")
    success_message = "Equipment added."


class EquipmentUpdateView(EditComplianceMixin, FormPageMixin, UpdateView):
    model = Equipment
    form_class = EquipmentForm
    form_title = "Edit equipment"
    success_url = reverse_lazy("compliance:equipment_list")
    success_message = "Equipment updated."


class EquipmentDeleteView(EditComplianceMixin, DeleteView):
    model = Equipment
    template_name = "core/components/confirm_delete.html"
    success_url = reverse_lazy("compliance:equipment_list")

    def get_context_data(self, **kwargs):
        ctx = super().get_context_data(**kwargs)
        ctx["cancel_url"] = self.get_success_url()
        count = self.object.calibrations.count()
        if count:
            ctx["extra_warning"] = f"This also deletes its {count} calibration record{'s' if count != 1 else ''} and certificate{'s' if count != 1 else ''}."
        return ctx

    def form_valid(self, form):
        for calibration in self.object.calibrations.all():
            _delete_stored_file(calibration.file)
        messages.success(self.request, "Equipment deleted.")
        return super().form_valid(form)


class EquipmentDetailView(ViewComplianceMixin, DetailView):
    model = Equipment
    template_name = "compliance/equipment_detail.html"
    context_object_name = "equipment"

    def get_context_data(self, **kwargs):
        ctx = super().get_context_data(**kwargs)
        today = services.today()
        calibrations = list(self.object.calibrations.all())
        for calibration in calibrations:
            calibration.status = services.expiry_status(calibration.next_due_date, today)
        ctx["calibrations"] = calibrations
        latest = self.object.latest_calibration
        ctx["status"] = services.expiry_status(latest.next_due_date, today) if latest else services.MISSING
        return ctx


class CalibrationCreateView(EditComplianceMixin, FormPageMixin, CreateView):
    file_kind = "calibration"
    model = Calibration
    form_class = CalibrationForm
    success_message = "Calibration recorded."

    def dispatch(self, request, *args, **kwargs):
        self.equipment = get_object_or_404(Equipment, pk=kwargs["equipment_pk"])
        return super().dispatch(request, *args, **kwargs)

    def get_success_url(self):
        return reverse("compliance:equipment_detail", args=[self.equipment.pk])

    def get_context_data(self, **kwargs):
        ctx = super().get_context_data(**kwargs)
        ctx["form_title"] = f"Record calibration — {self.equipment.name}"
        return ctx

    def form_valid(self, form):
        form.instance.equipment = self.equipment
        return super().form_valid(form)


class CalibrationUpdateView(EditComplianceMixin, FileReplacingUpdateMixin, FormPageMixin, UpdateView):
    file_kind = "calibration"
    model = Calibration
    form_class = CalibrationForm
    form_title = "Edit calibration"
    success_message = "Calibration updated."

    def get_success_url(self):
        return reverse("compliance:equipment_detail", args=[self.object.equipment_id])


class CalibrationDeleteView(EditComplianceMixin, ConfirmDeleteMixin, DeleteView):
    model = Calibration
    success_message = "Calibration deleted."

    def get_success_url(self):
        return reverse("compliance:equipment_detail", args=[self.object.equipment_id])


# ---------------------------------------------------------------- Medical certificates

class MedicalListView(ViewComplianceMixin, TemplateView):
    template_name = "compliance/medical_list.html"

    def get_context_data(self, **kwargs):
        ctx = super().get_context_data(**kwargs)
        today = services.today()
        certificates = list(MedicalCertificate.objects.select_related("employee"))
        for cert in certificates:
            cert.status = services.expiry_status(cert.expiry_date, today)
        ctx["rows"] = services.food_handler_rows(today)
        ctx["certificates"] = certificates
        return ctx


class MedicalCreateView(EditComplianceMixin, FormPageMixin, CreateView):
    file_kind = "medical"
    model = MedicalCertificate
    form_class = MedicalCertificateForm
    form_title = "Add medical certificate"
    success_url = reverse_lazy("compliance:medical_list")
    success_message = "Medical certificate added."

    def get_initial(self):
        initial = super().get_initial()
        employee = self.request.GET.get("employee")
        if employee and employee.isdigit():
            initial["employee"] = int(employee)
        return initial


class MedicalUpdateView(EditComplianceMixin, FileReplacingUpdateMixin, FormPageMixin, UpdateView):
    file_kind = "medical"
    model = MedicalCertificate
    form_class = MedicalCertificateForm
    form_title = "Edit medical certificate"
    success_url = reverse_lazy("compliance:medical_list")
    success_message = "Medical certificate updated."


class MedicalDeleteView(EditComplianceMixin, ConfirmDeleteMixin, DeleteView):
    model = MedicalCertificate
    success_url = reverse_lazy("compliance:medical_list")
    success_message = "Medical certificate deleted."


# ---------------------------------------------------------------- QC personnel documents

class PersonnelListView(ViewComplianceMixin, ListView):
    model = PersonnelDocument
    template_name = "compliance/personnel_list.html"
    context_object_name = "documents"

    def get_queryset(self):
        return PersonnelDocument.objects.select_related("employee")


class PersonnelCreateView(EditComplianceMixin, FormPageMixin, CreateView):
    file_kind = "personnel"
    model = PersonnelDocument
    form_class = PersonnelDocumentForm
    form_title = "Add personnel document"
    success_url = reverse_lazy("compliance:personnel_list")
    success_message = "Document added."


class PersonnelUpdateView(EditComplianceMixin, FileReplacingUpdateMixin, FormPageMixin, UpdateView):
    file_kind = "personnel"
    model = PersonnelDocument
    form_class = PersonnelDocumentForm
    form_title = "Edit personnel document"
    success_url = reverse_lazy("compliance:personnel_list")
    success_message = "Document updated."


class PersonnelDeleteView(EditComplianceMixin, ConfirmDeleteMixin, DeleteView):
    model = PersonnelDocument
    success_url = reverse_lazy("compliance:personnel_list")
    success_message = "Document deleted."


# ---------------------------------------------------------------- Procedures

class ProcedureListView(ViewComplianceMixin, ListView):
    model = Procedure
    template_name = "compliance/procedure_list.html"
    context_object_name = "procedures"

    def get_context_data(self, **kwargs):
        ctx = super().get_context_data(**kwargs)
        today = services.today()
        for procedure in ctx["procedures"]:
            procedure.review_overdue = bool(procedure.next_review_date and procedure.next_review_date < today)
        return ctx


class ProcedureDetailView(ViewComplianceMixin, DetailView):
    model = Procedure
    template_name = "compliance/procedure_detail.html"
    context_object_name = "procedure"

    def get_context_data(self, **kwargs):
        ctx = super().get_context_data(**kwargs)
        ctx["revisions"] = self.object.revisions.select_related("saved_by")
        return ctx


class ProcedureCreateView(EditComplianceMixin, FormPageMixin, CreateView):
    model = Procedure
    form_class = ProcedureForm
    form_title = "Add procedure"
    template_name = "compliance/procedure_form.html"
    success_message = "Procedure saved as a draft — approve it when it has been reviewed."

    def get_success_url(self):
        return reverse("compliance:procedure_detail", args=[self.object.pk])

    def get_cancel_url(self):
        return reverse("compliance:procedure_list")


class ProcedureUpdateView(EditComplianceMixin, FormPageMixin, UpdateView):
    model = Procedure
    form_class = ProcedureForm
    form_title = "Edit procedure"
    template_name = "compliance/procedure_form.html"

    def get_object(self, queryset=None):
        obj = super().get_object(queryset)
        self._before = (obj.content, obj.version, obj.status)
        return obj

    def get_success_url(self):
        return reverse("compliance:procedure_detail", args=[self.object.pk])

    def get_cancel_url(self):
        return reverse("compliance:procedure_detail", args=[self.kwargs["pk"]])

    def form_valid(self, form):
        old_content, old_version, old_status = self._before
        needs_reapproval = False
        if form.instance.content != old_content:
            ProcedureRevision.objects.create(
                procedure=form.instance, version=old_version, content=old_content, saved_by=self.request.user,
            )
            if old_status == Procedure.APPROVED:
                form.instance.status = Procedure.DRAFT
                form.instance.approved_by = ""
                form.instance.approved_date = None
                needs_reapproval = True
        self.success_message = (
            "Procedure updated — the wording changed, so it needs to be approved again."
            if needs_reapproval else "Procedure updated."
        )
        return super().form_valid(form)


class ProcedureDeleteView(EditComplianceMixin, DeleteView):
    model = Procedure
    template_name = "core/components/confirm_delete.html"
    success_url = reverse_lazy("compliance:procedure_list")

    def get_context_data(self, **kwargs):
        ctx = super().get_context_data(**kwargs)
        ctx["cancel_url"] = reverse("compliance:procedure_detail", args=[self.object.pk])
        return ctx

    def form_valid(self, form):
        messages.success(self.request, "Procedure deleted.")
        return super().form_valid(form)


class ProcedureApproveView(EditComplianceMixin, View):
    def post(self, request, pk):
        procedure = get_object_or_404(Procedure, pk=pk)
        today = services.today()
        procedure.status = Procedure.APPROVED
        procedure.approved_by = request.user.get_full_name() or request.user.get_username()
        procedure.approved_date = today
        procedure.effective_date = procedure.effective_date or today
        procedure.next_review_date = procedure.next_review_date or today + timedelta(days=365)
        procedure.save()
        messages.success(request, f"{procedure.code} approved.")
        return redirect("compliance:procedure_detail", pk=procedure.pk)


# ---------------------------------------------------------------- File download

class ComplianceFileView(ViewComplianceMixin, View):
    """Streams an uploaded certificate/licence after the role check. These files
    live outside MEDIA_ROOT precisely so this view is the only way to reach them."""

    MODELS = {
        "document": ComplianceDocument,
        "calibration": Calibration,
        "medical": MedicalCertificate,
        "personnel": PersonnelDocument,
    }

    def get(self, request, kind, pk):
        model = self.MODELS.get(kind)
        if model is None:
            raise Http404
        obj = get_object_or_404(model, pk=pk)
        if not obj.file:
            raise Http404("No file attached.")
        try:
            handle = obj.file.open("rb")
        except FileNotFoundError:
            raise Http404("The file is missing from storage.")
        content_type = mimetypes.guess_type(obj.file.name)[0] or "application/octet-stream"
        viewable = content_type == "application/pdf" or content_type.startswith("image/")
        return FileResponse(
            handle, content_type=content_type, as_attachment=not viewable,
            filename=os.path.basename(obj.file.name),
        )
