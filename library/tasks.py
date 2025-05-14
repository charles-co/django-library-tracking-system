from celery import shared_task
from .models import Loan
from django.core.mail import send_mail
from django.conf import settings
from django.utils import timezone

@shared_task
def send_loan_notification(loan_id):
    try:
        loan = Loan.objects.get(id=loan_id)
        member_email = loan.member.user.email
        book_title = loan.book.title
        send_mail(
            subject='Book Loaned Successfully',
            message=f'Hello {loan.member.user.username},\n\nYou have successfully loaned "{book_title}".\nPlease return it by the due date.',
            from_email=settings.DEFAULT_FROM_EMAIL,
            recipient_list=[member_email],
            fail_silently=False,
        )
    except Loan.DoesNotExist:
        pass


@shared_task
def check_overdue_loans():
    print("Running check overdue loans")
    loans = Loan.objects.select_related("member__user", "book")\
        .filter(is_returned=False, due_date__lt=timezone.now().date())

    # FIXME: One email per member for member that loan multiple book
    # to avoid clogging email
    if loans:
        for loan in loans:
            send_mail(
            subject='Book Loaned Successfully',
            message=f'Hello {loan.member.user.username},\n\nYou have an overdue book "{loan.book.title} to return since {loan.due_date}".\nPlease return it as soon as possible.',
            from_email=settings.DEFAULT_FROM_EMAIL,
            recipient_list=[loan.member.user.email],
            fail_silently=False,
        )


