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
import copy
import json
import logging
import re
from typing import Dict, List

from django.utils.translation import ugettext_lazy as _
from rest_framework import response, viewsets
from rest_framework.exceptions import ValidationError
from rest_framework.renderers import BrowsableAPIRenderer

from backend.accounts import bcs_perm
from backend.bcs_web.audit_log import client
from backend.bcs_web.viewsets import SystemViewSet
from backend.components import data as data_api
from backend.components import paas_cc
from backend.components.bcs import k8s, mesos
from backend.container_service.clusters import constants as cluster_constants
from backend.container_service.clusters import serializers as node_serializers
from backend.container_service.clusters import utils as cluster_utils
from backend.container_service.clusters.base.models import CtxCluster
from backend.container_service.clusters.base.utils import get_cluster_nodes
from backend.container_service.clusters.constants import DEFAULT_SYSTEM_LABEL_KEYS
from backend.container_service.clusters.driver import BaseDriver
from backend.container_service.clusters.models import CommonStatus, NodeLabel, NodeStatus, NodeUpdateLog
from backend.container_service.clusters.module_apis import get_cluster_node_mod, get_cmdb_mod, get_gse_mod
from backend.container_service.clusters.serializers import NodeLabelParamsSLZ
from backend.container_service.clusters.tools.node import query_cluster_nodes
from backend.container_service.clusters.utils import cluster_env_transfer, custom_paginator, status_transfer
from backend.iam.permissions.resources import ClusterPermCtx, ClusterPermission
from backend.utils.errcodes import ErrorCode
from backend.utils.error_codes import error_codes
from backend.utils.funutils import convert_mappings
from backend.utils.renderers import BKAPIRenderer

# 导入相应模块
node = get_cluster_node_mod()
cmdb = get_cmdb_mod()
gse = get_gse_mod()

logger = logging.getLogger(__name__)

DEFAULT_MIX_VALUE = cluster_constants.DEFAULT_MIX_VALUE


class NodeBase:
    def can_view_cluster(self, request, project_id, cluster_id):
        """has view cluster perm"""
        cluster_perm = bcs_perm.Cluster(request, project_id, cluster_id)
        cluster_perm.can_view(raise_exception=True)

    def can_edit_cluster(self, request, project_id, cluster_id):
        cluster_perm = bcs_perm.Cluster(request, project_id, cluster_id)
        return cluster_perm.can_edit(raise_exception=True)

    def get_node_list(self, request, project_id, cluster_id):
        """get cluster node list"""
        node_resp = paas_cc.get_node_list(
            request.user.token.access_token,
            project_id,
            cluster_id,
            params={'limit': cluster_constants.DEFAULT_NODE_LIMIT},
        )
        if node_resp.get('code') != ErrorCode.NoError:
            raise error_codes.APIError(node_resp.get('message'))
        return node_resp.get('data') or {}

    def get_all_cluster(self, request, project_id):
        resp = paas_cc.get_all_clusters(request.user.token.access_token, project_id)
        if (resp.get('code') != ErrorCode.NoError) or (not resp.get('data')):
            raise error_codes.APIError('search cluster error')
        return resp.get('data') or {}

    def get_cluster_env(self, request, project_id):
        """get cluster env map"""
        data = self.get_all_cluster(request, project_id)
        results = data.get('results') or []
        return {
            info['cluster_id']: cluster_env_transfer(info['environment']) for info in results if info.get('cluster_id')
        }

    def get_node_by_id(self, request, project_id, cluster_id, node_id):
        """get node info by node id"""
        resp = paas_cc.get_node(request.user.token.access_token, project_id, node_id, cluster_id=cluster_id)
        if resp.get('code') != ErrorCode.NoError:
            raise error_codes.APIError(resp.get('message'))
        return resp.get('data') or {}

    def get_project_cluster(self, request, project_id):
        """get cluster info"""
        data = self.get_all_cluster(request, project_id)
        results = data.get('results') or []
        return {info['cluster_id']: info['name'] for info in results}

    def update_nodes_in_cluster(self, request, project_id, cluster_id, node_ips, status):
        """update nodes with same cluster"""
        data = [{'inner_ip': ip, 'status': status} for ip in node_ips]
        resp = paas_cc.update_node_list(request.user.token.access_token, project_id, cluster_id, data=data)
        if resp.get('code') != ErrorCode.NoError:
            raise error_codes.APIError(resp.get('message'))
        return resp.get('data') or []

    def get_cluster(self, request, project_id, cluster_id):
        cluster_resp = paas_cc.get_cluster(request.user.token.access_token, project_id, cluster_id)
        if cluster_resp.get('code') != ErrorCode.NoError:
            raise error_codes.APIError.f(cluster_resp.get('message'))
        return cluster_resp.get('data') or {}


class NodeHandler:
    def filter_node(self, data, filter_ip, filter_key='InnerIP'):
        """filter rule:
        - single ip: fuzzy search
        - other: precise search
        """
        if not filter_ip:
            return data
        if isinstance(filter_ip, str):
            filter_ip = filter_ip.split(',')
        filter_data = []
        # fuzzy search
        if len(filter_ip) == 1:
            filter_data = [info for info in data if filter_ip[0].strip() in info[filter_key]]
        else:
            for info in data:
                if info[filter_key] in filter_ip:
                    filter_data.append(info)
                if len(filter_data) == len(filter_ip):
                    break
        return filter_data

    def clean_node(self, data):
        """remove the specific status node item
        Note: remove the node of the 'removed' status
        """
        return [info for info in data if info.get('status') not in [NodeStatus.Removed]]

    def get_order_by(self, request, project_id, data, ordering):
        if not (ordering and data['results']):
            return data
        # reverse order
        node_ip_list = [i['inner_ip'] for i in data['results']]
        cc_app_id = request.project['cc_app_id']
        # split the asc or desc
        if ordering.startswith('-'):
            metric, reverse = ordering[1:], False
        else:
            metric, reverse = ordering, True

        result = data_api.get_node_metrics_order(metric, cc_app_id, node_ip_list).get('list') or []
        # metric sort
        if metric == 'mem':
            result = sorted(result, key=lambda x: x['used'] / x['total'], reverse=reverse)
        elif metric == 'cpu_summary':
            result = sorted(result, key=lambda x: x['usage'], reverse=reverse)
        elif metric == 'disk':
            result = sorted(result, key=lambda x: x['in_use'], reverse=reverse)
        order_by = [i['ip'] for i in result]

        order_by = order_by[::-1] if reverse else order_by

        def index(ip):
            try:
                return order_by.index(ip)
            except ValueError:
                return 0

        data['results'] = sorted(data['results'], key=lambda x: (index(x['inner_ip']), x['inner_ip']), reverse=True)
        return data


class NodeLabelBase:
    def get_labels_by_node(self, request, project_id, node_id_list):
        node_label_info = NodeLabel.objects.filter(node_id__in=node_id_list, project_id=project_id, is_deleted=False)
        return node_label_info.values("id", "project_id", "node_id", "cluster_id", "labels")

    def delete_node_label(self, request, node_id):
        """set node label deleted"""
        try:
            cluster_utils.delete_node_labels_record(NodeLabel, [node_id], request.user.username)
        except Exception as err:
            logger.error('delete node label error, %s', err)


class NodeCreateListViewSet(NodeBase, NodeHandler, viewsets.ViewSet):
    renderer_classes = (BKAPIRenderer, BrowsableAPIRenderer)
    permission = ClusterPermission()

    def get_data(self, request):
        slz = node_serializers.ListNodeSLZ(data=request.GET)
        slz.is_valid(raise_exception=True)
        return dict(slz.validated_data)

    def get_post_data(self, request):
        slz = node_serializers.ListNodeSLZ(data=request.data)
        slz.is_valid(raise_exception=True)
        return dict(slz.validated_data)

    def add_container_count(self, request, project_id, cluster_id, project_kind, node_list):
        host_ip_list = [info['inner_ip'] for info in node_list]
        try:
            driver = BaseDriver(project_kind).driver(request, project_id, cluster_id)
            host_container_map = driver.get_host_container_count(host_ip_list)
        except Exception as e:
            logger.exception(f"通过BCS API查询主机container数量异常, 详情: {e}")
            host_container_map = {}
        for info in node_list:
            info["containers"] = host_container_map.get(info["inner_ip"], 0)
        return node_list

    def compose_data_with_containers(self, request, project_id, cluster_id, with_containers, data):
        if not (with_containers and data):
            return data
        # add container count
        return self.add_container_count(request, project_id, cluster_id, request.project['kind'], data)

    def add_env_perm(self, request, project_id, cluster_id, data, cluster_env_info):
        nodes_results = bcs_perm.Cluster.hook_perms(request, project_id, [{'cluster_id': cluster_id}])
        for info in data.get('results') or []:
            info['permissions'] = nodes_results[0]['permissions']
            info['cluster_env'] = cluster_env_info.get(cluster_id, '')

    def get_create_node_perm(self, request, project_id, cluster_id):
        perm_client = bcs_perm.Cluster(request, project_id, cluster_id)
        return perm_client.can_edit(raise_exception=False)

    def filter_node_with_labels(self, cluster_id, data, filter_label_list):
        """filter node list by node labels
        filter_label_list format: [{'a': '1'}, {'a': '2'}, {'b': '1'}]
        """
        if not filter_label_list:
            return data
        node_id_info_map = {info['id']: info for info in data}
        node_labels = NodeLabel.objects.filter(cluster_id=cluster_id, is_deleted=False)
        filter_data = []
        for info in node_labels:
            labels = info.node_labels
            for filter_label in filter_label_list:
                key = list(filter_label)[-1]
                if key in labels and labels[key] == filter_label[key] and info.node_id in node_id_info_map:
                    filter_data.append(node_id_info_map[info.node_id])
                    break
        return filter_data

    def filter_nodes_by_status(self, node_list, status_list):
        if not status_list:
            return node_list
        return [node for node in node_list if node["status"] in status_list]

    def data_handler_for_nodes(self, request, project_id, cluster_id, data):
        self.can_view_cluster(request, project_id, cluster_id)
        node_list = self.get_node_list(request, project_id, cluster_id)
        # filter by request ip
        node_list = self.filter_node(node_list.get('results') or [], data.get('ip'), filter_key="inner_ip")
        node_list = self.filter_node_with_labels(cluster_id, node_list, data.get('labels'))
        # 通过节点状态过滤节点
        node_list = self.filter_nodes_by_status(node_list, data["status_list"])
        node_list = self.clean_node(node_list)
        # pagination for node list
        ip_offset = data.pop('offset', 0)
        ip_limit = data.pop('limit', cluster_constants.DEFAULT_PAGE_LIMIT)
        pagination_data = custom_paginator(node_list, limit=ip_limit, offset=ip_offset)
        # add
        pagination_data['results'] = self.compose_data_with_containers(
            request, project_id, cluster_id, data.get('with_containers'), pagination_data['results']
        )
        # order the node list
        ordering = data.get('ordering')
        if ordering:
            pagination_data = self.get_order_by(request, project_id, pagination_data, ordering)

        cluster_env_info = self.get_cluster_env(request, project_id)
        # add perm
        self.add_env_perm(request, project_id, cluster_id, pagination_data, cluster_env_info)

        has_create_perm = self.get_create_node_perm(request, project_id, cluster_id)
        return {'code': ErrorCode.NoError, 'data': pagination_data, 'permissions': {'create': has_create_perm}}

    def post_node_list(self, request, project_id, cluster_id):
        """post request for node list"""
        # 权限校验
        perm_ctx = ClusterPermCtx(username=request.user.username, project_id=project_id, cluster_id=cluster_id)
        self.permission.can_view(perm_ctx)

        data = self.get_post_data(request)
        node_list_with_perm = self.data_handler_for_nodes(request, project_id, cluster_id, data)
        return response.Response(node_list_with_perm)

    def list(self, request, project_id, cluster_id):
        """get node list
        note: pagination by backend
        """
        # get request data
        data = self.get_data(request)
        node_list_with_perm = self.data_handler_for_nodes(request, project_id, cluster_id, data)
        return response.Response(node_list_with_perm)

    def create(self, request, project_id, cluster_id):
        """创建节点"""
        # 权限校验
        perm_ctx = ClusterPermCtx(username=request.user.username, project_id=project_id, cluster_id=cluster_id)
        self.permission.can_manage(perm_ctx)
        node_client = node.CreateNode(request, project_id, cluster_id)
        return node_client.create()

    def list_nodes_ip(self, request, project_id, cluster_id):
        """获取集群下节点的IP"""
        # 权限校验
        perm_ctx = ClusterPermCtx(username=request.user.username, project_id=project_id, cluster_id=cluster_id)
        self.permission.can_view(perm_ctx)
        nodes = get_cluster_nodes(request.user.token.access_token, project_id, cluster_id, raise_exception=False)
        return response.Response([info["inner_ip"] for info in nodes if info["status"] != CommonStatus.Removed])


class NodeGetUpdateDeleteViewSet(NodeBase, NodeLabelBase, viewsets.ViewSet):
    renderer_classes = (BKAPIRenderer, BrowsableAPIRenderer)
    permission = ClusterPermission()

    def retrieve(self, request, project_id, cluster_id, node_id):
        self.can_view_cluster(request, project_id, cluster_id)
        node_info = self.get_node_by_id(request, project_id, cluster_id, node_id)
        return response.Response(node_info)

    def reinstall(self, request, project_id, cluster_id, node_id):
        node_client = node.ReinstallNode(request, project_id, cluster_id, node_id)
        return node_client.reinstall()

    def get_request_params(self, request):
        slz = node_serializers.UpdateNodeSLZ(data=request.data)
        slz.is_valid(raise_exception=True)
        return slz.validated_data

    def allow_oper_node(self, node_info, curr_node_status):
        not_allow_msg = "some nodes of the selected nodes do not allow operation, please check the nodes status!"
        if node_info['status'] == NodeStatus.ToRemoved and curr_node_status in [
            node_info['status'],
            NodeStatus.Removable,
        ]:
            raise error_codes.CheckFailed(not_allow_msg)
        if node_info['status'] == NodeStatus.Normal and curr_node_status in [node_info['status'], NodeStatus.Normal]:
            raise error_codes.CheckFailed(not_allow_msg)

    def node_handler(self, request, project_id, cluster_id, node_info):
        driver = BaseDriver(request.project['kind']).driver(request, project_id, cluster_id)
        if node_info['status'] == NodeStatus.ToRemoved:
            driver.disable_node(node_info['inner_ip'])
        elif node_info['status'] == NodeStatus.Normal:
            driver.enable_node(node_info['inner_ip'])
        else:
            raise error_codes.CheckFailed(f'node of the {node_info["status"]} does not allow operation')

    def get_node_container_num(self, request, project_id, cluster_id, inner_ip):
        driver = BaseDriver(request.project['kind']).driver(request, project_id, cluster_id)
        node_container_data = driver.get_host_container_count([inner_ip])
        return node_container_data.get(inner_ip) or 0

    def update(self, request, project_id, cluster_id, node_id):
        """允许调度/停止调度节点"""
        # 权限校验
        perm_ctx = ClusterPermCtx(username=request.user.username, project_id=project_id, cluster_id=cluster_id)
        self.permission.can_manage(perm_ctx)

        # get params
        params = self.get_request_params(request)
        node_info = self.get_node_by_id(request, project_id, cluster_id, node_id)
        curr_node_status = node_info.get('status')
        # update request info
        node_info.update(params)
        self.allow_oper_node(node_info, curr_node_status)
        # enable/disable node info
        project_name = request.project['project_name']
        # 记录node的操作，这里包含disable: 停止调度，enable: 允许调度
        # 根据状态进行判断，当前端传递的是normal时，是要允许调度，否则是停止调度
        operate = "enable" if node_info["status"] == NodeStatus.Normal else "disable"
        log_desc = f'project: {project_name}, cluster: {cluster_id}, {operate} node: {node_info["inner_ip"]}'
        with client.ContextActivityLogClient(
            project_id=project_id,
            user=request.user.username,
            resource_type='node',
            resource=node_info['inner_ip'],
            resource_id=node_id,
            description=log_desc,
        ).log_modify():
            self.node_handler(request, project_id, cluster_id, node_info)
            container_num = self.get_node_container_num(request, project_id, cluster_id, node_info['inner_ip'])
            # update node status to removable, when container num in the host is zore
            if container_num == 0 and node_info['status'] == NodeStatus.ToRemoved:
                node_info['status'] = NodeStatus.Removable
            data = self.update_nodes_in_cluster(
                request, project_id, cluster_id, [node_info['inner_ip']], node_info['status']
            )
        node = data[0] if data else {}
        return response.Response(node)

    def delete(self, request, project_id, cluster_id, node_id):
        """删除节点
        1. 调用bcs接口，下发任务
        2. 启动后台轮训
        3. 更改主机状态为removing
        """
        # 权限校验
        perm_ctx = ClusterPermCtx(username=request.user.username, project_id=project_id, cluster_id=cluster_id)
        self.permission.can_manage(perm_ctx)

        self.delete_node_label(request, node_id)
        node_client = node.DeleteNode(request, project_id, cluster_id, node_id)
        return node_client.delete()


class FailedNodeDeleteViewSet(NodeBase, NodeLabelBase, viewsets.ViewSet):
    renderer_classes = (BKAPIRenderer, BrowsableAPIRenderer)

    def delete(self, request, project_id, cluster_id, node_id):
        """Delete failed node"""
        self.delete_node_label(request, node_id)
        node_client = node.DeleteNode(request, project_id, cluster_id, node_id)
        return node_client.force_delete()


class CCHostListViewSet(NodeBase, NodeHandler, viewsets.ViewSet):
    renderer_classes = (BKAPIRenderer, BrowsableAPIRenderer)

    def get_data(self, request):
        """serialize request data"""
        slz = node_serializers.ListNodeSLZ(data=request.data)
        slz.is_valid(raise_exception=True)
        return dict(slz.validated_data)

    def get_all_nodes(self, request, project_id):
        data = paas_cc.get_all_cluster_hosts(
            request.user.token.access_token, exclude_status_list=[CommonStatus.Removed]
        )
        return {info['inner_ip']: info for info in data}

    def get_cc_host_mappings(self, host_list):
        data = {info['InnerIP']: convert_mappings(cluster_constants.CCHostKeyMappings, info) for info in host_list}
        return data

    def get_project_cluster_resource(self, request):
        """get all master/node info"""
        resp = paas_cc.get_project_cluster_resource(request.user.token.access_token)
        if resp.get('code') != ErrorCode.NoError:
            raise error_codes.APIError(resp.get('message'))
        data = resp.get('data') or []
        # return format: {cluster_id: {project_name: xxx, cluster_name: xxx}}
        format_data = {
            cluster['id']: {'project_name': project['name'], 'cluster_name': cluster['name']}
            for project in data
            if project
            for cluster in project['cluster_list']
            if cluster
        }
        return format_data

    def update_agent_status(self, cc_host_map, gse_host_status):
        gse_host_status_map = {info['ip']: info for info in gse_host_status}
        for ips in cc_host_map:
            # one host may has many eth(ip)
            ip_list = ips.split(',')
            exist = -1
            for item in ip_list:
                if item not in gse_host_status_map or exist > 0:
                    continue
                item_info = gse_host_status_map[item]
                item_exist = item_info.get('exist') or item_info.get('bk_agent_alive')
                # 防止出现None情况
                exist = exist if exist > 0 else (item_exist or exist)
            # render agent status
            cc_host_map[ips]['agent'] = exist if exist else -1

    def render_node_with_use_status(self, host_list, exist_node_info, project_cluster_resource):
        # node_list: not used node list; used_node_list: used node list
        node_list = []
        used_node_list = []
        # handler
        for ip_info in host_list:
            used_status = False
            ips = ip_info.get('InnerIP')
            if not ips:
                continue
            # init the filed value
            project_name, cluster_name, cluster_id = '', '', ''
            for ip in ips.split(','):
                used_ip_info = exist_node_info.get(ip)
                if not used_ip_info:
                    continue
                used_status = True
                cluster_id = used_ip_info.get('cluster_id')
                project_cluster_name = project_cluster_resource.get(cluster_id) or {}
                project_name = project_cluster_name.get('project_name', '')
                cluster_name = project_cluster_name.get('cluster_name', '')
                break
            # update fields and value
            ip_info.update(
                {
                    'project_name': project_name,
                    'cluster_name': cluster_name,
                    'cluster_id': cluster_id,
                    'is_used': used_status,
                    # 添加是否docker机类型，docker机不允许使用
                    # 判断条件为，以`D`开头则为docker机
                    "is_valid": False if ip_info.get("DeviceClass", "").startswith("D") else True,
                }
            )
            if used_status:
                used_node_list.append(ip_info)
            else:
                node_list.append(ip_info)
        # append used node list
        node_list.extend(used_node_list)
        return node_list

    def post(self, request, project_id):
        """get cmdb host info, include gse status, use status"""
        # get request data
        data = self.get_data(request)
        cmdb_client = cmdb.CMDBClient(request)
        host_list = cmdb_client.get_cc_hosts()
        # filter node list
        host_list = self.filter_node(host_list, data['ip_list'])
        self.cc_application_name = cmdb_client.get_cc_application_name()
        # get host list, return as soon as possible when empty
        if not host_list:
            return response.Response({'results': [], 'cc_application_name': self.cc_application_name})
        # get resource from bcs cc
        project_cluster_resource = self.get_project_cluster_resource(request)
        exist_node_info = self.get_all_nodes(request, project_id)
        # add node use status, in order to display for frontend
        host_list = self.render_node_with_use_status(host_list, exist_node_info, project_cluster_resource)
        # 获取不可用节点的数量，返回供前端使用
        unavailable_ip_count = len([info for info in host_list if info.get("is_used") or not info.get("is_valid")])
        # paginator the host list
        pagination_data = custom_paginator(host_list, data['offset'], limit=data['limit'])
        # for frontend display
        cc_host_map = self.get_cc_host_mappings(pagination_data['results'])
        gse_host_status = gse.GSEClient.get_agent_status(request.user.username, cc_host_map.values())
        # compose the host list with gse status and host status
        self.update_agent_status(cc_host_map, gse_host_status)

        return response.Response(
            {
                'results': list(cc_host_map.values()),
                'count': pagination_data['count'],
                'cc_application_name': self.cc_application_name,
                "unavailable_ip_count": unavailable_ip_count,
            }
        )


class NodeUpdateLogView(NodeBase, viewsets.ModelViewSet):
    renderer_classes = (BKAPIRenderer, BrowsableAPIRenderer)
    serializer_class = node_serializers.NodeInstallLogSLZ
    queryset = NodeUpdateLog.objects.all()

    def get_queryset(self, project_id, cluster_id, node_id):
        return (
            super()
            .get_queryset()
            .filter(project_id=project_id, cluster_id=cluster_id, node_id__icontains='[%s]' % node_id)
            .order_by('-create_at')
        )

    def get_display_status(self, curr_status):
        return status_transfer(
            curr_status, cluster_constants.NODE_RUNNING_STATUS, cluster_constants.NODE_FAILED_STATUS
        )

    def get_node_ip(self, access_token, project_id, cluster_id, node_id):
        resp = paas_cc.get_node(access_token, project_id, node_id, cluster_id=cluster_id)
        if resp.get("code") != ErrorCode.NoError:
            logger.error("request paas cc node api error, %s", resp.get("message"))
            return None
        return resp.get("data", {}).get("inner_ip")

    def get_log_data(self, request, logs, project_id, cluster_id, node_id):
        if not logs:
            return {'status': 'none'}
        latest_log = logs[0]
        status = self.get_display_status(latest_log.status)
        data = {
            'project_id': project_id,
            'cluster_id': cluster_id,
            'status': status,
            'log': [],
            "task_url": latest_log.log_params.get("task_url") or "",
            "error_msg_list": [],
        }
        for info in logs:
            info.status = self.get_display_status(info.status)
            slz = node_serializers.NodeInstallLogSLZ(instance=info)
            data['log'].append(slz.data)

        return data

    def get(self, request, project_id, cluster_id, node_id):
        self.can_view_cluster(request, project_id, cluster_id)
        # get log
        logs = self.get_queryset(project_id, cluster_id, node_id)
        data = self.get_log_data(request, logs, project_id, cluster_id, node_id)
        return response.Response(data)


class NodeInfo(NodeBase, viewsets.ViewSet):
    renderer_classes = (BKAPIRenderer, BrowsableAPIRenderer)

    def get_node_id(self, inner_ip, node_list):
        """get node id by bcs cc"""
        node_id = 0
        for info in node_list:
            if info['inner_ip'] != inner_ip:
                continue
            node_id = info['id']
            break
        if not node_id:
            raise error_codes.CheckFailed(f'inner_ip[{inner_ip}] not found')
        return node_id

    def info(self, request, project_id, cluster_id):
        """get host info by cmdb"""
        self.can_view_cluster(request, project_id, cluster_id)
        inner_ip = request.GET.get('res_id')
        if not inner_ip:
            raise error_codes.APIError('params[res_id] is null')
        # get node list, compatible logic
        try:
            node_data = self.get_node_list(request, project_id, cluster_id)
            node_list = node_data.get("results") or []
        except Exception as err:
            logger.error('get node error, %s', err)
            return response.Response([])
        node_id = self.get_node_id(inner_ip, node_list)
        data = cmdb.CMDBClient(request).get_host_base_info(inner_ip)
        # provider can only be CMDB
        data.update({'provider': 'CMDB', 'id': node_id})
        return response.Response(data)


class NodeContainers(NodeBase, viewsets.ViewSet):
    renderer_classes = (BKAPIRenderer, BrowsableAPIRenderer)

    def get_params(self, request, project_id, cluster_id):
        slz = node_serializers.NodeSLZ(
            data=request.GET, context={'request': request, 'project_id': project_id, 'cluster_id': cluster_id}
        )
        slz.is_valid(raise_exception=True)
        return slz.data

    def list(self, request, project_id, cluster_id):
        """获取节点下的容器列表"""
        self.can_view_cluster(request, project_id, cluster_id)
        # get params
        params = self.get_params(request, project_id, cluster_id)
        # get containers
        driver = BaseDriver(request.project['kind']).driver(request, project_id, cluster_id)
        containers = driver.flatten_container_info(params['res_id'])

        return response.Response(containers)


class NodeLabelQueryCreateViewSet(NodeBase, NodeLabelBase, viewsets.ViewSet):
    def label_key_handler(self, pre_labels, curr_labels):
        """处理label的key"""
        ret_data = {}
        pre_label_keys = pre_labels.keys()
        curr_keys = curr_labels.keys()
        same_keys = list(set(pre_label_keys) & set(curr_keys))
        diff_keys = list(set(pre_label_keys) ^ set(curr_keys))
        # 相同的key，如果value不一样，也设置为mix value
        for key in same_keys:
            if pre_labels[key] != curr_labels[key]:
                ret_data[key] = DEFAULT_MIX_VALUE
            else:
                ret_data[key] = pre_labels[key]
        # 不同的key，都设置为mix value
        for key in diff_keys:
            ret_data[key] = DEFAULT_MIX_VALUE
        return ret_data

    def label_syntax(self, node_labels, exist_node_without_label=False):
        """处理节点标签
        如果为mix value，则设置为*****-----$$$$$
        """
        ret_data = {}
        for info in node_labels:
            labels = json.loads(info.get("labels") or "{}")
            if not labels:
                continue
            if exist_node_without_label:
                ret_data.update(labels)
            else:
                if not ret_data:
                    ret_data.update(labels)
                else:
                    ret_data = self.label_key_handler(ret_data, labels)

        if exist_node_without_label:
            ret_data = {key: DEFAULT_MIX_VALUE for key in ret_data}

        return ret_data

    def get_node_labels(self, request, project_id):
        """获取节点标签"""
        # 获取节点ID
        node_ids = request.GET.get("node_ids")
        cluster_id = request.GET.get("cluster_id")
        if not node_ids:
            raise error_codes.CheckFailed(_("节点信息不存在，请确认后重试!"))
        # 以半角逗号分隔
        node_id_list = [int(node_id) for node_id in node_ids.split(",") if str(node_id).isdigit()]
        # 判断节点属于项目
        all_nodes = self.get_node_list(request, project_id, cluster_id).get('results') or []
        if not all_nodes:
            raise error_codes.APIError(_("当前项目下没有节点!"))
        all_node_id_list = [info["id"] for info in all_nodes]
        diff_node_id_list = set(node_id_list) - set(all_node_id_list)
        if diff_node_id_list:
            return response.Response(
                {
                    "code": ErrorCode.UserError,
                    "message": _("节点ID [{}] 不属于当前项目，请确认").format(",".join(diff_node_id_list)),
                }
            )

        node_label_list = self.get_labels_by_node(request, project_id, node_id_list)
        # 校验权限
        cluster_id_list = [info["cluster_id"] for info in all_nodes if info["id"] in node_id_list]
        for cluster_id in set(cluster_id_list):
            perm_client = bcs_perm.Cluster(request, project_id, cluster_id)
            perm_client.can_view(raise_exception=True)
        if not node_label_list:
            return response.Response({"code": ErrorCode.NoError, "data": {}})

        # 如果有多个节点，并且有的节点不存在标签，则全部value为mix value
        exist_node_without_label = False
        if len(node_label_list) != len(node_id_list):
            exist_node_without_label = True
        for info in node_label_list:
            if not info.get("labels"):
                exist_node_without_label = True
        ret_data = self.label_syntax(node_label_list, exist_node_without_label=exist_node_without_label)
        return response.Response({"code": ErrorCode.NoError, "data": ret_data})

    def get_create_label_params(self, request):
        slz = NodeLabelParamsSLZ(data=request.data)
        slz.is_valid(raise_exception=True)
        node_id_labels = slz.data
        return node_id_labels.get("node_id_list"), node_id_labels.get("node_label_info")

    def label_regex(self, node_label_info, project_kind):
        """校验label满足正则"""
        # 由于mesos没有限制，因此可以直接跳过
        if project_kind != 1:
            return
        prefix_part_regex = re.compile(
            r"^(?=^.{3,253}$)[a-zA-Z0-9][-a-zA-Z0-9]{0,62}(\.[a-zA-Z0-9][-a-zA-Z0-9]{0,62})+$"
        )
        name_part_regex = re.compile(r"^[a-z0-9A-Z][\w.-]{0,61}[a-z0-9A-Z]$|^[a-z0-9A-Z]$")
        val_regex = re.compile(r"^[a-z0-9A-Z][\w.-]{0,61}[a-z0-9A-Z]$|^[a-z0-9A-Z]$")
        if not node_label_info:
            return
        for key, val in node_label_info.items():
            if key in DEFAULT_SYSTEM_LABEL_KEYS:
                raise error_codes.APIError(_("[{}]为系统默认key，禁止使用，请确认").format(key))
            # 针对key的限制
            if key.count("/") == 1:
                split_list = key.split("/")
                if not prefix_part_regex.match(split_list[0]):
                    raise error_codes.APIError(_("键[{}]不符合规范，请参考帮助文档!").format(key))
                if not name_part_regex.match(split_list[-1]):
                    raise error_codes.APIError(_("键[{}]不符合规范，请参考帮助文档!").format(key))
            else:
                if not name_part_regex.match(key):
                    raise error_codes.APIError(_("键[{}]不符合规范，请参考帮助文档!").format(key))
            # 针对val的校验
            if val != DEFAULT_MIX_VALUE and not val_regex.match(val):
                raise error_codes.APIError(_("键[{}]对应的值[{}]不符合规范，请参考帮助文档!").format(key, val))

    def get_label_operation(self, exist_node_labels, post_data, node_id_list, all_node_id_ip_map):
        """获取节点标签，并且和数据库中作对比，识别到添加、删除、更新操作对应的key:value
        format: {
            id: {
                ip: "",
                add: {
                    key: val
                },
                update: {
                    key: val
                },
                delete: {
                    key: val
                },
                existed: {
                },
            }
        }
        """
        label_operation_map = {}
        existed_node_id_list = []
        # 已经存在的记录调整
        for info in exist_node_labels:
            node_id = info["node_id"]
            existed_node_id_list.append(node_id)
            label_operation_map[node_id] = {
                "new": False,
                "cluster_id": all_node_id_ip_map[node_id]["cluster_id"],
                "ip": all_node_id_ip_map[node_id]["inner_ip"],
                "add": {},
                "update": {},
                "delete": {},
                "existed": {},
            }
            labels = json.loads(info["labels"] or "{}")
            if not labels:
                label_operation_map[node_id]["add"] = {
                    key: val for key, val in post_data.items() if val != DEFAULT_MIX_VALUE
                }
            else:
                post_data_copy = copy.deepcopy(post_data)
                for key, val in labels.items():
                    if key not in post_data:
                        label_operation_map[node_id]["delete"][key] = val
                        continue
                    if post_data[key] != DEFAULT_MIX_VALUE:
                        label_operation_map[node_id]["update"][key] = post_data[key]
                    else:
                        label_operation_map[node_id]["existed"][key] = val
                    post_data_copy.pop(key, None)
                label_operation_map[node_id]["add"].update(
                    {key: val for key, val in post_data_copy.items() if val != DEFAULT_MIX_VALUE}
                )
        # 新添加的node调整
        for node_id in set(node_id_list) - set(existed_node_id_list):
            item = {key: val for key, val in post_data.items() if val != DEFAULT_MIX_VALUE}
            if not item:
                continue
            label_operation_map[node_id] = {
                "new": True,
                "cluster_id": all_node_id_ip_map[node_id]["cluster_id"],
                "ip": all_node_id_ip_map[node_id]["inner_ip"],
                "add": item,
                "update": {},
                "delete": {},
                "existed": {},
            }
        return label_operation_map

    def create_node_label_via_k8s(self, request, project_id, label_operation_map):
        """K8S打Label"""
        for node_id, info in label_operation_map.items():
            client = k8s.K8SClient(request.user.token.access_token, project_id, info["cluster_id"], None)
            online_node_info = client.get_node_detail(info["ip"])
            if online_node_info.get("code") != ErrorCode.NoError:
                raise error_codes.APIError(online_node_info.get("message"))
            online_metadata = (online_node_info.get("data") or {}).get("metadata") or {}
            online_labels = online_metadata.get("labels") or {}
            online_labels.update(info["add"])
            online_labels.update(info["update"])
            for label_key in info["delete"]:
                online_labels.pop(label_key, None)
            online_labels["$patch"] = "replace"
            # 写入操作
            k8s_resp = client.create_node_labels(info["ip"], online_labels)
            if k8s_resp.get("code") != ErrorCode.NoError:
                raise error_codes.APIError(k8s_resp.get("message"))

    def create_node_label_via_mesos(self, request, project_id, label_operation_map):
        """Mesos打tag"""
        # 调整为全量更新
        cluster_node_map = {}
        for node_id, info in label_operation_map.items():
            labels = info['add']
            labels.update(info['update'])
            labels.update(info['existed'])
            inner_ip = info['ip']
            cluster_id = info['cluster_id']
            # mesos 排除inner_ip这个key
            labels.pop('InnerIP', None)
            ip_label_info = {
                'innerIP': inner_ip,
                'disable': False,
                'strings': {key: {"value": val} for key, val in labels.items()},
            }
            if cluster_id in cluster_node_map:
                cluster_node_map[cluster_id].append(ip_label_info)
            else:
                cluster_node_map[cluster_id] = [ip_label_info]

        for cluster_id, ip_label_info in cluster_node_map.items():
            client = mesos.MesosClient(request.user.token.access_token, project_id, cluster_id, None)
            resp = client.update_agent_attrs(ip_label_info)
            if resp.get("code") != ErrorCode.NoError:
                raise error_codes.APIError(resp.get("message"))

    def create_or_update(self, request, project_id, label_operation_map):
        for node_id, info in label_operation_map.items():
            if info["new"]:
                # 创建之前先检查是否有删除的，然后替换
                node_label_obj = NodeLabel.objects.filter(node_id=node_id)
                if node_label_obj.exists():
                    node_label_obj.update(
                        creator=request.user.username,
                        project_id=project_id,
                        cluster_id=info["cluster_id"],
                        labels=json.dumps(info["add"]),
                        is_deleted=False,
                    )
                else:
                    NodeLabel.objects.create(
                        creator=request.user.username,
                        project_id=project_id,
                        cluster_id=info["cluster_id"],
                        node_id=node_id,
                        labels=json.dumps(info["add"]),
                    )
            else:
                node_label_info = NodeLabel.objects.get(node_id=node_id, is_deleted=False)
                existed_labels = json.loads(node_label_info.labels or "{}")
                existed_labels.update(info["add"])
                existed_labels.update(info["update"])
                for key in info["delete"]:
                    existed_labels.pop(key, None)
                node_label_info.updator = request.user.username
                node_label_info.labels = json.dumps(existed_labels)
                node_label_info.save()

    def create_node_labels(self, request, project_id):
        """添加节点标签"""
        project_kind = request.project["kind"]
        # 解析参数
        node_id_list, node_label_info = self.get_create_label_params(request)
        # 校验label中key和value
        self.label_regex(node_label_info, project_kind)
        # 获取数据库中节点的label
        # NOTE: 节点为正常状态时，才允许设置标签
        project_node_info = self.get_node_list(request, project_id, None).get('results') or []
        if not project_node_info:
            raise error_codes.APIError(_("当前项目下节点为空，请确认"))
        all_node_id_list = []
        all_node_id_ip_map = {}
        for info in project_node_info:
            all_node_id_list.append(info["id"])
            all_node_id_ip_map[info["id"]] = {"inner_ip": info["inner_ip"], "cluster_id": info["cluster_id"]}
            if info['id'] in node_id_list and info['status'] != CommonStatus.Normal:
                raise error_codes.CheckFailed(_("节点不是正常状态时，不允许设置标签"))
        diff_node_id_list = set(node_id_list) - set(all_node_id_list)
        if diff_node_id_list:
            raise error_codes.CheckFailed(_("节点ID [{}] 不属于当前项目，请确认").format(",".join(diff_node_id_list)))
        # 匹配数据
        pre_node_labels = self.get_labels_by_node(request, project_id, node_id_list)
        label_operation_map = self.get_label_operation(
            pre_node_labels, node_label_info, node_id_list, all_node_id_ip_map
        )
        # 针对k8s和mesos做不同的处理
        # k8s 是以节点为维度；mesos是label为维度
        if project_kind == 1:
            self.create_node_label_via_k8s(request, project_id, label_operation_map)
        else:
            self.create_node_label_via_mesos(request, project_id, label_operation_map)
        # 写入数据库
        self.create_or_update(request, project_id, label_operation_map)

        client.ContextActivityLogClient(
            project_id=project_id,
            user=request.user.username,
            resource_type="node",
            resource=str(node_id_list),
            resource_id=str(node_id_list),
            extra=json.dumps(node_label_info),
            description=_("节点打标签"),
        ).log_add(activity_status="succeed")
        return response.Response({"code": 0, "message": _("创建成功!")})


class NodeLabelListViewSet(NodeBase, NodeLabelBase, SystemViewSet):
    def compose_nodes(
        self, node_id_info: Dict, label_info: List, project_code: str, cluster_name_env: Dict, nodes: Dict
    ) -> List:
        # map for node id and node label
        label_info_dict = {info['node_id']: info for info in label_info}
        node_info_with_label = []
        # compose the node info
        for node_id, info in node_id_info.items():
            info['labels'] = []
            info['project_code'] = project_code
            info.update(cluster_name_env.get(info['cluster_id']) or {})
            label_info = label_info_dict.get(node_id)
            if label_info:
                label_slz = json.loads(label_info.get('labels') or '{}')
                label_list = [{key: val} for key, val in label_slz.items()]
                info['labels'] = label_list

            # 添加集群 host name和污点信息
            node_info = nodes.get(info["inner_ip"], {})
            info["host_name"] = node_info.get("host_name", "")
            info["taints"] = node_info.get("taints", {})

            node_info_with_label.append(info)
        return node_info_with_label

    def exclude_removed_status_node(self, data):
        node_id_info_map = {info['id']: info for info in data if info['status'] not in [NodeStatus.Removed]}
        return node_id_info_map

    def get_cluster_id(self, request):
        cluster_id = request.query_params.get('cluster_id')
        return None if cluster_id in ['all', None] else cluster_id

    def get_cluster_id_info_map(self, request, project_id):
        """get cluster info map
        format: {'cluster_id': {'cluster_name': xxx, 'cluster_env': xxx}}
        """
        data = self.get_all_cluster(request, project_id)
        results = data.get('results') or []
        return {
            info['cluster_id']: {
                'cluster_env': cluster_env_transfer(info['environment']),
                'cluster_name': info['name'],
            }
            for info in results
            if info.get('cluster_id')
        }

    def list(self, request, project_id):
        # get cluster id by request
        cluster_id = self.get_cluster_id(request)
        # get node info
        node_list = self.get_node_list(request, project_id, cluster_id)
        node_list = node_list.get('results') or []
        if not node_list:
            return response.Response({'code': 0, 'result': []})
        node_id_info_map = self.exclude_removed_status_node(node_list)
        # get node labels
        node_label_list = self.get_labels_by_node(request, project_id, node_id_info_map.keys())
        # render cluster id, cluster name and cluster environment
        cluster_name_env = self.get_cluster_id_info_map(request, project_id)
        # 获取节点的taint
        ctx_cluster = CtxCluster.create(token=request.user.token.access_token, id=cluster_id, project_id=project_id)
        nodes = query_cluster_nodes(ctx_cluster)
        node_list = self.compose_nodes(
            node_id_info_map, node_label_list, request.project['english_name'], cluster_name_env, nodes
        )
        # add perm for node
        nodes_results = bcs_perm.Cluster.hook_perms(request, project_id, node_list)

        return response.Response({'count': len(node_list), 'results': nodes_results})


class RescheduleNodePods(NodeBase, viewsets.ViewSet):
    renderer_classes = (BKAPIRenderer, BrowsableAPIRenderer)
    permission = ClusterPermission()

    def validate_node_status(self, node_info):
        # NOTE: 需要注意，mesos not ready 状态需要list/watch功能上线后，支持
        if node_info.get('status') not in [NodeStatus.ToRemoved, NodeStatus.Removable, NodeStatus.NotReady]:
            raise ValidationError(_("节点必须为不可调度状态，请点击【停止调度】按钮！"))

    def reschedule_pods_taskgroups(self, request, project_id, cluster_id, node_info):
        project_kind = self.request.project['kind']
        driver = BaseDriver(project_kind).driver(request, project_id, cluster_id)
        driver.reschedule_host_pods(node_info['inner_ip'], raise_exception=False)

    def put(self, request, project_id, cluster_id, node_id):
        """重新调度节点上的POD or Taskgroup
        主要目的是由于主机裁撤或者机器故障，需要替换机器
        步骤:
        1. 停止节点调度(前置条件)
        2. 查询节点上的所有pod
        3. 重新调度
        """
        # 权限校验
        perm_ctx = ClusterPermCtx(username=request.user.username, project_id=project_id, cluster_id=cluster_id)
        self.permission.can_manage(perm_ctx)

        node_info = self.get_node_by_id(request, project_id, cluster_id, node_id)
        # 检查节点状态，节点必须处于停止调度状态
        self.validate_node_status(node_info)
        project_name = request.project.project_name
        inner_ip = node_info["inner_ip"]
        log_desc = f"project: {project_name}, cluster: {cluster_id}, node: {inner_ip}, reschedule pods"
        with client.ContextActivityLogClient(
            project_id=project_id,
            user=request.user.username,
            resource_type='node',
            resource=node_info['inner_ip'],
            resource_id=node_id,
            description=log_desc,
        ).log_modify():
            # reschedule the pod or taskgroup
            self.reschedule_pods_taskgroups(request, project_id, cluster_id, node_info)
        return response.Response(
            {"code": 0, "message": "task started, please pay attention to the change of container count"}
        )


class NodeForceDeleteViewSet(NodeBase, NodeLabelBase, viewsets.ViewSet):
    renderer_classes = (BKAPIRenderer, BrowsableAPIRenderer)
    permission = ClusterPermission()

    def delete(self, request, project_id, cluster_id, node_id):
        """强制删除节点"""
        # 权限校验
        perm_ctx = ClusterPermCtx(username=request.user.username, project_id=project_id, cluster_id=cluster_id)
        self.permission.can_manage(perm_ctx)

        self.delete_node_label(request, node_id)
        node_client = node.DeleteNode(request, project_id, cluster_id, node_id)
        return node_client.force_delete()

    def delete_oper(self, request, project_id, cluster_id, node_id):
        """强制删除节点
        1. 判断是否已经停用，如果没有停用进行停止调度操作
        2. 如果有pod/taskgroup，删除上面的pod/taskgroup
        3. 调用移除节点
        """
        self.delete_node_label(request, node_id)
        node_client = node.DeleteNode(request, project_id, cluster_id, node_id)
        return node_client.force_delete()


class BatchUpdateDeleteNodeViewSet(NodeGetUpdateDeleteViewSet):
    renderer_classes = (BKAPIRenderer, BrowsableAPIRenderer)
    permission = ClusterPermission()

    def get_request_params(self, request):
        slz = node_serializers.BatchUpdateNodesSLZ(data=request.data)
        slz.is_valid(raise_exception=True)
        return slz.validated_data

    def get_node_without_removed(self, node_list):
        node_list = [node for node in node_list if node['status'] != CommonStatus.Removed]
        if not node_list:
            raise error_codes.CheckFailed('there are not node in cluster')
        return node_list

    def get_oper_node_info(self, node_list, req_node_id_list, req_status):
        exist_node_list = []
        for info in node_list:
            curr_node_status = info.get('status')
            info['status'] = req_status
            # check node belong to the cluster and allow to operate
            if info['id'] in req_node_id_list:
                exist_node_list.append(info)
                self.allow_oper_node(info, curr_node_status)
        if len(exist_node_list) != len(req_node_id_list):
            raise error_codes.CheckFailed('many nodes do not belong the cluster')
        return exist_node_list

    def get_node_ips_and_ids(self, node_list):
        """get ips, ids for activity log
        restrict the length
        """
        id_list = []
        ip_list = []
        for info in node_list:
            id_list.append(str(info['id']))
            ip_list.append(info['inner_ip'])
        return ip_list, id_list

    def node_list_handler(self, request, project_id, cluster_id, node_list):
        for info in node_list:
            self.node_handler(request, project_id, cluster_id, info)

    def update_nodes_status(self, request, project_id, cluster_id, node_list, ip_list):
        driver = BaseDriver(request.project['kind']).driver(request, project_id, cluster_id)
        node_container_data = driver.get_host_container_count(ip_list)
        update_data = []
        for info in node_list:
            curr_node_container_count = node_container_data.get(info['inner_ip']) or 0
            if curr_node_container_count == 0 and info['status'] == NodeStatus.ToRemoved:
                info['status'] = NodeStatus.Removable
            update_data.append({'inner_ip': info['inner_ip'], 'status': info['status']})
        resp = paas_cc.update_node_list(request.user.token.access_token, project_id, cluster_id, data=update_data)
        if resp.get('code') != ErrorCode.NoError:
            raise error_codes.APIError(resp.get('message'))
        return resp.get('data') or []

    def batch_update_nodes(self, request, project_id, cluster_id):
        """批量操作节点，允许调度/停止调度"""
        # 权限校验
        perm_ctx = ClusterPermCtx(username=request.user.username, project_id=project_id, cluster_id=cluster_id)
        self.permission.can_manage(perm_ctx)

        params = self.get_request_params(request)
        # check node for operation
        node_list = self.get_node_list(request, project_id, cluster_id)
        node_list = node_list.get('results') or []
        node_list = self.get_node_without_removed(node_list)
        node_list = self.get_oper_node_info(node_list, params['node_id_list'], params['status'])
        project_name = request.project['project_name']
        # get update node ip and id, in order to render the activity
        req_ip_list, req_id_list = self.get_node_ips_and_ids(node_list)
        req_ip_str = ','.join(req_ip_list)
        # 记录node的操作，这里包含disable: 停止调度，enable: 允许调度
        # 根据状态进行判断，当前端传递的是normal时，是要允许调度，否则是停止调度
        operate = "enable" if params["status"] == NodeStatus.Normal else "disable"
        log_desc = f'project: {project_name}, cluster: {cluster_id}, {operate} node: {req_ip_str}'
        with client.ContextActivityLogClient(
            project_id=project_id,
            user=request.user.username,
            resource_type='node',
            resource=req_ip_str[:200],
            resource_id=','.join(req_id_list)[:200],
            description=log_desc,
        ).log_modify():
            self.node_list_handler(request, project_id, cluster_id, node_list)
            # update node status for bcs cc
            data = self.update_nodes_status(request, project_id, cluster_id, node_list, req_ip_list)

        return response.Response(data)

    def get_delete_params(self, request):
        slz = node_serializers.BatchDeleteNodesSLZ(data=request.data)
        slz.is_valid(raise_exception=True)
        return slz.validated_data

    def get_delete_status(self, force_delete=False):
        """compose the status, in order to allow to delete node"""
        delete_status_list = [
            NodeStatus.Removable,
            NodeStatus.RemoveFailed,
            NodeStatus.InitialFailed,
            CommonStatus.ScheduleFailed,
        ]
        if force_delete:
            delete_status_list.append(NodeStatus.ToRemoved)
        return delete_status_list

    def delete_nodes(self, node_list, req_node_id_list, force_delete=False):
        """
        NOTE: node status must be in removeable, removefailed, initialfailed and schedulefailed
        """
        delete_node_status_list = self.get_delete_status(force_delete=force_delete)
        exist_node_list = []
        illegle_status_nodes = []
        # check node exist and status
        for info in node_list:
            # check node belong to the cluster and allow to operate
            if info['id'] in req_node_id_list:
                if info['status'] not in delete_node_status_list:
                    illegle_status_nodes.append(info)
                    continue
                exist_node_list.append(info)
        if illegle_status_nodes:
            raise ValidationError(_("请先确认节点处于【不可调度】状态并且节点上业务的POD数量等于0，然后再执行删除"))
        if len(exist_node_list) != len(req_node_id_list):
            raise ValidationError(_("节点不属于当前集群，请确认后重试"))

        return exist_node_list

    def delete_flow(self, request, project_id, cluster_id, node_list):
        cluster_info = self.get_cluster(request, project_id, cluster_id)
        ip_list, id_list = self.get_node_ips_and_ids(node_list)
        project_name = request.project['project_name']
        req_ip_str = ','.join(ip_list)
        log_desc = f'project: {project_name}, cluster: {cluster_info["name"]}, delete nodes: {req_ip_str}'
        with client.ContextActivityLogClient(
            project_id=project_id,
            user=request.user.username,
            resource_type='node',
            resource=req_ip_str[:200],
            resource_id=','.join(id_list)[:200],
            description=log_desc,
        ).log_delete():
            cluster_utils.delete_node_labels_record(NodeLabel, id_list, request.user.username)
            node_client = node.BatchDeleteNode(request, project_id, cluster_id, node_list)
            node_client.delete_nodes()
        return

    def batch_delete_nodes(self, request, project_id, cluster_id):
        """批量操作节点 删除"""
        # 权限校验
        perm_ctx = ClusterPermCtx(username=request.user.username, project_id=project_id, cluster_id=cluster_id)
        self.permission.can_manage(perm_ctx)

        data = self.get_delete_params(request)
        # get node list
        node_list_info = self.get_node_list(request, project_id, cluster_id)
        node_list = self.get_node_without_removed(node_list_info.get('results') or [])
        node_list = self.delete_nodes(node_list, data['node_id_list'])
        self.delete_flow(request, project_id, cluster_id, node_list)
        # start delete flow by bcs
        return response.Response()
