# Dify 接入指南（MCP SSE / StreamableHTTP）

WideHive MCP server 支持 SSE 与 StreamableHTTP 传输，可通过 Dify 官方的
**MCP SSE / StreamableHTTP 插件**（marketplace.dify.ai）接入 Dify 应用与工作流。

## 启动 SSE 传输

```bash
# 同机自托管 Dify：默认绑定 127.0.0.1 即可
python mcp/server.py --transport sse --port 8808

# 跨机访问：绑定 0.0.0.0 并配置反向代理（务必加认证后再公网暴露）
python mcp/server.py --transport sse --host 0.0.0.0 --port 8808
```

启动后端点为：`http://<host>:8808/sse`

## Dify 侧配置

1. Dify → **工具** → 安装插件 **MCP SSE / StreamableHTTP**（marketplace 官方插件）；
2. 插件配置中添加 server：URL 填 `http://<host>:8808/sse`（自托管同机用 `host.docker.internal` 或宿主机 IP）；
3. 授权：本地无认证版本留空即可；公网部署务必先加反代认证；
4. Dify 的 Agent / 工作流节点即可调用 widehive 的四个工具：
   `merge_results` / `diff_results` / `build_corpus` / `build_dashboard`。

## 推荐用法

- Agent 节点按 WideHive 编排规范（prompt 资源 `widehive_orchestration`）执行扇出与落盘；
- 每对象结果落盘后调用 `merge_results` 做零幻觉校验（PASS / NEEDS_RETRY 机读判定）；
- 定期跑 `diff_results` 可将 WideHive 变成 Dify 应用里的持续情报源。

## 安全注意

server 默认**无认证**（本地工具定位）。公网暴露前必须：反向代理 + 认证头
（`-H "Authorization: ..."` 透传）或 VPN/内网限制——见仓库 README 的安全注意节。
