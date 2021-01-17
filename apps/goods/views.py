from django.shortcuts import render, redirect, reverse
from django.views import View
from django.core.cache import cache
from django.core.paginator import Paginator
from django_redis import get_redis_connection
from apps.goods.models import GoodsType, IndexGoodsBanner, IndexPromotionBanner, IndexTypeGoodsBanner, GoodsSKU
from apps.order.models import OrderGoods


# Create your views here.
class IndexView(View):
    def get(self, request):
        """首页"""
        # 尝试从缓存中获取数据
        context = cache.get("index_page_data")

        if context is None:
            # 缓存中没有数据
            print("设置缓存")
            # 获取商品的种类信息
            types = GoodsType.objects.all()
            # 获取首页轮播商品信息
            goods_banners = IndexGoodsBanner.objects.all().order_by("index")
            # 获取首页促销活动信息
            promotion_banners = IndexPromotionBanner.objects.all().order_by("index")

            # 获取首页分类商品展示信息
            for type_ in types:
                # 获取type种类首页分类商品的图片展示信息
                image_banners = IndexTypeGoodsBanner.objects.filter(type=type_, display_type=1).order_by("index")
                # 获取type种类首页分类商品的文字展示信息
                title_banners = IndexTypeGoodsBanner.objects.filter(type=type_, display_type=0).order_by("index")
                type_.image_banners = image_banners
                type_.title_banners = title_banners

            context = {
                "types": types,
                "goods_banners": goods_banners,
                "promotion_banners": promotion_banners,
            }

            # 设置缓存 (key, val ,expired_time)
            cache.set("index_page_data", context, 3600)

        # 获取用户购物车商品数目
        user = request.user
        cart_count = 0
        if user.is_authenticated:
            conn = get_redis_connection("default")
            cart_key = f'cart_{user.id}'
            cart_count = conn.hlen(cart_key)

        # 组织模板上下文
        context.update(cart_count=cart_count)

        return render(request, "index.html", context)


# /goods/item_id
class DetailView(View):
    def get(self, request, goods_id):
        try:
            sku = GoodsSKU.objects.get(id=goods_id)
        except GoodsSKU.DoesNotExist:
            return redirect(reverse("goods:index"))
        # 获取商品的分类信息
        types = GoodsType.objects.all()
        # 获取商品的评论信息
        sku_orders = OrderGoods.objects.filter(sku=sku).exclude(comment='')
        # 获取新品信息
        new_skus = GoodsSKU.objects.filter(type=sku.type).order_by('-create_time')[:2]
        # 获取同一个SPU的其他规格商品
        same_spu_skus = GoodsSKU.objects.filter(goods=sku.goods).exclude(id=goods_id)

        # 获取用户购物车中闪频的数目
        user = request.user
        cart_count = 0
        if user.is_authenticated:
            conn = get_redis_connection("default")
            cart_key = f'cart_{user.id}'
            cart_count = conn.hlen(cart_key)

            # 添加历史浏览记录
            conn = get_redis_connection("default")
            history_key = f"history_{user.id}"
            # 移除列表中的goods_id
            conn.lrem(history_key, -1, goods_id)
            # 把 goods_id插入到列表的左侧
            conn.lpush(history_key, goods_id)
            # 只保存用户最新浏览的5条记录
            conn.ltrim(history_key, 0, 4)

        context = {
            "sku": sku,
            'types': types,
            "new_skus":  new_skus,
            "sku_orders": sku_orders,
            "cart_count": cart_count,
            "same_spu_skus": same_spu_skus,
        }
        return render(request, "detail.html", context)


# 种类id 页码 排序方式
# restful api -> 请求一种资源
# /list?type_id=种类id&page页码&sort=排序方式
# /list/种类id/页码/排序方式
# /list/种类id/页码?sort=排序方式
class ListView(View):
    """列表页"""
    def get(self, request, type_id, page=1):
        # 先获取种类信息
        try:
            type = GoodsType.objects.get(id=type_id)
        except GoodsType.DoesNotExist:
            return redirect(reverse("goods:index"))
        # 获取分类商品信息
        types = GoodsType.objects.all()

        # 获取排序方式
        # sort=default 按照id
        # sort=price  按照价格
        # sort=hot   按照销量
        sort = request.GET.get("sort")
        if sort == "price":
            skus = GoodsSKU.objects.filter(type=type_id).order_by("price")
        elif sort == "hot":
            skus = GoodsSKU.objects.filter(type=type_id).order_by("-sales")
        else:
            sort = "default"
            skus = GoodsSKU.objects.filter(type=type_id).order_by("-id")

        # 对数据进行分页
        paginator = Paginator(skus, 3)
        # 获取第page页的内容
        try:
            page = int(page)
        except ValueError:
            page = 1
        if page > paginator.num_pages:
            page = 1
        # 获取第page页的实例对象
        skus_page = paginator.page(page)

        # 进行页码的控制，页面上最多显示5个页码
        # 1.总页数小于5页，页面上显示所有页码
        # 2.如果当前页是前3页，显示1-5页
        # 3.如果当前页是后3页，显示后5页
        # 4.其他情况，显示当前页的前2页，当前页，后2页
        num_pages = paginator.num_pages
        if num_pages < 5:
            pages = range(1, num_pages + 1)
        elif page <= 3:
            pages = range(1, 6)
        elif num_pages - page <= 2:
            pages = range(num_pages - 4, num_pages + 1)
        else:
            pages = range(page - 2, page + 3)

        # 获取新品信息
        new_skus = GoodsSKU.objects.filter(type=type).order_by('-create_time')[:2]

        # 获取用户购物车中闪频的数目
        user = request.user
        cart_count = 0
        if user.is_authenticated:
            conn = get_redis_connection("default")
            cart_key = f'cart_{user.id}'
            cart_count = conn.hlen(cart_key)

        context = {
            'type': type,
            'types': types,
            "new_skus": new_skus,
            'skus_page': skus_page,
            "cart_count": cart_count,
            'sort': sort,
            "pages": pages,
        }
        return render(request, "list.html", context)
