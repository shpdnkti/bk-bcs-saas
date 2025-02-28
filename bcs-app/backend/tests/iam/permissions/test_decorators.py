# -*- coding: utf-8 -*-
#
# Tencent is pleased to support the open source community by making 蓝鲸智云PaaS平台社区版 (BlueKing PaaS Community Edition) available.
# Copyright (C) 2017-2019 THL A29 Limited, a Tencent company. All rights reserved.
# Licensed under the MIT License (the "License"); you may not use this file except in compliance with the License.
# You may obtain a copy of the License at
#
#     http://opensource.org/licenses/MIT
#
# Unless required by applicable law or agreed to in writing, software distributed under the License is distributed on
# an "AS IS" BASIS, WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied. See the License for the
# specific language governing permissions and limitations under the License.
#
from unittest import mock

import pytest
from django.conf.urls import url
from rest_framework import permissions

from backend.bcs_web import viewsets
from backend.iam.permissions.decorators import response_perms
from backend.iam.permissions.resources.cluster import ClusterRequest
from backend.utils.response import PermsResponse

from ..fake_iam import FakeIAMClient

pytestmark = pytest.mark.django_db

cluster_data = [{'cluster_id': 'BCS-K8S-40000', 'name': "测试集群"}, {'cluster_id': 'BCS-K8S-40001', 'name': "演示集群"}]


@pytest.fixture(autouse=True)
def patch_iam_client():
    with mock.patch('backend.iam.permissions.decorators.IAMClient', new=FakeIAMClient):
        yield


class ClusterViewset(viewsets.SystemViewSet):
    permission_classes = (permissions.IsAuthenticated,)

    @response_perms(
        action_id_list=['cluster_view', 'cluster_manage'], res_request_cls=ClusterRequest, resource_id_key='cluster_id'
    )
    def get_clusters(self, request):
        return PermsResponse(cluster_data, iam_path_attrs={'project_id': 'test1234567'})


urlpatterns = [
    url('clusters/', ClusterViewset.as_view({'get': 'get_clusters'})),
]


@pytest.mark.urls(__name__)
class TestResponsePerms:
    def test_perms(self, api_client):
        response = api_client.get('http://testserver/clusters/')
        perms = response.json()['web_annotations']['perms']
        assert perms['BCS-K8S-40000'] == {'cluster_view': False, 'cluster_manage': False}
        assert perms['BCS-K8S-40001'] == {'cluster_view': True, 'cluster_manage': True}
