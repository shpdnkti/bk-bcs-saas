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
from rest_framework import serializers
from rest_framework.exceptions import ValidationError

from backend.apps import utils as app_utils
from backend.apps.constants import EnvType, ProjectKind
from backend.resources.namespace.constants import K8S_PLAT_NAMESPACE


class BaseNamespaceSLZ(serializers.Serializer):
    cluster_id = serializers.CharField()
    # TODO: 不确定是否可以删除，先保留
    env_type = serializers.ChoiceField(choices=[i.value for i in EnvType], required=False)
    # k8s同样限制长度为[2, 30]，只是为了前端显示使用
    name = serializers.RegexField(r'[a-z0-9]([-a-z0-9]*[a-z0-9])?', min_length=2, max_length=63)
    # 支持编辑环境变量
    ns_vars = serializers.JSONField(required=False)

    def validate_cluster_id(self, cluster_id):
        access_token = self.context['request'].user.token.access_token
        project_id = self.context['project_id']
        data = app_utils.get_project_cluster_info(access_token, project_id)
        if not data or data['count'] == 0:
            raise ValidationError('cluster of project is empty')

        for cluster in data['results']:
            if cluster_id == cluster['cluster_id']:
                return cluster_id
        raise ValidationError('not found cluster, please check cluster info')

    def validate(self, data):
        # 现阶段已经去掉，为兼容逻辑先保留
        if 'env_type' not in data:
            data['env_type'] = "dev"
        return data


class CreateNamespaceSLZ(BaseNamespaceSLZ):
    quota = serializers.DictField(default={})

    def validate_name(self, name):
        project_kind = self.context['request'].project.kind
        if project_kind != ProjectKind.MESOS.value:
            if name in K8S_PLAT_NAMESPACE:
                raise ValidationError(f'namespace: {",".join(K8S_PLAT_NAMESPACE)} can not be used')

        # namespace name is unique in same cluster
        access_token = self.context['request'].user.token.access_token
        project_id = self.context['project_id']
        cluster_id = self.initial_data['cluster_id']
        cluster_namespaces = app_utils.get_cluster_namespaces(access_token, project_id, cluster_id)
        ns_name_list = [ns['name'] for ns in cluster_namespaces]
        if name in ns_name_list:
            raise ValidationError(f'name: [{name}] is used in cluster: [{cluster_id}]')

        return name


class UpdateNSVariableSLZ(serializers.Serializer):
    ns_vars = serializers.JSONField(required=False)


class UpdateNamespaceQuotaSLZ(serializers.Serializer):
    """更新命名空间下资源配置的参数"""

    quota = serializers.DictField()
