from django.urls import path
from . import views

urlpatterns = [
    path('', views.dashboard, name='dashboard'),
    path('login/', views.login_view, name='login'),
    path('register/', views.register_view, name='register'),
    path('logout/', views.logout_view, name='logout'),

    # Teacher
    path('teacher/', views.teacher_dashboard, name='teacher_dashboard'),
    path('teacher/courses/', views.manage_courses, name='manage_courses'),
    path('teacher/courses/create/', views.create_course, name='create_course'),
    path('teacher/courses/<int:course_id>/schedule/', views.add_schedule, name='add_schedule'),
    path('teacher/schedule/<int:slot_id>/delete/', views.delete_schedule, name='delete_schedule'),
    path('teacher/courses/<int:course_id>/enrollment/', views.manage_enrollment, name='manage_enrollment'),
    path('teacher/courses/<int:course_id>/enroll/', views.enroll_student, name='enroll_student'),
    path('teacher/enrollment/<int:enrollment_id>/remove/', views.remove_student, name='remove_student'),
    path('teacher/qr/<int:schedule_id>/', views.generate_qr, name='generate_qr'),
    path('teacher/history/', views.attendance_history, name='attendance_history'),
    path('teacher/session/<int:session_id>/', views.session_detail, name='session_detail'),
    path('teacher/attendance/<int:record_id>/update/', views.update_attendance, name='update_attendance'),
    path('teacher/attempt/<int:attempt_id>/approve/', views.approve_attempt, name='approve_attempt'),
    path('teacher/attempt/<int:attempt_id>/reject/', views.reject_attempt, name='reject_attempt'),

    # Student
    path('student/', views.student_dashboard, name='student_dashboard'),
    path('student/mark/', views.mark_attendance, name='mark_attendance'),
    path('student/history/', views.student_history, name='student_history'),
]