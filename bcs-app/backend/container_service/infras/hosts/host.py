# -*- coding: utf-8 -*-
"""
Tencent is pleased to support the open source community by making 蓝鲸智云PaaS平台社区版 (BlueKing PaaS Community
Edition) available.
Copyright (C) 2017-2021 THL A29 Limited, a Tencent company. All rights reserved.
Licensed under the MIT License (the "License"); you may not use this file except in compliance with the License.
You may obtain a copy of the License at

    http://opensource.org/licenses/MIT

Unless required by applicable law or agreed to in writing, software distributed under the License is distributed on
an "AS IS" BASIS, WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied. See the License for the
specific language governing permissions and limitations under the License.
"""
from dataclasses import asdict, dataclass, field
from typing import Dict, List, Tuple

from backend.components import cc, gse, sops
from backend.utils.data_types import make_dataclass_from_dict

from .constants import APPLY_HOST_TEMPLATE_ID, SOPS_BIZ_ID


def get_cc_hosts(cc_app_id: str, username: str, **extra_data) -> List[Dict]:
    """获取主机信息

    :param cc_app_id: 业务 ID
    :param username: 当前请求的用户名
    :param extra_data: 资源池信息，默认为空

    :returns: 返回列表，列表中包含主机的属性信息，比如IP、所属区域、机房、机架等
    """
    resp = cc.get_app_hosts(username, cc_app_id)
    if not resp.get("result"):
        return []
    return resp.get("data") or []


@dataclass
class HostData:
    inner_ip: str
    bk_cloud_id: int = 0

    @property
    def inner_ip_list(self):
        """拆分inner_ip
        因为可能存在多个网卡的主机，需要拆分单独处理
        """
        return self.inner_ip.split(",")


@dataclass
class HostAgentData:
    ip: str = ""
    bk_cloud_id: int = 0
    bk_agent_alive: int = 1


def get_agent_status(username: str, host_list: List[HostData]) -> List[Dict]:
    """查询主机 agent 状态

    :param username: 当前请求的用户名
    :param ip_list: IP 列表，用于查询主机的 agent 状态
    """
    hosts = []
    for info in host_list:
        # 查询所属区域云区域
        hosts.extend(
            [
                {"plat_id": info.bk_cloud_id, "bk_cloud_id": info.bk_cloud_id, "ip": ip}
                for ip in info.inner_ip.split(",")
            ]
        )
    # 处理返回数据
    data = gse.get_agent_status(username, hosts)
    return [asdict(make_dataclass_from_dict(HostAgentData, info)) for info in data]


try:
    from .host_ext import *  # noqa
except ImportError:
    pass
