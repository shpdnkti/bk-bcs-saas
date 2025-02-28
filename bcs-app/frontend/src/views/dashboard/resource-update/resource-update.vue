<template>
    <div class="biz-content resource-content">
        <div class="biz-top-bar">
            <span class="icon-wrapper" @click="handleCancel">
                <i class="bcs-icon bcs-icon-arrows-left icon-back"></i>
            </span>
            <div class="dashboard-top-title">
                {{ title }}
            </div>
            <DashboardTopActions />
        </div>
        <div :class="['resource-update', { 'full-screen': fullScreen }]">
            <template v-if="!showDiff">
                <div class="code-editor" ref="editorWrapperRef">
                    <div class="top-operate">
                        <span class="title bcs-ellipsis">{{ subTitle }}</span>
                        <span class="tools">
                            <span v-if="isEdit" v-bk-tooltips.top="$t('重置')" @click="handleReset"><i class="bcs-icon bcs-icon-reset"></i></span>
                            <span class="upload" v-bk-tooltips.top="$t('上传（仅支持YAML格式）')">
                                <input type="file" ref="fileRef" tabindex="-1" accept=".yaml,.yml" @change="handleFileChange">
                                <i class="bcs-icon bcs-icon-upload"></i>
                            </span>
                            <span :class="{ active: showExample }" v-bk-tooltips.top="$t('示例')" @click="handleToggleExample">
                                <i class="bcs-icon bcs-icon-code-example"></i>
                            </span>
                            <span v-bk-tooltips.top="fullScreen ? $t('缩小') : $t('放大')" @click="handleFullScreen">
                                <i :class="['bcs-icon', fullScreen ? 'bcs-icon-zoom-out' : 'bcs-icon-enlarge']"></i>
                            </span>
                        </span>
                    </div>
                    <ResourceEditor
                        v-model="detail"
                        :height="fullScreen ? '100%' : height"
                        ref="editorRef"
                        key="editor"
                        v-bkloading="{ isLoading, opacity: 1, color: '#1a1a1a' }"
                        @error="handleEditorErr">
                    </ResourceEditor>
                    <EditorStatus class="status-wrapper" :message="editorErr.message" v-show="!!editorErr.message"></EditorStatus>
                </div>
                <div class="code-example" ref="exampleWrapperRef" v-if="showExample">
                    <div class="top-operate">
                        <bk-dropdown-menu trigger="click" @show="isDropdownShow = true" @hide="isDropdownShow = false"
                            v-if="examples.items && examples.items.length">
                            <div class="dropdown-trigger-text" slot="dropdown-trigger">
                                <span class="title">{{ activeExample.alias }}</span>
                                <i :class="['bk-icon icon-angle-down',{ 'icon-flip': isDropdownShow }]"></i>
                                <span :class="['desc-icon',{ active: showDesc }]"
                                    v-bk-tooltips.top="$t('提示')"
                                    @click.stop="showDesc = !showDesc">
                                    <i class="bcs-icon bcs-icon-prompt"></i>
                                </span>
                            </div>
                            <ul class="bk-dropdown-list" slot="dropdown-content">
                                <li v-for="(item, index) in (examples.items || [])" :key="index" @click="handleChangeExample(item)">
                                    {{ item.alias }}
                                </li>
                            </ul>
                        </bk-dropdown-menu>
                        <span v-else><!-- 空元素为了flex布局 --></span>
                        <span class="tools">
                            <span v-bk-tooltips.top="$t('复制代码')" @click="handleCopy"><i class="bcs-icon bcs-icon-copy"></i></span>
                            <span v-bk-tooltips.top="$t('帮助')" @click="handleHelp"><i :class="['bcs-icon bcs-icon-help-2', { active: showHelp }]"></i></span>
                            <span v-bk-tooltips.top="$t('关闭')" @click="showExample = false"><i class="bcs-icon bcs-icon-close-5"></i></span>
                        </span>
                    </div>
                    <div class="example-desc" v-if="showDesc" ref="descWrapperRef">{{ activeExample.description }}</div>
                    <bcs-resize-layout :ext-cls="['custom-layout-cls', { 'hide-help': !showHelp }]"
                        :initial-divide="initialDivide"
                        :disabled="!showHelp"
                        :style="{ height: fullScreen ? '100%' : 'auto' }">
                        <ResourceEditor
                            slot="aside"
                            :value="activeExample.manifest"
                            :height="fullScreen ? '100%' : exampleEditorHeight"
                            :options="{
                                renderLineHighlight: 'none'
                            }"
                            key="example"
                            readonly
                            v-bkloading="{ isLoading: exampleLoading, opacity: 1, color: '#1a1a1a' }">
                        </ResourceEditor>
                        <bcs-md v-show="showHelp"
                            slot="main"
                            theme="dark"
                            class="references"
                            :style="{ height: fullScreen ? '100%' : exampleEditorHeight - 2 + 'px' }"
                            :code="examples.references" />
                    </bcs-resize-layout>
                </div>
            </template>
            <div class="code-diff" v-else>
                <div class="top-operate">
                    <span class="title">
                        {{ subTitle }}
                        <span class="insert ml15">+{{ diffStat.insert }}</span>
                        <span class="delete ml15">-{{ diffStat.delete }}</span>
                    </span>
                </div>
                <ResourceEditor
                    key="diff"
                    :value="detail"
                    :original="original"
                    :height="fullScreen ? '100%' : height"
                    :options="{
                        renderLineHighlight: 'none'
                    }"
                    diff-editor
                    readonly
                    @diff-stat="handleDiffStatChange">
                </ResourceEditor>
                <EditorStatus class="status-wrapper" :message="editorErr.message" v-show="!!editorErr.message"></EditorStatus>
            </div>
        </div>
        <div class="resource-btn-group">
            <div v-bk-tooltips.top="{ disabled: !disabledResourceUpdate, content: $t('内容未变更或格式错误') }">
                <bk-button theme="primary"
                    class="main-btn"
                    :loading="updateLoading"
                    :disabled="disabledResourceUpdate"
                    @click="handleCreateOrUpdate">
                    {{ btnText }}
                </bk-button>
            </div>
            <bk-button class="ml10" v-if="isEdit" @click="toggleDiffEditor">{{ showDiff ? $t('继续编辑') : $t('显示差异') }}</bk-button>
            <bk-button class="ml10" @click="handleCancel">{{ $t('取消') }}</bk-button>
        </div>
    </div>
</template>
<script lang="ts">
    /* eslint-disable no-unused-expressions */
    import { defineComponent, computed, toRefs, ref, onMounted, watch, onBeforeUnmount } from '@vue/composition-api'
    import ResourceEditor from './resource-editor.vue'
    import DashboardTopActions from '../common/dashboard-top-actions'
    import { copyText } from '@/common/util'
    import yamljs from 'js-yaml'
    import EditorStatus from './editor-status.vue'
    import BcsMd from '@open/components/bcs-md/index.vue'

    export default defineComponent({
        name: 'ResourceUpdate',
        components: {
            ResourceEditor,
            DashboardTopActions,
            EditorStatus,
            BcsMd
        },
        props: {
            // 命名空间（更新的时候需要--crd类型编辑是可能没有，创建的时候为空）
            namespace: {
                type: String,
                default: ''
            },
            // 父分类，eg: workloads、networks（注意复数）
            type: {
                type: String,
                default: '',
                required: true
            },
            // 子分类，eg: deployments、ingresses
            category: {
                type: String,
                default: ''
            },
            // 名称（更新的时候需要，创建的时候为空）
            name: {
                type: String,
                default: ''
            },
            kind: {
                type: String,
                default: ''
            },
            // type 为crd时，必传
            crd: {
                type: String,
                default: ''
            },
            defaultShowExample: {
                type: Boolean,
                default: false
            }
        },
        setup (props, ctx) {
            const { $i18n, $store, $bkMessage, $router, $bkInfo } = ctx.root
            const { namespace, type, category, name, kind, crd, defaultShowExample } = toRefs(props)

            onMounted(() => {
                document.addEventListener('keyup', handleExitFullScreen)
                handleGetDetail()
                handleGetExample()
                handleSetHeight()
            })

            const isEdit = computed(() => { // 编辑态
                return name.value
            })
            const title = computed(() => { // 导航title
                const prefix = isEdit.value ? $i18n.t('更新') : $i18n.t('创建')
                return `${prefix} ${kind.value}`
            })

            // ====1.代码编辑器相关逻辑====
            const editorWrapperRef = ref<Element|null>(null)
            const editorRef = ref<any>(null)
            const fileRef = ref<any>(null)
            const isLoading = ref(false)
            const original = ref<any>({})
            const detail = ref<any>({})
            const showExample = ref(defaultShowExample.value)
            const fullScreen = ref(false)
            const height = ref(600)
            const editorErr = ref({
                type: '',
                message: ''
            })
            const subTitle = computed(() => { // 代码编辑器title
                return detail.value?.metadata?.name || $i18n.t('资源定义')
            })
            watch(fullScreen, (value) => {
                // 退出全屏后隐藏侧栏帮助文档（防止位置错乱）
                if (!value) {
                    showHelp.value = false
                }
            })
            const disabledResourceUpdate = computed(() => { // 禁用当前更新或者创建操作
                if (editorErr.value.message && editorErr.value.type === 'content') { // 编辑器格式错误
                    return true
                }
                if (isEdit.value) {
                    return showDiff.value && !Object.keys(diffStat.value).some(key => diffStat.value[key])
                }
                return !Object.keys(detail.value).length
            })
            const setDetail = (data = {}) => { // 设置代码编辑器初始值
                detail.value = data
                editorRef.value?.setValue(Object.keys(detail.value).length ? detail.value : '')
            }
            const handleGetDetail = async () => { // 获取详情
                if (!isEdit.value) return null
                isLoading.value = true
                let res: any = null
                if (type.value === 'crd') {
                    res = await $store.dispatch('dashboard/retrieveCustomResourceDetail', {
                        $crd: crd.value,
                        $category: category.value,
                        $name: name.value,
                        namespace: namespace.value
                    })
                } else {
                    res = await $store.dispatch('dashboard/getResourceDetail', {
                        $namespaceId: namespace.value,
                        $category: category.value,
                        $name: name.value,
                        $type: type.value
                    })
                }
                original.value = JSON.parse(JSON.stringify(res.data?.manifest || {})) // 缓存原始值
                setDetail(res.data?.manifest)
                isLoading.value = false
                return detail.value
            }
            const handleEditorChange = (code) => {
                ctx.emit('change', code)
                ctx.emit('input', code)
            }
            const handleReset = async () => { // 重置代码编辑器
                if (isLoading.value || !isEdit.value) return

                $bkInfo({
                    type: 'warning',
                    clsName: 'custom-info-confirm',
                    title: $i18n.t('确认重置当前编辑状态'),
                    subTitle: $i18n.t('重置后，你修改的内容将丢失'),
                    defaultInfo: true,
                    confirmFn: () => {
                        editorErr.value = {
                            type: '',
                            message: ''
                        }
                        setDetail(JSON.parse(JSON.stringify(original.value)))
                    }
                })
            }
            const handleFileChange = (event) => { // 文件上传
                const [file] = event.target?.files || []
                if (!file) return

                const reader = new FileReader()
                reader.readAsText(file)
                reader.onload = () => {
                    setDetail(yamljs.load(reader.result))
                    fileRef.value && (fileRef.value.value = '')
                }
                reader.onerror = () => {
                    $bkMessage({
                        theme: 'error',
                        message: reader.error
                    })
                    fileRef.value && (fileRef.value.value = '')
                }
            }
            const handleToggleExample = () => { // 显示隐藏代码示例编辑器
                showExample.value = !showExample.value
            }
            const handleFullScreen = () => { // 全屏
                fullScreen.value = !fullScreen.value
                fullScreen.value && $bkMessage({
                    theme: 'primary',
                    message: $i18n.t('按Esc即可退出全屏模式')
                })
            }
            const handleExitFullScreen = (event: KeyboardEvent) => { // esc退出全屏
                if (event.code === 'Escape') {
                    fullScreen.value = false
                }
            }
            const handleEditorErr = (err: string) => { // 捕获编辑器错误提示
                editorErr.value.type = 'content' // 编辑内容错误
                editorErr.value.message = err
            }
            const handleSetHeight = () => {
                const bounding = editorWrapperRef.value?.getBoundingClientRect()
                height.value = bounding ? bounding.height - 40 : 600 // 40: 编辑器顶部操作栏高度
            }

            // ====2.代码示例相关逻辑====
            const isDropdownShow = ref(false)
            const activeExample = ref<any>({})
            const exampleLoading = ref(false)
            const examples = ref<any>({})
            const showDesc = ref(false)
            const showHelp = ref(false)
            const exampleWrapperRef = ref<Element|null>(null)
            const descWrapperHeight = ref(0)
            const descWrapperRef = ref<Element|null>(null)
            const exampleEditorHeight = computed(() => { // 代码示例高度
                return height.value - descWrapperHeight.value
            })
            const initialDivide = computed(() => showHelp.value ? '50%' : '100%')
            watch(showDesc, () => {
                setTimeout(() => { // dom更新后获取描述文字的高度
                    descWrapperHeight.value = showDesc.value ? descWrapperRef.value?.getBoundingClientRect()?.height || 0 : 0
                }, 0)
            })
            const handleGetExample = async () => { // 获取示例模板
                // if (!showExample.value) return

                exampleLoading.value = true
                examples.value = await $store.dispatch('dashboard/exampleManifests', {
                    kind: type.value === 'crd' ? 'CustomObject' : kind.value // crd类型的模板kind固定为CustomObject
                })
                activeExample.value = examples.value?.items?.[0] || {}
                exampleLoading.value = false
                return examples.value
            }
            const handleChangeExample = (item) => { // 示例模板切换
                activeExample.value = item
            }
            const handleCopy = () => { // 复制例子
                copyText(yamljs.dump(activeExample.value?.manifest))
                $bkMessage({
                    theme: 'success',
                    message: $i18n.t('复制示例成功')
                })
            }
            const handleHelp = () => {
                // 帮助文档
                showHelp.value = !showHelp.value
            }

            // 3.====diff编辑器相关逻辑====
            const showDiff = ref(false)
            const updateLoading = ref(false)
            const diffStat = ref({
                insert: 0,
                delete: 0
            })
            const handleDiffStatChange = (stat) => {
                diffStat.value = stat
            }

            // 4.====创建、更新、取消、显示差异====
            const btnText = computed(() => {
                if (!isEdit.value) return $i18n.t('创建')

                return showDiff.value ? $i18n.t('更新') : $i18n.t('下一步')
            })
            const toggleDiffEditor = () => { // 显示diff
                showDiff.value = !showDiff.value
            }
            const handleCreateResource = async () => {
                let result = false
                if (type.value === 'crd') {
                    result = await $store.dispatch('dashboard/customResourceCreate', {
                        $crd: crd.value,
                        $category: category.value,
                        manifest: detail.value
                    }).catch(err => {
                        editorErr.value.type = 'http'
                        editorErr.value.message = err.message
                        return false
                    })
                } else {
                    result = await $store.dispatch('dashboard/resourceCreate', {
                        $type: type.value,
                        $category: category.value,
                        manifest: detail.value
                    }).catch(err => {
                        editorErr.value.type = 'http'
                        editorErr.value.message = err.message
                        return false
                    })
                }

                if (result) {
                    $bkMessage({
                        theme: 'success',
                        message: $i18n.t('创建成功')
                    })
                    $router.push({ name: $store.getters.curNavName })
                }
            }
            const handleUpdateResource = () => {
                if (!showDiff.value) {
                    showDiff.value = true
                    return
                }

                $bkInfo({
                    type: 'warning',
                    clsName: 'custom-info-confirm',
                    title: $i18n.t('确认资源更新'),
                    subTitle: $i18n.t('将执行 Replace 操作，若多人同时编辑可能存在冲突'),
                    defaultInfo: true,
                    confirmFn: async () => {
                        let result = false
                        if (type.value === 'crd') {
                            result = await $store.dispatch('dashboard/customResourceUpdate', {
                                $crd: crd.value,
                                $category: category.value,
                                $name: name.value,
                                manifest: detail.value
                            }).catch(err => {
                                editorErr.value.type = 'http'
                                editorErr.value.message = err.message
                                return false
                            })
                        } else {
                            result = await $store.dispatch('dashboard/resourceUpdate', {
                                $namespaceId: namespace.value,
                                $type: type.value,
                                $category: category.value,
                                $name: name.value,
                                manifest: detail.value
                            }).catch(err => {
                                editorErr.value.type = 'http'
                                editorErr.value.message = err.message
                                return false
                            })
                        }

                        if (result) {
                            $bkMessage({
                                theme: 'success',
                                message: $i18n.t('更新成功')
                            })
                            $router.push({ name: $store.getters.curNavName })
                        }
                    }
                })
            }
            const handleCreateOrUpdate = async () => { // 更新或创建
                updateLoading.value = true
                if (isEdit.value) {
                    await handleUpdateResource()
                } else {
                    await handleCreateResource()
                }
                updateLoading.value = false
            }
            const handleCancel = () => { // 取消
                $bkInfo({
                    type: 'warning',
                    clsName: 'custom-info-confirm',
                    title: $i18n.t('确认退出当前编辑状态'),
                    subTitle: $i18n.t('退出后，你修改的内容将丢失'),
                    defaultInfo: true,
                    confirmFn: () => {
                        $router.push({ name: $store.getters.curNavName })
                    }
                })
            }

            onBeforeUnmount(() => {
                document.removeEventListener('keyup', handleExitFullScreen)
            })

            return {
                showDiff,
                isEdit,
                title,
                subTitle,
                original,
                detail,
                editorRef,
                isLoading,
                exampleLoading,
                isDropdownShow,
                activeExample,
                examples,
                showExample,
                showDesc,
                showHelp,
                initialDivide,
                fullScreen,
                height,
                disabledResourceUpdate,
                exampleEditorHeight,
                editorErr,
                updateLoading,
                diffStat,
                editorWrapperRef,
                exampleWrapperRef,
                descWrapperRef,
                fileRef,
                btnText,
                handleChangeExample,
                handleGetDetail,
                handleEditorChange,
                handleReset,
                handleFileChange,
                handleToggleExample,
                handleFullScreen,
                handleCopy,
                handleHelp,
                handleGetExample,
                handleEditorErr,
                toggleDiffEditor,
                handleCreateOrUpdate,
                handleCancel,
                handleDiffStatChange
            }
        }
    })
</script>
<style lang="postcss" scoped>
.resource-content {
    padding-bottom: 0;
    height: 100%;
    .icon-back {
        font-size: 16px;
        font-weight: bold;
        color: #3A84FF;
        margin-left: 20px;
        cursor: pointer;
    }
    .dashboard-top-title {
        display: inline-block;
        height: 60px;
        line-height: 60px;
        font-size: 16px;
        margin-left: 0px;
    }
    .resource-update {
        width: 100%;
        height: calc(100% - 120px);
        border-radius: 2px;
        display: flex;
        padding: 20px 20px 0 20px;
        &.full-screen {
            position: fixed;
            top: 0;
            right: 0;
            bottom: 0;
            left: 0;
            height: 100% !important;
            width: 100% !important;
            z-index: 100;
            padding: 0;
        }
        .top-operate {
            display: flex;
            align-items: center;
            justify-content: space-between;
            background: #2e2e2e;
            height: 40px;
            padding: 0 10px 0 16px;
            color: #c4c6cc;
            i {
                &:hover, &.active {
                    color: #699df4;
                }
            }
            .title {
                font-size: 14px;
            }
            .tools {
                display: flex;
                font-size: 16px;
                span {
                    width: 26px;
                    height: 26px;
                    margin-left: 5px;
                    cursor: pointer;
                    display: flex;
                    align-items: center;
                    justify-content: center;
                    &.active {
                        color: #699df4;
                        background: #242424;
                    }
                    &:hover {
                        color: #699df4;
                    }
                }
            }
        }
        .code-editor {
            flex: 1;
            width: 0;
            position: relative;
            .upload {
                position: relative;
                input {
                    width: 100%;
                    height: 100%;
                    position: absolute;
                    left: 0;
                    top: 0;
                    cursor: pointer;
                    opacity: 0;
                }
            }
            .status-wrapper {
                width: calc(100% - 14px)
            }
        }
        .code-example {
            flex: 1;
            width: 0;
            margin-left: 2px;
            /deep/ .dropdown-trigger-text {
                display: flex;
                align-items: center;
                justify-content: center;
                cursor: pointer;
                font-size: 14px;
                .icon-angle-down {
                    font-size: 20px;
                }
            }
            /deep/ .bk-dropdown-list {
                li {
                    height: 32px;
                    line-height: 32px;
                    padding: 0 16px;
                    color: #63656e;
                    font-size: 12px;
                    white-space: nowrap;
                    cursor: pointer;
                    &:hover {
                        background-color: #eaf3ff;
                        color: #3a84ff;
                    }
                }
            }
            .desc-icon {
                width: 26px;
                height: 26px;
                display: flex;
                align-items: center;
                justify-content: center;
                &.active {
                    color: #699df4;
                    background: #242424;
                }
            }
            .example-desc {
                background: #292929;
                border: 1px solid #141414;
                font-size: 12px;
                color: #b0b2b8;
                padding: 15px;
            }
            .custom-layout-cls {
                border: none;
                /deep/ {
                    .bk-resize-layout-aside {
                        border-color: #292929;
                        &:after {
                            right: -6px;
                        }
                    }
                }
                &.hide-help {
                    /deep/ .bk-resize-layout-aside:after {
                        display: none;
                    }
                }
            }
            /deep/ .bk-resize-layout-main {
                background-color: #1a1a1a;
            }
            .bcs-md-preview {
                background-color: #2e2e2e !important;
            }
            .references {
                margin: 1px;
            }
        }
        .code-diff {
            width: 100%;
            position: relative;
            .insert {
                color: #5e8a48;
            }
            .delete {
                color: #e66565;
            }
        }
    }
    .resource-btn-group {
        height: 60px;
        padding: 0 24px;
        display: flex;
        align-items: center;
        button {
            min-width: 80px;
        }
        .main-btn {
            min-width: 100px;
        }
    }
}
</style>
