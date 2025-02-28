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
import logging

from iam.collection import FancyDict
from iam.resource.provider import ListResult, ResourceProvider
from iam.resource.utils import Page

from backend.components.base import ComponentAuth
from backend.components.paas_cc import PaaSCCClient
from backend.container_service.clusters.base import get_clusters
from backend.iam.open_apis.provider.utils import get_system_token

logger = logging.getLogger(__name__)


class ClusterProvider(ResourceProvider):
    """集群 资源拉取接口具体实现"""

    def list_instance(self, filter_obj: FancyDict, page_obj: Page, **options) -> ListResult:
        """
        获取集群实例列表
        :param filter_obj: 查询参数字典。 以下为必传如: {"parent": {"id": 1}}
        :param page_obj: 分页对象
        """
        project_id = filter_obj.parent["id"]
        cluster_list = get_clusters(get_system_token(), project_id)
        cluster_slice = cluster_list[page_obj.slice_from : page_obj.slice_to]
        results = [{'id': cluster['cluster_id'], 'display_name': cluster['name']} for cluster in cluster_slice]
        return ListResult(results=results, count=len(cluster_list))

    def fetch_instance_info(self, filter_obj: FancyDict, **options) -> ListResult:
        """
        批量获取集群实例属性详情
        :param filter_obj: 查询参数字典
        """
        cluster_ids = filter_obj.ids
        paas_cc = PaaSCCClient(auth=ComponentAuth(get_system_token()))
        cluster_list = paas_cc.list_clusters(cluster_ids)
        results = [{'id': cluster['cluster_id'], 'display_name': cluster['name']} for cluster in cluster_list]
        return ListResult(results=results, count=len(results))

    def list_instance_by_policy(self, filter_obj: FancyDict, page_obj: Page, **options) -> ListResult:
        # TODO 确认基于实例的查询是不是就是id的过滤查询
        return ListResult(results=[], count=0)

    def list_attr(self, **options) -> ListResult:
        return ListResult(results=[], count=0)

    def list_attr_value(self, filter_obj: FancyDict, page_obj: Page, **options) -> ListResult:
        return ListResult(results=[], count=0)
