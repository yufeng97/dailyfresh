import os.path
from datetime import datetime
from django.shortcuts import render, redirect, reverse
from django.views import View
from django.db import transaction
from django.contrib.auth.decorators import login_required
from django.utils.decorators import method_decorator
from django.http import JsonResponse
from django.conf import settings
from django_redis import get_redis_connection
from alipay import AliPay
from alipay.utils import AliPayConfig

from apps.goods.models import GoodsSKU
from apps.user.models import Address
from apps.order.models import OrderInfo, OrderGoods


# Create your views here.
class OrderPlaceView(View):
    """提交订单页面"""
    @method_decorator(login_required)
    def post(self, request):
        user = request.user

        sku_ids = request.POST.getlist("sku_ids")
        # 校验参数
        if not sku_ids:
            # 跳转到购物车页面
            return redirect(reverse("cart:show"))

        conn = get_redis_connection("default")
        cart_key = f"cart_{user.id}"

        skus = []
        total_count = 0
        total_price = 0
        # 遍历sku_ids用户要购买的商品的信息
        for sku_id in sku_ids:
            sku = GoodsSKU.objects.get(id=sku_id)
            count = conn.hget(cart_key, sku_id)
            count = int(count)
            amount = sku.price * count
            #  动态给sku增加属性count，保存购买商品的数量
            sku.count = count
            sku.amount = amount
            skus.append(sku)
            total_count += count
            total_price += amount
        # 运费：实际开发的时候，属于一个子系统
        transit_price = 10  # 写死
        # 实付款
        total_pay = total_price + transit_price
        # 获取用户的收件地址
        addrs = Address.objects.filter(user=user.id)
        sku_ids = ','.join(sku_ids)
        context = {
            "skus": skus,
            "total_count": total_count,
            "total_price": total_price,
            "total_pay": total_pay,
            "transit_price": transit_price,
            "addrs": addrs,
            "sku_ids": sku_ids,
        }
        return render(request, "place_order.html", context)


class OrderCommitView1(View):
    """订单创建"""
    @transaction.atomic
    def post(self, request):
        user = request.user
        if not user.is_authenticated:
            return JsonResponse({"res": 0, "errmsg": "请先登录"})

        addr_id = request.POST.get("addr_id")
        pay_method = request.POST.get("pay_method")
        sku_ids = request.POST.get("sku_ids")

        # 数据校验
        if not all([addr_id, pay_method, sku_ids]):
            return JsonResponse({"res": 1, "errmsg": "数据不完整"})

        if pay_method not in OrderInfo.PAY_METHODS:
            return JsonResponse({"res": 2, "errmsg": "非法的支付方式"})
        try:
            addr = Address.objects.get(id=addr_id)
        except Address.DoesNotExist:
            return JsonResponse({"res": 3, "errmsg": "地址非法"})

        # 设置事务保存点
        save_id = transaction.savepoint()
        try:
            # todo: 创建订单核心业务
            # 组织参数
            # 订单id: 年月日时分秒+用户id
            order_id = datetime.now().strftime("%Y%m%d%H%M%S") + str(user.id)
            # 运费
            transit_price = 10
            # 总数目和总金额
            total_count = 0
            total_price = 0
            # 向df_order_info表中添加一条记录
            order = OrderInfo.objects.create(order_id=order_id,
                                             user=user,
                                             addr=addr,
                                             pay_method=pay_method,
                                             total_count=total_count,
                                             total_price=total_price,
                                             transit_price=transit_price)

            conn = get_redis_connection("default")
            cart_key = f"cart_{user.id}"
            sku_ids = sku_ids.split(",")
            for sku_id in sku_ids:
                try:
                    # 悲观锁：select * from df_goods_sku where id=sku_id for update; for update 为加琐操作
                    sku = GoodsSKU.objects.select_for_update().get(id=sku_id)
                except GoodsSKU.DoesNotExist:
                    transaction.savepoint_rollback(save_id)
                    return JsonResponse({"res": 4, "errmsg": "商品不存在"})

                count = conn.hget(cart_key, sku_id)

                # todo: 判断商品的库存
                if int(count) > sku.stock:
                    transaction.savepoint_rollback(save_id)
                    return JsonResponse({"res": 6, "errmsg": "商品库存不足"})

                # 向df_order_goods表中添加一条记录
                OrderGoods.objects.create(order_id=order_id,
                                          sku=sku,
                                          count=count,
                                          price=sku.price)
                # 更新商品的库存和销量
                sku.stock -= int(count)
                sku.sales += int(count)
                sku.save()
                # 累加计算商品订单的总数量和总价格
                amount = int(count) * sku.price
                total_count += int(count)
                total_price += amount
            # 更新订单信息表中的商品的总数量和总价格
            order.total_count = total_count
            order.total_price = total_price
            order.save()

        except Exception as e:
            transaction.savepoint_rollback(save_id)
            return JsonResponse({"res": 7, "errmsg": "下单失败"})
        # 提交事务
        transaction.savepoint_commit(save_id)
        # 清除用户购物车中对应的记录
        conn.hdel(cart_key, *sku_ids)

        return JsonResponse({"res": 5, "message": "创建成功"})


class OrderCommitView(View):
    """订单创建"""
    @transaction.atomic
    def post(self, request):
        user = request.user
        if not user.is_authenticated:
            return JsonResponse({"res": 0, "errmsg": "请先登录"})

        addr_id = request.POST.get("addr_id")
        pay_method = request.POST.get("pay_method")
        sku_ids = request.POST.get("sku_ids")

        # 数据校验
        if not all([addr_id, pay_method, sku_ids]):
            return JsonResponse({"res": 1, "errmsg": "数据不完整"})

        if pay_method not in OrderInfo.PAY_METHODS:
            return JsonResponse({"res": 2, "errmsg": "非法的支付方式"})
        try:
            addr = Address.objects.get(id=addr_id)
        except Address.DoesNotExist:
            return JsonResponse({"res": 3, "errmsg": "地址非法"})

        # 设置事务保存点
        save_id = transaction.savepoint()
        try:
            # todo: 创建订单核心业务
            # 组织参数
            # 订单id: 年月日时分秒+用户id
            order_id = datetime.now().strftime("%Y%m%d%H%M%S") + str(user.id)
            # 运费
            transit_price = 10
            # 总数目和总金额
            total_count = 0
            total_price = 0
            # 向df_order_info表中添加一条记录
            order = OrderInfo.objects.create(order_id=order_id,
                                             user=user,
                                             addr=addr,
                                             pay_method=pay_method,
                                             total_count=total_count,
                                             total_price=total_price,
                                             transit_price=transit_price)

            conn = get_redis_connection("default")
            cart_key = f"cart_{user.id}"
            sku_ids = sku_ids.split(",")
            for sku_id in sku_ids:
                for i in range(3):
                    try:
                        # 悲观锁：select * from df_goods_sku where id=sku_id for update; for update 为加琐操作
                        sku = GoodsSKU.objects.get(id=sku_id)
                    except GoodsSKU.DoesNotExist:
                        transaction.savepoint_rollback(save_id)
                        return JsonResponse({"res": 4, "errmsg": "商品不存在"})

                    count = conn.hget(cart_key, sku_id)

                    # todo: 判断商品的库存
                    if int(count) > sku.stock:
                        transaction.savepoint_rollback(save_id)
                        return JsonResponse({"res": 6, "errmsg": "商品库存不足"})

                    # 更新商品的库存和销量
                    origin_stock = sku.stock
                    new_stock = origin_stock - int(count)
                    new_sales = sku.sales + int(count)

                    # update df_goods_sku set stock=new_stock, sales=new_sales
                    # where id=sku_id and stock=origin_stock
                    # 返回受影响的行数
                    res = GoodsSKU.objects.filter(id=sku_id, stock=origin_stock).update(stock=new_stock, sales=new_sales)
                    if res == 0:
                        import time
                        time.sleep(1)
                        if i == 2:
                            # 尝试三次都失败返回下单失败
                            transaction.rollback(save_id)
                            return JsonResponse({"res": 7, "errmsg": "下单失败2"})
                        continue

                    # 向df_order_goods表中添加一条记录
                    OrderGoods.objects.create(order_id=order_id,
                                              sku=sku,
                                              count=count,
                                              price=sku.price)
                    # 累加计算商品订单的总数量和总价格
                    amount = int(count) * sku.price
                    total_count += int(count)
                    total_price += amount
                    break

            # 更新订单信息表中的商品的总数量和总价格
            order.total_count = total_count
            order.total_price = total_price
            order.save()

        except Exception as e:
            transaction.savepoint_rollback(save_id)
            return JsonResponse({"res": 7, "errmsg": "下单失败"})
        # 提交事务
        transaction.savepoint_commit(save_id)
        # 清除用户购物车中对应的记录
        conn.hdel(cart_key, *sku_ids)

        return JsonResponse({"res": 5, "message": "创建成功"})


# ajax post
# params: order_id
class OrderPayView(View):
    """订单支付"""
    def post(self, request):
        # 用户是否登录
        user = request.user
        if not user.is_authenticated:
            return JsonResponse({"res": 0, "errmsg": "用户未登录 "})
        # 接收参数
        order_id = request.POST.get("order_id")
        # 校验参数
        if not order_id:
            return JsonResponse({"res": 1, "errmsg": "无效的订单id"})
        try:
            order = OrderInfo.objects.get(order_id=order_id,
                                          user=user,
                                          pay_method=3,
                                          order_status=1)
        except OrderInfo.DoesNotExist:
            return JsonResponse({"res": 2, "errmsg": "订单错误"})

        # 业务处理：使用python sdk调用支付宝的支付接口
        # alipay初始化
        app_private_key_string = open("apps/order/app_private_key.pem").read()
        alipay_public_key_string = open("apps/order/alipay_public_key.pem").read()

        alipay = AliPay(
            appid="2021000116694743",
            app_notify_url=None,  # 默认回调url
            app_private_key_string=app_private_key_string,
            # 支付宝的公钥，验证支付宝回传消息使用，不是你自己的公钥,
            alipay_public_key_string=alipay_public_key_string,
            sign_type="RSA2",  # RSA 或者 RSA2
            debug=True,  # 默认False
            # config=AliPayConfig(timeout=15)  # 可选, 请求超时时间
        )

        # 如果你是 Python 3的用户，使用默认的字符串即可
        subject = f"天天生鲜{order_id}"

        # 电脑网站支付，需要跳转到https://openapi.alipay.com/gateway.do? + order_string
        total_pay = order.total_price + order.transit_price
        order_string = alipay.api_alipay_trade_page_pay(
            out_trade_no=order_id,
            total_amount=str(total_pay),
            subject=subject,
            return_url=None,
            notify_url=None  # 可选, 不填则使用默认notify url
        )

        # 返回应答
        pay_url = f"https://openapi.alipaydev.com/gateway.do?{order_string}"
        return JsonResponse({"res": 3, "pay_url": pay_url})


# ajax post
# params order_id
class OrderCheckView(View):
    """查询支付交易结果"""
    def post(self, request):
        # 用户是否登录
        user = request.user
        if not user.is_authenticated:
            return JsonResponse({"res": 0, "errmsg": "用户未登录 "})
        # 接收参数
        order_id = request.POST.get("order_id")
        # 校验参数
        if not order_id:
            return JsonResponse({"res": 1, "errmsg": "无效的订单id"})
        try:
            order = OrderInfo.objects.get(order_id=order_id,
                                          user=user,
                                          pay_method=3,
                                          order_status=1)
        except OrderInfo.DoesNotExist:
            return JsonResponse({"res": 2, "errmsg": "订单错误"})

        # 业务处理：使用python sdk调用支付宝的支付接口
        # alipay初始化
        app_private_key_string = open("apps/order/app_private_key.pem").read()
        alipay_public_key_string = open("apps/order/alipay_public_key.pem").read()

        alipay = AliPay(
            appid="2021000116694743",
            app_notify_url=None,  # 默认回调url
            app_private_key_string=app_private_key_string,
            # 支付宝的公钥，验证支付宝回传消息使用，不是你自己的公钥,
            alipay_public_key_string=alipay_public_key_string,
            sign_type="RSA2",  # RSA 或者 RSA2
            debug=True,  # 默认False
            # config=AliPayConfig(timeout=15)  # 可选, 请求超时时间
        )

        # response = {
        #     "trade_no": "2017032121001004070200176844",   # 支付宝交易号
        #     "code": "10000",                              # 接口调用是否成功
        #     "invoice_amount": "20.00",
        #     "open_id": "20880072506750308812798160715407",
        #     "fund_bill_list": [
        #         {
        #             "amount": "20.00",
        #             "fund_channel": "ALIPAYACCOUNT"
        #         }
        #     ],
        #     "buyer_logon_id": "csq***@sandbox.com",
        #     "send_pay_date": "2017-03-21 13:29:17",
        #     "receipt_amount": "20.00",
        #     "out_trade_no": "out_trade_no15",
        #     "buyer_pay_amount": "20.00",
        #     "buyer_user_id": "2088102169481075",
        #     "msg": "Success",
        #     "point_amount": "0.00",
        #     "trade_status": "TRADE_SUCCESS",               # 支付结果
        #     "total_amount": "20.00"
        # }
        while True:
            # 调用支付宝的交易查询接口
            response = alipay.api_alipay_trade_query(out_trade_no=order_id)
            code = response.get("code")
            if code == '10000' and response.get("trade_status") == "TRADE_SUCCESS":
                # 支付成功
                trade_no = response.get("trade_no")
                order.trade_no = trade_no
                order.order_status = 4  # 待评价
                order.save()
                return JsonResponse({"res": 3, "message": "支付成功"})
            elif code == '40004' or (code == "10000" and response.get("trade_status") == "WAIT_BUYER_PAY"):
                # 等待买家付款
                import time
                time.sleep(2)
                continue
            else:
                # 支付出错
                return JsonResponse({"res": 4, "errmsg": "支付失败"})


class CommentView(View):
    """订单评论"""
    @method_decorator(login_required)
    def get(self, request, order_id):
        # 用户是否登录
        user = request.user

        # 校验参数
        if not order_id:
            return redirect(reverse("user:order"))
        try:
            order = OrderInfo.objects.get(order_id=order_id, user=user)
        except OrderInfo.DoesNotExist:
            return redirect(reverse("user:order"))

        # 根据订单的状态获取订单的状态标题
        order.status_name = OrderInfo.ORDER_STATUS[order.order_status]

        # 获取订单商品信息
        order_skus = OrderGoods.objects.filter(order_id=order.order_id)
        for order_sku in order_skus:
            amount = order_sku.count * order_sku.price
            order_sku.amount = amount
        order.order_skus = order_skus

        return render(request, "order_comment.html", {"order": order})

    @method_decorator(login_required)
    def post(self, request, order_id):
        # 用户是否登录
        user = request.user

        # 校验参数
        if not order_id:
            return redirect(reverse("user:order"))
        try:
            order = OrderInfo.objects.get(order_id=order_id, user=user)
        except OrderInfo.DoesNotExist:
            return redirect(reverse("user:order"))
        # 获取评论
        total_count = request.POST.get("total_count")
        total_count = int(total_count)

        for i in range(1, total_count + 1):
            sku_id = request.POST.get(f"sku_{i}")
            content = request.POST.get(f"content_{i}")
            try:
                order_goods = OrderGoods.objects.get(order=order, sku_id=sku_id)
            except OrderGoods.DoesNotExist:
                continue
            order_goods.comment = content
            order_goods.save()

        order.order_status = 5
        order.save()

        return redirect(reverse("user:order", kwargs={"page": 1}))
