<template>
    <div class="biz-content">
        <biz-header ref="commonHeader"
            @exception="exceptionHandler"
            @saveDeploymentSuccess="saveDeploymentSuccess"
            @switchVersion="initResource">
        </biz-header>
        <template>
            <div class="biz-content-wrapper biz-confignation-wrapper" v-bkloading="{ isLoading: isTemplateSaving }">
                <app-exception
                    v-if="exceptionCode && !isDataLoading"
                    :type="exceptionCode.code"
                    :text="exceptionCode.msg">
                </app-exception>
                <div class="biz-tab-box" v-else v-show="!isDataLoading">
                    <biz-tabs @tab-change="tabResource" ref="commonTab"></biz-tabs>
                    <div class="biz-tab-content" v-bkloading="{ isLoading: isTabChanging }">
                        <template v-if="!deployments.length">
                            <p class="biz-template-tip f12 mb10">
                                {{$t('Deployment是基于bcs-application抽象出的顶层概念，主要满足应用的滚动升级、回滚、暂停、扩缩容等需求')}}，<a class="bk-text-button" :href="PROJECT_CONFIG.doc.mesosDeployment" target="_blank">{{$t('详情查看文档')}}</a>
                            </p>
                            <div class="biz-guide-box mt0" style="padding: 140px 30px;">
                                <bk-button type="primary" @click.stop.prevent="addLocalDeployment">
                                    <i class="bcs-icon bcs-icon-plus"></i>
                                    <span style="margin-left: 0;">{{$t('添加')}}Deployment</span>
                                </bk-button>
                            </div>
                        </template>
                        <template v-else>
                            <div class="biz-configuration-topbar">
                                <p class="biz-template-tip f12 mb10">
                                    {{$t('Deployment是基于bcs-application抽象出的顶层概念，主要满足应用的滚动升级、回滚、暂停、扩缩容等需求')}}，<a class="bk-text-button" :href="PROJECT_CONFIG.doc.mesosDeployment" target="_blank">{{$t('详情查看文档')}}</a>
                                </p>
                                <div class="biz-list-operation">
                                    <div class="item" v-for="(deployment, index) in deployments" :key="deployment.id">
                                        <bk-button :class="['bk-button', { 'bk-primary': curDeployment.id === deployment.id }]" @click.stop="setCurDeployment(deployment, index)">
                                            {{(deployment && deployment.name) || $t('未命名')}}
                                            <span class="biz-update-dot" v-show="deployment.isEdited"></span>
                                        </bk-button>
                                        <span class="bcs-icon bcs-icon-close" @click.stop="removeDeployment(deployment, index)"></span>
                                    </div>

                                    <bcs-popover ref="deployTooltip" :content="$t('添加Deployment')" placement="top">
                                        <bk-button class="bk-button bk-default is-outline is-icon" @click.stop="addLocalDeployment">
                                            <i class="bcs-icon bcs-icon-plus"></i>
                                        </bk-button>
                                    </bcs-popover>
                                </div>
                            </div>

                            <div class="biz-configuration-content">
                                <div class="bk-form biz-configuration-form">
                                    <div class="bk-form-item is-required">
                                        <label class="bk-label" style="width: 110px;">{{$t('名称')}}：</label>
                                        <div class="bk-form-content" style="margin-left: 110px;">
                                            <div class="bk-dropdown-box" style="width: 310px;">
                                                <input type="text" :placeholder="$t('请输入64个以内的字符')" maxlength="64" :class="['bk-form-input', { 'is-danger': errors.has('deploymentName') }]" v-model="curDeployment.name" name="deploymentName" v-validate="{ required: true, regex: /^[a-z]{1}[a-z0-9-]{0,63}$/ }">
                                                <div class="bk-form-tip" v-if="errors.has('deploymentName')">
                                                    <p class="bk-tip-text">{{$t('名称必填，以字母开头，只能含小写字母、数字、连字符(-)')}}</p>
                                                </div>
                                            </div>
                                        </div>
                                    </div>
                                    <div class="bk-form-item is-required">
                                        <label class="bk-label" style="width: 110px;">{{$t('关联')}}：</label>
                                        <div class="bk-form-content" style="margin-left: 110px;">
                                            <div class="bk-dropdown-box" style="width: 310px;" @click="reloadApplications">
                                                <bk-selector
                                                    :placeholder="$t('请选择要关联的Application')"
                                                    :setting-key="'app_id'"
                                                    :display-key="'app_name'"
                                                    :selected.sync="curDeployment.app_id"
                                                    :list="applicationList"
                                                    :is-loading="isLoadingApps">
                                                </bk-selector>
                                            </div>
                                            <span class="biz-guard-tip ml10" v-if="!isDataLoading && !applicationList.length">{{$t('请先配置Application，再进行关联')}}</span>
                                        </div>
                                    </div>
                                    <div class="bk-form-item">
                                        <label class="bk-label" style="width: 110px;">{{$t('描述')}}：</label>
                                        <div class="bk-form-content" style="margin-left: 110px;">
                                            <textarea name="" id="" cols="30" rows="10" class="bk-form-textarea" :placeholder="$t('请输入50个以内的字符')" maxlength="50" v-model="curDeployment.desc"></textarea>
                                        </div>
                                    </div>
                                </div>

                                <div class="biz-span">
                                    <span class="title">{{$t('升级策略')}}</span>
                                </div>

                                <div class="bk-form biz-configuration-form">
                                    <div class="bk-form-item">
                                        <label class="bk-label" style="width: 110px;">{{$t('类型')}}：</label>
                                        <div class="bk-form-content" style="margin-left: 110px;">
                                            <bk-radio-group v-model="curDeployment.config.strategy.type">
                                                <bk-radio :value="'RollingUpdate'">{{$t('滚动升级')}}</bk-radio>
                                                <bk-radio :value="'Recreate'" :disabled="true">{{$t('重新创建')}}</bk-radio>
                                            </bk-radio-group>
                                        </div>
                                    </div>
                                    <div class="bk-form-item">
                                        <label class="bk-label" style="width: 110px;">{{$t('周期删除数')}}：</label>
                                        <div class="bk-form-content" style="margin-left: 110px;">
                                            <bkbcs-input
                                                type="number"
                                                :placeholder="$t('请输入')"
                                                style="width: 250px;"
                                                :min="0"
                                                :value.sync="curDeployment.config.strategy.rollingupdate.maxUnavilable"
                                                :list="varList">
                                            </bkbcs-input>
                                            <bcs-popover width="450" :content="$t('决定了每个rolling周期内可以删除的taskgroup数量。如果原有的taskgroup已经全部删除，则后续每一次rolling中不会再删除taskgroup')" placement="top">
                                                <span class="bk-badge">
                                                    <i class="bcs-icon bcs-icon-question-circle"></i>
                                                </span>
                                            </bcs-popover>
                                        </div>
                                    </div>

                                    <div class="bk-form-item">
                                        <label class="bk-label" style="width: 110px;">{{$t('周期新增数')}}：</label>
                                        <div class="bk-form-content" style="margin-left: 110px;">
                                            <bkbcs-input
                                                type="number"
                                                :placeholder="$t('请输入')"
                                                style="width: 250px;"
                                                :min="0"
                                                :value.sync="curDeployment.config.strategy.rollingupdate.maxSurge"
                                                :list="varList"
                                            >
                                            </bkbcs-input>
                                        </div>
                                    </div>
                                    <div class="bk-form-item">
                                        <label class="bk-label" style="width: 110px;">{{$t('更新间隔')}}：</label>
                                        <div class="bk-form-content" style="margin-left: 110px;">
                                            <div class="bk-form-input-group">
                                                <bkbcs-input
                                                    type="number"
                                                    :placeholder="$t('请输入')"
                                                    style="width: 215px;"
                                                    :min="0"
                                                    :value.sync="curDeployment.config.strategy.rollingupdate.upgradeDuration"
                                                    :list="varList"
                                                >
                                                </bkbcs-input>
                                                <span class="input-group-addon">
                                                    {{$t('秒')}}
                                                </span>
                                            </div>
                                        </div>
                                    </div>
                                    <div class="bk-form-item">
                                        <label class="bk-label" style="width: 110px;">{{$t('滚动顺序')}}：</label>
                                        <div class="bk-form-content" style="margin-left: 110px;">
                                            <bk-radio-group v-model="curDeployment.config.strategy.rollingupdate.rollingOrder">
                                                <bk-radio :value="'CreateFirst'">{{$t('滚动升级')}}</bk-radio>
                                                <bk-radio :value="'DeleteFirst'">{{$t('先删除')}}</bk-radio>
                                            </bk-radio-group>
                                        </div>
                                    </div>
                                    <div class="bk-form-item">
                                        <label class="bk-label" style="width: 110px;">{{$t('手动更新')}}：</label>
                                        <div class="bk-form-content" style="margin-left: 110px;">
                                            <bk-radio-group v-model="curDeployment.config.strategy.rollingupdate.rollingManually">
                                                <bk-radio :value="true">{{$t('是')}}</bk-radio>
                                                <bk-radio :value="false">{{$t('否')}}</bk-radio>
                                            </bk-radio-group>
                                        </div>
                                    </div>
                                </div>
                            </div>
                        </template>
                    </div>
                </div>
            </div>
        </template>
    </div>
</template>

<script>
    import deploymentParams from '@open/json/deployment.json'
    import header from './header.vue'
    import tabs from './tabs.vue'

    export default {
        async beforeRouteLeave (to, from, next) {
            // 修改模板集信息
            // await this.$refs.commonHeader.saveTemplate()
            clearInterval(this.compareTimer)
            next(true)
        },
        components: {
            'biz-header': header,
            'biz-tabs': tabs
        },
        data () {
            return {
                isTabChanging: false,
                exceptionCode: null,
                isDataLoading: true,
                isDataSaveing: false,
                curApplicationCache: Object.assign({}, deploymentParams), // 保存当前application初始状态
                compareTimer: 0, // 定时器，查看用户是否有修改
                curDeployment: deploymentParams,
                applicationList: [],
                numberIndex: -1,
                numberList: [],
                isLoadingApps: false,
                linkAppVersion: 0,
                setTimer: 0
            }
        },
        computed: {
            curTemplate () {
                return this.$store.state.mesosTemplate.curTemplate
            },
            varList () {
                return this.$store.state.variable.varList
            },
            isTemplateSaving () {
                return this.$store.state.mesosTemplate.isTemplateSaving
            },
            applications () {
                return this.$store.state.mesosTemplate.applications
            },
            deployments () {
                return this.$store.state.mesosTemplate.deployments
            },
            services () {
                return this.$store.state.mesosTemplate.services
            },
            configmaps () {
                return this.$store.state.mesosTemplate.configmaps
            },
            secrets () {
                return this.$store.state.mesosTemplate.secrets
            },
            curVersion () {
                return this.$store.state.mesosTemplate.curVersion
            },
            projectId () {
                return this.$route.params.projectId
            },
            templateId () {
                return this.$route.params.templateId
            }
        },
        watch: {
            'applications' () {
                if (this.curVersion) {
                    this.initApplications(this.curVersion)
                }
            }
        },
        mounted () {
            this.$refs.commonHeader.initTemplate((data) => {
                this.initResource(data)
                this.isDataLoading = false
            })
        },
        methods: {
            initResource (data) {
                const version = data.latest_version_id || data.version
                if (version) {
                    this.initApplications(version)
                }
                if (data.deployments && data.deployments.length) {
                    this.setCurDeployment(data.deployments[0], 0)
                } else if (data.deployment && data.deployment.length) {
                    this.setCurDeployment(data.deployment[0], 0)
                }
            },
            async tabResource (type, target) {
                this.isTabChanging = true
                await this.$refs.commonHeader.saveTemplate()
                await this.$refs.commonHeader.autoSaveResource(type)
                this.$refs.commonTab.goResource(target)
            },
            exceptionHandler (exceptionCode) {
                this.isDataLoading = false
                this.exceptionCode = exceptionCode
            },
            reloadApplications () {
                if (this.curVersion) {
                    this.isLoadingApps = true
                    this.initApplications(this.curVersion)
                }
            },
            initApplications (version) {
                const projectId = this.projectId
                this.linkAppVersion = version
                this.$store.dispatch('mesosTemplate/getApplicationsByVersion', { projectId, version }).then(res => {
                    const data = res.data
                    this.applicationList = data
                    this.isLoadingApps = false
                }, res => {
                    const message = res.message
                    this.$bkMessage({
                        theme: 'error',
                        message: message,
                        hasCloseIcon: true,
                        delay: 8000
                    })
                })
            },
            setCurDeployment (deployment, index) {
                this.curDeployment = deployment

                clearInterval(this.compareTimer)
                clearTimeout(this.setTimer)
                this.setTimer = setTimeout(() => {
                    if (!this.curDeployment.cache) {
                        this.curDeployment.cache = JSON.parse(JSON.stringify(deployment))
                    }
                    this.watchChange()
                }, 500)
            },
            watchChange () {
                this.compareTimer = setInterval(() => {
                    const appCopy = JSON.parse(JSON.stringify(this.curDeployment))

                    const cacheCopy = JSON.parse(JSON.stringify(this.curDeployment.cache))
                    // 删除无用属性
                    delete appCopy.isEdited
                    delete appCopy.cache
                    delete appCopy.id

                    delete cacheCopy.isEdited
                    delete cacheCopy.cache
                    delete cacheCopy.id

                    const appStr = JSON.stringify(appCopy)
                    const cacheStr = JSON.stringify(cacheCopy)
                    if (String(this.curDeployment.id).indexOf('local_') > -1) {
                        this.curDeployment.isEdited = true
                    } else if (appStr !== cacheStr) {
                        this.curDeployment.isEdited = true
                    } else {
                        this.curDeployment.isEdited = false
                    }
                }, 1500)
            },
            removeLocalDeployment (deployment, index) {
                // 是否删除当前项
                if (this.curDeployment.id === deployment.id) {
                    if (index === 0 && this.deployments[index + 1]) {
                        this.setCurDeployment(this.deployments[index + 1])
                    } else if (this.deployments[0]) {
                        this.setCurDeployment(this.deployments[0])
                    }
                }
                this.deployments.splice(index, 1)
            },
            removeDeployment (deployment, index) {
                const self = this
                const projectId = this.projectId
                const version = this.curVersion
                const deploymentId = deployment.id
                this.$bkInfo({
                    title: this.$t('确认删除'),
                    content: this.$createElement('p', { style: { 'text-align': 'left' } }, `${this.$t('删除Deployment')}：${deployment.name || this.$t('未命名')}`),
                    confirmFn () {
                        if (deploymentId.indexOf && deploymentId.indexOf('local_') > -1) {
                            self.removeLocalDeployment(deployment, index)
                        } else {
                            self.$store.dispatch('mesosTemplate/removeDeployment', { deploymentId, version, projectId }).then(res => {
                                const data = res.data
                                self.removeLocalDeployment(deployment, index)

                                if (data.version) {
                                    self.$store.commit('mesosTemplate/updateCurVersion', data.version)
                                    self.$store.commit('mesosTemplate/updateBindVersion', true)
                                }
                            }, res => {
                                const message = res.message
                                self.$bkMessage({
                                    theme: 'error',
                                    message: message
                                })
                            })
                        }
                    }
                })
            },
            saveDeploymentSuccess (params) {
                this.deployments.forEach(item => {
                    if (params.responseData.id === item.id || params.preId === item.id) {
                        item.cache = JSON.parse(JSON.stringify(item))
                    }
                })
                if (params.responseData.id === this.curDeployment.id || params.preId === this.curDeployment.id) {
                    this.updateLocalData(params.resource)
                }
            },
            updateLocalData (data) {
                if (data.id) {
                    this.curDeployment.id = data.id
                }
                if (data.version) {
                    this.$store.commit('mesosTemplate/updateCurVersion', data.version)
                }

                this.$store.commit('mesosTemplate/updateDeployments', this.deployments)

                setTimeout(() => {
                    this.deployments.forEach(item => {
                        if (item.id === data.id) {
                            this.setCurDeployment(item)
                        }
                    })
                }, 500)
            },
            createDeployment () {
                const version = this.curVersion
                const projectId = this.projectId
                const data = this.curDeployment
                this.$store.dispatch('mesosTemplate/addDeployment', { projectId, version, data }).then(res => {
                    const data = res.data
                    this.$bkMessage({
                        theme: 'success',
                        message: this.$t('数据保存成功')
                    })
                    this.updateLocalData(data)
                    this.isDataSaveing = false
                }, res => {
                    const message = res.message
                    this.$bkMessage({
                        theme: 'error',
                        message: message,
                        hasCloseIcon: true,
                        delay: '10000'
                    })
                    this.isDataSaveing = false
                })
            },
            createFirstDeployment () {
                const templateId = this.templateId
                const projectId = this.projectId
                const data = this.curDeployment
                this.$store.dispatch('mesosTemplate/addFirstDeployment', { projectId, templateId, data }).then(res => {
                    this.$bkMessage({
                        theme: 'success',
                        message: this.$t('数据保存成功')
                    })
                    this.updateLocalData(data)
                    this.isDataSaveing = false
                }, res => {
                    const message = res.message
                    this.$bkMessage({
                        theme: 'error',
                        message: message,
                        hasCloseIcon: true,
                        delay: '10000'
                    })
                    this.isDataSaveing = false
                })
            },
            updateDeployment () {
                const version = this.curVersion
                const projectId = this.projectId
                const data = this.curDeployment
                const deploymentId = this.curDeployment.id
                this.$store.dispatch('mesosTemplate/updateDeployment', { projectId, version, data, deploymentId }).then(res => {
                    const data = res.data
                    this.$bkMessage({
                        theme: 'success',
                        message: this.$t('数据保存成功')
                    })
                    this.updateLocalData(data)
                    this.isDataSaveing = false
                }, res => {
                    const message = res.message
                    this.$bkMessage({
                        theme: 'error',
                        message: message,
                        hasCloseIcon: true,
                        delay: '10000'
                    })
                    this.isDataSaveing = false
                })
            },
            checkData () {
                const deploymentName = this.curDeployment.name
                const appId = this.curDeployment.app_id
                const deploymentNameReg = /^[a-z]{1}[a-z0-9-]{0,63}$/
                if (deploymentName === '') {
                    this.$bkMessage({
                        theme: 'error',
                        message: this.$t('请输入名称')
                    })
                    return false
                }
                if (!deploymentNameReg.test(deploymentName)) {
                    this.$bkMessage({
                        theme: 'error',
                        message: this.$t('名称错误，只能包含：小写字母、数字、连字符(-)，必须是字母开头，长度小于64个字符'),
                        delay: 8000
                    })
                    return false
                }
                if (!appId) {
                    this.$bkMessage({
                        theme: 'error',
                        message: this.$t('请关联相应的Application')
                    })
                    return false
                }
                return true
            },
            saveDeployment () {
                if (!this.checkData()) {
                    return false
                }
                if (this.isDataSaveing) {
                    return false
                } else {
                    this.isDataSaveing = true
                }
                if (this.curVersion) {
                    if (this.curDeployment.id.indexOf && (this.curDeployment.id.indexOf('local') > -1)) {
                        this.createDeployment()
                    } else {
                        this.updateDeployment()
                    }
                } else {
                    this.createFirstDeployment()
                }
            },
            initDeploymentList () {
                const templateId = this.templateId
                const projectId = this.projectId
                const version = this.curTemplate.latest_version_id
                this.$store.dispatch('mesosTemplate/getTemplateResource', { projectId, templateId, version }).then(res => {
                    const data = res.data
                    if (data.version) {
                        this.$store.commit('mesosTemplate/updateCurVersion', data.version)
                    }
                    if (data.deployment) {
                        this.deployments.splice(0, this.deployments.length, ...data.deployment)
                        if (this.deployments.length === 0) {
                            // this.addLocalDeployment()
                        } else {
                            this.curDeployment = this.deployments[0]
                        }
                    } else {
                        this.deployments.splice(0, this.deployments.length)
                        // this.addLocalDeployment()
                    }

                    this.$store.commit('mesosTemplate/updateResources', data)
                    this.isDataLoading = false
                }, res => {
                    const message = res.message
                    this.$bkMessage({
                        theme: 'error',
                        message: message,
                        hasCloseIcon: true,
                        delay: '10000'
                    })
                    this.isDataLoading = false
                })
            },
            addLocalDeployment () {
                const deployment = JSON.parse(JSON.stringify(deploymentParams))
                const index = this.deployments.length
                const now = +new Date()

                deployment.id = 'local_' + now
                deployment.isEdited = true
                deployment.name = 'deployment-' + (index + 1)
                this.deployments.push(deployment)

                this.setCurDeployment(deployment, index)
                this.$refs.deployTooltip && (this.$refs.deployTooltip.visible = false)

                this.$store.commit('mesosTemplate/updateDeployments', this.deployments)
            }
        }
    }
</script>

<style scoped>
    @import './deployment.css';
</style>
