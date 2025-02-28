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
from dataclasses import dataclass
from typing import List, Optional, Type

from backend.iam.permissions import decorators
from backend.iam.permissions.perm import PermCtx, Permission, ResCreatorActionCtx, ResourceRequest
from backend.iam.permissions.request import IAMResource
from backend.packages.blue_krill.data_types.enum import EnumField, StructuredEnum

from ..exceptions import AttrValidationError
from .constants import ResourceType


class ProjectAction(str, StructuredEnum):
    CREATE = EnumField('project_create', label='project_create')
    VIEW = EnumField('project_view', label='project_view')
    EDIT = EnumField('project_edit', label='project_edit')


class ProjectRequest(ResourceRequest):
    resource_type: str = ResourceType.Project


@dataclass
class ProjectCreatorActionCtx(ResCreatorActionCtx):
    resource_type: str = ResourceType.Project


@dataclass
class ProjectPermCtx(PermCtx):
    project_id: Optional[str] = None

    @property
    def resource_id(self) -> str:
        return self.project_id


class ProjectPermission(Permission):
    """项目权限"""

    resource_type: str = ResourceType.Project
    resource_request_cls: Type[ResourceRequest] = ProjectRequest

    def can_create(self, perm_ctx: ProjectPermCtx, raise_exception: bool = True) -> bool:
        return self.can_action(perm_ctx, ProjectAction.CREATE, raise_exception)

    def can_view(self, perm_ctx: ProjectPermCtx, raise_exception: bool = True) -> bool:
        perm_ctx.validate_resource_id()
        return self.can_action(perm_ctx, ProjectAction.VIEW, raise_exception)

    def can_edit(self, perm_ctx: ProjectPermCtx, raise_exception: bool = True) -> bool:
        perm_ctx.validate_resource_id()
        return self.can_action(perm_ctx, ProjectAction.EDIT, raise_exception)

    def get_parent_chain(self, perm_ctx: ProjectPermCtx) -> List[IAMResource]:
        return []

    def get_resource_id(self, perm_ctx: ProjectPermCtx) -> Optional[str]:
        return perm_ctx.project_id


class related_project_perm(decorators.RelatedPermission):

    module_name: str = ResourceType.Project

    def _convert_perm_ctx(self, instance, args, kwargs) -> PermCtx:
        """仅支持第一个参数是 PermCtx 子类实例"""
        if len(args) <= 0:
            raise TypeError('missing ProjectPermCtx instance argument')
        if isinstance(args[0], PermCtx):
            return ProjectPermCtx(username=args[0].username, project_id=args[0].project_id)
        else:
            raise TypeError('missing ProjectPermCtx instance argument')
