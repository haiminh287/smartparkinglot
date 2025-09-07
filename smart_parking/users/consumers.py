import json
from channels.generic.websocket import AsyncWebsocketConsumer, WebsocketConsumer
from users.models import User, Connection, Message
from channels.db import database_sync_to_async
from asgiref.sync import sync_to_async
from django.contrib.auth.models import AnonymousUser
from django.core.files.base import ContentFile
from users import serializers
import base64
import time
from django.db.models import Q
from django.db.models import OuterRef
from django.db.models.functions import Coalesce
from rest_framework_simplejwt.tokens import UntypedToken
from rest_framework_simplejwt.exceptions import InvalidToken, TokenError
from django.conf import settings
from jwt import decode as jwt_decode
import pprint
call_rooms = {}


# class WebRTCConsumer(AsyncWebsocketConsumer):

#     async def connect(self):
#         self.token = self.scope['query_string'].decode().split('=')[1]
#         self.user = await self.get_user_from_token(self.token)
#         if self.user is None and isinstance(self.user, AnonymousUser):
#             await self.close()
#         await self.channel_layer.group_add(self.user.username, self.channel_name)
#         await self.accept()

#     async def disconnect(self, close_code):
#         await self.channel_layer.group_discard(self.user.username, self.channel_name)

#     async def receive(self, text_data):
#         data = json.loads(text_data)
#         print('receive', data)
#         action = data.get("offer")
#         target_username = data.get("receiverUsername")
#         # print('action', action)
#         if (action):
#             action = action['type']
#         if not target_username:
#             return
#         if action == "offer":
#             print('action', action)
#             await self.send_group(target_username, "offer", {"offer": data["offer"], "from": self.user.username})

#         elif action == "answer":
#             await self.send_group(target_username, "answer", {"answer": data["answer"], "from": self.user.username})

#         elif action == "candidate":
#             await self.send_group(target_username, "candidate", {"candidate": data["candidate"], "from": self.user.username})

#     async def send_group(self, group_name, source, data):
#         response = {
#             'type': 'broadcast_group',
#             'source': source,
#             'data': data
#         }
#         await self.channel_layer.group_send(group_name, response)

#     async def broadcast_group(self, event):
#         event.pop('type')
#         await self.send(text_data=json.dumps(event))

#     @database_sync_to_async
#     def get_user_from_token(self, token):
#         try:
#             # Validate token
#             UntypedToken(token)
#             # Decode payload
#             payload = jwt_decode(
#                 token, settings.SECRET_KEY, algorithms=["HS256"])
#             user_id = payload.get('user_id')
#             return User.objects.get(id=user_id)
#         except (InvalidToken, TokenError, User.DoesNotExist):
#             return AnonymousUser()


class ChatConsumer(AsyncWebsocketConsumer):
    async def connect(self):
        self.token = self.scope['query_string'].decode().split('=')[1]
        self.user = await self.get_user_from_token(self.token)
        if self.user is None and isinstance(self.user, AnonymousUser):
            await self.close()
        await self.channel_layer.group_add(self.user.username, self.channel_name)
        await self.accept()

    async def disconnect(self, close_code):
        await self.channel_layer.group_discard(self.user.username, self.channel_name)

    async def receive(self, text_data):
        data = json.loads(text_data)
        data_source = data.get('source')
        if data_source == 'friend.list':
            await self.receive_friend_list(data)

        elif data_source == 'message.list':
            await self.receive_message_list(data)

        elif data_source == 'message.send':
            await self.receive_message_send(data)

        elif data_source == 'message.type':
            await self.receive_message_type(data)

        elif data_source == 'request.connect':
            await self.receive_request_connect(data)

        if data_source == 'request.accept':
            await self.receive_request_accept(data)

        elif data_source == 'request.list':
            await self.receive_request_list(data)

        # elif data_source == 'thumbnail':
        #     await self.receive_thumbnail(data)
        print('receive', data)

    # async def receive_thumbnail(self, data):
    #     image_src = data.get('base64')
    #     print('user', self.user)
    #     image = ContentFile(base64.b64decode(image_src))
    #     file_name = f'thumbnails/{self.user.username}.png'
    #     await self.save_thumbnail(file_name, image)
    #     serialized_user = serializers.UserSerializer(self.user).data
    #     await self.send_group(self.user.username, 'thumbnail', serialized_user)

    # @database_sync_to_async
    # def save_thumbnail(self, file_name, image):
    #     self.user.thumbnail.save(file_name, image, save=True)

    async def receive_friend_list(self, data):
        print('receive_friend_list', data)
        friends = await self.get_friends(self.user)
        serializer_friends = serializers.FriendListSerializer(
            friends, context={'user': self.user}, many=True)

        await self.send_group(self.user.username, 'friend.list', serializer_friends.data)

    @database_sync_to_async
    def get_friends(self, user):
        latest_message = Message.objects.filter(
            connection=OuterRef('id')).order_by('-id')[:1]
        connections = list(Connection.objects.filter(Q(sender=user) | Q(receiver=user), accepted=True).annotate(
            latest_content=latest_message.values('content'),
            latest_created_at=latest_message.values('created_at')
        ).order_by(Coalesce('latest_created_at', 'updated_at').desc()))
        print('friends', connections)
        return connections

    async def receive_message_list(self, data):
        print('receive_message_list', data)
        connection_id = data.get('connectionId')
        page = data.get('page')
        page_size = 15
        try:
            connection = await self.get_connection_by_id(connection_id)
        except Connection.DoesNotExist:
            print('connection not found')
            return
        messages = await self.get_messages(connection, page, page_size)
        serializer_messages = serializers.MessageSerializer(
            messages, context={'user': self.user}, many=True)
        recipient = connection.sender if connection.sender != self.user else connection.receiver
        serializer_friend = serializers.UserSerializer(recipient)

        message_count = await self.count_messages(connection)
        next_page = page + 1 if message_count > (page+1)*page_size else None
        data = {
            'messages': serializer_messages.data,
            'next': next_page,
            'friend': serializer_friend.data
        }
        await self.send_group(self.user.username, 'message.list', data)

    @database_sync_to_async
    def get_messages(self, connection, page, page_size):
        messages = list(Message.objects.filter(
            connection=connection).order_by('-id')[page*page_size:(page+1)*page_size])
        print('messages', messages)
        return messages

    @database_sync_to_async
    def count_messages(self, connection):
        return Message.objects.filter(connection=connection).count()

    async def receive_message_send(self, data):
        print('receive_message_send', data)
        connection_id = data.get('connectionId')
        message_text = data.get('message')
        try:
            connection = await self.get_connection_by_id(connection_id)
        except Connection.DoesNotExist:
            print('connection not found')
            return
        message = await self.create_message(connection, self.user, message_text)

        recipient = connection.sender if connection.sender != self.user else connection.receiver
        serializer_message = serializers.MessageSerializer(
            message, context={'user': self.user})
        serializer_friend = serializers.UserSerializer(recipient)

        data = {
            'message': serializer_message.data,
            'friend': serializer_friend.data
        }
        await self.send_group(self.user.username, 'message.send', data)

        serializer_message = serializers.MessageSerializer(
            message, context={'user': recipient})
        serializer_friend = serializers.UserSerializer(self.user)

        data = {
            'message': serializer_message.data,
            'friend': serializer_friend.data
        }
        await self.send_group(recipient.username, 'message.send', data)

    async def receive_message_type(self, data):
        recipient_username = data.get('username')
        data = {
            'username': self.user.username
        }
        await self.send_group(recipient_username, 'message.type', data)

    @database_sync_to_async
    def create_message(self, connection, user, content):
        message = Message.objects.create(
            connection=connection, user=user, content=content)
        return message

    async def receive_request_connect(self, data):
        print('receive_request_connect', data)
        username = data.get('username')
        try:
            receiver = await self.get_user_from_username(username)
        except User.DoesNotExist:
            print('receiver not found')
            return
        connection = await self.create_connection(self.user, receiver)
        serializer_connection = serializers.ConnectionSerializer(connection)
        await self.send_group(connection.sender.username, 'request.connect', serializer_connection.data)
        await self.send_group(connection.receiver.username, 'request.connect', serializer_connection.data)

    async def receive_request_accept(self, data):
        print('receive_request_accept', data)
        username = data.get('username')
        try:
            connection = await self.get_connection(username)
        except Connection.DoesNotExist:
            print('connection not found')
            return
        connection.accepted = True
        await self.save_connection(connection)
        serializer_connection = serializers.ConnectionSerializer(connection)
        await self.send_group(connection.sender.username, 'request.accept', serializer_connection.data)
        await self.send_group(connection.receiver.username, 'request.accept', serializer_connection.data)

        serializer_friend = serializers.FriendListSerializer(
            connection, context={'user': connection.sender})
        await self.send_group(connection.sender.username, 'friend.new', serializer_friend.data)

        serializer_friend = serializers.FriendListSerializer(
            connection, context={'user': connection.receiver})
        await self.send_group(connection.receiver.username, 'friend.new', serializer_friend.data)

    @database_sync_to_async
    def get_connection(self, username):
        connection = Connection.objects.get(
            sender__username=username, receiver=self.user)
        print('new connection', connection)
        return connection

    @database_sync_to_async
    def get_connection_by_id(self, connection_id):
        connection = Connection.objects.get(id=connection_id)
        print('connection', connection)
        return connection

    @database_sync_to_async
    def save_connection(self, connection):
        connection.save()

    @database_sync_to_async
    def get_request_connections(self, receiver):
        connections = set(Connection.objects.filter(
            receiver=receiver, accepted=False))
        print('connections', connections)
        return connections

    async def receive_request_list(self, data):
        print('receive_request_list', data)
        print('user', self.user)
        try:
            connections = await self.get_request_connections(self.user)
            print('connection', connections)
        except Exception as e:
            print('connections not found', e)
            return
        serializer_connections = serializers.ConnectionSerializer(
            connections, many=True)
        print('serializer_connections', serializer_connections.data)
        await self.send_group(self.user.username, 'request.list', serializer_connections.data)

    async def send_group(self, group_name, source, data):
        response = {
            'type': 'broadcast_group',
            'source': source,
            'data': data
        }
        print("📡 send_group:", pprint.pformat(response))
        await self.channel_layer.group_send(group_name, response)

    async def broadcast_group(self, event):
        # event_type = event.get("type")
        # print("📡 broadcast_group:", pprint.pformat(event))
        # if event_type:
        #     event.pop("type")
        # await self.send(text_data=json.dumps(event))
        await self.send(text_data=json.dumps({
            "source": event.get("source"),
            "data": event.get("data"),
        }))

    @database_sync_to_async
    def get_user_from_token(self, token):
        try:
            # Validate token
            UntypedToken(token)
            # Decode payload
            payload = jwt_decode(
                token, settings.SECRET_KEY, algorithms=["HS256"])
            user_id = payload.get('user_id')
            return User.objects.get(id=user_id)
        except (InvalidToken, TokenError, User.DoesNotExist):
            return AnonymousUser()

    @database_sync_to_async
    def get_user_from_username(self, username):
        try:
            user = User.objects.get(username=username)
            return user
        except User.DoesNotExist:
            return AnonymousUser()

    @database_sync_to_async
    def create_connection(self, sender, receiver):
        connection, created = Connection.objects.get_or_create(
            sender=sender, receiver=receiver)
        return connection
