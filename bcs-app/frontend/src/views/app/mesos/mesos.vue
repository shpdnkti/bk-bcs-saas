<template src="./tmpl-list.html"></template>

<script>
    import State from '../mesos-state'
    import mixinBaseList from '../mixins/mixin-base-list.mesos'

    export default {
        mixins: [mixinBaseList],
        data () {
            return {
                PROJECT_TYPE: 'MESOS',
                State,
                updateDialogConf: {
                    isShow: false,
                    width: 1050,
                    title: '',
                    closeIcon: true,
                    loading: false,
                    oldContent: '',
                    newContent: '',
                    oldVer: '',
                    verList: [],
                    selectedVerId: '',
                    instanceNum: '',
                    newVersion: {
                        instance_num: '',
                        instance_num_key: '',
                        instance_num_var_flag: false
                    },
                    oldVariableList: [],
                    newVariableList: [],
                    isShowVariable: false,
                    noDiffMsg: ''
                }
            }
        },
        methods: {
            /**
             * 跳转到模板实例化页面
             *
             * @param {Object} tmplMuster 当前模板集对象
             * @param {Object} tpl 当前模板对象
             */
            goInstantiation (tmplMuster, tpl) {
                this.$router.push({
                    name: 'mesosInstantiation',
                    params: {
                        projectId: this.projectId,
                        projectCode: this.projectCode,
                        templateId: tmplMuster.tmpl_muster_id,
                        category: tpl.category,
                        tmplAppId: tpl.tmpl_app_id,
                        tmplAppName: tpl.tmpl_app_name,
                        searchParamsList: this.searchParamsList
                    }
                })
            },

            /**
             * 跳转到实例详情页面
             *
             * @param {Object} instance 当前实例对象
             * @param {Object} namespace 当前 namespace 对象，只有命名空间试图才会有
             */
            async goInstanceDetail (instance, namespace) {
                if (!instance.permissions.view) {
                    const resourceList = [
                        {
                            policy_code: 'view',
                            resource_code: instance.namespace_id,
                            resource_name: instance.namespace,
                            resource_type: 'namespace'
                        }
                    ]
                    if (instance.from_platform) {
                        resourceList.push({
                            policy_code: 'view',
                            resource_code: instance.muster_id,
                            resource_name: instance.muster_name,
                            resource_type: 'templates'
                        })
                    }
                    await this.$store.dispatch('getMultiResourcePermissions', {
                        project_id: this.projectId,
                        operator: 'and',
                        resource_list: resourceList
                    })
                }

                const params = {
                    projectId: this.projectId,
                    projectCode: this.projectCode,
                    instanceId: instance.id,
                    templateId: instance.templateId,
                    instanceName: instance.name,
                    instanceNamespace: instance.namespace,
                    instanceCategory: instance.category,
                    searchParamsList: this.searchParamsList
                }

                if (namespace) {
                    params.namespaceId = namespace.id
                }

                this.$router.push({
                    name: instance.id === 0 ? 'instanceDetail2' : 'instanceDetail',
                    params,
                    query: {
                        cluster_id: instance.cluster_id
                    }
                })
            }
        }
    }
</script>

<style scoped>
    @import '../list.css';
</style>
