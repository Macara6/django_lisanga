from django.contrib import admin
from django.contrib.auth.admin import UserAdmin


from .models import *
admin.site.register(CustomUser)
admin.site.register(Substitute)
admin.site.register(Transaction)
admin.site.register(CreditTransaction)
admin.site.register(Credit)
admin.site.register(CashOut)
admin.site.register(Cycle)

