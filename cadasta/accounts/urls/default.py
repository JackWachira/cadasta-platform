from django.conf.urls import url
import allauth.account.views as allauth_views
from ..views import default

urlpatterns = [
    url(r'^signup/$', default.AccountRegister.as_view(), name='register'),
    url(r'^profile/$', default.AccountProfile.as_view(), name='profile'),
    url(r'^login/$', default.AccountLogin.as_view(), name='login'),
    url(r'^confirm-email/(?P<key>[-:\w]+)/$', default.ConfirmEmail.as_view(),
        name='verify_email'),
    url(r'^password/change/$', default.PasswordChangeView.as_view(),
        name="account_change_password"),
    url(r'^password/reset/key/(?P<uidb36>[0-9A-Za-z]+)-(?P<key>.+)/$',
        default.PasswordResetFromKeyView.as_view(),
        name="account_reset_password_from_key"),
    url(r'^password/reset/$', default.PasswordResetView.as_view(),
        name="account_reset_password"),
    url(r'^dashboard/$', default.UserDashboard.as_view(),
        name='dashboard'),
    url(r'^accountverification/$',
        default.ConfirmPhone.as_view(), name='verify_phone'),
    url(r'^resendtokenpage/$',
        default.ResendTokenView.as_view(), name='resend_token'),
    url(r'^password/reset/done/$',
        default.PasswordResetDoneView.as_view(),
        name='account_reset_password_done'),
    url(r'^password/reset/phone/$',
        default.PasswordResetFromPhoneView.as_view(),
        name='account_reset_password_from_phone'),
    url(r'password/reset/key/done/$',
        allauth_views.PasswordResetFromKeyDoneView.as_view(),
        name='account_reset_password_from_key_done')
]
