
from chatbot.serializers import ChatHistorySerializer
from chatbot.models import ChatHistory
from datetime import datetime, timedelta, time
from django.utils.dateparse import parse_date
from parkinglot.models import Zone, CarSlot, Floor
from booking_app.models import Booking, Vehicle, PackagePricing
from django.db.models import Q, Exists, OuterRef, F, Count
import json
import re
import google.generativeai as genai
from rest_framework import viewsets, generics



genai.configure(api_key="AIzaSyDVjpI4hd739ZABaq7fTjzrHcl3aiupfPk")
model = genai.GenerativeModel("gemini-2.5-flash")


def format_reply_to_text(reply_json):
    if isinstance(reply_json, dict) and "error" in reply_json:
        return f"Lỗi: {reply_json['error']}"

    if isinstance(reply_json, dict) and reply_json.get("success") is True:
        return f"Đặt chỗ thành công! Mã đặt chỗ của bạn là {reply_json['booking_id']}."

    if isinstance(reply_json, dict) and "available_count" in reply_json:
        available_count = reply_json["available_count"]
        result = [
            f"✅ Có {available_count} chỗ trống cho xe {reply_json['vehicle_type']} tại {reply_json['parking_lot']}, tầng {reply_json['floor']}, zone {reply_json['zone']}.",
            f"Gói: {reply_json['package_type'].capitalize()}, Ngày bắt đầu: {reply_json['date']}.",
        ]

        if "available_slots" in reply_json:
            slot_lines = [f"- Mã chỗ: {slot['code']} (ID: {slot['id']})" for slot in reply_json["available_slots"]]
            result.append("Danh sách chỗ trống:\n" + "\n".join(slot_lines))
        return "\n".join(result)

    return str(reply_json)

# --- Helper: tính end date theo gói ---
def _calc_end_date(start_date, package_type):
    if package_type == "weekly":
        return start_date + timedelta(days=6)
    elif package_type == "monthly":
        return start_date + timedelta(days=30)
    return start_date


# --- Function: tính slot khả dụng ---
def get_available_slots(date, package_type, floor_level, license_plate=None):
    start_date = parse_date(date)
    if not start_date:
        return {"error": "Ngày không hợp lệ"}

    end_date = _calc_end_date(start_date, package_type)
    start_dt = datetime.combine(start_date, time.min)
    end_dt = datetime.combine(end_date, time.max)

    try:
        floor = Floor.objects.get(level=floor_level)
    except Floor.DoesNotExist:
        return {"error": "Không tìm thấy tầng"}

    # Lấy vehicle từ biển số
    vehicle = Vehicle.objects.filter(license_plate=license_plate).first()
    if not vehicle:
        return {"error": f"Không tìm thấy thông tin xe với biển số {license_plate}"}

    zones = Zone.objects.filter(floor=floor, vehicle_type=vehicle.vehicle_type)
    if not zones.exists():
        return {"error": "Không tìm thấy zone phù hợp"}

    zone = zones.first()
    zone = Zone.objects.filter(id=zone.id).annotate(
        active_bookings=Count(
            "bookings",
            filter=Q(bookings__start_time__lte=end_dt,
                     bookings__end_time__gte=start_dt),
            distinct=True
        ),
        unavailable_slots=Count(
            "slots",
            filter=Q(slots__is_available=False),
            distinct=True
        )
    ).annotate(
        available_count=F("capacity") - F("active_bookings") -
        F("unavailable_slots")
    ).first()

    result = {
        "parking_lot": zone.floor.parking_lot.name,
        "floor": f"Tầng {zone.floor.level}",
        "zone": zone.name,
        "date": date,
        "package_type": package_type,
        "license_plate": license_plate,
        "vehicle_type": vehicle.vehicle_type,
        "available_count": zone.available_count
    }
  
    if vehicle.vehicle_type == "Car":
        slots = CarSlot.objects.filter(zone=zone).annotate(
            is_booked=Exists(
                Booking.objects.filter(
                    car_slot=OuterRef("pk"),
                    start_time__lte=end_dt,
                    end_time__gte=start_dt
                )
            )
        ).filter(is_booked=False, is_available=True)

        result["available_slots"] = list(slots.values("id", "code"))

    return result


def book_slot(date=None, package_type=None, floor_level=None, slot_id=None, user=None, license_plate=None):
    start_date = parse_date(date)
    if not start_date:
        return {"error": "Ngày không hợp lệ"}
    end_date = _calc_end_date(start_date, package_type)

    vehicle = Vehicle.objects.filter(license_plate=license_plate).first()
    price = PackagePricing.objects.get(
        package_type=package_type, vehicle_type=vehicle.vehicle_type
    ).price
    if not vehicle:
        return {"error": f"Không tìm thấy thông tin xe với biển số {license_plate}"}

    if vehicle.vehicle_type == "Car":
        if not slot_id:
            return {"error": "Xe ô tô cần chọn slot_id để đặt"}
        try:
            slot = CarSlot.objects.select_related(
                "zone__floor").get(id=slot_id)
        except CarSlot.DoesNotExist:
            return {"error": "Slot không tồn tại"}

        zone = slot.zone
        floor = zone.floor
        booking = Booking.objects.create(
            user=user,
            vehicle=vehicle,
            package_type=package_type,
            floor=floor,
            zone=zone,
            car_slot=slot,
            start_time=datetime.combine(start_date, time.min),
            end_time=datetime.combine(end_date, time.max),
            price=price
        )
    else:  # Motorbike → không cần slot_id
        zone = Zone.objects.filter(
            floor__level=floor_level, vehicle_type="Motorbike").first()
        if not zone:
            return {"error": "Không có zone cho xe máy"}
        floor = zone.floor
        booking = Booking.objects.create(
            user=user,
            vehicle=vehicle,
            package_type=package_type,
            floor=floor,
            zone=zone,
            start_time=datetime.combine(start_date, time.min),
            end_time=datetime.combine(end_date, time.max),
            price=price
        )

    return {"success": True, "booking_id": booking.id}


# --- Tool mapping để Gemini gọi function ---
TOOLS = {
    "get_available_slots": get_available_slots,
    "book_slot": book_slot,
}


class ChatHistoryViewSet(viewsets.ViewSet, generics.ListCreateAPIView):
    queryset = ChatHistory.objects.all()
    serializer_class = ChatHistorySerializer

    def get_queryset(self):
        user = self.request.user
        if user.is_authenticated:
            return self.queryset.filter(user=user).order_by("id")
        return super().get_queryset()

    def perform_create(self, serializer):
        try:
            serializer.is_valid(raise_exception=True)
            user = self.request.user if self.request.user.is_authenticated else None
            message = self.request.data.get("message", "")

            history_qs = ChatHistory.objects.filter(
                user=user).order_by("-id")[:5]
            history = [{"role": "user", "content": h.message}
                       for h in reversed(history_qs)]

            # system prompt ép Gemini trả JSON tool-call
            system_prompt = """
Bạn là một **chatbot thông minh chuyên hỗ trợ người dùng đặt chỗ giữ xe** tại các bãi đậu xe của hệ thống.

Vai trò của bạn:
- Trợ giúp người dùng kiểm tra chỗ trống cho xe máy hoặc ô tô.
- Hướng dẫn và thực hiện đặt chỗ giữ xe dựa trên thông tin được cung cấp.
- Bạn không được trả lời các câu hỏi ngoài phạm vi giữ xe.

❗ Quan trọng:
1. Nếu người dùng hỏi: "còn chỗ không", "kiểm tra", "xem slot trống", hoặc cung cấp thông tin như biển số, tầng, gói và ngày — nhưng chưa chọn slot cụ thể:
   → bạn PHẢI trả JSON tiếng Anh như sau:
   {"tool": "get_available_slots", "args": {"date": "...", "package_type": "...", "floor_level": ..., "license_plate": "..."}}

2. Nếu người dùng xác nhận đặt và có đầy đủ thông tin bao gồm slot_id:
   → bạn mới được gọi:
   {"tool": "book_slot", "args": {"date": "...", "package_type": "...", "floor_level": ..., "license_plate": "...", "slot_id": ...}}

3. Không được gọi "book_slot" nếu thiếu slot_id.

4. Nếu người dùng chỉ chào hỏi (ví dụ: "xin chào", "hi"), bạn nên trả lời:
   "Chào bạn! Tôi là trợ lý đặt chỗ giữ xe. Bạn cần kiểm tra chỗ trống hay muốn đặt chỗ?"

5. Nếu thiếu thông tin (ví dụ: thiếu tầng, ngày, biển số...), bạn cần hỏi lại để lấy đủ thông tin.

6. Tránh trả lời lan man. Luôn tập trung vào nhiệm vụ chính: hỗ trợ đặt chỗ giữ xe.
"""


            # tạo messages
            messages = [
                {"role": "user", "parts": [system_prompt]},
                {"role": "user", "parts": [message]},
            ]
            for h in history:
                messages.append({"role": "user", "parts": [h["content"]]})

            # gọi Gemini
            response = model.generate_content(
                messages, request_options={"timeout": 15})
            raw_text = response.text.strip()

            clean_text = re.sub(
                r"^```[a-zA-Z]*\s*|\s*```$", "", raw_text.strip())

            reply = ""
            try:
                parsed = json.loads(clean_text)
                if "tool" in parsed and parsed["tool"] in TOOLS:
                    func = TOOLS[parsed["tool"]]
                    args = parsed.get("args", {})
                    print("Calling tool:", parsed["tool"], "with args:", args)

                    if parsed["tool"] == "book_slot":
                        context = self.request.session.get(
                            "last_booking_context", {})
                        args.setdefault("date", context.get("date"))
                        args.setdefault(
                            "package_type", context.get("package_type"))
                        args.setdefault(
                            "floor_level", context.get("floor_level"))
                        args.setdefault("license_plate",
                                        context.get("license_plate"))
                        args["user"] = user  # chỉ book_slot mới cần user

                    raw_reply = func(**args)
                    reply = format_reply_to_text(raw_reply)

                    # lưu context cho lần sau nếu là get_available_slots
                    if parsed["tool"] == "get_available_slots":
                        self.request.session["last_booking_context"] = args
                else:
                    reply = clean_text
            except Exception as e:
                print("JSON parse error:", e)
                reply = raw_text

            # lưu vào DB
            serializer.save(user=user, message=message, response=reply)
            return super().perform_create(serializer)

        except Exception as e:
            print("Error in perform_create:", str(e))
            raise e
