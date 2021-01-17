import re

from django.contrib.auth import authenticate, login, logout
from django.contrib.auth.decorators import login_required
from django.utils.decorators import method_decorator
from django.shortcuts import render, redirect, reverse
from django.views.generic import View
from django.core.mail import send_mail
from django.core.paginator import Paginator
from django.conf import settings
from django.http import HttpResponse, JsonResponse

from django_redis import get_redis_connection
from itsdangerous import TimedJSONWebSignatureSerializer as Serializer
from itsdangerous import SignatureExpired

from apps.user.models import User, Address
from apps.goods.models import GoodsSKU
from apps.order.models import OrderInfo, OrderGoods
from celery_tasks.tasks import send_register_active_email
from utils.mixin import LoginRequiredMixin


# Create your views here.
class RegisterView(View):
    """注册"""
    def get(self, request):
        # 显示注册页面
        return render(request, "register.html")

    def post(self, request):
        # 进行注册处理
        # 接收数据
        email = request.POST.get("email")
        username = request.POST.get("user_name")
        password = request.POST.get("pwd")
        allow = request.POST.get("allow")

        # 进行数据校验
        if not all([username, password, email]):
            return render(request, "register.html", {"errmsg": "数据不完整"})
        if not re.match(r'^[\w-]+(\.[\w-]+)*@\w+(\.\w+)+$', email):
            return render(request, "register.html", {"errmsg": "邮箱格式不正确"})
        if allow != "on":
            return render(request, "register.html", {"errmsg": "请同意协议"})

        # 校验用户名是否重复
        try:
            user = User.objects.get(username=username)
        except User.DoesNotExist:
            user = None
        if user:
            return render(request, "register.html", {"errmsg": "用户名已存在"})

        # 进行业务处理
        user = User.objects.create_user(username, email, password)
        user.is_active = 0
        user.save()

        # 发送激活邮件，包含激活链接：http://127.0.0.1:8000/user/active/token
        # 激活链接种需要包含用户的身份信息，并且要把身份信息进行加密
        serializer = Serializer(settings.SECRET_KEY, 3600)
        info = {"confirm": user.id}
        token = serializer.dumps(info)  # 解密token得到的类型是bytes
        token = token.decode("utf8")

        # 发邮件
        send_register_active_email.delay(email, username, token)

        # 返回应答，跳转到首页
        return redirect(reverse("goods:index"))


class ActiveView(View):
    """用户激活"""
    def get(self, request, token):
        serializer = Serializer(settings.SECRET_KEY, 3600)
        try:
            info = serializer.loads(token)
            user_id = info["confirm"]
            user = User.objects.get(id=user_id)
            user.is_active = 1
            user.save()

            return redirect(reverse("user:login"))
        except SignatureExpired as e:
            # 激活链接已过期
            return HttpResponse("激活链接已过期")


class LoginView(View):
    """登录"""
    def get(self, request):
        if "username" in request.COOKIES:
            username = request.COOKIES.get("username")
            checked = "checked"
        else:
            username = ""
            checked = ""

        return render(request, "login.html", {"username": username, "checked": checked})

    def post(self, request):
        """登录校验"""
        # 接收数据
        username = request.POST.get("username")
        password = request.POST.get("pwd")

        # 校验数据
        if not all([username, password]):
            return render(request, "login.html", {"errmsg": "数据不完整"})

        # 业务处理
        user = authenticate(username=username, password=password)
        if user is not None:
            if user.is_active:
                # 记录用户的登陆状态
                login(request, user)

                # 地址：http://127.0.0.1:8000/user/login?next=/user/
                # 获取登陆后要跳转的地址
                # 如果没有要跳转的地址则值为默认值
                next_url = request.GET.get("next", reverse("goods:index"))
                # 跳转到首页
                response = redirect(next_url)

                # 是否记住用户名
                remember = request.POST.get("remember")
                if remember == "on":
                    response.set_cookie("username", username, max_age=7*24*3600)
                else:
                    response.delete_cookie("username")

                return response
            else:
                return render(request, "login.html", {"errmsg": "账户未激活"})
        else:
            return render(request, "login.html", {"errmsg": "用户名或密码错误"})
        # 返回应答


class LogoutView(View):
    def get(self, request):
        logout(request)
        return redirect(reverse("goods:index"))


# class UserInfoView(LoginRequiredMixin, View):
#     """用户中心信息页"""
#     def get(self, request):
#         return render(request, "user_center_info.html", {"page": "user"})
#
#
# class UserOrderView(LoginRequiredMixin, View):
#     """用户中心订单页"""
#     def get(self, request):
#         return render(request, "user_center_order.html", {"page": "order"})
#
#
# class AddressView(LoginRequiredMixin, View):
#     """用户中心地址页"""
#     def get(self, request):
#         return render(request, "user_center_site.html", {"page": "address"})


class UserInfoView(View):
    """用户中心信息页"""
    @method_decorator(login_required)
    def get(self, request):
        # 获取用户的个人信息
        user = request.user
        address = Address.objects.get_default_address(user)

        # 获取用户的历史浏览记录
        con = get_redis_connection("default")
        history_key = f"history_{user.id}"
        # 获取用户最新浏览的五个商品id
        sku_ids = con.lrange(history_key, 0, 4)
        # 从数据中查询用户浏览的商品信息
        # goods_li = GoodsSKU.objects.filter(id__in=sku_ids)
        # goods_res = []
        # for sku in sku_ids:
        #     for goods in goods_li:
        #         if sku == goods.id:
        #             goods_res.append(goods)
        # goods_li = goods_res

        goods_li = []
        for sku in sku_ids:
            goods = GoodsSKU.objects.get(id=sku)
            goods_li.append(goods)

        context = {"page": "user",
                   "address": address,
                   "goods_li": goods_li}
        # django框架会自动把request.user也传给模板文件
        return render(request, "user_center_info.html", context)


class UserOrderView(View):
    """用户中心订单页"""
    @method_decorator(login_required)
    def get(self, request, page=1):
        # 获取用户的订单信息
        user = request.user
        orders = OrderInfo.objects.filter(user=user).order_by("-create_time")

        for order in orders:
            # 查询每个订单中的所有商品
            order_skus = OrderGoods.objects.filter(order_id=order.order_id)
            for sku in order_skus:
                # 计算小计
                amount = sku.count * sku.price
                sku.amount = amount
            # 动态给order增加属性，保存订单商品的信息
            order.order_skus = order_skus
            # 保存订单商品状态的名称
            order.status_name = OrderInfo.ORDER_STATUS[order.order_status]

        # 分页
        paginator = Paginator(orders, 2)
        try:
            page = int(page)
        except ValueError:
            page = 1
        if page > paginator.num_pages:
            page = 1
        # 获取第page页的实例对象
        order_page = paginator.page(page)
        num_pages = paginator.num_pages
        if num_pages < 5:
            pages = range(1, num_pages + 1)
        elif page <= 3:
            pages = range(1, 6)
        elif num_pages - page <= 2:
            pages = range(num_pages - 4, num_pages + 1)
        else:
            pages = range(page - 2, page + 3)

        context = {"order_page": order_page, "pages": pages, "page": "order"}
        return render(request, "user_center_order.html", context)


class AddressView(View):
    """用户中心地址页"""
    @method_decorator(login_required)
    def get(self, request):
        # 获取用户的默认收货地址
        user = request.user
        address = Address.objects.get_default_address(user)
        all_address = Address.objects.filter(user=user)
        context = {
            "page": "address",
            "address": address,
            "all_address": all_address,
        }
        return render(request, "user_center_site.html", context)

    @method_decorator(login_required)
    def post(self, request):
        # 接收数据
        receiver = request.POST.get("receiver")
        addr = request.POST.get("addr")
        zip_code = request.POST.get("zip_code")
        phone = request.POST.get("phone")

        # 数据校验
        if not all([receiver, addr, phone]):
            return render(request, "user_center_site.html", {"errmsg": "数据不完整"})
        # 校验手机号
        if not re.match(r'^1[3|4|5|7|8][0-9]{9}$', phone):
            return render(request, "user_center_site.html", {"errmsg": "手机号格式不正确"})

        # 业务处理：地址添加
        # 如果用户已存在默认收货地址，添加的地址不作为默认收货地址，否则作为默认收货地址
        user = request.user
        address = Address.objects.get_default_address(user)
        if address:
            is_default = False
        else:
            is_default = True
        Address.objects.create(user=user, receiver=receiver, addr=addr,
                               zip_code=zip_code, phone=phone, is_default=is_default)
        # 返回应答，刷新地址页面
        return redirect(reverse("user:address"))


class UpdateAddressView(View):
    def post(self, request):
        user = request.user

        if not user.is_authenticated:
            return JsonResponse({"res": 0, "errmsg": "请先登录"})

        addr_id = request.POST.get("addr_id")
        receiver = request.POST.get("receiver")
        addr = request.POST.get("addr")
        zip_code = request.POST.get("zip_code")
        phone = request.POST.get("phone")

        if not all([addr_id, receiver, addr, phone]):
            return JsonResponse({"res": 1, "errmsg": "数据不完整"})
        # 校验手机号
        if not re.match(r'^1[3|4|5|7|8][0-9]{9}$', phone):
            return JsonResponse({"res": 2, "errmsg": "手机号格式不正确"})

        try:
            address = Address.objects.get(id=addr_id)
        except Address.DoesNotExist:
            return JsonResponse({"res": 3, "errmsg": "地址不存在"})
        address.receiver = receiver
        address.addr = addr
        address.zip_code = zip_code
        address.phone = phone
        address.save()
        return JsonResponse({"res": 4, "message": "更新成功"})


class SetDefaultAddressView(View):
    def post(self, request):
        user = request.user

        if not user.is_authenticated:
            return JsonResponse({"res": 0, "errmsg": "请先登录"})
        addr_id = request.POST.get("addr_id")
        if not addr_id:
            return JsonResponse({"res": 1, "errmsg": "数据不完整"})
        try:
            address = Address.objects.get(id=addr_id)
        except Address.DoesNotExist:
            return JsonResponse({"res": 2, "errmsg": "地址不存在"})
        old_address = Address.objects.get_default_address(user)
        if old_address:
            old_address.is_default = False
            old_address.save()
        address.is_default = True
        address.save()
        return JsonResponse({"res": 3, "message": "更新成功", "old_id": old_address.id})
