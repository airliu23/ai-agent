#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
BUG 存储层抽象模块
支持不同存储后端（文件系统、数据库等）
"""
import os
import json
import shutil
import datetime
from abc import ABC, abstractmethod
from typing import Dict, List, Optional


class BugStorage(ABC):
    """BUG 存储抽象基类，支持不同存储后端"""
    
    @abstractmethod
    def init(self) -> None:
        """初始化存储"""
        pass
    
    @abstractmethod
    def load_index(self) -> Dict[str, Dict[str, str]]:
        """加载 BUG 索引"""
        pass
    
    @abstractmethod
    def save_index(self, index: Dict[str, Dict[str, str]]) -> bool:
        """保存 BUG 索引"""
        pass
    
    @abstractmethod
    def save_bug(self, bug_id: str, content: str, index_entry: Dict[str, str]) -> str:
        """保存 BUG 记录，返回存储路径/标识"""
        pass
    
    @abstractmethod
    def get_bug(self, bug_id: str) -> Optional[str]:
        """获取 BUG 记录内容"""
        pass
    
    @abstractmethod
    def delete_bug(self, bug_id: str) -> bool:
        """删除 BUG 记录"""
        pass
    
    @abstractmethod
    def save_images(self, bug_id: str, image_paths: List[str]) -> List[str]:
        """保存图片到 BUG 记录目录，返回相对路径列表"""
        pass
    
    @abstractmethod
    def update_bug(self, bug_id: str, content: str, index_entry: Dict[str, str]) -> bool:
        """更新 BUG 记录"""
        pass
    
    @abstractmethod
    def append_progress(self, bug_id: str, progress_content: str) -> bool:
        """追加进展到 BUG 记录"""
        pass
    
    @abstractmethod
    def save_bug_content(self, bug_id: str, content: str) -> bool:
        """直接保存 BUG 记录内容（不更新索引）"""
        pass
    
    def generate_id(self) -> str:
        """生成唯一 BUG ID"""
        timestamp = datetime.datetime.now().strftime("%Y%m%d%H%M%S")
        return f"BUG_{timestamp}"


class FileStorage(BugStorage):
    """基于文件系统的存储实现"""
    
    def __init__(self, base_dir: str = "bug_records"):
        self.base_dir = base_dir
        self._index_path = os.path.join(base_dir, "bugs_index.json")
    
    def init(self) -> None:
        """初始化存储目录"""
        if not os.path.exists(self.base_dir):
            os.makedirs(self.base_dir)
    
    def load_index(self) -> Dict[str, Dict[str, str]]:
        """从 JSON 文件加载索引"""
        if os.path.exists(self._index_path):
            try:
                with open(self._index_path, 'r', encoding='utf-8') as f:
                    return json.load(f)
            except Exception:
                return {}
        return {}
    
    def save_index(self, index: Dict[str, Dict[str, str]]) -> bool:
        """保存索引到 JSON 文件"""
        try:
            with open(self._index_path, 'w', encoding='utf-8') as f:
                json.dump(index, f, ensure_ascii=False, indent=2)
            return True
        except Exception:
            return False
    
    def save_bug(self, bug_id: str, content: str, index_entry: Dict[str, str]) -> str:
        """保存 BUG 记录到 Markdown 文件"""
        file_path = os.path.join(self.base_dir, f"{bug_id}.md")
        with open(file_path, 'w', encoding='utf-8') as f:
            f.write(content)
        return file_path
    
    def get_bug(self, bug_id: str) -> Optional[str]:
        """读取 BUG 记录内容"""
        file_path = os.path.join(self.base_dir, f"{bug_id}.md")
        if not os.path.exists(file_path):
            return None
        with open(file_path, 'r', encoding='utf-8') as f:
            return f.read()
    
    def delete_bug(self, bug_id: str) -> bool:
        """删除 BUG 记录文件"""
        file_path = os.path.join(self.base_dir, f"{bug_id}.md")
        if os.path.exists(file_path):
            os.remove(file_path)
            return True
        return False
    
    def save_images(self, bug_id: str, image_paths: List[str]) -> List[str]:
        """复制图片到 BUG 记录目录，返回相对路径列表"""
        if not image_paths:
            return []
        
        # 创建图片目录
        images_dir = os.path.join(self.base_dir, "images", bug_id)
        if not os.path.exists(images_dir):
            os.makedirs(images_dir)
        
        # 获取已存在的图片数量，避免覆盖
        existing_count = len([f for f in os.listdir(images_dir) if f.startswith('img_')]) if os.path.exists(images_dir) else 0
        
        saved_paths = []
        for i, src_path in enumerate(image_paths, existing_count + 1):
            if not os.path.exists(src_path):
                continue
            
            # 获取文件扩展名
            ext = os.path.splitext(src_path)[1] or '.png'
            # 生成目标文件名
            dest_name = f"img_{i}{ext}"
            dest_path = os.path.join(images_dir, dest_name)
            
            # 复制文件
            shutil.copy2(src_path, dest_path)
            
            # 返回相对路径（用于 Markdown 引用）
            relative_path = f"images/{bug_id}/{dest_name}"
            saved_paths.append(relative_path)
        
        return saved_paths
    
    def save_files(self, bug_id: str, file_paths: List[str]) -> List[str]:
        """复制文本文件到 BUG 记录目录，返回相对路径列表"""
        if not file_paths:
            return []
        
        # 创建文件目录
        files_dir = os.path.join(self.base_dir, "files", bug_id)
        if not os.path.exists(files_dir):
            os.makedirs(files_dir)
        
        # 获取已存在的文件数量，避免覆盖
        existing_count = len([f for f in os.listdir(files_dir) if f.startswith('file_')]) if os.path.exists(files_dir) else 0
        
        saved_paths = []
        for i, src_path in enumerate(file_paths, existing_count + 1):
            if not os.path.exists(src_path):
                continue
            
            # 获取原始文件名和扩展名
            original_name = os.path.basename(src_path)
            ext = os.path.splitext(src_path)[1] or '.txt'
            # 生成目标文件名
            dest_name = f"file_{i}_{original_name}"
            dest_path = os.path.join(files_dir, dest_name)
            
            # 复制文件
            shutil.copy2(src_path, dest_path)
            
            # 返回相对路径和原始文件名（用于 Markdown 链接）
            relative_path = f"files/{bug_id}/{dest_name}"
            saved_paths.append((relative_path, original_name))
        
        return saved_paths
    
    def update_bug(self, bug_id: str, content: str, index_entry: Dict[str, str]) -> bool:
        """更新 BUG 记录"""
        file_path = os.path.join(self.base_dir, f"{bug_id}.md")
        if not os.path.exists(file_path):
            return False
        try:
            with open(file_path, 'w', encoding='utf-8') as f:
                f.write(content)
            return True
        except Exception:
            return False
    
    def append_progress(self, bug_id: str, progress_content: str) -> bool:
        """追加进展到 BUG 记录末尾"""
        file_path = os.path.join(self.base_dir, f"{bug_id}.md")
        if not os.path.exists(file_path):
            return False
        try:
            with open(file_path, 'a', encoding='utf-8') as f:
                f.write(progress_content)
            return True
        except Exception:
            return False
    
    def save_bug_content(self, bug_id: str, content: str) -> bool:
        """直接保存 BUG 记录内容（不更新索引）"""
        file_path = os.path.join(self.base_dir, f"{bug_id}.md")
        try:
            with open(file_path, 'w', encoding='utf-8') as f:
                f.write(content)
            return True
        except Exception:
            return False
