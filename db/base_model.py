from django.db import models


class BaseModel(models.Model):
    """Abstract Base Model"""
    create_time = models.DateTimeField(verbose_name="创建时间", auto_now_add=True)
    update_time = models.DateTimeField(verbose_name="更新时间", auto_now=True)
    is_delete = models.BooleanField(verbose_name="删除标记", default=False)

    class Meta:
        abstract = True
