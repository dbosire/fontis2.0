from django.urls import path

from . import views

app_name = "crm"

urlpatterns = [
    path("complaints/", views.ComplaintListView.as_view(), name="complaints"),
    path("complaints/add/", views.ComplaintCreateView.as_view(), name="complaint_add"),
    path("complaints/<int:pk>/edit/", views.ComplaintUpdateView.as_view(), name="complaint_edit"),
    path("complaints/<int:pk>/delete/", views.ComplaintDeleteView.as_view(), name="complaint_delete"),

    path("feedback/", views.FeedbackListView.as_view(), name="feedback"),
    path("feedback/add/", views.FeedbackCreateView.as_view(), name="feedback_add"),
    path("feedback/<int:pk>/edit/", views.FeedbackUpdateView.as_view(), name="feedback_edit"),
    path("feedback/<int:pk>/delete/", views.FeedbackDeleteView.as_view(), name="feedback_delete"),

    path("follow-ups/", views.FollowUpListView.as_view(), name="followups"),
    path("follow-ups/add/", views.FollowUpCreateView.as_view(), name="followup_add"),
    path("follow-ups/<int:pk>/edit/", views.FollowUpUpdateView.as_view(), name="followup_edit"),
    path("follow-ups/<int:pk>/delete/", views.FollowUpDeleteView.as_view(), name="followup_delete"),
    path("follow-ups/<int:pk>/complete/", views.FollowUpCompleteView.as_view(), name="followup_complete"),

    path("sms/", views.SmsLogListView.as_view(), name="sms_log"),
    path("sms/send/", views.SmsSendView.as_view(), name="sms_send"),

    path("email/", views.EmailLogListView.as_view(), name="email_log"),
    path("email/send/", views.EmailSendView.as_view(), name="email_send"),

    path("promotions/", views.PromotionListView.as_view(), name="promotions"),
    path("promotions/add/", views.PromotionCreateView.as_view(), name="promotion_add"),
    path("promotions/<int:pk>/edit/", views.PromotionUpdateView.as_view(), name="promotion_edit"),
    path("promotions/<int:pk>/delete/", views.PromotionDeleteView.as_view(), name="promotion_delete"),
    path("promotions/<int:pk>/send/", views.PromotionSendView.as_view(), name="promotion_send"),

    path("loyalty/", views.LoyaltyListView.as_view(), name="loyalty"),
    path("loyalty/create/", views.LoyaltyCreateView.as_view(), name="loyalty_create"),
    path("loyalty/<int:pk>/adjust/", views.LoyaltyAdjustView.as_view(), name="loyalty_adjust"),
    path("loyalty/settings/", views.LoyaltySettingsView.as_view(), name="loyalty_settings"),
]
