from rest_framework import viewsets, status
from rest_framework.response import Response
from .models import Author, Book, Member, Loan
from .serializers import AuthorSerializer, BookSerializer, MemberSerializer, LoanSerializer, ExtendDueDateSerializer, TopMemberSerializer
from rest_framework.decorators import action
from django.utils import timezone
from django.db.models import Count, Q
from .tasks import send_loan_notification
import datetime

class AuthorViewSet(viewsets.ModelViewSet):
    queryset = Author.objects.all()
    serializer_class = AuthorSerializer

class BookViewSet(viewsets.ModelViewSet):
    queryset = Book.objects.select_related("author")
    serializer_class = BookSerializer

    @action(detail=True, methods=['post'])
    def loan(self, request, pk=None):
        book = self.get_object()
        if book.available_copies < 1:
            return Response({'error': 'No available copies.'}, status=status.HTTP_400_BAD_REQUEST)
        member_id = request.data.get('member_id')
        try:
            member = Member.objects.get(id=member_id)
        except Member.DoesNotExist:
            return Response({'error': 'Member does not exist.'}, status=status.HTTP_400_BAD_REQUEST)
        loan = Loan.objects.create(book=book, member=member)
        book.available_copies -= 1
        book.save()
        send_loan_notification.delay(loan.id)
        return Response({'status': 'Book loaned successfully.'}, status=status.HTTP_201_CREATED)

    @action(detail=True, methods=['post'])
    def return_book(self, request, pk=None):
        book = self.get_object()
        member_id = request.data.get('member_id')
        try:
            loan = Loan.objects.get(book=book, member__id=member_id, is_returned=False)
        except Loan.DoesNotExist:
            return Response({'error': 'Active loan does not exist.'}, status=status.HTTP_400_BAD_REQUEST)
        loan.is_returned = True
        loan.return_date = timezone.now().date()
        loan.save()
        book.available_copies += 1
        book.save()
        return Response({'status': 'Book returned successfully.'}, status=status.HTTP_200_OK)

class MemberViewSet(viewsets.ModelViewSet):
    queryset = Member.objects.all()
    serializer_class = MemberSerializer

    @action(detail=False, methods=['get'])
    def top_active(self, request, *args, **kwargs):
        top_members = Member.objects.annotate(
            active_loans=Count("loans", filter=Q(loans__is_returned=False)))\
                .filter(active_loans__gte=0).order_by("-active_loans")[:5]
        serializer = TopMemberSerializer(top_members, many=True)
        return Response(serializer.data, status=status.HTTP_200_OK)

class LoanViewSet(viewsets.ModelViewSet):
    queryset = Loan.objects.select_related("member__user", "book")
    serializer_class = LoanSerializer

    @action(detail=True, methods=['patch'])
    def extend_due_date(self, request, pk=None, *args, **kwargs):
        loan: Loan = self.get_object()
        serializer = ExtendDueDateSerializer(data=request.data)

        serializer.is_valid(raise_exception=True)

        if loan.due_date < timezone.now().date():
            return Response({
                "error": "Loan is already overdue"
            }, status=status.HTTP_400_BAD_REQUEST)
        loan.due_date = (loan.due_date + datetime.timedelta(days=serializer.validated_data["additional_days"]))
        loan.save(update_fields=["due_date"])

        return Response(LoanSerializer(loan).data, status=status.HTTP_200_OK)
