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
import os

from backend.components.apigw import get_api_public_key

logger = logging.getLogger(__name__)

# 项目类型映射
PROJECT_KIND_MAP = {"1": "k8s", "2": "mesos"}

# 类型映射
CATEGORY_MODULE_MAP = {
    "k8s": {
        "DaemonSet": "K8sDaemonSet",
        "Job": "K8sJob",
        "Deployment": "K8sDeployment",
        "StatefulSet": "K8sStatefulSet",
    },
    "mesos": {"Application": "application", "Deployment": "deployment"},
}

PAAS_CD_APIGW_PUBLIC_KEY = get_api_public_key("paas-cd", "bk_bcs", os.environ.get("BKAPP_BK_BCS_TOKEN"))

try:
    from .constants_ext import *  # noqa
except ImportError as e:
    logger.debug('Load extension failed: %s', e)
