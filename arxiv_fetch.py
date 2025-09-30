#!/usr/bin/env python3
"""
ArXiv Paper Collector

这个模块用于从 arXiv 获取最新的计算机科学论文。
支持将数据保存到本地文件或通过 API 发送到远程服务。

配置环境变量:
    ARXIV_OUTPUT_MODE: 输出模式 ('local' 或 'api')
    ARXIV_API_SERVICE_URL: API 服务地址 (当 OUTPUT_MODE 为 'api' 时必需)
    ARXIV_ENABLE_AUTH: 是否启用 API 认证 ('true' 或 'false')
    ARXIV_API_KEY: API 认证密钥 (当 ENABLE_AUTH 为 true 时必需)
    OUTPUT_DIR: 本地输出目录 (当 OUTPUT_MODE 为 'local' 时使用)
    FETCH_HOURS: 获取最近多少小时的论文 (默认: 96)
"""

import json
import logging
import os
import sys
import time
import xml.etree.ElementTree as ET
from datetime import datetime, timedelta, timezone
from typing import Dict, List, Optional, Set, Tuple, cast

import requests
from dotenv import load_dotenv

# 配置日志
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s',
    handlers=[logging.StreamHandler(sys.stdout)]
)
logger = logging.getLogger(__name__)

class Config:
    """配置管理类"""
    
    def __init__(self):
        load_dotenv()
        self.output_mode = os.getenv('ARXIV_OUTPUT_MODE', 'local').lower()
        self.enable_auth = os.getenv('ARXIV_ENABLE_AUTH', '').lower() == 'true'
        self.api_service_url = os.getenv('ARXIV_API_SERVICE_URL', '')
        self.output_dir = os.getenv('OUTPUT_DIR', './output')
        self.fetch_hours = int(os.getenv('FETCH_HOURS', '96'))
        self.api_key = os.getenv('ARXIV_API_KEY', '')

    def validate(self) -> None:
        """验证配置的有效性"""
        if self.output_mode not in ['api', 'local']:
            raise ValueError("ARXIV_OUTPUT_MODE must be either 'api' or 'local'")
            
        if self.output_mode == 'api':
            if not self.api_service_url:
                raise ValueError("ARXIV_API_SERVICE_URL is required when output mode is 'api'")
            if self.enable_auth and not self.api_key:
                raise ValueError("ARXIV_API_KEY is required when authentication is enabled")

class ArxivCollector:
    """arXiv 论文收集器"""

    def __init__(self, config: Config):
        """
        初始化收集器
        
        Args:
            config: 配置对象
        """
        self.config = config
        self.base_url = "http://export.arxiv.org/api/query"
        self.processed_papers: Set[str] = set()
        
        if self.config.output_mode == 'local':
            os.makedirs(self.config.output_dir, exist_ok=True)

    def _format_date_range(self) -> str:
        """生成指定时间范围的查询字符串"""
        end_date = datetime.now(timezone.utc)
        start_date = end_date - timedelta(hours=self.config.fetch_hours)
        return f"submittedDate:[{start_date.strftime('%Y%m%d%H%M')} TO {end_date.strftime('%Y%m%d%H%M')}]"

    @staticmethod
    def _parse_datetime(date_str: str) -> int:
        """将ISO格式的日期字符串转换为Unix时间戳"""
        dt = datetime.strptime(date_str, "%Y-%m-%dT%H:%M:%SZ")
        return int(dt.timestamp())
        
    @staticmethod
    def _safe_get_text(element: Optional[ET.Element]) -> Optional[str]:
        """安全地获取元素的文本内容"""
        return element.text if element is not None and element.text is not None else None

    def _parse_response(self, response_text: str) -> Tuple[List[Dict], int]:
        """
        解析API响应
        
        Args:
            response_text: API响应文本
            
        Returns:
            tuple: (论文列表, 总结果数)
        """
        root = ET.fromstring(response_text)
        namespaces = {
            'atom': 'http://www.w3.org/2005/Atom',
            'opensearch': 'http://a9.com/-/spec/opensearch/1.1/',
            'arxiv': 'http://arxiv.org/schemas/atom'
        }
        
        total_results_elem = root.find('.//opensearch:totalResults', namespaces)
        total_results = int(cast(str, self._safe_get_text(total_results_elem)))
        logger.info(f"Total results: {total_results}")
        
        papers = []
        for entry in root.findall('.//atom:entry', namespaces):
            try:
                paper = self._parse_entry(entry, namespaces)
                if paper:
                    papers.append(paper)
                    self.processed_papers.add(paper['arxiv_id'])
            except Exception as e:
                logger.error(f"Error parsing entry: {e}")
                continue
            
        return papers, total_results

    def _parse_entry(self, entry: ET.Element, namespaces: Dict[str, str]) -> Optional[Dict]:
        """
        解析单个论文条目
        
        Args:
            entry: 论文条目XML元素
            namespaces: XML命名空间
            
        Returns:
            Optional[Dict]: 解析后的论文数据，如果解析失败返回None
        """
        required_fields = {
            'id': entry.find('atom:id', namespaces),
            'title': entry.find('atom:title', namespaces),
            'summary': entry.find('atom:summary', namespaces),
            'published': entry.find('atom:published', namespaces)
        }
        
        # 检查必需字段
        if not all(self._safe_get_text(field) for field in required_fields.values()):
            return None
            
        # 解析作者
        authors = []
        for author in entry.findall('atom:author', namespaces):
            name = self._safe_get_text(author.find('atom:name', namespaces))
            if name:
                authors.append(name)
                
        if not authors:
            return None
            
        # 解析分类
        categories = []
        for cat in entry.findall('atom:category', namespaces):
            term = cat.get('term')
            if term:
                categories.append(term)
                
        if not categories:
            return None
            
        arxiv_id = cast(str, self._safe_get_text(required_fields['id'])).split('/')[-1].split('v')[0]
        
        return {
            'arxiv_id': arxiv_id,
            'title': cast(str, self._safe_get_text(required_fields['title'])).strip(),
            'authors': authors,
            'abstract': cast(str, self._safe_get_text(required_fields['summary'])).strip(),
            'categories': categories,
            'published_date': self._parse_datetime(cast(str, self._safe_get_text(required_fields['published'])))
        }

    def _send_to_api_service(self, papers: List[Dict]) -> None:
        """发送论文数据到API服务"""
        try:
            headers = {'Content-Type': 'application/json'}
            if self.config.enable_auth:
                headers['X-API-Key'] = self.config.api_key
            
            response = requests.post(
                self.config.api_service_url,
                data=json.dumps({'papers': papers}, separators=(',', ':')),
                headers=headers,
                timeout=90
            )
            response.raise_for_status()
            logger.info(f"Successfully sent {len(papers)} papers to API service")
        except Exception as e:
            logger.error(f"Failed to send papers to API service: {e}")
            raise

    def _save_to_local(self, papers: List[Dict]) -> None:
        """保存论文数据到本地文件"""
        try:
            timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')
            filepath = os.path.join(self.config.output_dir, f"arxiv_papers_{timestamp}.jsonl")
            
            with open(filepath, 'w', encoding='utf-8') as f:
                for paper in papers:
                    json.dump(paper, f, ensure_ascii=False)
                    f.write('\n')
            logger.info(f"Successfully saved {len(papers)} papers to {filepath}")
        except Exception as e:
            logger.error(f"Failed to save papers to local file: {e}")
            raise

    def collect_papers(self) -> None:
        """收集最近的CS类别论文"""
        start = 0
        max_results = 100
        
        while True:
            try:
                params = {
                    'search_query': f"cat:cs.* AND {self._format_date_range()}",
                    'start': start,
                    'max_results': max_results,
                    'sortBy': 'submittedDate',
                    'sortOrder': 'descending'
                }
                
                response = requests.get(self.base_url, params=params)
                response.raise_for_status()
                
                papers, total_results = self._parse_response(response.text)
                
                if papers:
                    if self.config.output_mode == 'api':
                        self._send_to_api_service(papers)
                    else:
                        self._save_to_local(papers)
                
                if start + max_results >= total_results:
                    break
                    
                start += max_results
                time.sleep(3)  # arXiv API 速率限制
                
            except Exception as e:
                logger.error(f"Error collecting papers: {e}")
                raise

def main() -> None:
    """主函数"""
    try:
        config = Config()
        config.validate()
        
        collector = ArxivCollector(config)
        collector.collect_papers()
    except Exception as e:
        logger.error(f"Application error: {e}")
        sys.exit(1)

if __name__ == "__main__":
    main()
