## 1.组件与类型命名：大驼峰命名法（PascalCase）
所有 React 组件（包括函数组件、类组件）和 TypeScript 类型 / 接口必须使用大驼峰，例如UserProfile.tsx组件、interface UserInfo、type OrderStatus。
原因：React 组件在 JSX 中使用时类似 HTML 标签，大驼峰能清晰区分组件与原生标签（如<div>），TypeScript 类型也需要与变量形成视觉区分。

## 2.变量、函数与属性：小驼峰命名法（camelCase）
组件内部的变量、函数、props 属性等使用小驼峰，例如const userData = {}、function handleClick()、<Button isDisabled={true}>。
例外：React hooks 必须以use开头且遵循小驼峰，如useAuth()、useFetchData()，这是 React 官方约定的钩子识别规则。

## 3.目录结构：按功能 / 页面划分，辅以公共资源目录
核心目录划分原则：
src/pages/：存放页面级组件（与路由一一对应），如src/pages/Home/、src/pages/User/Profile.tsx。
src/components/：存放可复用组件，按粒度分为Common/（通用 UI 组件，如 Button、Input）和Business/（业务组件，如OrderCard）。
src/hooks/、src/utils/、src/types/：分别存放自定义钩子、工具函数、全局类型定义。
优势：避免按 “文件类型”（如components/、styles/）混放，使功能相关文件集中管理。

## 4.组件拆分：单一职责原则，区分展示型与容器型
展示型组件（Presentational）：仅负责 UI 渲染，通过 props 接收数据和回调，如src/components/Common/Avatar.tsx。
容器型组件（Container）：处理逻辑、数据获取，不直接渲染 UI，如src/pages/Dashboard/useDashboardData.ts（配合 hooks 实现）。
拆分标准：当一个组件超过 200 行代码，或同时包含复杂逻辑和大量 JSX 时，应考虑拆分。

## 5.文件命名：与组件 / 功能同名，使用大驼峰
组件文件：与组件名完全一致，如UserList.tsx（对应UserList组件）。
工具 / 类型文件：工具函数用小驼峰（如dateUtils.ts），类型定义用大驼峰（如ApiTypes.ts）。
索引文件：使用index.ts作为目录入口，简化导入路径（如import { Button } from '@/components/Common'）。