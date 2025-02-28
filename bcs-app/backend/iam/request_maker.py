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
import importlib
import logging

from .perm_maker import make_perm_ctx
from .permissions.request import ResourceRequest

logger = logging.getLogger(__name__)


def make_res_request(res_type: str, **ctx_kwargs) -> ResourceRequest:
    p_module_name = __name__[: __name__.rfind(".")]
    try:
        res_request_cls = getattr(
            importlib.import_module(f'{p_module_name}.permissions.resources'), f'{res_type.capitalize()}Request'
        )
    except (ModuleNotFoundError, AttributeError) as e:
        logger.error('make_res_request error: %s', e)
        raise

    perm_ctx = make_perm_ctx(res_type, **ctx_kwargs)
    return res_request_cls(perm_ctx.resource_id, **ctx_kwargs)
