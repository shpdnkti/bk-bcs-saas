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
import mock
import pytest
from rest_framework.test import APIRequestFactory

from backend.iam.open_apis.views import ResourceAPIView
from backend.tests.bcs_mocks.misc import FakePaaSCCMod
from backend.tests.testing_utils.mocks.paas_cc import StubPaaSCCClient

factory = APIRequestFactory()


@pytest.fixture(autouse=True)
def patch_paas_cc():
    with mock.patch('backend.container_service.clusters.base.utils.paas_cc', new=FakePaaSCCMod()):
        yield


@pytest.fixture(autouse=True)
def patch_paas_cc_client():
    with mock.patch('backend.iam.open_apis.provider.cluster.PaaSCCClient', new=StubPaaSCCClient):
        yield


class TestClusterAPI:
    def test_list_instance(self, project_id):
        request = factory.post(
            '/apis/iam/v1/clusters/',
            {
                'method': 'list_instance',
                'type': 'cluster',
                'page': {'offset': 0, 'limit': 1},
                'filter': {'parent': {'id': project_id}},
            },
        )
        p_view = ResourceAPIView.as_view()
        response = p_view(request)
        data = response.data
        assert data['count'] == 1

    def test_fetch_instance_info_with_cluster_ids(self, cluster_id, project_id):
        """传入存在的cluster_id查询特定cluster_id数据。"""
        cluster_id = "BCS-K8S-10000"
        request = factory.post(
            '/apis/iam/v1/clusters/',
            {
                'method': 'fetch_instance_info',
                'type': 'cluster',
                'filter': {'ids': [cluster_id], 'parent': {'id': project_id}},
            },
        )
        p_view = ResourceAPIView.as_view()
        response = p_view(request)
        data = response.data
        assert len(data) == 1
        assert data[0]["id"] == "BCS-K8S-10000"
