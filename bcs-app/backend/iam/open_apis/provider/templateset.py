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
from typing import Optional

from iam.collection import FancyDict
from iam.resource.provider import ListResult, ResourceProvider
from iam.resource.utils import Page

from backend.templatesets.legacy_apps.configuration.utils import list_templatesets


class TemplatesetProvider(ResourceProvider):
    """模板集 资源拉取接口具体实现"""

    def list_instance(self, filter_obj: FancyDict, page_obj: Page, **options) -> ListResult:
        """
        获取模板集实例列表
        :param filter_obj: 查询参数。 以下为必传如: {"parent": {"id": 1}}
        :param page_obj: 分页对象
        """
        project_id = filter_obj.parent["id"]
        template_list = list_templatesets(project_id, filter_obj.ids, ["id", "project_id", "name"])
        count = len(template_list)
        template_slice = template_list[page_obj.slice_from : page_obj.slice_to]
        results = [{'id': template['id'], 'display_name': template['name']} for template in template_slice]
        return ListResult(results=results, count=count)

    def fetch_instance_info(self, filter_obj: FancyDict, **options) -> ListResult:
        """
        批量获取模板集实例属性详情
        :param filter_obj: 查询参数
        """
        template_list = list_templatesets(template_ids=filter_obj.ids, fields=["id", "project_id", "name"])
        results = [{'id': template['id'], 'display_name': template['name']} for template in template_list]
        return ListResult(results=results, count=len(template_list))

    def list_instance_by_policy(self, filter_obj: FancyDict, page_obj: Page, **options) -> ListResult:
        # TODO 确认基于实例的查询是不是就是id的过滤查询
        return ListResult(results=[], count=0)

    def list_attr(self, **options) -> ListResult:
        return ListResult(results=[], count=0)

    def list_attr_value(self, filter_obj: FancyDict, page_obj: Page, **options) -> ListResult:
        return ListResult(results=[], count=0)
