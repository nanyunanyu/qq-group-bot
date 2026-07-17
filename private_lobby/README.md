# 私有 Citra/Yuzu 大厅

仅兼容当前 Citra Canary 2798 与 Yuzu Mainline 1734 房间容器的内部大厅服务。

## 接口

- `POST /jwt/internal`：旧房间程序换取 JWT
- `GET /jwt/external/key.pem`：房间获取玩家 JWT 校验公钥
- `POST /lobby`：注册房间
- `POST /lobby/{id}`：更新玩家列表
- `DELETE /lobby/{id}`：注销房间
- `GET /lobby`：机器人查询房间快照
- `GET /health`：健康检查

服务只应加入 Docker 内部网络，不应映射宿主机端口。房间状态保存在内存中；大厅重启后，房间收到更新 `404` 会自动重新注册。

## 本地测试

```bash
python3 -m venv .venv
.venv/bin/pip install -r requirements-dev.txt
LOBBY_SHARED_TOKEN=test-token LOBBY_KEY_DIRECTORY=/tmp/private-lobby-keys .venv/bin/pytest
```