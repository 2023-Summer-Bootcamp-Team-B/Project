import json
import asyncio
import time
from channels.generic.websocket import AsyncWebsocketConsumer
from asgiref.sync import sync_to_async
from .models import Room, SubRoom, Topic
from .tasks import create_image, translate_text


class RoomConsumer(AsyncWebsocketConsumer):
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.room_id = None
        self.room_group_name = None
        self.sub_room_id = None
        # 게임중 자신이 주제를 넣고 있는 subroom
        self.present_sub_room = None
        self.last_activity_time = None
        self.ping_interval = 50  # 핑 메시지 전송 간격 (초)
        self.timeout = 60  # 연결 타임아웃 시간 (초)
        self.ping_task = None
        self.round = 0

    async def send(self, text_data=None, bytes_data=None, close=False):
        try:
            await super().send(text_data, bytes_data, close)
        except Exception as e:
            print(f"Failed to send message: {e}")

    async def connect(self, text_data=None):
        if text_data is not None:
            json.loads(text_data)

        self.room_id = self.scope["url_route"]["kwargs"]["roomid"]
        self.room_group_name = "main_room_%s" % self.room_id

        # 웹소켓 연결을 활성화하며 유저를 방에 참가시킴
        await self.channel_layer.group_add(self.room_group_name, self.channel_name)
        await self.accept()

        self.last_activity_time = time.time()
        self.ping_task = asyncio.create_task(self.send_ping())

        # 서브 게임방 생성 로직
        room = await sync_to_async(Room.objects.get)(id=self.room_id)
        sub_room_count = await sync_to_async(
            SubRoom.objects.filter(room=room, delete_at=None).count
        )()

        if sub_room_count >= 6:
            error_message = "방이 가득 찼습니다."
            await self.send(text_data=json.dumps({"error": error_message}))
            await self.close(1008)
            return

        sub_room = await sync_to_async(SubRoom.add_subroom)(room)  # 방 생성
        self.sub_room_id = sub_room.id

        await self.send(
            text_data=json.dumps(
                {
                    "event": "connected",
                    "data": {
                        "playerId": sub_room.id,
                    },
                }
            )
        )

        # 현재 연결된 subroom 초기화
        self.present_sub_room = sub_room
        if self.present_sub_room is None:
            print("present_sub_room 없어")
        print(self.present_sub_room.id)

        # 서브룸을 전부 가져오는 로직을 구현한 뒤, 해당 데이터를 전송합니다.
        await self.send_player_list()

    async def disconnect(self, close_code):
        if self.ping_task:
            self.ping_task.cancel()

        # 웹소켓 연결을 비활성화하며 유저를 방 그룹에서 제거
        await self.channel_layer.group_discard(self.room_group_name, self.channel_name)

        # 서브 게임방 테이블을 삭제
        sub_room = await sync_to_async(SubRoom.objects.get)(id=self.sub_room_id)
        if sub_room:
            await sync_to_async(sub_room.delete_subroom)()

        # 서브 게임방이 비어있으면 메인 게임방 테이블을 삭제
        room = await sync_to_async(Room.objects.get)(id=self.room_id)
        remaining_subrooms_exists = await sync_to_async(
            SubRoom.objects.filter(room=room, delete_at=None).exists
        )()
        if not remaining_subrooms_exists:
            await sync_to_async(room.delete)()

        # 서브룸을 전부 가져오는 로직을 구현한 뒤, 해당 데이터를 전송합니다.
        await self.send_player_list()

    async def receive(self, text_data=None, bytes_data=None, **kwargs):
        if text_data:
            res = json.loads(text_data)
            event = res.get("event")
            data = res.get("data")
            print(res)

            if event == "nameChanged":  # "change_name" 이벤트로 변경된 이름 처리
                await self.handle_name_change(data)

            elif event == "startGame":
                # 현재 연결된 subroom 초기화
                self.present_sub_room = await sync_to_async(SubRoom.objects.get)(
                    id=self.sub_room_id
                )

                # room에 있는 모든 인원에게 게임을 시작 신호 보냄, 모든 인원에 self.round를 1로 해줌
                self.round = 1
                await self.channel_layer.group_send(
                    self.room_group_name,
                    {
                        "type": "start",
                        "message": {"event": "gameStart", "round": self.round},
                    },
                )

            # subroom의 주제 입력 이벤트
            elif event == "inputTitle":
                title = data["title"]
                player_id = data["playerId"]

                # 현재 룸안에 모든 인원
                room_num = await self.get_room_count()

                # 주제 객체 만듬
                await self.save_topic(title, player_id)

                # room 가지고 옴
                room = await sync_to_async(Room.objects.get)(id=self.room_id)

                # completeNum 1 더함
                room.completeNum += 1
                await sync_to_async(room.save)()

                # 모든 인원에게 completeNum 보내줌
                await self.channel_layer.group_send(
                    self.room_group_name,
                    {
                        "type": "make_new_topic",
                        "message": {
                            "event": "completeUpdate",
                            "data": {"completeNum": room.completeNum},
                        },
                    },
                )

                # 라운드 변경
                # 1. room 인원수 == 완료 인원수
                if room_num <= room.completeNum:
                    # 1.5. completeNum = 0으로 변경
                    room.completeNum = 0
                    await sync_to_async(room.save)()

                    # 2. group_send로 로딩 화면 출력, 모든 인원 image url 생성
                    await self.channel_layer.group_send(
                        self.room_group_name,
                        {
                            "type": "show_loading",
                            "message": {"event": "loading_and_url", "data": "로딩이다."},
                        },
                    )

                    # 3. ai image url 생성하고 클라이언트에게 보냄
                    await self.channel_layer.group_send(
                        self.room_group_name,
                        {"type": "ai_image_url", "message": "ai image url 생성"},
                    )

                    # 4. 다음 라운드 정보들을 보내줌
                    await self.channel_layer.group_send(
                        self.room_group_name,
                        {"type": "next_round", "message": "다음 라운드 정보 주거나 게임 종료"},
                    )

            # 주제 편집 (가장 최신으로 만들어진 것을 변경함)
            elif event == "changeTitle":
                title = data["title"]
                player_id = data["playerId"]

                # 현재 subroom에 있는 가장 최신에 topic을 찾음
                topic = await sync_to_async(Topic.get_last_topic)(self.present_sub_room.id)

                # topic의 title을 data에 있는 title로 바꿔줌
                topic.title = title
                await sync_to_async(topic.save)()

            elif event == "ping":
                self.last_activity_time = time.time()
                print("ping received")
                await self.send(text_data=json.dumps({"event": "pong", "data": "pong"}))

            elif event == "pong":
                self.last_activity_time = time.time()
                print("pong received")

            elif event == "submitTopic":
                await self.handle_topic_submission(data)

    async def send_ping(self):
        while True:
            try:
                await self.send(text_data=json.dumps({"event": "ping", "data": "ping"}))
                await asyncio.sleep(self.ping_interval)
                self.last_activity_time = time.time()
                elapsed_time = time.time() - self.last_activity_time
                if elapsed_time > self.timeout:
                    await self.close()
                    break
            except asyncio.CancelledError:
                break
            except Exception as e:
                print(f"Unexpected error occurred: {e}")
                break

    async def handle_topic_submission(self, data):
        # 주제 제출 처리 로직 작성
        pass

    async def renew_list(self, event):
        message_content = event["message"]

        await self.send(text_data=json.dumps(message_content))

    async def make_new_topic(self, event):
        message_content = event["message"]

        await self.send(text_data=json.dumps(message_content))

    async def start(self, event):
        message_content = event["message"]
        self.round = message_content["round"]
        await self.send(text_data=json.dumps(message_content))

    async def show_loading(self, event):
        message_content = event["message"]

        await self.send(text_data=json.dumps(message_content))

    async def ai_image_url(self, event):
        # 이번 라운드 주제 가져옴
        topic = await sync_to_async(Topic.get_last_topic)(self.present_sub_room.id)

        # papago 번역
        translated_result = await sync_to_async(translate_text.delay)(topic.title)

        translated_text = await sync_to_async(translated_result.get)()
        # Celery 작업 호출
        result = await sync_to_async(create_image.delay)(translated_text)

        # 작업의 결과를 기다리지 않고 즉시 응답을 보냅니다.
        await self.send(
            text_data=json.dumps({"message": "Image creation started", "task_id": result.id})
        )

        # 작업 완료까지 대기하지 않고 클라이언트에게 결과를 전송합니다.
        image_url = await sync_to_async(result.get)()
        await self.send(
            text_data=json.dumps({"message": "Image creation completed", "image_url": image_url})
        )

        # DB에 url 저장
        topic.url = image_url
        await sync_to_async(topic.save)()

    async def next_round(self, event):
        # 현재 룸안에 모든 인원
        room_num = await self.get_room_count()

        # room 가지고 옴
        room = await sync_to_async(Room.objects.get)(id=self.room_id)

        # 1. round에 1 더해줌
        self.round += 1

        # 마지막 라운드인 경우
        # 2. room 인원수 < round
        if room_num < self.round:
            # 2-1. 게임 종료 group_send 함 (임시)
            await self.send(text_data=json.dumps({"event": "end", "data": "게임이 종료 됐습니다."}))

        # 3. present_sub_room을 현재 subroom의 next_sub_room으로 변경
        self.present_sub_room = await sync_to_async(SubRoom.objects.get)(
            id=self.present_sub_room.id
        )

        # 4. 다음 라운드로 이동해
        await self.send(
            text_data=json.dumps(
                {
                    "event": "moveNextRound",
                    "data": {
                        "round": self.round,
                        "complete": room.completeNum,
                    },
                }
            )
        )

    @sync_to_async
    def get_room_count(self):
        room = Room.objects.get(id=self.room_id)
        room_count = SubRoom.objects.filter(room=room, delete_at=None).count()

        return room_count

    @sync_to_async
    def save_topic(self, title, player_id):
        # subRoom 찾음
        sub_room = SubRoom.objects.get(id=player_id)
        topic = Topic.objects.create(title=title, url=None, sub_room=sub_room)
        return topic

    async def handle_name_change(self, data):
        player_id = data.get("playerId")
        new_name = data.get("name")

        sub_room = await self.get_sub_room_by_id(player_id)
        if sub_room:
            sub_room.first_player = new_name
            await sync_to_async(sub_room.save)()

            # 이름 변경 성공 메시지를 해당 클라이언트로 전송
            await self.send(text_data=json.dumps({"event": "changeName", "data": "이름 변경 성공"}))

            # 변경된 플레이어 리스트를 전체 클라이언트에게 전송
            await self.send_player_list()

    async def get_sub_room_by_id(self, player_id):
        try:
            return await sync_to_async(SubRoom.objects.get)(id=player_id)
        except SubRoom.DoesNotExist:
            return None

    async def send_player_list(self):
        # 현재 방에 있는 모든 플레이어 정보를 가져오고 프론트엔드로 해당 데이터를 전송
        room = await sync_to_async(Room.objects.get)(id=self.room_id)
        sub_rooms = await sync_to_async(SubRoom.objects.filter)(room=room, delete_at=None)

        players_data = await sync_to_async(
            lambda: [
                {
                    "player_id": subroom.id,
                    "name": subroom.first_player,
                    "isHost": subroom.is_host,
                }
                for subroom in sub_rooms
            ]
        )()

        await self.channel_layer.group_send(
            self.room_group_name,
            {
                "type": "renew_list",
                "message": {
                    "event": "renewList",
                    "data": {
                        "players": players_data,
                    },
                },
            },
        )
