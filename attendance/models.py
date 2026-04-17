from django.db import models
from django.contrib.auth.models import AbstractUser


class User(AbstractUser):
    ROLE_CHOICES = [('student', 'Student'), ('teacher', 'Teacher')]
    role = models.CharField(max_length=20, choices=ROLE_CHOICES, default='student')
    user_code = models.CharField(max_length=50, unique=True)

    def __str__(self):
        return f"{self.get_full_name()} ({self.user_code})"


class Course(models.Model):
    course_name = models.CharField(max_length=200)
    course_code = models.CharField(max_length=20, unique=True)
    instructor = models.ForeignKey(
        User, on_delete=models.SET_NULL, null=True, related_name='courses'
    )
    is_active = models.BooleanField(default=True)
    created_at = models.DateTimeField(auto_now_add=True)

    def __str__(self):
        return f"{self.course_code} - {self.course_name}"


class Enrollment(models.Model):
    STATUS = [('enrolled', 'Enrolled'), ('dropped', 'Dropped')]
    student = models.ForeignKey(User, on_delete=models.CASCADE, related_name='enrollments')
    course = models.ForeignKey(Course, on_delete=models.CASCADE, related_name='enrollments')
    status = models.CharField(max_length=20, choices=STATUS, default='enrolled')
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        unique_together = ('student', 'course')

    def __str__(self):
        return f"{self.student} - {self.course}"


class ClassSchedule(models.Model):
    DAYS = [(i, d) for i, d in enumerate(
        ['Sunday', 'Monday', 'Tuesday', 'Wednesday', 'Thursday', 'Friday', 'Saturday']
    )]
    course = models.ForeignKey(Course, on_delete=models.CASCADE, related_name='schedules')
    day_of_week = models.IntegerField(choices=DAYS)
    start_time = models.TimeField()
    end_time = models.TimeField()
    room_location = models.CharField(max_length=100, blank=True)

    def __str__(self):
        return f"{self.course.course_code} - {self.get_day_of_week_display()}"


class AttendanceSession(models.Model):
    course = models.ForeignKey(Course, on_delete=models.CASCADE)
    instructor = models.ForeignKey(
        User, on_delete=models.SET_NULL, null=True, related_name='sessions'
    )
    session_date = models.DateField()
    start_time = models.TimeField()
    end_time = models.TimeField()
    qr_code = models.CharField(max_length=10, unique=True)
    is_active = models.BooleanField(default=True)
    teacher_latitude = models.FloatField(null=True, blank=True)
    teacher_longitude = models.FloatField(null=True, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)

    def __str__(self):
        return f"{self.course.course_code} - {self.session_date}"


class AttendanceRecord(models.Model):
    STATUS = [('present', 'Present'), ('late', 'Late'), ('absent', 'Absent')]
    session = models.ForeignKey(AttendanceSession, on_delete=models.CASCADE, related_name='records')
    student = models.ForeignKey(User, on_delete=models.CASCADE, related_name='attendance')
    course = models.ForeignKey(Course, on_delete=models.CASCADE)
    status = models.CharField(max_length=20, choices=STATUS)
    class_date = models.DateField()
    marked_at = models.DateTimeField(auto_now_add=True)
    marked_by = models.ForeignKey(
        User, on_delete=models.SET_NULL, null=True, related_name='marked_attendance'
    )
    student_latitude = models.FloatField(null=True, blank=True)
    student_longitude = models.FloatField(null=True, blank=True)
    distance_from_teacher = models.FloatField(null=True, blank=True)

    class Meta:
        unique_together = ('session', 'student')

    def __str__(self):
        return f"{self.student} - {self.status}"


class AttendanceAttempt(models.Model):
    STATUS = [('pending', 'Pending'), ('approved', 'Approved'), ('rejected', 'Rejected')]
    session = models.ForeignKey(AttendanceSession, on_delete=models.CASCADE)
    student = models.ForeignKey(User, on_delete=models.CASCADE)
    failure_reason = models.TextField(blank=True)
    student_latitude = models.FloatField(null=True, blank=True)
    student_longitude = models.FloatField(null=True, blank=True)
    distance_from_teacher = models.FloatField(null=True, blank=True)
    gps_accuracy = models.FloatField(null=True, blank=True)
    status = models.CharField(max_length=20, choices=STATUS, default='pending')
    reviewed_by = models.ForeignKey(
        User, on_delete=models.SET_NULL, null=True, related_name='reviewed_attempts'
    )
    reviewed_at = models.DateTimeField(null=True, blank=True)
    attempted_at = models.DateTimeField(auto_now_add=True)