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
from django.conf.urls import url

from backend.uniapps.network.clb import views

urlpatterns = [
    url(
        r'^api/projects/(?P<project_id>\w{32})/network/clb/names/$',
        views.DescribeCLBNamesViewSet.as_view({'get': 'list'}),
    ),
    url(
        r'^api/projects/(?P<project_id>\w{32})/network/clbs/$',
        views.CLBListCreateViewSet.as_view({'get': 'list', 'post': 'create'}),
    ),
    url(
        r'^api/projects/(?P<project_id>\w{32})/network/clbs/(?P<clb_id>\d+)/$',
        views.CLBRetrieveOperateViewSet.as_view({'get': 'retrieve', 'delete': 'delete', 'put': 'update'}),
    ),
    url(
        r'^api/projects/(?P<project_id>\w{32})/network/mesos/clbs/(?P<clb_id>\d+)/$',
        views.MesosCLBOperateViewSet.as_view({'post': 'post', 'delete': 'delete'}),
    ),
    url(
        r'^api/projects/(?P<project_id>\w{32})/network/clbs/(?P<clb_id>\d+)/status/$',
        views.CLBStatusViewSet.as_view({'get': 'retrieve_status'}),
    ),
    url(
        r'^api/projects/(?P<project_id>\w{32})/network/clb/regions/$',
        views.GetCLBRegionsViewSet.as_view({'get': 'list'}),
    ),
]
