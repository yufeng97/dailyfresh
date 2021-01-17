# dailyfresh 天天生鲜 django3.0版本

本项目替换原项目框架django1.8为最新版的django3.1，该项目包含了实际开发中的电商项目中大部分的功能开发和知识点实践， 是一个非常不错的django学习项目。

关键词：django3 celery fdfs fdht haystack whoosh redis nginx

## 主要技术栈
* celery分别负责用户注册异步发送邮件以及不同用户登陆系统动态生成首页
* fdfs+nginx：存储网站静态文件，实现项目和资源分离，达到分布式效果 
* haystack+whoosh+jieba：全文检索框架，修改底层haystack库使之对中文搜索更加友好
* redis：作为django缓存和session存储后端，提升网站性能，给予用户更好体验
