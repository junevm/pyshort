from rest_framework import viewsets
from rest_framework.authentication import TokenAuthentication
from rest_framework.decorators import action
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response

from shortener.models import APIKey, ClickEvent, ShortenedURL
from shortener.serializers import APIKeySerializer, ClickEventSerializer, ShortenedURLSerializer


class ShortenedURLViewSet(viewsets.ModelViewSet):
    serializer_class = ShortenedURLSerializer
    authentication_classes = [TokenAuthentication]
    permission_classes = [IsAuthenticated]

    def get_queryset(self):
        return ShortenedURL.objects.filter(user=self.request.user)

    def perform_create(self, serializer):
        serializer.save(user=self.request.user)

    @action(detail=True, methods=['get'])
    def clicks(self, request, pk=None):
        obj = self.get_object()
        events = ClickEvent.objects.filter(shortened_url=obj).order_by('-clicked_at')[:100]
        serializer = ClickEventSerializer(events, many=True)
        return Response(serializer.data)

    @action(detail=True, methods=['post'])
    def toggle_active(self, request, pk=None):
        obj = self.get_object()
        obj.is_active = not obj.is_active
        obj.save(update_fields=['is_active'])
        return Response({'is_active': obj.is_active})


class APIKeyViewSet(viewsets.ModelViewSet):
    serializer_class = APIKeySerializer
    authentication_classes = [TokenAuthentication]
    permission_classes = [IsAuthenticated]

    def get_queryset(self):
        return APIKey.objects.filter(user=self.request.user)

    def perform_create(self, serializer):
        serializer.save(user=self.request.user)
