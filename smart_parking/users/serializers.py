from users.models import User, Vehicle, Connection, Message
from rest_framework import serializers


class UserSerializer (serializers.ModelSerializer):

    def to_representation(self, instance):
        data = super().to_representation(instance)

        avatar = instance.avatar
        if hasattr(avatar, 'url'):
            data['avatar'] = avatar.url
        elif isinstance(avatar, str):
            data['avatar'] = avatar
        else:
            data['avatar'] = 'https://res.cloudinary.com/duiwbkm7z/image/upload/v1736772934/jadvn6oen2g7vozqt2cp.jpg'

        return data

    def modify_user_info(self, user, data):
        user.set_password(user.password)
        return user

    def create(self, validated_data):
        data = validated_data.copy()
        user = self.get_instance(**data)

        u = self.modify_user_info(user, data)
        u.save()

        return u

    def get_instance(self, *args, **kwargs):
        return User(**kwargs)

    class Meta:
        model = User
        fields = ['id', 'first_name', 'last_name',
                  'username', 'password', 'avatar', 'is_staff']
        extra_kwargs = {
            'password': {
                'write_only': True
            }
        }


class VehicleSerializer(serializers.ModelSerializer):
    class Meta:
        model = Vehicle
        fields = ["id", "license_plate", "vehicle_type", "name"]

    def create(self, validated_data):
        user = self.context['request'].user
        validated_data['user'] = user
        return super().create(validated_data)


class UserStatusSerializer(UserSerializer):
    status = serializers.SerializerMethodField()
    name = serializers.SerializerMethodField()
    # thumbnail = serializers.SerializerMethodField(source ="thumbnail")

    class Meta:
        model = User
        fields = ['username', 'avatar', 'name', 'status']

    # def get_thumbnail(self, user):
    #     print(user.thumbnail)
    #     if user.thumbnail:
    #         return user.thumbnail.name
    #     return None
    def get_name(self, obj):
        fname = obj.first_name.capitalize()
        lname = obj.last_name.capitalize()
        return f'{fname} {lname}'

    def get_status(self, obj):
        print(obj)
        if hasattr(obj, 'pending_them') and obj.pending_them:
            return 'pending-them'
        elif hasattr(obj, 'pending_me') and obj.pending_me:
            return 'pending-me'
        elif hasattr(obj, 'connected') and obj.connected:
            return 'connected'
        return 'no-connected'


class ConnectionSerializer(serializers.ModelSerializer):
    sender = UserStatusSerializer()
    receiver = UserSerializer()

    class Meta:
        model = Connection
        fields = ['id', 'sender', 'receiver', 'created_at']


class FriendListSerializer(serializers.ModelSerializer):
    friend = serializers.SerializerMethodField()
    preview = serializers.SerializerMethodField()
    updated_at = serializers.SerializerMethodField()

    class Meta:
        model = Connection
        fields = ['id', 'friend', 'preview', 'updated_at']

    def get_friend(self, obj):
        if self.context['user'] == obj.sender:
            return UserStatusSerializer(obj.receiver).data
        elif self.context['user'] == obj.receiver:
            return UserStatusSerializer(obj.sender).data
        else:
            print('Error :No user found')

    def get_preview(self, obj):
        if not hasattr(obj, 'latest_content'):
            return 'New Connections'
        return obj.latest_content

    def get_updated_at(self, obj):
        date = getattr(obj, 'latest_created_at', obj.updated_at)
        print('date', date)
        if date is None:
            return ''
        return date.isoformat()


class MessageSerializer(serializers.ModelSerializer):
    is_me = serializers.SerializerMethodField()

    class Meta:
        model = Message
        fields = ['id', 'is_me', 'content', 'created_at']

    def get_is_me(self, obj):
        return self.context['user'] == obj.user
