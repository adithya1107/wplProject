from django.contrib import admin
from django.contrib.auth.admin import UserAdmin
from .models import *

@admin.register(User)
class CustomUserAdmin(UserAdmin):
    list_display = ('username', 'email', 'role', 'user_code', 'is_staff')
    fieldsets = UserAdmin.fieldsets + (
        ('Extra', {'fields': ('role', 'user_code')}),
    )
    add_fieldsets = UserAdmin.add_fieldsets + (
        ('Extra', {'fields': ('role', 'user_code')}),
    )

admin.site.register(Course)
admin.site.register(Enrollment)
admin.site.register(ClassSchedule)
admin.site.register(AttendanceSession)
admin.site.register(AttendanceRecord)
admin.site.register(AttendanceAttempt)