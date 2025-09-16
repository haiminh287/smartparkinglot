from rest_framework import viewsets, permissions, status
from booking_app import models, serializers, services
from rest_framework import generics
from rest_framework.response import Response
from rest_framework.decorators import action
import heapq
from parkinglot.models import MapNode, MapEdge


class PackagePricingListView(generics.ListAPIView):
    queryset = models.PackagePricing.objects.all()
    serializer_class = serializers.PackagePricingSerializer
    permission_classes = [permissions.AllowAny]


class BookingViewSet(viewsets.ModelViewSet):
    queryset = models.Booking.objects.all()
    serializer_class = serializers.BookingSerializer
    permission_classes = [permissions.IsAuthenticated]

    def get_serializer_class(self):
        if self.action in ["list", "retrieve"]:
            return serializers.BookingDetailSerializer
        return self.serializer_class

    def get_queryset(self):
        user = self.request.user
        queryset = self.queryset
        vehicle_type = self.request.query_params.get("vehicle_type")
        if vehicle_type:
            queryset = queryset.filter(vehicle__vehicle_type=vehicle_type)

        if user.is_authenticated:
            queryset = queryset.filter(user=user)
        return queryset

    @action(detail=True, methods=["get"], url_path="pay")
    def pay_booking(self, request, pk=None):
        booking = self.get_object()
        if booking.payment_status == models.PaymentStatus.COMPLETED:
            return Response({"detail": "Booking already paid."}, status=400)
        momo_response = services.get_qr_momo(
            booking.id, booking.price, '/booking-history', '/booking-history')
        if momo_response.status_code == 200:
            pay_url = momo_response.json().get('payUrl')
            if pay_url:
                return Response({"pay_url": pay_url}, status=200)

        return Response({"detail": "Payment init failed."}, status=400)

    @action(detail=True, methods=["post"], url_path="confirm-payment")
    def confirm_payment(self, request, pk=None):
        booking = self.get_object()
        result_code = request.data.get("resultCode")

        if str(result_code) == "0":
            booking.payment_status = models.PaymentStatus.COMPLETED
            booking.save()
            return Response({"detail": "Payment confirmed"}, status=200)

        booking.payment_status = models.PaymentStatus.FAILED
        booking.save()
        return Response({"detail": "Payment failed"}, status=400)

    @action(detail=True, methods=["post"], url_path="update-status")
    def update_status(self, request, pk=None):
        booking = self.get_object()
        payment_status = request.data.get("payment_status")
        booking.payment_status = payment_status
        booking.save()
        return Response({"detail": "Update status successfully"}, status=200)

    @action(detail=True, methods=["get"], url_path="path")
    def get_path(self, request, pk=None):
        booking = self.get_object()
        slot_node = getattr(booking.car_slot, "map_node", None)

        if not slot_node:
            return Response({"error": "Slot chưa có node"}, status=400)
       
        gate_node = MapNode.objects.filter(is_gate=True).first()
        if not gate_node:
            return Response({"error": "Không có Gate"}, status=400)

        graph = self.build_graph(target_slot_node_id=slot_node.id)

        path_node_ids = self.dijkstra(gate_node.id, slot_node.id, graph)
        if not path_node_ids:
            return Response({"error": "Không tìm được đường đi"}, status=400)
        nodes = MapNode.objects.filter(id__in=path_node_ids).in_bulk()
        path = [
            {
                "id": n.id,
                "name": n.name,
                "x": n.x,
                "y": n.y,
                "floor": n.floor.level if n.floor else None,
            }
            for n in (nodes[nid] for nid in path_node_ids)
        ]

        # ✅ Sinh step-by-step
        steps = []
        for i in range(len(path_node_ids) - 1):
            u, v = path_node_ids[i], path_node_ids[i + 1]
            edge = (
                MapEdge.objects.filter(start_id=u, end_id=v).first()
                or MapEdge.objects.filter(start_id=v, end_id=u).first()
                
            )
            if edge:
                action = edge.get_direction_display()
                if edge.direction == "elevator":
                    action = f"Đi thang máy lên tầng {nodes[v].floor.level}"
                steps.append(
                    {
                        "from": nodes[u].name,
                        "to": nodes[v].name,
                        "action": action,
                        "distance": edge.distance,
                    }
                )

        return Response(
            {
                "slot": {
                    "id": booking.car_slot.id,
                    "code": booking.car_slot.code,
                    "floor": booking.car_slot.zone.floor.level,
                    "x": booking.car_slot.map_node.x,
                    "y": booking.car_slot.map_node.y,
                },
                "path": path,
                "steps": steps,
            }
        )

    def build_graph(self, target_slot_node_id=None):
        graph = {}
        for edge in MapEdge.objects.select_related("start", "end").all():
            u, v = edge.start, edge.end
            
            if (u.node_type == "slot" and u.id != target_slot_node_id) or \
            (v.node_type == "slot" and v.id != target_slot_node_id):
                continue

            graph.setdefault(u.id, []).append((v.id, edge.distance))
            graph.setdefault(v.id, []).append((u.id, edge.distance))
        return graph



    def dijkstra(self, start_id, target_id, graph):
        distances = {node_id: float('inf') for node_id in graph.keys()}
        prev = {}
        distances[start_id] = 0
        pq = [(0, start_id)]

        while pq:
            dist_u, u = heapq.heappop(pq)
            if dist_u > distances.get(u, float('inf')):
                continue
            if u == target_id:
                break
            for v, w in graph.get(u, []):
                nd = dist_u + w
                if nd < distances.get(v, float('inf')):
                    distances[v] = nd
                    prev[v] = u
                    heapq.heappush(pq, (nd, v))

        if target_id not in prev and start_id != target_id:
            return []

        path = [target_id]
        cur = target_id
        while cur != start_id:
            cur = prev.get(cur)
            if cur is None:
                break
            path.insert(0, cur)
        return path
