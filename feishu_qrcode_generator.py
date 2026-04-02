#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
飞书多维表格对接脚本 - 生成小红书发布二维码
功能：读取飞书表格数据，为每条笔记生成二维码
"""

import requests
import qrcode
import json
import urllib.parse
from pathlib import Path
from PIL import Image, ImageDraw, ImageFont
import io

class FeishuXHSPublisher:
    """飞书小红书发布助手"""
    
    def __init__(self, app_id, app_secret, h5_base_url):
        """
        初始化
        :param app_id: 飞书应用ID
        :param app_secret: 飞书应用密钥
        :param h5_base_url: H5页面的基础URL (例如: https://yourdomain.com/xhs_publish.html)
        """
        self.app_id = app_id
        self.app_secret = app_secret
        self.h5_base_url = h5_base_url
        self.access_token = None
        
    def get_tenant_access_token(self):
        """获取飞书tenant_access_token"""
        url = "https://open.feishu.cn/open-apis/auth/v3/tenant_access_token/internal"
        headers = {"Content-Type": "application/json"}
        data = {
            "app_id": self.app_id,
            "app_secret": self.app_secret
        }
        
        response = requests.post(url, headers=headers, json=data)
        result = response.json()
        
        if result.get("code") == 0:
            self.access_token = result.get("tenant_access_token")
            print("✅ 飞书认证成功")
            return self.access_token
        else:
            raise Exception(f"❌ 飞书认证失败: {result}")
    
    def get_table_records(self, app_token, table_id, view_id=None):
        """
        读取飞书多维表格数据
        :param app_token: 多维表格的app_token
        :param table_id: 数据表ID
        :param view_id: 视图ID (可选)
        :return: 记录列表
        """
        if not self.access_token:
            self.get_tenant_access_token()
        
        url = f"https://open.feishu.cn/open-apis/bitable/v1/apps/{app_token}/tables/{table_id}/records"
        headers = {
            "Authorization": f"Bearer {self.access_token}",
            "Content-Type": "application/json"
        }
        
        params = {"page_size": 500}
        if view_id:
            params["view_id"] = view_id
        
        all_records = []
        has_more = True
        page_token = None
        
        while has_more:
            if page_token:
                params["page_token"] = page_token
            
            response = requests.get(url, headers=headers, params=params)
            result = response.json()
            
            if result.get("code") == 0:
                data = result.get("data", {})
                records = data.get("items", [])
                all_records.extend(records)
                
                has_more = data.get("has_more", False)
                page_token = data.get("page_token")
                
                print(f"📥 已读取 {len(all_records)} 条记录...")
            else:
                raise Exception(f"❌ 读取表格失败: {result}")
        
        print(f"✅ 共读取 {len(all_records)} 条记录")
        return all_records
    
    def parse_record(self, record):
        """
        解析单条记录
        :param record: 飞书记录
        :return: 解析后的数据字典
        """
        fields = record.get("fields", {})
        
        # 提取基本信息
        note_id = record.get("record_id", "")
        title = fields.get("标题", "") or fields.get("title", "")
        content = fields.get("正文", "") or fields.get("content", "") or fields.get("文案", "")
        
        # 处理图片 - 支持附件字段和URL字段
        images = []
        
        # 方式1: 附件字段
        image_attachments = fields.get("图片", []) or fields.get("images", [])
        if isinstance(image_attachments, list):
            for attachment in image_attachments:
                if isinstance(attachment, dict):
                    # 飞书附件格式
                    tmp_url = attachment.get("tmp_url") or attachment.get("url")
                    if tmp_url:
                        images.append(tmp_url)
        
        # 方式2: URL字段（逗号分隔或换行分隔）
        image_urls = fields.get("图片链接", "") or fields.get("image_urls", "")
        if isinstance(image_urls, str) and image_urls:
            # 支持逗号或换行分隔
            urls = [url.strip() for url in image_urls.replace('\n', ',').split(',')]
            images.extend([url for url in urls if url.startswith('http')])
        
        return {
            "id": note_id,
            "title": title,
            "content": content,
            "images": images
        }
    
    def generate_qrcode(self, note_data, output_path, with_label=True):
        """
        生成二维码
        :param note_data: 笔记数据
        :param output_path: 输出路径
        :param with_label: 是否添加标题标签
        """
        # 构建URL参数
        params = {
            "id": note_data["id"],
            "title": note_data["title"],
            "content": note_data["content"],
            "images": ",".join(note_data["images"])
        }
        
        # 生成完整URL
        full_url = f"{self.h5_base_url}?{urllib.parse.urlencode(params)}"
        
        # 生成二维码
        qr = qrcode.QRCode(
            version=1,
            error_correction=qrcode.constants.ERROR_CORRECT_H,
            box_size=10,
            border=2,
        )
        qr.add_data(full_url)
        qr.make(fit=True)
        
        # 创建二维码图片
        qr_img = qr.make_image(fill_color="black", back_color="white")
        
        if with_label:
            # 添加标题标签
            qr_img = self._add_label_to_qrcode(qr_img, note_data["title"], note_data["id"])
        
        # 保存
        qr_img.save(output_path)
        return output_path
    
    def _add_label_to_qrcode(self, qr_img, title, note_id):
        """为二维码添加标题标签"""
        # 转换为PIL Image
        if not isinstance(qr_img, Image.Image):
            qr_img = qr_img.convert('RGB')
        
        # 创建新画布（增加高度以容纳标题）
        qr_width, qr_height = qr_img.size
        new_height = qr_height + 100
        
        new_img = Image.new('RGB', (qr_width, new_height), 'white')
        new_img.paste(qr_img, (0, 0))
        
        # 添加文字
        draw = ImageDraw.Draw(new_img)
        
        try:
            # 尝试使用中文字体
            font_title = ImageFont.truetype("/System/Library/Fonts/PingFang.ttc", 20)
            font_id = ImageFont.truetype("/System/Library/Fonts/PingFang.ttc", 14)
        except:
            # 降级为默认字体
            font_title = ImageFont.load_default()
            font_id = ImageFont.load_default()
        
        # 标题（截断过长文字）
        title_display = title[:20] + "..." if len(title) > 20 else title
        
        # 计算文字位置（居中）
        bbox_title = draw.textbbox((0, 0), title_display, font=font_title)
        title_width = bbox_title[2] - bbox_title[0]
        title_x = (qr_width - title_width) // 2
        
        bbox_id = draw.textbbox((0, 0), f"ID: {note_id[:8]}", font=font_id)
        id_width = bbox_id[2] - bbox_id[0]
        id_x = (qr_width - id_width) // 2
        
        # 绘制文字
        draw.text((title_x, qr_height + 20), title_display, fill='black', font=font_title)
        draw.text((id_x, qr_height + 55), f"ID: {note_id[:8]}", fill='gray', font=font_id)
        
        return new_img
    
    def batch_generate(self, app_token, table_id, output_dir="qrcodes", view_id=None):
        """
        批量生成二维码
        :param app_token: 多维表格app_token
        :param table_id: 数据表ID
        :param output_dir: 输出目录
        :param view_id: 视图ID
        """
        # 创建输出目录
        output_path = Path(output_dir)
        output_path.mkdir(exist_ok=True)
        
        # 读取数据
        print("\n📖 正在读取飞书表格数据...")
        records = self.get_table_records(app_token, table_id, view_id)
        
        # 批量生成
        print(f"\n🎨 开始生成二维码...")
        generated = []
        
        for i, record in enumerate(records, 1):
            try:
                note_data = self.parse_record(record)
                
                # 跳过空记录
                if not note_data["title"] and not note_data["content"]:
                    print(f"⚠️  [{i}/{len(records)}] 跳过空记录")
                    continue
                
                # 生成文件名
                safe_title = "".join(c for c in note_data["title"][:20] if c.isalnum() or c in (' ', '-', '_'))
                filename = f"{i:03d}_{safe_title or note_data['id'][:8]}.png"
                output_file = output_path / filename
                
                # 生成二维码
                self.generate_qrcode(note_data, output_file)
                
                generated.append({
                    "file": str(output_file),
                    "title": note_data["title"],
                    "id": note_data["id"],
                    "image_count": len(note_data["images"])
                })
                
                print(f"✅ [{i}/{len(records)}] {note_data['title'][:30]} ({len(note_data['images'])}张图)")
                
            except Exception as e:
                print(f"❌ [{i}/{len(records)}] 生成失败: {e}")
        
        # 生成汇总报告
        report_path = output_path / "生成报告.json"
        with open(report_path, 'w', encoding='utf-8') as f:
            json.dump(generated, f, ensure_ascii=False, indent=2)
        
        print(f"\n🎉 完成！共生成 {len(generated)} 个二维码")
        print(f"📁 输出目录: {output_path.absolute()}")
        print(f"📊 详细报告: {report_path.absolute()}")
        
        return generated


# 使用示例
if __name__ == "__main__":
    # ============ 配置区域 ============
    
    # 飞书应用凭证（在飞书开放平台创建应用后获取）
    APP_ID = "你的飞书APP_ID"
    APP_SECRET = "你的飞书APP_SECRET"
    
    # H5页面地址（部署xhs_publish.html后的URL）
    H5_BASE_URL = "https://yourdomain.com/xhs_publish.html"
    
    # 多维表格信息
    APP_TOKEN = "你的多维表格app_token"  # 从URL中提取: https://xxx.feishu.cn/base/{app_token}
    TABLE_ID = "你的数据表ID"            # 从URL中提取或在表格设置中查看
    VIEW_ID = None                        # 可选：指定视图ID，留空则读取全部
    
    # =================================
    
    # 创建发布器实例
    publisher = FeishuXHSPublisher(APP_ID, APP_SECRET, H5_BASE_URL)
    
    # 批量生成二维码
    try:
        results = publisher.batch_generate(APP_TOKEN, TABLE_ID, output_dir="二维码输出", view_id=VIEW_ID)
        print("\n✨ 所有二维码已生成！现在可以：")
        print("   1. 打印二维码贴在对应手机上")
        print("   2. 或将二维码插入飞书文档中")
        print("   3. 扫码即可开始发布流程")
    except Exception as e:
        print(f"\n❌ 生成失败: {e}")
        print("\n请检查：")
        print("   1. 飞书应用凭证是否正确")
        print("   2. 多维表格app_token和table_id是否正确")
        print("   3. 是否已授权应用访问多维表格")
