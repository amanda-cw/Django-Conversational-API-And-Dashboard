from Dashboard import views
from django.urls import path, include
from django.views.generic import TemplateView

urlpatterns = [
    path("", views.home, name="home"),
    path("myleads/", views.leads, name="leads"),
    path("myleads/<int:id>/", views.myLeads, name="myLeads"),
    path("forms/", views.forms, name="forms"),
    path("forms/<int:id>/", views.showform, name="showform"),
    path("messages/", views.messages, name="messages"),
    path("login/", views.login_view, name="login"),
    path("logout/", views.logout_view, name="logout"),
    path(
        "settings/notifications",
        views.notificationSettings,
        name="notificationsettings",
    ),
    path(
        "settings/formquestions",
        views.formquestionSettings,
        name="formquestionsettings",
    ),
    path("settings/messages", views.messageSettings, name="messagesettings"),
    path("settings/account", views.accountSettings, name="accountsettings"),
    path("calls/", views.phone_calls, name="calls"),
    path("calls/<int:id>/", views.showcall, name="showcall"),
    path("support/documentation", views.documentation, name="documentation"),
    path("support/contact", views.contact, name="contact"),
]
