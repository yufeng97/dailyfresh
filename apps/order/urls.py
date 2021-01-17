from django.urls import path
from apps.order.views import OrderPlaceView, OrderCommitView, OrderPayView, OrderCheckView, CommentView

urlpatterns = [
    path("place", OrderPlaceView.as_view(), name="place"),
    path("commit", OrderCommitView.as_view(), name="commit"),
    path("pay", OrderPayView.as_view(), name="pay"),
    path("check", OrderCheckView.as_view(), name="check"),
    path("comment/<int:order_id>", CommentView.as_view(), name="comment"),
]
