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
import sys

from ..base import *  # noqa
from ..base import BASE_DIR, REST_FRAMEWORK

REGION = "ce"

APP_ID = "bk_bcs_app"
APP_TOKEN = os.environ.get("APP_TOKEN")

# drf鉴权, 权限控制配置
REST_FRAMEWORK["DEFAULT_AUTHENTICATION_CLASSES"] = ("backend.utils.authentication.BKTokenAuthentication",)
REST_FRAMEWORK["DEFAULT_PERMISSION_CLASSES"] = (
    "rest_framework.permissions.IsAuthenticated",
    "backend.utils.permissions.HasIAMProject",
    "backend.utils.permissions.ProjectHasBCS",
)

ALLOWED_HOSTS = ["*"]

INSTALLED_APPS += [
    "backend.uniapps.apis",
    "backend.bcs_web.apis.apps.APIConfig",
    "iam.contrib.iam_migration",
    "backend.iam.bcs_iam_migration.apps.BcsIamMigrationConfig",
]

# 统一登录页面
LOGIN_FULL = ""
LOGIN_SIMPLE = ""

# 设置存储在 session 中的 token 一天后过期，默认为 5 分钟
BKAUTH_SESSION_TIMEOUT = 86400

# bkpaas_auth 模块会通过用户的 AccessToken 获取用户基本信息，因为这个 API 调用比较昂贵。
# 所以最好设置 Django 缓存来避免不必要的请求以提高效率。
CACHES = {
    "default": {
        "BACKEND": "django.core.cache.backends.filebased.FileBasedCache",
        "LOCATION": "/tmp/paas-backend-django_cache",
    },
}

REDIS_HOST = os.environ.get("REDIS_HOST", "127.0.0.1")
REDIS_PORT = os.environ.get("REDIS_PORT", 6379)
REDIS_DB = os.environ.get("REDIS_DB", 0)
REDIS_PASSWORD = os.environ.get("REDIS_PASSWORD", "")
REDIS_URL = os.environ.get("REDIS_URL", f"redis://:{REDIS_PASSWORD}@{REDIS_HOST}:{REDIS_PORT}/{REDIS_DB}")

# apigw 环境
APIGW_ENV = "test"
APIGW_PAAS_CC_ENV = "uat"
# ci部分apigw 环境
APIGW_CI_ENV = "prod"

# BK 环境的账号要单独申请
BK_JFROG_ACCOUNT_DOMAIN = "bk.artifactory.bking.com"
BK_JFROG_ACCOUNT_AUTH = ""

# ############### 模板开启后台参数验证
IS_TEMPLATE_VALIDATE = True
IS_CUP_LIMIT = False

# mesos 不同集群对应的apigw环境, 正式环境暂时没有
# key 是 cc 中的environment变量, value 是bcs API 环境
BCS_API_ENV = {
    "stag": "uat",
    "debug": "debug",
    "prod": "prod",
}

# 针对集群的环境
CLUSTER_ENV = {
    "stag": "debug",
    "prod": "prod",
}

# 创建CC module环境
CC_MODDULE_ENV = {
    "stag": "test",
    "prod": "pro",
    "debug": "debug",
}

# 返回给前端的cluster环境
CLUSTER_ENV_FOR_FRONT = {"debug": "stag", "prod": "prod"}

# 查询事务时的bcs环境
BCS_EVENT_ENV = ["prod"]

APIGW_PUBLIC_KEY = ""

# 是否开启K8S
OPEN_K8S = True
# 使用使用 k8s 直连地址
IS_K8S_DRIVER_NO_APIGW = False

# cache invalid
CACHE_VERSION = "v1"

# OP SYSTEM ENV
APIGW_OP_ENV = "test"

RUN_ENV = "prod"

# ############### 仓库API
# 默认使用正式环境
DEPOT_STAG = "prod"
# 镜像地址前缀
DEPOT_PREFIX = ""

# CI系统API地址
DEVOPS_CI_API_HOST = ""

# 应用访问路径
SITE_URL = "/"
ENVIRONMENT = os.environ.get("BK_ENV", "development")

# 运行模式， DEVELOP(开发模式)， TEST(测试模式)， PRODUCT(正式模式)
RUN_MODE = "DEVELOP"
if ENVIRONMENT.endswith("production"):
    RUN_MODE = "PRODUCT"
    DEBUG = False
    SITE_URL = f"/o/{APP_ID}/"
elif ENVIRONMENT.endswith("testing"):
    RUN_MODE = "TEST"
    DEBUG = False
    SITE_URL = f"/t/{APP_ID}/"
else:
    RUN_MODE = "DEVELOP"
    DEBUG = True

# 是否使用容器服务自身的TLS证书
IS_USE_BCS_TLS = True

# CELERY 配置
IS_USE_CELERY = True
# 本地使用Redis做broker
BROKER_URL_DEV = REDIS_URL

WEB_CONSOLE_PORT = int(os.environ.get("WEB_CONSOLE_PORT", 28800))

if IS_USE_CELERY:
    try:
        import djcelery

        INSTALLED_APPS += ("djcelery",)  # djcelery
        djcelery.setup_loader()
        CELERY_ENABLE_UTC = False
        CELERYBEAT_SCHEDULER = "djcelery.schedulers.DatabaseScheduler"
        if "celery" in sys.argv:
            DEBUG = False
        # celery 的消息队列（RabbitMQ）信息
        BROKER_URL = os.environ.get("BK_BROKER_URL", BROKER_URL_DEV)
        if RUN_MODE == "DEVELOP":
            from celery.signals import worker_process_init

            @worker_process_init.connect
            def configure_workers(*args, **kwargs):
                import django

                django.setup()

        from celery.schedules import crontab

        CELERY_BEAT_SCHEDULE = {
            # 为防止出现资源注册权限中心失败的情况，每天定时同步一次
            'bcs_perm_tasks': {
                'task': 'backend.accounts.bcs_perm.tasks.sync_bcs_perm',
                'schedule': crontab(minute=0, hour=2),
            },
            # 每天三点进行一次强制同步
            'helm_force_sync_repo_tasks': {
                'task': 'backend.helm.helm.tasks.force_sync_all_repo',
                'schedule': crontab(minute=0, hour=3),
            },
        }
    except Exception as error:
        print("use celery error: %s" % error)

# ******************************** Helm Config Begin ********************************
# kubectl 只有1.12版本
HELM_BASE_DIR = os.environ.get("HELM_BASE_DIR", BASE_DIR)
HELM_BIN = os.path.join(HELM_BASE_DIR, "bin/helm")  # helm bin filename
HELM3_BIN = os.path.join(HELM_BASE_DIR, "bin/helm3")
YTT_BIN = os.path.join(HELM_BASE_DIR, "bin/ytt")
KUBECTL_BIN = os.path.join(HELM_BASE_DIR, "bin/kubectl-v1.12.3")  # default kubectl bin filename
DASHBOARD_CTL_BIN = os.path.join(HELM_BASE_DIR, "bin/dashboard-ctl")  # default dashboard ctl filename
KUBECTL_BIN_MAP = {
    "1.8.3": os.path.join(HELM_BASE_DIR, "bin/kubectl-v1.12.3"),
    "1.12.3": os.path.join(HELM_BASE_DIR, "bin/kubectl-v1.12.3"),
    "1.14.9": os.path.join(HELM_BASE_DIR, "bin/kubectl-v1.14.9"),
    "1.16.3": os.path.join(HELM_BASE_DIR, "bin/kubectl-v1.16.3"),
    "1.18.12": os.path.join(HELM_BASE_DIR, "bin/kubectl-v1.18.12"),
}

# BKE企业版证书
BKE_CACERT = os.path.join(HELM_BASE_DIR, "etc/prod-server.crt")

BK_CC_HOST = os.environ.get("BK_CC_HOST", "")

STATIC_URL = "/staticfiles/"
SITE_STATIC_URL = SITE_URL + STATIC_URL.strip("/")

# 是否在中间件中统一输出异常信息
IS_COMMON_EXCEPTION_MSG = False
COMMON_EXCEPTION_MSG = ""

BK_PAAS_HOST = os.environ.get("BK_PAAS_HOST")
BK_PAAS_INNER_HOST = os.environ.get("BK_PAAS_INNER_HOST", BK_PAAS_HOST)
APIGW_HOST = BK_PAAS_INNER_HOST
# 组件API地址
COMPONENT_HOST = BK_PAAS_INNER_HOST

DEPOT_API = f"{APIGW_HOST}/api/apigw/harbor_api/"

# env map bcs https server host
BCS_CLUSTER_ENV_AND_HTTPS_SERVER_HOST = {"prod": os.environ.get("BKAPP_BCS_API_DOMAIN")}
# BCS API PRE URL
BCS_API_PRE_URL = f"{APIGW_HOST}/api/apigw/bcs_api"

BK_SSM_HOST = os.environ.get("BKAPP_SSM_HOST")

# BCS CC HOST
BCS_CC_API_PRE_URL = f"{APIGW_HOST}/api/apigw/bcs_cc/prod"

BK_IAM_HOST = os.environ.get("BKAPP_IAM_HOST")
# BCS IAM MIGRATION相关，用于初始资源数据到权限中心
APP_CODE = APP_ID
SECRET_KEY = APP_TOKEN
BK_IAM_SYSTEM_ID = APP_ID
BK_IAM_MIGRATION_APP_NAME = "bcs_iam_migration"
BK_IAM_RESOURCE_API_HOST = BK_PAAS_INNER_HOST or "http://paas.service.consul"
BK_IAM_INNER_HOST = BK_IAM_HOST

# 数据平台清洗URL
_URI_DATA_CLEAN = '%2Fs%2Fdata%2Fdataset%2Finfo%2F{data_id}%2F%23data_clean'
URI_DATA_CLEAN = f'{BK_PAAS_HOST}?app=data&url=' + _URI_DATA_CLEAN

# 项目功能白名单Code
PROJECT_FUNC_CODES = ["ServiceMonitor"]

# 覆盖上层base中的DIRECT_ON_FUNC_CODE: 直接开启的功能开关，不需要在db中配置
DIRECT_ON_FUNC_CODE = ["HAS_IMAGE_SECRET", "ServiceMonitor"]

# SOPS API HOST
SOPS_API_HOST = os.environ.get("SOPS_API_HOST")

# admin 权限用户
ADMIN_USERNAME = "admin"
# BCS 默认业务
BCS_APP_ID = 1

# 集群及节点metric功能白名单
CLUSTER_FUNC_CODES = ["MesosResource"]

# 社区版特殊配置
BCS_APP_CODE = APP_CODE
BCS_APP_SECRET = SECRET_KEY

# REPO 相关配置
HELM_REPO_DOMAIN = os.environ.get('HELM_REPO_DOMAIN')
HELM_MERELY_REPO_URL = HELM_REPO_DOMAIN
BK_REPO_URL_PREFIX = os.environ.get('BK_REPO_URL_PREFIX')
