
from django.core.mail.backends.smtp import EmailBackend
import ssl
import smtplib

class UnsafeEmailBackend(EmailBackend):
    def open(self):
        if self.connection:
            return False

        try:
            self.connection = smtplib.SMTP(
                host=self.host,
                port=self.port,
                timeout=self.timeout,
            )
            self.connection.ehlo()

            if self.use_tls:
                context = ssl._create_unverified_context()
                self.connection.starttls(context=context)
                self.connection.ehlo()

            if self.username and self.password:
                self.connection.login(self.username, self.password)

            return True

        except Exception:
            if not self.fail_silently:
                raise
            return False