import os.path
from django.core.files.storage import Storage
from django.conf import settings
from fdfs_client.client import Fdfs_client, get_tracker_conf


class FDFSStorage(Storage):
    """fast dfs文件存储类"""
    def __init__(self, client_conf=None, base_url=None):
        if client_conf is None:
            client_conf = settings.FDFS_CLIENT_CONF
        self.client_conf = client_conf
        if base_url is None:
            base_url = settings.FDFS_URL
        self.base_url = base_url

    def _open(self, name, mode="rb"):
        pass

    def _save(self, name, content):
        # 读取tracker config
        # 创建一个Fdfs client
        tracker = get_tracker_conf(self.client_conf)
        client = Fdfs_client(tracker)
        # 上传文件到fast dfs系统中
        ext = os.path.splitext(name)[-1][1:]
        res = client.upload_by_buffer(content.read(), file_ext_name=ext)
        # dict
        # {
        #     'Group name': group_name,
        #     'Remote file_id': remote_file_id,
        #     'Status': 'Upload successed.',
        #     'Local file name': '',
        #     'Uploaded size': upload_size,
        #     'Storage IP': storage_ip
        # }
        if res.get("Status") != "Upload successed.":
            # 上传失败
            raise Exception("上传文件到fast dfs失败")
        # 获取返回的文件ID
        filename = res.get("Remote file_id")
        return filename.decode()

    def exists(self, name):
        """文件是存储在 fastdfs文件系统中的,对于django来说即不存在"""
        return False

    def url(self, name):
        return f"{self.base_url}{name}"
