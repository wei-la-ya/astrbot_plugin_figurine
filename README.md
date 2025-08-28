# 手办化 AstrBot 插件 (figurine) 基于调用openrouter API进行手办化的插件

将头像/图片“手办化”，支持 `手办化/2/3/4` 与 `Q版化`，可紧贴 QQ 号或使用 `@QQ`，统一在单条消息中返回图片与“预设：手办化X”。

## 特色
- 单条消息输出：图片 + `✅ 生成完成（Xs）｜预设：手办化X`
- 命令解析健壮：优先匹配更长命令，避免 `#手办化4` 被误解为 `#手办化` + QQ
- 头像/图片选择顺序：`@提及` > 命令 QQ > 回复/附图 > 发送者头像
- 持久化目录：`data/figurine`（安全、可备份）
- 网络请求：异步 `httpx`
- 提示词：单行、真实 prompt 反推预设名称

## 目录结构
```
astrbot_plugin_figurine/
  ├─ main.py
  ├─ star.json
  ├─ metadata.yaml
  ├─ _conf_schema.json
  ├─ requirements.txt
  ├─ LICENSE
  └─ README.md
```

## 安装
1) 将本目录放入 AstrBot 插件目录：`AstrBot/data/plugins/astrbot_plugin_figurine`
2) 安装依赖：
```bash
pip install -r astrbot_plugin_figurine/requirements.txt
```
3) 配置 OpenRouter Keys：`data/figurine/openrouter_keys.json`
前往 [openrouter 获取 key](https://openrouter.ai/settings/keys)
```json
{
  "keys": ["sk-or-v1_xxx"],
  "current": 0
}
```
4) 启动 AstrBot，在 WebUI 插件管理中 “重载插件”。

## 用法
- `#手办化`、`#手办化2`、`#手办化3`、`#手办化4`、`#Q版化`
- 可追加 QQ 号（无空格）：`#手办化4123456` 或 `#手办化4@123456`
- 也可在命令前后回复一张图片，自动取图

## 配置
- 面板可配置（见 `_conf_schema.json`）：
  - `use_proxy`：是否启用代理
  - `proxy_url`：代理地址（http/https）
  - `request_timeout_sec`：请求超时（秒）
- 按需求，`model` 与 `max_tokens` 已固定在 `main.py` 中。




## 许可
MIT
