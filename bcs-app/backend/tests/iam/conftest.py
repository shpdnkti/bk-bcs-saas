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
from typing import List
from unittest import mock

import pytest

from backend.iam.permissions.apply_url import ApplyURLGenerator
from backend.iam.permissions.request import ActionResourcesRequest
from backend.iam.permissions.resources.cluster import ClusterPermission
from backend.iam.permissions.resources.namespace import NamespacePermission
from backend.iam.permissions.resources.project import ProjectPermission

from .fake_iam import FakeClusterPermission, FakeNamespacePermission, FakeProjectPermission


def generate_apply_url(username: str, action_request_list: List[ActionResourcesRequest]) -> List[str]:
    expect = []
    for req in action_request_list:
        resources = ''
        if req.resources:
            resources = ''.join(req.resources)

        parent_chain = ''
        if req.parent_chain:
            parent_chain = ''.join([f'{item.resource_type}/{item.resource_id}' for item in req.parent_chain])
        expect.append(f'{req.resource_type}:{req.action_id}:{resources}:{parent_chain}')

    return expect


@pytest.fixture(autouse=True)
def patch_generate_apply_url():
    with mock.patch.object(ApplyURLGenerator, 'generate_apply_url', new=generate_apply_url):
        yield


@pytest.fixture
def project_permission_obj():
    patcher = mock.patch.object(ProjectPermission, '__bases__', (FakeProjectPermission,))
    with patcher:
        patcher.is_local = True  # 标注为本地属性，__exit__ 的时候恢复成 patcher.temp_original
        yield ProjectPermission()


@pytest.fixture
def namespace_permission_obj():
    cluster_patcher = mock.patch.object(ClusterPermission, '__bases__', (FakeClusterPermission,))
    project_patcher = mock.patch.object(ProjectPermission, '__bases__', (FakeProjectPermission,))
    namespace_patcher = mock.patch.object(NamespacePermission, '__bases__', (FakeNamespacePermission,))
    with cluster_patcher, project_patcher, namespace_patcher:
        cluster_patcher.is_local = True  # 标注为本地属性，__exit__ 的时候恢复成 patcher.temp_original
        project_patcher.is_local = True
        namespace_patcher.is_local = True
        yield NamespacePermission()
