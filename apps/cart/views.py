from django.shortcuts import render
from django.views import View
from django.http import JsonResponse
from django.contrib.auth.decorators import login_required
from django.utils.decorators import method_decorator
from django_redis import get_redis_connection

from apps.goods.models import GoodsSKU


# Create your views here.
class CartAddView(View):
    def post(self, request):
        """购物车记录添加"""
        user = request.user
        if not user.is_authenticated:
            return JsonResponse({"res": 0, "errmsg": "请先登录"})

        sku_id = request.POST.get("sku_id")
        count = request.POST.get("count")

        # 数据校验
        if not all([sku_id, count]):
            return JsonResponse({"res": 1, "errmsg": "数据不完整"})
        try:
            count = int(count)
        except ValueError as e:
            return JsonResponse({"res": 2, "errmsg": "商品数目出错"})
        try:
            sku = GoodsSKU.objects.get(id=sku_id)
        except GoodsSKU.DoesNotExist:
            return JsonResponse({"res": 3, "errmsg": "商品不存在"})

        # 业务处理：添加购物车记录
        conn = get_redis_connection("default")
        cart_key = f"cart_{user.id}"
        # 现场时获取sku_id的值 -> hget cart_key filed
        # 如果sku_id在hash中不存在，hget返回None
        cart_count = conn.hget(cart_key, sku_id)
        if cart_count:
            # 累加购物车中商品的数目
            count += int(cart_count)
        # 校验商品的库存
        if count > sku.stock:
            return JsonResponse({"res": 4, "errmsg": "商品库存不足"})
        # 设置hash中sku_id对应的值
        # hset -> 如果sku_id已经存在，更新数据，如果sku_id不存在，添加数据
        conn.hset(cart_key, sku_id, count)
        cart_count = conn.hlen(cart_key)
        return JsonResponse({"res": 5, "message": "添加成功", "cart_count": cart_count})


class CartInfoView(View):
    """购物车页面显示"""
    @method_decorator(login_required)
    def get(self, request):
        user = request.user

        conn = get_redis_connection("default")
        cart_key = f"cart_{user.id}"
        # {"sku_id": count}
        cart_dict = conn.hgetall(cart_key)
        skus = []
        total_count = 0
        total_price = 0
        for sku_id, count in cart_dict.items():
            sku = GoodsSKU.objects.get(id=sku_id)
            count = int(count)
            amount = sku.price * count
            # 动态给sku对象增加属性，保存商品的小计和商品的数量
            sku.amount = amount
            sku.count = count
            skus.append(sku)
            # 累加计算商品的总数目和总价格
            total_count += count
            total_price += amount
        context = {"total_count": total_count, "total_price": total_price, "skus": skus}
        return render(request, "cart.html", context)


class CartUpdateView(View):
    """购物车记录更新"""
    def post(self, request):
        user = request.user
        if not user.is_authenticated:
            return JsonResponse({"res": 0, "errmsg": "请先登录"})

        sku_id = request.POST.get("sku_id")
        count = request.POST.get("count")

        # 数据校验
        if not all([sku_id, count]):
            return JsonResponse({"res": 1, "errmsg": "数据不完整"})
        try:
            count = int(count)
        except ValueError as e:
            return JsonResponse({"res": 2, "errmsg": "商品数目出错"})
        try:
            sku = GoodsSKU.objects.get(id=sku_id)
        except GoodsSKU.DoesNotExist:
            return JsonResponse({"res": 3, "errmsg": "商品不存在"})

        # 业务处理：添加购物车记录
        conn = get_redis_connection("default")
        cart_key = f"cart_{user.id}"

        # 校验商品的库存
        if count > sku.stock:
            return JsonResponse({"res": 4, "errmsg": "商品库存不足"})
        # 设置hash中sku_id对应的值
        # hset -> 如果sku_id已经存在，更新数据，如果sku_id不存在，添加数据
        conn.hset(cart_key, sku_id, count)

        vals = conn.hvals(cart_key)
        total_count = 0
        for val in vals:
            total_count += int(val)
        return JsonResponse({"res": 5, "message": "添加成功", "total_count": total_count})


class CartDeleteView(View):
    """购物车记录的删除"""
    def post(self, request):
        user = request.user
        if not user.is_authenticated:
            return JsonResponse({"res": 0, "errmsg": "请先登录"})

        sku_id = request.POST.get("sku_id")

        # 数据校验
        if not sku_id:
            return JsonResponse({"res": 1, "errmsg": "无效的商品id"})

        try:
            sku = GoodsSKU.objects.get(id=sku_id)
        except GoodsSKU.DoesNotExist:
            return JsonResponse({"res": 2, "errmsg": "商品不存在"})

        # 业务处理：添加购物车记录
        conn = get_redis_connection("default")
        cart_key = f"cart_{user.id}"
        # 删除 hdel
        conn.hdel(cart_key, sku_id)

        vals = conn.hvals(cart_key)
        total_count = 0
        for val in vals:
            total_count += int(val)
        return JsonResponse({"res": 3, "message": "删除成功", "total_count": total_count})
