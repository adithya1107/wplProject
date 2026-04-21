from django.shortcuts import render, redirect, get_object_or_404
from django.contrib.auth import login, logout, authenticate
from django.contrib.auth.decorators import login_required
from django.http import JsonResponse
from django.utils import timezone
from django.views.decorators.http import require_POST
from django.views.decorators.csrf import csrf_exempt
from django.urls import reverse
from .models import *
import qrcode, io, base64, random, string, json, math


def generate_code():
    return ''.join(random.choices(string.ascii_uppercase + string.digits, k=6))


def haversine(lat1, lon1, lat2, lon2):
    R = 6371000
    p1, p2 = math.radians(lat1), math.radians(lat2)
    dp = math.radians(lat2 - lat1)
    dl = math.radians(lon2 - lon1)
    a = math.sin(dp/2)**2 + math.cos(p1)*math.cos(p2)*math.sin(dl/2)**2
    return R * 2 * math.atan2(math.sqrt(a), math.sqrt(1-a))


# ── AUTH ──────────────────────────────────────────────────────────────────────

def login_view(request):
    if request.user.is_authenticated:
        return redirect('dashboard')
    error = None
    if request.method == 'POST':
        user = authenticate(
            request,
            username=request.POST.get('username'),
            password=request.POST.get('password')
        )
        if user:
            login(request, user)
            return redirect('dashboard')
        error = 'Invalid username or password'
    return render(request, 'auth/login.html', {'error': error})


def register_view(request):
    if request.method == 'POST':
        username = request.POST.get('username')
        password = request.POST.get('password')
        first_name = request.POST.get('first_name')
        last_name = request.POST.get('last_name')
        role = request.POST.get('role', 'student')
        user_code = request.POST.get('user_code')

        if User.objects.filter(username=username).exists():
            return render(request, 'auth/register.html', {'error': 'Username already taken'})
        if User.objects.filter(user_code=user_code).exists():
            return render(request, 'auth/register.html', {'error': 'User code already taken'})

        user = User.objects.create_user(
            username=username, password=password,
            first_name=first_name, last_name=last_name,
            role=role, user_code=user_code
        )
        login(request, user)
        return redirect('dashboard')
    return render(request, 'auth/register.html')


def logout_view(request):
    logout(request)
    return redirect('login')


@login_required
def dashboard(request):
    if request.user.role == 'teacher':
        return redirect('teacher_dashboard')
    return redirect('student_dashboard')


# ── TEACHER ───────────────────────────────────────────────────────────────────

@login_required
def teacher_dashboard(request):
    if request.user.role != 'teacher':
        return redirect('student_dashboard')
    courses = Course.objects.filter(instructor=request.user, is_active=True).prefetch_related('schedules')
    today = timezone.localdate()
    today_day = today.weekday() + 1  # Django: Mon=0, but our model: Sun=0
    # Convert: Mon=1,Tue=2...Sun=0
    today_day = today.isoweekday() % 7  # Sun=0, Mon=1 ... Sat=6

    today_schedules = ClassSchedule.objects.filter(
        course__instructor=request.user,
        course__is_active=True,
        day_of_week=today_day
    ).select_related('course')

    active_sessions = AttendanceSession.objects.filter(
        instructor=request.user,
        session_date=today,
        is_active=True
    ).select_related('course')

    return render(request, 'teacher/dashboard.html', {
        'courses': courses,
        'today_schedules': today_schedules,
        'active_sessions': active_sessions,
        'today': today,
    })


@login_required
def generate_qr(request, schedule_id):
    if request.user.role != 'teacher':
        return JsonResponse({'error': 'Unauthorized'}, status=403)

    schedule = get_object_or_404(ClassSchedule, id=schedule_id, course__instructor=request.user)
    today = timezone.localdate()
    now_time = timezone.localtime().time()

    lat = request.POST.get('latitude')
    lon = request.POST.get('longitude')

    # Reuse existing session or create new one
    session = AttendanceSession.objects.filter(
        course=schedule.course,
        instructor=request.user,
        session_date=today,
        start_time=schedule.start_time,
    ).first()

    if session:
        session.is_active = True
        if lat and lon:
            session.teacher_latitude = float(lat)
            session.teacher_longitude = float(lon)
        session.save()
    else:
        code = generate_code()
        while AttendanceSession.objects.filter(qr_code=code, session_date=today).exists():
            code = generate_code()

        session = AttendanceSession.objects.create(
            course=schedule.course,
            instructor=request.user,
            session_date=today,
            start_time=schedule.start_time,
            end_time=schedule.end_time,
            qr_code=code,
            is_active=True,
            teacher_latitude=float(lat) if lat else None,
            teacher_longitude=float(lon) if lon else None,
        )

    # ── CHANGED: encode a full URL so phone cameras open the browser directly ──
    mark_url = request.build_absolute_uri(
        reverse('mark_attendance') + f'?code={session.qr_code}'
    )
    img = qrcode.make(mark_url)
    # ──────────────────────────────────────────────────────────────────────────

    buf = io.BytesIO()
    img.save(buf, format='PNG')
    qr_b64 = base64.b64encode(buf.getvalue()).decode()

    # Get attendance for this session
    records = AttendanceRecord.objects.filter(session=session).select_related('student')
    enrolled = Enrollment.objects.filter(course=schedule.course, status='enrolled').select_related('student')
    pending_attempts = AttendanceAttempt.objects.filter(session=session, status='pending').select_related('student')

    marked_ids = set(r.student_id for r in records)
    students_status = []
    for e in enrolled:
        rec = next((r for r in records if r.student_id == e.student_id), None)
        students_status.append({
            'student': e.student,
            'status': rec.status if rec else 'waiting',
            'marked_at': rec.marked_at if rec else None,
        })

    now = timezone.localtime()
    start_dt = timezone.make_aware(
        timezone.datetime.combine(today, session.start_time)
    )
    elapsed_minutes = int((now - start_dt).total_seconds() / 60)
    marked_count = sum(1 for s in students_status if s['status'] in ['present', 'late'])

    return render(request, 'teacher/qr_session.html', {
        'session': session,
        'schedule': schedule,
        'qr_b64': qr_b64,
        'students_status': students_status,
        'pending_attempts': pending_attempts,
        'elapsed_minutes': elapsed_minutes,
        'time_remaining': max(0, int((
            timezone.make_aware(timezone.datetime.combine(today, session.end_time)) - now
        ).total_seconds() / 60)),
        'marked_count': marked_count,
    })


@login_required
@require_POST
def approve_attempt(request, attempt_id):
    attempt = get_object_or_404(AttendanceAttempt, id=attempt_id)
    today = timezone.localdate()
    now = timezone.localtime()
    start_dt = timezone.make_aware(
        timezone.datetime.combine(today, attempt.session.start_time)
    )
    elapsed = int((now - start_dt).total_seconds() / 60)
    status = 'late' if elapsed > 10 else 'present'

    AttendanceRecord.objects.get_or_create(
        session=attempt.session,
        student=attempt.student,
        defaults={
            'course': attempt.session.course,
            'status': status,
            'class_date': today,
            'marked_by': request.user,
            'student_latitude': attempt.student_latitude,
            'student_longitude': attempt.student_longitude,
            'distance_from_teacher': attempt.distance_from_teacher,
        }
    )
    attempt.status = 'approved'
    attempt.reviewed_by = request.user
    attempt.reviewed_at = now
    attempt.save()

    # Redirect back to wherever the teacher came from
    schedule_id = request.POST.get('schedule_id', '0')
    if schedule_id and schedule_id != '0':
        return redirect('generate_qr', schedule_id=schedule_id)
    return redirect('session_detail', session_id=attempt.session.id)


@login_required
@require_POST
def reject_attempt(request, attempt_id):
    attempt = get_object_or_404(AttendanceAttempt, id=attempt_id)
    attempt.status = 'rejected'
    attempt.reviewed_by = request.user
    attempt.reviewed_at = timezone.now()
    attempt.save()

    schedule_id = request.POST.get('schedule_id', '0')
    if schedule_id and schedule_id != '0':
        return redirect('generate_qr', schedule_id=schedule_id)
    return redirect('session_detail', session_id=attempt.session.id)


@login_required
def manage_courses(request):
    if request.user.role != 'teacher':
        return redirect('dashboard')
    courses = Course.objects.filter(
        instructor=request.user
    ).prefetch_related('schedules', 'enrollments__student')
    return render(request, 'teacher/courses.html', {'courses': courses})


@login_required
@require_POST
def create_course(request):
    Course.objects.create(
        course_name=request.POST['course_name'],
        course_code=request.POST['course_code'].upper(),
        instructor=request.user,
    )
    return redirect('manage_courses')


@login_required
@require_POST
def add_schedule(request, course_id):
    course = get_object_or_404(Course, id=course_id, instructor=request.user)
    ClassSchedule.objects.create(
        course=course,
        day_of_week=int(request.POST['day_of_week']),
        start_time=request.POST['start_time'],
        end_time=request.POST['end_time'],
        room_location=request.POST.get('room_location', ''),
    )
    return redirect('manage_courses')


@login_required
@require_POST
def delete_schedule(request, slot_id):
    slot = get_object_or_404(ClassSchedule, id=slot_id, course__instructor=request.user)
    slot.delete()
    return redirect('manage_courses')


@login_required
def manage_enrollment(request, course_id):
    course = get_object_or_404(Course, id=course_id, instructor=request.user)
    enrolled = Enrollment.objects.filter(course=course, status='enrolled').select_related('student')
    all_students = User.objects.filter(role='student').exclude(
        id__in=enrolled.values_list('student_id', flat=True)
    )
    return render(request, 'teacher/enrollment.html', {
        'course': course,
        'enrolled': enrolled,
        'all_students': all_students,
    })


@login_required
@require_POST
def enroll_student(request, course_id):
    course = get_object_or_404(Course, id=course_id, instructor=request.user)
    student = get_object_or_404(User, id=request.POST['student_id'], role='student')
    Enrollment.objects.get_or_create(student=student, course=course, defaults={'status': 'enrolled'})
    return redirect('manage_enrollment', course_id=course_id)


@login_required
@require_POST
def remove_student(request, enrollment_id):
    enrollment = get_object_or_404(
        Enrollment, id=enrollment_id, course__instructor=request.user
    )
    course_id = enrollment.course_id
    enrollment.status = 'dropped'
    enrollment.save()
    return redirect('manage_enrollment', course_id=course_id)


@login_required
def attendance_history(request):
    if request.user.role != 'teacher':
        return redirect('dashboard')
    sessions = AttendanceSession.objects.filter(
        instructor=request.user
    ).select_related('course').order_by('-session_date', '-start_time')
    return render(request, 'teacher/history.html', {'sessions': sessions})


@login_required
def session_detail(request, session_id):
    session = get_object_or_404(AttendanceSession, id=session_id, instructor=request.user)
    records = AttendanceRecord.objects.filter(session=session).select_related('student')
    enrolled = Enrollment.objects.filter(course=session.course, status='enrolled').select_related('student')
    pending_attempts = AttendanceAttempt.objects.filter(session=session, status='pending').select_related('student')

    students_status = []
    for e in enrolled:
        rec = next((r for r in records if r.student_id == e.student_id), None)
        students_status.append({
            'student': e.student,
            'status': rec.status if rec else 'absent',
            'marked_at': rec.marked_at if rec else None,
            'record_id': rec.id if rec else None,
        })

    return render(request, 'teacher/session_detail.html', {
        'session': session,
        'students_status': students_status,
        'pending_attempts': pending_attempts,
    })


@login_required
@require_POST
def update_attendance(request, record_id):
    record = get_object_or_404(
        AttendanceRecord, id=record_id, session__instructor=request.user
    )
    new_status = request.POST.get('status')
    if new_status in ['present', 'late', 'absent']:
        record.status = new_status
        record.marked_by = request.user
        record.save()
    return redirect('session_detail', session_id=record.session_id)


# ── STUDENT ───────────────────────────────────────────────────────────────────

@login_required
def student_dashboard(request):
    if request.user.role != 'student':
        return redirect('teacher_dashboard')
    enrollments = Enrollment.objects.filter(
        student=request.user, status='enrolled'
    ).select_related('course')

    # Stats per course
    course_stats = []
    for e in enrollments:
        records = AttendanceRecord.objects.filter(student=request.user, course=e.course)
        total = records.count()
        present = records.filter(status='present').count()
        late = records.filter(status='late').count()
        absent = records.filter(status='absent').count()
        effective = present + late * 0.5
        percentage = round((effective / total) * 100) if total > 0 else 0
        course_stats.append({
            'course': e.course,
            'total': total, 'present': present,
            'late': late, 'absent': absent,
            'percentage': percentage,
        })

    # Today's attendance
    today = timezone.localdate()
    today_records = AttendanceRecord.objects.filter(
        student=request.user, class_date=today
    ).select_related('course')

    # Active sessions for enrolled courses
    now_time = timezone.localtime().time()
    active_sessions = AttendanceSession.objects.filter(
        course__in=[e.course for e in enrollments],
        session_date=today,
        is_active=True,
        start_time__lte=now_time,
        end_time__gte=now_time,
    ).select_related('course')

    return render(request, 'student/dashboard.html', {
        'course_stats': course_stats,
        'today_records': today_records,
        'active_sessions': active_sessions,
    })


@login_required
def mark_attendance(request):
    # ── CHANGED: support code arriving via GET (QR scan) or POST (manual form) ──
    prefilled_code = request.GET.get('code', '').upper().strip()

    if request.method == 'POST':
        code = request.POST.get('code', '').upper().strip()
        lat = request.POST.get('latitude')
        lon = request.POST.get('longitude')
        today = timezone.localdate()
        now = timezone.localtime()

        try:
            session = AttendanceSession.objects.get(
                qr_code=code, session_date=today, is_active=True
            )
        except AttendanceSession.DoesNotExist:
            return render(request, 'student/mark.html', {'error': 'Invalid or expired code', 'prefilled_code': prefilled_code})

        # Check enrollment
        if not Enrollment.objects.filter(
            student=request.user, course=session.course, status='enrolled'
        ).exists():
            return render(request, 'student/mark.html', {'error': 'You are not enrolled in this course', 'prefilled_code': prefilled_code})

        # Already marked?
        if AttendanceRecord.objects.filter(session=session, student=request.user).exists():
            return render(request, 'student/mark.html', {'error': 'Attendance already marked', 'prefilled_code': prefilled_code})

        # Already has pending attempt?
        if AttendanceAttempt.objects.filter(session=session, student=request.user, status='pending').exists():
            return render(request, 'student/mark.html', {
                'error': 'You have a pending verification request. Wait for teacher approval.',
                'prefilled_code': prefilled_code,
            })

        # Location check
        if session.teacher_latitude and session.teacher_longitude:
            if lat and lon:
                distance = haversine(
                    session.teacher_latitude, session.teacher_longitude,
                    float(lat), float(lon)
                )
                if distance > 200:
                    AttendanceAttempt.objects.create(
                    session=session,
                    student=request.user,
                    failure_reason=f'Outside range: {round(distance)}m away (limit: 15m)',
                    student_latitude=float(lat),
                    student_longitude=float(lon),
                    distance_from_teacher=distance,
                    )
                    return render(request, 'student/mark.html', {
                        'error': f'You are {round(distance)}m away from the classroom. Maximum allowed is 15m. Your attempt has been logged for teacher approval.'
                    })
            else:
                AttendanceAttempt.objects.create(
                    session=session,
                    student=request.user,
                    failure_reason='Location not provided',
                )
                return render(request, 'student/mark.html', {
                    'error': 'Location required. Please allow location access and try again.',
                    'prefilled_code': prefilled_code,
                })

        # Calculate status
        start_dt = timezone.make_aware(
            timezone.datetime.combine(today, session.start_time)
        )
        elapsed = int((now - start_dt).total_seconds() / 60)
        status = 'late' if elapsed > 10 else 'present'

        AttendanceRecord.objects.create(
            session=session,
            student=request.user,
            course=session.course,
            status=status,
            class_date=today,
            marked_by=request.user,
            student_latitude=float(lat) if lat else None,
            student_longitude=float(lon) if lon else None,
        )

        return render(request, 'student/mark.html', {
            'success': f'Marked as {status.upper()}!' + (' (0.5x credit)' if status == 'late' else '')
        })

    return render(request, 'student/mark.html', {'prefilled_code': prefilled_code})
    # ──────────────────────────────────────────────────────────────────────────


@login_required
def student_history(request):
    records = AttendanceRecord.objects.filter(
        student=request.user
    ).select_related('course', 'session').order_by('-class_date')
    return render(request, 'student/history.html', {'records': records})