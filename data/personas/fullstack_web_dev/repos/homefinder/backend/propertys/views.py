from django.db.models import Q
from rest_framework import serializers, viewsets
from rest_framework.permissions import IsAuthenticatedOrReadOnly

from .models import Property


class PropertySerializer(serializers.ModelSerializer):
    class Meta:
        model = Property
        fields = ["id", "address", "price", "bedrooms", "created_at"]


class PropertyViewSet(viewsets.ModelViewSet):
    serializer_class = PropertySerializer
    permission_classes = [IsAuthenticatedOrReadOnly]

    def get_queryset(self):
        queryset = Property.objects.all().order_by("-created_at")
        term = self.request.query_params.get("q")
        if term:
            queryset = queryset.filter(Q(address__icontains=term) | Q(bedrooms__icontains=term))
        return queryset
