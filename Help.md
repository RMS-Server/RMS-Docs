# RMS帮助文档
_本页面意在整合公告中出现的帮助文档_

## Q&A

### 我无法连接至服务器？

- 请检查你的网络连接是否正常
- 请检查你的游戏版本，由于服务端为1.17.1，高版本(>1.21)Via存在问题，请降低版本连接
- 由于主域名采用SRV解析，部分DNS可能无法解析，请尝试使用`beiyong.rms.net.cn:5555`连接
- 依然存在问题请联系管理或者在[这里](https://feedback.rms.net.cn)反馈问题

### 提示未在白名单内

- 请确定已经申请了服务器白名单并且已经通过审核（添加白名单[点我](https://wl.rms.net.cn)）
- 依然存在问题请联系管理或者在[这里](https://feedback.rms.net.cn)反馈问题

## 关于迁移小地图路径点的方法
_该方法仅适用于Xaero地图_
> 假设原服务器为`example.com`，新服务器为`game.rmsmcserver.ltd`

1. 首先打开你的 `.minecraft` 文件夹

2. 路径点迁移：
   - 找到原路径点文件夹：`.minecraft\XaeroWaypoints\Multiplayer_example.com`
   - 复制该文件夹中的所有文件

3. 找到新路径点文件夹：`.minecraft\XaeroWaypoints\Multiplayer_game.rmsmcserver.ltd`
   - 删除该文件夹中的所有文件
   - 将之前复制的路径点文件粘贴进去

4. 地图文件迁移：
   - 找到原地图文件夹：`.minecraft\XaeroWorldMap\Multiplayer_example.com`
   - 复制该文件夹中的所有文件

5. 找到新地图文件夹：`.minecraft\XaeroWorldMap\Multiplayer_game.rmsmcserver.ltd`
   - 删除该文件夹中的所有文件
   - 将之前复制的地图文件粘贴进去