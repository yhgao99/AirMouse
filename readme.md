# Remote Touchpad & Keyboard
内部代号：feishu（飞鼠）

这是一个基于 Python 后端的轻量级远程控制工具，可将移动设备（Android/iOS）转化为电脑的：触控板、键盘、语音输入工具、宏按键面板。

<table style="border: none;">
  <tr style="border: none;">
    <td style="border: none;">
      <img src="img/Screenshot_20260120-225705.jpg" width="400">
    </td>
    <td style="border: none;">
      <img src="img/Screenshot_20260123-224640.jpg" width="400">
    </td>
    <td style="border: none;">
      <img src="img/Screenshot_20260121-210258.jpg" width="400">
    </td>
    <td style="border: none;">
      <img src="img/Screenshot_20260123-224503.jpg" width="400">
    </td>
  </tr>
</table>

2026 03 22
增加手柄映射功能
<img width="2274" height="1263" alt="image" src="https://github.com/user-attachments/assets/64ea98af-8477-4033-88f0-90103079fd03" />


## 🌟 项目亮点

### 1. 简单启动
python一键启动，无需安装手机客户端。

### 2. 触控操作

* **单指**：移动 / 左键单击。
* **双指**：滚动 / 右键单击。
* **三指**：拖拽 / 中键单击。
* **gyro**：陀螺仪飞鼠

并且有提供鼠标前进、后退、中键、上下滚轮的按钮。



## 🛠️ 要求

* **Python 3.x**

## 🚀 快速启动
> 1 安装python3.11 ， 2 双击直接启动 AirMouseserver.bat ，会自动检查依赖并以托盘形式启动服务器。  
> 3 如果需要控制高权限程序，需要使用管理员权限启动。
> 4 首次依赖检查成功后会生成 `deps_ok.txt`，之后启动会跳过耗时的包检查；需要重新检查时删除该文件即可。
> 5 托盘图标可打开主页；主页右上角“扫码连接”进入二维码页面。

 **安装依赖**：
```bash
pip install -r requirments.txt
```

 **运行服务端**：
```bash
python server.py
```




 **连接**：
确保手机与电脑在同一局域网，访问电脑 IP 的端口（默认 5888）。

从主页右上角进入扫码连接页；页面使用 qrcodejs CDN 在浏览器端生成二维码，不会在手机端安装任何应用。

例如： http://192.168.31.18:5888/ 

注意，浏览器会提示网页不安全，需要手工点进去信任，因为我们用的是自签的证书
> CHROME 浏览器安全限制，只有https网页才能传输陀螺仪数据。

---

## 📂 项目结构

* `server.py`: Python 后端逻辑，处理 Socket 信号并调用系统接口。
* `templates/index.html`: 触控板页面。
* `templates/keyboard.html`: 键盘输入页面。
* `templates/voice.html`: 语音输入页面。
* `macro.html`: 宏按键页面。
* `macro_config.json`: 宏按键配置文件。
---

## 🔧 调优说明
- 建议使用安卓手机+chrome浏览器。
- 虽然 ios  safari 浏览器也可以正常使用，但是鼠标的移动会变得卡卡的。

## 🍎 macOS 专属增强与开箱即用
已内置 macOS 深度原生适配，**无需手动修改任何代码**，在 Mac 上双击 `start.command` 即可一键开箱即用：
* **全套原生触控板手势**：
  * **双指捏合 / 张开**：原生平滑与阶梯缩放（Pinch to Zoom）
  * **双指双击**：智能缩放 / 重置缩放（Smart Zoom）
  * **双指旋拧**：顺时针 / 逆时针旋转 90°（Rotate）
  * **双指滑动**：2D 物理惯性滚动（支持加速度甩动滑行与触碰即停）
  * **三指拖动**：流畅框选文本与拖拽文件
  * **四指张开 (Spread)**：显示桌面（Show Desktop，直调 Dock 通道瞬间拨开所有窗口）
  * **四指捏合 (Pinch)**：开启 / 关闭启动台（Launchpad）
  * **四指下滑**：原生 App Exposé（展开当前活跃 App 名下所有窗口，直调 Dock 内部通道，零按键冲突）
  * **四指左右滑**：原生切屏（在各桌面与全屏应用间平滑切换，硬件级 HID 管道）
  * **四指上滑**：调度中心（Mission Control）
* **拟真触觉反馈**：Web Audio 清脆音效 + 多级微震动模拟（Taptic Engine 拟真体验）
* **移动端防息屏**：引入 Web Wake Lock API，手机触控板常亮不黑屏
* **底层兼容优化**：彻底解决 macOS 下 `pystray` 托盘崩溃及 `pynput` 按键兼容性问题

## 更新日志
### 2026-10-27 macOS 原生体验全面增强 (Mac Enhanced)
- [x] **全套原生缩放与旋转手势**：
  - 双指捏合 / 张开缩放（Pinch-to-zoom）：通用适配 Safari、Chrome、预览、访达、VSCode、Office、Maps、Figma 等
  - 双指旋拧旋转（Rotate）：顺时针 / 逆时针旋转 90°（看图与设计软件）
  - 双指双击智能缩放（Smart Zoom）：居中快速缩放 / 重置
- [x] **四指物理张开与捏合**：四指张开（显示桌面）、四指捏合（启动台）
- [x] **原生系统级手势**：四指下滑（App Exposé）、四指左右滑（切屏/全屏切换）、四指上滑（调度中心）、三指拖拽（文本与文件拖拽）
- [x] **CoreDock 底层通道对接**：无需模拟键盘按键，直通 Dock 守护进程，零冲突、免特殊权限
- [x] **2D 物理惯性滚动**：双指甩动带加速度滑行，手指触碰瞬间制动
- [x] **Taptic Engine 拟真触觉**：Web Audio 清脆微动音效与多级震动反馈
- [x] **移动端防息屏**：引入 Web Wake Lock API，手机触控板常亮不黑屏
- [x] **macOS 开箱即用**：自动适配 Mac 快捷键与自然滚动，修复主线程托盘冲突，新增 `start.command` 双击一键启动脚本
- [x] **语音输入体验优化**：分次输入模式下自动上屏并清空输入框

2026-01-23 Day3
- [x]  两个手指快速抬起导致识别成鼠标跳转修复
- [x]  “单指长按拖拽”功能
- [x]  将触控板逻辑提取为独立模块 `touchpad.js`，实现多页面同步更新


2026-01-21 Day2
- [x]  点击返回时强制清除所有长按功能，以防止影响触控
- [x]  飞鼠增加一些微小动作滤除，防手抖

- [x]  键盘上下左右 无效 另外位置也不舒服
- [x]  键盘del 按钮位置不对 应该在F12右边
- [x]  缺少printscreen 按钮
- [x]  缺少反斜杠按钮（在括号右边）

- [x]  输入条太小并不能实时语音上屏（之前让他实时上屏存在一点问题）
- [x]  或许我可以再搞个独立页面专门用来语音上屏,并且可以切换实时上屏和输入框模式
- [x]  记住gyro模式，如果之前是开启那么回到页面自动开启
- [x]  键盘模式默认就横过来展示，无视手机的方向（如果检测到是手机）
  
2026-01-21 Day1
- [x]  实现整体基础架构
- [x]  实现飞鼠功能还有鼠标控制功能以及三指拖动功能等
- [x]  实现键盘功能
