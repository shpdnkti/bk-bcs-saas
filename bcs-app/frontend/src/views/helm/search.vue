<template>
    <div class="biz-data-searcher">
        <template v-if="localScopeList.length">
            <template v-if="scopeDisabled">
                <bk-button class="bk-button trigger-btn disabled" style="max-width: 200px;">
                    <span class="btn-text tc">{{curScope.name}}</span>
                </bk-button>
            </template>
            <template v-else>
                <bk-selector
                    class="bk-search-selctor"
                    style="right: -2px;"
                    :placeholder="$t('请选择')"
                    :search-placeholder="$t('请选择集群')"
                    :searchable="true"
                    :setting-key="'id'"
                    :display-key="'name'"
                    :selected.sync="searchScope"
                    :list="scopeList"
                    v-if="!clusterFixed"
                    @change="handleTest"
                    @item-selected="handleSechScope">
                </bk-selector>
                <bk-selector
                    class="bk-search-selctor"
                    :key="searchScope"
                    :placeholder="$t('请选择命名空间')"
                    :search-placeholder="$t('请选择命名空间')"
                    :searchable="true"
                    :setting-key="'namespace_id'"
                    :display-key="'name'"
                    :selected.sync="searchNamespace"
                    :list="namespaceList"
                    :allow-clear="true"
                    @item-selected="handleSechNamespace"
                    @clear="namespaceClear">>
                </bk-selector>
            </template>
        </template>
        <div class="biz-search-input" style="width: 250px;">
            <bkbcs-input right-icon="bk-icon icon-search"
                clearable
                :placeholder="placeholderRender"
                v-model="localKey"
                @enter="handleSearch"
                @clear="clearSearch" />
        </div>
        <div class="biz-refresh-wrapper" v-if="widthRefresh">
            <bcs-popover class="refresh" :content="$t('刷新')" :delay="500" placement="top">
                <bk-button :class="['bk-button bk-default is-outline is-icon']" @click="handleRefresh">
                    <i class="bcs-icon bcs-icon-refresh"></i>
                </bk-button>
            </bcs-popover>
        </div>
    </div>
</template>

<script>
    // import { bkDropdownMenu } from '@open/components/bk-magic'

    export default {
        components: {
            // bkDropdownMenu
        },
        props: {
            placeholder: {
                type: String,
                default: ''
            },
            searchKey: {
                type: String,
                default: ''
            },
            searchScope: {
                type: String,
                default: ''
            },
            searchNamespace: {
                type: String,
                default: ''
            },
            widthRefresh: {
                type: Boolean,
                default: true
            },
            clusterFixed: {
                type: Boolean,
                default: false
            },
            scopeList: {
                type: Array,
                default () {
                    return []
                }
            },
            namespaceList: {
                type: Array,
                default () {
                    return []
                }
            },
            scopeDisabled: {
                type: Boolean,
                default: false
            },
            searchable: {
                type: Boolean,
                default: true
            }
        },
        data () {
            return {
                isTriggerSearch: false,
                isRefresh: false,
                localKey: this.searchKey,
                localScopeList: [],
                curScope: {
                    id: '',
                    name: this.$t('全部集群')
                },
                placeholderRender: '',
                keyword: ''
            }
        },
        watch: {
            searchKey (val) {
                this.localKey = val
            },
            scopeList () {
                this.initLocalScopeList()
            },
            localKey (newVal, oldVal) {
                // 如果删除，为空时触发搜索
                if (oldVal && !newVal && !this.isRefresh) {
                    this.clearSearch()
                }
            }
        },
        created () {
            this.initLocalScopeList()
            this.placeholderRender = this.placeholder || this.$t('输入关键字，按Enter搜索')
        },
        methods: {
            handleTest (oldVal, newVal) {
                console.log(newVal, oldVal)
            },
            handleSechScope (index, data) {
                this.curScope = data
                this.$emit('update:searchScope', this.curScope.id)
                this.$emit('update:searchNamespace', '')
                this.$emit('cluster-change')
                this.handleSearch()
            },
            handleSechNamespace (index, data) {
                this.$emit('update:searchNamespace', data.namespace_id)
                this.handleSearch()
            },
            namespaceClear () {
                this.$emit('update:searchNamespace', '')
                this.handleSearch()
            },
            initLocalScopeList () {
                this.localScopeList = JSON.parse(JSON.stringify(this.scopeList))
                if (this.localScopeList.length) {
                    // 在初始化时，如果已经有值，选中
                    const clusterId = this.searchScope || sessionStorage['bcs-cluster']
                    if (clusterId) {
                        const matchItem = this.localScopeList.find(item => item.id === clusterId)
                        if (matchItem) {
                            this.curScope = matchItem
                        } else {
                            this.curScope = this.localScopeList[0]
                        }
                    } else {
                        this.curScope = this.localScopeList[0]
                    }
                    
                    sessionStorage['bcs-cluster'] = this.curScope.id
                    this.$emit('update:searchScope', this.curScope.id)
                }
            },
            handleSearch () {
                this.isTriggerSearch = true
                this.$emit('update:searchKey', this.localKey)
                this.$emit('search')
                this.isRefresh = false
            },
            handleRefresh () {
                this.isRefresh = true
                this.$emit('refresh')
            },
            clearSearch () {
                this.localKey = ''
                if (this.isTriggerSearch) {
                    this.handleSearch()
                    this.isTriggerSearch = false
                }
            }
        }
    }
</script>

<style scoped lang="postcss">
    @import '@/css/mixins/clearfix.css';
    @import '@/css/mixins/ellipsis.css';
    .biz-data-searcher {
        font-size: 0;
        @mixin clearfix;

        .biz-search-input {
            .bk-form-input {
                border-radius: 0 2px 2px 0;
            }
        }

        .bk-dropdown-menu {
            .dropdown-item {
                > a {
                    width: 100%;
                    cursor: pointer;
                    display: inline-block;
                    vertical-align: middle;
                    @mixin ellipsis 240px;
                }
            }
            .bk-button {
                border-radius: 2px 0 0 2px;
                border-right: none;
            }
            float: left;
        }
    }
    .trigger-btn {
        &.disabled {
            margin-right: -10px;
            cursor: default;
            background: #fafafa;
        }
    }
    .btn-text {
        width: 140px;
        text-align: left;
        display: inline-block;
        vertical-align: middle;
        @mixin ellipsis 150px;
    }
    .bk-search-selctor {
        width: 180px;
        float: left;
        position: relative;
        right: -1px;
        z-index: 1;
        &:hover {
            z-index: 100;
        }
    }
</style>
