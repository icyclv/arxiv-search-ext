import requests
import xml.etree.ElementTree as ET
from datetime import datetime, timedelta, timezone
import time
from typing import Set, Dict, Any, Optional, cast
import json
import base64
import os
from cryptography.hazmat.primitives import hashes, serialization
from cryptography.hazmat.primitives.asymmetric import padding, rsa

class ArxivCollector:
    def __init__(self, output_mode: str = 'local', api_service_url: Optional[str] = None, enable_signature: bool = False):
        self.base_url = "http://export.arxiv.org/api/query"
        self.output_mode = output_mode
        self.api_service_url = api_service_url
        self.processed_papers: Set[str] = set()
        self.enable_signature = enable_signature
        
        # 如果启用签名，则加载私钥
        if self.enable_signature and self.output_mode == 'api':
            private_key_str = os.getenv('ARXIV_IMPORT_PRIVATE_KEY')
            if not private_key_str:
                raise ValueError("ARXIV_IMPORT_PRIVATE_KEY environment variable is not set")
            self.private_key = self._load_private_key(private_key_str)

        # 如果输出模式为本地文件，确保输出目录存在
        if self.output_mode == 'local':
            self.output_dir = os.getenv('OUTPUT_DIR', 'output')
            os.makedirs(self.output_dir, exist_ok=True)
        
    def _load_private_key(self, private_key_str: str) -> rsa.RSAPrivateKey:
        """从字符串加载私钥"""
        try:
            private_key_bytes = private_key_str.encode('utf-8')
            private_key = serialization.load_pem_private_key(
                private_key_bytes,
                password=None
            )
            if not isinstance(private_key, rsa.RSAPrivateKey):
                raise ValueError("The provided key is not an RSA private key")
            return private_key
        except Exception as e:
            raise ValueError(f"Failed to load private key: {str(e)}")

    def _sign_request(self, request_body: bytes) -> str:
        """对请求体进行签名"""
        # 计算请求体的SHA256哈希
        digest = hashes.Hash(hashes.SHA256())
        digest.update(request_body)
        request_hash = digest.finalize()
        
        # 使用私钥对哈希值进行签名
        signature = self.private_key.sign(
            request_hash,
            padding.PKCS1v15(),
            hashes.SHA256()
        )
        
        # 将签名进行Base64编码
        return base64.b64encode(signature).decode('utf-8')

    def _format_date_range(self) -> str:
        """生成指定时间范围的查询字符串"""
        end_date = datetime.now(timezone.utc)
        # 从环境变量获取时间范围（小时），默认24小时
        hours = int(os.getenv('FETCH_HOURS', '24'))
        start_date = end_date - timedelta(hours=hours)
        
        return f"submittedDate:[{start_date.strftime('%Y%m%d%H%M')} TO {end_date.strftime('%Y%m%d%H%M')}]"

    def _parse_datetime(self, date_str: str) -> int:
        """将ISO格式的日期字符串转换为Unix时间戳"""
        dt = datetime.strptime(date_str, "%Y-%m-%dT%H:%M:%SZ")
        return int(dt.timestamp())
        
    def _safe_get_text(self, element: Optional[ET.Element]) -> Optional[str]:
        """安全地获取元素的文本内容"""
        if element is not None and element.text is not None:
            return element.text
        return None
        
    def _parse_response(self, response_text: str) -> tuple[list[Dict[str, Any]], int]:
        """解析API响应，返回论文列表和总结果数"""
        root = ET.fromstring(response_text)
        
        # 获取命名空间
        namespaces = {
            'atom': 'http://www.w3.org/2005/Atom',
            'opensearch': 'http://a9.com/-/spec/opensearch/1.1/',
            'arxiv': 'http://arxiv.org/schemas/atom'
        }
        
        # 获取总结果数
        total_results_elem = root.find('.//opensearch:totalResults', namespaces)
        total_results_text = self._safe_get_text(total_results_elem)
        if total_results_text is None:
            raise ValueError("Could not find total results in response")
        total_results = int(total_results_text)
        
        papers = []
        for entry in root.findall('.//atom:entry', namespaces):
            try:
                # 获取必需的字段
                id_elem = entry.find('atom:id', namespaces)
                title_elem = entry.find('atom:title', namespaces)
                summary_elem = entry.find('atom:summary', namespaces)
                published_elem = entry.find('atom:published', namespaces)
                
                # 获取文本内容
                id_text = self._safe_get_text(id_elem)
                title_text = self._safe_get_text(title_elem)
                summary_text = self._safe_get_text(summary_elem)
                published_text = self._safe_get_text(published_elem)
                
                # 检查必需字段是否都有值
                if not all([id_text, title_text, summary_text, published_text]):
                    continue
                
                # 由于我们已经检查了所有必需字段都有值，可以安全地使用类型转换
                id_str = cast(str, id_text)
                title_str = cast(str, title_text)
                summary_str = cast(str, summary_text)
                published_str = cast(str, published_text)
                
                # 解析arxiv_id并去掉版本号（如v1、v2等）
                arxiv_id = id_str.split('/')[-1].split('v')[0]
                
                # 如果论文已经处理过，跳过
                if arxiv_id in self.processed_papers:
                    continue
                    
                # 解析作者
                authors = []
                for author in entry.findall('atom:author', namespaces):
                    name_elem = author.find('atom:name', namespaces)
                    name_text = self._safe_get_text(name_elem)
                    if name_text is not None:
                        authors.append(name_text)
                
                # 如果没有作者信息，跳过
                if not authors:
                    continue
                
                # 解析分类
                categories = []
                for cat in entry.findall('atom:category', namespaces):
                    term = cat.get('term')
                    if term is not None:
                        categories.append(term)
                
                # 如果没有分类信息，跳过
                if not categories:
                    continue
                
                # 转换发布时间为Unix时间戳
                published_date = self._parse_datetime(published_str)
                
                paper = {
                    'arxiv_id': arxiv_id,
                    'title': title_str.strip(),
                    'authors': authors,
                    'abstract': summary_str.strip(),
                    'categories': categories,
                    'published_date': published_date
                }
                
                papers.append(paper)
                self.processed_papers.add(arxiv_id)
            except (AttributeError, TypeError, ValueError) as e:
                # 如果解析过程中出现任何问题，跳过该条目
                print(f"Error parsing entry: {str(e)}")
                continue
            
        return papers, total_results
    
    def _send_to_api_service(self, papers: list[Dict[str, Any]]) -> None:
        """发送论文数据到API服务"""
        if not self.api_service_url:
            print("Error: API service URL is not set")
            return

        try:
            # 准备请求数据
            request_data = {'papers': papers}
            request_body = json.dumps(request_data).encode('utf-8')
            
            # 准备请求头
            headers = {'Content-Type': 'application/json'}
            
            # 如果启用签名，添加签名头
            if self.enable_signature:
                signature = self._sign_request(request_body)
                headers['X-Signature'] = signature
            
            # 发送请求
            response = requests.post(
                self.api_service_url,
                data=request_body,
                headers=headers
            )
            response.raise_for_status()
            print(f"Successfully sent {len(papers)} papers to API service")
        except Exception as e:
            print(f"Failed to send papers to API service: {str(e)}")

    def _save_to_local(self, papers: list[Dict[str, Any]]) -> None:
        """保存论文数据到本地文件（JSONL格式）"""
        try:
            # 生成文件名，使用当前时间戳
            timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')
            filename = f"arxiv_papers_{timestamp}.jsonl"
            filepath = os.path.join(self.output_dir, filename)
            
            # 以JSONL格式保存数据
            with open(filepath, 'w', encoding='utf-8') as f:
                for paper in papers:
                    json.dump(paper, f, ensure_ascii=False)
                    f.write('\n')
            print(f"Successfully saved {len(papers)} papers to {filepath}")
        except Exception as e:
            print(f"Failed to save papers to local file: {str(e)}")

    def collect_papers(self) -> None:
        """收集最近一天的CS类别论文"""
        start = 0
        max_results = 100  # arXiv API建议的每页最大结果数
        
        while True:
            # 构建查询URL
            params = {
                'search_query': f"cat:cs.* AND {self._format_date_range()}",
                'start': start,
                'max_results': max_results,
                'sortBy': 'submittedDate',
                'sortOrder': 'descending'
            }
            
            try:
                # 发送请求
                response = requests.get(self.base_url, params=params)
                response.raise_for_status()
                
                # 解析响应
                papers, total_results = self._parse_response(response.text)
                
                # 根据输出模式处理数据
                if papers:
                    if self.output_mode == 'api':
                        self._send_to_api_service(papers)
                    else:
                        self._save_to_local(papers)
                
                # 检查是否需要继续获取下一页
                start += max_results
                if start >= total_results:
                    break
                    
                # arXiv API要求限制请求速率
                time.sleep(3)
                
            except Exception as e:
                print(f"Error occurred: {str(e)}")
                break

def main():
    # 从环境变量获取配置
    output_mode = os.getenv('OUTPUT_MODE', 'local').lower()  # 默认为本地文件模式
    enable_signature = os.getenv('ENABLE_SIGNATURE', '').lower() == 'true'
    api_service_url = os.getenv('API_SERVICE_URL', '')
    
    # 验证配置
    if output_mode not in ['api', 'local']:
        print("Error: OUTPUT_MODE must be either 'api' or 'local'")
        return
        
    if output_mode == 'api':
        if not api_service_url:
            print("Error: API_SERVICE_URL environment variable is not set")
            return
        if enable_signature and not os.getenv('ARXIV_IMPORT_PRIVATE_KEY'):
            print("Error: ARXIV_IMPORT_PRIVATE_KEY environment variable is not set")
            print("Please set it with your private key in PEM format:")
            print('export ARXIV_IMPORT_PRIVATE_KEY="-----BEGIN PRIVATE KEY-----\n...\n-----END PRIVATE KEY-----"')
            return

    # 创建收集器实例并运行
    collector = ArxivCollector(
        output_mode=output_mode,
        api_service_url=api_service_url if api_service_url else None,
        enable_signature=enable_signature
    )
    collector.collect_papers()

if __name__ == "__main__":
    main()
