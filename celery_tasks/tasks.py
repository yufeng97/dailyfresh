import time
from django.conf import settings
from django.core.mail import send_mail
from celery import Celery

from django.template import loader, RequestContext
from apps.goods.models import GoodsType, IndexGoodsBanner, IndexPromotionBanner, IndexTypeGoodsBanner


import os
import django
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'dailyfresh.settings')
django.setup()


app = Celery("celery_tasks.tasks", broker=settings.CELERY_BROKER_URL,)


@app.task
def send_register_active_email(to_email, username, token):
    """发送激活邮件"""
    subject = "天天生鲜欢迎信息"
    message = ""
    html_message = f"""<h2>{username}，欢迎您成为天天生鲜注册会员</h2>
                            请点击下面连接激活您的账户<br/>
                            <a href="http://127.0.0.1:8000/user/active/{token}">
                                http://127.0.0.1:8000/user/active/{token}
                            </a>"""
    sender = settings.EMAIL_FROM
    receiver = [to_email]
    send_mail(subject, message, sender, receiver, html_message=html_message)
    time.sleep(5)


@app.task
def generate_static_index_html():
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

    # 获取用户购物车商品数目
    cart_count = 0

    # 组织模板上下文
    context = {
        "types": types,
        "goods_banners": goods_banners,
        "promotion_banners": promotion_banners,
        "cart_count": cart_count,
    }
    # 使用模板
    # 1.加载模板文件
    temp = loader.get_template("static_index.html")

    # # 2.定义模板上下文
    # context = RequestContext(request, context)

    # 3.渲染模板
    static_index_html = temp.render(context)

    save_path = os.path.join(settings.BASE_DIR, "static/index.html")
    with open(save_path, "w") as f:
        f.write(static_index_html)
