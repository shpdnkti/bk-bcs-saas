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
from typing import Dict, List, Optional

from django.conf import settings
from iam import IAM, Action, MultiActionRequest, Request, Resource, Subject

from .request import ResourceRequest


class IAMClient:
    """提供基础的 iam client 方法封装"""

    iam = IAM(settings.APP_ID, settings.APP_TOKEN, settings.BK_IAM_HOST, settings.BK_PAAS_INNER_HOST)

    def resource_type_allowed(self, username: str, action_id: str, use_cache: bool = False) -> bool:
        """
        判断用户是否具备某个操作的权限
        note: 权限判断与资源实例无关，如创建某资源
        """
        request = self._make_request(username, action_id)
        if not use_cache:
            return self.iam.is_allowed(request)
        return self.iam.is_allowed_with_cache(request)

    def resource_inst_allowed(
        self, username: str, action_id: str, res_request: ResourceRequest, use_cache: bool = False
    ) -> bool:
        """
        判断用户对某个资源实例是否具有指定操作的权限
        note: 权限判断与资源实例有关，如更新某个具体资源
        """
        request = self._make_request(username, action_id, resources=res_request.make_resources())
        if not use_cache:
            return self.iam.is_allowed(request)
        return self.iam.is_allowed_with_cache(request)

    def resource_type_multi_actions_allowed(self, username: str, action_ids: List[str]) -> Dict[str, bool]:
        """
        判断用户是否具备多个操作的权限
        note: 权限判断与资源实例无关，如创建某资源

        :returns 示例 {'project_create': True}
        """
        return {action_id: self.resource_type_allowed(username, action_id) for action_id in action_ids}

    def resource_inst_multi_actions_allowed(
        self, username: str, action_ids: List[str], res_request: ResourceRequest
    ) -> Dict[str, bool]:
        """
        判断用户对某个资源实例是否具有多个操作的权限.
        note: 权限判断与资源实例有关，如更新某个具体资源

        :returns 示例 {'project_view': True, 'project_edit': False}
        """
        actions = [Action(action_id) for action_id in action_ids]
        request = MultiActionRequest(
            settings.APP_ID, Subject("user", username), actions, res_request.make_resources(), None
        )
        return self.iam.resource_multi_actions_allowed(request)

    def batch_resource_multi_actions_allowed(
        self, username: str, action_ids: List[str], res_request: ResourceRequest
    ) -> Dict[str, Dict[str, bool]]:
        """
        判断用户对某些资源是否具有多个指定操作的权限
        note: 当前sdk仅支持同类型的资源

        :returns 示例 {'0ad86c25363f4ef8adcb7ac67a483837': {'project_view': True, 'project_edit': False}}
        """
        actions = [Action(action_id) for action_id in action_ids]
        request = MultiActionRequest(settings.APP_ID, Subject("user", username), actions, [], None)
        resources_list = [[res] for res in res_request.make_resources()]
        return self.iam.batch_resource_multi_actions_allowed(request, resources_list)

    def _make_request(self, username: str, action_id: str, resources: Optional[List[Resource]] = None) -> Request:
        return Request(
            settings.APP_ID,
            Subject("user", username),
            Action(action_id),
            resources,
            None,
        )

    def _grant_resource_creator_actions(self, username: str, data: Dict):
        """
        用于创建资源时，注册用户对该资源的关联操作权限.
        note: 具体的关联操作见权限模型的 resource_creator_actions 字段
        """
        return self.iam._client.grant_resource_creator_actions(None, username, data)
