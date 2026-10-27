#!/bin/bash
set -e

DIR="$(cd "$(dirname "$0")" && pwd)"
cd "$DIR"

echo "=========================================="
echo "🍎 开始构建 AirMouse.app (macOS 原生应用)"
echo "=========================================="

# 1. 确保构建目录与图标存在
mkdir -p build
if [ ! -f "build/AppIcon.icns" ]; then
    echo "🎨 正在生成 macOS 原生应用图标 (AppIcon.icns)..."
    ./venv/bin/python -c "
import os, subprocess
from PIL import Image

src_img = Image.open('static/app-icon.png')
iconset_dir = 'build/AppIcon.iconset'
os.makedirs(iconset_dir, exist_ok=True)

sizes = [16, 32, 128, 256, 512]
for s in sizes:
    resized = src_img.resize((s, s), Image.LANCZOS)
    resized.save(f'{iconset_dir}/icon_{s}x{s}.png')
    if s <= 256:
        resized_2x = src_img.resize((s*2, s*2), Image.LANCZOS)
        resized_2x.save(f'{iconset_dir}/icon_{s}x{s}@2x.png')

subprocess.run(['iconutil', '-c', 'icns', iconset_dir, '-o', 'build/AppIcon.icns'], check=True)
"
    rm -rf build/AppIcon.iconset
fi

# 2. 调用 PyInstaller 根据 AirMouse.spec 打包
echo "📦 正在打包应用与依赖资源..."
./venv/bin/pyinstaller AirMouse.spec --noconfirm --clean

# 3. 对生成的 AirMouse.app 进行本地 Ad-hoc 代码签名
echo "🔐 正在进行本地代码签名..."
codesign --force --deep --sign - "dist/AirMouse.app"

# 4. 去除可能存在的隔离属性 (Quarantine)
xattr -cr "dist/AirMouse.app" 2>/dev/null || true

# 5. 压制生成 macOS DMG 分发安装镜像
echo "💿 正在压制 AirMouse.dmg 安装镜像..."
DMG_STAGING="build/dmg_staging"
rm -rf "$DMG_STAGING" "dist/AirMouse.dmg"
mkdir -p "$DMG_STAGING"

# 复制生成的 AirMouse.app 并建立 /Applications 快捷安装软链接
cp -R "dist/AirMouse.app" "$DMG_STAGING/"
ln -s /Applications "$DMG_STAGING/Applications"

# 使用 macOS 官方 hdiutil 压制高压缩只读 DMG
hdiutil create \
    -volname "AirMouse" \
    -srcfolder "$DMG_STAGING" \
    -ov \
    -format UDZO \
    "dist/AirMouse.dmg"

rm -rf "$DMG_STAGING"

echo "=========================================="
echo "🎉 全部构建完成！"
echo "   📱 原生应用: $DIR/dist/AirMouse.app"
echo "   💿 分发镜像: $DIR/dist/AirMouse.dmg"
echo "=========================================="
