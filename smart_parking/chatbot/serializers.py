from rest_framework import serializers
from chatbot.models import ChatHistory


class ChatHistorySerializer(serializers.ModelSerializer):
    class Meta:
        model = ChatHistory
        fields = "__all__"
        read_only_fields = ['id', 'user', 'response',
                            'created_at', 'updated_at', 'is_active']
