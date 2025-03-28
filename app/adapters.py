from allauth.account.adapter import DefaultAccountAdapter

class MyAccountAdapter(DefaultAccountAdapter):
    def send_mail(self, template_prefix, email, context):
        template_prefix = "account/email/password_reset"
        super().send_mail(template_prefix, email, context)
