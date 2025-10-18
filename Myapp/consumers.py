import json
from channels.generic.websocket import AsyncWebsocketConsumer

class UserConsumer(AsyncWebsocketConsumer):
    async def connect(self):
        self.user_id = self.scope['url_route']['kwargs']['user_id']
        self.group_name = f"user_{self.user_id}"
        await self.channel_layer.group_add(self.group_name, self.channel_name)
        await self.accept()
        print(f"✅ WebSocket connecté pour l'utilisateur {self.user_id}")

    async def disconnect(self, close_code):
        await self.channel_layer.group_discard(self.group_name, self.channel_name)
        print(f"❌ WebSocket déconnecté pour l'utilisateur {self.user_id}")

    # ⚠️ Cette méthode doit correspondre au type envoyé via group_send
    async def user_update(self, event):  # 🔥 correspond au type envoyé
        await self.send(text_data=json.dumps(event['data']))