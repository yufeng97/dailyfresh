from django.urls import path
from django.contrib.auth.decorators import login_required
from apps.user.views import RegisterView, ActiveView, LoginView, UserInfoView, UserOrderView, AddressView, LogoutView, \
    UpdateAddressView, SetDefaultAddressView

urlpatterns = [
    path("register", RegisterView.as_view(), name="register"),
    path("active/<path:token>", ActiveView.as_view(), name="active"),
    path("login", LoginView.as_view(), name="login"),
    path("logout", LogoutView.as_view(), name="logout"),
    # path("", login_required(UserInfoView.as_view()), name="user"),
    # path("order", login_required(UserOrderView.as_view()), name="order"),
    # path("address", login_required(AddressView.as_view()), name="address"),
    path("", UserInfoView.as_view(), name="user"),
    path("order/<int:page>", UserOrderView.as_view(), name="order"),
    path("order", UserOrderView.as_view(), name="order"),
    path("address", AddressView.as_view(), name="address"),
    path("address/update", UpdateAddressView.as_view(), name="update_address"),
    path("address/set_default", SetDefaultAddressView.as_view(), name="set_default_address"),
]
