from django.urls import path
from apps.goods.views import IndexView, DetailView, ListView


urlpatterns = [
    path("", IndexView.as_view(), name="index"),
    path("index", IndexView.as_view(), name="index"),
    path("goods/<int:goods_id>", DetailView.as_view(), name="detail"),
    path("list/<int:type_id>", ListView.as_view(), name="list"),
    path("list/<int:type_id>/<int:page>", ListView.as_view(), name="list"),
]
